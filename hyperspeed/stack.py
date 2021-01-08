#!/usr/bin/env python

import os
import time
import mistika
import text
import threading
import tempfile
import copy
import shutil
import re

import hyperspeed.utils
import hyperspeed.video

RENAME_MAGIC_WORDS = ['auto', 'rename']

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
        self.x = False
        self.duration = False
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
    def __init__(self, name, f_type, start = False, end = False, parent=None, level=False, x=False, duration=False):
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
            self.format = None
            self.level = level
            self.x = x
            self.duration = duration
            if f_type == 'dat':
                self.text = text.Title(self.path)
                for font in self.text.fonts:
                    self.dependencies.append(Dependency(font, 'font', parent=parent))
    def __str__(self):
        return 'Dependency(%s)' % self.name
    def __repr__(self):
        return 'Dependency(%s)' % self.name
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
    def codec(self):
        try:
            self._codec
        except AttributeError:
            self._codec = self.get_codec()
        return self._codec
    def get_codec(self):
        if '%%' in self.path:
            path = self.path % self.start
        else:
            path = self.path
        try:
            return hyperspeed.utils.get_stream_info(path)[0]['codec']
        except:
            return 'codec_unknown'
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
    def remove(self):
        if '%' in self.path:
            for frame_number in range(self.start, self.end):
                frame_path = self.path % frame_number
                try:
                    os.remove(frame_path)
                except OSError:
                    print 'Could not remove %s' % frame_path
            dirname = os.path.dirname(self.path)
            try:
                os.rmdir(dirname)
            except OSError:
                print 'Could not remove %s' % dirname
        else:
            try:
                os.remove(self.path)
            except OSError:
                print 'Could not remove %s' % self.path

