#!/usr/bin/env python

import os
import time
import mistika
import text
import threading
import tempfile
import copy

def escape_par(string):
    return string.replace('(', '\(').replace(')', '\)')
class DependencyType(object):
    def __init__(self, id, description):
        self.id = id
        self.description = description
        self.meta = {}
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
    def __init__(self, path, start = False, end = False, parent=None, delete_callback = None):
        self.path = path
        self.start = start
        self.end = end
        self.parent = parent
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
        if self.delete_callback != None:
            self.delete_callback(self)
        super(DependencyFrameRange, self).delete(*args,**kwargs)

class Dependency(object):
    def __init__(self, name, f_type, start = False, end = False, parent=None):
        self.lock = threading.Lock()
        with self.lock:
            self.name = name
            self.type = f_type
            self.start = min(start, end)
            self.end = max(start, end)
            self.ignore = False
            self.parents = [parent]
            self.dependencies = [] # Used for .dat files with font dependencies etc.
            self._path = False
            self._size = False
            self.row_reference = None
            # self.raw_frame_ranges = [(start, end, parent)]
            self.frame_ranges = [DependencyFrameRange(self.path, start, end, parent)]
            self._parsed_frame_ranges = None
            self._complete = None
            if f_type == 'dat':
                for font in text.Title(self.path).fonts:
                    self.dependencies.append(Dependency(font, 'font', parent=parent))
    def __str__(self):
        return self.name
    def __repr__(self):
        return self.name
    def parent_remove(self, parent):
        i = 0
        while i < len(self.frame_ranges):
            if self.frame_ranges[i].parent == parent:
                del self.frame_ranges[i]
                continue
            i += 1
        if parent in self.parents:
            self.parents.remove(parent)
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
            elif self.type == 'font':
                if self.name in mistika.fonts:
                    self._path = mistika.fonts[self.name]
                else:
                    self._path = self.name
                    self._size = None
            else: # should not happen
                self._path = self.name
        return self._path
    def frames_range_add(self, start, end, parent=None):
        # self.raw_frame_ranges.append((start, end, parent))
        self.frame_ranges.append(DependencyFrameRange(self.path, start, end, parent))
    @property
    def frames(self):
        with self.lock:
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
    def complete(self):
        if self._complete == None:
            self.size
        return self._complete
    @property
    def size(self):
        with self.lock:
            self._complete = True
            if not self._size:
                if '%' in self.path:
                    self._size = 0
                    for frame_range in self.frame_ranges:
                        if frame_range.size > 0:
                            self._size += frame_range.size
                        else:
                            self._complete = False
                else:
                    try:
                        self._size = os.path.getsize(self.path)
                    except OSError:
                        self._size = None
                        self._complete = False
            return self._size

