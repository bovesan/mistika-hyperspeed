#!/usr/bin/env python

import sys
import os
import subprocess
import platform
try:
    import gtk
    import gobject
    import pango
except ImportError as e:
    print e
    gtk = False
    # import ctypes
    # try:
    #     # ctypes.CDLL("/home/mistika/MISTIKA-ENV/bin/lib/libX11.so.6", mode = ctypes.RTLD_GLOBAL)
    #     # ctypes.CDLL(hyperspeed.folder+"/res/lib/libxcb-xlib.so.0", mode = ctypes.RTLD_GLOBAL)
    #     ctypes.CDLL(hyperspeed.folder+"/res/lib/ld-linux-x86-64.so.2", mode = ctypes.RTLD_GLOBAL)
    #     ctypes.CDLL(hyperspeed.folder+"/res/lib/libc.so.6", mode = ctypes.RTLD_GLOBAL)
    #     # OSError: /home/mistika/mistika-hyperspeed/res/lib/libc.so.6: symbol _dl_starting_up, version GLIBC_PRIVATE not defined in file ld-linux-x86-64.so.2 with link time reference
    #     sys.path.insert(1, os.path.join(hyperspeed.folder, 'res/lib/gtk-2.0'))
    #     import gtk
    #     import gobject
    #     import pango
    # except ImportError as e:
    #     print e
    # import hyperspeed.sockets
    # try:
    #     args = sys.argv
    #     args[0] = os.path.abspath(args[0])
    #     hyperspeed.sockets.launch(args)
    #     sys.exit(0)
    # except IOError as e:
    #     print e
    #     print 'Could not launch %s' % __file__
    #     sys.exit(1)

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

class Window(gtk.Window):
    quit = False
    def __init__(self, title, icon_path=None):
        super(Window, self).__init__()
        screen = self.get_screen()
        monitor = screen.get_monitor_geometry(0)
        self.set_title(title)
        self.set_default_size(monitor.width-200, monitor.height-200)
        self.set_border_width(20)
        self.set_position(gtk.WIN_POS_CENTER)
        if 'darwin' in platform.system().lower():
            self.set_resizable(False) # Because resizing crashes the app on Mac
        self.connect("key-press-event",self.on_key_press_event)
        if not icon_path:
            icon_path = 'res/img/hyperspeed_1024px.png'
        self.set_icon_list(
            gtk.gdk.pixbuf_new_from_file_at_size(icon_path, 16, 16),
            gtk.gdk.pixbuf_new_from_file_at_size(icon_path, 32, 32),
            gtk.gdk.pixbuf_new_from_file_at_size(icon_path, 64, 64),
            gtk.gdk.pixbuf_new_from_file_at_size(icon_path, 128, 128),
            gtk.gdk.pixbuf_new_from_file_at_size(icon_path, 256, 256),
        )
        self.connect("destroy", self.on_quit)
        # gtkrc = '''
        # style "theme-fixes" {
        #     font_name = "sans normal 12"
        # }
        # class "*" style "theme-fixes"'''
        # gtk.rc_parse_string(gtkrc)
    def on_key_press_event(self,widget,event):
        keyval = event.keyval
        keyval_name = gtk.gdk.keyval_name(keyval)
        state = event.state
        ctrl = (state & gtk.gdk.CONTROL_MASK)
        command = (state & gtk.gdk.MOD1_MASK)
        if (ctrl or command) and keyval_name == 'q':
            self.on_quit('Keyboard shortcut')
        else:
            return False
        return True
    def on_quit(self, widget):
        self.quit = True
        if type(widget) is gtk.Button:
            widget_name = widget.get_label() + ' button'
        else:
            widget_name = str(widget)
        print 'Closed by: ' + widget_name
        gtk.main_quit()