#!/usr/bin/python
# -*- coding: utf-8 -*-

import gtk
import os
import subprocess
import sys
import tempfile
import threading
import platform
import gobject
import re
import copy
import time
from datetime import datetime

try:
    cwd = os.getcwd()
    os.chdir(os.path.dirname(sys.argv[0]))
    sys.path.append("../..")
    from hyperspeed.stack import Stack, DEPENDENCY_TYPES
    from hyperspeed import mistika
    from hyperspeed import human
except ImportError:
    mistika = False

COLOR_DEFAULT = '#000000'
COLOR_DISABLED = '#888888'
COLOR_WARNING = '#ff8800'
COLOR_ALERT = '#cc0000'

class PyApp(gtk.Window):

    def __init__(self):
        super(PyApp, self).__init__()
        screen = self.get_screen()
        self.set_title("Consolidate Mistika structures")
        self.set_size_request(screen.get_width()/2-100, screen.get_height()-200)
        self.set_border_width(20)
        self.set_position(gtk.WIN_POS_CENTER)
        if 'darwin' in platform.system().lower():
            self.set_resizable(False) # Because resizing crashes the app on Mac
        self.connect("key-press-event",self.on_key_press_event)

        self.stacks = {}
        self.dependencies = {}
        self.threads = []
        self.queue_size = 0
        self.last_update = {'time':0, 'copied':0}

        vbox = gtk.VBox(False, 10)

        hbox = gtk.HBox(False, 10)
        hbox.pack_start(gtk.Label('Environments, groups or other structures to consolidate:'), False, False, 0)
        vbox.pack_start(hbox, False, False, 0)
        vbox.pack_start(self.init_stacks_window())

        hbox = gtk.HBox(False, 10)
        button = gtk.Button('Add structure ...')
        button.connect("clicked", self.add_file_dialog)
        hbox.pack_end(button, False, False, 0)
        button = gtk.Button('Remove selected')
        button.connect("clicked", self.gui_on_selected_stacks, 'remove')
        hbox.pack_end(button, False, False, 0)
        vbox.pack_start(hbox, False, False, 0)

        hbox = gtk.HBox(False, 10)
        hbox.pack_start(gtk.Label('Dependencies in loaded structures:'), False, False, 0)
        vbox.pack_start(hbox, False, False, 0)
        vbox.pack_start(self.init_dependencies_window())

        hbox = gtk.HBox(False, 10)
        self.status_label = gtk.Label('No stacks loaded')
        hbox.pack_start(self.status_label, False, False, 5)
        spinner = self.spinner_queue = gtk.Image()
        spinner.set_no_show_all(True)
        try:
            spinner.set_from_file('../../res/img/spinner01.gif')
        except:
            pass
        hbox.pack_start(spinner, False, False, 5)
        button = gtk.Button('Include selected')
        button.connect("clicked", self.gui_on_selected_dependencies, 'unskip')
        hbox.pack_end(button, False, False, 0)
        button = gtk.Button('Skip selected')
        button.connect("clicked", self.gui_on_selected_dependencies, 'skip')
        hbox.pack_end(button, False, False, 0)
        vbox.pack_start(hbox, False, False, 0)

        hbox = gtk.HBox(False, 10)
        button = gtk.Button('Destination folder ...')
        button.connect("clicked", self.set_destination_dialog)
        hbox.pack_start(button, False, False, 5)
        self.destination_folder_entry = gtk.Entry()
        hbox.pack_start(self.destination_folder_entry, False, False, 5)
        gtk.stock_add([(gtk.STOCK_COPY, "Copy", 0, 0, "")])
        button = self.button_copy = gtk.Button(stock=gtk.STOCK_COPY)
        button.connect("clicked", self.on_copy_start)
        hbox.pack_start(button, False, False, 5)
        gtk.stock_add([(gtk.STOCK_CANCEL, "Abort", 0, 0, "")])
        button = self.button_abort = gtk.Button(stock=gtk.STOCK_CANCEL)
        button.connect("clicked", self.on_copy_abort)
        button.set_no_show_all(True)
        hbox.pack_start(button, False, False, 5)
        vbox.pack_start(hbox, False, False, 0)

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
        #self.set_keep_above(True)
        #self.present()
        self.parse_command_line_arguments()
        # self.init_dependencies_daemon()

    def init_stacks_window(self):
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
        # treeview.expand_all()
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(treeview)
        return scrolled_window
    def init_dependencies_window(self):
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
        column = gtk.TreeViewColumn('Size', cell, text=5, foreground=7)
        column.set_resizable(True)
        treeview.append_column(column)
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn('Status')
        column.pack_start(cell, False)
        column.set_attributes(cell, text=6, foreground=7, visible=8)
        cell = gtk.CellRendererProgress()
        column.pack_start(cell, True)
        column.set_attributes(cell, value=1, text=2, visible=3)
        column.set_resizable(True)
        treeview.append_column(column)
        treeview.set_model(treestore)
        # treeview.expand_all()

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(treeview)
        return scrolled_window
    def parse_command_line_arguments(self):
        os.chdir(cwd)
        if len(sys.argv) > 1:
            i = 0
            while i < len(sys.argv) - 1:
                i += 1
                arg = sys.argv[i]
                if arg in ['-d']:
                    i += 1
                    self.destination_folder_entry.set_text(sys.argv[i])
                else:
                    self.gui_stack_add(arg)
    def on_quit(self, widget):
        print 'Closed by: ' + repr(widget)
        gtk.main_quit()
    def add_file_dialog(self, widget):
        if mistika:
            folder = os.path.join(mistika.projects_folder, mistika.project)
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
    def init_dependencies_daemon(self):
        t = self.dependencies_daemon_thread = threading.Thread(target=self.dependencies_daemon)
        self.threads.append(t)
        t.setDaemon(True)
        t.start()
    # def dependencies_daemon(self):

    def set_destination_dialog(self, widget):
        if mistika:
            folder = os.path.join(mistika.projects_folder, mistika.project)
        else:
            folder = '/'
        dialog = gtk.FileChooserDialog(title="Select destination folder", parent=None, action=gtk.FILE_CHOOSER_ACTION_CREATE_FOLDER, buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK), backend=None)
        dialog.set_select_multiple(True)
        #dialog.add_filter(filter)
        dialog.add_shortcut_folder('/home/mistika/MISTIKA-ENV')
        dialog.add_shortcut_folder(folder)
        dialog.set_current_folder(folder)
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            self.destination_folder_entry.set_text(dialog.get_filename())
        elif response == gtk.RESPONSE_CANCEL:
            print 'Closed, no files selected'
        dialog.destroy()
    def on_copy_start(self, widget):
        # print 'Launching copy thread'
        self.button_copy.hide()
        self.button_abort.show()
        self.abort = False
        self.launch_thread(self.io_copy)
    def on_copy_abort(self, widget):
        self.status_set('Aborted by user.')
        self.button_abort.hide()
        self.button_copy.show()
        self.abort = True
    def gui_row_update(self, treestore, row_reference, values):
        row_path = row_reference.get_path()
        for key, value in values.iteritems():
            # print treestore, row_path, key, value
            treestore[row_path][int(key)] = value
    def get_destination_path(self, dependency):
        name_parts = dependency.name.strip('/').split('/')
        if dependency.name.startswith('etc/'):
            return dependency.name.split('/', 1)[1]
        elif dependency.type == 'font':
            return os.path.join(self.dependency_types['font'].description, os.path.basename(dependency.path))
        elif len(name_parts) > 2 and name_parts[1] == 'PRIVATE':
            return '/'.join(name_parts[1:])
        elif dependency.name.startswith('/'):
            return os.path.join('Media', dependency.path.lstrip('/'))
        else:
            return os.path.join(dependency.name)
    def io_copy(self):
        copy_start_time = time.time()
        # self.dependencies_treestore.handler_block()
        destination_folder = self.destination_folder_entry.get_text()
        if not os.path.isdir(destination_folder):
            try:
                os.makedirs(destination_folder)
            except OSError:
                print 'Could not create destination folder. Aborting.'
                self.status_set('Could not create destination folder.')
                return
        if not destination_folder.endswith('/'):
            destination_folder += '/'
        treestore = self.stacks_treestore
        for stack_path in self.stacks:
            if self.abort:
                return
            stack = self.stacks[stack_path]
            row_path = stack.row_reference.get_path()
            treestore[row_path][1] = 0.0
            gobject.idle_add(self.gui_row_update, treestore, stack.row_reference, {'1': 0.0, '2' : 'Copying', '3': True, '4': False})
            cmd = ['rsync', '-ua', stack_path, destination_folder]
            subprocess.call(cmd)
            gobject.idle_add(self.gui_row_update, treestore, stack.row_reference, {'1': 0.0, '2' : 'Copied', '3': False, '4': True})
        treestore = self.dependencies_treestore
        for dependency_path, dependency in self.dependencies.iteritems():
            if self.abort:
                return
            if dependency.size in [None, 0] or dependency.ignore:
                continue
            row_path = dependency.row_reference.get_path()
            gobject.idle_add(self.gui_row_update, treestore, dependency.row_reference, {'1': 0.0,  '3': True, '8' : False})
            is_sequence = '%' in dependency_path
            destination_path = os.path.join(destination_folder, self.get_destination_path(dependency).lstrip('/'))
            # destination_path = os.path.join(dependency_path.lstrip('/'), destination_folder).rstrip('/')
            if not os.path.isdir(os.path.dirname(destination_path)):
                try:
                    os.makedirs(os.path.dirname(destination_path))
                except OSError:
                    print 'Could not create destination directory'
            if is_sequence:
                sequence_files = []
                basename = os.path.basename(dependency_path)
                for frame_range in dependency.frame_ranges:
                    for frame_n in range(frame_range.start, frame_range.end+1):
                        sequence_files.append(basename % frame_n)
                sequence_length = len(sequence_files)
                frames_done = 0
                temp_handle = tempfile.NamedTemporaryFile()
                temp_handle.write('\n'.join(sequence_files) + '\n')
                temp_handle.flush()
                cmd = ['rsync', '-uavv', '--out-format="%n was copied"', '--files-from=%s' % temp_handle.name, os.path.dirname(dependency_path)+'/', os.path.dirname(destination_path)+'/']
            else:
                cmd = ['rsync', '--progress', '-ua', dependency_path, destination_path]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            while proc.returncode == None:
                if self.abort:
                    proc.kill()
                    if is_sequence:
                        temp_handle.close()
                    return
                output = ''
                char = None
                while not char in ['\r', '\n']:
                    proc.poll()
                    if proc.returncode != None:
                        break
                    char = proc.stdout.read(1)
                    output += char
                fields = output.split()
                if len(fields) >= 4 and fields[1].endswith('%'):
                    progress_percent = float(fields[1].strip('%'))
                    self.set_progress(extra_bytes=int(fields[0]))
                    gobject.idle_add(self.gui_dependency_summary_update, dependency.type, int(fields[0]))
                    # self.status_set(fields[2])
                    gobject.idle_add(self.gui_row_update, treestore, dependency.row_reference, {'1': progress_percent, '2': fields[1]})
                elif is_sequence and output.strip().endswith('is uptodate') or output.strip().endswith('was copied'):
                    frames_done += 1
                    progress_percent = float(frames_done) / float(sequence_length)
                    progress_string = '%5.2f%%' % progress_percent
                    gobject.idle_add(self.gui_row_update, treestore, dependency.row_reference, {'1': progress_percent, '2': progress_string})
                proc.poll()
            # subprocess.call(cmd)
            if is_sequence:
                temp_handle.close()
            if proc.returncode == 0:
                # dependency.ignore = True
                self.dependency_types[dependency.type].meta['copied'] += dependency.size
                gobject.idle_add(self.gui_row_update, treestore, dependency.row_reference, {'1': 100.0, '6' : 'Copied', '3': False, '8' : True})
                self.set_progress()
            else:
                gobject.idle_add(self.gui_row_update, treestore, dependency.row_reference, {'6' : 'Error %i' % proc.returncode, '3': False, '7' : COLOR_ALERT, '8' : True})
            gobject.idle_add(self.gui_dependency_summary_update, dependency.type)
        time_delta = time.time() - copy_start_time
        self.status_set('Copy finished in %s' % human.duration(time_delta))
        self.button_abort.hide()
        self.button_copy.show()
        return
    def set_progress(self, extra_bytes=0):
        now = time.time()
        if self.last_update['time'] < now - 1:
            this_update = {'copied':0}
            for dependency_type in self.dependency_types:
                this_update['copied'] += self.dependency_types[dependency_type].meta['copied']
            this_update['copied'] += extra_bytes
            speed = float(this_update['copied'] - self.last_update['copied']) / (now - self.last_update['time'])
            bytes_left = self.queue_size - this_update['copied']
            etl = float(bytes_left) / speed
            status = human.size(bytes_left) + ' remaining. Estimated time left: ' + human.duration(etl) + ' @ ' + human.size(speed) + '/s'
            self.status_set(status)
            this_update['time'] = now
            self.last_update = this_update
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
                if dependency.size != None:
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
        self.status_set('%s in queue' % human.size(self.queue_size))
    def stack_read_progress(self, stack, progress):
        treestore = self.stacks_treestore
        row_path = stack.row_reference.get_path()
        progress_percent = progress * 100.0
        progress_string = '%5.2f%%' % progress_percent
        progress_string = '   Looking for dependencies   '
        # print stack, progress, progress_string
        show_progress = True
        if progress == 1.0:
            progress_string = '   Dependencies loaded   '
            show_progress = False
        gobject.idle_add(self.gui_row_update, treestore, stack.row_reference, {'1': progress_percent, '2' : progress_string, '3': show_progress, '4': not show_progress})
        self.status_set('%s in queue' % human.size(self.queue_size))
    def gui_dependency_add(self, dependency):
        treestore = self.dependencies_treestore
        self.dependency_types[dependency.type].meta['count'] += 1
        parent_stacks = []
        for parent_stack in dependency.parents:
            parent_stacks.append(parent_stack.path)
        details = '\n'.join(parent_stacks)
        if dependency.size == None:
            human_size = ''
            status = 'Missing'
            text_color = COLOR_ALERT
        else:
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
        if dependency.size != None:
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
    def status_set(self, status):
        gobject.idle_add(self.status_label.set_text, status)
    def gui_on_selected_dependencies(self, widget, action):
        treeview = self.dependencies_treeview
        selection = treeview.get_selection()
        (model, row_paths) = selection.get_selected_rows()
        for row_path in row_paths:
            row_iter = model.get_iter(row_path)
            if model.iter_has_child(row_iter):
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
    def gui_on_selected_stacks(self, widget, action):
        treeview = self.stacks_treeview
        selection = treeview.get_selection()
        (model, row_paths) = selection.get_selected_rows()
        for row_path in row_paths:
            row_iter = model.get_iter(row_path)
            if action == 'remove':
                self.gui_stack_remove(model[row_path][0])
    def gui_stack_remove(self, stack):
        if type(stack) != Stack:
            stack = self.stacks[stack]
        for dependency in stack.dependencies:
            frames_before = self.dependencies[dependency.path].frames
            self.dependencies[dependency.path].parent_remove(stack)
            if len(self.dependencies[dependency.path].parents) == 0:
                treestore = self.dependencies_treestore
                row_path = dependency.row_reference.get_path()
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
        self.calculate_queue_size()

    def gui_row_actions(self, row_path, action):
        model = self.dependencies_treestore
        dependency = self.dependencies[model[row_path][0]]
        if dependency.size == None:
            return
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
    def calculate_queue_size(self):
        gobject.idle_add(self.status_label.set_property, 'visible', False)
        gobject.idle_add(self.spinner_queue.set_property, 'visible', True)
        total = 0
        for dependency_path, dependency in self.dependencies.iteritems():
            if dependency.size == None:
                continue
            elif dependency.ignore == True:
                continue
            else:
                total += dependency.size
        for dependency_type in self.dependency_types:
            gobject.idle_add(self.gui_dependency_summary_update, dependency_type)
        self.queue_size = total
        gobject.idle_add(self.spinner_queue.set_property, 'visible', False)
        gobject.idle_add(self.status_label.set_text, '%s in queue' % human.size(self.queue_size))
        gobject.idle_add(self.status_label.set_property, 'visible', True)

    def on_key_press_event(self,widget,event):
        keyval = event.keyval
        keyval_name = gtk.gdk.keyval_name(keyval)
        state = event.state
        ctrl = (state & gtk.gdk.CONTROL_MASK)
        command = (state & gtk.gdk.MOD1_MASK)
        if ctrl or command and keyval_name == 'q':
            self.on_quit(widget)
        else:
            return False
        return True
    def gui_delete_frame_range(self):
        for model, row_reference in self.row_references:
            row_path = row_reference.get_path()
            row_iter = model.get_iter(row_path)
            model.remove(row_iter)
        self.calculate_queue_size()
        
gobject.threads_init()
PyApp()
gtk.main()