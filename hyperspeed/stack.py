#!/usr/bin/env python

import os
import time

class Stack:
    def __init__(self, path):
        self.path = path
        self.size = os.path.getsize(self.path)
        self._dependencies = None
    @property
    def dependencies(self):
        if self._dependencies == None:
            self._dependencies = list(self.iter_dependencies())
        return self._dependencies
    def iter_dependencies(self):
        self.dependencies = []
        try:
            level_names = []
            fx_type = None
            char_buffer = ''
            char_buffer_store = ''
            env_bytes_read = 0
            last_progress_update_time = 0
            for line in open(self.path):
                for char in line:
                    env_bytes_read += 1
                    time_now = time.time()
                    if time_now - last_progress_update_time > 0.1:
                        last_progress_update_time = time_now
                        progress_float = float(env_bytes_read) / float(self.size)
                    if char == '(':
                        char_buffer = char_buffer.replace('\n', '').strip()
                        level_names.append(char_buffer)
                        char_buffer = ''
                    elif char == ')':
                        f_path = False
                        object_path = '/'.join(level_names)
                        if object_path.endswith('F/T'):
                            fx_type = char_buffer
                        elif object_path.endswith('C/F'): # Clip source link
                            f_path = char_buffer
                        elif object_path.endswith('C/d/I/H/p'): # Clip media folder
                            CdIHp = char_buffer
                        elif object_path.endswith('C/d/I/s'): # Clip start frame
                            CdIs = int(char_buffer)
                        elif object_path.endswith('C/d/I/e'): # Clip end frame
                            CdIe = int(char_buffer)
                        elif object_path.endswith('C/d/I/H/n'): # Clip media name
                            f_path = CdIHp + char_buffer
                        elif object_path.endswith('F/D'): # .dat file relative path (from projects_path)
                            f_path = char_buffer
                        elif fx_type == '146' and object_path.endswith('F/p/s/c/p/s'): # GLSL file
                            f_path = char_buffer
                        if f_path:
                            if '%' in f_path:
                                f_tuple = (f_path, CdIs, CdIe)
                                self.dependencies.append(f_tuple)
                                yield f_tuple
                            else:
                                self.dependencies.append(f_path)
                                yield f_path
                        char_buffer = ''
                        del level_names[-1]
                    elif len(level_names) > 0 and level_names[-1] == 'Shape':
                        continue
                    elif char:
                        char_buffer += char
        except IOError as e:
            print 'Could not open ' + self.path
            raise e