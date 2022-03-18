#!/usr/bin/env python3

import argparse
import io
import platform
import re
import os
import subprocess
import sys

__version__ = '1.2'

# Usage:
# $ pwdumpstats.py <hashfile>
# $ pwdumpstats.py --pot john.pot pwdump.txt
# $ pwdumpstats.py -A --show pwdump.txt

# Class for coloured output
class col:
    if sys.stdout.isatty() and platform.system() != "Windows":
        green = '\033[32m'
        blue = '\033[94m'
        red = '\033[31m'
        brown = '\033[33m'
        grey = '\033[90m'
        end = '\033[0m'
    else:   # Colours mess up redirected or Windows output, disable them
        green = ""
        blue = ""
        red = ""
        brown = ""
        grey = ""
        end = ""

def print_percent(percent):
    percent = round(percent, 2)
    if percent == 0:
        out = col.end
    elif percent < 20:
        out = f'{col.green} ({str(percent)}%){col.end}'
    elif percent < 70:
        out = f'{col.brown} ({str(percent)}%{col.end}'
    else:
        out = f'{col.red} ({str(percent)}%{col.end}'
    return out

def mask(s):
    if args.mask:
        return s[:2] + '*' * (len(s) - 4) + s[-2:]
    else:
        return s


########
# Main #
########

parser = argparse.ArgumentParser('pwdumpstats.py', description='pwdumpstats version ' + __version__, formatter_class=lambda prog:argparse.HelpFormatter(prog,max_help_position=40))
parser.add_argument('--version', help="prints the current program version", action='version', version='%(prog)s '+__version__)
parser.add_argument('-f', '--filter', help='Filter users', dest='filter_file', required=False)
parser.add_argument('-H', '--history', help='Include password history hashes', action='store_true', default=False, dest='history', required=False)
parser.add_argument('-s', '--show', help='Show full re-use output', action='store_true', default=False, dest='show_full', required=False)
parser.add_argument('-a', '--admins', help='List admins', action='store_true', default=False, dest='show_admins', required=False)
parser.add_argument('-A', '--cracked-admins', help='List cracked admin accounts', action='store_true', default=False, dest='show_crackedadmins', required=False)
parser.add_argument('-n', '--noncomplex', help='List users with non-complex passwords', action='store_true', default=False, dest='show_noncomplex', required=False)
parser.add_argument('-E', '--empty', help='List users with empty passwords', action='store_true', default=False, dest='show_empty', required=False)
parser.add_argument('-c', '--cracked', help='Only print cracked hashes', action='store_true', default=False, dest='cracked_only', required=False)
parser.add_argument('-C', '--csv', help='CSV output for top 20', action='store_true', default=False, dest='csv_output', required=False)
parser.add_argument('-d', '--domain', help='Print domains', action='store_true', default=False, dest='domain', required=False)
parser.add_argument('-D', '--disabled', help='Include disabled accounts', action='store_true', default=False, dest='disabled', required=False)
parser.add_argument('-p', '--pot', help='Specify pot file (john or hashcat format)', dest='pot_file', required=False)
parser.add_argument('-m', '--mask', help='Mask passwords and hashes in output', action='store_true', default=False, dest='mask', required=False)
parser.add_argument('-l', '--lm', help='Show accounts with LM hashes', action='store_true', default=False, dest='show_lm', required=False)
parser.add_argument('-M', '--mindupecount', help='Don\'t show hashes with less that mindupecount users', type=int, default=False, dest='mindupecount', required=False)
parser.add_argument("files", nargs="+", help="Hash files")

# Usage
if len(sys.argv) < 2:
    parser.print_help()
    sys.exit(1)

args = parser.parse_args()

if args.filter_file:
    args.show_full = True

hashlist = []
filterlist = set()
crackedadmins = set()
admins = set()
pot = {}
users = {}
hashcount = {}
totaldupes = 0
usercount = 0
historycount = 0
crackedcount = 0
maxdupe = 0
noncomplex = []
empty = []
lmusers = []
lmhistory = []
userpass = []
administrators = []
domainadmins = []
enterpriseadmins = []