class Stack(object):
    def __init__(self, path):
        self.path = path
        self.size = os.path.getsize(self.path)
        self.dependencies_size = None
        self.ctime = os.path.getctime(self.path)
        self.project = None
        self.resX = None
        self.resY = None
        self.fps = None
        self.frames = None
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
                            self.resX = int(char_buffer)
                        elif object_path.endswith('D/Y'):
                            self.resY = int(char_buffer)
                        elif object_path.endswith('D/JobFrameRate'):
                            self.fps = char_buffer
                        elif object_path.endswith('p/W'):
                            self.frames = int(char_buffer)
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
    @property
    def title(self):
        try:
            self._title
        except AttributeError:
            self.set_groupname()
        return self._title
    @property
    def tags(self):
        try:
            self._tags
        except AttributeError:
            self.set_groupname()
        return self._tags
    def set_groupname(self):
        try:
            level_names = []
            fx_type = None
            char_buffer = ''
            char_buffer_store = ''
            ungroup = False
            for line in open(self.path):
                for char in line:
                    if char == '(':
                        char_buffer = char_buffer.replace('\n', '').strip()
                        level_names.append(char_buffer)
                        char_buffer = ''
                    elif char == ')':
                        f_path = False
                        object_path = '/'.join(level_names)
                        if object_path.endswith('/ungroup') and char_buffer == '1':
                            ungroup = True
                        elif object_path.endswith('Group/D'): # This is a render
                            ungroup = True
                        elif object_path.endswith('Group/p') and ungroup:
                            ungroup = False
                        elif object_path.endswith('Group/p/n'):
                            if not ungroup:
                                self._groupname = char_buffer
                                self._title = self._groupname.split('#', 1)[0]
                                try:
                                    self._tags = self._groupname.split('#')[1:]
                                except IndexError:
                                    self._tags = []
                                return
                            else:
                                ungroup = False
                        char_buffer = ''
                        del level_names[-1]
                    elif len(level_names) > 0 and level_names[-1] == 'Shape':
                        continue
                    elif char:
                        char_buffer += char
            self._groupname = False
            self._title = os.path.splitext(os.path.basename(self.path))[0]
            self._tags = []
        except IOError as e:
            print 'Could not open ' + self.path
            raise e
    @property
    def comment(self):
        try:
            self._comment
        except AttributeError:
            self.set_comment()
        return self._comment
    def set_comment(self):
        try:
            level_names = []
            fx_type = None
            char_buffer = ''
            char_buffer_store = ''
            ungroup = False
            for line in open(self.path):
                for char in line:
                    if char == '(':
                        char_buffer = char_buffer.replace('\n', '').strip()
                        level_names.append(char_buffer)
                        char_buffer = ''
                    elif char == ')':
                        f_path = False
                        object_path = '/'.join(level_names)
                        if object_path.endswith('/ungroup') and char_buffer == '1':
                            ungroup = True
                        elif object_path.endswith('/p') and ungroup:
                            ungroup = False
                        elif object_path.endswith('/c'):
                            if not ungroup:
                                self._comment = char_buffer
                                return
                            else:
                                ungroup = False
                        char_buffer = ''
                        del level_names[-1]
                    elif len(level_names) > 0 and level_names[-1] == 'Shape':
                        continue
                    elif char:
                        char_buffer += char
            self._comment = False
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
    def iter_dependencies(self, progress_callback=False, relink=False):
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
            if relink:
                temp_handle = tempfile.NamedTemporaryFile(delete=False)
                changes = False
            for line in open(self.path):
                for char in line:
                    env_bytes_read += 1
                    time_now = time.time()
                    if time_now - last_progress_update_time > 0.1:
                        last_progress_update_time = time_now
                        progress_float = float(env_bytes_read) / float(self.size)
                        if progress_callback:
                            progress_callback(self, progress_float)
                    if char == '\\':
                        escape = True
                        continue
                    elif char == '(' and not escape:
                        char_buffer = char_buffer.replace('\n', '').strip()
                        level += 1
                        level_names.append(char_buffer)
                        char_buffer = ''
                    elif char == ')' and not escape:
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
                        elif object_path.endswith('C/d/I/H/p') or object_path.endswith('C/d/I/L/p') or object_path.endswith('C/d/S/p'): # Clip media folder
                            f_folder = char_buffer
                        elif object_path.endswith('C/d/I/s'): # Clip start frame
                            CdIs = int(char_buffer)
                        elif object_path.endswith('C/d/I/e'): # Clip end frame
                            CdIe = int(char_buffer)
                        elif object_path.endswith('C/d/I/H/n'):
                            f_path = f_folder + char_buffer
                            f_type = 'highres'
                        elif object_path.endswith('C/d/I/L/n'):
                            f_path = f_folder + char_buffer
                            f_type = 'lowres'
                        elif object_path.endswith('C/d/S/n'):
                            f_path = f_folder + char_buffer
                            f_type = 'audio'
                        elif object_path.endswith('F/D'): # .dat file relative path (from projects_path)
                            f_path = char_buffer
                            f_type = 'dat'
                        elif fx_type == '146':
                            f_type = 'glsl'
                            if object_path.endswith('F/p/s/c/c'):
                                f_folder = char_buffer
                            elif object_path.endswith('F/p/s/c/E/s') or object_path.endswith('F/p/s/c/p/s'):
                                if char_buffer.startswith('/'):
                                    f_path = char_buffer
                                else:
                                    f_path = f_folder + '/' + char_buffer
                        elif fx_type == '143':
                            f_type = 'lut'
                            if object_path.endswith('F/p/s/c/c'):
                                f_folder = char_buffer
                            elif object_path.endswith('F/p/s/c/F/s'):
                                if char_buffer.startswith('/'):
                                    f_path = char_buffer
                                else:
                                    f_path = f_folder + '/' + char_buffer
                        if f_path:
                            if '%' in f_path:
                                dependency = Dependency(f_path, f_type, CdIs, CdIe, parent=self)
                            else:
                                dependency = Dependency(f_path, f_type, parent=self)
                            if relink and not dependency.complete:
                                print 'Missing dependency: ', dependency.name
                                new_line, dependency = self.relink_line(line, dependency)
                                if line != new_line:
                                    changes = True
                                    line = new_line
                                # dependency needs to be updated at this point
                            if not dependency.path in self._dependency_paths:
                                self._dependencies.append(dependency)
                                self._dependency_paths.append(dependency.path)
                                yield dependency
                                for child_dependency in dependency.dependencies:
                                    if not child_dependency.name in self._dependency_paths:
                                        self._dependencies.append(child_dependency)
                                        yield child_dependency

                        char_buffer = ''
                        del level_names[-1]
                    elif len(level_names) > 0 and level_names[-1] == 'Shape':
                        continue
                    elif char:
                        char_buffer += char
                    escape = False
                if relink:
                    temp_handle.write(line)
            if relink:
                if changes:
                    temp_handle.flush()
                    temp_handle.close()
                    backup_path = os.path.join(os.path.dirname(self.path), '.'+os.path.basename(self.path))
                    os.rename(self.path, backup_path)
                    os.rename(temp_handle.name, self.path)
                    print 'Wrote changes to file:', self.path
                else:
                    temp_handle.close()
                    os.remove(temp_handle.name)
            if progress_callback:
                progress_callback(self, 1.0)
        except IOError as e:
            print 'Could not open ' + self.path
            raise e
    def relink_dependencies(self, progress_callback=False):
        for dependency in self.iter_dependencies(progress_callback=progress_callback, relink=True):
            if dependency.type == 'font':
                try:
                    destination = os.path.join(mistika.fonts_folder, os.path.basename(dependency_path))
                    shutils.copy2(dependency.path, destination)
                except IOError:
                    print 'Could not copy %s to %s' % (dependency.path, destination)
                # copy to /usr/share/fonts/mistika/
            else:
                pass # relinking is handled in iter_dependencies(relink=True)
    def relink_line(self, line, dependency):
        dependency_basename = os.path.basename(dependency.path)
        dependency_foldername = os.path.dirname(dependency.path)
        print dependency.type, dependency_foldername, dependency_basename
        for root, dirs, files in os.walk(os.path.dirname(self.path)):
            for basename in files:
                if basename == dependency_basename:
                    abspath = os.path.join(root, basename)
                    dependency_new = Dependency(abspath, dependency.type, dependency.start, dependency.end, dependency.parents[0])
                    if dependency.type in ['dat']:
                        return (line.replace('('+escape_par(dependency.name)+')', '('+escape_par(dependency_new.name)+')'), dependency_new)
                    elif dependency.type in ['lnk']:
                        return (line.replace('('+escape_par(dependency.path)+')', '('+escape_par(abspath)+')'), dependency_new)
                    elif dependency.type in ['glsl', 'lut']:
                        return (line.replace('('+escape_par(dependency.name)+')', '('+escape_par(abspath)+')'), dependency_new)
                    elif dependency.type in ['highres', 'lowres', 'audio']:
                        return (line.replace('('+escape_par(dependency_foldername)+'/)', '('+escape_par(root)+'/)'), dependency_new)
        return (line, dependency)

