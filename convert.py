#!/usr/bin/env python2
import sys
import os
import zipfile
import hashlib
import json
import copy
from tqdm import tqdm

bk2_path = sys.argv[1]
if not os.path.isfile(bk2_path):
    print('ERROR: File does not exist!')
    sys.exit(1)
bk2_abs = os.path.abspath(bk2_path)
if len(sys.argv) == 3:
    lsmv_path = sys.argv[2]
    lsmv_abs = os.path.abspath(lsmv_path)
else:
    lsmv_abs = os.path.splitext(bk2_abs)[0]+'.lsmv'
bk2 = zipfile.ZipFile(bk2_abs)
header = bk2.open('Header.txt')
header_dict = {}
for line in iter(header):
    line = line.strip()
    if line == '':
        continue
    line_split = line.split(' ',1)
    header_dict[line_split[0]] = line_split[1]
if not header_dict['Platform'] == 'SNES':
    print('ERROR: Movie not for SNES, Quiting')
    sys.exit(1)

# Set basic settings
lsmv_dict = {}
lsmv_dict['controlsversion'] = '0'
lsmv_dict['coreversion'] = 'bsnes v085 (Compatibility core)'
lsmv_dict['gametype'] = 'snes_ntsc'
lsmv_dict['systemid'] = 'lsnes-rr1'
lsmv_dict['setting.hardreset'] = '1'
lsmv_dict['authors'] = header_dict['Author']
lsmv_dict['rom.hint'] = header_dict['GameName']
lsmv_dict['projectid'] = hashlib.md5(str(header_dict)).hexdigest()

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
while rrcount > 0:
    if rrcount >= 16777216:
        rrlist.append(rrc16m)
        rrcount = 0
        continue
    if rrcount >= 1048576:
        rrlist.append(rrc1m)
        rrcount -= 1048576
        continue
    if rrcount >= 65536:
        rrlist.append(rrc65k)
        rrcount -= 65536
        continue
    if rrcount >= 4096:
        rrlist.append(rrc4k)
        rrcount -= 4096
        continue
    if rrcount >= 256:
        rrlist.append(rrc256)
        rrcount -= 256
        continue
    if rrcount > 1:
        rrlist.append('\x3F\x00' + chr(rrcount - 2))
        rrcount = 0
        continue
    if rrcount == 1:
        rrlist.append('\x1F\x00')
        rrcount = 0
        continue
rrdata = ''.join(rrlist)
lsmv_dict['rrdata'] = rrdata

# Input Conversion
controller = {}
controller['A'] = {}
controller['B'] = {}
controller['X'] = {}
controller['Y'] = {}
controller['u'] = {}
controller['d'] = {}
controller['l'] = {}
controller['r'] = {}
controller['s'] = {}
controller['S'] = {}
controller['L'] = {}
controller['R'] = {}

input_data = {}
input_data['System'] = {'SoftReset': {}, 'HardReset': {}}
if lsmv_dict['port1'] == 'gamepad':
    input_data['Port1'] = {'P1': copy.deepcopy(controller)}
if lsmv_dict['port1'] == 'multitap':
    input_data['Port1'] = {'P1': copy.deepcopy(controller), 'P2': copy.deepcopy(controller), 'P3': copy.deepcopy(controller), 'P4': copy.deepcopy(controller)}
if lsmv_dict['port2'] == 'gamepad':
    input_data['Port2'] = {'P5': copy.deepcopy(controller)}
if lsmv_dict['port2'] == 'multitap':
    input_data['Port2'] = {'P5': copy.deepcopy(controller), 'P6': copy.deepcopy(controller), 'P7': copy.deepcopy(controller), 'P8': copy.deepcopy(controller)}

