#!/usr/bin/python
# -*- coding: utf-8 -*-  

import gtk
import os
import subprocess
import sys
import tempfile
import threading
import platform
import Queue
import socket
import gobject
import time
import warnings
from datetime import datetime

try:
    cwd = os.getcwd()
    os.chdir(os.path.dirname(sys.argv[0]))
    sys.path.append("../..")
    from hyperspeed.stack import Stack
    from hyperspeed import mistika
    from hyperspeed import human
    from hyperspeed import video
except ImportError:
    print 'Could not load Hyperspeed modules. Are you running in the Tools directory?'
    sys.exit(1)

THIS_HOST_ALIAS = 'This machine'
OTHER_HOSTS_ALIAS = 'Others'


class RenderItem(Stack):
    def __init__(self, path):
        super(RenderItem, self).__init__(path)
        self.progress = 0.0
        self.duration = video.frames2tc(self.frames, self.fps)
        self.afterscript = ''
        self.owner = 'Unknown'
        self.status = 'Not started'
    def run(self):
        cmd = ['mistika', '-c', self.path]
        self.logfile_path = self.path + '.log'
        logfile_h = open(self.logfile_path, 'w')
        self.process = subprocess.Popen(cmd, stdout=logfile_h, stderr=subprocess.STDOUT)
        self.ret_code = self.process.wait()
        logfile_h.flush()

