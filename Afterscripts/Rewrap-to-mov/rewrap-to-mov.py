#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import time
import subprocess
import json
import re
import gtk
import gobject
import pango
import threading

try:
    cwd = os.getcwd()
    os.chdir(os.path.dirname(os.path.realpath(sys.argv[0])))
    sys.path.append("../..")
    import hyperspeed.human
    import hyperspeed.mistika
    import hyperspeed.stack
    import hyperspeed.utils
    import hyperspeed.ui
    # from hyperspeed import afterscript
except ImportError:
    print 'Hyperspeed init error'
    sys.exit(1)

settings = {
    'autostart' : False, 
    'remove-input' : False,
    'overwrite' : False, 
    'reveal-output' : True 
}

script_path = os.path.realpath(__file__)
script_name = os.path.basename(script_path)
script_folder = os.path.dirname(script_path)
script_settings_path = os.path.join(script_folder, 'settings.cfg')
try:
    settings.update(json.loads(open(script_settings_path).read()))
except IOError:
    pass

rnd_name = sys.argv[2]
rnd_path = hyperspeed.mistika.get_rnd_path(rnd_name)
render = hyperspeed.stack.Render(rnd_path)


cmd = '-vcodec copy -acodec copy'

rename = False
for magic_word in hyperspeed.stack.RENAME_MAGIC_WORDS:
    if magic_word in rnd_name:
        rename = True
        break

if rename:
    output_path = os.path.join(os.path.dirname(render.output_video.path), render.project+'_'+render.groupname+'.mov')
else:
    output_path = os.path.splitext(render.output_video.path)[0]+'.mov'



class Ffmpeg(gtk.Window):
    processes = []
    abort = False
    def __init__(self, cmd, render, output_path, executable='ffmpeg'):
        super(Ffmpeg, self).__init__()
        self.cmd = [cmd]
        self.render = render
        self.output_path = output_path
        self.executable = executable
        self.input_args = self.init_input_args()
        self.init_gui()
    def init_gui(self):
        screen = self.get_screen()
        self.set_size_request(screen.get_width()/2-200, -1)
        self.set_border_width(20)
        self.set_position(gtk.WIN_POS_CENTER)
        vbox = gtk.VBox()
        entry = self.cmd_entry = gtk.Entry()
        full_cmd = [self.executable] + self.input_args + self.cmd
        cmd_string = ' '.join(full_cmd)
        entry.set_text(cmd_string)
        vbox.pack_start(entry, False, False, 10)
        hbox = gtk.HBox()
        entry = self.output_entry = gtk.Entry()
        entry.set_text(self.output_path)
        hbox.pack_start(entry)
        button = self.output_pick_button = gtk.Button('...')
        button.connect("clicked", self.on_output_pick)
        hbox.pack_start(button, False, False, 10)
        vbox.pack_start(hbox, False, False, 10)
        checkbox = self.checkbox_remove_input = gtk.CheckButton('Remove input after encoding')
        checkbox.set_active(settings['remove-input'])
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
        self.connect("destroy", self.on_quit)
        self.add(vbox)
        self.show_all()
    def init_input_args(self):
        render = self.render
        input_args = []
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
        return input_args
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
    def on_output_pick(self, widget):
        path = self.output_entry.get_text()
        dialog = gtk.FileChooserDialog(
            parent=self,
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
            self.output_entry.set_text(chosen_path)
            dialog.destroy()
            return chosen_path
        elif response == gtk.RESPONSE_CANCEL:
            dialog.destroy()
            return
    def gui_yesno_dialog(self, question, confirm_object=False, confirm_lock=False):
        dialog = gtk.MessageDialog(
            parent = self,
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
            parent = self,
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
        self.output_path = self.output_entry.get_text()
        force_overwrite = False
        if os.path.exists(self.output_path):
            if settings['overwrite']:
                overwrite = True
            else:
                overwrite = self.gui_yesno_dialog("File '%s' already exists. Overwrite?" % self.output_path)
            if overwrite:
                force_overwrite = True
            else:
                return
        t = threading.Thread(target=self.run, name='ffmpeg', kwargs={'overwrite' : force_overwrite})
        t.setDaemon(True)
        t.start()
    def run(self, overwrite=False):
        gobject.idle_add(self.progressbar.set_property, 'visible', True)
        cmd, cmd_args = self.cmd_entry.get_text().split(' ', 1)
        if overwrite:
            cmd += ' -y '
        else:
            cmd += ' -n '
        cmd += cmd_args
        cmd += ' "%s"' % self.output_path
        self.write(cmd+'\n')
        proc = subprocess.Popen([cmd], shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
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
                progress_float = float(status['frame']) / float(render.frames)
                progress_percent = progress_float * 100.0
                progress_string = '%5.2f%%' % progress_percent
                gobject.idle_add(self.progressbar.set_fraction, progress_float)
                gobject.idle_add(self.progressbar.set_text, progress_string)
            proc.poll()
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
        gobject.idle_add(self.console_buffer.insert, self.console_buffer.get_end_iter(), string)

gobject.threads_init()
ffmpeg = Ffmpeg(cmd, render, output_path)
gtk.main()
