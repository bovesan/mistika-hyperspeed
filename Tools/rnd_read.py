#!/usr/bin/env python

import os
import sys
import time

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
'Group/D/WorkType' # 0
]

def aux_mistika_object_path(level_names):
        return '/'.join(level_names)

class load:
    def __init__(self, file_path, verbose=False):
        self.read_path(file_path, verbose)
    def read_path(self, file_path, verbose=False):
        self.header = {}
        self.associated_files = []
        level_names = []
        char_buffer = ''
        env_bytes_read = 0
        last_progress_update_time = 0
        env_size = os.path.getsize(file_path)
        for line in open(file_path):
            for char in line:
                env_bytes_read += 1
                time_now = time.time()
                if time_now - last_progress_update_time > 0.1:
                    last_progress_update_time = time_now
                    progress_float = float(env_bytes_read) / float(env_size)
                    #print progress_float
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
                    elif object_path.endswith('C/d/I/H/p'): # Clip media folder
                        CdIHp = char_buffer
                    elif object_path.endswith('C/d/I/s'): # Clip start frame
                        CdIs = int(char_buffer)
                    elif object_path.endswith('C/d/I/e'): # Clip end frame
                        CdIe = int(char_buffer)
                    elif object_path.endswith('C/d/I/H/n'): # Clip media name
                        f_path = CdIHp + char_buffer
                        #print 'C/d/I/H: ' + f_path
                    elif object_path.endswith('F/D'): # .dat file relative path (from projects_path)
                        #print 'F/D: ' + char_buffer
                        f_path = char_buffer
                    if object_path in header:
                        self.header[object_path.rsplit('/', 1)[-1]] = char_buffer
                        if verbose: print '%s: %s' % (object_path, char_buffer)
                    if f_path:
                        if not f_path in self.associated_files:
                            self.associated_files.append(f_path)
                        # if '%' in f_path:
                        #     for i in range(CdIs, CdIe+1):
                        #         files_chunk.append(f_path.replace(self.projects_path_local+'/', '') % i)
                    char_buffer = ''
                    del level_names[-1]
                    #level -= 1
                elif len(level_names) > 0 and level_names[-1] == 'Shape':
                    continue
                elif char:
                    char_buffer += char
        if len(self.associated_files) > 0:
            for associated_file in self.associated_files:
                if verbose: print 'Associated_file: %s' % associated_file
        #return output

if __name__ == "__main__":
    for file_path in sys.argv[1:]:
        print file_path
        #render = 
        load(file_path, True)