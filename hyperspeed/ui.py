#!/usr/bin/env python

import gtk
import gobject
import sys
import os
import pango

class TerminalReplacement(gtk.Window):
    def __init__(self, method, inputs=False, default_folder=False):
        super(TerminalReplacement, self).__init__()
        screen = self.get_screen()
        self.set_size_request(screen.get_width()/2-100, screen.get_height()-200)
        self.set_border_width(20)
        self.set_position(gtk.WIN_POS_CENTER)
        self.connect("key-press-event",self.on_key_press_event)
        self.method = method
        self.default_folder = default_folder
        self.gui_ref = {}
        vbox = gtk.VBox(False, 10)
        for i, input_label in enumerate(inputs):
            input_id = 'input %i' % i
            self.gui_ref[input_id] = {}
            hbox = gtk.HBox(False, 10)
            label = gtk.Label(input_label+':')
            hbox.pack_start(label, False, False, 0)
            label = self.gui_ref[input_id]['label'] = gtk.Entry()
            hbox.pack_start(label, True, True, 0)
            button = self.gui_ref[input_id]['button'] = gtk.Button('...')
            button.connect("clicked", self.add_files_dialog, input_id, input_label)
            hbox.pack_start(button, False, False, 0)
            vbox.pack_start(hbox, False, False, 0)
        button = gtk.Button('Go')
        button.connect("clicked", self.run)
        vbox.pack_start(button, False, False, 5)
        textview = self.textview = gtk.TextView()
        fontdesc = pango.FontDescription("monospace")
        textview.modify_font(fontdesc)
        # textview.set_editable(False)
        scroll = gtk.ScrolledWindow()
        scroll.add(textview)
        # expander = gtk.Expander("Details")
        # expander.add(scroll)
        vbox.pack_start(scroll, True, True, 5)
        self.add(vbox)
        self.connect("destroy", gtk.main_quit)
        self.show_all()
        gobject.idle_add(self.present)
    def run(self, widget):
        inputs = []
        for input_id in self.gui_ref:
            inputs += self.gui_ref[input_id]['label'].get_text().split(', ')
        self.method(inputs, self.prnt)
    def prnt(self, string):
        gobject.idle_add(self.textview.get_buffer().insert_at_cursor, string+'\n')
    def add_files_dialog(self, widget, input_id, input_label):
        if self.default_folder:
            folder = self.default_folder
        else:
            folder = os.path.expanduser('~') 
        dialog = gtk.FileChooserDialog(title=input_label, parent=None, action=gtk.FILE_CHOOSER_ACTION_OPEN, buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK), backend=None)
        # if 'darwin' in platform.system().lower():
        #     dialog.set_resizable(False) # Because resizing crashes the app on Mac
        dialog.set_select_multiple(True)
        #dialog.add_filter(filter)
        dialog.set_current_folder(folder)
        # filter = gtk.FileFilter()
        # filter.set_name("Xml files")
        # filter.add_pattern("*.xml")
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            files = dialog.get_filenames()
            dialog.destroy()
            self.gui_ref[input_id]['label'].set_text(', '.join(files))
        elif response == gtk.RESPONSE_CANCEL:
            print 'Closed, no files selected'
            dialog.destroy()
            return
    def on_key_press_event(self,widget,event):
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