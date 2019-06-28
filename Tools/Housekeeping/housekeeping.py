#!/usr/bin/python
# -*- coding: utf-8 -*-

import gtk
import glob
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
import stat

try:
    cwd = os.getcwd()
    os.chdir(os.path.dirname(os.path.realpath(sys.argv[0])))
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

class Folder:
    row_reference = None
    path = None
    extensions = []
    @property
    def extensionsString(self):
        return ', '.join(self.extensions)
    @extensionsString.setter
    def extensionsString(self, value):
        self.extensions = [x.strip() for x in value.split(',')]
    def __init__(self, path):
        self.path = path
        pass

class Excess:
    row_reference = None
    size = None
    path = None
    status = None
    def __init__(self, path):
        self.path = path
        file_stat = os.stat(path)
        self.size = file_stat[stat.ST_SIZE]
        if oct(file_stat[stat.ST_MODE])[-3] == '2':
            self.status = 'Disabled'

class PyApp(gtk.Window):

    def __init__(self):
        super(PyApp, self).__init__()
        screen = self.get_screen()
        self.set_title("Housekeeping")
        self.set_size_request(screen.get_width()/2-100, screen.get_height()-200)
        self.set_border_width(20)
        self.set_position(gtk.WIN_POS_CENTER)
        if 'darwin' in platform.system().lower():
            self.set_resizable(False) # Because resizing crashes the app on Mac
        self.connect("key-press-event",self.on_key_press_event)

        self.stacks = {}
        self.folders = {}
        self.dependencies = {}
        self.excess = {}
        self.files = []
        self.threads = []
        self.queue_size = 0
        self.last_update = {'time':0, 'copied':0}

        vbox = gtk.VBox(False, 10)

        vbox.pack_start(self.init_stacks_window())

        hbox = gtk.HBox(False, 10)
        button = gtk.Button('Add structure ...')
        button.connect("clicked", self.add_file_dialog)
        hbox.pack_end(button, False, False, 0)
        button = gtk.Button('Remove selected')
        button.connect("clicked", self.gui_on_selected_stacks, 'remove')
        hbox.pack_end(button, False, False, 0)
        vbox.pack_start(hbox, False, False, 0)

        vbox.pack_start(self.init_folders_window())

        hbox = gtk.HBox(False, 10)
        button = gtk.Button('Add folder ...')
        button.connect("clicked", self.add_folder_dialog)
        hbox.pack_end(button, False, False, 0)
        button = gtk.Button('Remove selected')
        button.connect("clicked", self.gui_on_selected_folders, 'remove')
        hbox.pack_end(button, False, False, 0)
        vbox.pack_start(hbox, False, False, 0)

        vbox.pack_start(self.init_excess_window())

        hbox = gtk.HBox(False, 10)
        self.status_label = gtk.Label('No excess files')
        hbox.pack_start(self.status_label, False, False, 5)
        spinner = self.spinner_queue = gtk.Image()
        spinner.set_no_show_all(True)
        try:
            spinner.set_from_file('../../res/img/spinner01.gif')
        except:
            pass
        hbox.pack_start(spinner, False, False, 5)
        button = self.button_copy = gtk.Button('Permanently delete selected, disabled files')
        button.connect("clicked", self.gui_on_selected_excess, 'delete')
        hbox.pack_end(button, False, False, 5)
        button = self.button_copy = gtk.Button('Re-enable selected files')
        button.connect("clicked", self.gui_on_selected_excess, 'enable')
        hbox.pack_end(button, False, False, 5)
        button = self.button_copy = gtk.Button('Disable selected files')
        button.connect("clicked", self.gui_on_selected_excess, 'disable')
        hbox.pack_end(button, False, False, 5)
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
        self.add_defaults() 
        gobject.idle_add(self.bring_to_front)
    def gui_on_selected_excess(self, widget, action):
        treeview = self.excess_treeview
        selection = treeview.get_selection()
        (model, row_paths) = selection.get_selected_rows()
        excess_list = []
        for row_path in row_paths:
            row_iter = model.get_iter(row_path)
            excess_list.append(model[row_path][0])
        for excess_path in excess_list:
            if action == 'disable':
                self.excess_disable(excess_path)
            if action == 'enable':
                self.excess_enable(excess_path)
            if action == 'delete':
                self.excess_delete(excess_path)

    def excess_disable(self, excess):
        if type(excess) != Excess:
            excess = self.excess[excess]
        mode = os.lstat(excess.path).st_mode
        os.chmod(excess.path, mode & 0222)
        excess.status = 'Disabled'
        gobject.idle_add(self.gui_row_update, self.excess_treestore, excess.row_reference, {'6': excess.status})

    def excess_enable(self, excess):
        if type(excess) != Excess:
            excess = self.excess[excess]
        mode = os.lstat(excess.path).st_mode
        if oct(mode)[-3] == '2':
            mode |= 0400
        if oct(mode)[-2] == '2':
            mode |= 0040
        if oct(mode)[-1] == '2':
            mode |= 0004
        os.chmod(excess.path, mode)
        excess.status = None
        gobject.idle_add(self.gui_row_update, self.excess_treestore, excess.row_reference, {'6': excess.status})

    def excess_delete(self, excess):
        if type(excess) != Excess:
            excess = self.excess[excess]
        if excess.status != 'Disabled':
            return
        os.remove(excess.path)
        self.remove_file(excess.path)
        
    
    def bring_to_front(self):
        self.present()      

    def add_defaults(self):
        for path in glob.glob(os.path.join(mistika.projects_folder, mistika.project, 'DATA/*.env')):
            self.gui_stack_add(path)
        self.gui_folder_add(os.path.join(mistika.projects_folder, mistika.project, 'PRIVATE'), ['.dat'])
        for path in glob.glob(os.path.join('/Volumes/MATERIAL_HF/MISTIKA_MEDIA', mistika.project)):
            self.gui_folder_add(path)

    def init_stacks_window(self):
        treestore = self.stacks_treestore = gtk.TreeStore(str, float, str, bool, bool) # Name, progress float, progress text, progress visible, status visible
        treeview = self.stacks_treeview = gtk.TreeView()
        treeview.set_rules_hint(True)
        cell = gtk.CellRendererText()
        cell.set_property("editable", False)
        column = gtk.TreeViewColumn('Stacks', cell, text=0)
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
        return scrolled_window

    def init_folders_window(self):
        treestore = self.folders_treestore = gtk.TreeStore(str, float, str, bool, bool, str) # Name, progress float, progress text, progress visible, status visible, extensions
        treeview = self.folders_treeview = gtk.TreeView()
        treeview.set_rules_hint(True)
        cell = gtk.CellRendererText()
        cell.set_property("editable", False)
        column = gtk.TreeViewColumn('Folders to clean', cell, text=0)
        column.set_resizable(True)
        column.set_expand(True)
        treeview.append_column(column)
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn('Filter', cell, text=5)
        column.set_resizable(True)
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
        return scrolled_window

    def init_excess_window(self):
        treestore = self.excess_treestore = gtk.TreeStore(str, float, str, bool, str, str, str, str, bool) # Name, progress float, progress text, progress visible, details, human size, status, text color, status visible
        treeview = self.excess_treeview = gtk.TreeView()
        treeview.set_tooltip_column(4)
        treeview.set_rules_hint(True)
        treeselection = treeview.get_selection()
        treeselection.set_mode(gtk.SELECTION_MULTIPLE)
        cell = gtk.CellRendererText()
        cell.set_property("editable", False)
        column = gtk.TreeViewColumn('Excess files', cell, text=0, foreground=7)
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
        treeview.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        # treeview.expand_all()

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(treeview)
        return scrolled_window
    def parse_command_line_arguments(self):
        try:
            os.chdir(cwd)
        except OSError as e:
            pass
        if len(sys.argv) > 1:
            i = 0
            while i < len(sys.argv) - 1:
                i += 1
                arg = sys.argv[i]
                if os.path.exists(arg):
                    self.gui_stack_add(arg)    
    def on_quit(self, widget):
        print 'Closed by: ' + repr(widget)
        gtk.main_quit()
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
        t = threading.Thread(target=self.get_dependencies, args=[stack])
        self.threads.append(t)
        t.setDaemon(True)
        t.start()

    def add_folder_dialog(self, widget):
        if mistika:
            folder = os.path.join(mistika.projects_folder, mistika.project)
        else:
            folder = '/'
        dialog = gtk.FileChooserDialog(title="Add folders", parent=None, action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER, buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK), backend=None)
        dialog.set_select_multiple(True)
        #dialog.add_filter(filter)
        dialog.add_shortcut_folder(mistika.env_folder)
        dialog.add_shortcut_folder(folder)
        dialog.set_current_folder(folder)
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            for folder_path in dialog.get_filenames():
                self.gui_folder_add(folder_path)
        elif response == gtk.RESPONSE_CANCEL:
            print 'Closed, no files selected'
        dialog.destroy()

    def gui_folder_add(self, folder_path, extensions=[]):
        if folder_path in self.folders:
            return
        folder = self.folders[folder_path] = Folder(folder_path)
        folder.extensions = extensions
        row_iter = self.folders_treestore.append(None, [folder_path, 0.0, '0%', False, False, folder.extensionsString])
        row_path = self.folders_treestore.get_path(row_iter)
        folder.row_reference = gtk.TreeRowReference(self.folders_treestore, row_path)
        t = threading.Thread(target=self.get_files, args=[folder])
        self.threads.append(t)
        t.setDaemon(True)
        t.start()
    def get_files(self, folder):
        print "get_files", folder.path
        gobject.idle_add(self.gui_row_update, self.folders_treestore, folder.row_reference, {'1': 0, '2' : 'Indexing', '3': True, '4': False})
        i = 0
        for root, dir_names, file_names in os.walk(folder.path, topdown=True):
            for file_name in file_names:
                file_path = os.path.join(root, file_name)
                if folder.extensions:
                    if not os.path.splitext(file_name)[-1] in folder.extensions:
                        continue
                self.add_file(file_path)
        gobject.idle_add(self.gui_row_update, self.folders_treestore, folder.row_reference, {'1': 1, '2' : 'Loaded', '3': False, '4': True})

    def gui_row_update(self, treestore, row_reference, values):
        row_path = row_reference.get_path()
        for key, value in values.iteritems():
            # print treestore, row_path, key, value
            treestore[row_path][int(key)] = value

    def launch_thread(self, method):
        t = threading.Thread(target=method)
        self.threads.append(t)
        t.setDaemon(True)
        t.start()
        return t
    def add_file(self, file_path):
        print file_path
        self.files.append(file_path)
        if not file_path in self.dependencies:
            self.add_excess(file_path)
    def remove_file(self, file_path):
        print 'remove_file(%s)' % file_path
        try:
            self.remove_excess(self.excess[file_path])
        except KeyError:
            pass
        self.files.remove(file_path)
    def add_excess(self, file_path):
        if not file_path in self.excess:
            excess = self.excess[file_path] = Excess(file_path)
            gobject.idle_add(self.gui_excess_add, excess)
    def remove_excess(self, excess):
        if excess.path in self.excess:
            del self.excess[excess.path]
            gobject.idle_add(self.gui_excess_remove, excess)
    def add_dependency(self, dependency, stack):
        if dependency.path in self.excess:
            self.remove_excess(self.excess[dependency.path]) 
        if not dependency.path in self.dependencies:
            self.dependencies[dependency.path] = copy.copy(dependency)
            # gobject.idle_add(self.gui_dependency_add, dependency)
        else:
            dependency = self.dependencies[dependency.path]
            with dependency.lock:
                if not stack in dependency.parents:
                    dependency.parents.append(stack)
                    # gobject.idle_add(self.gui_dependency_add_parent, dependency.path, stack.path)
    def remove_dependency(self, dependency):
        try:
            del self.dependencies[dependency.path]
        except KeyError:
            pass
        if dependency.path in self.files:
            self.add_excess(dependency.path)
    def get_dependencies(self, stack):
        for dependency in stack.iter_dependencies(progress_callback=self.stack_read_progress):
            self.add_dependency(dependency, stack)
    def stack_read_progress(self, stack, progress):
        treestore = self.stacks_treestore
        row_path = stack.row_reference.get_path()
        progress_percent = progress * 100.0
        progress_string = '%5.2f%%' % progress_percent
        progress_string = '   Loading dependencies   '
        # print stack, progress, progress_string
        show_progress = True
        if progress == 1.0:
            progress_string = '   Dependencies loaded   '
            show_progress = False
        gobject.idle_add(self.gui_row_update, treestore, stack.row_reference, {'1': progress_percent, '2' : progress_string, '3': show_progress, '4': not show_progress})
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
        if dependency.size != None:
            self.dependency_types[dependency.type].meta['size'] += dependency.size
        self.gui_dependency_summary_update(dependency.type)
    def gui_excess_add(self, excess):
        treestore = self.excess_treestore
        human_size = human.size(excess.size)
        status = excess.status
        details = ''
        text_color = COLOR_DEFAULT
        parent_iter = None
        row_iter = treestore.append(parent_iter, [excess.path, 0, '', False, details, human_size, status, text_color, True])
        row_path = treestore.get_path(row_iter)
        excess.row_reference = gtk.TreeRowReference(treestore, row_path)
        if excess.size != None:
            self.queue_size += excess.size
            self.gui_status_set('Excess: %s' % human.size(self.queue_size))
    def gui_excess_remove(self, excess):
        treestore = self.excess_treestore
        row_path = excess.row_reference.get_path()
        if (row_path):
            row_iter = treestore.get_iter(row_path)
            treestore.remove(row_iter)
            if excess.size != None:
                self.queue_size -= excess.size
                self.gui_status_set('Excess: %s' % human.size(self.queue_size))
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
        gobject.idle_add(self.gui_status_set, status)
    def gui_status_set(self, status):
        self.status_label.set_text(status)
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
            try:
                dependency = self.dependencies[dependency.path]
            except KeyError:
                print 'Dependency was never added: ', dependency.path
            dependency.parent_remove(stack)
            if len(dependency.parents) == 0:
                self.remove_dependency(dependency)
        treestore = self.stacks_treestore
        row_path = stack.row_reference.get_path()
        row_iter = treestore.get_iter(row_path)
        del self.stacks[stack.path]
        treestore.remove(row_iter)
    def gui_on_selected_folders(self, widget, action):
        treeview = self.folders_treeview
        selection = treeview.get_selection()
        (model, row_paths) = selection.get_selected_rows()
        folder_list = []
        for row_path in row_paths:
            row_iter = model.get_iter(row_path)
            folder_list.append(model[row_path][0])
        for folder_path in folder_list:
            if action == 'remove':
                self.gui_folder_remove(folder_path)
    def gui_folder_remove(self, folder):
        if type(folder) != Stack:
            folder = self.folders[folder]
        print 'Remove folder: ',folder.path
        for file_path in reversed(self.files):
            if (file_path.startswith(folder.path)):
                self.remove_file(file_path)
        treestore = self.folders_treestore
        row_path = folder.row_reference.get_path()
        row_iter = treestore.get_iter(row_path)
        del self.folders[folder.path]
        treestore.remove(row_iter)
    def calculate_queue_size(self):
        return
        # gobject.idle_add(self.status_label.set_property, 'visible', False)
        # gobject.idle_add(self.spinner_queue.set_property, 'visible', True)
        # total = 0
        # for dependency_path, dependency in self.dependencies.iteritems():
        #     if dependency.size == None:
        #         continue
        #     elif dependency.ignore == True:
        #         continue
        #     else:
        #         total += dependency.size
        # for dependency_type in self.dependency_types:
        #     gobject.idle_add(self.gui_dependency_summary_update, dependency_type)
        # self.queue_size = total
        # gobject.idle_add(self.spinner_queue.set_property, 'visible', False)
        # gobject.idle_add(self.status_label.set_text, '%s in queue' % human.size(self.queue_size))
        # gobject.idle_add(self.status_label.set_property, 'visible', True)

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