class RenderManagerWindow(gtk.Window):
    def __init__(self):
        super(RenderManagerWindow, self).__init__()
        self.config_rw()
        self.threads = []
        self.queue_io = Queue.Queue()
        screen = self.get_screen()
        self.set_title("Hyperspeed render manager")
        self.set_size_request(screen.get_width()/2, screen.get_height()*8/10)
        self.set_border_width(20)
        self.set_position(gtk.WIN_POS_CENTER)
        if 'darwin' in platform.system().lower():
            self.set_resizable(False) # Because resizing crashes the app on Mac
        self.connect("key-press-event",self.on_key_press_event)
        self.set_icon_from_file("../../res/img/hyperspeed_1024px.png")
        gtkrc = '''
        style "theme-fixes" {
            font_name = "sans normal 12"
        }
        class "*" style "theme-fixes"'''
        # gtk.rc_parse_string(gtkrc)
        vbox = gtk.VBox(False, 10)
        # vbox.pack_start(self.init_toolbar(), False, False, 10)

        self.afterscripts_model = gtk.ListStore(str)
        self.afterscripts_model.append(['None'])

        vbox.pack_start(self.init_render_queue_window())
        vbox.pack_start(self.init_afterscript_queue_window())

        footer = gtk.HBox(False, 10)
        quitButton = gtk.Button('Quit')
        quitButton.set_size_request(70, 30)
        quitButton.connect("clicked", self.on_quit)
        footer.pack_end(quitButton, False, False)

        vbox.pack_end(footer, False, False, 10)

        self.add(vbox)

        self.connect("destroy", self.on_quit)
        self.show_all()

        self.comboEditable = None
        gobject.idle_add(self.bring_to_front)
    def bring_to_front(self):
        self.present()

    def config_rw(self, write=False):
        pass
    def on_quit(self, widget):
        if type(widget) is gtk.Button:
            widget_name = widget.get_label() + ' button'
        else:
            widget_name = str(widget)
        print 'Closed by: ' + widget_name
        gtk.main_quit()
    def init_render_queue_window(self):
        self.render_queue = {}
        row_references = self.row_references_render_queue = {}
        tree           = self.render_queue_tree      = gtk.TreeView()
        treestore      = self.render_queue_treestore = gtk.TreeStore(str, str, str, int, str, str, str, str, str, str, bool) # Id, Project, Name, Progress value, Progress str, Status, Afterscript, Added time, Description, human time, show progress
        tree_filter    = self.render_queue_filter    = treestore.filter_new();
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
    def init_afterscript_queue_window(self):
        self.render_queue = {}
        row_references = self.row_references_afterscript_queue = {}
        tree           = self.afterscript_queue_tree      = gtk.TreeView()
        treestore      = self.afterscript_queue_treestore = gtk.TreeStore(str, str, str, int, str, str, str, str, str, str, bool) # Id, Project, Name, Progress value, Progress str, Status, Afterscript, Added time, Description, human time, show progress
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
        queue = self.render_queue
        hostname = socket.gethostname()
        for queue_name in os.listdir(mistika.settings['BATCHPATH']):
            queue_path = os.path.join(mistika.settings['BATCHPATH'], queue_name)
            try:
                for file_name in os.listdir(queue_path):
                    file_path = os.path.join(queue_path, file_name)
                    file_id, file_ext = os.path.splitext(file_path)
                    if file_ext == '.rnd':
                        #print 'Render item: ', file_path
                        queue[file_id] = RenderItem(file_path)
                        render = queue[file_id]
                        render.private = queue_name.startswith(hostname)
                        #print 'Render groupname: ', queue[file_id].groupname
                        afterscript_setting_path = file_id+'.afterscript'
                        try:
                            render.afterscript = open(afterscript_setting_path).read()
                        except IOError:
                            pass
            except OSError:
                pass
        gobject.idle_add(self.gui_update_render_queue)
    def gui_update_render_queue(self):
        treeview = self.render_queue_tree
        treestore = self.render_queue_treestore
        row_references = self.row_references_render_queue
        queue = self.render_queue
        for file_id in sorted(queue):
            render = queue[file_id]
            if render.private:
                parent_row_reference = row_references[THIS_HOST_ALIAS]
            else:
                parent_row_reference = row_references[OTHER_HOSTS_ALIAS]
            parent_row_path = parent_row_reference.get_path()
            parent_row_iter = treestore.get_iter(parent_row_path)
            progress_string = '%5.2f%%' % (render.progress * 100.0)
            time_string = human.time(render.ctime)
            description = ''
            description += 'Resolution: %sx%s\n' % (render.resX, render.resY)
            description += 'Fps: %s\n' % render.fps
            description += 'Duration: %s (%s frames)\n' % (render.duration, render.frames)
            description = description.strip('\n')
            if not file_id in row_references:
                # Id, Project, Name, Progress value, Progress str, Status, Afterscript, Added time, Description, human time, show progress
                row_iter = treestore.append(parent_row_iter, [file_id, render.project, render.groupname, render.progress, progress_string,  render.status, render.afterscript, render.ctime, description, time_string, False])
                row_path = treestore.get_path(row_iter)
                row_references[file_id] = gtk.TreeRowReference(treestore, row_path)
            else:
                row_path = row_references[file_id].get_path()
                treestore[row_path] = (file_id, render.project, render.groupname, render.progress, progress_string,  render.status, render.afterscript, render.ctime, description, time_string, False)
        treeview.expand_all()
            

        pass
    def launch_thread(self, method):
        t = threading.Thread(target=method)
        self.threads.append(t)
        t.setDaemon(True)
        t.start()
        return t
    def on_render_afterscript_set(self, widget, path, text):
        treestore = self.render_queue_treestore
        file_id = treestore[path][0]
        afterscript_setting_path = file_id+'.afterscript'
        afterscript = text
        if afterscript == 'None':
            try:
                os.remove(afterscript_setting_path)
            except:
                pass
        else:
            open(afterscript_setting_path, 'w').write(afterscript)
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
        treestore = self.render_queue_treestore
        treepath = self.render_queue_selected_path
        name = treestore[treepath][0]
        print 'Delete', 
        print name
    def on_render_start(self, widget, *ignore):
        treestore = self.render_queue_treestore
        treepath = self.render_queue_selected_path
        name = treestore[treepath][0]
        print 'Start', 
        print name
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
                self.popup.popup( None, None, None, event.button, time)
                self.render_queue_selected_path = path
            return True
    def on_key_press_event(self,widget,event):
        keyval = event.keyval
        keyval_name = gtk.gdk.keyval_name(keyval)
        state = event.state
        ctrl = (state & gtk.gdk.CONTROL_MASK)
        command = (state & gtk.gdk.MOD1_MASK)
        if ctrl or command and keyval_name == 'q':
            self.on_quit('Keyboard shortcut')
        else:
            return False
        return True
    

warnings.filterwarnings("ignore")
os.environ['LC_CTYPE'] = 'en_US.utf8'
os.environ['LC_ALL'] = 'en_US.utf8'
gobject.threads_init()
RenderManagerWindow()
gtk.main()

