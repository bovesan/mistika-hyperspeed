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

try:
    os.chdir(os.path.dirname(sys.argv[0]))
    sys.path.append("..") 
    from hyperspeed.stack import Stack
    from hyperspeed import mistika
except (OSError):
    mistika = False

class PyApp(gtk.Window):

    def __init__(self):
        super(PyApp, self).__init__()
        screen = self.get_screen()
        self.set_title("Consolidate Mistika structures")
        self.set_size_request(800, screen.get_height()-200)
        self.set_border_width(20)
        self.set_position(gtk.WIN_POS_CENTER)
        if 'darwin' in platform.system().lower():
            self.set_resizable(False) # Because resizing crashes the app on Mac

        self.stacks = {}
        self.dependency_names = []
        self.threads = []


        vbox = gtk.VBox(False, 10)

        hbox = gtk.HBox(False, 10)
        hbox.pack_start(gtk.Label('Environments, groups or other structures to consolidate:'), False, False, 0)
        vbox.pack_start(hbox, False, False, 0)

        self.linksTree = gtk.TreeView()
        cell = gtk.CellRendererText()
        cell.set_property("editable", True)
        column = gtk.TreeViewColumn('', cell, text=0)
        column.set_resizable(True)
        column.set_expand(True)
        self.linksTree.append_column(column)
        cell = gtk.CellRendererProgress()
        column = gtk.TreeViewColumn('', cell, value=1, text=2)
        column.add_attribute(cell, 'visible', 3)
        column.set_expand(True)
        column.set_resizable(True)
        self.linksTree.append_column(column)

        self.stacks_treestore = gtk.TreeStore(str, float, str, bool) # Name, progress float, progress text, progress visible
        treestore = self.stacks_treestore
        self.linksTree.set_model(treestore)
        self.linksTree.expand_all()

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(self.linksTree)
        #vbox.pack_start(scrolled_window)
        vbox.pack_start(scrolled_window)

        hbox = gtk.HBox(False, 10)
        button = gtk.Button('Add structure ...')
        button.connect("clicked", self.add_file_dialog)
        hbox.pack_end(button, False, False, 0)
        vbox.pack_start(hbox, False, False, 0)

        hbox = gtk.HBox(False, 10)
        hbox.pack_start(gtk.Label('Dependencies in loaded structures:'), False, False, 0)
        vbox.pack_start(hbox, False, False, 0)

        self.linksTree = gtk.TreeView()
        cell = gtk.CellRendererText()
        cell.set_property("editable", True)
        column = gtk.TreeViewColumn('', cell, text=0)
        column.set_resizable(True)
        column.set_expand(True)
        self.linksTree.append_column(column)
        cell = gtk.CellRendererText()
        cell.set_property("foreground", "gray")
        cell.set_property("editable", True)
        column = gtk.TreeViewColumn('Path', cell, text=1)
        column.set_resizable(True)
        column.set_expand(True)
        self.dependencies_treestore = gtk.TreeStore(str, float, str, bool) # Name, progress float, progress text, progress visible
        treestore = self.dependencies_treestore
        # linksTreestore.append(None, ["Horten", 'horten.hocusfocus.no', 'mistika', 22, '/Volumes/SLOW_HF/PROJECTS/'])
        self.linksTree.set_model(treestore)
        self.linksTree.expand_all()

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(self.linksTree)
        #vbox.pack_start(scrolled_window)
        vbox.pack_start(scrolled_window)

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
        button.connect("clicked", self.copy_start)
        hbox.pack_start(button, False, False, 5)
        self.status_label = gtk.Label('Not started')
        hbox.pack_start(self.status_label, False, False, 5)
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
        dialog.add_shortcut_folder('/home/mistika/MISTIKA-ENV')
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
            stack_path = dialog.get_filename()
            print stack_path
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
        elif response == gtk.RESPONSE_CANCEL:
            print 'Closed, no files selected'
        dialog.destroy()
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
    def copy_start(self, widget):
        destination_folder = self.destination_folder_entry.get_text()
        if not os.path.isdir(destination_folder):
            try:
                os.makedirs(destination_folder)
            except OSError:
                print 'Could not create destination folder. Aborting.'
                return
        if not destination_folder.endswith('/'):
            destination_folder += '/'
        self.copy_queue = []
        for stack_path in self.stacks:
            cmd = ['rsync', '-ua', stack_path, destination_folder]
            subprocess.call(cmd)
            for dependency in self.stacks[stack_path].dependencies:
                self.copy_queue.append(dependency.path)
        print repr(self.copy_queue)
        with tempfile.NamedTemporaryFile() as temp:
            temp.write('\n'.join(self.copy_queue) + '\n')
            temp.flush()
            # subprocess.call(['cat', temp.name])
            # rsync -a --files-from=/tmp/foo /usr remote:/backup
            cmd = ['rsync', '-ua', '--files-from=%s' % temp.name, '/', destination_folder]
            status = subprocess.call(cmd)
            if status == 0:
                self.status_label.set_text('Finished successfully')
            else:
                self.status_label.set_text('Finished with errors')
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
            if not dependency.name in self.dependency_names:
                self.dependency_names.append(dependency.name)
                gobject.idle_add(self.gui_dependency_add, dependency)


    def stack_read_progress(self, stack, progress):
        gobject.idle_add(self.gui_stack_set_progress, stack, progress)
    def gui_stack_set_progress(self, stack, progress):
        row_path = stack.row_reference.get_path()
        progress_percent = progress * 100.0
        progress_string = '%5.2f%%' % progress_percent
        progress_string = 'Looking for dependencies'
        # print stack, progress, progress_string
        if progress == 1.0:
            progress_string = 'Loaded dependencies'
        self.stacks_treestore[row_path][1] = progress_percent
        self.stacks_treestore[row_path][2] = progress_string
        self.stacks_treestore[row_path][3] = True
    def gui_dependency_add(self, dependency):
        # print self, dependency
        self.dependencies_treestore.append(None, [dependency.name, 0, '', False])

gobject.threads_init()
PyApp()
gtk.main()