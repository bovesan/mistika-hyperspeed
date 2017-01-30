#!/usr/bin/env python

import os
import sys
import time

description = """This program parses Mistika files of type .grp, .rnd, .fx, .lnk and .env."""

header = [
'Group/D/video', # 3
'Group/D/audio', # 0
'Group/D/numAudioChannels', # 0
'Group/D/NumPerFile', # 0
'Group/D/fields', # 0
'Group/D/FirstFrameIndex', # 242
'Group/D/MediaPath', # #, ##skisse_0000, ##vfx01, #/home/mistika/MATERIAL/DELIVERY/DI/[project]/[ext]/[renderName][_eye?Left, #Right]/[renderName][_segmentIndex]_[frameIndex%6].[ext]
'Group/D/AudioPath', # #, ##skisse_0000, ##vfx01, #/home/mistika/MATERIAL/DELIVERY/DI/[project]/[ext]/[renderName][_eye?Left, #Right]/[renderName][_segmentIndex].[ext]
'Group/D/tape', # A002_C045_12120U
'Group/D/Timecode', # 0
'Group/D/clipRecordTimecode', # 323@25
'Group/D/RenderProject', # TrondheimTorg
'Group/D/X', # 1920
'Group/D/Y', # 1080
'Group/D/JobFrameRate', # 25.000000
'Group/D/screenRatio', # 1.777778
'Group/D/lowResRatio', # 2
'Group/D/extendedRange', # 0
'Group/D/reduceFactor', # 2
'Group/D/btColorSpaceHD', # 1
'Group/D/DeleteBeforeRender', # 0
'Group/D/WorkType', # 0
'Group/D/L/d', # Disk.dev
'Group/D/L/f', # IMAGE.jpeg
'Group/D/L/e', # .jpg
'Group/D/L/i', # 0
'Group/D/H/d', # Disk.dev
'Group/D/H/f', # IMAGE.jpeg
'Group/D/H/e', # .jpg
'Group/D/H/i', # 0
]

def aux_mistika_object_path(level_names):
        return '/'.join(level_names)

def print_progress(progress_float):
    progress_percent = progress_float * 100.0
    sys.stdout.write("  %5.2f%%\r" % progress_percent)
    sys.stdout.flush()

