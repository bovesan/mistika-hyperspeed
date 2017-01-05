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


gobject.threads_init()

class MainThread(threading.Thread):
    def __init__(self):
        super(MainThread, self).__init__()
        self.threads = []
        self.buffer = {}
        self.connection = {}
        self.is_mac = False
        self.is_mamba = False
        self.buffer_local = []
        self.buffer_remote = []

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


        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(self.hostsTree)
        #vbox.pack_start(scrolled_window)
        vbox.pack_start(scrolled_window)

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
        self.button_host_connect.connect("clicked", self.do_host_connect)
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
        column.set_visible(False)
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
        #vbox.pack_start(scrolled_window)
        vbox.pack_start(scrolled_window)


        hbox = gtk.HBox(False, 0)

        self.button_sync_files = gtk.Button('Sync selected files')
        #self.button_sync_files.set_image(gtk.image_new_from_stock(gtk.STOCK_REFRESH,  gtk.ICON_SIZE_BUTTON))
        self.button_sync_files.connect("clicked", self.do_sync_selected)
        hbox.pack_start(self.button_sync_files, False, False, 0)

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

    def run(self):
        self.io_hosts_populate(self.hostsTreeStore)
        treeselection = self.projectsTree.get_selection()
        treeselection.set_mode(gtk.SELECTION_MULTIPLE)
        #self.do_list_projects_local()

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
        selection = self.hostsTree.get_selection()
        (model, iter) = selection.get_selected()
        t = threading.Thread(target=self.io_list_projects, args=[file_path])
        self.threads.append(t)
        t.setDaemon(True)
        t.start()

    def on_host_edit(self, cell, path, new_text, user_data):
        tree, column = user_data
        print tree[path][column],
        gobject.idle_add(self.gui_set_value, tree, path, column, new_text)
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

    def do_list_projects_local(self, *widget):
        t = threading.Thread(target=self.io_list_projects_local)
        self.threads.append(t)
        t.setDaemon(True)
        t.start()

    def do_host_connect(self, *widget):
        t = threading.Thread(target=self.io_host_connect)
        self.threads.append(t)
        t.setDaemon(True)
        t.start()

    def do_list_projects_remote(self, widget):
        self.do_clear_remote()
        selection = self.hostsTree.get_selection()
        (model, iter) = selection.get_selected()
        print model[iter][0]
        t = threading.Thread(target=self.io_hosts_store)
        self.threads.append(t)
        t.setDaemon(True)
        t.start()
        t = threading.Thread(target=self.io_list_projects_remote, args=[model[iter][0], model[iter][1], model[iter][2], model[iter][3], model[iter][4]])
        self.threads.append(t)
        t.setDaemon(True)
        t.start()

    def do_sync_selected(self, widget):
        selection = self.projectsTree.get_selection()
        (model, pathlist) = selection.get_selected_rows()
        for path in pathlist:
            print repr(path)
            path_str = self.projectsTreeStore[path][1]
            print path_str
            #self.projectsTreeStore[path][3] = gtk.gdk.PixbufAnimation('../res/img/spinner01.gif')
            if path_str.endswith('/PRIVATE'):
                continue
            gobject.idle_add(self.gui_set_value, self.projectsTreeStore, path, 6, 'Queued')
            gobject.idle_add(self.gui_set_value, self.projectsTreeStore, path, 7, True)
            #gobject.idle_add(self.gui_show_error, repr(self.buffer[self.projectsTreeStore[path][1]]))
            gobject.idle_add(self.gui_show_error, path_str+'\n'+cgi.escape(pprint.pformat(self.buffer[path_str])))
            #self.projectsTreeStore[path][6] = 'Queued'
            #self.projectsTreeStore[path][5] += 1
            #self.projectsTreeStore[path][7] = True # Visibility

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

    def gui_refresh_path(self, path):
        print 'Refreshing ' + path
        tree = self.projectsTreeStore
        if '/' in path:
            parent_dir, basename = path.rsplit('/', 1) # parent_dir will not have trailing slash
            parent = tree.get_iter(self.buffer[parent_dir]['row_reference'].get_path())
            #print 'Parent: %s %s' % (parent_dir, parent)
        else:
            parent_dir = None
            basename = path
            parent = None
        markup = basename
        if 'row_reference' in self.buffer[path]:
            row_iter = tree.get_iter(self.buffer[path]['row_reference'].get_path())
        else:
            local = None
            direction = None
            remote = None
            markup = basename
            progress = 0
            progress_str = ''
            progress_visibility = False
            row_iter = tree.append(parent, [basename, path, local, direction, remote, progress, progress_str, progress_visibility, str(self.connection['address'])])
            self.buffer[path]['row_reference'] = gtk.TreeRowReference(tree, tree.get_path(row_iter))
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
            tree.set_value(row_iter, 6, 'Use media sync to process this folder')
            tree.set_value(row_iter, 7, True)
        tree.set_value(row_iter, 0, markup)
        tree.set_value(row_iter, 2, local)
        tree.set_value(row_iter, 3, direction)
        tree.set_value(row_iter, 4, remote)

    def gui_set_value(self, model, path, col, value):
        #print repr(item)
        #print repr(value)
        #item = value
        model[path][col] = value

    def gui_show_error(self, message):
        dialog = gtk.MessageDialog(parent=self.window, 
                            flags=gtk.DIALOG_MODAL, 
                            type=gtk.MESSAGE_ERROR, 
                            buttons=gtk.BUTTONS_NONE, 
                            message_format=None)
        dialog.set_markup(message)
        dialog.run()

    def fix_mac_printf(self, str):
        return str.replace('-printf',  '-print0 | xargs -0 stat -f').replace('%T@', '%c').replace('%s', '%z').replace('%y', '%T').replace('%p', '%N').replace('\\\\n', '')

    def io_list_projects_local(self, find_cmd):
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
                cmd = self.fix_mac_printf(cmd)
            print repr(cmd)
            try:
                p1 = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                output, stderr = p1.communicate()
                if p1.returncode > 0:
                    loader.set_from_stock(gtk.STOCK_APPLY, gtk.ICON_SIZE_BUTTON)
                    gobject.idle_add(self.gui_show_error, stderr)
                    return
                self.buffer_local = output.splitlines()
            except:
                print stderr
                raise
                gobject.idle_add(self.gui_show_error, stderr)
                return
        except:
            raise
        gobject.idle_add(loader.set_from_stock, gtk.STOCK_APPLY, gtk.ICON_SIZE_BUTTON)

    def io_list_projects_remote(self, find_cmd):
        loader = gtk.image_new_from_animation(gtk.gdk.PixbufAnimation('../res/img/spinner01.gif'))
        gobject.idle_add(self.button_load_remote_projects.set_image, loader)
        cmd = ['ssh', '-oBatchMode=yes', '-p', str(self.connection['port']), '%s@%s' % (self.connection['user'], self.connection['address']), find_cmd.replace('<root>', self.connection['projects_path'])]
        print cmd
        try:
            p1 = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, stderr = p1.communicate()
            if p1.returncode > 0:
                loader.set_from_stock(gtk.STOCK_APPLY, gtk.ICON_SIZE_BUTTON)
                gobject.idle_add(self.gui_show_error, stderr)
                return
            self.buffer_remote = output.splitlines()
        except:
            print stderr
            raise
            gobject.idle_add(self.gui_show_error, stderr)
            return
        #self.project_cell.set_property('foreground', '#000000')
        #self.project_cell.set_property('style', 'normal')
        gobject.idle_add(loader.set_from_stock, gtk.STOCK_APPLY, gtk.ICON_SIZE_BUTTON)

    def buffer_add(self, lines, host, root):
        for file_line in lines:
            f_inode, f_type, f_size, f_time, full_path = file_line.strip().split(' ', 4)
            f_time = int(f_time.split('.')[0])
            if f_type == '/': # Host is Mac
                f_type = 'd'
            if f_type == 'd':
                f_size = 0
            else:
                f_size = int(f_size)
            f_basename = full_path.strip('/').split('/')[-1]
            path = full_path.replace(root, '').strip('/')
            if path == '': # Skip root item
                continue
            print 'Buffer add: %s "%s" %s %s' % (host, path, f_type, f_time)
            if not path in self.buffer:
                self.buffer[path] = {}
                self.buffer[path]['mtime_remote'] = -1
                self.buffer[path]['mtime_local'] = -1
                self.buffer[path]['size_remote'] = -1
                self.buffer[path]['size_local'] = -1
                self.buffer[path]['type_remote'] = ''
                self.buffer[path]['type_local'] = ''
            if host == 'localhost':
                self.buffer[path]['type_local'] = f_type
                self.buffer[path]['size_local'] = f_size
                self.buffer[path]['mtime_local'] = f_time
            else:
                self.buffer[path]['type_remote'] = f_type
                self.buffer[path]['size_remote'] = f_size
                self.buffer[path]['mtime_remote'] = f_time
                self.buffer[path]['host'] = host

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
        self.io_list_projects()

    def io_list_projects(self, path=''):
        type_filter = ''
        if path == '':
            type_filter = ' -type d'
        root = '<root>'
        find_cmd = 'find %s/%s -name PRIVATE -prune -o -maxdepth 2 %s -printf "%%i %%y %%s %%T@ %%p\\\\n"' % (root, path, type_filter)
        print find_cmd
        thread_remote = threading.Thread(target=self.io_list_projects_remote, args=[find_cmd])
        self.threads.append(thread_remote)
        thread_remote.setDaemon(True)
        thread_remote.start()

        thread_local = threading.Thread(target=self.io_list_projects_local, args=[find_cmd])
        self.threads.append(thread_local)
        thread_local.setDaemon(True)
        thread_local.start()

        thread_local.join()
        thread_remote.join()
        self.buffer_add(self.buffer_local, 'localhost', self.projects_path_local)
        self.buffer_add(self.buffer_remote, self.connection['alias'], self.connection['projects_path'])
        for f_path in sorted(self.buffer):
            if f_path.startswith(path):
                gobject.idle_add(self.gui_refresh_path, f_path)

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