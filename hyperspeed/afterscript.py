#!/usr/bin/env python

import csv
import json
import sys
import os
import re
import subprocess
import shlex
import threading
import time

import hyperspeed
import hyperspeed.utils
import hyperspeed.stack
import hyperspeed.sockets
from hyperspeed import mistika

try:
    import gtk
    import gobject
    import pango
except ImportError:
    gtk = False

SETTINGS_DEFAULT = {
    'autostart' : False, 
    'remove-input' : False,
    'overwrite' : False, 
    'reveal-output' : True
}
SETTINGS_FILENAME = 'settings.cfg'
RENAME_MAGIC_WORDS = ['auto', 'rename']
RENDER_DEFAULT_PATH = 'No render loaded'

class Afterscript(object):
    render = None
    cmd = []
    output_path = ''
    render_path = RENDER_DEFAULT_PATH
    render_name = ''
    def __init__(self, script_path, cmd, output_pattern, title='Afterscript'):
        self.script_path = script_path
        if type(cmd) == list:
            self.cmd = cmd
        elif type(cmd) == str:
            self.cmd = [cmd]
        self.output_pattern = output_pattern
        self.init_settings()
        if len(sys.argv) >= 3 and sys.argv[1] == 'ok':
            render_name = sys.argv[2]
            render_path = self.render_path = mistika.get_rnd_path(render_name)
            self.load_render(render_path)
    def init_settings(self):
        self.settings = SETTINGS_DEFAULT
        script_folder = os.path.dirname(self.script_path)
        script_settings_path = os.path.join(script_folder, SETTINGS_FILENAME)
        try:
            self.settings.update(json.loads(open(script_settings_path).read()))
        except IOError:
            # No settings found
            pass
    def load_render(self, render_path):
        render = self.render = hyperspeed.stack.Render(render_path)
        self.render_name = render.name
        if render.exists:
            self.init_output_path()
        else:
            print 'Could not load render: %s' % render_path
            
    def init_output_path(self):
        variables = {
            '<project>' : mistika.project,
            '<render_name>' : self.render_name,
            '<codec>' : self.render.primary_output.get_codec
        }
        rename = False
        for magic_word in RENAME_MAGIC_WORDS:
            if magic_word in self.render_name:
                variables['<render_name>'] = self.render.title
                rename = True
                break
        output_path = os.path.normpath(os.path.join(os.path.dirname(self.render.primary_output.path), self.output_pattern))
        for k, v in variables.iteritems():
            if callable(v):
                output_path = output_path.replace(k, v())
            else:
                output_path = output_path.replace(k, v)
        # Strip _%05d or .%06d from sequences:
        output_path = re.sub('\.*_*%\d+d$', '',  output_path)
        self.output_path = output_path

