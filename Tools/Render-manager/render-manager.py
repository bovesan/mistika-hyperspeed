#!/usr/bin/python
# -*- coding: utf-8 -*-  

import gtk
import os
import subprocess
import sys
import tempfile
import threading
import multiprocessing
import platform
import Queue
import socket
import gobject
import time
import warnings
import json
import shutil
from datetime import datetime
import glob
import signal
import re

import hyperspeed
import hyperspeed.ui
import hyperspeed.afterscript
import hyperspeed.tools
import hyperspeed.utils
import hyperspeed.human
import hyperspeed.stack
import hyperspeed.video
from hyperspeed import mistika

THIS_HOST_ALIAS = 'Submitted by this machine'
OTHER_HOSTS_ALIAS = 'Submitted by others'
THREAD_LIMIT = multiprocessing.cpu_count()
HOSTNAME = socket.gethostname()
UPDATE_RATE = 1.0
COLOR_DEFAULT = '#111111'
TEMPORARY_RENDERS_FOLDER = '/Volumes/SAN3/Limbo'
MAX_RENDER_ATTEMPTS = 3
MAX_AFTERSCRIPT_ATTEMPTS = 1
START_TIME = time.time()

def process_suspended_status(pid):
    try:
        return re.sub(r'\(.*\)', '()', open(os.path.join('/proc', str(pid), 'stat')).readline()).split()[2]=='T'
    except AttributeError:
        return None

class RenderItem(hyperspeed.stack.Render):
    treeview = None
    treestore = None
    row_reference = None
    owner = 'Unknown'
    gui_freeze_render = None
    renders_dict = None
    def __init__(self, path, global_settings, renders_dict):
        super(RenderItem, self).__init__(path)
        self.global_settings = global_settings
        self.renders_dict = renders_dict
        self.duration = hyperspeed.video.frames2tc(self.frames, self.fps)
        description = 'Resolution: %sx%s' % (self.resX, self.resY)
        description += '\nFps: %s' % self.fps
        description += '\nDuration: %s (%s frames)' % (self.duration, self.frames)
        self.settings = {
            'description'          : description,
            'color'                : COLOR_DEFAULT,
            'priority'             : self.ctime,
            'submit_time'          : self.ctime,
            'submit_host'          : HOSTNAME,
            'stage'                : 'render',
            'is_rendering'         : False,
            'render_paused'        : False,
            'render_host'          : None,
            'render_queued'        : False,
            'render_frames'        : 0,
            'renders_failed'       : [],
            'afterscript'          : None,
            'afterscript_paused'   : False,
            'afterscript_host'     : None,
            'afterscript_queued'   : False,
            'afterscript_frames'   : 0,
            'afterscripts_failed'  : [],
            'status'               : 'Not started',
        }
        self.settings_path = os.path.join(os.path.dirname(self.path), self.uid+'.cfg')
        self.settings_read()
        self.set_settings()
        self.prev_treestore_values = None
    def do_render(self, render_processes):
        cmd = ['mistika', '-r', self.path]
        print ' '.join(cmd)
        log_path = self.path + '.log'
        # self.process = subprocess.Popen(cmd, stdout=logfile_h, stderr=subprocess.STDOUT)
        # total time: 4.298 sec, 0.029 sec per frame, 34.665 frames per sec
        self.set_settings({
            'render_host' : HOSTNAME,
            'render_start_time' : time.time(),
            'is_rendering' : True,
            'render_frames' : 0,
        })
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE)
        mistika_bin_pids = []
        with open(log_path, 'w') as log:
            while proc.returncode == None:
                mistika_bin_pids = mistika.get_mistika_bin_pids(proc.pid)
                if len(mistika_bin_pids) > 0:
                    if not mistika_bin_pids[0] in render_processes:
                        render_processes.append(mistika_bin_pids[0])
                if not self.settings['render_queued']:
                    print 'Render aborted'
                    # proc.send_signal(signal.SIGINT)
                    os.kill(mistika_bin_pids[0], signal.SIGINT)
                    break
                if not self.global_settings['render_process']:
                    print 'Render paused'
                    os.kill(mistika_bin_pids[0], signal.SIGSTOP)
                    while not self.global_settings['render_process']:
                        time.sleep(1)
                    os.kill(mistika_bin_pids[0], signal.SIGCONT)
                line = proc.stdout.readline()
                log.write(line)
                if line.startswith('Done:'):
                    self.set_settings({
                        'render_frames' : int(line.split(' ')[1].strip(','))
                    })
                elif line.startswith('total time:'):
                    self.set_settings({
                        'render_frames' : int(self.frames),
                        'render_end_time' : time.time(),
                        'render_elapsed_time' : float(line.split()[2]),
                    })
                proc.poll()
            if proc.returncode == 0:
                print 'Render complete'
                self.set_settings({
                    'render_queued' : False,
                    })
            elif proc.returncode == 1:
                print 'Render process ended with returncode 1'
                self.set_settings({
                    'render_queued' : False,
                    })
            elif proc.returncode == 2:
                self.set_settings({
                    'render_queued' : False,
                    'render_frames' : self.frames,
                    'is_rendering' : False,
                    'status' : 'Render complete',
                })
                if self.settings['afterscript']:
                    self.move_to_stage('afterscript')
            elif proc.returncode == 3:
                print 'Aborted by user'
                self.set_settings({
                    'render_queued' : False,
                    'status' : 'Aborted by user',
                    'is_rendering' : False,
                    })
            else:
                print proc.returncode
                self.set_settings({
                    'renders_failed' :self.settings['renders_failed'] + [
                        self.settings['render_frames']
                    ],
                    'is_rendering' : False,
                })
        # logfile_h.flush()
    def move_to_stage(self, stage):
        # gobject.idle_add(self.gui_remove)
        # self.treestore = None
        # self.row_reference = None
        new_settings = {
            'stage' : stage,
        }
        if stage == 'afterscript':
            new_settings['afterscript_queued'] = True
        self.set_settings(new_settings)
    def gui_remove(self, remove_render=False):
        try:
            row_path = self.row_reference.get_path()
            row_iter = self.treestore.get_iter(row_path)
            self.treestore.remove(row_iter)
        except AttributeError:
            pass
        if remove_render:
            del self.renders_dict[self.uid]
    def set_settings(self, settings={}):
        self.settings.update(settings)
        json_dump = json.dumps(self.settings, indent=4, sort_keys=True)
        try:
            if not os.path.exists(self.settings_path) or open(self.settings_path).read() != json_dump:
                open(self.settings_path, 'w').write(json_dump)
        except IOError:
            print 'Settings file is moved'
            return
        gobject.idle_add(self.gui_update)
    def settings_read(self):
        try:
            self.settings.update(json.loads(open(self.settings_path).read()))
        except (IOError, ValueError) as e:
            pass
    def gui_update(self):
        treestore = self.treestore
        if self.row_reference == None:
            return
        if self.gui_freeze_render:
            return
        new_values = self.treestore_values
        if new_values == self.prev_treestore_values:
            return
        self.prev_treestore_values = new_values
        row_path = self.row_reference.get_path()
        row_iter = treestore.get_iter(row_path)
        print 'Updating tree row: %s' % self.uid
        try:
            treestore[row_path] = self.treestore_values
        except ValueError:
            pass # Just changed stage
    @property
    def render_progress(self):
        try:
            return float(self.settings['render_frames']) / float(self.frames)
        except (KeyError, ZeroDivisionError) as e:
            return 0
    @property
    def afterscript_progress(self):
        try:
            return float(self.settings['afterscript_frames']) / float(self.frames)
        except (KeyError, ZeroDivisionError) as e:
            return 0.0
    def afterscript_pulse(self):
        if self.settings['afterscript_host'] == None:
            return -1
        value = self.afterscript_progress
        if value > 0:
            return -1
        fraction = (time.time() - START_TIME) * 5.0
        return int(fraction)
    def attempts_string(self, current, total):
        if current == 0:
            return ''
        return "%i/%i" % (current,total)
    def progress_string(self, value):
        if value > 0:
            return '%5.2f%%' % (value * 100.0)
        else:
            return ''
    @property
    def treestore_values(self):
        if self.settings['stage'] == 'render':
            return [
                self.uid, # Id
                self.project, # Project
                self.prettyname, # Name
                self.render_progress * 100.0, # Progress
                '%5.2f%%' % (self.render_progress * 100.0), # Progress str
                self.settings['status'], # Status
                self.settings['afterscript'], # Afterscript
                self.settings['submit_time'], # Added time
                self.settings['description'], # Description
                hyperspeed.human.time(self.settings['submit_time']), # Human time
                self.settings['is_rendering'] , # 10 Progress visible
                self.settings['priority'],
                self.settings['submit_host'],
                self.settings['render_host'],
                self.settings['color'],
                not self.settings['is_rendering'], # Status visible
                self.duration, # 16
                self.private, 
                self.settings['submit_host'] == HOSTNAME,
                self.settings['render_queued'],
                self.render_progress < 1, # 20 Settings visible
                self.attempts_string(len(self.settings['renders_failed']), MAX_RENDER_ATTEMPTS), # 21 Failed attempts
                self.format,
            ]
        else:
            return [
                self.uid, # Id
                self.project, # Project
                self.prettyname, # Name
                self.afterscript_progress * 100.0, # Progress
                self.progress_string(self.afterscript_progress), # Progress str
                self.settings['status'], # Status
                self.settings['afterscript'], # Afterscript
                self.settings['submit_time'], # Added time
                self.settings['description'], # Description
                hyperspeed.human.time(self.settings['submit_time']), # Human time
                bool(self.settings['afterscript_host']) , # 10 Progress visible
                self.settings['priority'],
                self.settings['submit_host'],
                self.settings['afterscript_host'],
                self.settings['color'],
                not bool(self.settings['afterscript_host']), # Status visible
                self.duration, # 16
                self.private,
                self.settings['submit_host'] == HOSTNAME,
                self.settings['afterscript_queued'],
                self.afterscript_progress < 1, # 20 Settings visible
                self.attempts_string(len(self.settings['afterscripts_failed']), MAX_AFTERSCRIPT_ATTEMPTS), # 21 Failed attempts
                self.format,
                self.afterscript_pulse(), # pulse
            ]
