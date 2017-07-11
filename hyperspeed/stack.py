#!/usr/bin/env python

import os
import time
import mistika

class DependencyType(object):
    def __init__(self, id, description):
        self.id = id
        self.description = description
    def __str__(self):
        return self.id
    def __repr__(self):
        return self.id + ' ' + self.description

DEPENDENCY_TYPES = {
    'dat' : DependencyType('dat', '.dat files'),
    'glsl' : DependencyType('glsl', 'GLSL filters'),
    'lut' : DependencyType('lut', 'Look-up-tables'),
    'highres' : DependencyType('highres', 'Highres media'),
    'lowres' : DependencyType('lowres', 'Proxy media'),
    'audio' : DependencyType('audio', 'Audio files'),
    'lnk' : DependencyType('lnk', 'Media links'),
    'font' : DependencyType('font', 'Fonts'),
}
class DependencyFrameRange(object):
    def __init__(self, path, start = False, end = False, delete_callback = None):
        self.path = path
        self.start = start
        self.end = end
        self._size = False
        self.complete = True
        self.row_references = []
        self.delete_callback = delete_callback
    @property
    def size(self):
        if not self._size:
            self._size = 0
            for i in range(self.start, self.end+1):
                try:
                    self._size += os.path.getsize(self.path % i)
                except OSError:
                    self.complete = False
        return self._size

    def delete(self,*args,**kwargs):
        self.delete_callback(self)
        super(DependencyFrameRange, self).delete(*args,**kwargs)

class Dependency(object):
    def __init__(self, name, f_type, start = False, end = False):
        self.name = name
        self.type = f_type
        self.start = min(start, end)
        self.end = max(start, end)
        self.ignore = False
        self.parents = []
        self._path = False
        self._size = False
        self.raw_frame_ranges = [(start, end)]
        self.frame_ranges = [DependencyFrameRange(self.path, start, end)]
        self._parsed_frame_ranges = None
        self.complete = True
    def __str__(self):
        return self.name
    def __repr__(self):
        return self.name
    @property
    def path(self):
        if not self._path:
            if self.name.startswith('/'):
                self._path = self.name
            elif self.type == 'dat':
                self._path = os.path.join(mistika.projects_folder, self.name)
            elif self.type in ['glsl', 'lut']:
                if self.name.startswith('/'):
                    self._path = self.name
                else:
                    self._path = os.path.join(mistika.env_folder, self.name)
            else: # should not happen
                self._path = self.name
        return self._path
    def frames_range_add(self, start, end):
        self.raw_frame_ranges.append(start, end)
        self.frame_ranges.append(DependencyFrameRange(self.path, start, end))
    @property
    def frames(self):
        if True or self._parsed_frame_ranges != self.frame_ranges:
            self.frame_ranges = sorted(self.frame_ranges, key=lambda frame_range: frame_range.start)
            i = 0
            while i < len(self.frame_ranges):
                if i > 0 and self.frame_ranges[i].start <= self.frame_ranges[i-1].end:
                     self.frame_ranges[i-1].end = self.frame_ranges[i].end
                     del(self.frame_ranges[i])
                     i -= 1
                i += 1
            self._parsed_frame_ranges = self.frame_ranges
        return self.frame_ranges
    @property
    def size(self):
        if not self._size:
            if '%' in self.path:
                self._size = 0
                for frame_range in self.frame_ranges:
                    if frame_range.size > 0:
                        self._size += frame_range.size
                    else:
                        self.complete = False
            else:
                try:
                    self._size = os.path.getsize(self.path)
                except OSError:
                    self._size = None
        return self._size
    def check(self):
        return os.path.exists(self.path)

class Stack(object):
    def __init__(self, path):
        self.path = path
        self.size = os.path.getsize(self.path)
        self.dependencies_size = None
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
                            f_type = 'highres'
                        elif object_path.endswith('F/D'): # .dat file relative path (from projects_path)
                            f_path = char_buffer
                            f_type = 'dat'
                        elif fx_type == '146':
                            f_type = 'glsl'
                            if object_path.endswith('F/p/s/c/c'):
                                f_folder = char_buffer
                            elif object_path.endswith('F/p/s/c/E/s'):
                                f_path = f_folder + '/' + char_buffer
                        elif fx_type == '143':
                            f_type = 'lut'
                            if object_path.endswith('F/p/s/c/c'):
                                f_folder = char_buffer
                            elif object_path.endswith('F/p/s/c/F/s'):
                                f_path = f_folder + '/' + char_buffer
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