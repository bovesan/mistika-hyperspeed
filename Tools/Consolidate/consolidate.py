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

try:
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


        vbox = gtk.VBox(False, 10)

        hbox = gtk.HBox(False, 10)
        hbox.pack_start(gtk.Label('Environments, groups or other structures to consolidate:'), False, False, 0)
        vbox.pack_start(hbox, False, False, 0)

        treestore = self.stacks_treestore = gtk.TreeStore(str, float, str, bool) # Name, progress float, progress text, progress visible
        treeview = self.stacks_treeview = gtk.TreeView()
        treeview.set_rules_hint(True)
        cell = gtk.CellRendererText()
        cell.set_property("editable", True)
        column = gtk.TreeViewColumn('', cell, text=0)
        column.set_resizable(True)
        column.set_expand(True)
        treeview.append_column(column)
        cell = gtk.CellRendererProgress()
        column = gtk.TreeViewColumn('', cell, value=1, text=2)
        column.add_attribute(cell, 'visible', 3)
        column.set_expand(True)
        column.set_resizable(True)
        treeview.append_column(column)
        treeview.set_model(treestore)
        treeview.expand_all()
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(treeview)
        vbox.pack_start(scrolled_window)

        hbox = gtk.HBox(False, 10)
        button = gtk.Button('Add structure ...')
        button.connect("clicked", self.add_file_dialog)
        hbox.pack_end(button, False, False, 0)
        vbox.pack_start(hbox, False, False, 0)

        hbox = gtk.HBox(False, 10)
        hbox.pack_start(gtk.Label('Dependencies in loaded structures:'), False, False, 0)
        vbox.pack_start(hbox, False, False, 0)

        treestore = self.dependencies_treestore = gtk.TreeStore(str, float, str, bool, str, str, str, str, bool) # Name, progress float, progress text, progress visible, details, human size, status, text color, status visible
        treeview = self.dependencies_treeview = gtk.TreeView()
        treeview.set_tooltip_column(4)
        treeview.set_rules_hint(True)
        treeselection = treeview.get_selection()
        treeselection.set_mode(gtk.SELECTION_MULTIPLE)
        for dependency_type_id, dependency_type in DEPENDENCY_TYPES.iteritems():
            row_iter = treestore.append(None, [dependency_type.description, 0.0, '', False, dependency_type.description, '', '', COLOR_DISABLED, False])
            row_path = treestore.get_path(row_iter)
            dependency_type.row_reference = gtk.TreeRowReference(treestore, row_path)
        cell = gtk.CellRendererText()
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
        # column = gtk.TreeViewColumn('Status', cell, text=6, foreground=7)
        cell = gtk.CellRendererProgress()
        column.pack_start(cell, True)
        column.set_attributes(cell, value=1, text=2, visible=3)
        column.set_resizable(True)
        treeview.append_column(column)
        cell = gtk.CellRendererProgress()
        column = gtk.TreeViewColumn('Progress', cell, value=1, text=2)
        column.add_attribute(cell, 'visible', 3)
        # column.set_expand(True)
        column.set_resizable(True)
        # treeview.append_column(column)
        treeview.set_model(treestore)
        treeview.expand_all()

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(treeview)
        vbox.pack_start(scrolled_window)



        hbox = gtk.HBox(False, 10)
        self.status_label = gtk.Label('No stacks loaded')
        hbox.pack_start(self.status_label, False, False, 5)
        spinner = self.spinner_queue = gtk.Image()
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
        vbox2 = gtk.HBox(False, 10)
        hbox2 = gtk.HBox(False, 10)
        hbox2.pack_start(gtk.Label('Include:'), False, False, 0)
        vbox2.pack_start(hbox2, False, False, 0)
        button = gtk.CheckButton('.js')
        vbox2.pack_start(button, False, False, 0)
        button = gtk.CheckButton('.dat')
        vbox2.pack_start(button, False, False, 0)
        button = gtk.CheckButton('All other files')
        vbox2.pack_start(button, False, False, 0)
        button = gtk.CheckButton('Files stored in current project')
        vbox2.pack_start(button, False, False, 0)
        vbox2.pack_start(button, False, False, 0)
        hbox.pack_start(vbox2, False, False, 0)
        # vbox.pack_start(hbox, False, False, 0)


        hbox = gtk.HBox(False, 10)
        button = gtk.Button('Destination folder ...')
        button.connect("clicked", self.set_destination_dialog)
        hbox.pack_start(button, False, False, 5)
        self.destination_folder_entry = gtk.Entry()
        hbox.pack_start(self.destination_folder_entry, False, False, 5)
        button = gtk.Button('Copy')
        button.connect("clicked", self.on_copy_start)
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
        spinner.set_property('visible', False)
        #self.set_keep_above(True)
        #self.present()
        if len(sys.argv) > 1:
            for stack_path in sys.argv[1:]:
                self.gui_stack_add(stack_path)


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
        self.stacks[stack_path] = Stack(stack_path)
        stack = self.stacks[stack_path]
        row_iter = self.stacks_treestore.append(None, [stack_path, 0.0, '0%', False])
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
        self.launch_thread(self.io_copy)
    def gui_row_update(self, treestore, row_reference, values):
        row_path = row_reference.get_path()
        for key, value in values.iteritems():
            print treestore, row_path, key, value
            treestore[row_path][int(key)] = value
    def io_copy(self):
        # self.dependencies_treestore.handler_block()
        destination_folder = self.destination_folder_entry.get_text()
        if not os.path.isdir(destination_folder):
            try:
                os.makedirs(destination_folder)
            except OSError:
                print 'Could not create destination folder. Aborting.'
                return
        if not destination_folder.endswith('/'):
            destination_folder += '/'
        treestore = self.stacks_treestore
        for stack_path in self.stacks:
            stack = self.stacks[stack_path]
            row_path = stack.row_reference.get_path()
            treestore[row_path][1] = 0.0
            gobject.idle_add(self.gui_row_update, treestore, stack.row_reference, {'1': 0.0, '3': True, '8' : False})
            cmd = ['rsync', '-ua', stack_path, destination_folder]
            subprocess.call(cmd)
            gobject.idle_add(self.gui_row_update, treestore, stack.row_reference, {'1': 0.0, '2' : 'Copied', '3': False, '8' : True})
        treestore = self.dependencies_treestore
        for dependency_path, dependency in self.dependencies.iteritems():
            if dependency.size == None:
                continue
            row_path = dependency.row_reference.get_path()
            gobject.idle_add(self.gui_row_update, treestore, dependency.row_reference, {'1': 0.0,  '3': True, '8' : False})
            destination_path = os.path.join(dependency_path.lstrip('/'), destination_folder).rstrip('/')
            cmd = ['rsync', '-ua', dependency_path, destination_path]
            subprocess.call(cmd)
            gobject.idle_add(self.gui_row_update, treestore, dependency.row_reference, {'1': 100.0, '6' : 'Copied', '3': False, '8' : True})
        return
        self.copy_queue = []
        for dependency_path, dependency in self.dependencies.iteritems():
            row_path = dependency.row_reference.get_path()
            self.copy_queue.append(self.dependencies_treestore[row_path][0])
        # print repr(self.copy_queue)
        with tempfile.NamedTemporaryFile() as temp:
            temp.write('\n'.join(self.copy_queue) + '\n')
            temp.flush()
            # subprocess.call(['cat', temp.name])
            # rsync -a --files-from=/tmp/foo /usr remote:/backup
            cmd = ['rsync', '--progress', '-uavv', '--files-from=%s' % temp.name, '/', destination_folder]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            while proc.returncode == None:
                proc.poll()
                output = proc.stdout.readline()
                print output,
                if output.strip().endswith('is uptodate'):
                    f_path = output.strip()[:-11].strip()
                    if not f_path.startswith('/'):
                        f_path = '/'+f_path
                    self.gui_dependency_update(f_path, 100.0, 'Up to date')
                elif output.strip().endswith('failed: No such file or directory (2)'):
                    f_path = output.split('"', 1)[1].rsplit('"')[0]
                    if not f_path.startswith('/'):
                        f_path = '/'+f_path
                    self.gui_dependency_update(f_path, 0.0, 'Not found')
                elif '/'+output.strip() in self.dependencies:
                    f_path = output.strip()
                    if not f_path.startswith('/'):
                        f_path = '/'+f_path
                    self.gui_dependency_update(f_path, 0.0, 'Copying')
                    current_path = f_path
                elif 'to-check' in output:
                    self.gui_dependency_update(current_path, 100.0, 'Copied')
                    m = re.findall(r'to-check=(\d+)/(\d+)', output)
                    progress = (100 * (int(m[0][1]) - int(m[0][0]))) / len(self.copy_queue)
                    sys.stdout.write('\rDone: ' + str(progress) + '%')
                    sys.stdout.flush()
                    if int(m[0][0]) == 0:
                        break
            status = proc.returncode
            # status = subprocess.call(cmd)
            # gobject.idle_add(self.gui_dependency_add, dependency)
            if status == 0:
                gobject.idle_add(self.gui_status_set, 'Finished successfully')
            else:
                gobject.idle_add(self.gui_status_set, 'Finished with errors')
    def launch_thread(self, method):
        t = threading.Thread(target=method)
        self.threads.append(t)
        t.setDaemon(True)
        t.start()
        return t
    def get_dependencies(self, stack):
        # print 'get_dependencies(%s)' % repr(stack)
        for dependency in stack.iter_dependencies(progress_callback=self.stack_read_progress):
            #print dependency.name
            if not dependency.path in self.dependencies:
                self.dependencies[dependency.path] = dependency
                if dependency.size != None:
                    self.queue_size += dependency.size
                self.dependencies[dependency.path].parents.append(stack)
                gobject.idle_add(self.gui_dependency_add, dependency)
            else:
                this_frame_range = dependency.raw_frame_ranges[0]
                if '%' in dependency.path and not this_frame_range in self.dependencies[dependency.path].raw_frame_ranges:
                    self.dependencies[dependency.path].frames_range_add(this_frame_range)
                    gobject.idle_add(self.gui_dependency_frames_update, dependency.path)
                if not stack in self.dependencies[dependency.path].parents:
                    self.dependencies[dependency.path].parents.append(stack)
                    gobject.idle_add(self.gui_dependency_add_parent, dependency.path, stack.path)
        gobject.idle_add(self.gui_status_set, '%s in queue' % human.size(self.queue_size))
    def stack_read_progress(self, stack, progress):
        gobject.idle_add(self.gui_stack_set_progress, stack, progress)
    def gui_stack_set_progress(self, stack, progress):
        row_path = stack.row_reference.get_path()
        progress_percent = progress * 100.0
        progress_string = '%5.2f%%' % progress_percent
        progress_string = 'Looking for dependencies'
        # print stack, progress, progress_string
        show_progress = True
        if progress == 1.0:
            progress_string = 'Loaded dependencies'
            show_progress = False
        self.stacks_treestore[row_path][1] = progress_percent
        self.stacks_treestore[row_path][2] = progress_string
        self.stacks_treestore[row_path][3] = show_progress
    def gui_dependency_add(self, dependency):
        treestore = self.dependencies_treestore
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
        parent_row_path = DEPENDENCY_TYPES[dependency.type].row_reference.get_path()
        parent_iter = treestore.get_iter(parent_row_path)
        row_iter = self.dependencies_treestore.append(parent_iter, [dependency.path, 0, '', False, details, human_size, status, text_color, True])
        row_path = self.dependencies_treestore.get_path(row_iter)
        self.dependencies[dependency.path].row_reference = gtk.TreeRowReference(self.dependencies_treestore, row_path)
        self.dependencies_treeview.expand_all()
        if '%' in dependency.path:
            gobject.idle_add(self.gui_dependency_frames_update, dependency.path)
    def gui_dependency_frames_update(self, dependency_path):
        treestore = self.dependencies_treestore
        parent_row_path = self.dependencies[dependency_path].row_reference.get_path()
        parent_row_iter = treestore.get_iter(parent_row_path)
        child_row_iter = treestore.iter_children(parent_row_iter)
        while child_row_iter != None:
            treestore.remove(child_row_iter)
            child_row_iter = treestore.iter_next(child_row_iter)
        for frame_range in self.dependencies[dependency_path].frames:
            if frame_range.start == frame_range.end:
                frames_name = str(frame_range.start)
            else:
                frames_name = '%i - %i' % (frame_range.start, frame_range.end)
            details = ''
            status = ''
            if frame_range.size > 0:
                human_size = human.size(frame_range.size)
                if frame_range.complete:
                    text_color = COLOR_DEFAULT
                else:
                    text_color = COLOR_WARNING
                    details = 'Some frames are missing.'
                    gobject.idle_add(self.gui_row_update, treestore, self.dependencies[dependency_path].row_reference, {'7': COLOR_WARNING})
            else:
                human_size = ''
                text_color = COLOR_ALERT
                details = 'The whole range is missing.'
                gobject.idle_add(self.gui_row_update, treestore, self.dependencies[dependency_path].row_reference, {'7': COLOR_WARNING})
                status = 'Missing'
            frames_row_iter = self.dependencies_treestore.append(parent_row_iter, [frames_name, 0, '', False, details, human_size, status, text_color])
        self.dependencies_treeview.expand_all()
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
    def gui_status_set(self, status):
        self.status_label.set_text(status)
    def gui_on_selected_dependencies(self, widget, action):
        treeview = self.dependencies_treeview
        selection = treeview.get_selection()
        (model, row_paths) = selection.get_selected_rows()
        for row_path in row_paths:
            row_iter = model.get_iter(row_path)
            if model.iter_has_child(row_iter):
                child_row_iter = model.iter_children(row_iter)
                while child_row_iter != None:
                    child_row_path = model.get_path(child_row_iter)
                    self.gui_row_actions(child_row_path, action)
                    child_row_iter = model.iter_next(child_row_iter)
            else:
                self.gui_row_actions(row_path, action)
        if action in ['skip', 'unskip']:
            self.launch_thread(self.calculate_queue_size)
    def gui_row_actions(self, row_path, action):
        model = self.dependencies_treestore
        dependency = self.dependencies[model[row_path][0]]
        if dependency.size == None:
            return
        if action == 'skip':
            dependency.ignore = True
            model[row_path][6] = 'Skip'
            model[row_path][7] = COLOR_DISABLED
        if action == 'unskip':
            dependency.ignore = False
            model[row_path][6] = ''
            model[row_path][7] = COLOR_DEFAULT
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
        
gobject.threads_init()
PyApp()
gtk.main()