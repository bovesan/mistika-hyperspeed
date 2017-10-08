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
from datetime import datetime

import hyperspeed
import hyperspeed.ui
import hyperspeed.afterscript
import hyperspeed.tools
import hyperspeed.utils
import hyperspeed.human
import hyperspeed.stack
import hyperspeed.video
from hyperspeed import mistika

THIS_HOST_ALIAS = 'This machine'
OTHER_HOSTS_ALIAS = 'Others'
THREAD_LIMIT = multiprocessing.cpu_count()
HOSTNAME = socket.gethostname()
UPDATE_RATE = 1.0
COLOR_DEFAULT = '#111111'

class RenderItem(hyperspeed.stack.Render):
    treeview = None
    treestore = None
    row_reference = None
    afterscript_progress = 0.0
    owner = 'Unknown'
    def __init__(self, path, uid):
        super(RenderItem, self).__init__(path)
        self.duration = hyperspeed.video.frames2tc(self.frames, self.fps)
        description = 'Resolution: %sx%s\n' % (self.resX, self.resY)
        description += '\nFps: %s' % self.fps
        description += '\nDuration: %s (%s frames)' % (self.duration, self.frames)
        self.settings = {
            'description' : description,
            'color' : COLOR_DEFAULT,
            'priority' : self.ctime,
            'submit_host' : HOSTNAME,
            'stage': 'render',
            'render_host' : None,
            'render_frames' : 0,
            'afterscript' : None,
            'status' : 'Not started',
            'afterscript_progress' : 0.0,
        }
        self.uid = uid
    def do_render(self):
        cmd = ['mistika', '-r', self.path]
        log_path = self.path + '.log'
        logfile_h = open(log_path, 'w')
        # self.process = subprocess.Popen(cmd, stdout=logfile_h, stderr=subprocess.STDOUT)
        # total time: 4.298 sec, 0.029 sec per frame, 34.665 frames per sec
        self.set_settings({
            'render_host' : HOSTNAME,
            'render_start_time' : time.time(),
        })
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        with open(log_path, 'w') as log:
            while proc.returncode == None:
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
                    })
                proc.poll()
        # logfile_h.flush()
    def gui_remove(self, item):
        row_path = self.row_reference.get_path()
        row_iter = treestore.get_iter(row_path)
        treestore.remove(iter)
    def set_settings(self, settings):
        self.settings.update(settings)
        open(self.settings_path, 'w').write(json.dumps(self.settings, indent=4, sort_keys=True))
        gobject.idle_add(self.gui_update)
    def gui_update(self):
        row_path = self.row_reference.get_path()
        self.treestore[row_path] = self.treestore_values
    @property
    def render_progress(self):
        try:
            return float(self.settings['render_frames']) / float(self.frames)
        except (KeyError, ZeroDivisionError) as e:
            return 0.0
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
                1 > self.render_progress > 0, # 10 Progress visible
                self.settings['priority'],
                self.settings['submit_host'],
                self.settings['render_host'],
                self.settings['color'],
                not 1 > self.render_progress > 0, # Status visible
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
    renders = {}
    threads = []
    queue_io = Queue.Queue()
    def __init__(self):
        super(RenderManagerWindow, self).__init__(
            title='Hyperspeed render manager'
        )
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
    def settings_panel(self):
        expander = gtk.Expander('Settings')
        vbox = gtk.VBox()
        hbox = gtk.HBox()
        label =  gtk.Label('Shared queue:')
        hbox.pack_start(label, False, False, 5)
        entry = self.shared_queue_entry = gtk.Entry()
        # entry.set_text(self.cmd_string)
        hbox.pack_start(entry)
        button = self.shared_queue_pick_button = gtk.Button('...')
        button.connect("clicked", self.on_folder_pick, entry, 'Select shared queue folder')
        hbox.pack_start(button, False, False, 5)
        vbox.pack_start(hbox, False, False, 5)
        vbox.pack_start(gtk.HSeparator(), False, False, 10)
        expander.add(vbox)
        return expander
    def gui_periodical_updates(self):
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
            bool, # 10 Progress visible
            float,# 11 Priority
            str,  # 12 Submit host
            str,  # 13 Render host
            str,  # 14 Color
            bool, # 15 Status visible
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
        treeview.append_column(column)
        column = gtk.TreeViewColumn('Name', gtk.CellRendererText(), text=2)
        column.set_resizable(True)
        column.set_expand(True)
        treeview.append_column(column)
        column = gtk.TreeViewColumn('Submit time', gtk.CellRendererText(), text=9)
        column.set_resizable(True)
        column.set_expand(False)
        treeview.append_column(column)
        column = gtk.TreeViewColumn('Submit node', gtk.CellRendererText(), text=12)
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
        cell.connect('changed', self.on_combo_changed)
        cell.connect('editing-started', self.on_editing_started)
        cell.connect("edited", self.on_render_settings_change, 'afterscript', treestore)
        column = gtk.TreeViewColumn("Afterscript", cell, text=6)
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
        newi = gtk.ImageMenuItem(gtk.STOCK_MEDIA_PLAY)
        newi.set_label('Start')
        newi.connect("activate", self.on_render_start)
        newi.show()
        menu.append(newi)
        newi = gtk.ImageMenuItem(gtk.STOCK_DELETE)
        newi.connect("activate", self.on_render_delete)
        newi.show()
        menu.append(newi)
        menu.set_title('Popup')
        treeview.connect('button_release_event', self.on_render_button_press_event, treeview)

        self.launch_thread(self.io_populate_render_queue)
        vbox.pack_start(afterscriptsBox, True, True, 5)
        return vbox
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
        cell.connect('changed', self.on_combo_changed)
        cell.connect('editing-started', self.on_editing_started)
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

        self.launch_thread(self.io_populate_render_queue)
        vbox.pack_start(afterscriptsBox, True, True, 5)
        return vbox
    def io_populate_render_queue(self):
        renders = self.renders
        hostname = socket.gethostname()
        for queue_name in os.listdir(mistika.settings['BATCHPATH']):
            queue_path = os.path.join(mistika.settings['BATCHPATH'], queue_name)
            try:
                for file_name in os.listdir(queue_path):
                    file_path = os.path.join(queue_path, file_name)
                    file_size = os.path.getsize(file_path)
                    file_id, file_ext = os.path.splitext(file_path)
                    # file_uid = file_id+str(file_size)
                    file_uid = file_id
                    if file_ext == '.rnd':
                        if not file_uid in renders:
                            render = renders[file_uid] = RenderItem(file_path, file_uid)
                        else:
                            render = renders[file_uid]
                        render.private = queue_name.startswith(hostname)
                        #print 'Render groupname: ', queue[file_id].groupname
                        render.settings_path = file_id+'.settings'
                        try:
                            render.settings.update(json.loads(open(render.settings_path).read()))
                        except (IOError, ValueError) as e:
                            pass
            except OSError as e:
                pass
        gobject.idle_add(self.gui_update_render_queue)
    def gui_update_render_queue(self):
        renders = self.renders
        for file_id in sorted(renders):
            render = renders[file_id]
            if render.settings['stage'] == 'render':
                render.treeview = self.render_treeview
                if render.private:
                    parent_row_reference = self.row_references_render[THIS_HOST_ALIAS]
                else:
                    parent_row_reference = self.row_references_render[OTHER_HOSTS_ALIAS]
            else:
                render.treeview = self.afterscript_tree
                if render.private:
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
        self.render_treeview.expand_all()
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
    def on_render_settings_change(self, cell, path, value, setting_key, treestore):
        file_id = treestore[path][0]
        render = self.renders[file_id]
        render.settings[setting_key] = value
        if value == 'None':
            value = None
        render.set_settings({
            setting_key : value
        })
        self.launch_thread(self.io_populate_render_queue)
    def on_editing_started(self, cell, editable, path):
        self.comboEditable = editable
    def on_combo_changed(self, cell, path, newiter):
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
        for k, v in render.settings.iteritems():
            message += '\n%s: %s' % (k, v)
        self.gui_info_dialog(message)
    def on_render_delete(self, widget, *ignore):
        treestore = self.render_treestore
        treepath = self.render_queue_selected_path
        path = treestore[treepath][0]
        print 'Delete', 
        print path
    def on_render_start(self, widget, *ignore):
        treestore = self.render_treestore
        treepath = self.render_queue_selected_path
        path = treestore[treepath][0]
        render = self.renders[path]
        render.set_settings({
            'status': 'Rendering',
            'host': HOSTNAME,
            'progress': 0.0
            })
        self.launch_thread(render.do_render, name='Render %s' % render.name)
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