class MistikaObject:
    def __init__(self, file_path, batch=True, header_only=False):
        self.read_path(file_path, batch, header_only)
    def read_path(self, file_path, batch=True, header_only=False):
        if not sys.stdout.isatty(): batch=True
        self.render_name = None
        self.group_name = None
        self.header = {}
        self.associated_files_dat = []
        self.associated_files_lnk = []
        self.associated_files_highres = []
        self.associated_files_lowres = []
        self.associated_files_audio = []
        level_names = []
        char_buffer = ''
        env_bytes_read = 0
        last_progress_update_time = time.time()
        env_size = os.path.getsize(file_path)
        for line in open(file_path):
            # time.sleep(0.01) # Debugging
            for char in line:
                env_bytes_read += 1
                if not batch:
                    time_now = time.time()
                    if time_now - last_progress_update_time > 0.1:
                        last_progress_update_time = time_now
                        progress_float = float(env_bytes_read) / float(env_size)
                        print_progress(progress_float)
                if char == '(':
                    #print ''
                    #level += 1
                    char_buffer = char_buffer.replace('\n', '').strip()
                    level_names.append(char_buffer)
                    #print ('-'*level ) + char_buffer + ':',
                    char_buffer = ''
                elif char == ')':
                    f_path = False
                    #print self.aux_mistika_object_path(level_names)
                    object_path = aux_mistika_object_path(level_names)
                    #print object_path
                    if object_path.endswith('C/F'): # Clip source link
                        #print 'C/F: ' + char_buffer
                        f_path = char_buffer
                        if not f_path in self.associated_files_lnk: self.associated_files_lnk.append(f_path)
                    elif object_path.endswith('C/d/I/L/p'): # Clip lowres folder
                        CdILp = char_buffer
                    elif object_path.endswith('C/d/I/H/p'): # Clip highres folder
                        CdIHp = char_buffer
                    elif object_path.endswith('C/d/S/p'): # Clip audio folder
                        CdSp = char_buffer
                    elif object_path.endswith('C/d/I/s'): # Clip start frame
                        CdIs = int(char_buffer)
                    elif object_path.endswith('C/d/I/e'): # Clip end frame
                        CdIe = int(char_buffer)
                    elif object_path.endswith('C/d/I/L/n'): # Clip lowres path
                        f_path = CdILp + char_buffer
                        if not f_path in self.associated_files_lowres: self.associated_files_lowres.append(f_path)
                    elif object_path.endswith('C/d/I/H/n'): # Clip highres path
                        f_path = CdIHp + char_buffer
                        if not f_path in self.associated_files_highres: self.associated_files_highres.append(f_path)
                        # if '%' in f_path:
                        #     for i in range(CdIs, CdIe+1):
                        #         files_chunk.append(f_path.replace(self.projects_path_local+'/', '') % i)
                    elif object_path.endswith('C/d/S/n'): # Clip audio path
                        f_path = CdSp + char_buffer
                        if not f_path in self.associated_files_audio: self.associated_files_audio.append(f_path)
                    elif object_path.endswith('F/D'): # .dat file relative path (from projects_path)
                        #print 'F/D: ' + char_buffer
                        f_path = char_buffer
                        if not f_path in self.associated_files_dat: self.associated_files_dat.append(f_path)
                    elif object_path.endswith('Group/p/n') and self.render_name == None:
                        self.render_name = char_buffer
                    elif object_path.endswith('Group/p/n') and self.group_name == None:
                        self.group_name = char_buffer
                        if '#' in self.group_name:
                            self.group_tags = self.group_name.split('#')
                            self.group_name = self.group_tags.pop(0)
                    if object_path in header:
                        self.header[object_path.rsplit('/', 1)[-1]] = char_buffer
                    char_buffer = ''
                    del level_names[-1]
                    if header_only and object_path == 'Group/D':
                        return True
                    #level -= 1
                elif len(level_names) > 0 and level_names[-1] == 'Shape':
                    continue
                elif char:
                    char_buffer += char
        #return output

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("mistika_object", nargs='+', help='One or more files to read')
    parser.add_argument("-a", "--all", help="Displays all available information (default)", action='store_true')
    parser.add_argument("-g", "--group", help="Display first group name", action='store_true')
    parser.add_argument("-q", "--header", help="Read and display header.", action='store_true')
    parser.add_argument("-b", "--batch", help="Do not print progress while parsing.", action='store_true')
    parser.add_argument("-d", "--dat", help="List associated .dat files", action='store_true')
    parser.add_argument("-c", "--source", help="List associated .clp and .lnk files", action='store_true')
    parser.add_argument("-i", "--image", help="List associated image files", action='store_true')
    parser.add_argument("-l", "--lowres", help="List associated lowres image files", action='store_true')
    parser.add_argument("-s", "--sound", help="List associated audio files", action='store_true')
    parser.add_argument("-f", "--files", help="List all associated files", action='store_true')
    args = parser.parse_args()
    header_only = not (args.group or args.files or args.all) and args.header
    args.all = not (args.header or args.group or args.files) or args.all
    for file_path in args.mistika_object:
        print 'structure: '+file_path
        structure = MistikaObject(file_path, args.batch, header_only)
        if args.group or args.all:
            print 'group_name:',
            if structure.group_name == None:
                print 'N/A'
            else:
                print structure.group_name
            if len(structure.group_tags) > 0:
                print 'tags: ',
                print ', '.join(structure.group_tags)
        if args.header or args.all:
            if len(structure.header) > 0:
                for key in structure.header.keys():
                    print 'header_%s: %s' % (key, structure.header[key])
        if args.files or args.all or args.links:
            if len(structure.associated_files_lnk) > 0:
                for associated_file in structure.associated_files_lnk:
                    print 'file_link: ' + associated_file
        if args.files or args.all or args.dat:
            if len(structure.associated_files_dat) > 0:
                for associated_file in structure.associated_files_dat:
                    print 'file_dat: ' + associated_file
        if args.files or args.all or args.highres:
            if len(structure.associated_files_highres) > 0:
                for associated_file in structure.associated_files_highres:
                    print 'file_highres: ' + associated_file
        if args.files or args.all or args.lowres:
            if len(structure.associated_files_lowres) > 0:
                for associated_file in structure.associated_files_lowres:
                    print 'file_lowres: ' + associated_file