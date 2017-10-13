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

def process_suspended_status(pid):
    try:
        return re.sub(r'\(.*\)', '()', open(os.path.join('/proc', str(pid), 'stat')).readline()).split()[2]=='T'
    except AttributeError:
        return None

class RenderItem(hyperspeed.stack.Render):
    treeview = None
    treestore = None
    row_reference = None
    afterscript_progress = 0.0
    owner = 'Unknown'
    gui_freeze_render = None
    def __init__(self, path, global_settings):
        super(RenderItem, self).__init__(path)
        self.global_settings = global_settings
        self.duration = hyperspeed.video.frames2tc(self.frames, self.fps)
        description = 'Resolution: %sx%s' % (self.resX, self.resY)
        description += '\nFps: %s' % self.fps
        description += '\nDuration: %s (%s frames)' % (self.duration, self.frames)
        self.settings = {
            'description'          : description,
            'color'                : COLOR_DEFAULT,
            'priority'             : self.ctime,
            'submit_host'          : HOSTNAME,
            'stage'                : 'render',
            'is_rendering'         : False,
            'render_paused'        : False,
            'render_host'          : None,
            'render_queued'        : False,
            'render_frames'        : 0,
            'renders_failed'       : [],
            'afterscript'          : None,
            'status'               : 'Not started',
            'afterscript_progress' : 0.0,
        }
        self.settings_path = os.path.join(os.path.dirname(self.path), self.uid+'.cfg')
        self.settings_read()
        self.set_settings()
        self.prev_treestore_values = None
    def do_render(self, render_processes):
        cmd = ['mistika', '-r', self.path]
        print ' '.join(cmd)
        log_path = self.path + '.log'
        logfile_h = open(log_path, 'w')
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
                        'status' : 'Render complete',
                        'is_rendering' : False,
                    })
                proc.poll()
            if proc.returncode == 0:
                self.set_settings({
                    'render_queued' : False,
                    })
            elif proc.returncode == 3:
                print 'Aborted by user'
                self.set_settings({
                    'render_queued' : False,
                    })
            else:
                print proc.returncode
                self.set_settings({
                    'renders_failed' :self.settings['renders_failed'] + [
                        self.settings['render_frames']
                    ],
                })
        # logfile_h.flush()
    def gui_remove(self, item):
        row_path = self.row_reference.get_path()
        row_iter = treestore.get_iter(row_path)
        treestore.remove(iter)
    def set_settings(self, settings={}):
        self.settings.update(settings)
        open(self.settings_path, 'w').write(json.dumps(self.settings, indent=4, sort_keys=True))
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
        treestore[row_path] = self.treestore_values
    @property
    def render_progress(self):
        try:
            return float(self.settings['render_frames']) / float(self.frames)
        except (KeyError, ZeroDivisionError) as e:
            return 0
    @property
    def treestore_values(self):
        if self.settings['stage'] == 'render':
            return [
                self.uid, # Id
                self.project, # Project
                self.name, # Name
                self.render_progress * 100.0, # Progress
                '%5.2f%%' % (self.render_progress * 100.0), # Progress str
                self.settings['status'], # Status
                self.settings['afterscript'], # Afterscript
                self.ctime, # Added time
                self.settings['description'], # Description
                hyperspeed.human.time(self.ctime), # Human time
                self.settings['is_rendering'] , # 10 Progress visible
                self.settings['priority'],
                self.settings['submit_host'],
                self.settings['render_host'],
                self.settings['color'],
                not 1 > self.render_progress >= 0, # Status visible
                self.duration, # 16
                self.private, 
                self.settings['submit_host'] == HOSTNAME,
                self.settings['render_queued'],
                self.render_progress < 1, # 20 Settings visible
            ]
        else:
            return [
                self.uid, # Id
                self.project, # Project
                self.name, # Name
                self.afterscript_progress * 100.0, # Progress
                '%5.2f%%' % (self.afterscript_progress * 100.0), # Progress str
                self.status, # Status
                self.settings['afterscript'], # Afterscript
                self.ctime, # Added time
                self.settings['description'], # Description
                hyperspeed.human.time(self.ctime), # Human time
                self.afterscript_progress > 0, # Progress visible
                self.settings['priority'],
                self.settings['submit_host'],
                self.settings['render_host'],
                self.private,
                self.settings['submit_host'] == HOSTNAME,
                self.settings['afterscript_queued'],
            ]

