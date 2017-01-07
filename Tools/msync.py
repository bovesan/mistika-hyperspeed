#!/usr/bin/env python
#-*- coding:utf-8 -*-

import cgi
import json
import glob
import gobject
import gtk
import os
import platform
import pprint
import subprocess
import threading
import time
import sys

MISTIKA_EXTENSIONS = ['env', 'grp', 'rnd', 'fx']

gobject.threads_init()

class MainThread(threading.Thread):
    def __init__(self):
        super(MainThread, self).__init__()
        self.threads = []
        self.buffer = {}
        self.buffer_lock = threading.Lock()
        self.buffer_local = []
        self.buffer_local = []
        self.connection = {}
        self.is_mac = False
        self.is_mamba = False
        self.transfer_queue = {}
        self.cfgdir = os.path.expanduser('~/.mistika-hyperspeed/sync/')

        self.window = gtk.Window()
        window = self.window
        screen = self.window.get_screen()
        window.set_title("Mistika sync")
        window.set_size_request(screen.get_height()-200, screen.get_height()-200)
        window.set_border_width(20)
        window.set_position(gtk.WIN_POS_CENTER)
        if 'darwin' in platform.system().lower():
            self.is_mac = True
            self.window.set_resizable(False) # Because resizing crashes the app on Mac

        vbox = gtk.VBox(False, 10)

        self.status_bar = gtk.Statusbar()     
        vbox.pack_end(self.status_bar, False, False, 0)
        self.status_bar.show()
        self.context_id = self.status_bar.get_context_id("Statusbar example")

        hbox = gtk.HBox(False, 10)
        hbox.pack_start(gtk.Label('Remote host:'), False, False, 0)
        vbox.pack_start(hbox, False, False, 0)

        self.hostsTreeStore = gtk.TreeStore(str, str, str, int, str) # Name, url, color, underline
        self.hostsTree = gtk.TreeView()
        cell = gtk.CellRendererText()
        cell.set_property("editable", True)
        cell.connect('edited', self.on_host_edit, (self.hostsTreeStore, 0))
        column = gtk.TreeViewColumn('', cell, text=0)
        column.set_resizable(True)
        column.set_expand(True)
        self.hostsTree.append_column(column)
        cell = gtk.CellRendererText()
        cell.set_property("foreground", "gray")
        cell.set_property("editable", True)
        cell.connect('edited', self.on_host_edit, (self.hostsTreeStore, 1))
        column = gtk.TreeViewColumn('Host', cell, text=1)
        column.set_resizable(True)
        column.set_expand(True)
        self.hostsTree.append_column(column)
        cell = gtk.CellRendererText()
        cell.set_property("foreground", "gray")
        cell.set_property("editable", True)
        cell.connect('edited', self.on_host_edit, (self.hostsTreeStore, 2))
        column = gtk.TreeViewColumn('Username', cell, text=2)
        column.set_resizable(True)
        column.set_expand(True)
        self.hostsTree.append_column(column)
        cell = gtk.CellRendererText()
        cell.set_property("foreground", "gray")
        cell.set_property("editable", True)
        cell.connect('edited', self.on_host_edit, (self.hostsTreeStore, 3))
        column = gtk.TreeViewColumn('Port', cell, text=3)
        column.set_resizable(True)
        column.set_expand(True)
        self.hostsTree.append_column(column)
        cell = gtk.CellRendererText()
        cell.set_property("foreground", "gray")
        cell.set_property("editable", True)
        cell.connect('edited', self.on_host_edit, (self.hostsTreeStore, 4))
        column = gtk.TreeViewColumn('Projects path', cell, text=4)
        column.set_resizable(True)
        column.set_expand(True)
        self.hostsTree.append_column(column)
        hostsTreeStore = self.hostsTreeStore
        #hostsTreeStore.append(None, ["Horten", 'horten.hocusfocus.no', 'mistika', 22, '/Volumes/SLOW_HF/PROJECTS/'])
        #hostsTreeStore.append(None, ["Oslo", 's.hocusfocus.no', 'mistika', 22, '/Volumes/SLOW_HF/PROJECTS/'])
        linksFilter = hostsTreeStore.filter_new();
        self.hostsTree.set_model(hostsTreeStore)
        self.hostsTree.expand_all()

        self.hostsTree.set_size_request(100,150)
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(self.hostsTree)
        vbox.pack_start(scrolled_window, False, False, 0)

        hbox = gtk.HBox(False, 0)
        button = gtk.Button('+')
        button.set_size_request(30, 30)
        button.connect("clicked", self.gui_host_add)
        hbox.pack_end(button, False, False, 0)
        button = gtk.Button('-')
        button.set_size_request(30, 30)
        button.connect("clicked", self.gui_host_remove)
        hbox.pack_end(button, False, False, 0)


        self.button_host_connect = gtk.Button('Connect to host')
        self.button_host_connect.set_image(gtk.image_new_from_stock(gtk.STOCK_REFRESH,  gtk.ICON_SIZE_BUTTON))
        self.button_host_connect.connect("clicked", self.on_host_connect)
        hbox.pack_start(self.button_host_connect, False, False, 0)

        self.label_active_host = gtk.Label('')
        hbox.pack_start(self.label_active_host, False, False, 10)

        self.button_load_local_projects = gtk.Button('Local list')
        self.button_load_local_projects.set_image(gtk.image_new_from_stock(gtk.STOCK_REFRESH,  gtk.ICON_SIZE_BUTTON))
        #button.connect("clicked", self.do_list_projects_local)
        hbox.pack_start(self.button_load_local_projects, False, False, 0)

        self.button_load_remote_projects = gtk.Button('Remote list')
        self.button_load_remote_projects.set_image(gtk.image_new_from_stock(gtk.STOCK_REFRESH,  gtk.ICON_SIZE_BUTTON))
        #self.button_load_remote_projects.connect("clicked", self.do_list_projects_remote)
        hbox.pack_start(self.button_load_remote_projects, False, False, 0)

        vbox.pack_start(hbox, False, False, 0)

        self.projectsTreeStore = gtk.TreeStore(str, str, str, str, str, int, str, bool, str) # Basenae, Path, Local, Direction, Remote, Host, Progress int, Progress text, Progress visibility
        self.projectsTree = gtk.TreeView()
        #self.project_cell = gtk.CellRendererText()
        #project_cell = self.project_cell
        #project_cell.set_property('foreground', '#cccccc')
        #project_cell.set_property('style', 'italic')
        #cell.connect('edited', self.on_host_edit, (self.projectsTreeStore, 0))
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn('', cell, markup=0)
        column.set_resizable(True)
        column.set_expand(True)
        column.set_sort_column_id(0)
        self.projectsTree.append_column(column)

        column = gtk.TreeViewColumn('Path', gtk.CellRendererText(), text=1)
        column.set_resizable(True)
        column.set_expand(True)
        #column.set_visible(False)
        self.projectsTree.append_column(column)

        column = gtk.TreeViewColumn('Local', gtk.CellRendererPixbuf(), stock_id=2)
        column.set_resizable(True)
        column.set_expand(False)
        self.projectsTree.append_column(column)

        column = gtk.TreeViewColumn('Action', gtk.CellRendererPixbuf(), stock_id=3)
        column.set_resizable(True)
        column.set_expand(False)
        self.projectsTree.append_column(column)

        column = gtk.TreeViewColumn('Remote', gtk.CellRendererPixbuf(), stock_id=4)
        column.set_resizable(True)
        column.set_expand(False)
        self.projectsTree.append_column(column)

        column = gtk.TreeViewColumn('Status', gtk.CellRendererProgress(), pulse=5, text=6, visible=7)
        column.set_resizable(True)
        column.set_expand(True)
        self.projectsTree.append_column(column)

        projectsTreeStore = self.projectsTreeStore
        #hostsTreeStore.append(None, ["Horten", 'horten.hocusfocus.no', 'mistika', 22, '/Volumes/SLOW_HF/PROJECTS/'])
        #hostsTreeStore.append(None, ["Oslo", 's.hocusfocus.no', 'mistika', 22, '/Volumes/SLOW_HF/PROJECTS/'])
        #self.io_hosts_populate(projectsTreeStore)
        #projectsTreeStore.append(None, ['Loading projects ...'])
        self.projectsTree.set_model(projectsTreeStore)
        self.projectsTree.set_search_column(0)
        self.projectsTree.connect("row-expanded", self.on_expand)

        self.projectsTreeStore.set_sort_column_id(0, gtk.SORT_ASCENDING)
        #self.projectsTree.expand_all()

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(self.projectsTree)
        vbox.pack_start(scrolled_window)

        hbox = gtk.HBox(False, 0)

        self.button_sync_files = gtk.Button('Sync selected files')
        #self.button_sync_files.set_image(gtk.image_new_from_stock(gtk.STOCK_REFRESH,  gtk.ICON_SIZE_BUTTON))
        self.button_sync_files.connect("clicked", self.on_sync_selected)
        hbox.pack_start(self.button_sync_files, False, False, 0)

        button = gtk.Button('Unqueue selected files')
        #self.button_sync_files.set_image(gtk.image_new_from_stock(gtk.STOCK_REFRESH,  gtk.ICON_SIZE_BUTTON))
        button.connect("clicked", self.on_sync_selected_abort)
        hbox.pack_start(button, False, False, 0)

        button = gtk.Button('Sync associated files')
        #self.button_sync_files.set_image(gtk.image_new_from_stock(gtk.STOCK_REFRESH,  gtk.ICON_SIZE_BUTTON))
        button.connect("clicked", self.on_sync_associated)
        hbox.pack_start(button, False, False, 0)

        vbox.pack_start(hbox, False, False, 0)

        #menu = ['Sync project', 'Sync media']
        footer = gtk.HBox(False, 10)
        quitButton = gtk.Button('Quit')
        quitButton.set_size_request(70, 30)
        quitButton.connect("clicked", self.on_quit)
        footer.pack_end(quitButton, False, False)

        vbox.pack_end(footer, False, False, 10)

        window.add(vbox)
        window.show_all()
        window.connect("destroy", self.on_quit)
        self.window.connect("key-press-event",self.on_key_press_event)
        self.quit = False
        self.do_queue_process()

    def run(self):
        self.io_hosts_populate(self.hostsTreeStore)
        treeselection = self.projectsTree.get_selection()
        treeselection.set_mode(gtk.SELECTION_MULTIPLE)
        #self.do_list_projects_local()

    def aux_fix_mac_printf(self, str):
        return str.replace('-printf',  '-print0 | xargs -0 stat -f').replace('%T@', '%c').replace('%s', '%z').replace('%y', '%T').replace('%p', '%N').replace('\\\\n', '')

    def aux_mistika_object_path(self, level_names):
        #print repr(level_names)
        return '/'.join(level_names)

    def on_quit(self, widget):
        print 'Closed by: ' + repr(widget)
        for thread in self.threads:
            pass
        gtk.main_quit()

    #on_<object name>_<signal name>(<signal parameters>);.
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

    def on_expand(self, treeview, iter, path, *user_params):
        # print 'Expanding'
        # print repr(model)
        # print repr(iter)
        # print repr(path)
        file_path = self.projectsTreeStore[iter][1]
        if file_path.rsplit('.', 1)[-1] in MISTIKA_EXTENSIONS: # Should already be loaded
            return
        selection = self.hostsTree.get_selection()
        (model, iter) = selection.get_selected()
        t = threading.Thread(target=self.io_list_files, args=[[file_path]])
        self.threads.append(t)
        t.setDaemon(True)
        t.start()

    def on_host_edit(self, cell, path, new_text, user_data):
        tree, column = user_data
        print tree[path][column],
        row_reference = gtk.TreeRowReference(tree, path)
        gobject.idle_add(self.gui_set_value, tree, row_reference, column, new_text)
        #tree[path][column] = new_text
        print '-> ' + tree[path][column]
        t = threading.Thread(target=self.io_hosts_store)
        self.threads.append(t)
        t.setDaemon(True)
        t.start()

    def on_host_select(self, widget):
        print model[iter][0]
        t = threading.Thread(target=self.io_hosts_store)
        self.threads.append(t)
        t.setDaemon(True)
        t.start()

    def on_host_connect(self, widget):
        t = threading.Thread(target=self.io_host_connect)
        self.threads.append(t)
        t.setDaemon(True)
        t.start()

    def do_clear_remote(self):
        for path in self.buffer.keys():
            row_path = self.buffer[path]['row_reference'].get_path()
            if row_path == None:
                print path
                continue
            row_iter = self.projectsTreeStore.get_iter(self.buffer[path]['row_reference'].get_path())
            if self.buffer[path]['mtime_local'] < 0:
                self.projectsTreeStore.remove(row_iter)
                del self.buffer[path]
            elif self.buffer[path]['mtime_remote'] >= 0:
                self.buffer[path]['mtime_remote'] = -1
                self.buffer[path]['size_remote'] = -1
                self.buffer[path]['fingerprint_remote'] = ''
                gobject.idle_add(self.gui_refresh_path, path)

    def do_queue_process(self):
        self.queue_process = True
        t = threading.Thread(target=self.io_queue_process)
        self.threads.append(t)
        t.setDaemon(True)
        t.start()

    def on_sync_associated(self, widget):
        selection = self.projectsTree.get_selection()
        (model, pathlist) = selection.get_selected_rows()
        for path in pathlist:
            path_str = model[path][1]
            if path_str.lower().rsplit('.', 1)[-1] in MISTIKA_EXTENSIONS:
                t = threading.Thread(target=self.io_get_associated, args=[os.path.join(self.projects_path_local, path_str)])
                self.threads.append(t)
                t.setDaemon(True)
                t.start()

    def io_get_associated(self, path_str):
        files_chunk_max_size = 10
        files_chunk = []
        try:
            #level = -1
            level_names = []
            #level_val = []
            char_buffer = ''
            char_buffer_store = ''
            for line in open(path_str):
                for char in line:
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
                        object_path = self.aux_mistika_object_path(level_names)
                        if object_path.endswith('C/F'): # Clip source link
                            print 'C/F: ' + char_buffer
                            f_path = char_buffer
                        elif object_path.endswith('C/d/I/H/p'): # Clip media folder
                            CdIHp = char_buffer
                        elif object_path.endswith('C/d/I/s'): # Clip start frame
                            CdIs = int(char_buffer)
                        elif object_path.endswith('C/d/I/e'): # Clip end frame
                            CdIe = int(char_buffer)
                        elif object_path.endswith('C/d/I/H/n'): # Clip media name
                            f_path = CdIHp + char_buffer
                            print 'C/d/I/H: ' + f_path
                        elif object_path.endswith('F/D'): # .dat file relative path (from projects_path)
                            print 'F/D: ' + char_buffer
                            f_path = char_buffer
                        if f_path:
                            if '%' in f_path:
                                for i in range(CdIs, CdIe+1):
                                    files_chunk.append(f_path.replace(self.projects_path_local+'/', '') % i)
                            else:
                                files_chunk.append(f_path.replace(self.projects_path_local+'/', ''))
                            if len(files_chunk) >= files_chunk_max_size:
                                self.aux_list_files(file_path_list=files_chunk, parent_file_path=path_str, sync=True)
                                files_chunk = []
                                #self.io_list_files(files_chunk, path_str.replace(self.projects_path_local+'/', ''), sync=True)
                                #self.do_sync_item(files_chunk, False, path_str.replace(self.projects_path_local+'/', ''))
                        # if len(level_val) < level+1:
                        #     level_val.append(char_buffer)
                        # else:
                        #     level_val[level] = char_buffer
                        char_buffer = ''
                        del level_names[-1]
                        #level -= 1
                    elif len(level_names) > 0 and level_names[-1] == 'Shape':
                        continue
                    elif char:
                        char_buffer += char
            if len(files_chunk) > 0:
                self.aux_list_files(file_path_list=files_chunk, parent_file_path=path_str, sync=True)
                files_chunk = []
        except IOError as e:
            print 'Could not open ' + path_str
            raise e

    def aux_list_files(self, file_path_list, parent_file_path, sync=False):
        if parent_file_path.startswith(self.projects_path_local):
            parent_file_path = parent_file_path.replace(self.projects_path_local+'/', '')

        t = threading.Thread(target=self.io_list_files, kwargs={
            'paths' : list(file_path_list), # Creates a copy
            'parent_path' : parent_file_path.replace(self.projects_path_local+'/', ''),
            'sync' : True
            })
        self.threads.append(t)
        t.setDaemon(True)
        t.start()

    def on_sync_selected(self, widget):
        selection = self.projectsTree.get_selection()
        (model, pathlist) = selection.get_selected_rows()
        for path in pathlist:
            print repr(path)
            path_str = model[path][1]
            print path_str
            # row_reference = gtk.TreeRowReference(model, path)
            # child_iter = model.iter_children(model.get_iter(path))
            # while child_iter != None:
            #     path_child = model.get_path(child_iter)
            #     path_str_child = model[path_child][1]
            #     row_reference_child = gtk.TreeRowReference(model, path_child)
            #     #self.do_sync_item([path_str_child], row_reference_child, path)
            #     self.gui_refresh_path(path=path_str_child, sync=True)
            #     child_iter = model.iter_next(child_iter)
            self.do_sync_item([path_str], relist=True)
            #self.projectsTreeStore[path][3] = gtk.gdk.PixbufAnimation('../res/img/spinner01.gif')
            #gobject.idle_add(self.gui_show_error, repr(self.buffer[self.projectsTreeStore[path][1]]))
            #gobject.idle_add(self.gui_show_error, path_str+'\n'+cgi.escape(pprint.pformat(self.buffer[path_str])))

    def do_sync_item(self, paths, parent_path=False, relist=False):
        model = self.projectsTreeStore
        for path_str in paths:
            if path_str in self.transfer_queue:
                paths.remove(path_str)
        if parent_path and len(paths) > 0:
            self.io_list_files(paths, parent_path, sync=True, maxdepth=False)
        elif relist:
            self.io_list_files(paths, False, sync=True, maxdepth=False)
        for path_str in paths:
            #print 'do_sync_item: ' + path_str
            transfer_item = {}
            transfer_item['path'] = path_str
            for row_reference in self.buffer[path_str]['row_references']:
                child_iter = model.iter_children(model.get_iter(row_reference.get_path()))
                while child_iter != None:
                    path_child = model.get_path(child_iter)
                    path_str_child = model[path_child][1]
                    #self.do_sync_item([path_str_child])
                    child_iter = model.iter_next(child_iter)
                gobject.idle_add(self.gui_set_value, model, row_reference, 6, 'Queued')
                gobject.idle_add(self.gui_set_value, model, row_reference, 7, True)
            self.transfer_queue[path_str] = transfer_item
        #self.projectsTreeStore[path][6] = 'Queued'
        #self.projectsTreeStore[path][5] += 1
        #self.projectsTreeStore[path][7] = True # Visibility

    def on_sync_selected_abort(self, widget):
        selection = self.projectsTree.get_selection()
        (model, pathlist) = selection.get_selected_rows()
        for path in pathlist:
            path_str = model[path][1]
            self.transfer_remove(path_str)

    def transfer_remove(self, path_str):
        model = self.projectsTreeStore
        for i, transfer_item in enumerate(self.transfer_queue): # Race?
            if transfer_item['path'] == path_str:
                del self.transfer_queue[i]
        for row_reference in self.buffer[path_str]['row_references']:
            gobject.idle_add(self.gui_set_value, model, row_reference, 7, False)
            child_iter = model.iter_children(model.get_iter(row_reference.get_path()))
            while child_iter != None:
                path_child = model.get_path(child_iter)
                path_str_child = model[path_child][1]
                self.transfer_remove(path_str_child)
                child_iter = model.iter_next(child_iter)
        print 'Removed ' + path_str

    def gui_host_add(self, widget, alias='New host', address='', user='mistika', port=22, path='', selected=False):
        row_iter = self.hostsTreeStore.append(None, [alias, address, user, port, path])
        if selected:
            selection = self.hostsTree.get_selection()
            selection.select_iter(row_iter)
        # status = 'Loaded hosts.'
        # self.status_bar.push(self.context_id, status)

    def gui_host_remove(self, widget):
        selection = self.hostsTree.get_selection()
        (model, iter) = selection.get_selected()
        try:
            model.remove(iter)
            t = threading.Thread(target=self.io_hosts_store)
            self.threads.append(t)
            t.setDaemon(True)
            t.start()
        except:
            raise

        #self.hostsTreeStore.append(None, ['New host', '', 'mistika', 22, ''])

    def gui_append_path(self, host, path, children, time, size):
        print 'Appending ' + path
        is_dir = path.endswith('/')
        path = path.strip('/')
        if path == '':
            return
        if '/' in path:
            parent_dir, basename = path.rsplit('/', 1) # parent_dir will not have trailing slash
            parent = self.projectsTreeStore.get_iter(self.buffer[parent_dir]['row_reference'].get_path())
        else:
            parent_dir = None
            basename = path
            parent = None
        tree = self.projectsTreeStore
        #print 'Path: %s Parent dir: %s ' % (path, parent_dir)
        #print 'Parent: ' + repr(parent)
        local = None
        direction = None
        remote = None
        markup = basename
        progress = 0
        progress_str = ''
        progress_visibility = False
        if not path in self.buffer:
            self.buffer[path] = {}
            row_iter = self.projectsTreeStore.append(parent, [basename, path, local, direction, remote, progress, progress_str, progress_visibility, str(host)])
            self.buffer[path]['row_reference'] = gtk.TreeRowReference(self.projectsTreeStore, self.projectsTreeStore.get_path(row_iter))
            self.buffer[path]['fingerprint_remote'] = ''
            self.buffer[path]['fingerprint_local'] = ''
            self.buffer[path]['mtime_remote'] = -1
            self.buffer[path]['mtime_local'] = -1
            self.buffer[path]['size_remote'] = -1
            self.buffer[path]['size_local'] = -1
        if host:
            self.buffer[path]['size_remote'] = size
            self.buffer[path]['mtime_remote'] = time
        else:
            self.buffer[path]['size_local'] = size
            self.buffer[path]['mtime_local'] = time
        self.gui_refresh_path(path)

    def gui_parent_modified(self, row_iter):
        #print 'Modified parent of: %s' % self.projectsTreeStore.get_value(row_iter, 1)
        try:
            parent = self.projectsTreeStore.iter_parent(row_iter)
            self.projectsTreeStore.set_value(parent, 2, None)
            self.projectsTreeStore.set_value(parent, 3, gtk.STOCK_REFRESH)
            self.projectsTreeStore.set_value(parent, 4, None)
            self.gui_parent_modified(parent)
        except: # Reached top level
            pass

    def gui_refresh_path(self, path, sync):
        #print 'Refreshing ' + path
        tree = self.projectsTreeStore
        if path.startswith('/'): # Absolute path, child of a MISTIKA_EXTENSIONS object
            basename = path
            parents = self.buffer[path]['parent_paths']
        elif '/' in path:
            parent_dir, basename = path.rsplit('/', 1) # parent_dir will not have trailing slash
            parents = self.buffer[path]['parent_paths']
            #print 'Parents: ' + repr(parents)
            #print 'Parent: %s %s' % (parent_dir, parent)
        else:
            parent_dir = None
            basename = path
            parents = [None]
        markup = basename
        if self.buffer[path]['row_references'] == []: # Will not append objects to parent objects later on
            local = None
            direction = None
            remote = None
            progress = 0
            progress_str = ''
            progress_visibility = False
        else:
            row_reference = self.buffer[path]['row_references'][0]
            markup = tree[row_reference.get_path()][0]
            local = tree[row_reference.get_path()][2]
            direction = tree[row_reference.get_path()][3]
            remote = tree[row_reference.get_path()][4]
            progress = tree[row_reference.get_path()][5]
            progress_str = tree[row_reference.get_path()][6]
            progress_visibility = tree[row_reference.get_path()][7]
        for parent in parents:
            if parent == None and len(self.buffer[path]['row_references']) > 0:
                continue
            append_to_this_parent = True
            #print 'Parent: ' + repr(parent)
            if parent != None:
                if not parent in self.buffer:
                    continue
                #print 'Parent: ' + repr(parent)
                parent = tree.get_iter(self.buffer[parent]['row_references'][0].get_path())
                for row_reference in self.buffer[path]['row_references']:
                    if tree.is_ancestor(parent, tree.get_iter(row_reference.get_path())):
                        append_to_this_parent = False
            if append_to_this_parent:
                row_iter = tree.append(parent, [basename, path, local, direction, remote, progress, progress_str, progress_visibility, str(self.connection['address'])])
                self.buffer[path]['row_references'].append(gtk.TreeRowReference(tree, tree.get_path(row_iter)))
        if self.buffer[path]['size_remote'] == self.buffer[path]['size_local']:
            markup = '<span foreground="#888888">%s</span>' % basename
            if self.buffer[path]['size_remote'] == 0:
                local = None
                direction = None
                remote = None
            else:
                local = gtk.STOCK_YES
                direction = None
                remote = gtk.STOCK_YES
        else:
            for row_reference in self.buffer[path]['row_references']:
                row_iter = tree.get_iter(row_reference.get_path())
                self.gui_parent_modified(row_iter) # More confusing than informative?
            if self.buffer[path]['mtime_remote'] > self.buffer[path]['mtime_local']:
                if self.buffer[path]['mtime_local'] < 0:
                    local = None
                else:
                    local = gtk.STOCK_NO
                direction = gtk.STOCK_GO_BACK
                remote = gtk.STOCK_YES
            else:
                local = gtk.STOCK_YES
                direction = gtk.STOCK_GO_FORWARD
                if self.buffer[path]['mtime_remote'] < 0:
                    remote = None
                else:
                    remote = gtk.STOCK_NO
                #gtk.STOCK_STOP
        if basename == 'PRIVATE':
            local = None
            direction = None
            remote = None
        self.buffer[path]['direction'] = direction
        for row_reference in self.buffer[path]['row_references']:
            row_iter = tree.get_iter(row_reference.get_path())
            tree.set_value(row_iter, 0, markup)
            tree.set_value(row_iter, 2, local)
            tree.set_value(row_iter, 3, direction)
            tree.set_value(row_iter, 4, remote)
        if sync:
            self.do_sync_item([path], False)

    def gui_set_value(self, model, row_reference, col, value):
        #print repr(item)
        #print repr(value)
        #item = value
        path = row_reference.get_path()
        model[path][col] = value

    def gui_show_error(self, message):
        dialog = gtk.MessageDialog(parent=self.window, 
                            #flags=gtk.DIALOG_MODAL, 
                            type=gtk.MESSAGE_ERROR, 
                            buttons=gtk.BUTTONS_NONE, 
                            message_format=None)
        dialog.set_markup(message)
        dialog.run()

    def io_list_files_local(self, find_cmd, parent_path=False):
        loader = gtk.image_new_from_animation(gtk.gdk.PixbufAnimation('../res/img/spinner01.gif'))
        gobject.idle_add(self.button_load_local_projects.set_image, loader)
        projects_path_file = os.path.expanduser('~/MISTIKA-ENV/MISTIKA_WORK')
        if not os.path.isfile(projects_path_file):
            projects_path_file = os.path.expanduser('~/MAMBA-ENV/MAMBA_WORK')
        if not os.path.isfile(projects_path_file):
            gobject.idle_add(self.gui_show_error, 'Cannot determine local projects path')
        try:
            for line in open(projects_path_file):
                if line.split()[0].endswith('_WORK'):
                    self.projects_path_local = line.split()[-1]
                    break
            cmd = find_cmd.replace('<root>', self.projects_path_local)
            if self.is_mac:
                cmd = self.aux_fix_mac_printf(cmd)
            print repr(cmd)
            try:
                p1 = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                output, stderr = p1.communicate()
                if False and p1.returncode > 0:
                    loader.set_from_stock(gtk.STOCK_APPLY, gtk.ICON_SIZE_BUTTON)
                    gobject.idle_add(self.gui_show_error, stderr)
                    return
                lines = output.splitlines()
                self.buffer_add(lines, 'localhost', self.projects_path_local, parent_path)
            except:
                print stderr
                raise
                gobject.idle_add(self.gui_show_error, stderr)
                return
        except:
            raise
        gobject.idle_add(loader.set_from_stock, gtk.STOCK_APPLY, gtk.ICON_SIZE_BUTTON)

    def io_list_files_remote(self, find_cmd, parent_path=False):
        loader = gtk.image_new_from_animation(gtk.gdk.PixbufAnimation('../res/img/spinner01.gif'))
        gobject.idle_add(self.button_load_remote_projects.set_image, loader)
        cmd = ['ssh', '-oBatchMode=yes', '-p', str(self.connection['port']), '%s@%s' % (self.connection['user'], self.connection['address']), find_cmd.replace('<root>', self.connection['projects_path'])]
        print cmd
        try:
            p1 = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, stderr = p1.communicate()
            if False and p1.returncode > 0:
                loader.set_from_stock(gtk.STOCK_APPLY, gtk.ICON_SIZE_BUTTON)
                gobject.idle_add(self.gui_show_error, stderr)
                return
            lines = output.splitlines()
            self.buffer_add(lines, self.connection['alias'], self.connection['projects_path'], parent_path)
        except:
            print stderr
            raise
            gobject.idle_add(self.gui_show_error, stderr)
            return
        #self.project_cell.set_property('foreground', '#000000')
        #self.project_cell.set_property('style', 'normal')
        gobject.idle_add(loader.set_from_stock, gtk.STOCK_APPLY, gtk.ICON_SIZE_BUTTON)

    def buffer_add(self, lines, host, root, parent_path=False):
        root = root.rstrip('/')
        if not root == '':
            root += '/'
        for file_line in lines:
            if parent_path:
                parent_paths = [parent_path]
            else:
                parent_paths = []
            f_inode, f_type, f_size, f_time, full_path = file_line.strip().split(' ', 4)
            f_time = int(f_time.split('.')[0])
            if f_type == '/': # Host is Mac
                f_type = 'd'
            if f_type == 'd':
                f_size = 0
            else:
                f_size = int(f_size)
            f_basename = full_path.strip('/').split('/')[-1]
            if full_path.startswith(root):
                path = full_path.replace(root, '').strip('/')
            else:
                path = full_path # Absolute path
            if '/' in path.strip('/'):
                parent_dir, basename = path.rsplit('/', 1) # parent_dir will not have trailing slash
                if not parent_dir in parent_paths:
                    #print 'Append ' + parent_dir
                    parent_paths.append(parent_dir)
            else:
                parent_dir = ''
                basename = path

            if path == '': # Skip root item
                continue
            self.buffer_lock.acquire()
            if not path in self.buffer:
                print 'Buffer add: %s "%s" %s %s' % (host, path, f_type, f_time)
                self.buffer[path] = {}
                self.buffer[path]['row_references'] = []
                self.buffer[path]['parent_paths'] = parent_paths
                self.buffer[path]['mtime_remote'] = -1
                self.buffer[path]['mtime_local'] = -1
                self.buffer[path]['size_remote'] = -1
                self.buffer[path]['size_local'] = -1
                self.buffer[path]['type_remote'] = ''
                self.buffer[path]['type_local'] = ''
            if parent_path and not parent_path in self.buffer[path]['parent_paths']:
                self.buffer[path]['parent_paths'].append(parent_path)
            self.buffer_lock.release()
            if host == 'localhost':
                self.buffer[path]['type_local'] = f_type
                self.buffer[path]['size_local'] = f_size
                self.buffer[path]['mtime_local'] = f_time
            else:
                self.buffer[path]['type_remote'] = f_type
                self.buffer[path]['size_remote'] = f_size
                self.buffer[path]['mtime_remote'] = f_time
                self.buffer[path]['host'] = host
            #self.buffer[path]['parent_row_references'] += parent_row_references

    def io_queue_process(self):
        while self.queue_process:
            file_lines = {}
            file_lines['local_to_remote_absolute'] = []
            file_lines['local_to_remote_relative'] = []
            file_lines['remote_to_local_absolute'] = []
            file_lines['remote_to_local_relative'] = []
            for path in self.transfer_queue.keys():
                print 'In queue:' + path
                direction = self.buffer[path]['direction']
                if direction == None:
                    del self.transfer_queue[path]
                #print direction
                line = path + '\n'
                if direction == gtk.STOCK_GO_FORWARD:
                    if path.endswith('/'):
                        # ssh mkdir -p path
                    if path.startswith('/'):
                        file_lines['local_to_remote_absolute'].append(line)
                    else:
                        file_lines['local_to_remote_relative'].append(line)

            for file_lines_list in file_lines:
                if len(file_lines[file_lines_list]) > 0:
                    files_list_path = self.cfgdir + file_lines_list + '.lst'
                    open(files_list_path, 'w').writelines(file_lines[file_lines_list])
                    if file_lines_list == 'local_to_remote_relative' > 0:
                        cmd = ['rsync',  '--progress', '-a', '-e', 'ssh', '--files-from=' + files_list_path, self.projects_path_local, '%s@%s:%s' % (self.connection['user'], self.connection['address'], self.connection['projects_path'])]
                        print repr(cmd)
                        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                        self.check_transfer(process)

                    if file_lines_list == 'local_to_remote_absolute' > 0:
                        cmd = ['rsync',  '--progress', '-a', '-e', 'ssh', '--files-from=' + files_list_path, '/', '%s@%s:/' % (self.connection['user'], self.connection['address'])]
                        print repr(cmd)
                        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                        self.check_transfer(process)

            time.sleep(10)

    def check_transfer(self, process):
        print 'Waiting for process to finish'
        process.poll()
        out_buffer = ''
        while process.returncode == None:
            c = process.stdout.read(1)
            out_buffer += c
            sys.stdout.write(c)
            sys.stdout.flush()
            if c == '\n':
                line = out_buffer
                out_buffer == ''
                for path in self.transfer_queue:
                    if path.endswith(line.replace('is uptodate\n', '').strip().rstrip('/')):
                        del self.transfer_queue[path]
                        for row_reference in self.buffer[path]['row_references']:
                            gobject.idle_add(self.gui_set_value, model, row_reference, 5, 100)
                            gobject.idle_add(self.gui_set_value, model, row_reference, 6, '100%')
                        print 'Transfer complete: ' + path
            process.poll()
        print 'Process has ended'
        lines = process.communicate()[0].splitlines()
        for line in lines:
            print line
            for path in self.transfer_queue:
                if line.replace('is uptodate\n', '').strip().rstrip('/') == path:
                    del self.transfer_queue[path]
                    for row_reference in self.buffer[path]['row_references']:
                        gobject.idle_add(self.gui_set_value, model, row_reference, 5, 100)
                        gobject.idle_add(self.gui_set_value, model, row_reference, 6, '100%')
                    print 'Transfer complete: ' + path

    def io_host_connect(self):
        loader = gtk.image_new_from_animation(gtk.gdk.PixbufAnimation('../res/img/spinner01.gif'))
        gobject.idle_add(self.button_host_connect.set_image, loader)
        selection = self.hostsTree.get_selection()
        (model, iter) = selection.get_selected()
        self.connection['alias'] = model[iter][0]
        self.connection['address'] = model[iter][1]
        self.connection['user'] = model[iter][2]
        self.connection['port'] = model[iter][3]
        self.connection['projects_path'] = model[iter][4]
        cmd = ['ssh', '-oBatchMode=yes', '-p', str(self.connection['port']), '%s@%s' % (self.connection['user'], self.connection['address']), 'exit']
        p1 = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, stderr = p1.communicate()
        if p1.returncode > 0:
            loader.set_from_stock(gtk.STOCK_APPLY, gtk.ICON_SIZE_BUTTON)
            gobject.idle_add(self.gui_show_error, stderr)
        else:
            gobject.idle_add(self.label_active_host.set_markup, '<span foreground="#888888">Connected to host:</span> %s <span foreground="#888888">(%s)</span>' % (self.connection['alias'], self.connection['address']))
        gobject.idle_add(loader.set_from_stock, gtk.STOCK_APPLY, gtk.ICON_SIZE_BUTTON)
        self.io_list_files()

    def io_list_files(self, paths=[''], parent_path=False, sync=False, maxdepth = 2):        
        type_filter = ''
        maxdepth_str = ''
        if paths == ['']:
            type_filter = ' -type d'

        search_paths = ''
        for path in paths:
            if path.startswith('/'):
                root = ''
            else:
                root = '<root>/'
            search_paths += ' "%s%s"' % (root, path)
        if maxdepth:
            maxdepth_str = ' -maxdepth %i' % maxdepth
        find_cmd = 'find %s -name PRIVATE -prune -o %s %s -printf "%%i %%y %%s %%T@ %%p\\\\n"' % (search_paths, maxdepth_str, type_filter)
        print find_cmd
        thread_remote = threading.Thread(target=self.io_list_files_remote, args=[find_cmd, parent_path])
        self.threads.append(thread_remote)
        thread_remote.setDaemon(True)
        thread_remote.start()

        thread_local = threading.Thread(target=self.io_list_files_local, args=[find_cmd, parent_path])
        self.threads.append(thread_local)
        thread_local.setDaemon(True)
        thread_local.start()

        thread_local.join()
        thread_remote.join()
        #self.buffer_add(self.buffer_local, 'localhost', self.projects_path_local)
        #self.buffer_add(self.buffer_remote, self.connection['alias'], self.connection['projects_path'], parent_path)
        for path in paths:
            for f_path in sorted(self.buffer):
                if f_path.startswith(path):
                    gobject.idle_add(self.gui_refresh_path, f_path, sync)

    def io_hosts_populate(self, tree):
        cfg_path = os.path.expanduser('~/.mistika-hyperspeed/sync/hosts.json')
        try:
            hosts = json.loads(open(cfg_path).read())
        except IOError as e:
            return
        #print repr(hosts)
        for host in hosts:
            #row_iter = tree.append(None, [host, hosts[host]['address'], hosts[host]['user'], hosts[host]['port'], hosts[host]['path']])
            gobject.idle_add(self.gui_host_add, None, host, hosts[host]['address'], hosts[host]['user'], hosts[host]['port'], hosts[host]['path'], hosts[host]['selected'])

    def io_hosts_store(self):
        selection = self.hostsTree.get_selection()
        (model, row_iter) = selection.get_selected()
        selected_row = model[row_iter]
        cfg_path = os.path.expanduser('~/.mistika-hyperspeed/sync/hosts.json')
        hosts = {}
        # i = model.get_iter(0)
        # row = model[i]
        for row in self.hostsTreeStore:
            print repr(selected_row[0])
            print repr(row[0])
            selected = selected_row[0] == row[0]
            #selected = selection.iter_is_selected(model[row])
            alias = row[0]
            for value in row:
                print value,
            print ''
            hosts[alias] = {}
            hosts[alias]['address'] = row[1]
            hosts[alias]['user'] = row[2]
            hosts[alias]['port'] = row[3]
            hosts[alias]['path'] = row[4]
            hosts[alias]['selected'] = selected
        cfg_path_parent = os.path.dirname(cfg_path)
        if not os.path.isdir(cfg_path_parent):
            try:
                os.makedirs(cfg_path_parent)
            except IOError as e:
                gobject.idle_add(self.gui_show_error, 'Could not create config folder:\n'+cfg_path_parent)
                return
        try:
            open(cfg_path, 'w').write(json.dumps(hosts, sort_keys=True, indent=4, separators=(',', ': ')))
            status = 'Wrote to %s' % cfg_path
            print status
            gobject.idle_add(self.status_bar.push, self.context_id, status)
        except IOError as e:
            gobject.idle_add(self.gui_show_error, 'Could not write to file:\n'+cfg_path)
        except:
            raise




os.environ['LC_CTYPE'] = 'en_US.utf8'
t = MainThread()
t.start()
gtk.main()
t.quit = True