conmaps = {
'gamepadnone': ['System', ('Port1', 'P1')],
'nonegamepad': ['System', ('Port2', 'P5')],
'gamepadgamepad': ['System', ('Port1', 'P1'), ('Port2', 'P5')],
'multitapnone': ['System', ('Port1', 'P1'), ('Port1', 'P2'), ('Port1', 'P3'), ('Port1', 'P4')],
'nonemultitap': ['System', ('Port2', 'P5'), ('Port2', 'P6'), ('Port2', 'P7'), ('Port2', 'P8')],
'multitapgamepad': ['System', ('Port1', 'P1'), ('Port1', 'P2'), ('Port1', 'P3'), ('Port1', 'P4'), ('Port2', 'P5')],
'gamepadmultitap': ['System', ('Port1', 'P1'), ('Port2', 'P5'), ('Port2', 'P6'), ('Port2', 'P7'), ('Port2', 'P8')],
'multitapmultitap': ['System', ('Port1', 'P1'), ('Port1', 'P2'), ('Port1', 'P3'), ('Port1', 'P4'), ('Port2', 'P5'), ('Port2', 'P6'), ('Port2', 'P7'), ('Port2', 'P8')],
}
conmap = conmaps[str(lsmv_dict['port1'] + lsmv_dict['port2'])]

bk2_inputs = bk2.open('Input Log.txt')
frameNum = 0
for line in tqdm(iter(bk2_inputs), desc='processing bizhawk side'):
    frame = frameNum
    line = line.strip()
    if line[:1] != '|':
        continue
    if line == '':
        continue
    frame_inputs = line.split('|')
    del frame_inputs[0]
    frame_inputs.pop()
    if frame_inputs[-1] == '':
        frame_inputs.pop()
    
    # SYSTEM
    if frame_inputs[0][0] == 'r':
        input_data['System']['SoftReset'][frame] = True
    else:
        input_data['System']['SoftReset'][frame] = False
    if frame_inputs[0][1] == 'P':
        input_data['System']['HardReset'][frame] = True
    else:
        input_data['System']['HardReset'][frame] = False
    
    # CONTROLLERS
    for pNum in range(1,len(frame_inputs)):
        port = str(conmap[pNum][0])
        player = str(conmap[pNum][1])
        # Up Down Left Right
        if frame_inputs[pNum][0] == 'U':
            input_data[port][player]['u'][frame] = True
        else:
            input_data[port][player]['u'][frame] = False
        if frame_inputs[pNum][1] == 'D':
            input_data[port][player]['d'][frame] = True
        else:
            input_data[port][player]['d'][frame] = False
        if frame_inputs[pNum][2] == 'L':
            input_data[port][player]['l'][frame] = True
        else:
            input_data[port][player]['l'][frame] = False
        if frame_inputs[pNum][3] == 'R':
            input_data[port][player]['r'][frame] = True
        else:
            input_data[port][player]['r'][frame] = False
        # A B X Y
        if frame_inputs[pNum][9] == 'A':
            input_data[port][player]['A'][frame] = True
        else:
            input_data[port][player]['A'][frame] = False
        if frame_inputs[pNum][7] == 'B':
            input_data[port][player]['B'][frame] = True
        else:
            input_data[port][player]['B'][frame] = False
        if frame_inputs[pNum][8] == 'X':
            input_data[port][player]['X'][frame] = True
        else:
            input_data[port][player]['X'][frame] = False
        if frame_inputs[pNum][6] == 'Y':
            input_data[port][player]['Y'][frame] = True
        else:
            input_data[port][player]['Y'][frame] = False
        # Select Start LBump RBump
        if frame_inputs[pNum][4] == 's':
            input_data[port][player]['s'][frame] = True
        else:
            input_data[port][player]['s'][frame] = False
        if frame_inputs[pNum][5] == 'S':
            input_data[port][player]['S'][frame] = True
        else:
            input_data[port][player]['S'][frame] = False
        if frame_inputs[pNum][10] == 'l':
            input_data[port][player]['L'][frame] = True
        else:
            input_data[port][player]['L'][frame] = False
        if frame_inputs[pNum][11] == 'r':
            input_data[port][player]['R'][frame] = True
        else:
            input_data[port][player]['R'][frame] = False
    frameNum = frameNum + 1
totalFrames = frameNum - 1