if args.filter_file:
    with io.open(args.filter_file, encoding="utf8", errors='replace') as infile:
        for line in infile:
            line = line.rstrip()
            filterlist.add(line)

if args.pot_file:
    pot_path = args.pot_file
else:
    common_paths = ['john.pot', '$JOHN/john.pot', '~/.john/john.pot', 'hashcat.potfile']
    for path in common_paths:
        path = os.path.expandvars(os.path.expanduser(path))
        if os.path.isfile(path):
            pot_path = path
            print(f'Using potfile: {pot_path}')
            break
    if not pot_path:
        print(f'{col.red}Could not find a pot file. Please specify one with --pot{col.end}')
        sys.exit(1)

try:
    with io.open(pot_path, encoding="utf8", errors='replace') as potfile:
        hashregex = re.compile('(^(\$NT\$)?([a-fA-F0-9]{32}):(.*)$)')
        for line in potfile:
            line = line.rstrip()
            m = hashregex.match(line)
            if m:
                hash = m.group(3).upper()
                pw = m.group(4)
                if hash == '31D6CFE0D16AE931B73C59D7E0C089C0':
                    pw = ""
                pot[hash] = pw
except IOError:
    print(f'{col.red}Could not open pot file: {pot_path}{col.end}')
    sys.exit(1)
if not pot:
    print(f"{col.red}[-] Pot doesn't contain any NTLM hashes{col.end}\n")


for filename in args.files:
    with io.open(filename, encoding="utf8", errors='replace') as userfile:
        for line in userfile:
            if not args.disabled:
                if "Disabled=1" in line or "Disabled=True" in line or ",Expired=True" in line:
                    continue
            line = line.rstrip()
            split = line.split(":")
            if len(split) == 7:     # pwdump format
                user = split[0]
                lmhash = split[2].upper()
                hash = split[3].upper().replace('$NT$', '')
            elif len(split) == 2:   # username : hash format
                user = split[0]
                hash = split[1].upper().replace('$NT$', '')
                lmhash = ''
            if user and hash:
                admin = 0
                if "__history_" in user:
                    if lmhash and not lmhash == "AAD3B435B51404EEAAD3B435B51404EE":
                        lmhistory.append(user)
                    historycount += 1
                    if not args.history:
                        continue
                else:
                    usercount += 1
                
                m2 = re.match('^(.*?)\\\(.*)', user)
                if m2:
                    if args.domain:
                        user = m2.group(0)              # Keep domain
                    else:
                        user = m2.group(2)              # Strip domain
                else:
                    m2 = re.match('^(.*?)@(.*)', user)
                    if m2:
                        user = m2.group(1)
                if lmhash and not lmhash == "AAD3B435B51404EEAAD3B435B51404EE":
                    lmusers.append(user)
                if ("IsAdministrator=True" in line or "isAdministrator=1" in line) and not "__history_" in user:
                    administrators.append(user)
                    admin = 1
                if ("IsDomainAdmin=True" in line or "isDomainAdmin=1" in line) and not "__history_" in user:
                    domainadmins.append(user)
                    admin = 1
                if ("IsEnterpriseAdmin=True" in line or "isEnterpriseAdmin=1" in line) and not "__history_" in user:
                    enterpriseadmins.append(user)
                    admin = 1
                users[user] = hash
                # Admin
                if admin == 1:
                    admins.add(user)
                if hash in pot:
                    crackedcount += 1
                    if args.domain:
                        if user.split('\\')[1] == pot[hash]:
                            userpass.append(user)
                    else:
                        if user == pot[hash]:
                            userpass.append(user)
                    # Complexity
                    if len(pot[hash]) == 0:
                        empty.append(user)
                    elif len(pot[hash]) < 8:
                        noncomplex.append(user)
                    else:
                        score = 0
                        if re.search("[A-Z]", pot[hash]):
                            score += 1
                        if re.search("[a-z]", pot[hash]):
                            score += 1
                        if re.search("[0-9]", pot[hash]):
                            score += 1
                        if pot[hash] and re.search("[^0-9a-zA-Z]", pot[hash]):
                            score += 1
                        if score < 3:
                            noncomplex.append(user)

                    # Admin
                    if admin == 1:
                        crackedadmins.add(f'{user}:{mask(pot[hash])}')

                if not args.filter_file or user.casefold() in map(str.lower, filterlist) :
                    hashlist.append(hash)

