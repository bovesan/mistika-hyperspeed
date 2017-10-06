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

class RenderItem(hyperspeed.stack.Render):
    settings = {}
    treeview = None
    treestore = None
    row_reference = None
    afterscript_progress = 0.0
    owner = 'Unknown'
    settings = {
        'stage': 'render',
        'afterscript' : None,
        'status' : 'Not started',
        'frames_rendered' : 0.0,
        'afterscript_progress' : 0.0,
    }
    description = None
    def __init__(self, path, uid):
        super(RenderItem, self).__init__(path)
        self.uid = uid
        self.duration = hyperspeed.video.frames2tc(self.frames, self.fps)
    def do_render(self):
        cmd = ['mistika', '-r', self.path]
        # self.logfile_path = self.path + '.log'
        # logfile_h = open(self.logfile_path, 'w')
        # self.process = subprocess.Popen(cmd, stdout=logfile_h, stderr=subprocess.STDOUT)
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        while proc.returncode == None:
            line = proc.stdout.readline()
            if line.startswith('Done:'):
                self.set_settings({
                    'frames_rendered' : line.split(' ')[1].strip(',')
                })
            proc.poll()
        # logfile_h.flush()
    def gui_remove(self, item):
        row_path = self.row_reference.get_path()
        row_iter = treestore.get_iter(row_path)
        treestore.remove(iter)
    def set_settings(self, settings):
        self.settings.update(settings)
        open(self.settings_path, 'w').write(json.dumps(self.settings, indent=4))
    @property
    def render_progress(self):
        try:
            return float(self.settings['frames_rendered']) / float(self.frames)
        except (KeyError, ZeroDivisionError) as e:
            return 0.0
    @property
    def treestore_values(self):
        if self.settings['stage'] == 'render':
            return [
                self.uid, # Id
                self.project, # Project
                self.name, # Name
                self.render_progress, # Progress
                '%5.2f%%' % (self.render_progress * 100.0), # Progress str
                self.settings['status'], # Status
                self.settings['afterscript'], # Afterscript
                self.ctime, # Added time
                self.description, # Description
                hyperspeed.human.time(self.ctime), # Human time
                self.render_progress > 0 # Progress visible
            ]
        else:
            return [
                self.uid, # Id
                self.project, # Project
                self.name, # Name
                self.afterscript_progress, # Progress
                '%5.2f%%' % (self.afterscript_progress * 100.0), # Progress str
                self.status, # Status
                self.settings['afterscript'], # Afterscript
                self.ctime, # Added time
                self.description, # Description
                hyperspeed.human.time(self.ctime), # Human time
                self.afterscript_progress > 0 # Progress visible
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
    def bring_to_front(self):
        self.present()
    def config_rw(self, write=False):
        pass
    def init_render_queue_window(self):
        self.render_queue = {}
        row_references = self.row_references_render = {}
        tree           = self.render_treeview  = gtk.TreeView()
        treestore      = self.render_treestore = gtk.TreeStore(
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
        tree_filter    = self.render_queue_filter    = treestore.filter_new();
        # tree.connect('button-press-event' , self.button_press_event)
        for queue_name in [THIS_HOST_ALIAS, OTHER_HOSTS_ALIAS]:
            row_iter = treestore.append(None, [queue_name, queue_name, '', 0, '', '', '', '', 'Render jobs submitted by %s' % queue_name.lower(), '', False])
            row_path = treestore.get_path(row_iter)
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

        menu = self.popup_menu = gtk.Menu()
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
                            description = ''
                            description += 'Resolution: %sx%s\n' % (render.resX, render.resY)
                            description += 'Fps: %s\n' % render.fps
                            description += 'Duration: %s (%s frames)\n' % (render.duration, render.frames)
                            description = description.strip('\n')
                            render.description = description
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
            print repr(treestore), repr(render.treestore)
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
                row_path = render.row_reference.get_path()
                render.treestore[row_path] = render.treestore_values
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