# Generate lsnes Inputfile
lsmv_dict['input'] = str()
for frameNum in tqdm(range(totalFrames), desc='lsnes side'):
    frameStr = 'F'
    if input_data['System']['SoftReset'][frameNum]:
        frameStr += 'R'
    else:
        frameStr += '.'
    if input_data['System']['HardReset'][frameNum]:
        frameStr += 'H'
    else:
        frameStr += '.'
    frameStr += '|'
    for pNum in range(1,5):
        player = 'P' + str(pNum)
        port = 'Port1'
        if player in input_data[port]:
            # B Y Select Start
            if input_data[port][player]['B'][frameNum]:
                frameStr += 'B'
            else:
                frameStr += '.'
            if input_data[port][player]['Y'][frameNum]:
                frameStr += 'Y'
            else:
                frameStr += '.'
            if input_data[port][player]['s'][frameNum]:
                frameStr += 's'
            else:
                frameStr += '.'
            if input_data[port][player]['S'][frameNum]:
                frameStr += 'S'
            else:
                frameStr += '.'
            # Up Down Left Right
            if input_data[port][player]['u'][frameNum]:
                frameStr += 'u'
            else:
                frameStr += '.'
            if input_data[port][player]['d'][frameNum]:
                frameStr += 'd'
            else:
                frameStr += '.'
            if input_data[port][player]['l'][frameNum]:
                frameStr += 'l'
            else:
                frameStr += '.'
            if input_data[port][player]['r'][frameNum]:
                frameStr += 'r'
            else:
                frameStr += '.'
            # A X LBump RBump
            if input_data[port][player]['A'][frameNum]:
                frameStr += 'A'
            else:
                frameStr += '.'
            if input_data[port][player]['X'][frameNum]:
                frameStr += 'X'
            else:
                frameStr += '.'
            if input_data[port][player]['L'][frameNum]:
                frameStr += 'L'
            else:
                frameStr += '.'
            if input_data[port][player]['R'][frameNum]:
                frameStr += 'R'
            else:
                frameStr += '.'
            frameStr += '|'
    for pNum in range(5,9):
        player = 'P' + str(pNum)
        port = 'Port2'
        if player in input_data[port]:
            # B Y Select Start
            if input_data[port][player]['B'][frameNum]:
                frameStr += 'B'
            else:
                frameStr += '.'
            if input_data[port][player]['Y'][frameNum]:
                frameStr += 'Y'
            else:
                frameStr += '.'
            if input_data[port][player]['s'][frameNum]:
                frameStr += 's'
            else:
                frameStr += '.'
            if input_data[port][player]['S'][frameNum]:
                frameStr += 'S'
            else:
                frameStr += '.'
            # Up Down Left Right
            if input_data[port][player]['u'][frameNum]:
                frameStr += 'u'
            else:
                frameStr += '.'
            if input_data[port][player]['d'][frameNum]:
                frameStr += 'd'
            else:
                frameStr += '.'
            if input_data[port][player]['l'][frameNum]:
                frameStr += 'l'
            else:
                frameStr += '.'
            if input_data[port][player]['r'][frameNum]:
                frameStr += 'r'
            else:
                frameStr += '.'
            # A X LBump RBump
            if input_data[port][player]['A'][frameNum]:
                frameStr += 'A'
            else:
                frameStr += '.'
            if input_data[port][player]['X'][frameNum]:
                frameStr += 'X'
            else:
                frameStr += '.'
            if input_data[port][player]['L'][frameNum]:
                frameStr += 'L'
            else:
                frameStr += '.'
            if input_data[port][player]['R'][frameNum]:
                frameStr += 'R'
            else:
                frameStr += '.'
            frameStr += '|'
    #print(frameStr[:-1])
    frameStr = frameStr[:-1] + "\n"
    lsmv_dict['input'] += frameStr

# Creating the lsmv file
lsmv = zipfile.ZipFile(lsmv_abs, 'w')
for file in iter(lsmv_dict):
    lsmv.writestr(file, lsmv_dict[file])
lsmv.close()