#!/usr/bin/env python
#-*- coding:utf-8 -*-

import json
import glob
import gobject
import gtk
import os
import platform
import subprocess
import threading
import time


gobject.threads_init()

class MyThread(threading.Thread):
    def __init__(self):
        super(MyThread, self).__init__()
        self.threads = []
        self.window = gtk.Window()
        window = self.window
        screen = self.window.get_screen()
        window.set_title("Mistika sync")
        window.set_size_request(screen.get_height()-200, screen.get_height()-200)
        window.set_border_width(20)
        window.set_position(gtk.WIN_POS_CENTER)
        if 'darwin' in platform.system().lower():
            self.window.set_resizable(False) # Because resizing crashes the app on Mac
        self.is_mamba = False

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
        button.connect("clicked", self.add_host)
        hbox.pack_end(button, False, False, 0)
        button = gtk.Button('-')
        button.set_size_request(30, 30)
        button.connect("clicked", self.remove_host)
        hbox.pack_end(button, False, False, 0)

        self.button_load_local_projects = gtk.Button('Load local projects')
        self.button_load_local_projects.set_image(gtk.image_new_from_stock(gtk.STOCK_REFRESH,  gtk.ICON_SIZE_BUTTON))
        button.connect("clicked", self.reload_local_projects)
        hbox.pack_start(self.button_load_local_projects, False, False, 0)

        self.button_load_remote_projects = gtk.Button('Load remote projects')
        self.button_load_remote_projects.set_image(gtk.image_new_from_stock(gtk.STOCK_REFRESH,  gtk.ICON_SIZE_BUTTON))
        self.button_load_remote_projects.connect("clicked", self.on_host_load)
        hbox.pack_start(self.button_load_remote_projects, False, False, 0)

        self.label_active_host = gtk.Label('')
        hbox.pack_start(self.label_active_host, False, False, 10)

        vbox.pack_start(hbox, False, False, 0)

        self.projectsTreeStore = gtk.TreeStore(str, str, str, str, str, int, str, bool) # Basenae, Path, Local, Direction, Remote, Progress int, Progress text, Progress visibility
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
        #self.hosts_populate(projectsTreeStore)
        #projectsTreeStore.append(None, ['Loading projects ...'])
        self.projectsTree.set_model(projectsTreeStore)
        self.projectsTree.set_search_column(0)
        self.projectsTree.connect("row-expanded", self.on_expand)

        self.projectsTreeStore.set_sort_column_id(0, gtk.SORT_ASCENDING)
        #self.projectsTree.expand_all()
        self.rows = {}

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(self.projectsTree)
        #vbox.pack_start(scrolled_window)
        vbox.pack_start(scrolled_window)


        hbox = gtk.HBox(False, 0)

        self.button_sync_files = gtk.Button('Sync selected files')
        #self.button_sync_files.set_image(gtk.image_new_from_stock(gtk.STOCK_REFRESH,  gtk.ICON_SIZE_BUTTON))
        self.button_sync_files.connect("clicked", self.on_sync_selected)
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
        self.window.connect("key-press-event",self._key_press_event)
        self.quit = False

    def run(self):
        self.hosts_populate(self.hostsTreeStore)
        treeselection = self.projectsTree.get_selection()
        treeselection.set_mode(gtk.SELECTION_MULTIPLE)
        self.reload_local_projects()
        pass

    def _key_press_event(self,widget,event):
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

    def on_sync_selected(self, widget):
        selection = self.projectsTree.get_selection()
        (model, pathlist) = selection.get_selected_rows()
        for path in pathlist:
            print repr(path)
            print repr(self.projectsTreeStore[path][1])
            #self.projectsTreeStore[path][3] = gtk.gdk.PixbufAnimation('../res/img/spinner01.gif')
            gobject.idle_add(self.gui_set_value, self.projectsTreeStore, path, 6, 'Queued')
            gobject.idle_add(self.gui_set_value, self.projectsTreeStore, path, 7, True)
            #self.projectsTreeStore[path][6] = 'Queued'
            #self.projectsTreeStore[path][5] += 1
            #self.projectsTreeStore[path][7] = True # Visibility

    def gui_set_value(self, model, path, col, value):
        #print repr(item)
        #print repr(value)
        #item = value
        model[path][col] = value

    def on_host_select(self, widget):
        print model[iter][0]
        t = threading.Thread(target=self.hosts_store)
        self.threads.append(t)
        t.setDaemon(True)
        t.start()

    def on_host_load(self, widget):
        selection = self.hostsTree.get_selection()
        (model, iter) = selection.get_selected()
        print model[iter][0]
        t = threading.Thread(target=self.hosts_store)
        self.threads.append(t)
        t.setDaemon(True)
        t.start()
        t = threading.Thread(target=self.list_projects_remote, args=[model[iter][0], model[iter][1], model[iter][2], model[iter][3], model[iter][4]])
        self.threads.append(t)
        t.setDaemon(True)
        t.start()

    def reload_local_projects(self, *widget):
        t = threading.Thread(target=self.list_projects_local)
        self.threads.append(t)
        t.setDaemon(True)
        t.start()

    def list_projects_local(self):
        loader = gtk.image_new_from_animation(gtk.gdk.PixbufAnimation('../res/img/spinner01.gif'))
        self.button_load_local_projects.set_image(loader)
        projects_path_file = os.path.expanduser('~/MISTIKA-ENV/MISTIKA_WORK')
        if not os.path.isfile(projects_path_file):
            projects_path_file = os.path.expanduser('~/MAMBA-ENV/MAMBA_WORK')
        if not os.path.isfile(projects_path_file):
            gobject.idle_add(self.error, 'Cannot determine local projects path')
        try:
            for line in open(projects_path_file):
                if line.split()[0].endswith('_WORK'):
                    projects_path = line.split()[-1]
                    break
            for root, dirs, files in os.walk(projects_path):
                root_rel = root.replace(projects_path, '')
                for name in dirs:
                    gobject.idle_add(self.append_project, False, root_rel+'/'+name+'/')
                for name in files:
                    if not root_rel == '':
                        gobject.idle_add(self.append_project, False, root_rel+'/'+name)
        except:
            raise
        loader.set_from_stock(gtk.STOCK_APPLY, gtk.ICON_SIZE_BUTTON)

    def append_project(self, is_remote, path, children=None):
        is_dir = path.endswith('/')
        path = path.strip('/')
        if path == '':
            return
        if '/' in path:
            parent_dir, basename = path.rsplit('/', 1) # parent_dir will not have trailing slash
            parent = self.rows[parent_dir]['iter']
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
        if not path in self.rows:
            self.rows[path] = {}
            self.rows[path]['iter'] = self.projectsTreeStore.append(parent, [basename, path, local, direction, remote, progress, progress_str, progress_visibility])
            self.rows[path]['fingerprint_remote'] = ''
            self.rows[path]['fingerprint_local'] = ''
            self.rows[path]['mtime_remote'] = 0
            self.rows[path]['mtime_local'] = 0
        if is_remote:
            self.rows[path]['fingerprint_remote'] = 'foo'
            self.rows[path]['mtime_remote'] = 1
        if not is_remote:
            self.rows[path]['fingerprint_local'] = 'foo'
            self.rows[path]['mtime_local'] = 1
        if self.rows[path]['fingerprint_remote'] == self.rows[path]['fingerprint_local']:
            markup = '<span foreground="#888888">%s</span>' % basename
            local = gtk.STOCK_YES
            direction = None
            remote = gtk.STOCK_YES
        else:
            if self.rows[path]['mtime_remote'] > self.rows[path]['mtime_local']:
                local = gtk.STOCK_NO
                direction = gtk.STOCK_GO_BACK
                remote = gtk.STOCK_YES
            else:
                local = gtk.STOCK_YES
                direction = gtk.STOCK_GO_FORWARD
                remote = gtk.STOCK_NO
        tree.set_value(self.rows[path]['iter'], 0, markup)
        tree.set_value(self.rows[path]['iter'], 2, local)
        tree.set_value(self.rows[path]['iter'], 3, direction)
        tree.set_value(self.rows[path]['iter'], 4, remote)



    def on_expand(self, treeview, iter, path, *user_params):
        # print 'Expanding'
        # print repr(model)
        # print repr(iter)
        # print repr(path)
        file_path = self.projectsTreeStore[iter][1]

        selection = self.hostsTree.get_selection()
        (model, iter) = selection.get_selected()
        t = threading.Thread(target=self.list_projects_remote, args=[model[iter][0], model[iter][1], model[iter][2], model[iter][3], model[iter][4], file_path])
        self.threads.append(t)
        t.setDaemon(True)
        t.start()


    def list_projects_remote(self, alias, address, user, port, projects_path, child=''):
        loader = gtk.image_new_from_animation(gtk.gdk.PixbufAnimation('../res/img/spinner01.gif'))
        self.button_load_remote_projects.set_image(loader)
        #cmd = ['ssh', '-oBatchMode=yes', '-p', str(port), '%s@%s' % (user, address), 'ls -xd %s/*/ %s/*/*' % (projects_path, projects_path)]
        type_filter = ''
        if child == '':
            type_filter = ' -type d'
        cmd = ['ssh', '-oBatchMode=yes', '-p', str(port), '%s@%s' % (user, address), 'find %s/%s %s -name PRIVATE -prune -o -maxdepth 2 -printf "%%i %%s %%T@ %%p\\\\n"' % (projects_path, child, type_filter)]
        print cmd
        try:
            p1 = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            output = p1.communicate()[0]
            if p1.returncode > 0:
                loader.set_from_stock(gtk.STOCK_APPLY, gtk.ICON_SIZE_BUTTON)
                gobject.idle_add(self.error, output)
                return
            projects = output.splitlines()
        except:
            print output
            raise
            gobject.idle_add(self.error, output)
            return
        #self.project_cell.set_property('foreground', '#000000')
        #self.project_cell.set_property('style', 'normal')
        for project_line in projects:
            try:
                print project_line
                f_inode, f_size, f_time, project_path = project_line.strip().split(' ', 3)
                project_name = project_path.strip('/').split('/')[-1]
                rel = project_path.replace(projects_path, '')
                gobject.idle_add(self.append_project, True, rel)
            except:
                continue
        loader.set_from_stock(gtk.STOCK_APPLY, gtk.ICON_SIZE_BUTTON)
        self.label_active_host.set_markup('<span foreground="#888888">Connected to host:</span> %s <span foreground="#888888">(%s)</span>' % (alias, address))
            #self.projectsTreeStore.append(None, [project_name])
        # cmd = ['ssh', '-p', str(port), '%s@%s' % (user, address), 'grep MISTIKA_WORK MISTIKA-ENV/MISTIKA_WORK']
        # output = subprocess.check_output(cmd)
        # projects_path = output.splitlines()[0].split()[1]
        #print projects_path

    def add_host(self, widget):
        self.hostsTreeStore.append(None, ['New host', '', 'mistika', 22, ''])

    def remove_host(self, widget):
        selection = self.hostsTree.get_selection()
        (model, iter) = selection.get_selected()
        try:
            model.remove(iter)
            self.hosts_store()
        except:
            raise

        #self.hostsTreeStore.append(None, ['New host', '', 'mistika', 22, ''])

    #def on_host_edit(self, cellrenderertoggle, path, *ignore):
    def on_host_edit(self, cell, path, new_text, user_data):
        tree, column = user_data
        print tree[path][column],
        tree[path][column] = new_text
        print '-> ' + tree[path][column]
        self.hosts_store()

    def error(self, message):
        dialog = gtk.MessageDialog(parent=self.window, 
                            flags=gtk.DIALOG_MODAL, 
                            type=gtk.MESSAGE_ERROR, 
                            buttons=gtk.BUTTONS_NONE, 
                            message_format=None)
        dialog.set_markup(message)
        dialog.run()

    def hosts_populate(self, tree):
        cfg_path = os.path.expanduser('~/.mistika-hyperspeed/sync/hosts.json')
        try:
            hosts = json.loads(open(cfg_path).read())
        except IOError as e:
            return
        #print repr(hosts)
        for host in hosts:
            row_iter = tree.append(None, [host, hosts[host]['address'], hosts[host]['user'], hosts[host]['port'], hosts[host]['path']])
            if hosts[host]['selected']:
                selection = self.hostsTree.get_selection()
                selection.select_iter(row_iter)
        status = 'Loaded hosts.'
        self.status_bar.push(self.context_id, status)


    def hosts_store(self):
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
                self.error('Could not create config folder:\n'+cfg_path_parent)
                return
        try:
            open(cfg_path, 'w').write(json.dumps(hosts, sort_keys=True, indent=4, separators=(',', ': ')))
            status = 'Wrote to %s' % cfg_path
            print status
            self.status_bar.push(self.context_id, status)
        except IOError as e:
            self.error('Could not write to file:\n'+cfg_path)
        except:
            raise

    def on_quit(self, widget):
        print 'Closed by: ' + repr(widget)
        for thread in self.threads:
            pass
        gtk.main_quit()

    def update_label(self, counter, label):
        label.set_text(counter)
        return False


    def worker(self, *task):
        task[0](task[1:])

    def ping(self, widget):
        self.p1 = subprocess.Popen(['ping', 'vg.no'], stdout=subprocess.PIPE)
        while self.p1.returncode == None:
            line = self.p1.stdout.readline()
            self.p1.poll()
            print line
            gobject.idle_add(self.update_label, line, self.label2)

    def button_click(self, widget):
        t = threading.Thread(target=self.ping, args=[widget])
        self.threads.append(t)
        t.setDaemon(True)
        t.start()

t = MyThread()
t.start()
gtk.main()
t.quit = True