class RendersDelete(object):
    def __init__(self, renders):
        self.files = []
        self.execute(renders)
    def trash_path(self, f_path):
        f_dirname, f_basename = os.path.split(f_path)
        return os.path.join(f_dirname, '.trash', f_basename)
    def execute(self, renders):
        for render in renders:
            render_files = glob.glob(re.sub('rnd$', '*', render.path))
            # Remove settings at last so they are not recreated by mistake
            try:
                render_files.remove(render.settings_path)
                render_files.append(render.settings_path)
            except ValueError:
                pass # Render had no settings
            for f_path in render_files:
                self.files.append(f_path)
                os.renames(f_path, self.trash_path(f_path))
                # print '%s -> %s' % (f_path, self.trash_path(f_path))
    def undo(self):
        for f_path in reversed(self.files):
            os.renames(self.trash_path(f_path), f_path)
            # print '%s -> %s' % (self.trash_path(f_path), f_path)

class RenderManagerWindow(hyperspeed.ui.Window):
    def __init__(self):
        super(RenderManagerWindow, self).__init__(
            title='Hyperspeed render manager',
            settings_default = {
                'shared_queues_folder' : '',
                'render_process' : True,
                'afterscript_process' : True,
            }
        )
        self.renders = {}
        self.threads = []
        self.render_threads = []
        self.render_processes = []
        self.render_threads_limit = 1
        self.afterscript_threads = []
        self.afterscript_processes = []
        self.afterscript_threads_limit = 1
        self.queue_io = Queue.Queue()
        self.config_rw()
        self.hotkeys.append({
                'combination' : ['Delete'],
                'method' : self.on_renders_delete,
            })
        vbox = gtk.VBox(False, 10)
        # vbox.pack_start(self.init_toolbar(), False, False, 10)

        self.afterscripts_model_refresh()
        gobject.timeout_add(5000, self.afterscripts_model_refresh)

        vbox.pack_start(self.settings_panel(), False, False, 10)
        vbox.pack_start(self.init_render_queue_window())
        vbox.pack_start(self.init_afterscript_queue_window())

        footer = gtk.HBox(False, 10)
        quitButton = gtk.Button('Quit')
        quitButton.set_size_request(70, 30)
        quitButton.connect("clicked", self.on_quit)
        footer.pack_end(quitButton, False, False)

        vbox.pack_end(footer, False, False, 10)

        self.add(vbox)

        self.show_all()

        self.comboEditable = None
        gobject.idle_add(self.bring_to_front)
        gobject.timeout_add(1000, self.gui_periodical_updates)
        gobject.idle_add(self.gui_batch_folders_setup)
    def on_quit(self, widget):
        for pid in self.render_processes:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
        super(RenderManagerWindow, self).on_quit(widget)
    def afterscripts_model_refresh(self):
        try:
            self.afterscripts_model
        except AttributeError:
            self.afterscripts_model = gtk.ListStore(str)
            self.afterscripts_prev = []
        afterscripts = []
        for afterscript in hyperspeed.afterscript.list():
            afterscripts.append(afterscript)
        if afterscripts != self.afterscripts_prev:
            self.afterscripts_prev = afterscripts
            new_model = gtk.ListStore(str)
            for afterscript in afterscripts:
                new_model.append([afterscript])
            self.afterscripts_model = new_model
        return True
    def gui_batch_folders_setup(self):
        batchpath_fstype = subprocess.Popen(['df', '--output=fstype', mistika.settings['BATCHPATH']],
            stdout=subprocess.PIPE).communicate()[0].splitlines()[-1]
        if batchpath_fstype in ['nfs', 'cifs', 'cvfs']:
            private_queue_folder = os.path.expanduser('~/BATCH_QUEUES')
            setup = hyperspeed.ui.dialog_yesno(
                parent=self,
                question=
'''It looks like the Mistika batch queue folder is on a shared file system.
To separate private and public jobs, the batch queue folder must be unique for each computer.
Any public jobs will be moved to a shared location.

Change local batch queue folder to %s?''' % private_queue_folder)
            if not setup:
                return
            if self.settings['shared_queues_folder'] == '':
                self.settings['shared_queues_folder'] = mistika.settings['BATCHPATH']
                self.shared_queue_entry.set_text(mistika.settings['BATCHPATH'])
            if self.set_mistika_batchpath(private_queue_folder):
                self.batch_queue_entry.set_text(private_queue_folder)
    def get_selected_treeview(self):
        treeviews = [
            self.render_treeview,
            self.afterscript_treeview
        ]
        for treeview in treeviews:
            if treeview.is_focus():
                return treeview
    def get_selected_renders(self, treeview=None):
        renders = []
        if not treeview:
            treeview = self.get_selected_treeview()
            if treeview:
                selection = treeview.get_selection()
                (treestore, row_paths) = selection.get_selected_rows()
                row_paths = sorted(row_paths)
                for row_path in row_paths:
                    renders.append(self.renders[treestore[row_path][0]])
        return renders
    def set_mistika_batchpath(self, batchpath):
        cache_queue_folder = os.path.join(batchpath, 'Cache')
        default_queues = [
            os.path.join(batchpath, 'Private'),
            os.path.join(batchpath, 'Public'),
            cache_queue_folder,
        ]
        for queue_folder in default_queues:
            if not os.path.isdir(queue_folder):
                try:
                    os.makedirs(queue_folder)
                    open(os.path.join(queue_folder, 'priority.cfg'), 'w').write('1\n')
                except OSError as e:
                    hyperspeed.ui.dialog_error(self,
                        'Could not create folder: %s\n%s' % (batchpath, e))
        if not os.path.isdir(batchpath):
            return
        hyperspeed.mistika.set_settings({
            'BATCHPATH' : batchpath,
            'CACHE_BATCH_PATH' : cache_queue_folder
        })
        return True
    def on_batchpath_change(self, widget=None):
        self.set_mistika_batchpath(widget.get_text())
    def settings_panel(self):
        expander = gtk.Expander('Settings')
        vbox = gtk.VBox()
        hbox = gtk.HBox()
        label =  gtk.Label('Batch queues folder:')
        hbox.pack_start(label, False, False, 5)
        entry = self.batch_queue_entry = gtk.Entry()
        entry.set_text(mistika.settings['BATCHPATH'])
        hbox.pack_start(entry)
        button = self.shared_queue_pick_button = gtk.Button('...')
        button.connect("clicked", self.on_folder_pick, entry, 'Select batch queue folder')
        entry.connect('changed', self.on_batchpath_change)
        hbox.pack_start(button, False, False, 5)
        vbox.pack_start(hbox, False, False, 5)
        hbox = gtk.HBox()
        label =  gtk.Label('Shared queue folder:')
        hbox.pack_start(label, False, False, 5)
        entry = self.shared_queue_entry = gtk.Entry()
        entry.set_text(self.settings['shared_queues_folder'])
        entry.connect('changed', self.on_settings_change, 'shared_queues_folder')
        hbox.pack_start(entry)
        button = self.shared_queue_pick_button = gtk.Button('...')
        button.connect("clicked", self.on_folder_pick, entry, 'Select shared queue folder')
        hbox.pack_start(button, False, False, 5)
        vbox.pack_start(hbox, False, False, 5)
        vbox.pack_start(gtk.HSeparator(), False, False, 10)
        expander.add(vbox)
        return expander
    def gui_process_renders(self):
        if self.process_queue_checkbox.get_active():
            if not self.gui_process_start_renders(THIS_HOST_ALIAS):
                if self.process_others_checkbox.get_active():
                    self.gui_process_start_renders(OTHER_HOSTS_ALIAS)
    def gui_process_start_renders(self, host_group):
        model = self.render_treestore
        row_path = self.row_references_render[host_group].get_path()
        row_iter = model.get_iter(row_path)
        for n in range(model.iter_n_children(row_iter)):
            child_iter = model.iter_nth_child(row_iter, n)
            child_id = model.get_value(child_iter, 0)
            render = self.renders[child_id]
            if render.settings['render_queued']:
                if render.settings['render_frames'] < render.frames:
                    self.render_start(render)
                    return True
    def gui_process_afterscripts(self):
        if self.process_queue_afterscripts_checkbox.get_active():
            if not self.gui_process_start_afterscripts(THIS_HOST_ALIAS):
                if self.process_others_afterscripts_checkbox.get_active():
                    self.gui_process_start_afterscripts(OTHER_HOSTS_ALIAS)
    def gui_process_start_afterscripts(self, host_group):
        model = self.afterscript_treestore
        row_path = self.row_references_afterscript[host_group].get_path()
        row_iter = model.get_iter(row_path)
        for n in range(model.iter_n_children(row_iter)):
            child_iter = model.iter_nth_child(row_iter, n)
            child_id = model.get_value(child_iter, 0)
            try:
                render = self.renders[child_id]
            except KeyError:
                print '%s has been removed'
                continue
            if not render.settings['afterscript']:
                # print 'No afterscript selected:', render.prettyname
                continue
            if not render.settings['afterscript_queued']:
                # print 'Not afterscript queued:', render.prettyname
                continue
            if render.settings['afterscript_frames'] >= render.frames:
                # print 'Afterscript is already complete:', render.prettyname
                continue
            if render.settings['afterscript_host']:
                # print 'Afterscript is already running:', render.prettyname
                continue
            self.afterscript_start(render)
            return True
    def gui_periodical_updates(self):
        self.gui_process_renders()
        self.gui_process_afterscripts()
        self.launch_thread(self.io_populate_render_queue)
        return True # Must return true to keep repeating
    def on_folder_pick(self, widget, entry, title):
        folder = entry.get_text()
        if not os.path.isdir(folder):
            folder = os.path.join(mistika.projects_folder)
        dialog = gtk.FileChooserDialog(
            title=title,
            parent=None,
            action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK),
            backend=None
        )
        dialog.add_shortcut_folder(folder)
        dialog.set_current_folder(folder)
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            entry.set_text(dialog.get_filename())
        elif response == gtk.RESPONSE_CANCEL:
            print 'Closed, no files selected'
        dialog.destroy()
    def bring_to_front(self):
        self.present()
    def config_rw(self, write=False):
        pass
    def init_render_queue_window(self):
        settings = self.settings
        self.render_queue = {}
        row_references = self.row_references_render = {}
        treeview       = self.render_treeview  = gtk.TreeView()
        treeview.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        treestore      = self.render_treestore = gtk.TreeStore(
            str,  # 00 Id
            str,  # 01 Project
            str,  # 02 Name
            int,  # 03 Progress
            str,  # 04 Progress str
            str,  # 05 Status
            str,  # 06 Afterscript
            float,# 07 Added time
            str,  # 08 Description
            str,  # 09 Human time
            bool, # 10 Is rendering
            float,# 11 Priority
            str,  # 12 Submit host
            str,  # 13 Render host
            str,  # 14 Color
            bool, # 15 Status visible
            str,  # 16 Duration
            bool, # 17 Private
            bool, # 18 This host
            bool, # 19 Queued
            bool, # 20 Settings visible
            str,  # 21 Failed attempts
            str,  # 22 Format
        )
        treestore.set_sort_column_id(11, gtk.SORT_ASCENDING)
        tree_filter    = self.render_queue_filter    = treestore.filter_new();
        # tree.connect('button-press-event' , self.button_press_event)
        for queue_name in [THIS_HOST_ALIAS, OTHER_HOSTS_ALIAS]:
            row_iter = treestore.append(None, None)
            row_path = treestore.get_path(row_iter)
            treestore[row_path][1] = queue_name
            row_references[queue_name] = gtk.TreeRowReference(treestore, row_path)
        vbox = gtk.VBox(False, 10)
        headerBox = gtk.HBox(False, 5)
        headerLabel  = gtk.Label('<span size="large"><b>Render queue:</b></span>')
        headerLabel.set_use_markup(True)
        headerBox.pack_start(headerLabel, False, False, 5)
        vbox.pack_start(headerBox, False, False, 2)
        toolbar = gtk.HBox(False, 2)
        checkButton = self.process_queue_checkbox = gtk.CheckButton('Process queue')
        checkButton.set_property("active", settings['render_process'])
        checkButton.connect("toggled", self.on_settings_change, 'render_process')
        toolbar.pack_start(checkButton, False, False, 5)
        checkButton = self.process_others_checkbox = gtk.CheckButton('Process jobs for other hosts')
        checkButton.set_property("active", False)
        toolbar.pack_start(checkButton, False, False, 5)
        checkButton = self.autoqueue_checkbox = gtk.CheckButton('Autoqueue new jobs from this machine')
        checkButton.set_property("active", False)
        toolbar.pack_start(checkButton, False, False, 5)
        button = gtk.CheckButton('Autostart jobs from this machine')
        checkButton.set_property("active", False)
        toolbar.pack_start(checkButton, False, False, 5)
        vbox.pack_start(toolbar, False, False, 2)
        afterscriptsBox = gtk.HBox(False, 5)
        column = gtk.TreeViewColumn('Project', gtk.CellRendererText(), text=1)
        column.set_resizable(True)
        column.set_expand(False)
        treeview.append_column(column)
        column = gtk.TreeViewColumn('Name', gtk.CellRendererText(), text=2)
        column.set_resizable(True)
        column.set_expand(True)
        treeview.append_column(column)
        column = gtk.TreeViewColumn('Duration', gtk.CellRendererText(), text=16)
        column.set_resizable(True)
        column.set_expand(False)
        treeview.append_column(column)
        column = gtk.TreeViewColumn('Format', gtk.CellRendererText(), text=22)
        column.set_resizable(True)
        column.set_expand(False)
        treeview.append_column(column)
        column = gtk.TreeViewColumn('Submit time', gtk.CellRendererText(), text=9)
        column.set_resizable(True)
        column.set_expand(False)
        treeview.append_column(column)
        column = gtk.TreeViewColumn('Submit node', gtk.CellRendererText(), text=12)
        column.set_resizable(True)
        column.set_expand(False)
        treeview.append_column(column)
        cell = gtk.CellRendererToggle()
        cell.connect("toggled", self.on_toggle_private, treeview)
        column = gtk.TreeViewColumn('Private', cell, active=17, visible=18)
        column.set_resizable(True)
        column.set_expand(False)
        treeview.append_column(column)
        cell = gtk.CellRendererToggle()
        cell.connect("toggled", self.on_render_settings_change, None, 'render_queued', treestore)
        column = gtk.TreeViewColumn('Queued', cell, active=19, visible=20)
        column.set_resizable(True)
        column.set_expand(False)
        treeview.append_column(column)
        column = gtk.TreeViewColumn('Render node', gtk.CellRendererText(), text=13)
        column.set_resizable(True)
        column.set_expand(False)
        treeview.append_column(column)
        column = gtk.TreeViewColumn('Attempts', gtk.CellRendererText(), text=21)
        column.set_resizable(True)
        column.set_expand(False)
        treeview.append_column(column)
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn('Status')
        column.pack_start(cell, False)
        column.set_attributes(cell, text=5, foreground=14, visible=15)
        cell = gtk.CellRendererProgress()
        column.pack_start(cell, True)
        column.set_attributes(cell, value=3, text=4, visible=10)
        column.set_resizable(True)
        column.set_expand(True)
        treeview.append_column(column)
        cell = gtk.CellRendererCombo()
        cell.set_property("editable", True)
        cell.set_property("has-entry", False)
        cell.set_property("text-column", 0)
        cell.set_property("model", self.afterscripts_model)
        # cell.connect('clicked', hyperspeed.ui.event_debug)
        cell.connect('editing-started', self.on_edit_afterscript, True, treestore)
        cell.connect("edited", self.on_render_settings_change, 'afterscript', treestore)
        column = gtk.TreeViewColumn("Afterscript", cell, text=6)
        # column.connect('clicked', hyperspeed.ui.event_debug)
        column.set_resizable(True)
        column.set_expand(True)
        treeview.append_column(column)
        treeview.set_tooltip_column(8)
        treeview.set_rules_hint(True)
        treeview.set_model(treestore)
        treeview.expand_all()
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(treeview)
        afterscriptsBox.pack_start(scrolled_window)
        vbox_move = gtk.VBox(False, 3)
        vbox_move.set_size_request(30,80)
        gtk.stock_add([(gtk.STOCK_GO_UP, "", 0, 0, "")])
        button = gtk.Button(stock=gtk.STOCK_GO_UP)
        vbox_move.pack_start(button)
        button.connect('clicked', self.on_move, -1, treeview)
        gtk.stock_add([(gtk.STOCK_GO_DOWN, "", 0, 0, "")])
        button = gtk.Button(stock=gtk.STOCK_GO_DOWN)
        button.connect('clicked', self.on_move, +1, treeview)
        vbox_move.pack_start(button)
        afterscriptsBox.pack_start(vbox_move, False, False)

        # treeview.connect('event', hyperspeed.ui.event_debug, treeview)
        treeview.connect('button_press_event', self.on_render_button_press_event, treeview)

        self.launch_thread(self.io_populate_render_queue, kwargs={ 'first_run' : True })
        vbox.pack_start(afterscriptsBox, True, True, 5)
        return vbox
    def render_item_menu(self):
        selection = self.render_treeview.get_selection()
        (treestore, row_paths) = selection.get_selected_rows()
        row_paths = sorted(row_paths)
        menu = gtk.Menu()
        if len(row_paths) == 1:
            newi = gtk.ImageMenuItem(gtk.STOCK_INFO)
            newi.connect("activate", self.on_render_info)
            newi.show()
            menu.append(newi)
        enqueue = False
        reset = False
        abort = False
        renders = []
        for row_path in row_paths:
            render = self.renders[treestore[row_path][0]]
            renders.append(render)
            if render.settings['render_frames'] < render.frames:
                enqueue = True
            else:
                reset = True
            if render.settings['is_rendering']:
                abort = True
        if enqueue:
            newi = gtk.ImageMenuItem(gtk.STOCK_MEDIA_PLAY)
            newi.set_label('Enqueue')
            newi.connect("activate", self.on_render_enqueue)
            newi.show()
            menu.append(newi)
        if reset:
            newi = gtk.ImageMenuItem(gtk.STOCK_UNDO)
            newi.set_label('Reset')
            newi.connect("activate", self.on_render_reset)
            newi.show()
            menu.append(newi)
        if abort:
            newi = gtk.ImageMenuItem(gtk.STOCK_CANCEL)
            newi.set_label('Abort')
            newi.connect("activate", self.on_render_abort)
            newi.show()
            menu.append(newi)
        newi = gtk.ImageMenuItem(gtk.STOCK_DELETE)
        newi.set_label('Remove')
        newi.connect("activate", self.on_renders_delete, renders)
        newi.show()
        menu.append(newi)
        menu.set_title('Popup')
        return menu
    def afterscript_item_menu(self):
        selection = self.afterscript_treeview.get_selection()
        (treestore, row_paths) = selection.get_selected_rows()
        row_paths = sorted(row_paths)
        menu = gtk.Menu()
        if len(row_paths) == 1:
            newi = gtk.ImageMenuItem(gtk.STOCK_INFO)
            newi.connect("activate", self.on_afterscript_info)
            newi.show()
            menu.append(newi)
        enqueue = False
        reset = False
        abort = False
        renders = []
        for row_path in row_paths:
            render = self.renders[treestore[row_path][0]]
            renders.append(render)
            if render.settings['afterscript_frames'] < render.frames:
                enqueue = True
            else:
                reset = True
            if render.settings['afterscript_host']:
                abort = True
        if enqueue:
            newi = gtk.ImageMenuItem(gtk.STOCK_MEDIA_PLAY)
            newi.set_label('Enqueue')
            newi.connect("activate", self.on_afterscript_enqueue)
            newi.show()
            menu.append(newi)
        if reset:
            newi = gtk.ImageMenuItem(gtk.STOCK_UNDO)
            newi.set_label('Reset')
            newi.connect("activate", self.on_afterscript_reset)
            newi.show()
            menu.append(newi)
        if abort:
            newi = gtk.ImageMenuItem(gtk.STOCK_CANCEL)
            newi.set_label('Abort')
            newi.connect("activate", self.on_afterscript_abort)
            newi.show()
            menu.append(newi)
        newi = gtk.ImageMenuItem(gtk.STOCK_DELETE)
        newi.set_label('Remove')
        newi.connect("activate", self.on_renders_delete, renders)
        newi.show()
        menu.append(newi)
        menu.set_title('Popup')
        return menu
    def on_toggle_private(self, cellrenderertoggle, path, treeview):
        was_private = cellrenderertoggle.get_active()
        treestore = treeview.get_model()
        try: # If there is a filter in the middle
            treestore = treestore.get_model()
        except AttributeError:
            pass
        uid = treestore[path][0]
        render = self.renders[uid]
        current_folder = os.path.dirname(render.path)
        if was_private:
            new_folder = os.path.join(self.settings['shared_queues_folder'], 'Public')
        else:
            new_folder = os.path.join(mistika.settings['BATCHPATH'], 'Private')
        errors = []
        if not os.path.isdir(new_folder):
            try:
                os.makedirs(new_folder)
                open(os.path.join(queue_folder, 'priority.cfg'), 'w').write('1\n')
            except OSError as e:
                print e
                hyperspeed.ui.dialog_error(self, str(e))
                return
        # Move settings first to avoid reset
        new_settings_path = render.settings_path.replace(current_folder, new_folder, 1)
        try:
            # print 'Moving settings: %s -> %s' % (render.settings_path, new_settings_path)
            shutil.move(render.settings_path, new_settings_path)
        except IOError as e:
            errors.append(str(e))
        for current_path in glob.glob(os.path.join(current_folder, render.uid+'.*')):
            new_path = current_path.replace(
            current_folder, new_folder, 1)
            try:
                # print 'Moving files: %s -> %s' % (current_path, new_path)
                shutil.move(current_path, new_path)
            except IOError as e:
                errors.append(str(e))
        if len(errors) > 0:
            print repr(errors)
            hyperspeed.ui.dialog_error(self, '\n'.join(errors))
        self.launch_thread(self.io_populate_render_queue)
    def on_move(self, widget, direction, treeview):
        selection = treeview.get_selection()
        (treestore, row_paths) = selection.get_selected_rows()
        row_paths = sorted(row_paths, reverse=direction>0)
        row_references = []
        for row_path in row_paths:
            row_references.append(gtk.TreeRowReference(treestore, row_path))
        for row_reference in row_references:
            row_path = row_reference.get_path()
            file_id = treestore[row_path][0]
            render = self.renders[file_id]
            row_path_parent = row_path[:-1]
            row_path_lastbit = row_path[1]
            if direction < 0 and row_path_lastbit == 0:
                print 'Cannot move before first position'
                return
            path_one_away = row_path_parent+(row_path_lastbit+direction,)
            if direction > 0:
                path_two_away = row_path_parent+(row_path_lastbit+(direction+1),)
            else:
                path_two_away = row_path_parent+(row_path_lastbit+(direction-1),)
            try:
                priority_one_away = treestore[path_one_away][11]
            except IndexError:
                print 'Cannot move after end'
                return
            try:
                priority_two_away = treestore[path_two_away][11]
            except IndexError:
                priority_two_away = priority_one_away+(direction*0.01)
            priority_between = priority_one_away - ((priority_one_away - priority_two_away) * 0.5)
            print 'New priority: %s' % priority_between
            treestore[row_path][11] = priority_between
            render.set_settings({
                'priority' :  priority_between
            })
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
    def init_afterscript_queue_window(self):
        settings = self.settings
        self.afterscript_queue = {}
        row_references = self.row_references_afterscript = {}
        treeview       = self.afterscript_treeview  = gtk.TreeView()
        treeview.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        treestore      = self.afterscript_treestore = gtk.TreeStore(
            str,  # 00 Id
            str,  # 01 Project
            str,  # 02 Name
            int,  # 03 Progress
            str,  # 04 Progress str
            str,  # 05 Status
            str,  # 06 Afterscript
            float,# 07 Added time
            str,  # 08 Description
            str,  # 09 Human time
            bool, # 10 Is afterscripting
            float,# 11 Priority
            str,  # 12 Submit host
            str,  # 13 Afterscript host
            str,  # 14 Color
            bool, # 15 Status visible
            str,  # 16 Duration
            bool, # 17 Private
            bool, # 18 This host
            bool, # 19 Queued
            bool, # 20 Settings visible
            str,  # 21 Failed attempts
            str,  # 22 Format
            int,  # 23 Progress pulse
        )
        treestore.set_sort_column_id(11, gtk.SORT_ASCENDING)
        tree_filter    = self.afterscript_queue_filter    = treestore.filter_new();
        # tree.connect('button-press-event' , self.button_press_event)
        for queue_name in [THIS_HOST_ALIAS, OTHER_HOSTS_ALIAS]:
            row_iter = treestore.append(None, None)
            row_path = treestore.get_path(row_iter)
            treestore[row_path][1] = queue_name
            row_references[queue_name] = gtk.TreeRowReference(treestore, row_path)
        vbox = gtk.VBox(False, 10)
        headerBox = gtk.HBox(False, 5)
        headerLabel  = gtk.Label('<span size="large"><b>Afterscript queue:</b></span>')
        headerLabel.set_use_markup(True)
        headerBox.pack_start(headerLabel, False, False, 5)
        vbox.pack_start(headerBox, False, False, 2)
        toolbar = gtk.HBox(False, 2)
        checkButton = self.process_queue_afterscripts_checkbox = gtk.CheckButton('Process queue')
        checkButton.set_property("active", settings['afterscript_process'])
        checkButton.connect("toggled", self.on_settings_change, 'afterscript_process')
        toolbar.pack_start(checkButton, False, False, 5)
        checkButton = self.process_others_afterscripts_checkbox = gtk.CheckButton('Process jobs for other hosts')
        checkButton.set_property("active", False)
        toolbar.pack_start(checkButton, False, False, 5)
        checkButton = self.autoqueue_checkbox = gtk.CheckButton('Autoqueue new jobs from this machine')
        checkButton.set_property("active", False)
        toolbar.pack_start(checkButton, False, False, 5)
        vbox.pack_start(toolbar, False, False, 2)
        afterscriptsBox = gtk.HBox(False, 5)
        column = gtk.TreeViewColumn('Project', gtk.CellRendererText(), text=1)
        column.set_resizable(True)
        column.set_expand(False)
        treeview.append_column(column)
        column = gtk.TreeViewColumn('Name', gtk.CellRendererText(), text=2)
        column.set_resizable(True)
        column.set_expand(True)
        treeview.append_column(column)
        column = gtk.TreeViewColumn('Duration', gtk.CellRendererText(), text=16)
        column.set_resizable(True)
        column.set_expand(False)
        treeview.append_column(column)
        column = gtk.TreeViewColumn('Format', gtk.CellRendererText(), text=22)
        column.set_resizable(True)
        column.set_expand(False)
        treeview.append_column(column)
        column = gtk.TreeViewColumn('Submit time', gtk.CellRendererText(), text=9)
        column.set_resizable(True)
        column.set_expand(False)
        treeview.append_column(column)
        column = gtk.TreeViewColumn('Submit node', gtk.CellRendererText(), text=12)
        column.set_resizable(True)
        column.set_expand(False)
        treeview.append_column(column)
        cell = gtk.CellRendererToggle()
        cell.connect("toggled", self.on_render_settings_change, None, 'afterscript_queued', treestore)
        column = gtk.TreeViewColumn('Queued', cell, active=19, visible=20)
        column.set_resizable(True)
        column.set_expand(False)
        treeview.append_column(column)
        column = gtk.TreeViewColumn('Afterscript node', gtk.CellRendererText(), text=13)
        column.set_resizable(True)
        column.set_expand(False)
        treeview.append_column(column)
        column = gtk.TreeViewColumn('Attempts', gtk.CellRendererText(), text=21)
        column.set_resizable(True)
        column.set_expand(False)
        treeview.append_column(column)
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn('Status')
        column.pack_start(cell, False)
        column.set_attributes(cell, text=5, foreground=14, visible=15)
        cell = gtk.CellRendererProgress()
        column.pack_start(cell, True)
        column.set_attributes(cell, value=3, text=4, visible=10, pulse=23)
        column.set_resizable(True)
        column.set_expand(True)
        treeview.append_column(column)

        cell = gtk.CellRendererCombo()
        cell.set_property("editable", True)
        cell.set_property("has-entry", False)
        cell.set_property("text-column", 0)
        cell.set_property("model", self.afterscripts_model)
        # cell.connect('event', hyperspeed.ui.event_debug)
        cell.connect('editing-started', self.on_edit_afterscript, True, treestore)
        cell.connect("edited", self.on_render_settings_change, 'afterscript', treestore)
        column = gtk.TreeViewColumn("Afterscript", cell, text=6)
        # column.connect('clicked', hyperspeed.ui.event_debug)
        column.set_resizable(True)
        column.set_expand(True)
        treeview.append_column(column)
        treeview.set_tooltip_column(8)
        treeview.set_rules_hint(True)
        treeview.set_model(treestore)
        treeview.expand_all()
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(treeview)
        afterscriptsBox.pack_start(scrolled_window)
        vbox_move = gtk.VBox(False, 3)
        vbox_move.set_size_request(30,80)
        gtk.stock_add([(gtk.STOCK_GO_UP, "", 0, 0, "")])
        button = gtk.Button(stock=gtk.STOCK_GO_UP)
        vbox_move.pack_start(button)
        button.connect('clicked', self.on_move, -1, treeview)
        gtk.stock_add([(gtk.STOCK_GO_DOWN, "", 0, 0, "")])
        button = gtk.Button(stock=gtk.STOCK_GO_DOWN)
        button.connect('clicked', self.on_move, +1, treeview)
        vbox_move.pack_start(button)
        afterscriptsBox.pack_start(vbox_move, False, False)

        # treeview.connect('event', hyperspeed.ui.event_debug, treeview)
        treeview.connect('button_press_event', self.on_afterscript_button_press_event, treeview)

        # self.launch_thread(self.io_populate_afterscript_queue, kwargs={ 'first_run' : True })
        vbox.pack_start(afterscriptsBox, True, True, 5)
        return vbox
    def io_parse_queue_folder(self, queue_folder, private=False):
        renders = self.renders
        hostname = socket.gethostname()
        for queue_name in os.listdir(queue_folder):
            queue_path = os.path.join(queue_folder, queue_name)
            try:
                for file_name in os.listdir(queue_path):
                    file_path = os.path.join(queue_path, file_name)
                    file_id, file_ext = os.path.splitext(file_path)
                    if file_ext != '.rnd':
                        continue
                    render = RenderItem(file_path, self.settings, renders)
                    id_path = os.path.join(os.path.dirname(render.path), render.uid+'.rnd')
                    if not os.path.basename(render.path) == id_path:
                        os.rename(render.path, id_path)
                    if render.settings['afterscript_host'] == HOSTNAME:
                        try:
                            os.kill(render.settings['afterscript_pid'], 0)
                        except (OSError, KeyError) as e:
                            render.set_settings({
                                'afterscript_host' : None,
                            })
                    if private:
                        if not queue_name.lower().startswith('private'):
                            shared_file_path = file_path.replace(
                                mistika.settings['BATCHPATH'], self.settings['shared_queues_folder'], 1)
                            try:
                                shutil.move(file_path, shared_file_path)
                                print 'Moved %s to %s' % (file_path, shared_file_path)
                                continue
                            except IOError as e:
                                print e
                    file_size = os.path.getsize(file_path)
                    if not render.uid in renders:
                        renders[render.uid] = render
                    else:
                        render = renders[render.uid]
                    render.private = private
                    render.path = file_path
                    render.settings_read()
            except OSError as e:
                pass
    def io_populate_render_queue(self, first_run=False):
        self.io_parse_queue_folder(mistika.settings['BATCHPATH'], private=True)
        self.io_parse_queue_folder(self.settings['shared_queues_folder'])
        renders = self.renders
        for render_id in renders.keys():
            if not os.path.exists(renders[render_id].path):
                gobject.idle_add(renders[render_id].gui_remove, True)
        gobject.idle_add(self.gui_update_render_queue, first_run)
    def gui_update_render_queue(self, expand=False):
        renders = self.renders
        for file_id in sorted(renders):
            render = renders[file_id]
            if render.settings['stage'] == 'render':
                render.treeview = self.render_treeview
                if render.settings['submit_host'] == HOSTNAME:
                    parent_row_reference = self.row_references_render[THIS_HOST_ALIAS]
                else:
                    parent_row_reference = self.row_references_render[OTHER_HOSTS_ALIAS]
            else:
                render.treeview = self.afterscript_treeview
                if render.settings['submit_host'] == HOSTNAME:
                    parent_row_reference = self.row_references_afterscript[THIS_HOST_ALIAS]
                else:
                    parent_row_reference = self.row_references_afterscript[OTHER_HOSTS_ALIAS]
            treestore = render.treeview.get_model()
            parent_row_path = parent_row_reference.get_path()
            parent_row_iter = treestore.get_iter(parent_row_path)
            if not render.treestore == treestore:
                if render.treestore != None:
                    row_path = render.row_reference.get_path()
                    row_iter = render.treestore.get_iter(row_path)
                    render.treestore.remove(row_iter)
                row_iter = treestore.append(parent_row_iter, render.treestore_values)
                row_path = treestore.get_path(row_iter)
                render.row_reference = gtk.TreeRowReference(treestore, row_path)
                render.treestore = treestore
            else:
                render.gui_update()
        if expand:
            self.render_treeview.expand_all()
            self.afterscript_treeview.expand_all()
    def on_edit_afterscript(self, cell, widget, path, value, treestore):
        file_id = treestore[path][0]
        render = self.renders[file_id]
        render.gui_freeze_render = True
        widget.connect('notify::popup-shown', self.on_edit_afterscript_popup, render, cell)
    def on_edit_afterscript_popup(self, widget, status, render, cell):
        if widget.get_property('popup-shown'):
            render.gui_freeze_render = True
        else:
            render.gui_freeze_render = False
            cell.stop_editing(False)
    def on_render_settings_change(self, cell, path, value, setting_key, treestore):
        if hasattr(cell, 'get_active'): # Checkbox
            value = not cell.get_active()
        file_id = treestore[path][0]
        render = self.renders[file_id]
        render.gui_freeze_render = False
        if value == 'None':
            value = None
        render.set_settings({
            setting_key : value
        })
        if setting_key == 'afterscript':
            if render.render_progress >= 1.0 and render.settings['stage'] != 'afterscript':
                render.move_to_stage('afterscript')
                return
        self.launch_thread(self.io_populate_render_queue)
    def on_editing_started(self, cell, editable, path):
        print 'on_editing_started()'
        self.comboEditable = editable
    def on_combo_changed(self, cell, path, newiter):
        print 'on_combo_changed'
        e = gtk.gdk.Event(gtk.gdk.FOCUS_CHANGE)
        e.window = self.window
        e.send_event = True
        e.in_ = False
        self.comboEditable.emit('focus-out-event', e)
    def on_render_info(self, widget, *ignore):
        treestore = self.render_treestore
        treepath = self.render_queue_selected_path
        path = treestore[treepath][0]
        render = self.renders[path]
        message = render.uid
        message += '\nPrivate: %s' % render.private
        for k, v in render.settings.iteritems():
            message += '\n%s: %s' % (k, v)
        self.gui_info_dialog(message)
    def on_renders_delete(self, widget=False, renders=[]):
        if renders == []:
            renders = self.get_selected_renders()
        for render in renders:
            for dependency in render.output_stack.dependencies:
                if dependency.path.startswith(TEMPORARY_RENDERS_FOLDER):
                    print 'Delete intermediate render file: %s' % dependency.path
            self.history.append(RendersDelete(renders))
    def on_render_reset(self, widget, *ignore):
        selection = self.render_treeview.get_selection()
        (treestore, row_paths) = selection.get_selected_rows()
        row_paths = sorted(row_paths)
        for row_path in row_paths:
            render = self.renders[treestore[row_path][0]]
            render.set_settings({
                'render_queued': False,
                'render_frames': 0,
                'render_host'  : None,
                })
            render.is_rendering = False
    def on_render_enqueue(self, widget, *ignore):
        selection = self.render_treeview.get_selection()
        (treestore, row_paths) = selection.get_selected_rows()
        row_paths = sorted(row_paths)
        for row_path in row_paths:
            render = self.renders[treestore[row_path][0]]
            print repr(render)
            render.set_settings({
                'render_queued': True,
                })
    def on_render_abort(self, widget, *ignore):
        selection = self.render_treeview.get_selection()
        (treestore, row_paths) = selection.get_selected_rows()
        row_paths = sorted(row_paths)
        for row_path in row_paths:
            render = self.renders[treestore[row_path][0]]
            render.set_settings({
                'render_queued': False,
                })
    def on_afterscript_info(self, widget, *ignore):
        selection = self.afterscript_treeview.get_selection()
        (treestore, row_paths) = selection.get_selected_rows()
        row_paths = sorted(row_paths)
        render = self.renders[treestore[row_paths[0]][0]]
        message = render.uid
        message += '\nPrivate: %s' % render.private
        for k, v in render.settings.iteritems():
            message += '\n%s: %s' % (k, v)
        self.gui_info_dialog(message)
    def on_afterscript_reset(self, widget, *ignore):
        selection = self.afterscript_treeview.get_selection()
        (treestore, row_paths) = selection.get_selected_rows()
        row_paths = sorted(row_paths)
        for row_path in row_paths:
            render = self.renders[treestore[row_path][0]]
            render.set_settings({
                'afterscript_queued': False,
                'afterscript_frames': 0,
                'afterscript_host'  : None,
                })
    def on_afterscript_enqueue(self, widget, *ignore):
        selection = self.afterscript_treeview.get_selection()
        (treestore, row_paths) = selection.get_selected_rows()
        row_paths = sorted(row_paths)
        for row_path in row_paths:
            afterscript = self.renders[treestore[row_path][0]]
            print repr(afterscript)
            afterscript.set_settings({
                'afterscript_queued': True,
                })
    def on_afterscript_abort(self, widget, *ignore):
        selection = self.afterscript_treeview.get_selection()
        (treestore, row_paths) = selection.get_selected_rows()
        row_paths = sorted(row_paths)
        for row_path in row_paths:
            afterscript = self.renders[treestore[row_path][0]]
            afterscript.set_settings({
                'afterscript_queued': False,
                'afterscript_host': None,
                })
    def on_render_resume(self, widget, *ignore):
        selection = self.render_treeview.get_selection()
        (treestore, row_paths) = selection.get_selected_rows()
        row_paths = sorted(row_paths)
        for row_path in row_paths:
            render = self.renders[treestore[row_path][0]]
            render.set_settings({
                'render_paused': False,
                })
    def render_start(self, render):
        # for thread in self.render_threads:
        #     if not thread.is_alive():
        #         print '%s is active' % thread.name
        #         self.render_threads.remove(thread)
        active_renders = 0
        for pid in self.render_processes:
            try:
                os.kill(pid, 0)
                active_renders += 1
            except OSError:
                self.render_processes.remove(pid)
            
        if active_renders < self.render_threads_limit:
            if 'render_host' in render.settings:
                if not render.settings['render_host'] in [HOSTNAME, None]:
                    print '%s is already rendering on %s' % (render.name, render.settings['render_host'])
                    return
            render.set_settings({
                'status': 'Rendering',
                'render_host': HOSTNAME,
                })
            self.render_threads.append(
                self.launch_thread(
                    render.do_render,
                    name='Render %s' % render.name,
                    kwargs={
                        'render_processes' : self.render_processes
                    }
                )
            )
        else:
            return
            # print 'All %i render threads in use' % self.render_threads_limit
    def thread_afterscript(self, render):
        cmd = [
            os.path.join(mistika.scripts_folder, render.settings['afterscript']),
            'ok',
            render.path,
            '--no-socket',
            '--autostart',
            '--no-remove-input',
            '--overwrite',
            '--autoquit',
        ]
        print ' '.join(cmd)
        log_path = render.path + '.log'
        # self.process = subprocess.Popen(cmd, stdout=logfile_h, stderr=subprocess.STDOUT)
        # total time: 4.298 sec, 0.029 sec per frame, 34.665 frames per sec
        if json.loads(open(render.settings_path).read())['afterscript_host']:
            return
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE
        )
        render.set_settings({
            'afterscript_host' : HOSTNAME,
            'afterscript_start_time' : time.time(),
            'afterscript_frames' : 0,
            'afterscript_pid' : proc.pid,
        })
        self.afterscript_processes.append(proc)
        with open(log_path, 'w') as log:
            output = ''
            while proc.returncode == None:
                # print 'afterscript exec proc loop. pid: %i' % proc.pid
                # subprocess.Popen(['pstree', str(proc.pid)]).communicate()
                if not render.settings['afterscript_queued']:
                    print 'Afterscript aborted'
                    # proc.send_signal(signal.SIGINT)
                    os.kill(proc.pid, signal.SIGINT)
                    break
                if not self.settings['afterscript_process']:
                    print 'Render paused'
                    os.kill(proc.pid, signal.SIGSTOP)
                    while not self.settings['afterscript_process']:
                        time.sleep(1)
                    os.kill(proc.pid, signal.SIGCONT)
                # print 'line 1271'
                output_prev = output
                # output = proc.stdout.readline()
                output = ''
                char = None
                while not char in ['\r', '\n', '']:
                    char = proc.stdout.read(1)
                    output += char
                proc.stdout.flush()
                if char == '':
                    break
                # print 'line 1280'
                log.write(output)
                output = output.rstrip()
                # print output
                if output.startswith('frame='):
                    status = {}
                    keyvalue_pairs = re.findall('\w+=\s*\S+', output)
                    for keyvalue_pair in keyvalue_pairs:
                        k, v = keyvalue_pair.split('=')
                        status[k] = v
                    # print '\r'+output,
                    render.set_settings({
                        'afterscript_frames' : status['frame']
                    })
                # print 'line 1294'
                proc.poll()
            proc.wait()
            if proc.returncode == 0:
                print 'Afterscript complete'
                render.set_settings({
                    'afterscript_host' : None,
                    'afterscript_queued' : False,
                    'afterscript_frames' : render.frames,
                    'status' : 'Afterscript complete',
                    })
            else:
                print 'Return code: %i' % proc.returncode
                render.set_settings({
                    'afterscripts_failed' :render.settings['afterscripts_failed'] + [
                        render.settings['afterscript_frames']
                    ],
                    'afterscript_queued' : False,
                    'status' : 'Afterscript failed',
                    'afterscript_host' : None,
                })
    def afterscript_start(self, render):
        # Check cpu wait and IO to determine wether to start new processes
        cmd = ['uptime']
        status = subprocess.Popen(cmd, stdout=subprocess.PIPE).communicate()[0].splitlines()[0]
        wait = float(status.split()[-3].strip(','))
        # if wait * multiprocessing.cpu_count() > 1:
        #     print 'System is busy'
        #     return
        if 'afterscript_host' in render.settings:
            if not render.settings['afterscript_host'] in [HOSTNAME, None]:
                print '%s is already rendering on %s' % (render.name, render.settings['render_host'])
                return
        render.set_settings({
            'status': 'Afterscript starting',
            })
        self.render_threads.append(
            self.launch_thread(
                self.thread_afterscript,
                name='%s %s' % (render.settings['afterscript'], render.name),
                kwargs={
                    'render' : render
                }
            )
        )
    def on_render_button_press_event(self, treeview, event, *ignore):
        treestore = treeview.get_model()
        if event.button == 3:
            x = int(event.x)
            y = int(event.y)
            time = event.time
            pthinfo = treeview.get_path_at_pos(x, y)
            if pthinfo is not None:
                path, col, cellx, celly = pthinfo
                if treestore[path].parent == None:
                    return False
                treeview.grab_focus()
                selection = self.render_treeview.get_selection()
                (treestore, row_paths) = selection.get_selected_rows()
                if len(row_paths) <= 1:
                    treeview.set_cursor( path, col, 0)
                    # selection.select_path(path)
                self.render_item_menu().popup( None, None, None, event.button, time)
                self.render_queue_selected_path = path
            return True
    def on_afterscript_button_press_event(self, treeview, event, *ignore):
        treestore = treeview.get_model()
        if event.button == 3:
            x = int(event.x)
            y = int(event.y)
            time = event.time
            pthinfo = treeview.get_path_at_pos(x, y)
            if pthinfo is not None:
                path, col, cellx, celly = pthinfo
                if treestore[path].parent == None:
                    return False
                treeview.grab_focus()
                selection = self.afterscript_treeview.get_selection()
                (treestore, row_paths) = selection.get_selected_rows()
                if len(row_paths) <= 1:
                    treeview.set_cursor( path, col, 0)
                    # selection.select_path(path)
                # treeview.set_cursor( path, col, 0)
                self.afterscript_item_menu().popup( None, None, None, event.button, time)
                self.afterscript_queue_selected_path = path
            return True
    
warnings.filterwarnings("ignore")
os.environ['LC_CTYPE'] = 'en_US.utf8'
os.environ['LC_ALL'] = 'en_US.utf8'
gobject.threads_init()
RenderManagerWindow()
gtk.main()

