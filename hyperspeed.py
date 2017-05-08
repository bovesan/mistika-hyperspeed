#!/usr/bin/python
# -*- coding: utf-8 -*-

import gtk
import json
import os
import sys
import platform
import subprocess

CONFIG_FOLDER = '/home/mistika/.mistika-hyperspeed/'
CONFIG_FILE = 'hyperspeed.cfg'

class PyApp(gtk.Window):

    def __init__(self):
        super(PyApp, self).__init__()
        self.config_rw()
        self.files_update()
        screen = self.get_screen()
        self.set_title("Hyperspeed")
        self.set_size_request(800, screen.get_height()-200)
        self.set_border_width(20)
        self.set_position(gtk.WIN_POS_CENTER)
        if 'darwin' in platform.system().lower():
            self.set_resizable(False) # Because resizing crashes the app on Mac

        vbox = gtk.VBox(False, 10)


        #title = gtk.Label('<span size="38000">Hyperspeed</span>')
        #title.set_use_markup(gtk.TRUE)

        #halign = gtk.Alignment(0, 0, 0, 0)
        #halign.add(title)
        self.iters = {}
        toolbarBox = gtk.HBox(False, 10)

        filterBox = gtk.HBox(False, 10)
        filterLabel = gtk.Label('Filter: ')
        filterBox.pack_start(filterLabel, False, False,)
        filterEntry = gtk.Entry()
        filterEntry.add_events(gtk.gdk.KEY_RELEASE_MASK)
        filterEntry.connect("activate", self.on_filter)
        filterEntry.connect("key-release-event", self.on_filter)
        filterEntry.grab_focus()
        self.filterEntry = filterEntry
        filterBox.pack_start(filterEntry, False, False)
        toolbarBox.pack_start(filterBox, False, False)

        versionBox = gtk.HBox(False, 2)
        versionStr = '<span color="#11cc11">Up to date.</span> Updated 27 Nov 2016.'
        versionLabel = gtk.Label(versionStr)
        versionLabel.set_use_markup(gtk.TRUE)
        versionBox.pack_start(versionLabel, False, False, 5)
        updateButton = gtk.Button('Update')
        #versionBox.pack_start(updateButton, False, False, 5)
        toolbarBox.pack_end(versionBox, False, False)

        vbox.pack_start(toolbarBox, False, False, 10)

        notebook = gtk.Notebook()
        #vbox.pack_start(gtk.Label('Tools'), False, False, 5)
        self.toolsTree = gtk.TreeView()
        cell = gtk.CellRendererText()
        toolsTreeNameColumn = gtk.TreeViewColumn('', cell, text=0)
        toolsTreeNameColumn.set_resizable(True)
        toolsTreeNameColumn.set_expand(True)
        self.toolsTree.append_column(toolsTreeNameColumn)
        autorunStates = gtk.ListStore(str)
        autorunStates.append(['Never'])
        autorunStates.append(['On startup'])
        autorunStates.append(['Hourly'])
        autorunStates.append(['Daily'])
        autorunStates.append(['Weekly'])
        autorunStates.append(['Monthly'])
        cell3 = gtk.CellRendererCombo()
        #cell3.connect("toggled", self.on_tools_toggle, self.toolsTree)
        cell3.set_property("editable", True)
        cell3.set_property("has-entry", False)
        cell3.set_property("text-column", 0)
        cell3.set_property("model", autorunStates)
        cell3.connect("edited", self.on_combo_changed)
        toolsTreeAutorunColumn = gtk.TreeViewColumn("Autorun", cell3, text=3)
        toolsTreeAutorunColumn.set_resizable(True)
        #toolsTreeInMistikaColumn.set_cell_data_func(cell3, self.hide_if_parent)
        toolsTreeAutorunColumn.set_expand(False)
        toolsTreeAutorunColumn.set_cell_data_func(cell3, self.hide_if_parent)
        self.toolsTree.append_column(toolsTreeAutorunColumn)
        cell2 = gtk.CellRendererToggle()
        cell2.connect("toggled", self.on_tools_toggle, self.toolsTree)
        toolsTreeInMistikaColumn = gtk.TreeViewColumn("Show in Mistika", cell2, active=1)
        toolsTreeInMistikaColumn.set_cell_data_func(cell2, self.hide_if_parent)
        toolsTreeInMistikaColumn.set_expand(False)
        toolsTreeInMistikaColumn.set_resizable(True)
        self.toolsTree.append_column(toolsTreeInMistikaColumn)
        self.toolsTreestore = gtk.TreeStore(str, bool, bool, str, str) # Name, show in Mistika, is folder, autorun, file_path
        toolsTreestore = self.toolsTreestore
        self.gui_update_tools()

        toolsFilter = toolsTreestore.filter_new();
        self.toolsFilter = toolsFilter
        toolsFilter.set_visible_func(self.FilterTree, (filterEntry, self.toolsTree));
        self.toolsTree.set_model(toolsFilter)
        self.toolsTree.expand_all()
        self.toolsTree.connect('row-activated', self.on_tools_run, self.toolsTree)

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(self.toolsTree)
        #vbox.pack_start(scrolled_window)
        notebook.append_page(scrolled_window, gtk.Label('Tools'))

        #vbox.pack_start(gtk.Label('Afterscripts'), False, False, 5)
        self.afterscriptsTree = gtk.TreeView()
        cell = gtk.CellRendererText()
        afterscriptsTreeNameColumn = gtk.TreeViewColumn('', cell, text=0)
        afterscriptsTreeNameColumn.set_resizable(True)
        afterscriptsTreeNameColumn.set_expand(True)
        self.afterscriptsTree.append_column(afterscriptsTreeNameColumn)
        cell2 = gtk.CellRendererToggle()
        cell2.connect("toggled", self.on_afterscripts_toggle, self.afterscriptsTree)
        afterscriptsTreeInMistikaColumn = gtk.TreeViewColumn("Show in Mistika", cell2, active=1)
        afterscriptsTreeInMistikaColumn.set_cell_data_func(cell2, self.hide_if_parent)
        afterscriptsTreeInMistikaColumn.set_expand(False)
        self.afterscriptsTree.append_column(afterscriptsTreeInMistikaColumn)

        self.afterscriptsTreestore = gtk.TreeStore(str, bool, bool) # Name, show in Mistika, is folder
        afterscriptsFilter = self.afterscriptsTreestore.filter_new();
        self.gui_update_afterscripts()

        self.afterscriptsFilter = afterscriptsFilter
        afterscriptsFilter.set_visible_func(self.FilterTree, (filterEntry, self.afterscriptsTree));
        self.afterscriptsTree.set_model(afterscriptsFilter)
        self.afterscriptsTree.expand_all()

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(self.afterscriptsTree)
        #vbox.pack_start(scrolled_window)
        notebook.append_page(scrolled_window, gtk.Label('Afterscripts'))

        #vbox.pack_start(gtk.Label('Afterscripts'), False, False, 5)
        self.sharedTree = gtk.TreeView()
        cell = gtk.CellRendererText()
        sharedTreeNameColumn = gtk.TreeViewColumn('', cell, text=0)
        sharedTreeNameColumn.set_resizable(True)
        sharedTreeNameColumn.set_expand(True)
        self.sharedTree.append_column(sharedTreeNameColumn)
        cell2 = gtk.CellRendererToggle()
        cell2.connect("toggled", self.on_shared_toggle, self.sharedTree)
        sharedTreeInMistikaColumn = gtk.TreeViewColumn("Active", cell2, active=1)
        sharedTreeInMistikaColumn.set_cell_data_func(cell2, self.hide_if_parent)
        sharedTreeInMistikaColumn.set_expand(False)
        self.sharedTree.append_column(sharedTreeInMistikaColumn)
        self.sharedTreestore = gtk.TreeStore(str, bool, bool) # Name, active, is folder
        self.gui_update_configs()
        sharedFilter = self.sharedTreestore.filter_new();
        self.sharedFilter = sharedFilter
        sharedFilter.set_visible_func(self.FilterTree, (filterEntry, self.sharedTree));
        self.sharedTree.set_model(sharedFilter)
        self.sharedTree.expand_all()

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(self.sharedTree)
        #vbox.pack_start(scrolled_window)
        notebook.append_page(scrolled_window, gtk.Label('Shared items'))

        #vbox.pack_start(gtk.Label('Afterscripts'), False, False, 5)
        self.linksTree = gtk.TreeView()
        cell = gtk.CellRendererText()
        linksTreeNameColumn = gtk.TreeViewColumn('', cell, text=0)
        linksTreeNameColumn.set_resizable(True)
        linksTreeNameColumn.set_expand(True)
        self.linksTree.append_column(linksTreeNameColumn)
        cell2 = gtk.CellRendererText()
        linksTreeUrlColumn = gtk.TreeViewColumn('URL', cell2, text=1, foreground=2)
        linksTreeUrlColumn.set_resizable(True)
        linksTreeUrlColumn.set_expand(True)
        #linksTreeUrlColumn.add_attribute(cell2, 'underline-set', 3)
        #linksTreeUrlColumn.set_attribute(cell2, foreground='blue')
        self.linksTree.append_column(linksTreeUrlColumn)
        self.linksTreestore = gtk.TreeStore(str, str, str) # Name, url, color, underline
        linksTreestore = self.linksTreestore
        it = linksTreestore.append(None, ["sgo.es", '', 'black'])
        linksTreestore.append(it, ["Support home", 'http://support.sgo.es/support/home', '#9999ff'])

        it = linksTreestore.append(None, ["bovesan.com", '', 'black'])
        linksTreestore.append(it, ["Comp3D builder", 'https://bovesan.com/cb', '#9999ff'])
        linksTreestore.append(it, ["Online Reel Browser", 'https://bovesan.com/orb', '#9999ff'])
        linksFilter = linksTreestore.filter_new();
        self.linksFilter = linksFilter
        linksFilter.set_visible_func(self.FilterTree, (filterEntry, self.linksTree));
        self.linksTree.set_model(linksFilter)
        self.linksTree.expand_all()

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(self.linksTree)
        #vbox.pack_start(scrolled_window)
        notebook.append_page(scrolled_window, gtk.Label('Web links'))
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
        it = queueTreestore.append(None, ["Private (6)", '', '', '', '', 0, ''])
        queueTreestore.append(it, ["RnD", 'test_0001', 'Rendering on gaia', 'gaia', '08:27', 20, '20%'])
        queueTreestore.append(it, ["RnD", 'test_0001', 'Queued', 'gaia', '08:27', 0, ''])
        queueTreestore.append(it, ["RnD", 'test_0001', 'Queued', 'gaia', '08:27', 0, ''])
        queueTreestore.append(it, ["RnD", 'test_0001', 'Queued', 'gaia', '08:27', 0, ''])
        queueTreestore.append(it, ["RnD", 'test_0001', 'Queued', 'gaia', '08:27', 0, ''])
        queueTreestore.append(it, ["RnD", 'test_0001', 'Queued', 'gaia', '08:27', 0, ''])
        it = queueTreestore.append(None, ["Public (2)", '', '', '', '', 0, ''])
        queueTreestore.append(it, ["Mastering", 'film01', 'Queued', 'apollo2', '08:27', 0, ''])
        queueTreestore.append(it, ["Mastering", 'film02', 'Queued', 'apollo2', '08:27', 0, ''])
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
        queueTreestore.append(None, ["RnD", 'test_0001', 'Running on apollo2', 'gaia', '08:27'])
        queueTreestore.append(None, ["RnD", 'test_0001', 'Running on apollo2', 'gaia', '08:27'])
        queueTreestore.append(None, ["RnD", 'test_0001', 'Running on apollo2', 'gaia', '08:27'])
        queueTreestore.append(None, ["RnD", 'test_0001', 'Running on apollo2', 'apollo2', '08:27'])
        queueTreestore.append(None, ["RnD", 'test_0001', 'Running on apollo2', 'apollo1', '08:27'])
        queueTreestore.append(None, ["RnD", 'test_0001', 'Running on apollo2', 'gaia', '08:27'])
        queueTreestore.append(None, ["RnD", 'test_0001', 'Running on apollo2', 'gaia', '08:27'])
        queueTreestore.append(None, ["RnD", 'test_0001', 'Queued', 'gaia', '08:27'])
        queueTreestore.append(None, ["RnD", 'test_0001', 'Queued', 'gaia', '08:27'])
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
        #self.present()
    def gui_update_tools(self):
        tree_store = self.toolsTreestore # Name, show in Mistika, is folder, autorun, file path
        iters = self.iters
        items = self.config['files']['Tools']
        for item_path in sorted(items):
            item = items[item_path]
            dir_name = os.path.dirname(item_path)
            base_name = os.path.basename(item_path)
            print item_path,
            print dir_name
            if not dir_name in iters:
                iters[dir_name] = None
            if item['isdir']:
                iters[item_path] = tree_store.append(iters[dir_name], [base_name, False, True, '', item_path])
            else:
                tree_store.append(iters[dir_name], [base_name, item['Show in Mistika'], True, item['Autorun'], item_path])

    def gui_update_afterscripts(self):
        tree_store = self.afterscriptsTreestore # Name, show in Mistika, is folder
        iters = self.iters
        items = self.config['files']['Afterscripts']
        for item_path in sorted(items):
            item = items[item_path]
            dir_name = os.path.dirname(item_path)
            base_name = os.path.basename(item_path)
            print item_path,
            print dir_name
            if not dir_name in iters:
                iters[dir_name] = None
            if item['isdir']:
                iters[item_path] = tree_store.append(iters[dir_name], [base_name, False, True])
            else:
                tree_store.append(iters[dir_name], [base_name, item['Show in Mistika'], True])

    def gui_update_configs(self):
        tree_store = self.sharedTreestore # Name, show in Mistika, is folder
        iters = self.iters
        items = self.config['files']['Configurations']
        for item_path in sorted(items):
            item = items[item_path]
            dir_name = os.path.dirname(item_path)
            base_name = os.path.basename(item_path)
            print item_path,
            print dir_name
            if not dir_name in iters:
                iters[dir_name] = None
            if item['isdir']:
                iters[item_path] = tree_store.append(iters[dir_name], [base_name, False, True])
            else:
                tree_store.append(iters[dir_name], [base_name, item['Active'], True])


    def files_update(self):
        if not 'files' in self.config:
            self.config['files'] = {}
        files_ref = self.config['files']
        file_types = {
            'Tools': {
                'Autorun' : 'Never',
                'Show in Mistika' : False,
            },
            'Afterscripts': {
                'Show in Mistika' : False,
            },
            'Configurations': {
                'Active' : False,
            },
            'Links': {
            }
        }
        for file_type, file_type_defaults in file_types.iteritems():
            if not file_type in files_ref:
                files_ref[file_type] = {}
            for root, dirs, files in os.walk(os.path.join(self.config['app_folder'], file_type)):
                for name in dirs:
                    path = os.path.join(root, name)
                    if not path in files_ref[file_type]:
                        files_ref[file_type][path] = {'isdir' : True}
                for name in files:
                    path = os.path.join(root, name)
                    if not path in files_ref[file_type]:
                        files_ref[file_type][path] = {'isdir' : False}
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

    def on_combo_changed(self, widget, path, text):
        self.toolsTreestore[path][3] = text

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
        #is_folder = model[iter][2]
        if has_child:
            cell.set_property('visible', False)
            #print model[iter][0] + ' ' + model[model.iter_children(iter)][0]
        else:
            cell.set_property('visible', True)

    def on_tools_toggle(self, cellrenderertoggle, path, *ignore):
        self.toolsTreestore[path][1] = not self.toolsTreestore[path][1]
        #print self.toolsTreestore[path][0]


    def on_afterscripts_toggle(self, cellrenderertoggle, path, *ignore):
        name = self.afterscriptsTreestore[path][0]
        state = not self.afterscriptsTreestore[path][1]
        self.afterscriptsTreestore[path][1] = state
        #print name + ' ' + repr(state)

    def on_shared_toggle(self, cellrenderertoggle, path, *ignore):
        name = self.sharedTreestore[path][0]
        state = not self.sharedTreestore[path][1]
        self.sharedTreestore[path][1] = state
        #print name + ' ' + repr(state)
    def on_tools_run(self, treeview, path, view_column, *ignore):

        file_path = self.toolsTreestore[path][4]
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


PyApp()
gtk.main()