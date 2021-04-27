#!/usr/bin/env python
# -*- coding: utf-8 -*-

import gtk
import os
import uuid
import math
import subprocess
import time
import sys
import gobject
import platform
import json
import threading
import copy
import re
from Queue import Queue

try:
    cwd = os.getcwd()
    os.chdir(os.path.dirname(os.path.realpath(sys.argv[0])))
    sys.path.append("../..")
    from hyperspeed import config_folder
    from hyperspeed.stack import Stack, Dependency, DEPENDENCY_TYPES
    from hyperspeed import mistika
    from hyperspeed import human
    from hyperspeed.copy import copy_with_progress
except ImportError:
    mistika = False
    config_folder = os.path.expanduser('~/.mistika-hyperspeed/fetch.cfg')

script_settings_path = os.path.join(config_folder, 'fetch.cfg')

COLOR_DEFAULT = '#000000'
COLOR_DISABLED = '#888888'
COLOR_WARNING = '#ff8800'
COLOR_ALERT = '#cc0000'

def get_size(localOrRemote):
    remote = re.search(r'^(.*?)(?:([^\s@]*)@)?([^\s@]+)\:(.+)', localOrRemote)
    if remote:
        remoteArgs = remote.group(1)
        remoteUser = remote.group(2)
        remoteHost = remote.group(3)
        remotePath = remote.group(4)
        # print remoteArgs, remoteUser, remoteHost, remotePath
        cmd = ['ssh']
        cmd += remoteArgs.split()
        if remoteUser:
            cmd += ['-l', remoteUser]
        cmd += [remoteHost]
        cmd += ['ls', '-n', remotePath]
        # print cmd
        sshProc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=open(os.devnull, 'wb'))
        if sshProc.wait() == 0:
            result = sshProc.communicate()[0]
            return int(result.split()[4])
    else:
        try:
            return os.path.getsize(localOrRemote)
        except OSError:
            return 0