if not users:
        print(f"{col.red}[-] No hashes loaded from {' '.join(map(str, args.files))}{col.end}")
        sys.exit(1)

# Reverse the dictionary
hashlist_user = {}
for key, value in users.items():
    hashlist_user.setdefault(value, set()).add(key)

for hash,users in sorted(hashlist_user.items()):
    dupecount = len(users)
    if args.filter_file:
        if not set(map(str.casefold, users)) & set(map(str.lower, filterlist)):
            continue
    if dupecount == 1:
        continue
    if dupecount > maxdupe:
        maxdupe = dupecount
    totaldupes += dupecount
    hashcount[hash] = dupecount

for hash,count in sorted(hashcount.items(), key=lambda x: x[1], reverse=True):
    if args.show_full:
        if args.mindupecount:
            if count < args.mindupecount:
                continue
        users = hashlist_user[hash]
        if hash in pot:
            if pot[hash] == "":
                pw = f'{col.red}[empty]{col.end}'
                hash = mask(hash)
            else:
                pw = mask(pot[hash])
                hash = mask(hash)
            print(f'{col.green}{hash} : {pw}{col.blue} [{str(count)}]{col.end}')
        elif args.cracked_only:
            continue
        else:
            hash = mask(hash)
            print(f'{col.brown}{hash}{col.blue} [{str(count)}]{col.end}')
        usorted = sorted(users, key = lambda s: s.casefold())
        for user in usorted:
            if args.filter_file and user.casefold() in map(str.lower, filterlist):
                print(f'{col.red}{user}{col.end}') # Filtered users in red
            elif "__history_" in user.casefold():
                    print(f'{col.grey}{user}{col.end}')
            else:
                if user.casefold() in map(str.lower, admins):
                    print(f'{col.red}{user}{col.end}') # Admins in red
                else:
                    print(user)
        print("")


if args.show_full:
    if userpass and not args.filter_file:
        print(f'{col.red}[+] Username == Password {col.blue}[{str(len(userpass))}{col.end}')
        for user in sorted(userpass, key=lambda s: s.casefold()):
            print(user)
        print("")

if args.show_noncomplex and len(noncomplex) > 0:
    print(f'{col.red}[+] Non-complex Passwords ({str(len(noncomplex))}){col.end}')
    for user in sorted(noncomplex, key=lambda s: s.casefold()):
        print(user)
    print("")

if args.show_empty and len(empty) > 0:
    print(f'{col.red}[+] Empty Passwords ({str(len(empty))}){col.end}')
    for user in sorted(empty, key=lambda s: s.casefold()):
        print(user)
    print("")

if args.show_lm and len(lmusers) > 0:
    print(f'{col.red}[+] LM Hashes ({str(len(lmusers))}){col.end}')
    for user in sorted(lmusers, key=lambda s: s.casefold()):
        print(user)
    print("")

admins = set(administrators + domainadmins + enterpriseadmins)
if crackedadmins:
    crackedadminspercent = float(len(crackedadmins)) / float(len(admins)) * 100

if args.show_admins and len(admins) > 0:
    print(f'{col.red}[+] Admins ({str(len(admins))}){col.end}')
    for user in sorted(admins, key=lambda s: s.casefold()):
        print(user)
    print("")

if args.show_crackedadmins and len(crackedadmins) > 0:
    print(f'{col.red}[+] Cracked Admins ({str(len(crackedadmins))}){col.end}')
    for user in sorted(crackedadmins, key=lambda s: s.casefold()):
        print(user)
    print("")

top20 = 0
for hash,count in sorted(hashcount.items(), key=lambda x: x[1], reverse=True)[:20]:
    top20 += count