class RenderQueue(object):
    queue = Queue.Queue()
    items = {}
    def __init__(self, treeview_renders, treeview_afterscripts):
        self.treeview_renders = treeview_renders
        self.treeview_afterscripts = treeview_afterscripts
    def put(self, item):
        queue.put_nowait(self._put, item)
    def _put(self, item):
        self.items[item.path] = item
    def remove(self, item):
        queue.put_nowait(self._remove, item)
    def _remove(self, item):
        gobject.idle_add(self._remove_from_views, item.path)
        del self.items[item.path]

class RenderManagerWindow(hyperspeed.ui.Window):
    def __init__(self):
        super(RenderManagerWindow, self).__init__(
            title='Hyperspeed render manager',
            settings_default = {
                'shared_queues_folder' : '',
                'render_process' : True,
            }
        )
        self.renders = {}
        self.threads = []
        self.render_threads = []
        self.render_processes = []
        self.render_threads_limit = 1
        self.queue_io = Queue.Queue()
        self.config_rw()
        vbox = gtk.VBox(False, 10)
        # vbox.pack_start(self.init_toolbar(), False, False, 10)

        self.afterscripts_model = gtk.ListStore(str)
        for afterscript in hyperspeed.afterscript.list():
            self.afterscripts_model.append([afterscript])

        vbox.pack_start(self.settings_panel(), False, False, 10)
        vbox.pack_start(self.init_render_queue_window())
        # vbox.pack_start(self.init_afterscript_queue_window())

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
        model = self.render_treestore
        if self.process_queue_checkbox.get_active():
            row_path = self.row_references_render[THIS_HOST_ALIAS].get_path()
            row_iter = model.get_iter(row_path)
            for n in range(model.iter_n_children(row_iter)):
                child_iter = model.iter_nth_child(row_iter, n)
                child_id = model.get_value(child_iter, 0)
                render = self.renders[child_id]
                if render.settings['render_queued'] and \
                render.settings['render_frames'] < render.frames and \
                not render.settings['render_paused']:
                    self.render_start(render)
                    return
                child_has_child = model.iter_has_child(child_iter)
                child_is_folder = model.get_value(child_iter, 2)
        if self.process_others_checkbox.get_active():
            print 'Starting other jobs'
    def gui_periodical_updates(self):
        self.gui_process_renders()
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
        # cell.connect('event', hyperspeed.ui.event_debug)
        cell.connect('editing-started', self.on_render_freeze, True)
        # cell.connect('editing-canceled', self.on_render_freeze, False, False, False)
        # cell.connect('changed', self.on_render_freeze, False)
        # cell.connect("popup", self.on_render_freeze, True)
        # cell.connect("popdown", self.on_render_freeze, True)
        cell.connect("edited", self.on_render_settings_change, 'afterscript', treestore)
        column = gtk.TreeViewColumn("Afterscript", cell, text=6)
        # column.connect('clicked', hyperspeed.ui.event_debug)
        column.set_resizable(True)
        column.set_expand(True)
        treeview.append_column(column)
        treeview.set_tooltip_column(8)
        treeview.set_rules_hint(True)
        # it = queueTreestore.append(None, ["Private (6)", '', '', '', '', 0, ''])
        # queueTreestore.append(it, ["RnD", 'test_0001', 'Rendering on gaia', 'gaia', '08:27', 20, '20%'])
        # queueTreestore.append(it, ["RnD", 'test_0001', 'Queued', 'gaia', '08:27', 0, ''])
        # queueTreestore.append(it, ["RnD", 'test_0001', 'Queued', 'gaia', '08:27', 0, ''])
        # queueTreestore.append(it, ["RnD", 'test_0001', 'Queued', 'gaia', '08:27', 0, ''])
        # queueTreestore.append(it, ["RnD", 'test_0001', 'Queued', 'gaia', '08:27', 0, ''])
        # queueTreestore.append(it, ["RnD", 'test_0001', 'Queued', 'gaia', '08:27', 0, ''])
        # it = queueTreestore.append(None, ["Public (2)", '', '', '', '', 0, ''])
        # queueTreestore.append(it, ["Mastering", 'film01', 'Queued', 'apollo2', '08:27', 0, ''])
        # queueTreestore.append(it, ["Mastering", 'film02', 'Queued', 'apollo2', '08:27', 0, ''])
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

        menu = self.popup_menu = gtk.Menu()
        newi = gtk.ImageMenuItem(gtk.STOCK_INFO)
        newi.connect("activate", self.on_render_info)
        newi.show()
        menu.append(newi)
        newi = gtk.ImageMenuItem(gtk.STOCK_UNDO)
        newi.set_label('Reset')
        newi.connect("activate", self.on_render_reset)
        newi.show()
        menu.append(newi)
        newi = gtk.ImageMenuItem(gtk.STOCK_CANCEL)
        newi.set_label('Abort')
        newi.connect("activate", self.on_render_abort)
        newi.show()
        menu.append(newi)
        newi = gtk.ImageMenuItem(gtk.STOCK_DELETE)
        newi.connect("activate", self.on_render_delete)
        newi.show()
        menu.append(newi)
        menu.set_title('Popup')
        treeview.connect('button_release_event', self.on_render_button_press_event, treeview)

        self.launch_thread(self.io_populate_render_queue, kwargs={ 'first_run' : True })
        vbox.pack_start(afterscriptsBox, True, True, 5)
        return vbox
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
            except OSError as e:
                hyperspeed.ui.dialog_error(self, str(e))
                return
        # Move settings first to avoid reset
        new_settings_path = render.settings_path.replace(current_folder, new_folder, 1)
        try:
            shutil.move(render.settings_path, new_settings_path)
        except IOError as e:
            errors.append(str(e))
        for current_path in glob.glob(os.path.join(current_folder, render.uid+'.*')):
            new_path = current_path.replace(
            current_folder, new_folder, 1)
            try:
                shutil.move(current_path, new_path)
            except IOError as e:
                errors.append(str(e))
        if len(errors) > 0:
            hyperspeed.ui.dialog_error(self, '\n'.join(errors))
        self.launch_thread(self.io_populate_render_queue)
    def on_move(self, widget, direction, treeview):
        selection = treeview.get_selection()
        (treestore, row_paths) = selection.get_selected_rows()
        for row_path in sorted(row_paths, reverse=True):
            file_id = treestore[row_path][0]
            render = self.renders[file_id]
            row_path_parent = row_path[:-1]
            row_path_lastbit = row_path[1]
            if direction < 0 and row_path_lastbit == 0:
                return
            path_one_away = row_path_parent+(row_path_lastbit+direction,)
            path_two_away = row_path_parent+(row_path_lastbit+(direction*2),)
            try:
                priority_one_away = treestore[path_one_away][11]
            except IndexError:
                return
            try:
                priority_two_away = treestore[path_two_away][11]
            except IndexError:
                priority_two_away = priority_one_away+(direction*0.01)
            priority_between = priority_one_away - ((priority_one_away - priority_two_away) * 0.5)
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
        self.render_queue = {}
        row_references = self.row_references_afterscript = {}
        tree           = self.afterscript_treeview  = gtk.TreeView()
        treestore      = self.afterscript_treestore = gtk.TreeStore(
            str, # Id
            str, # Project
            str, # Name
            int, # Progress
            str, # Progress str
            str, # Status
            str, # Afterscript
            str, # Added time
            str, # Description
            str, # Human time
            bool # Progress visible
        )
        tree_filter    = self.afterscript_queue_filter    = treestore.filter_new();
        for queue_name in [THIS_HOST_ALIAS, OTHER_HOSTS_ALIAS]:
            row_iter = treestore.append(None, [queue_name, queue_name, '', 0, '', '', '', '', 'Render jobs submitted by %s' % queue_name.lower(), '', False])
            row_path = treestore.get_path(row_iter)
            row_references[queue_name] = gtk.TreeRowReference(treestore, row_path)
        vbox = gtk.VBox(False, 10)
        headerBox = gtk.HBox(False, 5)
        headerLabel  = gtk.Label('<span size="large"><b>Afterscript queue:</b></span>')
        headerLabel.set_use_markup(True)
        headerBox.pack_start(headerLabel, False, False, 5)
        vbox.pack_start(headerBox, False, False, 2)
        toolbar = gtk.HBox(False, 2)
        checkButton = gtk.CheckButton('Process queue')
        checkButton.set_property("active", True)
        toolbar.pack_start(checkButton, False, False, 5)
        checkButton = gtk.CheckButton('Process jobs for other hosts')
        checkButton.set_property("active", False)
        toolbar.pack_start(checkButton, False, False, 5)
        checkButton = gtk.CheckButton('Autostart jobs from this machine')
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
        tree.append_column(column)
        column = gtk.TreeViewColumn('Name', gtk.CellRendererText(), text=2)
        column.set_resizable(True)
        column.set_expand(False)
        tree.append_column(column)
        cell = gtk.CellRendererProgress()
        column = gtk.TreeViewColumn('Progress', cell, value=3, text=4)
        column.add_attribute(cell, 'visible', 10)
        column.set_resizable(True)
        column.set_expand(False)
        tree.append_column(column)
        column = gtk.TreeViewColumn('Status', gtk.CellRendererText(), text=5)
        column.set_resizable(True)
        column.set_expand(True)
        tree.append_column(column)

        afterscripts_model = self.afterscripts_model
        cell = gtk.CellRendererCombo()
        cell.set_property("editable", True)
        cell.set_property("has-entry", False)
        cell.set_property("text-column", 0)
        cell.set_property("model", afterscripts_model)
        # cell.connect('changed', self.on_combo_changed)
        # cell.connect('editing-started', self.on_editing_started)
        cell.connect("popup-shown", self.on_render_editing)
        cell.connect("edited", self.on_render_afterscript_set)
        column = gtk.TreeViewColumn("Afterscript", cell, text=6)
        column.set_resizable(True)
        column.set_expand(False)
        tree.append_column(column)
        column = gtk.TreeViewColumn('Added time', gtk.CellRendererText(), text=9)
        column.set_resizable(True)
        column.set_expand(False)
        tree.append_column(column)
        tree.set_tooltip_column(8)
        tree.set_rules_hint(True)
        # it = queueTreestore.append(None, ["Private (6)", '', '', '', '', 0, ''])
        # queueTreestore.append(it, ["RnD", 'test_0001', 'Rendering on gaia', 'gaia', '08:27', 20, '20%'])
        # queueTreestore.append(it, ["RnD", 'test_0001', 'Queued', 'gaia', '08:27', 0, ''])
        # queueTreestore.append(it, ["RnD", 'test_0001', 'Queued', 'gaia', '08:27', 0, ''])
        # queueTreestore.append(it, ["RnD", 'test_0001', 'Queued', 'gaia', '08:27', 0, ''])
        # queueTreestore.append(it, ["RnD", 'test_0001', 'Queued', 'gaia', '08:27', 0, ''])
        # queueTreestore.append(it, ["RnD", 'test_0001', 'Queued', 'gaia', '08:27', 0, ''])
        # it = queueTreestore.append(None, ["Public (2)", '', '', '', '', 0, ''])
        # queueTreestore.append(it, ["Mastering", 'film01', 'Queued', 'apollo2', '08:27', 0, ''])
        # queueTreestore.append(it, ["Mastering", 'film02', 'Queued', 'apollo2', '08:27', 0, ''])
        tree.set_model(treestore)
        tree.expand_all()
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(tree)
        afterscriptsBox.pack_start(scrolled_window)
        afterscriptsButtons = gtk.VBox(False, 3)
        afterscriptsButtons.set_size_request(30,80)
        gtk.stock_add([(gtk.STOCK_GO_UP, "", 0, 0, "")])
        upButton = gtk.Button(stock=gtk.STOCK_GO_UP)
        afterscriptsButtons.pack_start(upButton)
        gtk.stock_add([(gtk.STOCK_GO_DOWN, "", 0, 0, "")])
        downButton = gtk.Button(stock=gtk.STOCK_GO_DOWN)
        afterscriptsButtons.pack_start(downButton)
        afterscriptsBox.pack_start(afterscriptsButtons, False, False)

        menu = self.popup = gtk.Menu()
        newi = gtk.ImageMenuItem(gtk.STOCK_DELETE)
        newi.connect("activate", self.on_render_delete)
        newi.show()
        menu.append(newi)
        newi = gtk.ImageMenuItem(gtk.STOCK_MEDIA_PLAY)
        newi.set_label('Start')
        newi.connect("activate", self.on_render_start)
        newi.show()
        menu.append(newi)
        menu.set_title('Popup')
        tree.connect('button_release_event', self.on_render_button_press_event, tree)

        self.launch_thread(self.io_populate_render_queue, kwargs={ 'first_run' : True })
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
                    render = RenderItem(file_path, self.settings)
                    if private:
                        id_path = os.path.join(os.path.dirname(render.path), render.uid+'.rnd')
                        if not os.path.basename(render.path) == id_path:
                            os.rename(render.path, id_path)
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
        gobject.idle_add(self.gui_update_render_queue)
        if first_run:
            gobject.idle_add(self.render_treeview.expand_all)
    def gui_update_render_queue(self):
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
                render.treeview = self.afterscript_tree
                if render.settings['submit_host'] == HOSTNAME:
                    parent_row_reference = self.row_references_afterscripts[THIS_HOST_ALIAS]
                else:
                    parent_row_reference = self.row_references_afterscripts[OTHER_HOSTS_ALIAS]
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
        # self.render_treeview.expand_all()
        # self.afterscript_tree.expand_all()
    def launch_thread(self, target, name=False, args=[], kwargs={}):
        if threading.active_count() >= THREAD_LIMIT:
            print 'Thread limit reached: %i/%i' % (threading.active_count(), THREAD_LIMIT)
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
    def on_render_freeze(self, cell, widget, path, value):
        treestore = self.render_treestore
        # print 'cell: %s' % cell
        # print 'path: %s' % path
        # print 'value: %s' % value
        file_id = treestore[path][0]
        render = self.renders[file_id]
        render.gui_freeze = True
        widget.connect('notify::popup-shown', self.render_unfreeze, render)
    def render_unfreeze(self, widget, status, render):
        if widget.get_property('popup-shown'):
            render.gui_freeze_render = False
        else:
            render.gui_freeze_render = False
    def on_render_settings_change(self, cell, path, value, setting_key, treestore):
        if hasattr(cell, 'get_active'): # Checkbox
            value = not cell.get_active()
        print '%s:%s' % (setting_key, value)
        file_id = treestore[path][0]
        render = self.renders[file_id]
        render.gui_freeze_render = False
        if value == 'None':
            value = None
        render.set_settings({
            setting_key : value
        })
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
    def on_render_delete(self, widget, *ignore):
        treestore = self.render_treestore
        treepath = self.render_queue_selected_path
        path = treestore[treepath][0]
        render = self.renders[path]
        for dependency in render.output_stack.dependencies:
            if dependency.path.startswith(TEMPORARY_RENDERS_FOLDER):
                print 'Delete intermediate render file: %s' % dependency.path
        print 'Delete', 
        print path
    def on_render_reset(self, widget, *ignore):
        treestore = self.render_treestore
        treepath = self.render_queue_selected_path
        path = treestore[treepath][0]
        render = self.renders[path]
        render.set_settings({
            'render_queued': False,
            'render_frames': 0,
            'render_host'  : None,
            })
        render.is_rendering = False
    def on_render_pause(self, widget, *ignore):
        treestore = self.render_treestore
        treepath = self.render_queue_selected_path
        path = treestore[treepath][0]
        render = self.renders[path]
        render.set_settings({
            'render_paused': not render.settings['render_paused'],
            })
    def on_render_abort(self, widget, *ignore):
        treestore = self.render_treestore
        treepath = self.render_queue_selected_path
        path = treestore[treepath][0]
        render = self.renders[path]
        render.set_settings({
            'render_queued': False,
            })
    def on_render_resume(self, widget, *ignore):
        treestore = self.render_treestore
        treepath = self.render_queue_selected_path
        path = treestore[treepath][0]
        render = self.renders[path]
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
            if 'render_host' in  render.settings and not render.settings['render_host'] in [HOSTNAME, None]:
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
            print 'All %i render threads in use' % self.render_threads_limit
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
                treeview.set_cursor( path, col, 0)
                self.popup_menu.popup( None, None, None, event.button, time)
                self.render_queue_selected_path = path
            return True
    
warnings.filterwarnings("ignore")
os.environ['LC_CTYPE'] = 'en_US.utf8'
os.environ['LC_ALL'] = 'en_US.utf8'
gobject.threads_init()
RenderManagerWindow()
gtk.main()

