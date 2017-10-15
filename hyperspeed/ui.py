#!/usr/bin/env python

import sys
import os
import subprocess
import platform
import threading
import hyperspeed
import json

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
    def __init__(self, title, settings_default, icon_path=None):
        super(Window, self).__init__()
        self.history = []
        self.hotkeys = [
            {
                'combination' : ['Ctrl', 'q'],
                'method' : self.on_quit,
                'args' : ['Keyboard shortcut']
            },
            {
                'combination' : ['Ctrl', 'z'],
                'method' : self.undo,
                'args' : [1]
            },
        ]
        settings = self.settings = settings_default
        self.settings_load()
        screen = self.get_screen()
        monitor = screen.get_monitor_geometry(0)
        self.set_title(title)
        if 'window_size' in settings:
            self.set_default_size(settings['window_size']['width'], settings['window_size']['height'])
        else:
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
        self.connect('check-resize', self.on_window_resize)
        self.connect("destroy", self.on_quit)
        # gtkrc = '''
        # style "theme-fixes" {
        #     font_name = "sans normal 12"
        # }
        # class "*" style "theme-fixes"'''
        # gtk.rc_parse_string(gtkrc)

    def on_window_resize(self, window):
        width, height = self.get_size()
        self.set_settings({
            'window_size' : {
                'width' : width,
                'height': height
            }
        })
        # self.launch_thread(self.set_settings, [{
        #     'window_size' : {
        #         'width' : width,
        #         'height': height
        #     }
        # }])
    def on_key_press_event(self,widget,event):
        hotkeys = self.hotkeys
        keyval = event.keyval
        keyval_name = gtk.gdk.keyval_name(keyval)
        state = event.state
        ctrl = (state & gtk.gdk.CONTROL_MASK)
        command = (state & gtk.gdk.MOD1_MASK)
        combination = []
        if (ctrl or command):
            combination.append('Ctrl')
        combination.append(keyval_name)
        for hotkey in hotkeys:
            if combination == hotkey['combination']:
                if 'args' in hotkey:
                    args = hotkey['args']
                else:
                    args = []
                if 'kwargs' in hotkey:
                    kwargs = hotkey['kwargs']
                else:
                    kwargs = {}
                hotkey['method'](*args,**kwargs)
                return True
        return False
    def on_quit(self, widget):
        self.quit = True
        if type(widget) is gtk.Button:
            widget_name = widget.get_label() + ' button'
        else:
            widget_name = str(widget)
        # print 'Closed by: ' + widget_name
        gtk.main_quit()
    def undo(self, steps):
        history = self.history
        while steps > 0 and len(history) > 0:
            previous = history.pop()
            previous.undo()
            steps -= 1
    def settings_load(self):
        script_path = os.path.realpath(sys.argv[0])
        if not script_path.endswith('.cfg'): # Just to be sure we don't overwrite the script
            script_path = os.path.splitext(script_path)[0]
        if script_path.startswith(hyperspeed.folder):
            self.settings_path = script_path.replace(hyperspeed.folder, hyperspeed.config_folder)+'.cfg'
            settings_folder = os.path.dirname(self.settings_path)
            if not os.path.isdir(settings_folder):
                try:
                    os.makedirs(settings_folder)
                except OSError as e:
                    self.settings_path = script_path+'.cfg'
        else:
            self.settings_path = script_path+'.cfg'
        try:
            self.settings.update(json.loads(open(self.settings_path).read()))
        except IOError:
            # No settings found
            pass
    def set_settings(self, settings={}):
        self.settings.update(settings)
        t = threading.Thread(target=self.settings_store, name='Store settings')
        t.setDaemon(True)
        t.start()
    def on_settings_change(self, widget, setting_key):
        if hasattr(widget, 'get_active'): # Checkbox
            value = widget.get_active()
        elif hasattr(widget, 'get_text'): # Textbox
            value = widget.get_text()
        self.set_settings({
            setting_key : value
        })
    def settings_store(self):
        try:
            open(self.settings_path, 'w').write(json.dumps(self.settings, sort_keys=True, indent=4))
            return True
        except IOError as e:
            print 'Could not store settings. %s' % e
            return False
    def launch_thread(self, target, name=False, args=[], kwargs={}):
        arg_strings = []
        for arg in list(args):
            arg_strings.append(repr(arg))
        for k, v in kwargs.iteritems():
            arg_strings.append('%s=%s' % (k, v))
        if not name:
            name = '%s(%s)' % (target, ', '.join(arg_strings))
        t = threading.Thread(target=target, name=name, args=args, kwargs=kwargs)
        t.setDaemon(True)
        t.start()
        return t


def dialog_yesno(parent, question, confirm_object=False, confirm_lock=False):
    dialog = gtk.MessageDialog(
        parent = parent,
        flags=0,
        type=gtk.MESSAGE_QUESTION,
        buttons=gtk.BUTTONS_YES_NO,
        message_format=question
    )
    dialog.set_position(gtk.WIN_POS_CENTER)
    response = dialog.run()
    dialog.destroy()
    if response == -8:
        status = True
    else:
        status = False
    if confirm_object:
        confirm_object[0] = status
    if confirm_lock:
        confirm_lock.release()
    if status:
        return True
    else:
        return False

def dialog_info(parent, message):
    dialog = gtk.MessageDialog(
        parent = parent,
        flags=0,
        type=gtk.MESSAGE_INFO,
        buttons=gtk.BUTTONS_OK,
        message_format=message
    )
    dialog.set_position(gtk.WIN_POS_CENTER)
    response = dialog.run()
    dialog.destroy()

def dialog_error(parent, message):
    dialog = gtk.MessageDialog(
        parent = parent,
        flags=0,
        type=gtk.MESSAGE_ERROR,
        buttons=gtk.BUTTONS_OK,
        message_format=message
    )
    dialog.set_position(gtk.WIN_POS_CENTER)
    response = dialog.run()
    dialog.destroy()

def event_debug(*args):
    print repr(args)