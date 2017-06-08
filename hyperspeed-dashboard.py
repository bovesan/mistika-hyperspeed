#!/usr/bin/python
# -*- coding: utf-8 -*-

import gtk
import gobject
import hashlib
import imp
import json
import os
import sys
import platform
import Queue
import subprocess
import threading
import xml.etree.ElementTree as ET
import webbrowser

VERSION_STRING = '<span color="#ff9900" weight="bold">Development version.</span>'

CONFIG_FOLDER = '~/.mistika-hyperspeed/'
CONFIG_FILE = 'hyperspeed.cfg'
STACK_EXTENSIONS = ['.grp', '.fx', '.env']

AUTORUN_TIMES = {
    'Never' :   False,
    'Hourly' :  '0 * * * *',
    'Daily' :   '0 4 * * *',
    'Weekly' :  '0 4 * * 7',
    'Monthly' : '0 4 1 * *'
}

CONFIG_FOLDER = os.path.expanduser(CONFIG_FOLDER)
os.chdir(os.path.dirname(sys.argv[0]))

import hyperspeed.manage
from hyperspeed import mistika

def md5(fname):
    hash_md5 = hashlib.md5()
    if os.path.isdir(fname):
        fnames = []
        for root, dirs, files in os.walk(fname):
            for fname in files:
                fnames.append(os.path.join(root, fname))
    else:
        fnames = [fname]
    for fname in fnames:
        try:
            with open(fname, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
        except OSError:
            pass
    return hash_md5.hexdigest()

def get_crontab_lines():
    try:
        crontab = subprocess.Popen(['crontab', '-l'], stdout=subprocess.PIPE).communicate()[0].splitlines()
    except subprocess.CalledProcessError:
        crontab = []
    return crontab

class PyApp(gtk.Window):

    def __init__(self):


        super(PyApp, self).__init__()

        self.config_rw()
        # self.files_update()
        self.threads = []
        self.queue_io = Queue.Queue()
        self.files = {}
        screen = self.get_screen()
        self.set_title("Hyperspeed")
        self.set_size_request(screen.get_width()/2, screen.get_height()-200)
        self.set_border_width(20)
        self.set_position(gtk.WIN_POS_CENTER)
        if 'darwin' in platform.system().lower():
            self.set_resizable(False) # Because resizing crashes the app on Mac

        gtkrc = '''
        style "theme-fixes" {
            font_name = "sans normal %i"
        }
        class "*" style "theme-fixes"''' % (screen.get_width()/300)
        gtk.rc_parse_string(gtkrc)

        vbox = gtk.VBox(False, 10)
        self.filterEntry = gtk.Entry()
        vbox.pack_start(self.init_toolbar(), False, False, 10)
        self.iters = {}

        notebook = gtk.Notebook()

        notebook.append_page(self.init_tools_window(), gtk.Label('Tools'))
        notebook.append_page(self.init_afterscripts_window(), gtk.Label('Afterscripts'))
        notebook.append_page(self.init_stacks_window(), gtk.Label('Stacks'))
        notebook.append_page(self.init_configs_window(), gtk.Label('Configs'))
        notebook.append_page(self.init_links_window(), gtk.Label('Web links'))
        vbox.pack_start(notebook)

        #vbox.pack_start(gtk.HSeparator())
        headerBox = gtk.HBox(False, 5)
        headerLabel  = gtk.Label('<span size="large"><b>Render queue:</b></span>')
        headerLabel.set_use_markup(True)
        headerBox.pack_start(headerLabel, False, False, 5)
        vbox.pack_start(headerBox, False, False, 2)
        afterscriptsToolbar = gtk.HBox(False, 2)
        #afterscriptsToolbar.pack_start(headerBox, False, False, 2)
        checkButton = gtk.CheckButton('Process queue')
        checkButton.set_property("active", True)
        afterscriptsToolbar.pack_start(checkButton, False, False, 5)
        afterscriptsToolbar.pack_start(gtk.CheckButton('Process jobs for other hosts'), False, False, 5)
        vbox.pack_start(afterscriptsToolbar, False, False, 2)
        afterscriptsBox = gtk.HBox(False, 5)
        self.queueTree = gtk.TreeView()
        queueTreeNameColumn = gtk.TreeViewColumn('Project', gtk.CellRendererText(), text=0)
        queueTreeNameColumn.set_resizable(True)
        queueTreeNameColumn.set_expand(False)
        self.queueTree.append_column(queueTreeNameColumn)
        queueTreeNameColumn = gtk.TreeViewColumn('Name', gtk.CellRendererText(), text=1)
        queueTreeNameColumn.set_resizable(True)
        queueTreeNameColumn.set_expand(False)
        self.queueTree.append_column(queueTreeNameColumn)
        cell = gtk.CellRendererProgress()
        queueTreeNameColumn = gtk.TreeViewColumn('Progress', cell, value=5, text=6)
        queueTreeNameColumn.set_cell_data_func(cell, self.hide_if_parent)
        queueTreeNameColumn.set_resizable(True)
        queueTreeNameColumn.set_expand(False)
        self.queueTree.append_column(queueTreeNameColumn)
        queueTreeNameColumn = gtk.TreeViewColumn('Status', gtk.CellRendererText(), text=2)
        queueTreeNameColumn.set_resizable(True)
        queueTreeNameColumn.set_expand(True)
        self.queueTree.append_column(queueTreeNameColumn)
        queueTreeNameColumn = gtk.TreeViewColumn('Added by', gtk.CellRendererText(), text=3)
        queueTreeNameColumn.set_resizable(True)
        queueTreeNameColumn.set_expand(False)
        self.queueTree.append_column(queueTreeNameColumn)
        queueTreeNameColumn = gtk.TreeViewColumn('Added time', gtk.CellRendererText(), text=4)
        queueTreeNameColumn.set_resizable(True)
        queueTreeNameColumn.set_expand(False)
        self.queueTree.append_column(queueTreeNameColumn)
        cell2 = gtk.CellRendererToggle()
        self.queueTreestore = gtk.TreeStore(str, str, str, str, str, int, str)
        queueTreestore = self.queueTreestore
        # it = queueTreestore.append(None, ["Private (6)", '', '', '', '', 0, ''])
        # queueTreestore.append(it, ["RnD", 'test_0001', 'Rendering on gaia', 'gaia', '08:27', 20, '20%'])
        # queueTreestore.append(it, ["RnD", 'test_0001', 'Queued', 'gaia', '08:27', 0, ''])
        # queueTreestore.append(it, ["RnD", 'test_0001', 'Queued', 'gaia', '08:27', 0, ''])
        # queueTreestore.append(it, ["RnD", 'test_0001', 'Queued', 'gaia', '08:27', 0, ''])
        # queueTreestore.append(it, ["RnD", 'test_0001', 'Queued', 'gaia', '08:27', 0, ''])
        # queueTreestore.append(it, ["RnD", 'test_0001', 'Queued', 'gaia', '08:27', 0, ''])
        # it = queueTreestore.append(None, ["Public (2)", '', '', '', '', 0, ''])
        # queueTreestore.append(it, ["Mastering", 'film01', 'Queued', 'apollo2', '08:27', 0, ''])
        # queueTreestore.append(it, ["Mastering", 'film02', 'Queued', 'apollo2', '08:27', 0, ''])
        self.queueTree.set_model(queueTreestore)
        self.queueTree.expand_all()
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(self.queueTree)
        afterscriptsBox.pack_start(scrolled_window)
        afterscriptsButtons = gtk.VBox(False, 3)
        afterscriptsButtons.set_size_request(30,80)
        gtk.stock_add([(gtk.STOCK_GO_UP, "", 0, 0, "")])
        upButton = gtk.Button(stock=gtk.STOCK_GO_UP)
        afterscriptsButtons.pack_start(upButton)
        gtk.stock_add([(gtk.STOCK_GO_DOWN, "", 0, 0, "")])
        downButton = gtk.Button(stock=gtk.STOCK_GO_DOWN)
        afterscriptsButtons.pack_start(downButton)
        afterscriptsBox.pack_start(afterscriptsButtons, False, False)
        vbox.pack_start(afterscriptsBox, True, True, 5)


        headerBox = gtk.HBox(False, 5)
        headerLabel  = gtk.Label('<span size="large"><b>Afterscript queue:</b></span>')
        headerLabel.set_use_markup(True)
        headerBox.pack_start(headerLabel, False, False, 5)
        vbox.pack_start(headerBox, False, False, 2)
        afterscriptsToolbar = gtk.HBox(False, 2)
        #afterscriptsToolbar.pack_start(headerBox, False, False, 2)
        checkButton = gtk.CheckButton('Process queue')
        checkButton.set_property("active", True)
        afterscriptsToolbar.pack_start(checkButton, False, False, 5)
        afterscriptsToolbar.pack_start(gtk.CheckButton('Process jobs for other hosts'), False, False, 5)
        simulBox =  gtk.HBox(False, 5)
        simulBox.pack_start(gtk.Label('Simultaneous jobs:'), False, False, 0)
        simulBox.pack_start(gtk.SpinButton(gtk.Adjustment(value=5, lower=0, upper=999, step_incr=1, page_incr=0, page_size=0)), False, False, 0)
        afterscriptsToolbar.pack_start(simulBox, False, False, 5)
        vbox.pack_start(afterscriptsToolbar, False, False, 2)
        afterscriptsBox = gtk.HBox(False, 5)
        self.queueTree = gtk.TreeView()
        queueTreeNameColumn = gtk.TreeViewColumn('Project', gtk.CellRendererText(), text=0)
        queueTreeNameColumn.set_resizable(True)
        queueTreeNameColumn.set_expand(False)
        self.queueTree.append_column(queueTreeNameColumn)
        queueTreeNameColumn = gtk.TreeViewColumn('Name', gtk.CellRendererText(), text=1)
        queueTreeNameColumn.set_resizable(True)
        queueTreeNameColumn.set_expand(False)
        self.queueTree.append_column(queueTreeNameColumn)
        queueTreeNameColumn = gtk.TreeViewColumn('Progress', gtk.CellRendererProgress())
        queueTreeNameColumn.set_resizable(True)
        queueTreeNameColumn.set_expand(False)
        self.queueTree.append_column(queueTreeNameColumn)
        queueTreeNameColumn = gtk.TreeViewColumn('Status', gtk.CellRendererText(), text=2)
        queueTreeNameColumn.set_resizable(True)
        queueTreeNameColumn.set_expand(True)
        self.queueTree.append_column(queueTreeNameColumn)
        queueTreeNameColumn = gtk.TreeViewColumn('Added by', gtk.CellRendererText(), text=3)
        queueTreeNameColumn.set_resizable(True)
        queueTreeNameColumn.set_expand(False)
        self.queueTree.append_column(queueTreeNameColumn)
        queueTreeNameColumn = gtk.TreeViewColumn('Added time', gtk.CellRendererText(), text=4)
        queueTreeNameColumn.set_resizable(True)
        queueTreeNameColumn.set_expand(False)
        self.queueTree.append_column(queueTreeNameColumn)
        cell2 = gtk.CellRendererToggle()
        self.queueTreestore = gtk.TreeStore(str, str, str, str, str)
        queueTreestore = self.queueTreestore
        # queueTreestore.append(None, ["RnD", 'test_0001', 'Running on apollo2', 'gaia', '08:27'])
        # queueTreestore.append(None, ["RnD", 'test_0001', 'Running on apollo2', 'gaia', '08:27'])
        # queueTreestore.append(None, ["RnD", 'test_0001', 'Running on apollo2', 'gaia', '08:27'])
        # queueTreestore.append(None, ["RnD", 'test_0001', 'Running on apollo2', 'apollo2', '08:27'])
        # queueTreestore.append(None, ["RnD", 'test_0001', 'Running on apollo2', 'apollo1', '08:27'])
        # queueTreestore.append(None, ["RnD", 'test_0001', 'Running on apollo2', 'gaia', '08:27'])
        # queueTreestore.append(None, ["RnD", 'test_0001', 'Running on apollo2', 'gaia', '08:27'])
        # queueTreestore.append(None, ["RnD", 'test_0001', 'Queued', 'gaia', '08:27'])
        # queueTreestore.append(None, ["RnD", 'test_0001', 'Queued', 'gaia', '08:27'])
        self.queueTree.set_model(queueTreestore)
        self.queueTree.expand_all()
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(self.queueTree)
        afterscriptsBox.pack_start(scrolled_window)
        afterscriptsButtons = gtk.VBox(False, 3)
        afterscriptsButtons.set_size_request(30,80)
        gtk.stock_add([(gtk.STOCK_GO_UP, "", 0, 0, "")])
        upButton = gtk.Button(stock=gtk.STOCK_GO_UP)
        afterscriptsButtons.pack_start(upButton)
        gtk.stock_add([(gtk.STOCK_GO_DOWN, "", 0, 0, "")])
        downButton = gtk.Button(stock=gtk.STOCK_GO_DOWN)
        afterscriptsButtons.pack_start(downButton)
        afterscriptsBox.pack_start(afterscriptsButtons, False, False)
        vbox.pack_start(afterscriptsBox, True, True, 5)


        footer = gtk.HBox(False, 10)
        quitButton = gtk.Button('Quit')
        quitButton.set_size_request(70, 30)
        quitButton.connect("clicked", self.on_quit)
        footer.pack_end(quitButton, False, False)

        vbox.pack_end(footer, False, False, 10)

        self.add(vbox)

        self.connect("destroy", self.on_quit)
        self.show_all()
        self.set_keep_above(True)

        self.comboEditable = None
        #self.present()
    def init_toolbar(self):
        filterEntry = self.filterEntry
        toolbarBox = gtk.HBox(False, 10)
        filterBox = gtk.HBox(False, 10)
        filterLabel = gtk.Label('Filter: ')
        filterBox.pack_start(filterLabel, False, False,)
        filterEntry.add_events(gtk.gdk.KEY_RELEASE_MASK)
        filterEntry.connect("activate", self.on_filter)
        filterEntry.connect("key-release-event", self.on_filter)
        filterEntry.grab_focus()
        filterBox.pack_start(filterEntry, False, False)
        toolbarBox.pack_start(filterBox, False, False)
        versionBox = gtk.HBox(False, 2)
        versionStr = VERSION_STRING
        versionLabel = gtk.Label(versionStr)
        versionLabel.set_use_markup(True)
        versionBox.pack_start(versionLabel, False, False, 5)
        updateButton = gtk.Button('Update')
        #versionBox.pack_start(updateButton, False, False, 5)
        toolbarBox.pack_end(versionBox, False, False)
        return toolbarBox

    def init_tools_window(self):
        tree        = self.tools_tree      = gtk.TreeView()
        treestore   = self.tools_treestore = gtk.TreeStore(str, bool, bool, str, str) # Name, show in Mistika, is folder, autorun, file_path
        tree_filter = self.tools_filter    = treestore.filter_new();
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn('', cell, text=0)
        column.set_resizable(True)
        column.set_expand(True)
        tree.append_column(column)
        autorunStates = gtk.ListStore(str)
        autorunStates.append(['Never'])
        autorunStates.append(['Hourly'])
        autorunStates.append(['Daily'])
        autorunStates.append(['Weekly'])
        autorunStates.append(['Monthly'])
        cell = gtk.CellRendererCombo()
        cell.set_property("editable", True)
        cell.set_property("has-entry", False)
        cell.set_property("text-column", 0)
        cell.set_property("model", autorunStates)
        cell.connect('changed', self.on_combo_changed)
        cell.connect('editing-started', self.on_editing_started)
        cell.connect("edited", self.on_autorun_set)
        toolsTreeAutorunColumn = gtk.TreeViewColumn("Autorun", cell, text=3)
        toolsTreeAutorunColumn.set_resizable(True)
        toolsTreeAutorunColumn.set_expand(False)
        toolsTreeAutorunColumn.set_cell_data_func(cell, self.hide_if_parent)
        tree.append_column(toolsTreeAutorunColumn)
        if hyperspeed.mistika.product == 'Mistika':
            cell = gtk.CellRendererToggle()
            cell.connect("toggled", self.on_tools_toggle, tree)
            toolsTreeInMistikaColumn = gtk.TreeViewColumn("Show in %s" % mistika.product, cell, active=1)
            toolsTreeInMistikaColumn.set_cell_data_func(cell, self.hide_if_parent)
            toolsTreeInMistikaColumn.set_expand(False)
            toolsTreeInMistikaColumn.set_resizable(True)
            tree.append_column(toolsTreeInMistikaColumn)
        tree_filter.set_visible_func(self.FilterTree, (self.filterEntry, tree));
        tree.set_model(tree_filter)
        tree.expand_all()
        tree.connect('row-activated', self.on_tools_run, tree)
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(tree)
        t = threading.Thread(target=self.io_populate_tools)
        self.threads.append(t)
        t.setDaemon(True)
        t.start()
        return scrolled_window

    def io_populate_tools(self):
        file_type = 'Tools'
        file_type_defaults = {
            'Autorun' : 'Never',
            'Show in Mistika' : False,
        }
        if not file_type in self.files:
            self.files[file_type] = {}
        files = self.files[file_type]
        # Installed tools
        tools_installed = []
        if hyperspeed.mistika.product == 'Mistika':
            for line in open(mistika.tools_path):
                line_alias, line_path = line.strip().split(' ', 1)
                tools_installed.append(line_path)
        # Crontab
        crontab = get_crontab_lines()
        for root, dirs, filenames in os.walk(os.path.join(self.config['app_folder'], file_type)):
            for name in dirs:
                path = os.path.join(root, name)
                if 'config.xml' in os.listdir(path):
                    tree = ET.parse(os.path.join(path, 'config.xml'))
                    treeroot = tree.getroot()
                    path = os.path.join(path, treeroot.find('executable').text)
                    files[path] = {'isdir' : False}
                    for child in treeroot:
                        files[path][child.tag] = child.text
                else:
                    files[path] = {'isdir' : True}
        for path in files:
            if not os.path.exists(path):
                del files[path]
                continue
            if files[path]['isdir']:
                continue
            for key, value in file_type_defaults.iteritems():
                files[path].setdefault(key, value)
            if path in tools_installed:
                files[path]['Show in Mistika'] = True
            for line in crontab:
                print repr(line)
                line = line.strip()
                if line.endswith(path):
                    for autorun_alias, autorun_value in AUTORUN_TIMES.iteritems():
                        if autorun_value == False:
                            continue
                        if line.startswith(autorun_value):
                            files[path]['Autorun'] = autorun_alias
        gobject.idle_add(self.gui_update_tools)

    def gui_update_tools(self):
        treestore = self.tools_treestore # Name, show in Mistika, is folder, autorun, file path
        iters = self.iters
        items = self.files['Tools']
        for item_path in sorted(items):
            item = items[item_path]
            dir_name = os.path.dirname(item_path)
            alias = os.path.basename(item_path)
            try:
                alias = items[item_path]['alias']
            except KeyError:
                pass
            if not dir_name in iters:
                iters[dir_name] = None
            if item['isdir']:
                iters[item_path] = treestore.append(iters[dir_name], [alias, False, True, '', item_path])
            else:
                treestore.append(iters[dir_name], [alias, item['Show in Mistika'], False, item['Autorun'], item_path])

    def init_afterscripts_window(self):
        tree        = self.afterscripts_tree      = gtk.TreeView()
        treestore   = self.afterscripts_treestore = gtk.TreeStore(str, bool, bool, str) # Name, show in Mistika, is folder, file path
        tree_filter = self.afterscripts_filter    = treestore.filter_new();
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn('', cell, text=0)
        column.set_resizable(True)
        column.set_expand(True)
        tree.append_column(column)
        cell = gtk.CellRendererToggle()
        cell.connect("toggled", self.on_afterscripts_toggle, tree)
        toolsTreeInMistikaColumn = gtk.TreeViewColumn("Show in %s" % mistika.product, cell, active=1)
        toolsTreeInMistikaColumn.set_cell_data_func(cell, self.hide_if_parent)
        toolsTreeInMistikaColumn.set_expand(False)
        toolsTreeInMistikaColumn.set_resizable(True)
        tree.append_column(toolsTreeInMistikaColumn)
        tree_filter.set_visible_func(self.FilterTree, (self.filterEntry, tree));
        tree.set_model(tree_filter)
        tree.expand_all()
        tree.connect('row-activated', self.on_afterscripts_run, tree)
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(tree)
        t = threading.Thread(target=self.io_populate_afterscripts)
        self.threads.append(t)
        t.setDaemon(True)
        t.start()
        return scrolled_window

    def io_populate_afterscripts(self):
        file_type = 'Afterscripts'
        file_type_defaults = {
            'Show in Mistika' : False
        }
        if not file_type in self.files:
            self.files[file_type] = {}
        files = self.files[file_type]
        # Installed afterscripts
        afterscripts_installed = []
        for line in open(mistika.afterscripts_path):
            alias = line.strip()
            link_path = os.path.join(mistika.scripts_folder, alias)
            afterscripts_installed.append(os.path.realpath(link_path))
        for root, dirs, filenames in os.walk(os.path.join(self.config['app_folder'], file_type)):
            for name in dirs:
                path = os.path.join(root, name)
                if 'config.xml' in os.listdir(path):
                    tree = ET.parse(os.path.join(path, 'config.xml'))
                    root = tree.getroot()
                    path = os.path.join(path, root.find('executable').text)
                    files[path] = {
                        'isdir' : False,
                        'alias' : name
                    }
                    for key, value in file_type_defaults.iteritems():
                        files[path].setdefault(key, value)
                    for child in root:
                        files[path][child.tag] = child.text
                else:
                    files[path] = {'isdir' : True}
        for path in files:
            if not os.path.exists(path):
                del files[path]
                continue
            if files[path]['isdir']:
                continue
            if path in afterscripts_installed:
                files[path]['Show in Mistika'] = True
        gobject.idle_add(self.gui_update_afterscripts)

    def gui_update_afterscripts(self):
        tree_store = self.afterscripts_treestore # Name, show in Mistika, is folder
        iters = self.iters
        items = self.files['Afterscripts']
        for item_path in sorted(items):
            item = items[item_path]
            dir_name = os.path.dirname(item_path)
            base_name = os.path.basename(item_path)
            if not dir_name in iters:
                iters[dir_name] = None
            if item['isdir']:
                iters[item_path] = tree_store.append(iters[dir_name], [base_name, False, True, item_path])
            else:
                tree_store.append(iters[dir_name], [base_name, item['Show in Mistika'], False, item_path])

    def init_stacks_window(self):
        tree        = self.stacks_tree      = gtk.TreeView()
        treestore   = self.stacks_treestore = gtk.TreeStore(str, bool, bool, str, bool) # Name, installed, is folder, file path, requires installation (has dependencies)
        tree_filter = self.stacks_filter    = treestore.filter_new();
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn('', cell, text=0)
        column.set_resizable(True)
        column.set_expand(True)
        tree.append_column(column)
        cell = gtk.CellRendererToggle()
        cell.connect("toggled", self.on_stacks_toggle, tree)
        toolsTreeInMistikaColumn = gtk.TreeViewColumn("Installed", cell, active=1)
        toolsTreeInMistikaColumn.set_cell_data_func(cell, self.hide_if_parent)
        toolsTreeInMistikaColumn.add_attribute(cell, 'activatable', 4)
        #linksTreeUrlColumn.add_attribute(cell2, 'underline-set', 3)
        toolsTreeInMistikaColumn.set_expand(False)
        toolsTreeInMistikaColumn.set_resizable(True)
        tree.append_column(toolsTreeInMistikaColumn)
        tree_filter.set_visible_func(self.FilterTree, (self.filterEntry, tree));
        tree.set_model(tree_filter)
        tree.expand_all()
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(tree)
        t = threading.Thread(target=self.io_populate_stacks)
        self.threads.append(t)
        t.setDaemon(True)
        t.start()
        return scrolled_window

    def io_populate_stacks(self):
        file_type = 'Stacks'
        file_type_defaults = {
            'Installed' : True,
            'Dependent' : False
        }
        if not file_type in self.files:
            self.files[file_type] = {}
        files = self.files[file_type]
        for root, dirs, filenames in os.walk(os.path.join(self.config['app_folder'], file_type)):
            for name in dirs:
                path = os.path.join(root, name)
                files[path] = {'isdir' : True}
            for name in filenames:
                path = os.path.join(root, name)
                if os.path.splitext(name)[1].lower() in STACK_EXTENSIONS:
                    files[path] = {'isdir' : False}
        for path in files:
            if not os.path.exists(path):
                del files[path]
                continue
            if files[path]['isdir']:
                continue
            if not 'dependencies' in files[path]:
                files[path]['dependencies'] = hyperspeed.Stack(path).dependencies
            if len(files[path]['dependencies']) > 0:
                files[path]['Dependent'] = True
            for dependency in files[path]['dependencies']:
                if not dependency.check():
                    files[path]['Installed'] = False
            for key, value in file_type_defaults.iteritems():
                files[path].setdefault(key, value)
            if files[path]['isdir']:
                continue
        gobject.idle_add(self.gui_update_stacks)

    def gui_update_stacks(self):
        tree = self.stacks_treestore # Name, installed, is folder, file path, requires installation (has dependencies)
        iters = self.iters
        items = self.files['Stacks']
        for item_path in sorted(items):
            item = items[item_path]
            dir_name = os.path.dirname(item_path)
            base_name = os.path.basename(item_path)
            if not dir_name in iters:
                iters[dir_name] = None
            if item['isdir']:
                iters[item_path] = tree.append(iters[dir_name], [base_name, False, True, item_path, False])
            else:
                tree.append(iters[dir_name], [base_name, item['Installed'], False, item_path, item['Dependent']])

    def init_configs_window(self):
        tree        = self.configs_tree      = gtk.TreeView()
        treestore   = self.configs_treestore = gtk.TreeStore(str, bool, bool, str) # Name, active, is folder, path
        tree_filter = self.configs_filter    = treestore.filter_new();
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn('', cell, text=0)
        column.set_resizable(True)
        column.set_expand(True)
        tree.append_column(column)
        cell = gtk.CellRendererToggle()
        cell.connect("toggled", self.on_configs_toggle, tree)
        column = gtk.TreeViewColumn("Active", cell, active=1)
        column.set_cell_data_func(cell, self.hide_if_parent)
        column.set_expand(False)
        column.set_resizable(True)
        tree.append_column(column)
        tree_filter.set_visible_func(self.FilterTree, (self.filterEntry, tree));
        tree.set_model(tree_filter)
        tree.expand_all()
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(tree)
        t = threading.Thread(target=self.io_populate_configs)
        self.threads.append(t)
        t.setDaemon(True)
        t.start()
        return scrolled_window

    def io_populate_configs(self):
        file_type = 'Configs'
        file_type_defaults = {
            'Active' : False
        }
        if not file_type in self.files:
            self.files[file_type] = {}
        files = self.files[file_type]
        for root, dirs, filenames in os.walk(os.path.join(self.config['app_folder'], file_type)):
            for name in dirs:
                path = os.path.join(root, name)
                if 'config.xml' in os.listdir(path):
                    tree = ET.parse(os.path.join(path, 'config.xml'))
                    treeroot = tree.getroot()
                    files[path] = {'isdir' : False}
                    for child in treeroot:
                        if child.tag == 'links':
                            files[path][child.tag] = {}
                            for link in child:
                                link_target = link.find('target').text
                                link_target = os.path.abspath(os.path.join(path, link_target))
                                link_location = link.find('location').text
                                if link_location.startswith('MISTIKA-ENV/'):
                                    link_location = os.path.join(mistika.env_folder, link_location[12:])
                                files[path][child.tag][link_target] = link_location
                                
                        elif child.tag == 'manage':
                            files[path][child.tag] = child.text.lower() == 'true'
                        else:
                            files[path][child.tag] = child.text
                else:
                    files[path] = {'isdir' : True}
        for path in files:
            if not os.path.exists(path):
                del files[path]
                continue
            if files[path]['isdir']:
                continue
            detected = True
            if files[path]['manage']:
                try:
                    if subprocess.call([os.path.join(path, 'manage'), 'detect']) > 0:
                        detected = False
                except OSError as e:
                    detected = False
            if 'links' in files[path]:
                print repr(files[path]['links'])
                for link_target, link in files[path]['links'].iteritems():
                    if not hyperspeed.manage.detect(link_target, link):
                        detected = False
            files[path]['Active'] = detected
            for key, value in file_type_defaults.iteritems():
                files[path].setdefault(key, value)
        gobject.idle_add(self.gui_update_configs)
    def gui_update_configs(self):
        tree = self.configs_treestore # Name, show in Mistika, is folder
        iters = self.iters
        items = self.files['Configs']
        for item_path in sorted(items):
            item = items[item_path]
            dir_name = os.path.dirname(item_path)
            base_name = os.path.basename(item_path)
            if not dir_name in iters:
                iters[dir_name] = None
            if item['isdir']:
                iters[item_path] = tree.append(iters[dir_name], [base_name, False, True, item_path])
            else:
                tree.append(iters[dir_name], [base_name, item['Active'], False, item_path])

    def init_links_window(self):
        tree        = self.links_tree      = gtk.TreeView()
        treestore   = self.links_treestore = gtk.TreeStore(str, str) # Name, url
        tree_filter = self.links_filter    = treestore.filter_new();
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn('', cell, text=0)
        column.set_resizable(True)
        column.set_expand(True)
        tree.append_column(column)
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn('URL', cell, text=1)
        column.set_resizable(True)
        column.set_expand(True)
        cell.set_property('foreground', '#0000ff')
        cell.set_property('underline', 'single')
        tree.append_column(column)
        tree_filter.set_visible_func(self.FilterTree, (self.filterEntry, tree));
        tree.set_model(tree_filter)
        tree.expand_all()
        tree.connect('row-activated', self.on_links_run, tree)
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(tree)
        t = threading.Thread(target=self.io_populate_links)
        self.threads.append(t)
        t.setDaemon(True)
        t.start()
        return scrolled_window

    def add_link(self, xmlobject):
        link_dict = {}
        for child in xmlobject:
            if child.tag == 'alias':
                link_dict['alias'] = child.text
            elif child.tag == 'url':
                link_dict['url'] =  child.text
            elif child.tag == 'link':
                link_dict['children'] = add_link(child)
        return link_dict

    def io_populate_links(self):
        file_type = 'Links'
        if not file_type in self.files:
            self.files[file_type] = {}
        files = self.files[file_type]
        for root, dirs, filenames in os.walk(os.path.join(self.config['app_folder'], file_type)):
            for name in dirs:
                path = os.path.join(root, name)
                files[path] = {'isdir' : True}
            for name in filenames:
                if name.endswith('.xml'):
                    path = os.path.join(root, name)
                    files[path] = {'isdir' : False}
                    tree = ET.parse(path)
                    treeroot = tree.getroot()
                    for child in treeroot:
                        if child.tag == 'link':
                            if not 'children' in files[path]:
                                files[path]['children'] = []
                            files[path]['children'].append(self.add_link(child))
                        else:
                            files[path][child.tag] = child.text
        gobject.idle_add(self.gui_update_links)

    def gui_update_links(self):
        tree = self.links_treestore # Name, show in Mistika, is folder
        iters = self.iters
        items = self.files['Links']
        for item_path in sorted(items):
            item = items[item_path]
            dir_name = os.path.dirname(item_path)
            base_name = os.path.basename(item_path)
            if not dir_name in iters:
                iters[dir_name] = None
            alias = base_name
            url = ''
            try:
                alias = item['alias']
                url = item['url']
            except KeyError:
                pass
            if 'children' in item:
                iters[item_path] = tree.append(iters[dir_name], [alias, url])
                for child in item['children']:
                    tree.append(iters[item_path], [child['alias'], child['url']])
            else:
                tree.append(iters[dir_name], [alias, url])

    def files_update(self):
        if not hasattr(self, 'files'):
            self.files = {}
        files_ref = self.files
        file_types = {
            'Tools': {
                'defaults': {
                    'Autorun' : 'Never',
                    'Show in Mistika' : False,
                }
            },
            'Afterscripts': {
                'defaults': {
                    'Show in Mistika' : False,
                }
            },
            'Stacks': {
                'required files' : [
                    'config.json'
                ],
                'defaults': {
                    'Dependencies installed' : True,
                }
            },
            'Configs': {
                'required files' : [
                    'config.json'
                ],
                'defaults': {
                    'Active' : False,
                }
            },
            'Links': {
                'defaults': {
                }
            }
        }
        for file_type, file_type_meta in file_types.iteritems():
            file_type_defaults = file_type_meta['defaults']
            if not file_type in files_ref:
                files_ref[file_type] = {}
            for root, dirs, files in os.walk(os.path.join(self.config['app_folder'], file_type)):
                for name in dirs:
                    path = os.path.join(root, name)
                    if not path in files_ref[file_type]:
                        if 'required files' in file_type_meta:
                            files_ref[file_type][path] = {'isdir' : False}
                            for required_file in file_type_meta['required files']:
                                if not required_file in os.listdir(path):
                                    files_ref[file_type][path] = {'isdir' : True}
                            if files_ref[file_type][path]['isdir'] == False:
                                file_md5 = md5(path)
                                files_ref[file_type][path]['md5'] = file_md5
                                if file_type == 'Configs':
                                    print path
                                    print os.path.join(path, 'config.json')
                                    file_config = json.loads(open(os.path.join(path, 'config.json')).read())
                                    detected = True
                                    if file_config['manage']:
                                        try:
                                            if subprocess.call([os.path.join(path, 'manage'), 'detect']) > 0:
                                                detected = False
                                        except OSError as e:
                                            detected = False
                                    if 'links' in file_config:
                                        for link_target, link in file_config['links'].iteritems():
                                            if not hyperspeed.manage.detect(link_target, link):
                                                detected = False
                                    files_ref[file_type][path]['Active'] = detected
                            continue
                        else:
                            files_ref[file_type][path] = {'isdir' : True}
                for name in files:
                    if 'required files' in file_type_meta:
                        continue
                    path = os.path.join(root, name)
                    file_md5 = md5(path)
                    if not path in files_ref[file_type] or file_md5 != files_ref[file_type][path]['md5']:
                        files_ref[file_type][path] = {
                            'isdir' : False,
                            'md5' : file_md5
                        }
            for path in files_ref[file_type].keys():
                if not os.path.exists(path):
                    del files_ref[file_type][path]
                    continue
                if not files_ref[file_type][path]['isdir']:
                    for key in file_type_defaults:
                        if not key in files_ref[file_type][path]:
                            files_ref[file_type][path][key] = file_type_defaults[key]
        self.config_rw(write=True)

    def error(self, msg):
        print msg
    def config_rw(self, write=False):
        config_defaults = {
            'app_folder' : os.path.dirname(os.path.realpath(sys.argv[0]))
        }
        try:
            self.config
        except AttributeError:
            self.config = {}
        config_path = os.path.join(CONFIG_FOLDER, CONFIG_FILE) 
        try:
            stored_config = json.loads(open(config_path).read())
        except IOError as e:
            stored_config = {}
        if write:
            if stored_config != self.config:
                if not os.path.isdir(CONFIG_FOLDER):
                    os.makedirs(CONFIG_FOLDER)
                try:
                    open(config_path, 'w').write(json.dumps(self.config, sort_keys=True, indent=4, separators=(',', ': ')))
                    stored_config = self.config
                except IOError as e:
                    error('Could not write config file')
        else:
            if stored_config != self.config:
                self.config = stored_config
        for config_item in config_defaults:
            if not config_item in self.config.keys():
                self.config[config_item] = config_defaults[config_item]
                self.config_rw(write=True)

    def on_quit(self, widget):
        print 'Closed by: ' + repr(widget)
        gtk.main_quit()

    def on_filter(self, widget, event):
        #print widget.get_text()
        self.toolsFilter.refilter();
        self.afterscriptsFilter.refilter();
        self.sharedFilter.refilter();
        self.linksFilter.refilter();
        #self.toolsTreestore.foreach(self.row_match, widget.get_text())

    def row_match(self, model, path, iter, data):
        name = self.toolsTreestore[path][0]
        match = True
        for word in data.split():
            if not word in name:
                match = False
        if match:
            self.toolsTreestore[path][0]
        # if self.myView.row_expanded(path):
        #    self.expandedLines.append(path)
        #visible_func(model, iter, user_data):

    def FilterTree(self, model, iter, user_data, seek_up=True, seek_down=True, filter=False):
        widget, tree = user_data
        tree.expand_all()
        if not filter:
            filter = widget.get_text().lower()
        row = model.get_value(iter, 0)
        if row == None:
            return False
        name = model.get_value(iter, 0).lower()
        parent = model.iter_parent(iter)
        has_child = model.iter_has_child(iter)
            # print name + ' has child'
            # return True
        #print 'Seeking ' + name
        for word in filter.split():
            if word in name:
                continue
            relative_match = False
            if seek_down and has_child:
                #print 'Seeking children'
                for n in range(model.iter_n_children(iter)):
                    if self.FilterTree(model, model.iter_nth_child(iter, n), user_data, seek_up=False, filter=word):
                        #print 'Child matches!'
                        relative_match = True
            if seek_up and parent != None:
                #print 'Seeking parents'
                if self.FilterTree(model, parent, user_data, seek_down=False, filter=word):
                    #print 'Parent matches!'
                    relative_match = True
            if relative_match:
                continue
            return False

        return True

    def hide_if_parent(self, column, cell, model, iter):
        has_child = model.iter_has_child(iter)
        is_folder = model[iter][2]
        if is_folder:
            cell.set_property('visible', False)
            #print model[iter][0] + ' ' + model[model.iter_children(iter)][0]
        else:
            cell.set_property('visible', True)

    def on_tools_toggle(self, cellrenderertoggle, path, treeview, *ignore):
        treestore = treeview.get_model()
        try: # If there is a filter in the middle
            treestore = treestore.get_model()
        except AttributeError:
            pass
        new_config = ''
        alias = treestore[path][0]
        alias = alias.replace(' ', '_')
        activated = not treestore[path][1]
        file_path = treestore[path][4]
        stored = False
        for line in open(mistika.tools_path):
            line_alias, line_path = line.strip().split(' ', 1)
            if file_path == line_path:
                if activated:
                    new_config += '%s %s\n' % (alias, file_path)
                    stored = True
                else:
                    continue
            elif not os.path.exists(line_path):
                continue
            new_config += line
        if activated and not stored:
            new_config += '%s %s\n' % (alias, file_path)
        print '\nNew config:'
        print new_config
        open(mistika.tools_path, 'w').write(new_config)
        treestore[path][1] = activated

    def on_autorun_set(self, widget, path, text):
        temp_config_path = '/tmp/mistika-hyperspeed-crontab'
        treestore = self.tools_treestore
        alias = treestore[path][0]
        autorun = text # Never, Hourly, Daily, Weekly, Monthly
        file_path = treestore[path][4]
        stored = False
        new_config = ''
        cron_time = AUTORUN_TIMES[autorun]
        if cron_time:
            cron_line = '%s %s\n' % (cron_time, file_path)
        else:
            cron_line = ''
        try:
            for line in get_crontab_lines():
                fields = line.split(' ', 5)
                if len(fields) == 6:
                    minute, hour, date, month, weekday, cmd = fields
                    if cmd == file_path:
                        continue
                new_config += line + '\n'
            if cron_line != '':
                new_config += cron_line
        except:
            raise
        print '\nNew crontab:'
        print new_config
        open(temp_config_path, 'w').write(new_config)
        subprocess.Popen(['crontab', temp_config_path])
        print new_config
        treestore[path][3] = text

    def on_editing_started(self, cell, editable, path):
        self.comboEditable = editable
        
    def on_combo_changed(self, cell, path, newiter):
      e = gtk.gdk.Event(gtk.gdk.FOCUS_CHANGE)
      e.window = self.window
      e.send_event = True
      e.in_ = False
      self.comboEditable.emit('focus-out-event', e)

    def on_afterscripts_toggle(self, cellrenderertoggle, path, treeview, *ignore):
        treestore = treeview.get_model()
        try: # If there is a filter in the middle
            treestore = treestore.get_model()
        except AttributeError:
            pass
        alias = treestore[path][0]
        activated = not treestore[path][1]
        file_path = treestore[path][3]
        linked = False
        for link in os.listdir(mistika.scripts_folder):
            link_path = os.path.join(mistika.scripts_folder, link)
            if os.path.realpath(link_path) == os.path.realpath(file_path):
                if activated:
                    linked = True
        if activated and not linked:
            link_path = os.path.join(mistika.scripts_folder, alias)
            if os.path.islink(link_path):
                os.remove(link_path)
            os.symlink(file_path, link_path)
        stored = False
        new_config = 'None\n'
        for line in open(mistika.afterscripts_path):
            line_alias = line.strip()
            line_path = os.path.join(mistika.scripts_folder, line_alias)
            if alias == line_alias:
                if activated:
                    stored = True
                else:
                    continue
            elif not os.path.exists(line_path):
                continue
            new_config += line
        if activated and not stored:
            new_config += '%s\n' % alias
        print '\nNew config:'
        print new_config
        open(mistika.afterscripts_path, 'w').write(new_config)
        treestore[path][1] = activated
        #print name + ' ' + repr(state)

    def on_stacks_toggle(self, cellrenderertoggle, path, *ignore):
        print 'Not yet implemented'
        pass

    def on_configs_toggle(self, cellrenderertoggle, treepath, *ignore):
        tree = self.configs_treestore
        name = tree[treepath][0]
        state = not tree[treepath][1]
        path = tree[treepath][3]
        f_item = self.files['Configs'][path]
        print repr(f_item)
        links = f_item['links']
        if state: # Install
            for link_target, link in links.iteritems():
                state = state and hyperspeed.manage.install(link_target, link)
        else: # remove
            for link_target, link in links.iteritems():
                hyperspeed.manage.remove(link_target, link)
        tree[treepath][1] = state

    def on_tools_run(self, treeview, path, view_column, *ignore):

        file_path = self.tools_treestore[path][4]
        print file_path
        try:
            subprocess.Popen(['konsole', '-e', os.path.join(self.config['app_folder'], 'res/scripts/bash_wrapper.sh'), file_path])
            return
        except OSError as e:
            try:
                subprocess.Popen(['xterm', '-e', os.path.join(self.config['app_folder'], 'res/scripts/bash_wrapper.sh'), file_path])
                return
            except OSError as e:
                try:
                    subprocess.Popen([file_path])
                    return
                except:
                    pass
        print 'Failed to execute %s' % file_path

    def on_afterscripts_run(self, treeview, path, view_column, *ignore):
        print 'Not yet implemented'

    def on_links_run(self, treeview, path, view_column, *ignore):
        treestore = treeview.get_model()
        try: # If there is a filter in the middle
            treestore = treestore.get_model()
        except AttributeError:
            pass
        url = treestore[path][1]
        print url
        webbrowser.get('firefox').open(url)


os.environ['LC_CTYPE'] = 'en_US.utf8'
os.environ['LC_ALL'] = 'en_US.utf8'
gobject.threads_init()
PyApp()
gtk.main()