if args.history:
    totalcount = usercount + historycount
else:
    totalcount = usercount

dupepercent = float(totaldupes) / float(totalcount) * 100
maxdupepercent = float(maxdupe) / float(totalcount) * 100
crackedpercent = float(crackedcount) / float(totalcount) * 100
noncomplexpercent = float(len(noncomplex)) / float(totalcount) * 100
emptypercent = float(len(empty)) / float(totalcount) * 100
userpasspercent = float(len(userpass)) / float(totalcount) * 100
top20percent = float(top20) / float(totalcount) * 100
lmpercent = float(len(lmusers)) / float(totalcount) * 100



print(f'\n{col.brown}##############{col.end}')
print(f'{col.brown}# Statistics #{col.end}')
print(f'{col.brown}##############{col.end}\n')
if not args.filter_file:
    print(f'Users:                  {col.blue}{str(usercount)}{col.end}')
    print(f'LM Hashes (current):    {col.blue}{str(len(lmusers))}{print_percent(lmpercent)}{col.end}')
    print(f'LM Hashes (history):    {col.blue}{str(len(lmhistory))}{col.end}')
    print(f'History hashes:         {col.blue}{str(historycount)}{col.end}')
    print(f'Total hashes:           {col.blue}{str(totalcount)}{col.end}\n')
    print(f'Cracked passwords:      {col.blue}{str(crackedcount)}{print_percent(crackedpercent)}{col.end}')
    print(f'Non-complex passwords:  {col.blue}{str(len(noncomplex))}{print_percent(noncomplexpercent)}{col.end}')
    print(f'Empty passwords:        {col.blue}{str(len(empty))}{print_percent(emptypercent)}{col.end}\n')
    print(f'Duplicate passwords:    {col.blue}{str(totaldupes)}{print_percent(dupepercent)}{col.end}')
    print(f'Highest duplicate:      {col.blue}{str(maxdupe)}{print_percent(maxdupepercent)}{col.end}')
    print(f'Top 20 passwords:       {col.blue}{str(top20)}{print_percent(top20percent)}{col.end}\n')
    print(f'Username as password:   {col.blue}{str(len(userpass))}{print_percent(userpasspercent)}{col.end}\n')
else:
    print(f'Duplicate passwords:    {col.blue}{str(totaldupes)}{col.end}')
    print(f'Highest duplicate:      {col.blue}{str(maxdupe)}{col.end}\n')

if len(admins) > 0:
    print(f'Total admin accounts:   {col.blue}{str(len(admins))}{col.end}')
if crackedadmins:
    print(f'Cracked admin passwords {col.blue}{str(len(crackedadmins))}{print_percent(crackedadminspercent)}{col.end}')
if len(administrators) > 0:
    print(f'Administrators:         {col.blue}{str(len(administrators))}{col.end}')
if len(domainadmins) > 0:
    print(f'Domain Admins:          {col.blue}{str(len(domainadmins))}{col.end}')
if len(enterpriseadmins) > 0:
    print(f'Enterprise Admins       {col.blue}{str(len(enterpriseadmins))}{col.end}')


if top20:
        print(f'{col.brown}\nTop 20 hashes\n{col.end}')
        if args.csv_output:
            print("Count,Hash,Password")
        for hash,count in sorted(hashcount.items(), key=lambda x: x[1], reverse=True)[:20]:
            if hash in pot:
                if pot[hash] == "":
                    pw = f'{col.red}[empty]{col.end}'
                    hash = mask(hash)
                else:
                    pw = mask(pot[hash])
                    hash = mask(hash)
                if args.csv_output:
                    print(f'{str(count)},{hash},{pw}')
                else:
                    print(f'{str(count)}\t{hash}\t{pw}')
            else:
                hash = mask(hash)
                if args.csv_output:
                    print(f'{str(count)},{hash},[uncracked]')
                else:
                    print(f'{str(count)}\t{hash}\t{col.green}[uncracked]{col.end}')

if sys.stdout.isatty():
    print("")
