#!/usr/bin/python

# ZetCode PyGTK tutorial 
#
# This is a more complicated layout
# example
#
# author: jan bodnar
# website: zetcode.com 
# last edited: February 2009

import gtk
import sys


class PyApp(gtk.Window):

    def __init__(self):
        super(PyApp, self).__init__()

        self.set_title("Hyperspeed")
        self.set_size_request(800, 800)
        self.set_border_width(20)
        self.set_position(gtk.WIN_POS_CENTER)
        self.set_resizable(False) # Because resizing crashes the app on Mac

        vbox = gtk.VBox(False, 10)


        #title = gtk.Label('<span size="38000">Hyperspeed</span>')
        #title.set_use_markup(gtk.TRUE)

        #halign = gtk.Alignment(0, 0, 0, 0)
        #halign.add(title)
        toolbarBox = gtk.HBox(False, 10)

        filterBox = gtk.HBox(False, 10)
        filterLabel = gtk.Label('Search: ')
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

        #vbox.pack_start(gtk.Label('Tools'), False, False, 5)
        self.toolsTree = gtk.TreeView()
        cell = gtk.CellRendererText()
        toolsTreeNameColumn = gtk.TreeViewColumn('Tools', cell, text=0)
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
        #toolsTreeInMistikaColumn.set_cell_data_func(cell3, self.checkbox_toggle)
        toolsTreeAutorunColumn.set_expand(False)
        self.toolsTree.append_column(toolsTreeAutorunColumn)
        cell2 = gtk.CellRendererToggle()
        cell2.connect("toggled", self.on_tools_toggle, self.toolsTree)
        toolsTreeInMistikaColumn = gtk.TreeViewColumn("Show in Mistika", cell2, active=1)
        toolsTreeInMistikaColumn.set_cell_data_func(cell2, self.checkbox_toggle)
        toolsTreeInMistikaColumn.set_expand(False)
        toolsTreeInMistikaColumn.set_resizable(True)
        self.toolsTree.append_column(toolsTreeInMistikaColumn)
        self.toolsTreestore = gtk.TreeStore(str, bool, bool, str) # Name, show in Mistika, is folder, autorun
        toolsTreestore = self.toolsTreestore
        it = toolsTreestore.append(None, ["Conform", False, True, ''])
        toolsTreestore.append(it, ["tcSwap.py", True, False, ''])
        toolsTreestore.append(it, ["empConform.py", False, False, ''])
        it = toolsTreestore.append(None, ["VFX", False, True, ''])
        toolsTreestore.append(it, ["some vfx tool", False, False, ''])
        itit = toolsTreestore.append(it, ["folder", False, True, ''])
        toolsTreestore.append(itit, ["bar.py", False, False, ''])
        toolsTreestore.append(None, ["font_parse.py", False, False, 'Hourly'])

        toolsFilter = toolsTreestore.filter_new();
        self.toolsFilter = toolsFilter
        toolsFilter.set_visible_func(self.FilterTree, (filterEntry, self.toolsTree));
        self.toolsTree.set_model(toolsFilter)
        self.toolsTree.expand_all()

        vbox.pack_start(self.toolsTree)

        #vbox.pack_start(gtk.Label('Afterscripts'), False, False, 5)
        self.afterscriptsTree = gtk.TreeView()
        cell = gtk.CellRendererText()
        afterscriptsTreeNameColumn = gtk.TreeViewColumn('Afterscripts', cell, text=0)
        afterscriptsTreeNameColumn.set_resizable(True)
        afterscriptsTreeNameColumn.set_expand(True)
        self.afterscriptsTree.append_column(afterscriptsTreeNameColumn)
        cell2 = gtk.CellRendererToggle()
        cell2.connect("toggled", self.on_afterscripts_toggle, self.afterscriptsTree)
        afterscriptsTreeInMistikaColumn = gtk.TreeViewColumn("Show in Mistika", cell2, active=1)
        afterscriptsTreeInMistikaColumn.set_cell_data_func(cell2, self.checkbox_toggle)
        afterscriptsTreeInMistikaColumn.set_expand(False)
        self.afterscriptsTree.append_column(afterscriptsTreeInMistikaColumn)

        self.afterscriptsTreestore = gtk.TreeStore(str, bool, bool) # Name, show in Mistika, is folder
        afterscriptsTreestore = self.afterscriptsTreestore
        it = afterscriptsTreestore.append(None, ["Conform", False, True])
        afterscriptsTreestore.append(it, ["tcSwap.py", True, False])
        afterscriptsTreestore.append(it, ["empConform.py", False, False])

        it = afterscriptsTreestore.append(None, ["VFX", False, True])
        afterscriptsTreestore.append(it, ["some vfx tool", False, False])
        itit = afterscriptsTreestore.append(it, ["folder", False, True])
        afterscriptsTreestore.append(itit, ["bar.py", False, False])

        afterscriptsFilter = afterscriptsTreestore.filter_new();
        self.afterscriptsFilter = afterscriptsFilter
        afterscriptsFilter.set_visible_func(self.FilterTree, (filterEntry, self.afterscriptsTree));
        self.afterscriptsTree.set_model(afterscriptsFilter)
        self.afterscriptsTree.expand_all()

        vbox.pack_start(self.afterscriptsTree)

        #vbox.pack_start(gtk.Label('Afterscripts'), False, False, 5)
        self.sharedTree = gtk.TreeView()
        cell = gtk.CellRendererText()
        sharedTreeNameColumn = gtk.TreeViewColumn('Shared items', cell, text=0)
        sharedTreeNameColumn.set_resizable(True)
        sharedTreeNameColumn.set_expand(True)
        self.sharedTree.append_column(sharedTreeNameColumn)
        cell2 = gtk.CellRendererToggle()
        cell2.connect("toggled", self.on_shared_toggle, self.sharedTree)
        sharedTreeInMistikaColumn = gtk.TreeViewColumn("Active", cell2, active=1)
        sharedTreeInMistikaColumn.set_cell_data_func(cell2, self.checkbox_toggle)
        sharedTreeInMistikaColumn.set_expand(False)
        self.sharedTree.append_column(sharedTreeInMistikaColumn)
        self.sharedTreestore = gtk.TreeStore(str, bool, bool) # Name, active, is folder
        sharedTreestore = self.sharedTreestore
        it = sharedTreestore.append(None, ["Shared items", False, True])
        sharedTreestore.append(it, ["hotKeys.cfg", False, False])
        sharedFilter = sharedTreestore.filter_new();
        self.sharedFilter = sharedFilter
        sharedFilter.set_visible_func(self.FilterTree, (filterEntry, self.sharedTree));
        self.sharedTree.set_model(sharedFilter)
        self.sharedTree.expand_all()

        vbox.pack_start(self.sharedTree)

        #vbox.pack_start(gtk.Label('Afterscripts'), False, False, 5)
        self.linksTree = gtk.TreeView()
        cell = gtk.CellRendererText()
        linksTreeNameColumn = gtk.TreeViewColumn('Links', cell, text=0)
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

        vbox.pack_start(self.linksTree)

        vbox.pack_start(gtk.Label('Afterscript queue'), False, False, 5)
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
        #cell2.connect("toggled", self.on_queue_toggle, self.queueTree)

        self.queueTreestore = gtk.TreeStore(str, str, str, str, str)
        queueTreestore = self.queueTreestore
        it = queueTreestore.append(None, ["RnD", 'test_0001', 'Running on apollo2', 'gaia', '08:27'])

        self.queueTree.set_model(queueTreestore)
        self.queueTree.expand_all()

        vbox.pack_start(self.queueTree)


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

    def checkbox_toggle(self, column, cell, model, iter):
        has_child = model.iter_has_child(iter)
        is_folder = model[iter][2]
        if has_child:
            cell.set_property('visible', False)
        else:
            cell.set_property('visible', True)

    def on_tools_toggle(self, cellrenderertoggle, path, *ignore):
        self.toolsTreestore[path][1] = not self.toolsTreestore[path][1]
        print self.toolsTreestore[path][0]


    def on_afterscripts_toggle(self, cellrenderertoggle, path, *ignore):
        name = self.afterscriptsTreestore[path][0]
        state = not self.afterscriptsTreestore[path][1]
        self.afterscriptsTreestore[path][1] = state
        print name + ' ' + repr(state)

    def on_shared_toggle(self, cellrenderertoggle, path, *ignore):
        name = self.sharedTreestore[path][0]
        state = not self.sharedTreestore[path][1]
        self.sharedTreestore[path][1] = state
        print name + ' ' + repr(state)


PyApp()
gtk.main()