class Stack(object):
    exists = False
    dependencies_size = None
    project = None
    mediaPath = None
    audioPath = None
    resX = None
    resY = None
    fps = None
    frames = None
    format = None
    def __init__(self, path):
        self.path = path
        self._tags = []
        self.getTagsInName()
        try:
            self.size = os.path.getsize(self.path)
            self.ctime = os.path.getctime(self.path)
            self.exists = True
            self.read_header()
        except (TypeError, OSError) as e:
            print e
            pass
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
                        elif object_path.endswith('D/MediaPath'):
                            self.mediaPath = char_buffer
                        elif object_path.endswith('D/AudioPath'):
                            self.audioPath = char_buffer
                        elif object_path.endswith('D/X') or object_path.endswith('outputFraming/w'):
                            self.resX = int(char_buffer)
                        elif object_path.endswith('D/Y') or object_path.endswith('outputFraming/h'):
                            self.resY = int(char_buffer)
                        elif object_path.endswith('D/JobFrameRate'):
                            self.fps = char_buffer
                        elif object_path.endswith('p/W'):
                            self.frames = int(char_buffer)
                        elif object_path.endswith('D/H/f'):
                            self.format = char_buffer
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
            self.getTagsInName()
        return self._tags
    def getTagsInName(self):
        #print os.path.basename(self.path)
        if '+' in os.path.basename(self.path):
            try:
                subject = os.path.basename(self.path).split('+', 1)[1]
                self._tags += re.split(r'_\d{4}', subject)[0].split('+')
            except IndexError:
                pass
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
                                    self._tags += self._groupname.split('#')[1:]
                                except IndexError:
                                    pass
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
        self.subtitleIds = []
        try:
            dependency = None
            level_names = []
            level_offsets = self.level_offsets = {}
            f_type = None
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
            line_i = 0
            for line in open(self.path):
                line_i += 1
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
                                # print 'Hidden ends, line', str(line_i)
                        object_path = '/'.join(level_names)
                        if object_path.endswith('p/X'):
                            try:
                                x = int(char_buffer)
                                if object_path.endswith('Group/p/X'):
                                    if not level in level_offsets or x < level_offsets[level]:
                                        level_offsets[level] = x
                            except ValueError:
                                pass
                        if object_path.endswith('p/W'):
                            try:
                                duration = int(char_buffer)
                            except ValueError:
                                pass
                        if object_path.endswith('F/T'):
                            fx_type = char_buffer
                        elif object_path.endswith('p/h'):
                            if bool(char_buffer):
                                hidden_level = level-1
                                # print 'Hidden starts:', object_path, ',line', str(line_i)
                        elif object_path.endswith('C/F'): # Clip source link
                            f_path = char_buffer
                            f_type = 'lnk'
                            dependency = Dependency(f_path, f_type, parent=self)
                        elif object_path.endswith('C/d/I/H/p') or object_path.endswith('C/d/I/L/p') or object_path.endswith('C/d/S/p'): # Clip media folder
                            f_folder = char_buffer
                        elif object_path.endswith('C/d/I/s'): # Clip start frame
                            CdIs = int(char_buffer)
                        elif object_path.endswith('C/d/I/e'): # Clip end frame
                            CdIe = int(char_buffer)
                        elif object_path.endswith('C/d/I/H/n'):
                            f_path = f_folder + char_buffer
                            f_type = 'highres'
                        elif object_path.endswith('C/d/I/H/f'):
                            f_format = char_buffer
                        elif object_path.endswith('C/d/I/L/n'):
                            f_path = f_folder + char_buffer
                            f_type = 'lowres'
                        elif object_path.endswith('C/d/I/L/f'):
                            f_format = char_buffer
                        elif object_path.endswith('Group/groupType') and char_buffer == '3':
                            f_type = 'template'
                        elif f_type == 'template' and object_path.endswith('Group/p/n') and char_buffer.lower().startswith('subs'):
                            f_type = 'subtitle'
                        elif f_type == 'subtitle' and object_path.endswith('Group/p/X'):
                            try:
                                self.subtitleIds.append(int(char_buffer))
                                f_type = None
                            except ValueError:
                                # print 'Invalid frame number:', char_buffer
                                pass
                        elif object_path.endswith('C/d/I/H') or object_path.endswith('C/d/I/L'):
                            if '%' in f_path:
                                dependency = Dependency(f_path, f_type, CdIs, CdIe, parent=self)
                            else:
                                dependency = Dependency(f_path, f_type, parent=self)
                            dependency.format = f_format
                        elif object_path.endswith('C/d/S/n'):
                            f_path = f_folder + char_buffer
                            f_type = 'audio'
                            dependency = Dependency(f_path, f_type, parent=self)
                        elif object_path.endswith('F/D'): # .dat file relative path (from projects_path)
                            f_path = char_buffer
                            f_type = 'dat'
                        elif f_type == 'dat' and object_path.endswith('p/W'):
                            dependency = Dependency(f_path, f_type, parent=self, level=level, x=x, duration=duration)
                        elif fx_type == '146':
                            f_type = 'glsl'
                            if object_path.endswith('F/p/s/c/c'):
                                f_folder = char_buffer
                            elif object_path.endswith('F/p/s/c/E/s') or object_path.endswith('F/p/s/c/p/s'):
                                if char_buffer.startswith('/'):
                                    f_path = char_buffer
                                else:
                                    f_path = f_folder + '/' + char_buffer
                                dependency = Dependency(f_path, f_type, parent=self)
                        elif fx_type == '143':
                            f_type = 'lut'
                            if object_path.endswith('F/p/s/c/c'):
                                f_folder = char_buffer
                            elif object_path.endswith('F/p/s/c/F/s'):
                                if char_buffer.startswith('/'):
                                    f_path = char_buffer
                                else:
                                    f_path = f_folder + '/' + char_buffer
                                dependency = Dependency(f_path, f_type, parent=self)
                        if dependency:
                            if relink and not dependency.complete:
#                                print 'Missing dependency: ', dependency.name
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
                                dependency = None

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
                    destination = os.path.join(mistika.fonts_folder, os.path.basename(dependency.path))
                    shutil.copy2(dependency.path, destination)
                except (IOError, shutil.Error):
                    print 'Could not copy %s to %s' % (dependency.path, destination)
                # copy to /usr/share/fonts/mistika/
            else:
                pass # relinking is handled in iter_dependencies(relink=True)
    def relink_line(self, line, dependency):
        dependency_basename = os.path.basename(dependency.path)
        dependency_foldername = os.path.dirname(dependency.path)
        #print dependency.type, dependency_foldername, dependency_basename
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
    @property
    def subtitles(self):
        try:
            self._subtitles
        except AttributeError:
            self._subtitles = Subtitles(self)
        return self._subtitles


class Render(Stack):
    output_stack = None
    output_video = None
    output_proxy = None
    output_audio = None
    afterscript = None
    
    def __init__(self, path):
        super(Render, self).__init__(path)
        self.name = os.path.splitext(os.path.basename(self.path))[0]
        self.output_paths = []
        self.id = self.project+'/'+self.name
        if self.exists:
            self.clp_path = 'clp'.join(self.path.rsplit('rnd', 1))
            if os.path.exists(self.clp_path):
                self.output_stack = Stack(self.clp_path)
                for dependency in self.output_stack.dependencies:
                    if dependency.type == 'highres':
                        self.output_video = dependency
                        self.output_paths.append(dependency.path)
                    elif dependency.type == 'lowres':
                        self.output_proxy = dependency
                        self.output_paths.append(dependency.path)
                    elif dependency.type == 'audio':
                        self.output_audio = dependency
                        self.output_paths.append(dependency.path)
            else:
                self.output_stack = None

    @property
    def prettyname(self):
        if self.groupname:
            for magic_word in RENAME_MAGIC_WORDS:
                if magic_word in self.name:
                    return self.groupname
        return re.sub('^%s\W*' % self.project, '', self.name)

    @property
    def primary_output(self):
        if self.output_video != None:
            return self.output_video
        elif self.output_proxy != None:
            return self.output_proxy
        elif self.output_audio != None:
            return self.output_audio
        else:
            return None
    def remove_output(self):
        for dependency in self.output_stack.dependencies:
            if dependency.type in ['highres', 'lowres', 'audio']:
                dependency.remove()
    def archive(self, tag=''):
        archiveFolder = os.path.join(mistika.projects_folder, self.project, 'DATA', 'RENDER', 'Exported_files')
        if not os.path.isdir(archiveFolder):
            os.makedirs(archiveFolder)
        timeStr = time.strftime("%y%m%d-%H%M")
        if tag:
            tag = '_'+tag
        archivePath = os.path.join(archiveFolder, "%s%s_%s.rnd" % (timeStr, tag, self.groupname))
        shutil.copy2(self.path, archivePath)

class Subtitles(object):
    count = 0
    def __init__(self, render):
        self.render = render
        subs = {}
        for dependency in render.dependencies:
            if dependency.type == 'dat':
                if not dependency.x in render.subtitleIds:
                    continue
                if dependency.level != 4:
                    continue
                subs[dependency.x] = dependency
        srt = ''
        vtt = 'WEBVTT\r\n\r\n'
        srtIndex = 0
        for subId in sorted(subs):
            dependency = subs[subId]
            srtIndex += 1
            srtStart = hyperspeed.video.frames2tc_float(subId - render.level_offsets[dependency.level], render.fps)
            srtEnd = hyperspeed.video.frames2tc_float(subId - render.level_offsets[dependency.level] + dependency.duration, render.fps)
            srt += '''%i
%s --> %s
%s

''' % (srtIndex, srtStart, srtEnd, dependency.text.string )
            vtt += '''%i
%s --> %s
%s

''' % (srtIndex, srtStart.replace(',', '.'), srtEnd.replace(',', '.'), dependency.text.string )
            self.count = len(subs)
            self.srt = srt
            self.vtt = vtt


