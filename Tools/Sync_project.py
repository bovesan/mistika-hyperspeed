#!/usr/bin/python
# -*- coding: utf-8 -*-

import gtk
import sys, platform


class PyApp(gtk.Window):

    def __init__(self):
        super(PyApp, self).__init__()
        screen = self.get_screen()
        self.set_title("Mistika remote sync")
        self.set_size_request(800, screen.get_height()-200)
        self.set_border_width(20)
        self.set_position(gtk.WIN_POS_CENTER)
        if 'darwin' in platform.system().lower():
            self.set_resizable(False) # Because resizing crashes the app on Mac

        vbox = gtk.VBox(False, 10)

        hbox = gtk.HBox(False, 10)
        hbox.pack_start(gtk.Label('Remote host:'), False, False, 0)
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
        column = gtk.TreeViewColumn('Host', cell, text=1)
        column.set_resizable(True)
        column.set_expand(True)
        self.linksTree.append_column(column)
        cell = gtk.CellRendererText()
        cell.set_property("foreground", "gray")
        cell.set_property("editable", True)
        column = gtk.TreeViewColumn('Username', cell, text=2)
        column.set_resizable(True)
        column.set_expand(True)
        self.linksTree.append_column(column)
        cell = gtk.CellRendererText()
        cell.set_property("foreground", "gray")
        cell.set_property("editable", True)
        column = gtk.TreeViewColumn('Port', cell, text=3)
        column.set_resizable(True)
        column.set_expand(True)
        self.linksTree.append_column(column)
        cell = gtk.CellRendererText()
        cell.set_property("foreground", "gray")
        cell.set_property("editable", True)
        column = gtk.TreeViewColumn('Projects path', cell, text=4)
        column.set_resizable(True)
        column.set_expand(True)
        self.linksTree.append_column(column)
        self.linksTreestore = gtk.TreeStore(str, str, str, int, str) # Name, url, color, underline
        linksTreestore = self.linksTreestore
        linksTreestore.append(None, ["Horten", 'horten.hocusfocus.no', 'mistika', 22, '/Volumes/SLOW_HF/PROJECTS/'])
        linksTreestore.append(None, ["Oslo", 's.hocusfocus.no', 'mistika', 22, '/Volumes/SLOW_HF/PROJECTS/'])
        linksFilter = linksTreestore.filter_new();
        self.linksTree.set_model(linksTreestore)
        self.linksTree.expand_all()

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(self.linksTree)
        #vbox.pack_start(scrolled_window)
        vbox.pack_start(scrolled_window)

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
        self.set_keep_above(True)
        #self.present()


    def on_quit(self, widget):
        print 'Closed by: ' + repr(widget)
        gtk.main_quit()

PyApp()
gtk.main()