#!/usr/bin/env python
# -*- coding: utf-8 -*-

import gtk
import os
import uuid
import math
import subprocess
import time
import sys
import gobject
import platform
import hyperspeed
import json

script_settings_path = os.path.join(hyperspeed.config_folder, 'fetch.cfg')


class PyApp(gtk.Window):
    batch_mode = False
    settings = {
        'mappings' : {},
    }
    def __init__(self):
        super(PyApp, self).__init__()
        screen = self.get_screen()
        self.set_title("Fetch")
        self.set_size_request(screen.get_width()/2-100, screen.get_height()-200)
        self.set_border_width(20)
        self.set_position(gtk.WIN_POS_CENTER)
        if 'darwin' in platform.system().lower():
            self.set_resizable(False) # Because resizing crashes the app on Mac
        # self.connect("key-press-event",self.on_key_press_event)

        vbox = gtk.VBox(False, 10)

        vbox.pack_start(self.init_mappings_view())

        hbox = gtk.HBox(False, 10)
        button = gtk.Button('Add local folder')
        button.connect("clicked", self.add_local_folder)
        hbox.pack_start(button, False, False, 0)
        button = gtk.Button('Add source')
        button.connect("clicked", self.add_remote_folder)
        hbox.pack_start(button, False, False, 0)
        button = gtk.Button('Remove selected')
        button.connect("clicked", self.remove_selected_mappings)
        hbox.pack_start(button, False, False, 0)
        vbox.pack_start(hbox, False, False, 0)

        vbox.pack_start(self.init_files_view())

        hbox = gtk.HBox(False, 10)
        button = gtk.Button('Add folder ...')
        # button.connect("clicked", self.add_folder_dialog)
        hbox.pack_end(button, False, False, 0)
        button = gtk.Button('Remove selected')
        # button.connect("clicked", self.gui_on_selected_folders, 'remove')
        hbox.pack_end(button, False, False, 0)
        vbox.pack_start(hbox, False, False, 0)

        # vbox.pack_start(self.init_excess_window())

        hbox = gtk.HBox(False, 10)
        self.status_label = gtk.Label('No excess files')
        hbox.pack_start(self.status_label, False, False, 5)
        spinner = self.spinner_queue = gtk.Image()
        spinner.set_no_show_all(True)
        try:
            spinner.set_from_file('../../res/img/spinner01.gif')
        except:
            pass
        hbox.pack_start(spinner, False, False, 5)
        button = self.button_copy = gtk.Button('Permanently delete selected, disabled files')
        # button.connect("clicked", self.gui_on_selected_excess, 'delete')
        hbox.pack_end(button, False, False, 5)
        button = self.button_copy = gtk.Button('Re-enable selected files')
        # button.connect("clicked", self.gui_on_selected_excess, 'enable')
        hbox.pack_end(button, False, False, 5)
        button = self.button_copy = gtk.Button('Disable selected files')
        # button.connect("clicked", self.gui_on_selected_excess, 'disable')
        hbox.pack_end(button, False, False, 5)
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
        self.parse_command_line_arguments()
        self.load_settings()
        gobject.idle_add(self.present)
    def load_settings(self):
        try:
            print 'script_settings_path', script_settings_path, open(script_settings_path).read()
            self.settings.update(json.loads(open(script_settings_path).read()))
            treestore = self.mappings_treestore
            treestore.clear();
            print self.settings['mappings']
            for local, remotes in self.settings['mappings'].iteritems():
                print local
                local_row = treestore.append(None, [local])
                for remote in remotes:
                    print remote
                    treestore.append(local_row, [remote])
            # print self.settings
        except ValueError as e:
            print e
            pass
        else:
            pass
        finally:
            pass
    def save_settings(self):
        open(script_settings_path, 'w').write(json.dumps(self.settings, sort_keys=True, indent=2))
    def on_quit(self, widget):
        gtk.main_quit()
    def parse_command_line_arguments(self):
        # -H /Volumes/mediaraid/Projects/22189_Hurtigruta/MISTIKA_JS/MR2_0009_0021.js -L /Volumes/mediaraid/Projects/22189_Hurtigruta/MISTIKA_JS/L_MR2_0009_0021.js -S None -l 0 -n MR2_0009_0021_Raftsundet_V1-0004 -i 0 -s 0 -e 249 -p 22189_Hurtigruta -f RGB10:XFS.RGB10 -T 00:56:28:13 -a 160
        print ' '.join(sys.argv[1:])
    def on_mapping_edited(self, cellrenderertext, path, new_text):
        print cellrenderertext, path, new_text
        treestore = self.mappings_treestore
        treestore[path][0] = new_text
        self.on_mappings_changed()
    def on_mappings_changed(self):
        treestore = self.mappings_treestore
        mappings = {}
        for x in treestore:
            mapping = []
            for y in x.iterchildren():
                print '-', y[0]
                mapping.append(y[0])
            print x[0]
            mappings[x[0]] = mapping
        self.settings['mappings'] = mappings
        self.save_settings()
    def init_mappings_view(self):
        treestore = self.mappings_treestore = gtk.TreeStore(str) # Local, Local editable, Remote, Remote editable
        treeview = self.mappings_treeview = gtk.TreeView()
        treeview.set_rules_hint(True)
        cell = gtk.CellRendererText()
        cell.set_property("editable", True)
        cell.connect('edited', self.on_mapping_edited, )
        column = gtk.TreeViewColumn('Mappings', cell, text=0)
        column.set_resizable(True)
        column.set_expand(True)
        treeview.append_column(column)
        treeview.set_model(treestore)
        treeview.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(treeview)
        return scrolled_window
    def init_files_view(self):
        treestore = self.files_treestore = gtk.TreeStore(str, float, str, bool, bool) # Local, progress float, progress text, progress visible, status, status visible
        treeview = self.files_treeview = gtk.TreeView()
        treeview.set_rules_hint(True)
        cell = gtk.CellRendererText()
        cell.set_property("editable", True)
        column = gtk.TreeViewColumn('Local folder', cell, text=0)
        column.set_resizable(True)
        column.set_expand(True)
        treeview.append_column(column)
        cell = gtk.CellRendererText()
        cell.set_property("editable", True)
        column = gtk.TreeViewColumn('Remote source', cell, text=1)
        column.set_resizable(True)
        column.set_expand(True)
        treeview.append_column(column)
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn('Status')
        column.pack_start(cell, False)
        column.set_attributes(cell, text=5, visible=6)
        cell = gtk.CellRendererProgress()
        column = gtk.TreeViewColumn('Progress')
        column.pack_start(cell, True)
        column.set_attributes(cell, value=2, text=3, visible=4)
        column.set_resizable(True)
        treeview.append_column(column)
        treeview.set_model(treestore)
        treeview.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(treeview)
        return scrolled_window

    def add_local_folder(self, widget):
        treeview = self.mappings_treeview
        row_iter = self.mappings_treestore.append(None, ['/'])
        row_path = self.mappings_treestore.get_path(row_iter)
        selection = treeview.get_selection()
        selection.select_path(row_path)
        self.on_mappings_changed()
    def add_remote_folder(self, widget):
        treeview = self.mappings_treeview
        selection = treeview.get_selection()
        (model, row_paths) = selection.get_selected_rows()
        for selected_row_path in row_paths:
            if type(selected_row_path) is tuple:
                selected_row_path = selected_row_path[0]
            selected_row_iter = model.get_iter(selected_row_path)
            row_iter = self.mappings_treestore.append(selected_row_iter, ['user@host:/'])
            row_path = self.mappings_treestore.get_path(row_iter)
            treeview.expand_to_path(row_path)
            selection.unselect_all()
            selection.select_path(row_path)
        self.on_mappings_changed()
    def remove_selected_mappings(self, widget):
        treeview = self.mappings_treeview
        treestore = self.mappings_treestore
        selection = treeview.get_selection()
        (model, row_paths) = selection.get_selected_rows()
        for selected_row_path in reversed(row_paths):
            selected_row_iter = model.get_iter(selected_row_path)
            treestore.remove(selected_row_iter)
        self.on_mappings_changed()

gobject.threads_init()
PyApp()
gtk.main()