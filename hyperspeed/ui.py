#!/usr/bin/env python

import gtk
import gobject
import sys
import os
import pango
import platform
import subprocess
import hyperspeed
import tempfile
import time

BASH_WRAPPER = '''#!/bin/bash
%s
if [ $? -ne 0 ];then                   # $? holds exit status, test if error occurred
        read -p "Press any key to exit "
fi
exit 0
'''

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

def terminal(exec_args):
    if platform.system() == 'Linux':
        try:
            return subprocess.Popen(['konsole', '-e', os.path.join(hyperspeed.folder, 'res/scripts/bash_wrapper.sh')] + exec_args)
            
        except OSError as e:
            try:
                return subprocess.Popen(['xterm', '-e', os.path.join(hyperspeed.folder, 'res/scripts/bash_wrapper.sh')] + exec_args)
            except OSError as e:
                try:
                    return subprocess.Popen([exec_args])
                except:
                    pass
    elif platform.system() == 'Darwin':
        # return subprocess.Popen(['open', '-a', 'Terminal.app', '--args', os.path.join(hyperspeed.folder, 'res/scripts/bash_wrapper.sh')] + exec_args)
        temp_dir = tempfile.mkdtemp()
        temp_file = os.path.join(temp_dir, 'exec.sh')
        open(temp_file, 'w').write(BASH_WRAPPER % ' '.join(exec_args))
        # print 'Temp file:', temp_file
        # print open(temp_file).read()
        os.chmod(temp_file, 0700)
        proc = subprocess.Popen(['open', '-a', 'Terminal.app', temp_file])
        # time.sleep(5)
        # os.remove(temp_file)
        # os.rmdir(temp_dir)
        return proc
    else:
        return subprocess.Popen(exec_args)
    print 'Failed to execute %s' % repr(exec_args)

class PlaceholderEntry(gtk.Entry):

    placeholder = ''
    _default = True

    def __init__(self, placeholder, *args, **kwds):
        gtk.Entry.__init__(self, *args, **kwds)
        self.placeholder = placeholder
        self.connect('focus-in-event', self._focus_in_event)
        self.connect('focus-out-event', self._focus_out_event)
        self.connect("key-release-event", self._key_release_event)
        gobject.idle_add(self._focus_out_event)

    def _focus_in_event(self, widget=False, event=False):
        if self._default:
            self.set_text('')
            self.modify_text(gtk.STATE_NORMAL, gtk.gdk.color_parse('black'))

    def _focus_out_event(self, widget=False, event=False):
        if gtk.Entry.get_text(self) == '':
            self.set_text(self.placeholder)
            self.modify_text(gtk.STATE_NORMAL, gtk.gdk.color_parse('gray'))
            self._default = True
        else:
            self._default = False
    def _key_release_event(self, widget=False, event=False):
        if gtk.Entry.get_text(self) == '':
            self._default = True
        else:
            self._default = False
    def get_text(self):
        if self._default:
            return ''
        return gtk.Entry.get_text(self)
        