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
        versionBox = gtk.HBox(False, 10)

        versionStr = '<span color="#11cc11">Up to date.</span> Updated 27 Nov 2016.'
        versionLabel = gtk.Label(versionStr)
        versionLabel.set_use_markup(gtk.TRUE)
        versionBox.pack_start(versionLabel, False, False, 5)
        updateButton = gtk.Button('Update')
        #versionBox.pack_start(updateButton, False, False, 5)
        vbox.pack_start(versionBox, False, False)

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
        vbox.pack_start(filterBox, False, False, 10)


        self.toolsTree = gtk.TreeView()
        cell = gtk.CellRendererText()
        toolsTreeNameColumn = gtk.TreeViewColumn('Name', cell, text=0)
        toolsTreeNameColumn.set_resizable(True)
        toolsTreeNameColumn.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        toolsTreeNameColumn.set_fixed_width(650)
        self.toolsTree.append_column(toolsTreeNameColumn)
        cell2 = gtk.CellRendererToggle()
        #cell2.set_property('activatable', True)
        cell2.connect("toggled", self.on_tools_toggle, self.toolsTree)
        toolsTreeInMistikaColumn = gtk.TreeViewColumn("Show in Mistika", cell2, active=1)

        toolsTreeInMistikaColumn.set_resizable(True)
        toolsTreeInMistikaColumn.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        #toolsTreeInMistikaColumn.set_fixed_width(3)
        #toolsTreeInMistikaColumn.set_expand(True)
        # toolsTreeInMistikaColumn.set_fixed_width(6)
        # toolsTreeInMistikaColumn.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        #toolsTreeInMistikaColumn.set_title("Show in Mistika")
        #toolsTreeInMistikaColumn.pack_start(cell2, False)
        #toolsTreeInMistikaColumn.add_attribute(cell2, "active", 0)
        self.toolsTree.append_column(toolsTreeInMistikaColumn)

        self.toolsTreestore = gtk.TreeStore(str, bool)
        toolsTreestore = self.toolsTreestore
        it = toolsTreestore.append(None, ["Conform", False])
        toolsTreestore.append(it, ["tcSwap.py", True])
        toolsTreestore.append(it, ["empConform.py", False])

        it = toolsTreestore.append(None, ["VFX", False])
        toolsTreestore.append(it, ["some vfx tool", False])
        itit = toolsTreestore.append(it, ["folder", False])
        toolsTreestore.append(itit, ["bar.py", False])

        # toolsTree.set_model(toolsTreestore)
        toolsFilter = toolsTreestore.filter_new();
        self.toolsFilter = toolsFilter
        toolsFilter.set_visible_func(self.FilterTree, filterEntry);
        self.toolsTree.set_model(toolsFilter)
        self.toolsTree.expand_all()

        vbox.pack_start(self.toolsTree)

        table = gtk.Table(8, 4, False)
        table.set_col_spacings(3)

        wins = gtk.TextView()
        wins.set_editable(False)
        wins.modify_fg(gtk.STATE_NORMAL, gtk.gdk.Color(5140, 5140, 5140))
        wins.set_cursor_visible(False)
        table.attach(wins, 0, 2, 1, 3, gtk.FILL | gtk.EXPAND,
            gtk.FILL | gtk.EXPAND, 1, 1)

        activate = gtk.Button("Activate")
        activate.set_size_request(50, 30)
        table.attach(activate, 3, 4, 1, 2, gtk.FILL, 
            gtk.SHRINK, 1, 1)
        
        valign = gtk.Alignment(0, 0, 0, 0)
        close = gtk.Button("Close")
        close.set_size_request(70, 30)
        valign.add(close)
        table.set_row_spacing(1, 3)
        table.attach(valign, 3, 4, 2, 3, gtk.FILL,
            gtk.FILL | gtk.EXPAND, 1, 1)
            
        halign2 = gtk.Alignment(0, 1, 0, 0)
        help = gtk.Button("Help")
        help.set_size_request(70, 30)
        halign2.add(help)
        table.set_row_spacing(3, 6)
        table.attach(halign2, 0, 1, 4, 5, gtk.FILL, 
            gtk.FILL, 0, 0)
        
        ok = gtk.Button("OK")
        ok.set_size_request(70, 30)
        table.attach(ok, 3, 4, 4, 5, gtk.FILL, 
            gtk.FILL, 0, 0);
                   
        #vbox.pack_start(table, True, True, 10)

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
        
    def on_quit(self, widget):
        print 'Closed by: ' + repr(widget)
        gtk.main_quit()

    def on_filter(self, widget, event):
        print widget.get_text()
        self.toolsFilter.refilter();
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
    def FilterTree(self, model, iter, widget, seek_up=True, seek_down=True, filter=False):
        self.toolsTree.expand_all()
        if not filter:
            filter = widget.get_text().lower()
        name = model.get_value(iter, 0).lower()
        parent = model.iter_parent(iter)
        has_child = model.iter_has_child(iter)
            # print name + ' has child'
            # return True
        print 'Seeking ' + name
        for word in filter.split():
            if word in name:
                continue
            relative_match = False
            if seek_down and has_child:
                print 'Seeking children'
                for n in range(model.iter_n_children(iter)):
                    if self.FilterTree(model, model.iter_nth_child(iter, n), widget, seek_up=False, filter=word):
                        print 'Child matches!'
                        relative_match = True
            if seek_up and parent != None:
                print 'Seeking parents'
                if self.FilterTree(model, parent, widget, seek_down=False, filter=word):
                    print 'Parent matches!'
                    relative_match = True
            if relative_match:
                continue
            return False

        return True

# private bool FilterTree (Gtk.TreeModel model, Gtk.TreeIter iter)
#     {
#         string artistName = model.GetValue (iter, 0).ToString ();
 
#         if (filterEntry.Text == "")
#             return true;
 
#         if (artistName.IndexOf (filterEntry.Text) > -1)
#             return true;
#         else
#             return false;
#     }

    def on_tools_toggle(self, cellrenderertoggle, path, *ignore):
        self.toolsTreestore[path][1] = not self.toolsTreestore[path][1]
        print self.toolsTreestore[path][0]


PyApp()
gtk.main()