class AfterscriptFfmpeg(Afterscript):
    processes = []
    abort = False
    input_args = []
    cmd_string = ''
    args = []
    def __init__(self, script_path, cmd, output_path, title='Afterscript', executable='ffmpeg'):
        super(AfterscriptFfmpeg, self).__init__(script_path, cmd, output_path, title)
        if not gtk or '--force-socket' in sys.argv:
            try:
                args = sys.argv
                args[0] = os.path.abspath(args[0])
                hyperspeed.sockets.launch(args)
                sys.exit(0)
            except IOError as e:
                print e
                print 'Could not launch afterscript'
                sys.exit(1)
        self.executable = executable
        self.init_input_args()
        gobject.threads_init()
        self.init_window()
        self.cmd_update()
        if self.render != None and self.settings['autostart']:
            gobject.idle_add(self.on_run)
    def init_window(self):
        window = self.window = gtk.Window()
        screen = window.get_screen()
        window.set_size_request(screen.get_width()/2-200, -1)
        window.set_border_width(20)
        window.set_position(gtk.WIN_POS_CENTER)
        vbox = gtk.VBox()
        hbox = gtk.HBox()
        label =  gtk.Label('Render:')
        hbox.pack_start(label, False, False, 10)
        entry = self.render_path_entry = gtk.Entry()
        entry.set_text(self.render_path)
        entry.set_sensitive(False)
        hbox.pack_start(entry)
        button = self.output_pick_button = gtk.Button('...')
        button.connect("clicked", self.on_render_pick)
        hbox.pack_start(button, False, False, 10)
        vbox.pack_start(hbox, False, False, 10)
        hbox = gtk.HBox()
        label =  gtk.Label('Command:')
        hbox.pack_start(label, False, False, 10)
        entry = self.cmd_entry = gtk.Entry()
        entry.set_text(self.cmd_string)
        hbox.pack_start(entry)
        vbox.pack_start(hbox, False, False, 10)
        button = self.output_pick_button = gtk.Button('...')
        button.connect("clicked", self.on_output_pick)
        hbox.pack_start(button, False, False, 10)
        checkbox = self.checkbox_overwrite = gtk.CheckButton('Overwrite existing output without asking')
        checkbox.set_active(self.settings['overwrite'])
        checkbox.connect('toggled', self.on_settings_change, 'overwrite')
        vbox.pack_start(checkbox, False, False, 10)
        checkbox = self.checkbox_remove_input = gtk.CheckButton('Remove input after encoding')
        checkbox.set_active(self.settings['remove-input'])
        checkbox.connect('toggled', self.on_settings_change, 'overwrite')
        vbox.pack_start(checkbox, False, False, 10)
        button = gtk.Button('Go')
        button.connect("clicked", self.on_run)
        vbox.pack_start(button, False, False, 10)
        vbox.pack_start(self.log_widget(), True, True, 10)
        progressbar = self.progressbar = gtk.ProgressBar()
        progressbar.set_no_show_all(True)
        vbox.pack_start(progressbar, False, False, 10)
        button = self.reveal_output_button = gtk.Button('Reveal output')
        button.connect("clicked", self.on_reveal_output)
        button.set_no_show_all(True)
        vbox.pack_start(button, False, False, 10)
        footer = gtk.HBox(False, 10)
        quitButton = gtk.Button('Quit')
        quitButton.set_size_request(70, 30)
        quitButton.connect("clicked", self.on_quit)
        footer.pack_end(quitButton, False, False)
        vbox.pack_end(footer, False, False, 10)
        window.connect("destroy", self.on_quit)
        window.add(vbox)
        window.show_all()
    def on_settings_change(self, widget, setting_key):
        value = widget.get_active()
        self.settings[setting_key] = value
    def cmd_update(self):
        full_cmd = [self.executable] + self.input_args + self.cmd + [self.output_path]
        cmd_string = self.cmd_string = ' '.join(full_cmd)
        try:
            self.cmd_entry.set_text(cmd_string)
        except AttributeError:
            # Window is not created yet
            pass
    def init_input_args(self):
        render = self.render
        input_args = []
        if render != None:
            if render.output_video != None:
                input_args.append('-i')
                if '%' in render.output_video.path:
                    video_file_path = render.output_video.path % render.output_video.start
                else:
                    video_file_path = render.output_video.path
                input_args.append(video_file_path)
            elif render.output_proxy != None:
                input_args.append('-i')
                if '%' in render.output_proxy.path:
                    video_file_path = render.output_proxy.path % render.output_proxy.start
                else:
                    video_file_path = render.output_proxy.path
                input_args.append(video_file_path)
            if render.output_audio != None:
                input_args.append('-i')
                input_args.append(render.output_audio.path)
        self.input_args = input_args
        self.cmd_update()
    def on_quit(self, widget):
        self.abort = True
        # print 'Closed by: ' + repr(widget)
        for proc in self.processes:
            try:
                proc.kill()
            except OSError:
                pass
        # for thread in threading.enumerate():
        #     print 'Ending thread: %s' % thread.name
        gtk.main_quit()
    def on_render_pick(self, widget):
        path = self.render_path_entry.get_text()
        if path == RENDER_DEFAULT_PATH:
            path = os.path.join(mistika.projects_folder, mistika.project, 'DATA/RENDER/111')
        dialog = gtk.FileChooserDialog(
            parent=self.window,
            title="Read render file",
            action=gtk.FILE_CHOOSER_ACTION_OPEN,
            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_SAVE, gtk.RESPONSE_OK),
            backend=None
        )
        dialog.set_filename(path)
        filter_mov = gtk.FileFilter()
        filter_mov.set_name("Mistika render")
        filter_mov.add_pattern("*.rnd")
        dialog.set_filter(filter_mov)
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            chosen_path = dialog.get_filename()
            self.render_path_entry.set_text(chosen_path)
            dialog.destroy()
            self.load_render(chosen_path)
            self.init_input_args()
            return chosen_path
        elif response == gtk.RESPONSE_CANCEL:
            dialog.destroy()
            return
    def on_output_pick(self, widget):
        path = self.output_entry.get_text()
        dialog = gtk.FileChooserDialog(
            parent=self.window,
            title="Export to ...",
            action=gtk.FILE_CHOOSER_ACTION_SAVE,
            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_SAVE, gtk.RESPONSE_OK),
            backend=None
        )
        dialog.set_filename(path)
        filter_mov = gtk.FileFilter()
        filter_mov.set_name("QuickTime video")
        filter_mov.add_pattern("*.mov")
        dialog.set_filter(filter_mov)
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            chosen_path = dialog.get_filename()
            self.update_output_path.set_text(chosen_path)
            dialog.destroy()
            return chosen_path
        elif response == gtk.RESPONSE_CANCEL:
            dialog.destroy()
            return
    def update_output_path(self, new_path=False):
        args = shlex.split(self.cmd_entry.get_text())
        last_arg = args[-1]
        self.output_path = last_arg
        if new_path:
            self.output_path = new_path
            if not last_arg in self.input_args:
                args = args[:-1]
            args.append(new_path)
        args_quoted = []
        for arg in args:
            if ' ' in arg:
                args_quoted.append('"%s"' % arg)
            else:
                args_quoted.append(arg)
        self.cmd_entry.set_text(' '.join(args_quoted))
        self.args = args_quoted
    def gui_yesno_dialog(self, question, confirm_object=False, confirm_lock=False):
        dialog = gtk.MessageDialog(
            parent = self.window,
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
    def gui_info_dialog(self, message):
        dialog = gtk.MessageDialog(
            parent = self.window,
            flags=0,
            type=gtk.MESSAGE_INFO,
            buttons=gtk.BUTTONS_OK,
            message_format=message
        )
        dialog.set_position(gtk.WIN_POS_CENTER)
        response = dialog.run()
        dialog.destroy()
    def on_reveal_output(self, widget):
        hyperspeed.utils.reveal_file(self.output_path)
    def on_run(self, widget=False):
        self.update_output_path()
        self.output_marker = self.output_path+'.incomplete'
        force_overwrite = False
        render_to_input_folder = False
        if os.path.exists(self.output_path):
            if self.settings['overwrite']:
                overwrite = True
            else:
                overwrite = self.gui_yesno_dialog("File '%s' already exists. Overwrite?" % self.output_path)
            if overwrite:
                force_overwrite = True
            else:
                return
        elif not os.path.exists(os.path.dirname(self.output_path)):
            try:
                os.makedirs(os.path.dirname(self.output_path))
            except OSError:
                render_to_input_folder = True
        elif os.path.dirname(self.render.primary_output.path) != os.path.dirname(self.output_path):
            try:
                open(self.output_marker, 'w').write(str(time.time()))
            except IOError:
                render_to_input_folder = True
        else:
            try:
                open(self.output_marker, 'w').write(str(time.time()))
            except IOError:
                error = 'Cannot write to neither input nor output folder'
                self.write(error+'\n')
                gobject.idle_add(self.gui_info_dialog, error)
                return
        if render_to_input_folder:
            self.update_output_path(os.path.join(os.path.dirname(self.render.primary_output.path), os.path.basename(self.output_path)))
            self.on_run()
            return
        t = threading.Thread(target=self.run, name='ffmpeg', kwargs={'overwrite' : force_overwrite})
        t.setDaemon(True)
        t.start()
    def run(self, overwrite=False):
        gobject.idle_add(self.progressbar.set_property, 'visible', True)
        cmd_args = self.args
        if overwrite:
            cmd_args = [cmd_args[0]] + ['-y'] + cmd_args[1:]
        else:
            cmd_args = [cmd_args[0]] + ['-n'] + cmd_args[1:]
        self.write(' '.join(cmd_args)+'\n')
        proc = subprocess.Popen(cmd_args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.processes.append(proc)
        output = ''
        while True:
            if self.abort:
                proc.kill()
                return
            output_prev = output
            output = ''
            char = None
            while not char in ['\r', '\n', '']:
                char = proc.stdout.read(1)
                output += char
            if char == '':
                break
            output = output.rstrip()
            # print repr(output)
            self.write(output+'\n')
            fields = output.split()
            if output.endswith('[y/N]'):
                confirm = [False]
                confirm_lock = threading.Lock()
                confirm_lock.aqcuire()
                confirm = gobject.idle_add(self.gui_yesno_dialog, output, confirm, confirm_lock)
                confirm_lock.aqcuire()
                if confirm[0]:
                    proc.write('y\r')
                else:
                    proc.write('n\r')
                    print 'Aborted by user'
                    return
            elif output.startswith('frame='):
                status = {}
                keyvalue_pairs = re.findall('\w+=\s*\S+', output)
                for keyvalue_pair in keyvalue_pairs:
                    k, v = keyvalue_pair.split('=')
                    status[k] = v
                progress_float = float(status['frame']) / float(self.render.frames)
                progress_percent = progress_float * 100.0
                progress_string = '%5.2f%%' % progress_percent
                gobject.idle_add(self.progressbar.set_fraction, progress_float)
                gobject.idle_add(self.progressbar.set_text, progress_string)
            proc.poll()
        try:
            os.remove(self.output_marker)
        except OSError:
            print 'Could not remote incomplete marker: %s' % self.output_marker
        print 'Process ended'
        if proc.returncode > 0:
            gobject.idle_add(self.gui_info_dialog, output_prev)
        else:
            gobject.idle_add(self.reveal_output_button.set_property, 'visible', True)
            if self.checkbox_remove_input.get_active():
                render.remove_output()
    def log_widget(self):
        textview = self.console = gtk.TextView()
        fontdesc = pango.FontDescription("monospace")
        textview.modify_font(fontdesc)
        textview.set_editable(False)
        textview.set_cursor_visible(False)
        textbuffer = self.console_buffer = textview.get_buffer()
        scroll = gtk.ScrolledWindow()
        scroll.add(textview)
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        expander = gtk.Expander("Log")
        expander.add(scroll)
        return expander
    def write(self, string):
        print string,
        gobject.idle_add(self.gui_write, string)
    def gui_write(self, string):
        self.console_buffer.insert(self.console_buffer.get_end_iter(), string)

# if len(sys.argv) > 1 and sys.argv[1] == 'AfterscriptFfmpeg':
#     AfterscriptFfmpeg(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
#     gtk.main()
