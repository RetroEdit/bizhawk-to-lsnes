#!/usr/bin/env python2
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
lsmv_dict = {
    'controlsversion': '0',
    'coreversion': 'bsnes v085 (Compatibility core)',
    'gametype': 'snes_ntsc',
    'systemid': 'lsnes-rr1',
    'setting.hardreset': '1',
    'authors': header_dict['Author'],
    'rom.hint': header_dict['GameName'],
    'projectid': hashlib.md5(str(header_dict)).hexdigest()
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
for button_name in 'ABXYudlrsSLR':
    controller[button_name] = {}

# RetroEdit: This is a fundamentally bad way to structure it.
# deepcopy should be unnecessary here.
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

device_num_controllers = {'none': 0, 'gamepad': 1, 'multitap': 4}
def get_conmap(port_num, device):
    pnum_offset = 0
    if port_num == 2:
        pnum_offset = 4
    return [
        ('Port' + str(port_num), 'P' + str(pnum_offset + pnum))
        for pnum in range(device_num_controllers[device])
    ]
conmap = ['System'] + get_conmap(1, lsmv_dict['port1']) + get_conmap(2, lsmv_dict['port2'])

bk2_inputs = bk2.open('Input Log.txt')
for frame, line in tqdm(enumerate(bk2_inputs), desc='processing bizhawk side'):
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
# RetroEdit: Bad
totalFrames = frame - 1

# Generate lsnes Inputfile

# RetroEdit: Probably revise this later.
BUTTONS = 'BYsSudlrAXLR'
NUM_BUTTONS = len(BUTTONS)
CLEAR_BUTTON_BLOCK = '.' * NUM_BUTTONS
NUM_PLAYERS = 8

lsmv_dict['input'] = []
for frameNum in tqdm(range(totalFrames), desc='lsnes side'):
    input_start = 'F..|'
    # RetroEdit: Still a bit questionable, but better.
    if input_data['System']['SoftReset'][frameNum]:
        input_start[1] = 'R'
    if input_data['System']['HardReset'][frameNum]:
        input_start[2] = 'H'
    player_inputs = []
    for p_num in range(1, NUM_PLAYERS + 1):
        player = 'P' + str(p_num)
        if p_num < 5:
            port = 'Port1'
        else:
            port = 'Port2'
        if player in input_data[port]:
            button_block = CLEAR_BUTTON_BLOCK
            for i, button_name in enumerate(BUTTONS):
                if input_data[port][player][button_name][frameNum]:
                    button_block[i] = button_name
            player_inputs.append(button_block)

    frame_str = input_start + '|'.join(player_inputs)
    # print(frame_str)
    lsmv_dict['input'].append(frame_str)

# RetroEdit: This isn't the cleanest code to do this,
# but it's better than the string concatenation that happened before.
# 2. Do we want an extra newline at the end?
lsmv_dict['input'] = '\n'.join(lsmv_dict['input'])

# Creating the lsmv file
lsmv = zipfile.ZipFile(lsmv_abs, 'w')
for file_name, contents in lsmv_dict.items():
    lsmv.writestr(file, contents)
lsmv.close()
