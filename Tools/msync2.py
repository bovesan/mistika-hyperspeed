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
        window.set_title("Mistika remote sync")
        window.set_size_request(screen.get_width()-200, screen.get_height()-200)
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
        self.hosts_populate(hostsTreeStore)
        linksFilter = hostsTreeStore.filter_new();
        self.hostsTree.set_model(hostsTreeStore)
        self.hostsTree.expand_all()


        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(self.hostsTree)
        #vbox.pack_start(scrolled_window)
        vbox.pack_start(scrolled_window)

        hbox = gtk.HBox(False, 10)
        button = gtk.Button('+')
        button.set_size_request(30, 30)
        button.connect("clicked", self.add_host)
        hbox.pack_end(button, False, False, 0)
        button = gtk.Button('-')
        button.set_size_request(30, 30)
        button.connect("clicked", self.remove_host)
        hbox.pack_end(button, False, False, 0)

        button = gtk.Button('Reload local projects')
        button.connect("clicked", self.reload_local_projects)
        hbox.pack_start(button, False, False, 0)
        button = gtk.Button('Load remote projects')
        button.connect("clicked", self.on_host_select)
        hbox.pack_start(button, False, False, 0)


        vbox.pack_start(hbox, False, False, 0)
        self.projectsTreeStore = gtk.TreeStore(str) # Path
        self.projectsTree = gtk.TreeView()
        self.project_cell = gtk.CellRendererText()
        project_cell = self.project_cell
        #project_cell.set_property('foreground', '#cccccc')
        #project_cell.set_property('style', 'italic')
        #cell.connect('edited', self.on_host_edit, (self.projectsTreeStore, 0))
        column = gtk.TreeViewColumn('', project_cell, text=0)
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
        #self.projectsTree.expand_all()
        self.reload_local_projects()

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(self.projectsTree)
        #vbox.pack_start(scrolled_window)
        vbox.pack_start(scrolled_window)



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
        self.quit = False

    def on_host_select(self, widget):
        selection = self.hostsTree.get_selection()
        (model, iter) = selection.get_selected()
        print model[iter][0]
        t = threading.Thread(target=self.list_projects, args=[model[iter][1], model[iter][2], model[iter][3], model[iter][4]])
        self.threads.append(t)
        t.setDaemon(True)
        t.start()

    def reload_local_projects(self, *widget):
        t = threading.Thread(target=self.list_projects_local)
        self.threads.append(t)
        t.setDaemon(True)
        t.start()

    def list_projects_local(self):
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
                    gobject.idle_add(self.append_project, 'local', root_rel+'/'+name)
        except:
            raise

    def append_project(self, location, path, children=None):
        path = path.lstrip('/')
        projects_in_tree = {}
        tree = self.projectsTreeStore
        parts = path.split('/')
        parent = None
        for i, row in enumerate(tree):
            if row[0] == parts[0]:
                parent = tree[i]
                parts.pop(0)
                iterator = parent.iterchildren()
                while len(parts) > 1:
                    print path
                    item = iterator.next()
                    print item[0]
                    if path.startswith(item[0]):
                        parent = item
                        iterator = parent.iterchildren()
        if parent == None:
            parent = self.projectsTreeStore.append(None, [path])
            self.projectsTreeStore.append(parent, ['Loading project structure ...'])
        else:
            parent = self.projectsTreeStore.append(parent, [path])
            self.projectsTreeStore.append(parent, ['Loading project structure ...'])




    def list_projects(self, address, user, port, projects_path):
        cmd = ['ssh', '-oBatchMode=yes', '-p', str(port), '%s@%s' % (user, address), 'ls -xd %s/*/' % projects_path]
        try:
            p1 = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            output = p1.communicate()[0]
            if p1.returncode > 0:
                gobject.idle_add(self.error, output)
                return
            projects = output.splitlines()
        except:
            print output
            raise
            gobject.idle_add(self.error, output)
            return
        self.projectsTreeStore.clear()
        self.project_cell.set_property('foreground', '#000000')
        self.project_cell.set_property('style', 'normal')
        for project_path in projects:
            project_name = project_path.strip('/').split('/')[-1]
            gobject.idle_add(self.append_project, 'remote', project_name)
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
            tree.append(None, [host, hosts[host]['address'], hosts[host]['user'], hosts[host]['port'], hosts[host]['path']])
        status = 'Loaded hosts.'
        self.status_bar.push(self.context_id, status)


    def hosts_store(self):
        tree = self.hostsTreeStore
        cfg_path = os.path.expanduser('~/.mistika-hyperspeed/sync/hosts.json')
        hosts = {}
        for row in tree:
            alias = row[0]
            for value in row:
                print value,
            print ''
            hosts[alias] = {}
            hosts[alias]['address'] = row[1]
            hosts[alias]['user'] = row[2]
            hosts[alias]['port'] = row[3]
            hosts[alias]['path'] = row[4]
        cfg_path_parent = os.path.dirname(cfg_path)
        if not os.path.isdir(cfg_path_parent):
            try:
                os.makedirs(cfg_path_parent)
            except IOError as e:
                self.error('Could not create config folder:\n'+cfg_path_parent)
                return
        try:
            open(cfg_path, 'w').write(json.dumps(hosts))
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

    def run(self):
        selection = self.hostsTree.get_selection()
        selection.unselect_all()

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