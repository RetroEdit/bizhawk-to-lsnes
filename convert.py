#!/usr/bin/env python3
"""
SNES BK2 to LSMV converter
Originally by TheMas3212
Ported to Python 3 and partially rewritten by RetroEdit
"""
import sys
import os
import zipfile
import hashlib
import json
import copy
try:
    from tqdm import tqdm
except ImportError:
    def tqdm(it):
        return it

bk2_path = sys.argv[1]
if not os.path.isfile(bk2_path):
    print('ERROR: File does not exist!')
    sys.exit(1)
bk2_abs = os.path.abspath(bk2_path)
if len(sys.argv) == 3:
    lsmv_path = sys.argv[2]
    lsmv_abs = os.path.abspath(lsmv_path)
else:
    lsmv_abs = os.path.splitext(bk2_abs)[0] + '.lsmv'

bk2 = zipfile.ZipFile(bk2_abs)
header = bk2.read('Header.txt').decode('latin_1')
header_dict = {}
for line in header.split('\n'):
    line = line.strip()
    if line:
        k, v = line.split(' ', 1)
        if k not in header_dict:
            header_dict[k] = v
if not header_dict['Platform'] == 'SNES':
    print('ERROR: Movie not for SNES, Quiting')
    sys.exit(1)

# Set basic settings
lsmv_dict = {
    'controlsversion': '0',
    'coreversion': 'bsnes v085 (Compatibility core)',
    'gametype': 'snes_ntsc',
    'systemid': 'lsnes-rr1',
    'setting.hardreset': '1',
    'authors': header_dict['Author'],
    'rom.hint': header_dict['GameName'],
    # RetroEdit: This looks arbitrary; it's probably "randomly" chosen
    'projectid': hashlib.md5(str(header_dict).encode('latin_1')).hexdigest()
}

# Controller Configuration
jsonfile = bk2.open('SyncSettings.json')
jsondict = json.load(jsonfile)
bh_controller = {'0': 'none','1': 'gamepad','2': 'multitap'}
try:
    lsmv_dict['port1'] = bh_controller[str(jsondict['o']['LeftPort'])]
except KeyError:
    lsmv_dict['port1'] = 'gamepad'
try:
    lsmv_dict['port2'] = bh_controller[str(jsondict['o']['RightPort'])]
except KeyError:
    lsmv_dict['port2'] = 'gamepad'

# RetroEdit: This whole section is bleh.
# Why are there these blocks of data?
# I think this code is wrong; I doubt the LSMV format works like this.
# Generate rrdata
rrlist = []
rrc16m = '\x7F\x00\xFE\xFE\xFE'
rrc1m = '\x7F\x00\x0E\xFE\xFE'
rrc65k = '\x5F\x00\xFE\xFE'
rrc4k = '\x5F\x00\x0E\xFE'
rrc256 = '\x3F\x00\xFE'
try:
    rrcount = int(header_dict['rerecordCount']) + 1
except KeyError:
    rrcount = 1
lsmv_dict['rerecords'] = str(rrcount)
while True:
    if rrcount >= 16777216:
        rrlist.append(rrc16m)
        rrcount = 0
    elif rrcount >= 1048576:
        rrlist.append(rrc1m)
        rrcount -= 1048576
    elif rrcount >= 65536:
        rrlist.append(rrc65k)
        rrcount -= 65536
    elif rrcount >= 4096:
        rrlist.append(rrc4k)
        rrcount -= 4096
    elif rrcount >= 256:
        rrlist.append(rrc256)
        rrcount -= 256
    elif rrcount > 1:
        rrlist.append('\x3F\x00' + chr(rrcount - 2))
        rrcount = 0
    elif rrcount == 1:
        rrlist.append('\x1F\x00')
        rrcount = 0
    elif rrcount <= 0:
        break
rrdata = ''.join(rrlist)
lsmv_dict['rrdata'] = rrdata

BK2_BTN  = 'UDLRsSYBXAlr'
LSMV_BTN = 'BYsSudlrAXLR'
NUM_BTN = len(LSMV_BTN)
REORDER_BTN = [
    LSMV_BTN.find(b.swapcase() if b in 'UDLR' else b)
    for i, b in
    enumerate(BK2_BTN)
]
BK2_SYS_BTN  = 'rP'
LSMV_SYS_BTN = 'RH'
NUM_SYS_BTN = len(BK2_SYS_BTN)

bk2_inputs = bk2.read('Input Log.txt').decode('latin_1').split('\n')
lsmv_inputs = [None] * len(bk2_inputs)
l = 0
for line in bk2_inputs:
    line = line.strip()
    if not line.startswith('|') or line == '':
        continue
    line_parts = line.split('|')[1:-1]
    for p, part in enumerate(line_parts):
        if len(part) == NUM_SYS_BTN:
            new_part = list('F..')
            # TODO: This code should probably be more generic
            if part[0] != '.':
                new_part[1] = 'R'
            elif part[1] != '.':
                new_part[2] = 'H'
        elif len(part) == NUM_BTN:
            new_part = ['.'] * NUM_BTN
            for i, b in enumerate(part):
                if b != '.':
                    # Could warn if b != BK2_BTN[i]
                    j = REORDER_BTN[i]
                    new_part[j] = LSMV_BTN[j]
        else:
            # TODO: need to warn under certain conditions
            continue
        line_parts[p] = ''.join(new_part)
    lsmv_inputs[l] = '|'.join(line_parts)
    l += 1
# Hack to efficiently remove trailing items off the end
while len(lsmv_inputs) > l:
    lsmv_inputs.pop()

# RetroEdit: This isn't the cleanest code to do this,
# but it's better than the string concatenation that happened before.
# 2. Do we want an extra newline at the end?
lsmv_dict['input'] = '\n'.join(lsmv_inputs)

# Creating the lsmv file
lsmv = zipfile.ZipFile(lsmv_abs, 'w')
for file_name, contents in lsmv_dict.items():
    lsmv.writestr(file_name, contents)
lsmv.close()