class PyApp(gtk.Window):
    batch_mode = False
    settings = {
        'mappings' : {},
    }
    statPoints = []
    bytesCopied = 0
    def __init__(self):
        super(PyApp, self).__init__()
        self.stacks = {}
        self.dependencies = {}
        self.threads = []
        self.queue_size = 0
        self.last_update = {'time':0, 'copied':0}
        screen = self.get_screen()
        self.set_title("Fetch")
        self.set_size_request(screen.get_width()/2-100, screen.get_height()-200)
        self.set_border_width(20)
        self.set_position(gtk.WIN_POS_CENTER)
        if 'darwin' in platform.system().lower():
            self.set_resizable(False) # Because resizing crashes the app on Mac
        # self.connect("key-press-event",self.on_key_press_event)

        vbox = gtk.VBox(False, 10)
        vbox.pack_start(self.init_mappings_view(), False, False, 5)
        vbox.pack_start(self.init_stacks_view())
        vbox.pack_start(self.init_dependencies_view())

        #menu = ['Sync project', 'Sync media']
        footer = gtk.HBox(False, 10)
        quitButton = gtk.Button('Quit')
        quitButton.set_size_request(70, 30)
        quitButton.connect("clicked", self.on_quit)
        footer.pack_end(quitButton, False, False)

        vbox.pack_end(footer, False, False, 10)

        self.add(vbox)

        self.connect("destroy", self.on_quit)
        self.show_all()
        self.parse_command_line_arguments()
        self.load_settings()
        self.init_finder_daemon()
        self.init_fetch_daemon()
        gobject.idle_add(self.present)
    def load_settings(self):
        try:
            # print 'script_settings_path', script_settings_path, open(script_settings_path).read()
            self.settings.update(json.loads(open(script_settings_path).read()))
            treestore = self.mappings_treestore
            treestore.clear();
            # print self.settings['mappings']
            for local, remotes in self.settings['mappings'].iteritems():
                local_row = treestore.append(None, [local])
                for remote in remotes:
                    treestore.append(local_row, [remote])
            # print self.settings
        except Exception as e:
            print e
            pass
        else:
            pass
        finally:
            pass
    def save_settings(self):
        open(script_settings_path, 'w').write(json.dumps(self.settings, sort_keys=True, indent=2))
    def on_quit(self, widget):
        gtk.main_quit()
    def parse_command_line_arguments(self):
        # -H /Volumes/mediaraid/Projects/22189_Hurtigruta/MISTIKA_JS/MR2_0009_0021.js -L /Volumes/mediaraid/Projects/22189_Hurtigruta/MISTIKA_JS/L_MR2_0009_0021.js -S None -l 0 -n MR2_0009_0021_Raftsundet_V1-0004 -i 0 -s 0 -e 249 -p 22189_Hurtigruta -f RGB10:XFS.RGB10 -T 00:56:28:13 -a 160
        if len(sys.argv) > 1:
            print 'Command line arguments:', ' '.join(sys.argv[1:])
            dependencies = []
            for i in range(1, len(sys.argv)):
                if sys.argv[i] == '-H' and len(sys.argv) > i+1:
                    if sys.argv[i+1] != 'None':
                        dependencies.append(Dependency(sys.argv[i+1], 'highres'))
                if sys.argv[i] == '-L' and len(sys.argv) > i+1:
                    if sys.argv[i+1] != 'None':
                        dependencies.append(Dependency(sys.argv[i+1], 'lowres'))
                if sys.argv[i] == '-S' and len(sys.argv) > i+1:
                    if sys.argv[i+1] != 'None':
                        dependencies.append(Dependency(sys.argv[i+1], 'audio'))
            for dependency in dependencies:
                if not dependency.path in self.dependencies:
                    self.dependencies[dependency.path] = dependency
                    gobject.idle_add(self.gui_dependency_add, dependency)
    def on_mapping_edited(self, cellrenderertext, path, new_text):
        # print cellrenderertext, path, new_text
        treestore = self.mappings_treestore
        treestore[path][0] = new_text
        self.on_mappings_changed()
    def on_mappings_changed(self):
        treestore = self.mappings_treestore
        mappings = {}
        for x in treestore:
            mapping = []
            for y in x.iterchildren():
                # print '-', y[0]
                mapping.append(y[0])
            # print x[0]
            mappings[x[0]] = mapping
        self.settings['mappings'] = mappings
        self.save_settings()
    def init_mappings_view(self):
        expander = gtk.Expander("Mappings")
        vbox = gtk.VBox(False, 10)
        hbox = gtk.HBox(False, 10)
        button = gtk.Button('Add local folder')
        button.connect("clicked", self.add_local_folder)
        hbox.pack_start(button, False, False, 0)
        button = gtk.Button('Add source')
        button.connect("clicked", self.add_remote_folder)
        hbox.pack_start(button, False, False, 0)
        button = gtk.Button('Remove selected')
        button.connect("clicked", self.remove_selected_mappings)
        hbox.pack_start(button, False, False, 0)
        vbox.pack_start(hbox, False, False, 0)

        treestore = self.mappings_treestore = gtk.TreeStore(str) # Local, Local editable, Remote, Remote editable
        treeview = self.mappings_treeview = gtk.TreeView()
        treeview.set_rules_hint(True)
        cell = gtk.CellRendererText()
        cell.set_property("editable", True)
        cell.connect('edited', self.on_mapping_edited, )
        column = gtk.TreeViewColumn('Mappings', cell, text=0)
        column.set_resizable(True)
        column.set_expand(True)
        treeview.append_column(column)
        treeview.set_model(treestore)
        treeview.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(treeview)
        vbox.pack_start(scrolled_window)
        expander.add(vbox)
        return expander

    def add_local_folder(self, widget):
        treeview = self.mappings_treeview
        row_iter = self.mappings_treestore.append(None, ['/'])
        row_path = self.mappings_treestore.get_path(row_iter)
        selection = treeview.get_selection()
        selection.select_path(row_path)
        self.on_mappings_changed()
    def add_remote_folder(self, widget):
        treeview = self.mappings_treeview
        selection = treeview.get_selection()
        (model, row_paths) = selection.get_selected_rows()
        for selected_row_path in row_paths:
            if type(selected_row_path) is tuple:
                selected_row_path = selected_row_path[0]
            selected_row_iter = model.get_iter(selected_row_path)
            row_iter = self.mappings_treestore.append(selected_row_iter, ['user@host:/'])
            row_path = self.mappings_treestore.get_path(row_iter)
            treeview.expand_to_path(row_path)
            selection.unselect_all()
            selection.select_path(row_path)
        self.on_mappings_changed()
    def remove_selected_mappings(self, widget):
        treeview = self.mappings_treeview
        treestore = self.mappings_treestore
        selection = treeview.get_selection()
        (model, row_paths) = selection.get_selected_rows()
        for selected_row_path in reversed(row_paths):
            selected_row_iter = model.get_iter(selected_row_path)
            treestore.remove(selected_row_iter)
        self.on_mappings_changed()

    def init_stacks_view(self):
        vbox = gtk.VBox(False, 10)
        hbox = gtk.HBox(False, 10)
        hbox.pack_start(gtk.Label('Environments, groups or other structures to consolidate'), False, False)
        spacer = gtk.HBox(False)
        hbox.pack_start(spacer)
        button = gtk.Button('Add structure ...')
        button.connect("clicked", self.add_file_dialog)
        hbox.pack_start(button, False, False, 0)
        button = gtk.Button('Remove selected')
        button.connect("clicked", self.gui_on_selected_stacks, 'remove')
        hbox.pack_start(button, False, False, 0)
        vbox.pack_start(hbox, False, False, 0)
        treestore = self.stacks_treestore = gtk.TreeStore(str, float, str, bool, bool) # Name, progress float, progress text, progress visible, status visible
        treeview = self.stacks_treeview = gtk.TreeView()
        treeview.set_rules_hint(True)
        cell = gtk.CellRendererText()
        cell.set_property("editable", True)
        column = gtk.TreeViewColumn('Stack', cell, text=0)
        column.set_resizable(True)
        column.set_expand(True)
        treeview.append_column(column)
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn('Status')
        column.pack_start(cell, False)
        column.set_attributes(cell, text=2, visible=4)
        cell = gtk.CellRendererProgress()
        column.pack_start(cell, True)
        column.set_attributes(cell, value=1, text=2, visible=3)
        column.set_resizable(True)
        treeview.append_column(column)
        treeview.set_model(treestore)
        treeview.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        # treeview.expand_all()
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(treeview)
        vbox.pack_start(scrolled_window)
        return vbox

    def init_dependencies_view(self):
        vbox = gtk.VBox(False, 10)

        hbox = gtk.HBox(False, 10)
        hbox.pack_start(gtk.Label('Missing files'), False, False)
        spacer = gtk.HBox(False)
        hbox.pack_start(spacer)
        self.status_label = gtk.Label('No stacks loaded')
        # hbox.pack_start(self.status_label, False, False, 5)
        spinner = self.spinner_queue = gtk.Image()
        spinner.set_no_show_all(True)
        try:
            spinner.set_from_file('../../res/img/spinner01.gif')
        except:
            pass
        hbox.pack_start(spinner, False, False, 5)
        # button = gtk.Button('Include selected')
        # button.connect("clicked", self.gui_on_selected_dependencies, 'unskip')
        # hbox.pack_end(button, False, False, 0)
        # button = gtk.Button('Skip selected')
        # button.connect("clicked", self.gui_on_selected_dependencies, 'skip')
        # hbox.pack_end(button, False, False, 0)
        vbox.pack_start(hbox, False, False, 0)

        treestore = self.dependencies_treestore = gtk.TreeStore(str, float, str, bool, str, str, str, str, bool) # Name, progress float, progress text, progress visible, details, human size, status, text color, status visible
        treeview = self.dependencies_treeview = gtk.TreeView()
        treeview.set_tooltip_column(4)
        treeview.set_rules_hint(True)
        treeselection = treeview.get_selection()
        treeselection.set_mode(gtk.SELECTION_MULTIPLE)
        self.dependency_types = copy.copy(DEPENDENCY_TYPES)
        for dependency_type_id, dependency_type in self.dependency_types.iteritems():
            dependency_type.meta = {
                'count' : 0,
                'size' : 0,
                'copied' : 0
            }
            row_iter = treestore.append(None, [dependency_type.description, 0.0, '', False, dependency_type.description, '', '', COLOR_DISABLED, False])
            row_path = treestore.get_path(row_iter)
            dependency_type.row_reference = gtk.TreeRowReference(treestore, row_path)
        cell = gtk.CellRendererText()
        cell.set_property("editable", True)
        column = gtk.TreeViewColumn('', cell, text=0, foreground=7)
        column.set_resizable(True)
        column.set_expand(True)
        treeview.append_column(column)
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn('Source')
        column.pack_start(cell, False)
        column.set_attributes(cell, text=6, foreground=7, visible=8)
        cell = gtk.CellRendererProgress()
        column.pack_start(cell, True)
        column.set_attributes(cell, value=1, text=2, visible=3)
        column.set_resizable(True)
        treeview.append_column(column)
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn('Size', cell, text=5, foreground=7)
        column.set_resizable(True)
        treeview.append_column(column)
        treeview.set_model(treestore)
        treeview.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        # treeview.expand_all()

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(treeview)
        vbox.pack_start(scrolled_window)

        hbox = gtk.HBox(False, 10)
        label = gtk.Label('Transferred:');
        hbox.pack_start(label, False, False, 5)
        label = self.bytes_copied_label = gtk.Label('0B');
        hbox.pack_start(label, False, False, 5)
        label = gtk.Label('Time:');
        hbox.pack_start(label, False, False, 5)
        label = self.time_copied_label = gtk.Label('0');
        hbox.pack_start(label, False, False, 5)
        label = gtk.Label('Average rate:');
        hbox.pack_start(label, False, False, 5)
        label = self.average_rate_label = gtk.Label('0B/s');
        hbox.pack_start(label, False, False, 5)
        label = gtk.Label('Current rate:');
        hbox.pack_start(label, False, False, 5)
        label = self.rate_label = gtk.Label('0B/s');
        hbox.pack_start(label, False, False, 5)
        spacer = gtk.HBox(False)
        hbox.pack_start(spacer)
        button = gtk.Button('Fetch selected')
        button.connect("clicked", self.selected_dependencies_perform, 'fetch')
        hbox.pack_end(button, False, False, 0)
        vbox.pack_start(hbox, False, False, 0)
        return vbox
    def add_file_dialog(self, widget):
        if mistika:
            folder = os.path.join(mistika.projects_folder, mistika.project, 'DATA')
        else:
            folder = '/'
        dialog = gtk.FileChooserDialog(title="Add files", parent=None, action=gtk.FILE_CHOOSER_ACTION_OPEN, buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK), backend=None)
        dialog.set_select_multiple(True)
        #dialog.add_filter(filter)
        dialog.add_shortcut_folder(mistika.env_folder)
        dialog.add_shortcut_folder(folder)
        dialog.set_current_folder(folder)
        filter = gtk.FileFilter()
        filter.set_name("Mistika structures")
        filter.add_pattern("*.fx")
        filter.add_pattern("*.env")
        filter.add_pattern("*.grp")
        filter.add_pattern("*.rnd")
        filter.add_pattern("*.clp")
        filter.add_pattern("*.lnk")
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            for stack_path in dialog.get_filenames():
                self.gui_stack_add(stack_path)
        elif response == gtk.RESPONSE_CANCEL:
            print 'Closed, no files selected'
        dialog.destroy()
    def gui_stack_add(self, stack_path):
        if stack_path in self.stacks:
            return
        self.stacks[stack_path] = Stack(stack_path)
        stack = self.stacks[stack_path]
        row_iter = self.stacks_treestore.append(None, [stack_path, 0.0, '0%', False, False])
        row_path = self.stacks_treestore.get_path(row_iter)
        stack.row_reference = gtk.TreeRowReference(self.stacks_treestore, row_path)
        # for dependency in stack.dependencies:
        #     self.dependencies_treestore.append(None, [dependency.name])
        # print 'creating thread'
        t = threading.Thread(target=self.get_dependencies, args=[stack])
        self.threads.append(t)
        t.setDaemon(True)
        t.start()
        # print 'started thread'
        # print threading.active_count()
    sources = {}
    def finder_daemon(self):
        q = self.finder_queue = Queue()
        while True:
            dependency = q.get()
            for localPath in self.settings['mappings']:
                if dependency.path.startswith(localPath):
                    for source in self.settings['mappings'][localPath]:
                        sourcePath = dependency.path.replace(localPath, source)
                        with dependency.lock:
                            if '%' in dependency.path:
                                dependency._size = 0
                                for frame_range in dependency.frame_ranges:
                                    frame_range._size = 0
                                    for i in range(frame_range.start, frame_range.end+1):
                                        frame_range._size += get_size(sourcePath % i)
                                    dependency._size += frame_range.size
                            else:
                                dependency._size = get_size(sourcePath)
                                # print 'Found', sourcePath, human.size(dependency.size)
                                break
                if dependency._size > 0:
                    self.sources[dependency.path] = sourcePath;
                    gobject.idle_add(self.gui_row_update, self.dependencies_treestore, dependency.row_reference, {
                        '6': source,
                        '5': human.size(dependency.size),
                    })
                    self.dependency_types[dependency.type].meta['size'] += dependency.size
                    self.gui_dependency_summary_update(dependency.type)
                    break
            q.task_done()

    def init_finder_daemon(self):
        t = self.finder_daemon_thread = threading.Thread(target=self.finder_daemon)
        self.threads.append(t)
        t.setDaemon(True)
        t.start()
    def fetch_daemon(self):
        stats = self.stats = {
            'bytesCopied': 0,
            'timeCopied': 0,
        }
        treestore = self.dependencies_treestore
        self.abort = False
        q = self.fetch_queue = Queue()
        while True:
            dependency = q.get()
            if dependency.path in self.sources:
                taskStartedAt = time.time()
                sourcePath = self.sources[dependency.path]
                if self.abort:
                    return
                if dependency.size in [None, 0] or dependency.ignore:
                    continue
                row_path = dependency.row_reference.get_path()
                gobject.idle_add(self.gui_row_update, treestore, dependency.row_reference, {'1': 0.0,  '3': True, '8' : False})
                is_sequence = '%' in dependency.path
                destination_path = dependency.path
                # destination_path = os.path.join(dependency_path.lstrip('/'), destination_folder).rstrip('/')
                if is_sequence:
                    frame_ranges = dependency.frame_ranges
                else:
                    frame_ranges = None
                # frame_ranges = is_sequence ? dependency.frame_ranges : None
                def copyProgressCallback(bytesCopied, progress, rate):
                    gobject.idle_add(self.gui_dependency_summary_update, dependency.type, bytesCopied)
                    gobject.idle_add(self.gui_row_update, treestore, dependency.row_reference, {'1': progress * 100.0, '2': '%5.2f%%' % (progress * 100.0)})
                    gobject.idle_add(self.rate_label.set_text, human.size(rate)+'/s')

                success = copy_with_progress(sourcePath, destination_path, copyProgressCallback, frame_ranges)
                if success:
                    self.dependency_types[dependency.type].meta['copied'] += dependency.size
                    gobject.idle_add(self.gui_row_update, treestore, dependency.row_reference, {'1': 100.0, '6' : 'Copied', '3': False, '8' : True})
                else:
                    gobject.idle_add(self.gui_row_update, treestore, dependency.row_reference, {'4': success ,'6' : 'Error', '3': False, '7' : COLOR_ALERT, '8' : True})
                gobject.idle_add(self.gui_dependency_summary_update, dependency.type)
                taskCompletedAt = time.time()
                stats['bytesCopied'] += dependency.size
                stats['timeCopied'] += taskCompletedAt - taskStartedAt
                gobject.idle_add(self.gui_stats_update)
            q.task_done()
            if q.empty():
                gobject.idle_add(self.rate_label.set_text, human.size(0)+'/s')

    def init_fetch_daemon(self):
        t = self.fetch_daemon_thread = threading.Thread(target=self.fetch_daemon)
        self.threads.append(t)
        t.setDaemon(True)
        t.start()
    def gui_stats_update(self):
        self.bytes_copied_label.set_text(human.size(self.stats['bytesCopied']))
        self.time_copied_label.set_text(human.duration(self.stats['timeCopied']))
        self.average_rate_label.set_text(human.size(float(self.stats['bytesCopied']) / self.stats['timeCopied'])+'/s')
    def gui_on_selected_stacks(self, widget, action):
        treeview = self.stacks_treeview
        selection = treeview.get_selection()
        (model, row_paths) = selection.get_selected_rows()
        stack_list = []
        for row_path in row_paths:
            row_iter = model.get_iter(row_path)
            stack_list.append(model[row_path][0])
        for stack_path in stack_list:
            if action == 'remove':
                self.gui_stack_remove(stack_path)
    def gui_stack_remove(self, stack):
        if type(stack) != Stack:
            stack = self.stacks[stack]
        for dependency in stack.dependencies:
            frames_before = self.dependencies[dependency.path].frames
            self.dependencies[dependency.path].parent_remove(stack)
            if len(self.dependencies[dependency.path].parents) == 0:
                treestore = self.dependencies_treestore
                if self.dependencies[dependency.path].row_reference:
                    row_path = self.dependencies[dependency.path].row_reference.get_path()
                    row_iter = treestore.get_iter(row_path)
                    treestore.remove(row_iter)  
                    if self.dependencies[dependency.path].size != None:
                        self.dependency_types[dependency.type].meta['size'] -= self.dependencies[dependency.path].size
                    self.dependency_types[dependency.type].meta['count'] -= 1
                    del self.dependencies[dependency.path]
                    self.gui_dependency_summary_update(dependency.type)
            elif self.dependencies[dependency.path].frames != frames_before:
                self.gui_dependency_frames_update(self.dependencies[dependency.path])
        treestore = self.stacks_treestore
        row_path = stack.row_reference.get_path()
        row_iter = treestore.get_iter(row_path)
        del self.stacks[stack.path]
        treestore.remove(row_iter)
        # self.calculate_queue_size()

    def launch_thread(self, method):
        t = threading.Thread(target=method)
        self.threads.append(t)
        t.setDaemon(True)
        t.start()
        return t
    def get_dependencies(self, stack):
        for dependency in stack.iter_dependencies(progress_callback=self.stack_read_progress):
            #print dependency.name
            if not dependency.path in self.dependencies:
                self.dependencies[dependency.path] = dependency = copy.copy(dependency)
                if dependency.size == None:
                    # self.finder_queue.put(dependency)
                    pass
                else:
                    self.queue_size += dependency.size
                # self.dependencies[dependency.path].parents.append(stack)
                gobject.idle_add(self.gui_dependency_add, dependency)
            else:
                with self.dependencies[dependency.path].lock:
                    this_frame_range = dependency.frame_ranges[0]
                    if '%' in dependency.path and not this_frame_range in self.dependencies[dependency.path].frame_ranges:
                        self.dependencies[dependency.path].frame_ranges.append(this_frame_range)
                        gobject.idle_add(self.gui_dependency_frames_update, dependency.path)
                    if not stack in self.dependencies[dependency.path].parents:
                        self.dependencies[dependency.path].parents.append(stack)
                        gobject.idle_add(self.gui_dependency_add_parent, dependency.path, stack.path)
        # self.status_set('%s in queue' % human.size(self.queue_size))
    def stack_read_progress(self, stack, progress):
        treestore = self.stacks_treestore
        row_path = stack.row_reference.get_path()
        progress_percent = progress * 100.0
        progress_string = '%5.2f%%' % progress_percent
        progress_string = '   Looking for missing files   '
        # print stack, progress, progress_string
        show_progress = True
        if progress == 1.0:
            progress_string = '   Loaded   '
            show_progress = False
        gobject.idle_add(self.gui_row_update, treestore, stack.row_reference, {'1': progress_percent, '2' : progress_string, '3': show_progress, '4': not show_progress})
        # self.status_set('%s in queue' % human.size(self.queue_size))
    def gui_dependency_add(self, dependency):
        treestore = self.dependencies_treestore
        self.dependency_types[dependency.type].meta['count'] += 1
        parent_stacks = []
        for parent_stack in dependency.parents:
            if parent_stack:
                parent_stacks.append(parent_stack.path)
        details = '\n'.join(parent_stacks)
        if dependency.size == None:
            human_size = ''
            status = ''
            text_color = COLOR_DEFAULT
        else:
            return
            human_size = human.size(dependency.size)
            status = ''
            text_color = COLOR_DEFAULT
        parent_row_path = self.dependency_types[dependency.type].row_reference.get_path()
        parent_iter = treestore.get_iter(parent_row_path)
        row_iter = self.dependencies_treestore.append(parent_iter, [dependency.path, 0, '', False, details, human_size, status, text_color, True])
        row_path = self.dependencies_treestore.get_path(row_iter)
        self.dependencies[dependency.path].row_reference = gtk.TreeRowReference(self.dependencies_treestore, row_path)
        if '%' in dependency.path:
            gobject.idle_add(self.gui_dependency_frames_update, dependency.path)
        if dependency.size == None:
            self.finder_queue.put(dependency)
        else:
            self.dependency_types[dependency.type].meta['size'] += dependency.size
        self.gui_dependency_summary_update(dependency.type)
    def gui_dependency_summary_update(self, dependency_type, extra_bytes=0):
        dependency_type_object = self.dependency_types[dependency_type]
        treestore = self.dependencies_treestore
        row_path = dependency_type_object.row_reference.get_path()
        if dependency_type_object.meta['count'] > 0:
            header = '%s (%i)' % (dependency_type_object.description, dependency_type_object.meta['count'])
            human_size = human.size(dependency_type_object.meta['size'])
        else:
            header = self.dependency_types[dependency_type].description
            human_size = ''
        treestore[row_path][0] = header
        treestore[row_path][5] = human_size
        if 0 < dependency_type_object.meta['copied'] < dependency_type_object.meta['size']:
            progress = float(dependency_type_object.meta['copied']+extra_bytes) / float(dependency_type_object.meta['size'])
            progress_percent = progress * 100.0
            progress_string = '%5.2f%%' % progress_percent
            treestore[row_path][1] = progress_percent
            treestore[row_path][2] = progress_string
            treestore[row_path][3] = True
        else:
            treestore[row_path][3] = False
    def gui_dependency_frames_update(self, dependency_path):
        dependency = self.dependencies[dependency_path]
        treestore = self.dependencies_treestore
        parent_row_path = dependency.row_reference.get_path()
        parent_row_iter = treestore.get_iter(parent_row_path)
        child_row_iter = treestore.iter_children(parent_row_iter)
        while child_row_iter != None:
            treestore.remove(child_row_iter)
            child_row_iter = treestore.iter_next(child_row_iter)
        good_frame_ranges = 0
        if dependency.size != None:
            self.dependency_types[dependency.type].meta['size'] -= dependency.size
            self.queue_size -= dependency.size
        dependency_size = 0
        for frame_range in dependency.frames:
            if frame_range.start == frame_range.end:
                frames_name = str(frame_range.start)
            else:
                frames_name = '%i - %i' % (frame_range.start, frame_range.end)
            details = ''
            status = ''
            if frame_range.size > 0:
                dependency_size += frame_range.size
                human_size = human.size(frame_range.size)
                if frame_range.complete:
                    text_color = COLOR_DEFAULT
                    good_frame_ranges += 1
                else:
                    text_color = COLOR_WARNING
                    details = 'Some frames are missing.'
            else:
                human_size = ''
                text_color = COLOR_ALERT
                details = 'The whole range is missing.'
                status = 'Missing'

            if len(dependency.frames) == good_frame_ranges:
                dependency_status = ''
                dependency_color = COLOR_DEFAULT
                dependency_size_human = human.size(dependency_size)
            elif good_frame_ranges > 0:
                dependency_status = 'Incomplete'
                dependency_color = COLOR_WARNING
                dependency_size_human = human.size(dependency_size)
            else:
                dependency_status = 'Missing'
                dependency_color = COLOR_ALERT
                dependency_size_human = ''
            gobject.idle_add(self.gui_row_update, treestore, dependency.row_reference, {'5' : dependency_size_human, '6' : dependency_status, '7': dependency_color})
            frames_row_iter = self.dependencies_treestore.append(parent_row_iter, [frames_name, 0, '', False, details, human_size, status, text_color, True])
        if dependency_size > 0:
            # dependency.size = dependency_size
            self.queue_size += dependency_size
            self.dependency_types[dependency.type].meta['size'] += dependency_size
        # else:
        #     dependency.size = None
        self.gui_dependency_summary_update(dependency.type)
        # self.dependencies_treeview.expand_all()
    def gui_dependency_add_parent(self, dependency_path, parent):
        treestore = self.dependencies_treestore
        row_path = self.dependencies[dependency_path].row_reference.get_path()
        treestore[row_path][4] += parent + '\n'
    def gui_dependency_update(self, dependency_path, progress=0.0, progress_string=''):
        treestore = self.dependencies_treestore
        try:
            row_path = self.dependencies[dependency_path].row_reference.get_path()
            treestore[row_path][1] = progress
            treestore[row_path][2] = progress_string
            treestore[row_path][3] = True
        except KeyError:
            print 'No row reference for %s' % dependency_path

    def gui_row_update(self, treestore, row_reference, values):
        row_path = row_reference.get_path()
        for key, value in values.iteritems():
            # print treestore, row_path, key, value
            treestore[row_path][int(key)] = value
    def selected_dependencies_perform(self, widget, action):
        treeview = self.dependencies_treeview
        selection = treeview.get_selection()
        (model, row_paths) = selection.get_selected_rows()
        for row_path in row_paths:
            row_iter = model.get_iter(row_path)
            if model[row_path][0] in self.dependencies:
                self.gui_row_actions(row_path, action)
            elif model.iter_has_child(row_iter):
                if model.iter_parent(row_iter) == None:
                    child_row_iter = model.iter_children(row_iter)
                    while child_row_iter != None:
                        child_row_path = model.get_path(child_row_iter)
                        self.gui_row_actions(child_row_path, action)
                        child_row_iter = model.iter_next(child_row_iter)
                else:
                    child_row_iter = model.iter_children(row_iter)
                    while child_row_iter != None:
                        child_row_path = model.get_path(child_row_iter)
                        self.gui_row_actions(child_row_path, action)
                        child_row_iter = model.iter_next(child_row_iter)
                    self.gui_row_actions(row_path, action)
            else:
                self.gui_row_actions(row_path, action)
        if action in ['skip', 'unskip']:
            self.launch_thread(self.calculate_queue_size)

    def gui_row_actions(self, row_path, action):
        model = self.dependencies_treestore
        dependency = self.dependencies[model[row_path][0]]
        if action == 'fetch' and model[row_path][6] != True:
            self.fetch_queue.put(dependency)
        if action == 'skip' and model[row_path][6] != 'Skip':
            dependency.ignore = True
            model[row_path][6] = 'Skip'
            model[row_path][7] = COLOR_DISABLED
            self.dependency_types[dependency.type].meta['size'] -= dependency.size
        if action == 'unskip' and model[row_path][6] == 'Skip':
            dependency.ignore = False
            model[row_path][6] = ''
            model[row_path][7] = COLOR_DEFAULT
            self.dependency_types[dependency.type].meta['size'] += dependency.size
        


gobject.threads_init()
PyApp()
gtk.main()
