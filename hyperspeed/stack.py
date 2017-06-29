#!/usr/bin/env python

import os
import time
import mistika

class Dependency(object):
    def __init__(self, name, f_type, start = False, end = False):
        self.name = name
        self.type = f_type
        self.start = start
        self.end = end
    def __str__(self):
        return self.name
    def __repr__(self):
        return self.name
    @property
    def path(self):
        if self.name.startswith('/'):
            return self.name
        elif self.type == 'dat':
            return os.path.join(mistika.projects_folder, self.name)
        elif self.type == 'glsl':
            return os.path.join(mistika.glsl_folder, self.name)
        else: # should not happen
            return self.name
    def check(self):
        return os.path.exists(self.path)

class Stack(object):
    def __init__(self, path):
        self.path = path
        self.size = os.path.getsize(self.path)
        self.ctime = os.path.getctime(self.path)
        self.read_header()
    def read_header(self):
        try:
            level_names = []
            fx_type = None
            char_buffer = ''
            char_buffer_store = ''
            for line in open(self.path):
                for char in line:
                    if char == '(':
                        char_buffer = char_buffer.replace('\n', '').strip()
                        level_names.append(char_buffer)
                        char_buffer = ''
                    elif char == ')':
                        f_path = False
                        object_path = '/'.join(level_names)
                        if object_path.endswith('D/RenderProject'):
                            self.project = char_buffer
                        elif object_path.endswith('D/X'):
                            self.resX = char_buffer
                        elif object_path.endswith('D/Y'):
                            self.resY = char_buffer
                        elif object_path.endswith('D/JobFrameRate'):
                            self.fps = char_buffer
                        elif object_path.endswith('p/W'):
                            self.frames = char_buffer
                        elif object_path.endswith('Group/p'): # End of header
                            return
                        char_buffer = ''
                        del level_names[-1]
                    elif len(level_names) > 0 and level_names[-1] == 'Shape':
                        continue
                    elif char:
                        char_buffer += char
        except IOError as e:
            print 'Could not open ' + self.path
            raise e


    @property
    def groupname(self):
        try:
            self._groupname
        except AttributeError:
            self.set_groupname()
        return self._groupname
    def set_groupname(self):
        try:
            level_names = []
            fx_type = None
            char_buffer = ''
            char_buffer_store = ''
            for line in open(self.path):
                for char in line:
                    if char == '(':
                        char_buffer = char_buffer.replace('\n', '').strip()
                        level_names.append(char_buffer)
                        char_buffer = ''
                    elif char == ')':
                        f_path = False
                        object_path = '/'.join(level_names)
                        if object_path.endswith('Group/Group/p/n'):
                            self._groupname = char_buffer
                            return
                        char_buffer = ''
                        del level_names[-1]
                    elif len(level_names) > 0 and level_names[-1] == 'Shape':
                        continue
                    elif char:
                        char_buffer += char
            self._groupname = False
        except IOError as e:
            print 'Could not open ' + self.path
            raise e
    @property
    def dependencies(self):
        try:
            self._dependencies
        except AttributeError:
            list(self.iter_dependencies())
        return self._dependencies
    def iter_dependencies(self, progress_callback=False):
        self._dependencies = []
        self._dependency_paths = []
        try:
            level_names = []
            fx_type = None
            char_buffer = ''
            char_buffer_store = ''
            env_bytes_read = 0
            last_progress_update_time = 0
            level = 0
            hidden_level = False
            for line in open(self.path):
                for char in line:
                    env_bytes_read += 1
                    time_now = time.time()
                    if time_now - last_progress_update_time > 0.1:
                        last_progress_update_time = time_now
                        progress_float = float(env_bytes_read) / float(self.size)
                        if progress_callback:
                            progress_callback(self, progress_float)
                    if char == '(':
                        char_buffer = char_buffer.replace('\n', '').strip()
                        level += 1
                        level_names.append(char_buffer)
                        char_buffer = ''
                    elif char == ')':
                        level -= 1
                        if hidden_level:
                            if hidden_level <= level:
                                char_buffer = ''
                                del level_names[-1]
                                continue
                            else:
                                hidden_level = False
                        f_path = False
                        object_path = '/'.join(level_names)
                        if object_path.endswith('F/T'):
                            fx_type = char_buffer
                        elif object_path.endswith('p/h'):
                            if bool(char_buffer):
                                hidden_level = level-2
                                # hidden_level = False # Because it is not working
                        elif object_path.endswith('C/F'): # Clip source link
                            f_path = char_buffer
                            f_type = 'lnk'
                        elif object_path.endswith('C/d/I/H/p'): # Clip media folder
                            CdIHp = char_buffer
                        elif object_path.endswith('C/d/I/s'): # Clip start frame
                            CdIs = int(char_buffer)
                        elif object_path.endswith('C/d/I/e'): # Clip end frame
                            CdIe = int(char_buffer)
                        elif object_path.endswith('C/d/I/H/n'): # Clip media name
                            f_path = CdIHp + char_buffer
                            f_type = 'media'
                        elif object_path.endswith('F/D'): # .dat file relative path (from projects_path)
                            f_path = char_buffer
                            f_type = 'dat'
                        elif fx_type == '146' and object_path.endswith('F/p/s/c/p/s'): # GLSL file
                            f_path = char_buffer
                            f_type = 'glsl'
                        if f_path:
                            if '%' in f_path:
                                dependency = Dependency(f_path, f_type, CdIs, CdIe)
                            else:
                                dependency = Dependency(f_path, f_type)
                            if not f_path in self._dependency_paths:
                                self._dependencies.append(dependency)
                                yield dependency
                        char_buffer = ''
                        del level_names[-1]
                    elif len(level_names) > 0 and level_names[-1] == 'Shape':
                        continue
                    elif char:
                        char_buffer += char
            if progress_callback:
                progress_callback(self, 1.0)
        except IOError as e:
            print 'Could not open ' + self.path
            raise e