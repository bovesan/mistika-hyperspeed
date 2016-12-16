#!/usr/bin/python
# -*- coding: utf-8 -*-

import gtk
import sys, platform


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
        cell = gtk.CellRendererText()
        cell.set_property("foreground", "gray")
        cell.set_property("editable", True)
        column = gtk.TreeViewColumn('Path', cell, text=1)
        column.set_resizable(True)
        column.set_expand(True)
        self.linksTreestore = gtk.TreeStore(str) # Name, url, color, underline
        linksTreestore = self.linksTreestore
        self.linksTree.set_model(linksTreestore)
        self.linksTree.expand_all()

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(self.linksTree)
        #vbox.pack_start(scrolled_window)
        vbox.pack_start(scrolled_window)

        hbox = gtk.HBox(False, 10)
        button = gtk.Button('Add structure ...')
        button.set_size_request(70, 30)
        button.connect("clicked", self.add_file_dialog)
        hbox.pack_end(button, False, False, 0)

        vbox.pack_start(hbox, False, False, 0)


        hbox = gtk.HBox(False, 10)
        hbox.pack_start(gtk.Button('Destination folder:'), False, False, 5)
        hbox.pack_start(gtk.Entry(), False, False, 5)
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
        dialog = gtk.FileChooserDialog(title="Add files", parent=None, action=gtk.FILE_CHOOSER_ACTION_OPEN, buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK), backend=None)
        dialog.set_select_multiple(True)
        #dialog.add_filter(filter)
        dialog.add_shortcut_folder('/home/mistika/MISTIKA-ENV')
        filter = gtk.FileFilter()
        filter.set_name("Mistika structures")
        filter.add_pattern("*.env")
        filter.add_pattern("*.grp")
        filter.add_pattern("*.rnd")
        filter.add_pattern("*.clp")
        filter.add_pattern("*.lnk")
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            print dialog.get_filename(), 'selected'
        elif response == gtk.RESPONSE_CANCEL:
            print 'Closed, no files selected'
        dialog.destroy()

PyApp()
gtk.main()