#!/usr/bin/env python
#-*- coding:utf-8 -*-

import cgi
import datetime
import json
import glob
import gobject
import gtk
import os
import pango
import platform
import pprint
import subprocess
import tempfile
import threading
import time
import sys
import Queue

try:
    cwd = os.getcwd()
    os.chdir(os.path.dirname(sys.argv[0]))
    sys.path.append("../..")
    from hyperspeed.stack import Stack, DEPENDENCY_TYPES
    from hyperspeed import mistika
    from hyperspeed import human
    import hyperspeed.ui
except ImportError:
    mistika = False

MISTIKA_EXTENSIONS = ['env', 'grp', 'rnd', 'fx', 'lnk']
CFG_DIR = os.path.expanduser('~/.mistika-hyperspeed/msync/')
CFG_HOSTS_PATH = os.path.join(CFG_DIR, 'hosts.json')

COLOR_DEFAULT = '#000000'
COLOR_DISABLED = '#888888'
COLOR_WARNING = '#ff8800'
COLOR_ALERT = '#cc0000'

ICON_CONNECT = gtk.image_new_from_stock(gtk.STOCK_CONNECT,  gtk.ICON_SIZE_BUTTON)
ICON_DISCONNECT = gtk.image_new_from_stock(gtk.STOCK_DISCONNECT,  gtk.ICON_SIZE_BUTTON)
ICON_CONNECTED = gtk.image_new_from_stock(gtk.STOCK_APPLY,  gtk.ICON_SIZE_BUTTON)
ICON_STOP = gtk.image_new_from_stock(gtk.STOCK_STOP,  gtk.ICON_SIZE_BUTTON)
ICON_FOLDER = gtk.gdk.pixbuf_new_from_file_at_size('../../res/img/folder.png', 16, 16)
ICON_LIST = gtk.gdk.pixbuf_new_from_file_at_size('../../res/img/list.png', 16, 16)
PIXBUF_SEARCH = gtk.gdk.pixbuf_new_from_file_at_size('../../res/img/search.png', 16, 16)
PIXBUF_EQUAL = gtk.gdk.pixbuf_new_from_file_at_size('../../res/img/equal.png', 16, 16)
ICON_FILE = gtk.gdk.pixbuf_new_from_file_at_size('../../res/img/file.png', 16, 16)
ICON_LINK = gtk.gdk.pixbuf_new_from_file_at_size('../../res/img/link.png', 16, 16)
ICON_LEFT = gtk.gdk.pixbuf_new_from_file_at_size('../../res/img/left.png', 16, 16)
ICON_RIGHT = gtk.gdk.pixbuf_new_from_file_at_size('../../res/img/right.png', 16, 16)
ICON_BIDIR = gtk.gdk.pixbuf_new_from_file_at_size('../../res/img/reset.png', 16, 16)
ICON_INFO = gtk.gdk.pixbuf_new_from_file_at_size('../../res/img/info.png', 16, 16)
ICON_HELP = gtk.gdk.pixbuf_new_from_file_at_size('../../res/img/info.png', 12, 12)
PIXBUF_PLUS = gtk.gdk.pixbuf_new_from_file_at_size('../../res/img/plus.png', 16, 16)
PIXBUF_MINUS = gtk.gdk.pixbuf_new_from_file_at_size('../../res/img/minus.png', 16, 16)
PIXBUF_CANCEL = gtk.gdk.pixbuf_new_from_file_at_size('../../res/img/cancel.png', 16, 16)
PIXBUF_RESET = gtk.gdk.pixbuf_new_from_file_at_size('../../res/img/reset.png', 16, 16)


class File(object):
    def __init__(self, path, parent, treestore, treeview, attributes=False):
        self._parents = []
        self._icon = False
        self.row_references = []
        self.path = path
        # print 'Creating ', self.path,
        self.absolute = path.startswith('/')
        self.alias = os.path.basename(self.path)
        if self.alias == '':
            self.alias = '/'
        self.is_stack = self.path.rsplit('.', 1)[-1] in MISTIKA_EXTENSIONS
        self.treestore = treestore
        self.treeview = treeview
        self._children = []
        self.mtime_remote = -1
        self.mtime_local = -1
        self.size_remote = -1
        self.size_local = -1
        self.type_remote = ''
        self.type_local = ''
        self.virtual = False
        self.direction = None
        self.deep_searched = False
        self.host = None
        self.progress_percent = 0
        self.progress_string = ''
        self.progress_visibility = False
        self.no_reload = False
        self.color = COLOR_DEFAULT
        self.bytes_done = 0
        self.bytes_total = 0
        self.bytes_done_inc_children = 0
        self.bytes_total_inc_children = 0
        self.transfer = False
        self.stack = False
        self.status = ''
        self.status_visibility = True
        self.placeholder_child = False
        self.placeholder = False
        if attributes:
            for key, value in attributes.iteritems():
                key_private = '_'+key
                if hasattr(self, key_private):
                    setattr(self, key_private, value)
                else:
                    setattr(self, key, value)
        self.on_top_level = False
        self.add_parent(parent) # Adds to view
        self.direction_update()
        # print 'created ', self.path
    def __getitem__(self, key):
        return getattr(self, key)
    def set_attributes(self, attributes):
        for key, value in attributes.iteritems():
            setattr(self, key, value)
        self.direction_update()
        gobject.idle_add(self.gui_update)
    def set_progress(self, progress_float, prefix=''):
        self.progress_percent = progress_float*100.0
        self.progress_string = '%s%5.2f%%' % (prefix, self.progress_percent)
        if progress_float < 1.0:
            self.status_visibility = False
            self.progress_visibility = True
        else:
            self.progress_visibility = False
            self.status_visibility = True
        gobject.idle_add(self.gui_update)
    def progress_update(self):
        if len(self.children) == 0:
            self.bytes_done_inc_children = self.bytes_done
            self.bytes_total_inc_children = self.bytes_total
        try:
            progress_float = float(self.bytes_done_inc_children) / float(self.bytes_total_inc_children)
        except ZeroDivisionError:
            progress_float = 1.0
        self.set_progress(progress_float)
    def set_parse_progress(self, stack=False, progress_float=0.0):
        self.placeholder_child.set_progress(progress_float)
        if progress_float >= 1.0:
            if len(self.children) > 1:
                gobject.idle_add(self.placeholder_child.gui_remove)
            else:
                self.placeholder_child.alias = 'No dependencies found'
                gobject.idle_add(self.placeholder_child.gui_update)
    def set_remap_progress(self, stack=False, progress_float=0.0):
        self.set_progress(progress_float, prefix='Remapping: ')
    @property
    def treestore_values(self):
        #self.projectsTreeStore = gtk.TreeStore(str, str, str, gtk.gdk.Pixbuf, str, int, str, bool, str, bool, gtk.gdk.Pixbuf, str, str, str, int, int) # Basename, Tree Path, Local time, Direction, Remote time, Progress int, Progress text, Progress visibility, remote_address, no_reload, icon, Local size, Remote size, Color(str), int(bytes_done), int(bytes_total)
        size_local_str = '' if self.type_local == 'd' else human.size(self.size_local)
        size_remote_str = '' if self.type_remote == 'd' else human.size(self.size_remote)
        return [
            self.alias, # 0
            self.path, # 1
            human.time(self.mtime_local), # 2
            self.direction_icon, # 3
            human.time(self.mtime_remote), # 4
            int(self.progress_percent), # 5
            self.progress_string, # 6
            self.progress_visibility, # 7
            str(self.host), # 8
            self.no_reload, # 9
            self.icon, # 10
            size_local_str, # 11
            size_remote_str, # 12
            self.color, # 13
            self.bytes_done, # 14
            self.bytes_total, # 15
            self.status, # 16
            self.status_visibility, # 17
        ]
    def direction_update(self):
        if self.type_local in ['d', 'l'] and self.type_remote in ['d', 'l']:
            self.direction = 'unknown'
        elif self.placeholder:
            self.direction = 'unknown'
        elif self.mtime_local > self.mtime_remote:
            self.direction = 'push'
        elif self.mtime_local < self.mtime_remote:
            self.direction = 'pull'
        elif self.size_local == self.size_remote:
            self.direction = 'equal'
        else:
            self.direction == 'unknown'
    def set_status(self, status=False):
        if status:
            self.status = status
        elif len(self.children) > 0:
            statuses = []
            for child in self.children:
                if child.status != '' and not child.status in statuses:
                    statuses.append(child.status)
            if len(statuses) == 0:
                self.status = ''
            elif len(statuses) == 1:
                self.status = statuses[0]
            else:
                self.status = 'Completed with errors'
        if self.progress_percent >= 100.0:
            self.status_visibility = True
            self.progress_visibility = False
        gobject.idle_add(self.gui_update)
        for parent in self.parents:
            parent.set_status()
    @property
    def icon(self):
        if not self._icon:
            if self.is_stack:
                self._icon = ICON_LIST
            elif 'd' in [self.type_local, self.type_remote]:
                self._icon = ICON_FOLDER
            elif 'l' in [self.type_local, self.type_remote]:
                self._icon = ICON_LINK
            else:
                self._icon = ICON_FILE
        return self._icon
    @property
    def direction_icon(self):
        if self.direction == 'push':
            return ICON_RIGHT
        elif self.direction == 'pull':
            return ICON_LEFT
        elif self.direction == 'equal':
            return PIXBUF_EQUAL
        elif self.direction == 'bidir':
            return ICON_BIDIR
        else:
            return None
    @property
    def parents(self):
        return self._parents
    def add_parent(self, parent):
        if parent != None and not parent in self._parents:
            self._parents.append(parent)
            parent.children = self
            gobject.idle_add(self.gui_add_parent, parent)
            # if not parent.virtual:
            if parent.placeholder_child and parent.placeholder_child.progress_percent >= 100.0:
                gobject.idle_add(parent.placeholder_child.gui_remove)
        elif parent == None and not self.on_top_level:
            self.on_top_level = True
            gobject.idle_add(self.gui_add_parent, parent)
    @property
    def children(self):
        return self._children
    @children.setter
    def children(self, child):
        if not child in self._children:
            self._children.append(child)
            gobject.idle_add(self.gui_update)
    @property
    def path(self):
        return self._path
    @path.setter
    def path(self, value):
        self._path = value
        gobject.idle_add(self.gui_update)
    @property
    def placeholder_child_row_reference(self):
        try:
            return self.placeholder_child.row_references[0]
        except AttributeError:
            return
    def gui_expand(self):
        for row_reference in self.row_references:
            row_path = row_reference.get_path()
            self.treeview.expand_row(row_path, False)
    def gui_add_parent(self, parent):
        # print repr(self.treestore_values)
        # if self.buffer[path]['mtime_local'] >= self.buffer[path]['mtime_remote'] and basename.rsplit('.', 1)[-1] in MISTIKA_EXTENSIONS and not 'placeholder_child_row_reference' in self.buffer[path]:
        #             placeholder_child_iter = tree.append(row_iter, ['<i>Getting associated files ...</i>', '', '', None, '', 0, '0%', True, '', True, self.pixbuf_search, '', '', '', 0, 0])
        #             self.buffer[path]['placeholder_child_row_reference'] = gtk.TreeRowReference(tree, tree.get_path(placeholder_child_iter)
        if parent == None:
            parent_row_references = [None]
        else:
            parent_row_references = parent.row_references
        for parent_row_reference in parent_row_references:
            if parent_row_reference == None:
                parent_row_iter = None
            else:
                parent_row_path = parent_row_reference.get_path()
                parent_row_iter = self.treestore.get_iter(parent_row_path)
            row_iter = self.treestore.append(parent_row_iter, self.treestore_values)
            row_path = self.treestore.get_path(row_iter)
            row_reference = gtk.TreeRowReference(self.treestore, row_path)
            self.row_references.append(row_reference)
        if self.is_stack and self.size_local > 0:
            dependency_fetcher_path = '%s dependency fetcher' % self.path
            attributes = {
            'alias': ' <i>Getting dependencies ...</i>',
            'icon' : PIXBUF_SEARCH,
            'placeholder' : True,
            'progress_visibility' : True
            }
            self.placeholder_child = File(dependency_fetcher_path, self, self.treestore, self.treeview, attributes)
    def gui_update(self):
        for row_reference in self.row_references:
            row_path = row_reference.get_path()
            if row_path != None:
                self.treestore[row_path] = self.treestore_values
    def transfer_start(self):
        self.status = 'Transferring'
    def transfer_end(self):
        bytes_done_delta = self.bytes_total - self.bytes_done
        self.bytes_done = self.bytes_total
        self.transfer = False
        self.set_status('Completed')
        self.queue_change(add_bytes_done=bytes_done_delta)
    def transfer_fail(self, message='Transfer error'):
        bytes_done_before = self.bytes_done
        bytes_total_before = self.bytes_total
        self.bytes_total = self.bytes_done
        self.bytes_done = 0
        bytes_done_delta = self.bytes_done - bytes_done_before
        bytes_total_delta = self.bytes_total - bytes_total_before
        self.transfer = False
        self.set_status(message)
        self.queue_change(add_bytes_done=bytes_done_delta, add_bytes_total=bytes_total_delta)
        # if message:
        #     self.set_status(message)
    def queue_change(self, add_bytes_total=False, add_bytes_done=False, direction=False):
        self.bytes_total_inc_children += add_bytes_total
        self.bytes_done_inc_children += add_bytes_done
        if self.direction in ['unknown', 'equal']:
            self.direction = direction
        elif direction in ['push', 'pull', 'bidir'] and self.direction != direction:
            self.direction = 'bidir'
        self.progress_update()
        for parent in self.parents:
            parent.queue_change(add_bytes_total, add_bytes_done, self.direction)
    def set_bytes_done(self, bytes_done):
        bytes_done_before = self.bytes_done
        self.bytes_done = bytes_done
        bytes_done_delta = self.bytes_done - bytes_done_before
        self.progress_update()
        for parent in self.parents:
            parent.queue_change(add_bytes_done=bytes_done_delta)
    def enqueue(self, queue_push, queue_pull, queue_push_size, queue_pull_size, recursive=True):
        if recursive and len(self.children) > 0:
            for child in self.children:
                child.enqueue(queue_push, queue_pull, queue_push_size, queue_pull_size)
        if not self.transfer:
            # print 'Enqueing:', self.path
            bytes_total_before = self.bytes_total
            if self.virtual:
                return
            if self.direction == 'push':
                self.bytes_total = self.size_local
                queue_push_size[0] += self.size_local
                queue_push.put(self)
                self.progress_string = 'Queued'
                self.progress_visibility = True
                self.status_visibility = False
            elif self.direction == 'pull':
                self.bytes_total = self.size_remote
                queue_pull_size[0] += self.size_remote
                queue_pull.put(self)
                self.progress_string = 'Queued'
                self.progress_visibility = True
                self.status_visibility = False
            else:
                self.bytes_total = 0
                self.bytes_done = 0
                self.progress_visibility = False
            self.transfer = True
            bytes_total_delta = self.bytes_total - bytes_total_before
            self.queue_change(add_bytes_total=bytes_total_delta, direction=self.direction)
            gobject.idle_add(self.gui_update)
        else:
            print 'Already in transfer queue:', self.path
    def gui_remove(self):
        for row_reference in self.row_references:
            row_path = row_reference.get_path()
            try:
                del self.treestore[row_path]
            except TypeError:
                pass
gobject.threads_init()
def print_str(self, str):
    print str

def string_format_to_wildcard(raw_str, wrapping=''):
    #H( d(Disk.dev) p(/Volumes/SLOW_HF/PROJECTS/18438_IFA/CENTRAL/Graphics/Unprocessed/packshots/packshots/) n(pakning.%02d.jpg) f((641x747)) )
    output = ''
    formatting = False
    for char in raw_str:
        if char == '%':
            formatting = True
        elif formatting:
            if char == 'd':
                output += wrapping+'*'+wrapping
                formatting = False
        else:
            output += char

    return output
def responseToDialog(entry, dialog, response):
    dialog.response(response)
class MainThread(threading.Thread):
    def __init__(self):
        super(MainThread, self).__init__()
        self.threads = []
        self.buffer = {}
        self.files = {}
        self.directions = {} # Controlled by GUI
        self.buffer_lock = threading.Lock()
        self.lines_local = []
        self.lines_remote = []
        self.queue_buffer = Queue.Queue()
        self.queue_remote = Queue.Queue()
        self.queue_local = Queue.Queue()
        self.queue_push = Queue.Queue()
        self.queue_pull = Queue.Queue()
        self.queue_push_size = [0]
        self.queue_pull_size = [0]
        self.remote = {}
        self.is_mac = False
        self.is_mamba = False
        self.transfer_queue = {}
        self.abort = False
        self.window = gtk.Window()
        window = self.window
        screen = self.window.get_screen()
        monitor = screen.get_monitor_geometry(0)
        window.set_title("Mistika sync")
        window.set_size_request(monitor.width-200, monitor.height-200)
        window.set_border_width(20)
        #window.set_icon_from_file('../res/img/msync_icon.png')
        window.set_position(gtk.WIN_POS_CENTER)
        if 'darwin' in platform.system().lower():
            self.is_mac = True
            self.window.set_resizable(False) # Because resizing crashes the app on Mac
            self.window.maximize()

        tooltips = self.tooltips = gtk.Tooltips()

        self.icon_connect = gtk.image_new_from_stock(gtk.STOCK_CONNECT,  gtk.ICON_SIZE_BUTTON)
        self.icon_disconnect = gtk.image_new_from_stock(gtk.STOCK_DISCONNECT,  gtk.ICON_SIZE_BUTTON)
        self.icon_connected = gtk.image_new_from_stock(gtk.STOCK_APPLY,  gtk.ICON_SIZE_BUTTON)
        self.icon_stop = gtk.image_new_from_stock(gtk.STOCK_STOP,  gtk.ICON_SIZE_BUTTON)
        self.icon_folder = gtk.gdk.pixbuf_new_from_file_at_size('../../res/img/folder.png', 16, 16)
        self.icon_list = gtk.gdk.pixbuf_new_from_file_at_size('../../res/img/list.png', 16, 16)
        self.pixbuf_search = gtk.gdk.pixbuf_new_from_file_at_size('../../res/img/search.png', 16, 16)
        self.pixbuf_equal = gtk.gdk.pixbuf_new_from_file_at_size('../../res/img/equal.png', 16, 16)
        self.icon_file = gtk.gdk.pixbuf_new_from_file_at_size('../../res/img/file.png', 16, 16)
        self.icon_left = gtk.gdk.pixbuf_new_from_file_at_size('../../res/img/left.png', 16, 16)
        self.icon_right = gtk.gdk.pixbuf_new_from_file_at_size('../../res/img/right.png', 16, 16)
        self.icon_info = gtk.gdk.pixbuf_new_from_file_at_size('../../res/img/info.png', 16, 16)
        self.pixbuf_plus = gtk.gdk.pixbuf_new_from_file_at_size('../../res/img/plus.png', 16, 16)
        self.pixbuf_minus = gtk.gdk.pixbuf_new_from_file_at_size('../../res/img/minus.png', 16, 16)
        self.pixbuf_cancel = gtk.gdk.pixbuf_new_from_file_at_size('../../res/img/cancel.png', 16, 16)
        self.pixbuf_reset = gtk.gdk.pixbuf_new_from_file_at_size('../../res/img/reset.png', 16, 16)
        #self.spinner = gtk.Spinner()
        #self.spinner.start()
        #self.spinner.set_size_request(20, 20)
        self.spinner = gtk.Image()
        self.spinner.set_from_file('../../res/img/spinner01.gif')

        vpane = gtk.VPaned()
        vpane.add1(self.init_connection_panel())
        vpane.add2(self.init_files_panel())
        window.add(vpane)
        window.show_all()
        window.connect("destroy", self.on_quit)
        self.window.connect("key-press-event",self.on_key_press_event)
        self.quit = False
        gobject.timeout_add(1000, self.gui_periodical_updates)
    def init_connection_panel(self):
        tooltips = self.tooltips
        vbox = gtk.VBox(False, 10)
        tree_store = self.hostsTreeStore = gtk.TreeStore(
            str, # alias
            str, # Address
            str, # User
            int, # Port
            str, # Remote project path
            str, # Local media root
            bool,# Push
            bool,# Pull
        )
        hbox = gtk.HBox(False, 10)
        label_markup = '<span foreground="#888888">%s</span>'

        vbox2 = gtk.VBox(False, 5)
        tooltips.set_tip(vbox2, "Enter an alias for this remote")
        hbox2 = gtk.HBox(False, 0)
        label = gtk.Label(label_markup % 'Remote host:')
        label.set_use_markup(True)
        hbox2.pack_start(label, False, False, 0)
        vbox2.pack_start(hbox2, False, False, 0)
        entry = self.entry_host = gtk.ComboBoxEntry(model=tree_store, column=0)
        entry.connect("key-release-event", self.on_host_update)
        entry.connect('changed', self.on_host_selected)
        vbox2.pack_start(entry, False, False, 0)
        hbox.pack_start(vbox2, False, False, 0)

        vbox2 = gtk.VBox(False, 5)
        tooltips.set_tip(vbox2, "Domain or IP address")
        hbox2 = gtk.HBox(False, 0)
        label = gtk.Label(label_markup % 'Address:')
        label.set_use_markup(True)
        hbox2.pack_start(label, False, False, 0)
        vbox2.pack_start(hbox2, False, False, 0)
        entry = self.entry_address = gtk.Entry()
        entry.connect('key-release-event', self.on_host_update)
        #entry.connect('event', print_str)
        vbox2.pack_start(entry, False, False, 0)
        hbox.pack_start(vbox2, False, False, 0)

        vbox2 = gtk.VBox(False, 5)
        tooltips.set_tip(vbox2, "SSH username")
        hbox2 = gtk.HBox(False, 0)
        label = gtk.Label(label_markup % 'User:')
        label.set_use_markup(True)
        hbox2.pack_start(label, False, False, 0)
        vbox2.pack_start(hbox2, False, False, 0)
        entry = self.entry_user = gtk.Entry()
        entry.connect('key-release-event', self.on_host_update)
        vbox2.pack_start(entry, False, False, 0)
        hbox.pack_start(vbox2, False, False, 0)

        vbox2 = gtk.VBox(False, 5)
        tooltips.set_tip(vbox2, "SSH port")
        hbox2 = gtk.HBox(False, 0)
        label = gtk.Label(label_markup % 'Port:')
        label.set_use_markup(True)
        hbox2.pack_start(label, False, False, 0)
        vbox2.pack_start(hbox2, False, False, 0)
        entry = self.entry_port = gtk.SpinButton(gtk.Adjustment(value=22, lower=0, upper=9999999, step_incr=1))
        entry.connect('key-release-event', self.on_host_update)
        entry.connect('button-release-event', self.on_host_update)
        #spinner.set_size_request(80,0)
        vbox2.pack_start(entry, False, False, 0)
        hbox.pack_start(vbox2, False, False, 0)

        vbox2 = gtk.VBox(False, 5)
        tooltips.set_tip(vbox2, "Allow sending changes")
        hbox2 = gtk.HBox(False, 0)
        label = gtk.Label(label_markup % 'Push:')
        label.set_use_markup(True)
        hbox2.pack_start(label, False, False, 0)
        vbox2.pack_start(hbox2, False, False, 0)
        entry = self.allow_push = gtk.CheckButton()
        entry.connect('clicked', self.on_host_update)
        vbox2.pack_start(entry, False, False, 0)
        hbox.pack_start(vbox2, False, False, 0)

        vbox2 = gtk.VBox(False, 5)
        tooltips.set_tip(vbox2, "Allow receiving changes")
        hbox2 = gtk.HBox(False, 0)
        label = gtk.Label(label_markup % 'Pull:')
        label.set_use_markup(True)
        hbox2.pack_start(label, False, False, 0)
        vbox2.pack_start(hbox2, False, False, 0)
        entry = self.allow_pull = gtk.CheckButton()
        entry.connect('clicked', self.on_host_update)
        vbox2.pack_start(entry, False, False, 0)
        hbox.pack_start(vbox2, False, False, 0)

        vbox2 = gtk.VBox(False, 5)
        tooltips.set_tip(vbox2, "The path to the projects folder on the remote.\nIf left empty, this setting will be set automatically when connecting to a Mistika system.")
        hbox2 = gtk.HBox(False, 0)
        label = gtk.Label(label_markup % 'Projects path (optional):')
        label.set_use_markup(True)
        hbox2.pack_start(label, False, False, 0)
        vbox2.pack_start(hbox2, False, False, 0)
        entry = self.entry_projects_path = gtk.Entry()
        entry.connect('key-release-event', self.on_host_update)
        vbox2.pack_start(entry, True, True, 0)
        hbox.pack_start(vbox2, True, True, 0)

        vbox2 = gtk.VBox(False, 5)
        tooltips.set_tip(vbox2, "Collect all media from this remote in a single folder on this computer.\nThe default value of / means all media is copied to the same folder as on the server. Set a different folder if you don't have permissions for those folders or you need to separate media collections.")
        hbox2 = gtk.HBox(False, 0)
        label = gtk.Label(label_markup % 'Local media root:')
        label.set_use_markup(True)
        hbox2.pack_start(label, False, False, 0)
        vbox2.pack_start(hbox2, False, False, 0)
        hbox2 = gtk.HBox(False, 0)
        entry = self.entry_local_media_root = gtk.Entry()
        entry.set_text('/')
        entry.connect('key-release-event', self.on_host_update)
        hbox2.pack_start(entry, True, True, 0)
        button = self.entry_local_media_root_button = gtk.Button('...')
        button.connect('clicked', self.on_local_media_root_pick)
        hbox2.pack_start(button, False, False, 0)
        vbox2.pack_start(hbox2, True, True, 0)
        hbox.pack_start(vbox2, True, True, 0)

        #cell = gtk.CellRendererText()
        #combobox.pack_start(cell, True)
        #combobox.add_attribute(cell, 'text', 0)  

        vbox.pack_start(hbox, False, False, 0)

        hbox = gtk.HBox(False, 10)

        button = self.button_connect = gtk.Button(stock=gtk.STOCK_CONNECT)
        #button.set_image(self.icon_connect)
        button.connect("clicked", self.on_host_connect)
        hbox.pack_start(button, False, False)

        button = self.button_disconnect = gtk.Button(stock=gtk.STOCK_DISCONNECT)
        button.connect("clicked", self.on_host_disconnect)
        button.set_no_show_all(True)
        hbox.pack_start(button, False, False)

        # Remote status
        spinner = self.spinner_remote = gtk.Image()
        spinner.set_from_file('../../res/img/spinner01.gif')
        #self.spinner_remote = gtk.Spinner()
        #self.spinner_remote.start()
        #self.spinner_remote.set_size_request(20, 20)
        spinner.set_no_show_all(True)
        hbox.pack_start(spinner, False, False)
        label = self.remote_status_label = gtk.Label()
        hbox.pack_start(label, False, False)

        # Local status
        spinner = self.spinner_local = gtk.Image()
        spinner.set_from_file('../../res/img/spinner01.gif')
        #self.spinner_local = gtk.Spinner()
        #self.spinner_local.start()
        #self.spinner_local.set_size_request(20, 20)
        spinner.set_no_show_all(True)
        hbox.pack_start(spinner, False, False)
        label = self.local_status_label = gtk.Label()
        hbox.pack_start(label, False, False)

        #button.set_image(spinner)
        vbox.pack_start(hbox, False, False, 0)

        return vbox
    def init_files_panel(self):
        tooltips = self.tooltips
        vbox = gtk.VBox(False, 10)
        tree_store = self.projectsTreeStore = gtk.TreeStore(
            str,             #  0 Basename
            str,             #  1 path_id
            str,             #  2 Local time
            gtk.gdk.Pixbuf,  #  3 Direction
            str,             #  4 Remote time
            int,             #  5 Progress int
            str,             #  6 Progress text
            bool,            #  7 Progress visibility
            str,             #  8 remote_address
            bool,            #  9 no_reload
            gtk.gdk.Pixbuf,  # 10 icon
            str,             # 11 Local size
            str,             # 12 Remote size
            str,             # 13 Color(str)
            int,             # 14 bytes_done
            int,             # 15 bytes_total
            str,             # 16 status
            bool,            # 17 status visibility
        ) 
        tree_view = self.projectsTree = gtk.TreeView()
        tree_view.set_rules_hint(True)
        tree_view.set_search_equal_func(func=self.on_search)

        column = gtk.TreeViewColumn()
        column.set_title('')
        tree_view.append_column(column)

        renderer = gtk.CellRendererPixbuf()
        #renderer.set_property('stock-size', 0)
        column.pack_start(renderer, expand=False)
        column.add_attribute(renderer, 'pixbuf', 10)

        renderer = gtk.CellRendererText()
        column.pack_start(renderer, expand=True)
        column.add_attribute(renderer, 'markup', 0)
        column.add_attribute(renderer, 'foreground', 13)
        column.set_resizable(True)
        column.set_expand(True)

        tree_view.append_column(column)

        column = gtk.TreeViewColumn('File path', gtk.CellRendererText(), text=1, foreground=13)
        column.set_resizable(True)
        column.set_expand(True)
        #column.set_property('visible', False)
        tree_view.append_column(column)

        column = gtk.TreeViewColumn('Local size', gtk.CellRendererText(), text=11, foreground=13)
        column.set_resizable(True)
        column.set_expand(False)
        #column.set_property('visible', False)
        tree_view.append_column(column)

        column = gtk.TreeViewColumn('Local time', gtk.CellRendererText(), text=2, foreground=13)
        column.set_resizable(True)
        column.set_expand(False)
        tree_view.append_column(column)

        column = gtk.TreeViewColumn('Action', gtk.CellRendererPixbuf(), pixbuf=3)
        column.set_resizable(True)
        column.set_expand(False)
        tree_view.append_column(column)

        column = gtk.TreeViewColumn('Remote size', gtk.CellRendererText(), text=12, foreground=13)
        column.set_resizable(True)
        column.set_expand(False)
        tree_view.append_column(column)

        column = gtk.TreeViewColumn('Remote time', gtk.CellRendererText(), text=4, foreground=13)
        column.set_resizable(True)
        column.set_expand(False)
        tree_view.append_column(column)

        column = gtk.TreeViewColumn('Bytes done', gtk.CellRendererText(), text=14, foreground=13)
        column.set_resizable(True)
        column.set_expand(False)
        #self.projectsTree.append_column(column)

        column = gtk.TreeViewColumn('Bytes total', gtk.CellRendererText(), text=15, foreground=13)
        column.set_resizable(True)
        column.set_expand(False)
        #self.projectsTree.append_column(column)

        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn('Status')
        column.pack_start(cell, False)
        column.set_attributes(cell, text=16, visible=17)
        cell = gtk.CellRendererProgress()
        column.pack_start(cell, True)
        column.set_attributes(cell, value=5, text=6, visible=7)
        # column = gtk.TreeViewColumn('Status', gtk.CellRendererProgress(), value=5, text=6, visible=7)
        column.set_resizable(True)
        column.set_expand(True)
        tree_view.append_column(column)

        tree_view.set_model(tree_store)
        tree_view.set_search_column(0)
        tree_view.connect("row-expanded", self.on_expand)

        tree_store.set_sort_column_id(0, gtk.SORT_ASCENDING)
        #self.projectsTree.expand_all()

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(tree_view)
        vbox.pack_start(scrolled_window)

        hbox = gtk.HBox(False, 0)
        
        button = gtk.Button()
        button.set_image(gtk.image_new_from_pixbuf(self.pixbuf_plus))
        button.connect("clicked", self.on_sync_selected)
        tooltips.set_tip(button, 'Sync selected file(s)')
        hbox.pack_start(button, False, False, 0)
        
        button = gtk.Button()
        button.set_image(gtk.image_new_from_pixbuf(self.pixbuf_minus))
        button.connect("clicked", self.on_sync_selected_abort)
        tooltips.set_tip(button, 'Remove selected file(s) from sync queue')
        hbox.pack_start(button, False, False, 0)

        button = gtk.Button()
        #self.button_sync_files.set_image(gtk.image_new_from_stock(gtk.STOCK_REFRESH,  gtk.ICON_SIZE_BUTTON))
        button.connect("clicked", self.on_file_info)
        button.set_image(gtk.image_new_from_pixbuf(self.icon_info))
        tooltips.set_tip(button, 'Show more information on selected file(s)')
        hbox.pack_start(button, False, False, 0)

        hbox.pack_start(gtk.Label('Override action:'), False, False, 5)

        button = gtk.Button()
        button.connect("clicked", self.on_force_action, 'pull')
        button.set_image(gtk.image_new_from_pixbuf(self.icon_left))
        tooltips.set_tip(button, 'Remote to local (pull)')
        hbox.pack_start(button, False, False, 0)

        button = gtk.Button()
        button.connect("clicked", self.on_force_action, 'nothing')
        button.set_image(gtk.image_new_from_pixbuf(self.pixbuf_cancel))
        tooltips.set_tip(button, 'Do not sync selected file(s)')
        hbox.pack_start(button, False, False, 0)


        button = gtk.Button()
        button.connect("clicked", self.on_force_action, 'push')
        button.set_image(gtk.image_new_from_pixbuf(self.icon_right))
        tooltips.set_tip(button, 'Local to remote (push)')
        hbox.pack_start(button, False, False, 0)

        button = gtk.Button()
        button.connect("clicked", self.on_force_action, 'reset')
        button.set_image(gtk.image_new_from_pixbuf(self.pixbuf_reset))
        tooltips.set_tip(button, 'Reset selected file(s) to default action')
        hbox.pack_start(button, False, False, 0)

        label = self.push_queue_size_label = gtk.Label('push size')
        hbox.pack_start(label, False, False, 5)
        label = self.pull_queue_size_label = gtk.Label('pull size')
        hbox.pack_start(label, False, False, 5)

        vbox.pack_start(hbox, False, False, 0)

        #menu = ['Sync project', 'Sync media']
        footer = gtk.HBox(False, 10)
        quitButton = gtk.Button('Quit')
        quitButton.set_size_request(70, 30)
        quitButton.connect("clicked", self.on_quit)
        footer.pack_end(quitButton, False, False)

        vbox.pack_end(footer, False, False, 10)
        return vbox
    def run(self):
        self.io_hosts_populate(self.hostsTreeStore)
        treeselection = self.projectsTree.get_selection()
        treeselection.set_mode(gtk.SELECTION_MULTIPLE)
        #self.do_list_projects_local()
        self.start_daemon(self.daemon_buffer)
        self.start_daemon(self.daemon_local)
        self.start_daemon(self.daemon_push)
        self.start_daemon(self.daemon_pull)
        # self.start_daemon(self.daemon_pull)
        #start_daemon(self.daemon_remote)
        #self.start_daemon(self.daemon_transfer)
    def start_daemon(self, daemon):
        t = threading.Thread(target=daemon)
        self.threads.append(t)
        t.setDaemon(True)
        t.start()
    def aux_fix_mac_printf(self, str):
        return str.replace('-printf',  '-print0 | xargs -0 stat -f').replace('%T@', '%m').replace('%s', '%z').replace('%y', '%T').replace('%p', '%N').replace('%l', '%Y').replace('\\\\n', '')
    def aux_mistika_object_path(self, level_names):
        #print repr(level_names)
        return '/'.join(level_names)
    def on_quit(self, widget):
        print 'Closed by: ' + repr(widget)
        for thread in self.threads:
            pass
        gtk.main_quit()
    #on_<object name>_<signal name>(<signal parameters>);.
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
    def on_expand(self, treeview, iter, path, *user_params):
        # print 'Expanding'
        # print repr(model)
        # print repr(iter)
        # print repr(path)
        model = self.projectsTreeStore
        file_path = model[iter][1]
        # print 'Expanding ' + file_path
        file_item = self.buffer[file_path]
        if file_path.rsplit('.', 1)[-1] in MISTIKA_EXTENSIONS: # Should already be loaded
            t = threading.Thread(target=self.io_get_associated, args=[file_path])
            self.threads.append(t)
            t.setDaemon(True)
            t.start()
            return
        if file_item.virtual:
            # print 'Virtual item'
            if model.iter_n_children(iter) == 1:
                # print 'Expand'
                treeview.expand_row(path+(0,), False) # Expand single child items automatically
        elif not file_item.deep_searched:
            self.queue_buffer.put_nowait([self.buffer_list_files, {
            'paths':[file_path]
            }])
        # t = threading.Thread(target=self.io_list_files, args=[[file_path]])
        # self.threads.append(t)
        # t.setDaemon(True)
        # t.start()
    def on_search(self, model, column, key, iter, *user_data):
        print 'on_search(%s, %s, %s, %s, %s, %s)' % (self, model, column, key, iter, user_data)
    def on_host_edit(self, cell, path, new_text, user_data):
        tree, column = user_data
        print tree[path][column],
        row_reference = gtk.TreeRowReference(tree, path)
        gobject.idle_add(self.gui_set_value, tree, row_reference, column, new_text)
        #tree[path][column] = new_text
        print '-> ' + tree[path][column]
        t = threading.Thread(target=self.io_hosts_store)
        self.threads.append(t)
        t.setDaemon(True)
        t.start()
    def on_host_update(self, widget, *user_data):
        #print model[iter][0]
        model = self.hostsTreeStore
        print repr(self.entry_host.get_active_iter())
        selected_row_iter = self.entry_host.get_active_iter()
        if selected_row_iter == None:
            try:
                selected_row_path = self.selected_host_row_reference.get_path()
                selected_row_iter = model.get_iter(selected_row_path)
            except AttributeError:
                selected_row_iter = self.hostsTreeStore.append(None, ['new', '', '', 0, ''])

        # if widget == self.entry_host:
        #     print widget.get_active_text()
        # elif widget == self.entry_port:
        #     print widget.get_value_as_int()
        # else:
        #     try:
        #         print widget.get_text()
        #     except AttributeError:
        #         pass
        model.set_value(selected_row_iter, 0, self.entry_host.get_active_text())
        model.set_value(selected_row_iter, 1, self.entry_address.get_text())
        model.set_value(selected_row_iter, 2, self.entry_user.get_text())
        model.set_value(selected_row_iter, 3, self.entry_port.get_value_as_int())
        model.set_value(selected_row_iter, 4, self.entry_projects_path.get_text())
        model.set_value(selected_row_iter, 5, self.entry_local_media_root.get_text())
        model.set_value(selected_row_iter, 6, self.allow_push.get_active())
        model.set_value(selected_row_iter, 7, self.allow_pull.get_active())
        hosts = {}
        # i = model.get_iter(0)
        # row = model[i]
        for row in model:
            #print repr(selected_row[0])
            #print repr(row[0])
            selected = model[selected_row_iter][0] == row[0]
            #selected = selection.iter_is_selected(model[row])
            alias = row[0]
            for value in row:
                print value,
            print ''
            host_dict = {}
            host_dict['address'] = row[1]
            if host_dict['address'] == '':
                continue
            host_dict['user'] = row[2]
            host_dict['port'] = row[3]
            host_dict['path'] = row[4]
            host_dict['local_media_root'] = row[5]
            host_dict['push'] = row[6]
            host_dict['pull'] = row[7]
            host_dict['selected'] = selected
            hosts[alias] = host_dict
        print 'hosts: ' + repr(hosts)
        t = threading.Thread(target=self.io_hosts_store, args=[hosts])
        self.threads.append(t)
        t.setDaemon(True)
        t.start()
    def on_host_connect(self, widget):
        self.daemon_remote_active = True
        t = threading.Thread(target=self.daemon_remote)
        self.threads.append(t)
        t.setDaemon(True)
        t.start()
    def on_host_disconnect(self, widget):
        self.queue_remote.put([self.remote_disconnect])
    # def buffer_clear_remote(self):
    #     model = self.projectsTreeStore
    #     for file_path in self.buffer.keys():
    #         row_path = self.buffer[file_path].row_reference.get_path()
    #         if row_path == None:
    #             print file_path
    #             continue
    #         row_iter = model.get_iter(row_path)
    #         if self.buffer[file_path].mtime_local < 0:
    #             self.projectsTreeStore.remove(row_iter)
    #             del self.buffer[file_path]
    #         elif self.buffer[file_path].mtime_remote >= 0:
    #             self.buffer[file_path].mtime_remote = -1
    #             self.buffer[file_path].size_remote = -1
    #             self.buffer[file_path].fingerprint_remote = ''
                # self.gobject.idle_add(self.gui_refresh_path, file_path)
    # def on_list_associated(self, widget):
    #     selection = self.projectsTree.get_selection()
    #     (model, pathlist) = selection.get_selected_rows()
    #     for path in pathlist:
    #         path_id = model[path][1]
    #         if path_id.lower().rsplit('.', 1)[-1] in MISTIKA_EXTENSIONS:
    #             t = threading.Thread(target=self.io_get_associated, args=[path_id])
    #             self.threads.append(t)
    #             t.setDaemon(True)
    #             t.start()
    def gui_refresh_progress(self, row_reference, progress_float=0.0):
        model = self.projectsTreeStore
        row_path = row_reference.get_path()
        if model[row_path][14] == 0 or model[row_path][15]:
            progress_float = 0.0
        else:
            progress_float = float(model[row_path][14]) / float(model[row_path][15])
        progress_percent = progress_float * 100.0
        model[row_path][5] = int(progress_percent)
        model[row_path][6] = "%5.2f%% Done: %s Total: %s" % (progress_percent, human_size(model[row_path][14]), human_size(model[row_path][15]))
    def gui_row_delete(self, row_reference):
        model = self.projectsTreeStore
        row_path = row_reference.get_path()
        del model[row_path]
    def io_get_associated(self, path_id, sync=False, remap=False):
        file_object = self.buffer[path_id]
        abs_path = os.path.join(mistika.projects_folder, path_id)
        stack = file_object.stack = Stack(abs_path)
        files_chunk_max_size = 100
        files_chunk = []
        parent_file_path = path_id
        if remap:
            progress_callback = file_object.set_remap_progress
        else:
            progress_callback = file_object.set_parse_progress
        progress_callback(progress_float=0.0)
        for dependency in stack.iter_dependencies(progress_callback=progress_callback, remap=remap):
            search_path = dependency.path
            if search_path.startswith(mistika.projects_folder):
                search_path = search_path.replace(mistika.projects_folder+'/', '', 1)
            elif search_path.startswith(self.remote['projects_path']):
                search_path = search_path.replace(self.remote['projects_path']+'/', '', 1)
            # print 'search_path:', search_path
            files_chunk.append(search_path)
            if len(files_chunk) >= files_chunk_max_size:
                self.queue_buffer.put_nowait([self.buffer_list_files, {
                    'paths' : files_chunk,
                    'parent' : file_object,
                    'sync' : False,
                    'pre_allocate' : True,
                    }])
                files_chunk = []
        if len(files_chunk) > 0:
            self.queue_buffer.put_nowait([self.buffer_list_files, {
                                'paths' : files_chunk,
                                'parent' : file_object,
                                'sync' : False,
                                'pre_allocate' : True,
                                }])
            files_chunk = []
        self.queue_buffer.put_nowait([progress_callback, {'progress_float':1.0}])
        if sync:
            self.queue_buffer.put_nowait([self.buffer[path_id].enqueue, {
                'queue_push' : self.queue_push,
                'queue_pull':self.queue_pull,
                'queue_push_size' : self.queue_push_size,
                'queue_pull_size' : self.queue_pull_size,
                }])
    def buffer_remove_item(self, row_reference):
        gobject.idle_add(self.gui_row_delete, row_reference)
    def on_sync_selected(self, widget):
        selection = self.projectsTree.get_selection()
        (model, pathlist) = selection.get_selected_rows()
        for row_path in pathlist:
            row_reference = gtk.TreeRowReference(model, row_path)
            path_id = model[row_path][1]
            print path_id
            if len(self.buffer[path_id].children) > 0 and not self.buffer[path_id].deep_searched and not self.buffer[path_id].virtual:
                if self.buffer[path_id].direction == 'pull':
                    continue
                if self.buffer[path_id].is_stack:
                    self.queue_buffer.put_nowait([self.io_get_associated, {
                        'path_id': path_id,
                        'sync': True
                    }])
                else:
                    self.queue_buffer.put_nowait([self.buffer_list_files, {
                        'paths': [path_id],
                        'sync': True,
                        'maxdepth': False
                    }])
                # self.queue_buffer.put_nowait([self.buffer[path_id].fetch_dependencies])
            else:
                self.queue_buffer.put_nowait([self.buffer[path_id].enqueue, {
                    'queue_push' : self.queue_push,
                    'queue_pull':self.queue_pull,
                    'queue_push_size' : self.queue_push_size,
                    'queue_pull_size' : self.queue_pull_size,
                    }])
    def do_sync_item(self, row_reference, walk_parent=True):
        model = self.projectsTreeStore
        row_path = row_reference.get_path()
        row_iter = model.get_iter(row_path)
        f_path = model[row_path][1]
        is_folder = self.buffer[f_path].type_local == 'd' or self.buffer[f_path].type_remote == 'd'
        print 'do_sync_item(%s)' % f_path
        if not f_path in self.transfer_queue:
            self.transfer_queue[f_path] = {}
            buffer_item = self.buffer[f_path]
            #pprint.pprint(buffer_item)
            if self.directions[f_path]['direction'] == self.icon_left: # pull
                print 'pull'
                model[row_path][15] = buffer_item['size_remote']
            elif self.directions[f_path]['direction'] == self.icon_right: # push
                print 'push'
                model[row_path][15] = buffer_item['size_local']
            else:
                print 'nothing'
                model[row_path][15] = 0
            model[row_path][14] = 0 # Bytes done
            #model[row_path][6] = 'Queued: '+human_size(model[row_path][15]) # Bytes total
            model[row_path][7] = True # Visibility
        # Children
        child_iter = model.iter_children(row_iter)
        while child_iter != None:
            path_child = model.get_path(child_iter)
            path_str_child = model[path_child][1]
            row_reference_child = gtk.TreeRowReference(model, path_child)
            print 'Child: ' + path_str_child
            if not path_str_child == '': self.do_sync_item(row_reference_child, walk_parent=False)
            child_iter = model.iter_next(child_iter)
        #self.gui_refresh_progress(row_reference)
        # Parents
        if model.iter_children(row_iter) != None: # Has children. Size needs to be summarized
            self.gui_progress_refresh(row_reference, walk_parent) # Starts by updating this
        else:
            self.gui_refresh_progress(row_reference) # Is not a folder. Size is already set
    def gui_progress_refresh(self, row_reference, walk_parent=True):
        model = self.projectsTreeStore
        row_path = row_reference.get_path()
        row_iter = model.get_iter(row_path)
        f_path = model[row_path][1]
        print 'Path: ' + f_path
        size = 0
        if self.buffer[f_path].size_local > 0 or self.buffer[f_path].size_remote > 0:
            print 'Parent has size'
            if self.directions[f_path]['direction'] == self.icon_left: # pull
                size = self.buffer[f_path].size_remote
            elif self.directions[f_path]['direction'] == self.icon_right: # push
                size = self.buffer[f_path].size_local
        # Sum children
        child_iter = model.iter_children(row_iter)
        print 'Child iter: ' + repr(child_iter)
        while child_iter != None:
            path_child = model.get_path(child_iter)
            print "%s %s" % (model[path_child][1], model[path_child][15])
            size  += model[path_child][15]
            child_iter = model.iter_next(child_iter)

        model[row_path][15] = size
        model[row_path][7] = True # Visibility
        #gui_refresh_progress(self, row_reference, progress_float):
        self.gui_refresh_progress(row_reference)
        if walk_parent:
            parent_row_iter = model.iter_parent(row_iter)
            #print 'parent_row_iter: ' + repr(parent_row_iter)
            if parent_row_iter != None:
                parent_row_path = model.get_path(parent_row_iter)
                #print repr(parent_row_path)
                parent_row_reference = gtk.TreeRowReference(model, parent_row_path)
                #print repr(parent_row_reference)
                gobject.idle_add(self.gui_progress_refresh, parent_row_reference)
    def gui_parent_add_bytes(self, row_reference, size):
        model = self.projectsTreeStore
        row_path = row_reference.get_path()
        row_iter = model.get_iter(row_path)
        #print model[row_path][1]
        model[row_path][15] += size
        #print 'Refreshing progressbar ...'
        #gui_refresh_progress(self, row_reference, progress_float):
        self.gui_refresh_progress(row_reference)
        parent_row_iter = model.iter_parent(row_iter)
        #print repr(parent_row_iter)
        if parent_row_iter != None:
            parent_row_path = model.get_path(parent_row_iter)
            #print repr(parent_row_path)
            parent_row_reference = gtk.TreeRowReference(model, parent_row_path)
            #print repr(parent_row_reference)
            self.gui_parent_add_bytes(parent_row_reference, size)
    def on_sync_selected_abort(self, widget):
        selection = self.projectsTree.get_selection()
        (model, pathlist) = selection.get_selected_rows()
        for row_path in pathlist:
            row_reference = gtk.TreeRowReference(model, row_path)
            path_id = model[row_path][1]
            self.buffer[path_id].transfer = False
    def transfer_remove(self, path_str):
        model = self.projectsTreeStore
        for i, transfer_item in enumerate(self.transfer_queue): # Race?
            if transfer_item['path'] == path_str:
                del self.transfer_queue[i]
        for row_reference in self.buffer[path_str].row_references:
            gobject.idle_add(self.gui_set_value, model, row_reference, 7, False)
            child_iter = model.iter_children(model.get_iter(row_reference.get_path()))
            while child_iter != None:
                path_child = model.get_path(child_iter)
                path_str_child = model[path_child][1]
                self.transfer_remove(path_str_child)
                child_iter = model.iter_next(child_iter)
        print 'Removed ' + path_str
    def gui_host_add(self, widget, hosts):
        default_connection = {
            'alias'            : '[ New connection ]',
            'address'          : '',
            'user'             : 'mistika',
            'port'             : 22,
            'path'             : '',
            'local_media_root' : '/',
            'push'             : False,
            'pull'             : False,
        }
        model = self.hostsTreeStore
        for host in hosts:
            connection = default_connection.copy()
            connection.update(hosts[host])
            row_values = [
                host,
                connection['address'],
                connection['user'],
                connection['port'],
                connection['path'],
                connection['local_media_root'],
                connection['push'],
                connection['pull'],
            ]
            row_iter = self.hostsTreeStore.append(None, row_values)
            #, alias='New host', address='', user='mistika', port=22, path='', selected=False
            if hosts[host]['selected']:
                self.entry_host.set_active_iter(row_iter)
                #selection.select_iter(row_iter)
                self.on_host_selected(None)
        row_values = [
                host,
                default_connection['address'],
                default_connection['user'],
                default_connection['port'],
                default_connection['path'],
                default_connection['local_media_root'],
                default_connection['push'],
                default_connection['pull'],
            ]
        row_iter = self.hostsTreeStore.append(None, row_values)
    def on_host_selected(self, host):
        #selected_host = self.entry_host.get_text()
        model = self.hostsTreeStore
        selected_row_iter = self.entry_host.get_active_iter()
        selected_row_path = model.get_path(selected_row_iter)
        self.selected_host_row_reference = gtk.TreeRowReference(model, selected_row_path)
        #(model, selected_row_iter) = selection.get_selected()
        #self.entry_host.set_text(model[selected_row_iter][0])
        self.entry_address.set_text(model[selected_row_iter][1])
        self.entry_user.set_text(model[selected_row_iter][2])
        self.entry_port.set_value(model[selected_row_iter][3])
        self.entry_projects_path.set_text(model[selected_row_iter][4])
        self.entry_local_media_root.set_text(model[selected_row_iter][5])
        self.allow_push.set_active(model[selected_row_iter][6])
        self.allow_pull.set_active(model[selected_row_iter][7])
        # status = 'Loaded hosts.'
        # self.status_bar.push(self.context_id, status)
    def gui_host_remove(self, widget):
        selection = self.hostsTree.get_selection()
        (model, iter) = selection.get_selected()
        try:
            model.remove(iter)
            t = threading.Thread(target=self.io_hosts_store)
            self.threads.append(t)
            t.setDaemon(True)
            t.start()
        except:
            raise

        #self.hostsTreeStore.append(None, ['New host', '', 'mistika', 22, ''])
    def gui_parent_modified(self, row_iter, direction):
        #print 'Modified parent of: %s' % self.projectsTreeStore.get_value(row_iter, 1)
        try:
            parent = self.projectsTreeStore.iter_parent(row_iter)
            parent_direction = self.projectsTreeStore.get_value(parent, 3)
            if parent_direction != direction:
                if parent_direction == None:
                    parent_direction = direction
                else:
                    parent_direction = self.icon_bidirectional
                self.projectsTreeStore.set_value(parent, 2, None)
                self.projectsTreeStore.set_value(parent, 3, parent_direction)
                self.projectsTreeStore.set_value(parent, 4, None)
                self.projectsTreeStore.set_value(parent, 13, '#000')
            self.gui_parent_modified(parent, parent_direction)
        except: # Reached top level
            pass
    def gui_refresh_path_disabled(self, path):
        #print 'Refreshing ' + path
        tree = self.projectsTreeStore
        file_path = path
        #print 'gui_refresh_path(%s)' % path
        if path.startswith('/'): # Absolute path, real file and child of a MISTIKA_EXTENSIONS object
            #basename = path
            parent_dir, basename = path.rsplit('/', 1) # parent_dir will not have trailing slash (unless child is absolute)
            parents = self.buffer[path].parents
        elif '/' in path:
            parent_dir, basename = path.rsplit('/', 1) # parent_dir will not have trailing slash (unless child is absolute)
            if parent_dir.endswith('/'):
                parent_dir = parent_dir[:-1]
                basename = '/' + basename
            #print 'DEBUG: %s base: %s' % (parent_dir, basename)
            parents = self.buffer[path].parents
            #print 'Parents: ' + repr(parents)
            #print 'Parent: %s %s' % (parent_dir, parent)
        else:
            parent_dir = None
            basename = path
            parents = [None]
        is_folder = self.buffer[path].size_local == 0 or self.buffer[path].size_remote == 0
        markup = basename
        fg_color = "#000"
        mtime_local_str = mtime_remote_str = size_local_str = size_remote_str = ''
        bytes_done = bytes_total = 0
        try:
            bytes_done = self.transfer_queue[path]['bytes_done']
            bytes_total = self.transfer_queue[path]['bytes_total']
        except:
            pass
        if not is_folder:
            if self.buffer[path]['mtime_local'] >= 0: mtime_local_str = human_time(self.buffer[path]['mtime_local'])
            if self.buffer[path]['mtime_remote'] >= 0: mtime_remote_str = human_time(self.buffer[path]['mtime_remote'])
            if self.buffer[path]['size_local'] >= 0: size_local_str = human_size(self.buffer[path]['size_local'])
            if self.buffer[path]['size_remote'] >= 0: size_remote_str = human_size(self.buffer[path]['size_remote'])
        if self.buffer[path]['row_references'] == []: # Create new entry
            local = None
            self.directions[path] = {}
            self.directions[path]['direction'] = None
            self.directions[path]['forced'] = False
            remote = None
            progress = 0
            progress_str = ''
            progress_visibility = False
            no_reload = False
            remote_address = str(self.remote['address'])
            if is_folder:
                icon = self.icon_folder
            else:
                icon = self.icon_file
        else: # Read existing entry
            row_reference = self.buffer[path]['row_references'][0]
            markup = tree[row_reference.get_path()][0]
            local = tree[row_reference.get_path()][2]
            direction = self.directions[path]['direction']
            remote = tree[row_reference.get_path()][4]
            progress = tree[row_reference.get_path()][5]
            progress_str = tree[row_reference.get_path()][6]
            progress_visibility = tree[row_reference.get_path()][7]
            remote_address = tree[row_reference.get_path()][8]
            no_reload = tree[row_reference.get_path()][9]
            icon = tree[row_reference.get_path()][10]
        for parent in parents:
            #print 'parent: ' + repr(parent)
            if parent == None and len(self.buffer[path]['row_references']) > 0:
                continue
            append_to_this_parent = True
            #print 'Parent: ' + repr(parent)
            if parent != None:
                if not parent in self.buffer:
                    continue
                #print 'Parent: ' + repr(parent)
                parent_row_references = self.buffer[parent]['row_references']
                #print 'parent_row_references: ' + repr(parent_row_references)
                if len(parent_row_references) == 0:
                    self.gui_refresh_path(parent)
                parent_row_iter = tree.get_iter(parent_row_references[0].get_path())
                for row_reference in self.buffer[path]['row_references']:
                    if tree.is_ancestor(parent_row_iter, tree.get_iter(row_reference.get_path())):
                        append_to_this_parent = False
            else:
                parent_row_iter = None
            if append_to_this_parent:
                #print 'Appending to parent: ' + repr(parent)
                row_iter = tree.append(parent_row_iter, [basename, path, mtime_local_str, self.directions[path]['direction'], mtime_remote_str, progress, progress_str, progress_visibility, remote_address, no_reload, icon, size_local_str, size_remote_str, fg_color, bytes_done, bytes_total])
                self.buffer[path]['row_references'].append(gtk.TreeRowReference(tree, tree.get_path(row_iter)))
                if self.buffer[path]['mtime_local'] >= self.buffer[path]['mtime_remote'] and basename.rsplit('.', 1)[-1] in MISTIKA_EXTENSIONS and not 'placeholder_child_row_reference' in self.buffer[path] and not self.buffer[path].virtual:
                    placeholder_child_iter = tree.append(row_iter, ['<i>Getting associated files ...</i>', '', '', None, '', 0, '0%', True, '', True, self.pixbuf_search, '', '', '', 0, 0])
                    self.buffer[path]['placeholder_child_row_reference'] = gtk.TreeRowReference(tree, tree.get_path(placeholder_child_iter))
                # if parent.split('.', 1)[-1] in MISTIKA_EXTENSIONS:
                #     tree.expand_row(parent_row_path)
        if self.buffer[path]['size_remote'] == self.buffer[path]['size_local']:
            #markup = '<span foreground="#888888">%s</span>' % basename
            fg_color = "#888888"
            self.directions[path]['direction'] = None
        elif self.buffer[path]['virtual']:
            fg_color = "#888888"
        else:
            markup = basename
            if not self.directions[path]['forced']:
                if self.buffer[path]['mtime_remote'] > self.buffer[path]['mtime_local']:
                    if self.buffer[path]['mtime_local'] < 0:
                        local = None
                    else:
                        local = gtk.STOCK_NO
                    self.directions[path]['direction'] = self.icon_left
                    remote = gtk.STOCK_YES
                else:
                    local = gtk.STOCK_YES
                    self.directions[path]['direction'] = self.icon_right
                    if self.buffer[path]['mtime_remote'] < 0:
                        remote = None
                    else:
                        remote = gtk.STOCK_NO
                    #gtk.STOCK_STOP
            for row_reference in self.buffer[path]['row_references']:
                row_iter = tree.get_iter(row_reference.get_path())
                self.gui_parent_modified(row_iter, self.directions[path]['direction'])
        if basename.rsplit('.', 1)[-1] in MISTIKA_EXTENSIONS:
            #markup = '<span foreground="#00cc00">%s</span>' % basename
            icon = self.icon_list
        if basename == 'PRIVATE':
            local = None
            self.directions[path]['direction'] = None
            remote = None

        for row_reference in self.buffer[path]['row_references']:
            row_path = row_reference.get_path()
            tree[row_path][0] = markup
            #tree.set_value(row_iter, 2, local)
            tree[row_path][3] = self.directions[path]['direction']
            #tree.set_value(row_iter, 4, remote)   
            tree[row_path][10] = icon
            tree[row_path][13] = fg_color  

        #if sync:
            #self.do_sync_item([path], False)
    def gui_set_value(self, model, row_reference, col, value):
        if model == None:
            model = self.projectsTreeStore
        path = row_reference.get_path()
        model[path][col] = value
    def gui_row_set_value(self, row_reference, col, value):
        model = self.projectsTreeStore
        path = row_reference.get_path()
        model[path][col] = value
    def gui_show_error(self, message):
        dialog = gtk.MessageDialog(parent=self.window, 
                            #flags=gtk.DIALOG_MODAL, 
                            type=gtk.MESSAGE_ERROR, 
                            buttons=gtk.BUTTONS_NONE, 
                            message_format=None)
        dialog.set_markup(message)
        dialog.run()
    def on_local_media_root_pick(self, widget):
        dialog = gtk.FileChooserDialog(
            title='Local media root folder',
            parent=self.window,
            action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK),
            backend=None
        )
        # dialog.set_default_response(gtk.RESPONSE_OK)
        current_folder = self.entry_local_media_root.get_text()
        dialog.set_current_folder(current_folder)
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            folder = dialog.get_filename().rstrip('/')+'/'
            self.entry_local_media_root.set_text(folder)
        else:
            print 'No folder selected'
        dialog.destroy()
        self.on_host_update(self.entry_local_media_root)
    def gui_copy_ssh_key(self, user, host, port):
        # message = 'Please enter the password for %s@%s' % (user, host)
        # dialog = gtk.MessageDialog(
        #     parent=self.window,
        #     flags=gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
        #     type=gtk.MESSAGE_QUESTION,
        #     buttons=gtk.BUTTONS_OK,
        #     message_format=None
        # )
        # dialog.set_markup(message)
        # dialog.format_secondary_markup("This will copy your public ssh key to the server.")
        # entry = gtk.Entry()
        # entry.set_visibility(False)
        # entry.connect("activate", responseToDialog, dialog, gtk.RESPONSE_OK)
        # hbox = gtk.HBox()
        # hbox.pack_start(gtk.Label("Password:"), False, 5, 5)
        # hbox.pack_end(entry)
        # dialog.vbox.pack_end(hbox, True, True, 0)
        # dialog.show_all()
        # dialog.run()
        # password = entry.get_text()
        # dialog.destroy()
        cmd = ['ssh-copy-id', '-n', 'localhost'] # Test existence of key
        if 'No such file' in subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).communicate()[0]:
            cmd = ['ssh-keygen', '-q', '-N', '']
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE)
            while proc.returncode == None:
                proc.stdin.write('\n')
                proc.stdin.flush()
            if proc.returncode > 0:
                gobject.idle_add(self.gui_show_error, 'Failed to create ssh key:\n\n'+proc.stdout.read())
                return
        cmd = ['ssh-copy-id', '-p', str(port), '%s@%s' % (user, host)]
        proc = hyperspeed.ui.terminal(cmd)
        output_full = proc.communicate()[0]
        if proc.returncode > 0:
            gobject.idle_add(self.gui_show_error, 'Could not copy ssh key:')
            return
        # proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE)
        # output_full = ''
        # while proc.returncode == None:
        #     output = ''
        #     char = None
        #     while not char in ['\r', '\n']:
        #         proc.poll()
        #         if proc.returncode != None:
        #             break
        #         char = proc.stdout.read(1)
        #         print char
        #         output += char
        #         if output.endswith('password:'):
        #             proc.stdin.write(password+'\n')
        #             proc.stdin.flush()
        #     output_full += output
        # output_full += proc.stdout.read()
        # if proc.returncode > 0:
        #     gobject.idle_add(self.gui_show_error, 'Could not copy ssh key:\n\n'+output_full)
        #     return

        # self.queue_remote.put_nowait([self.remote_connect])        
    def on_force_action(self, widget, action, row_path=None):
        # print 'Force action: ' + action
        file_infos = []
        if row_path == None:
            selection = self.projectsTree.get_selection()
            (model, pathlist) = selection.get_selected_rows()
        else:
            model = self.projectsTreeStore
            pathlist = [row_path]
        for row_path in pathlist:
            row_iter = model.get_iter(row_path)
            path_id = model[row_path][1]
            if action == 'pull':
                self.buffer[path_id].direction = 'pull'
            elif action == 'push':
                self.buffer[path_id].direction = 'push'
            elif action == 'nothing':
                self.buffer[path_id].direction = 'nothing'
            elif action == 'reset':
                self.buffer[path_id].direction_update()
            gobject.idle_add(self.buffer[path_id].gui_update)
            child_iter = model.iter_children(row_iter)
            while child_iter != None:
                row_path_child = model.get_path(child_iter)
                path_str_child = model[row_path_child][1]
                # print 'Child: ' + path_str_child
                if not path_str_child == '': self.on_force_action(None, action, row_path_child) # Avoid placeholders
                child_iter = model.iter_next(child_iter)
    def on_file_info(self, widget):
        file_infos = []
        selection = self.projectsTree.get_selection()
        (model, pathlist) = selection.get_selected_rows()
        paths = []
        for row_path in pathlist:
            path = model[row_path][1]
            file_info = 'File path: ' + path + '\n'
            for attribute in dir(self.buffer[path]):
                if attribute.startswith('_'):
                    continue
                file_info += '* %s: %s\n' % (attribute, cgi.escape(repr(getattr(self.buffer[path], attribute))))
            file_infos.append(file_info)
            #file_infos.append('File path: path + cgi.escape(pprint.pformat(self.buffer[path])))
        dialog = gtk.MessageDialog(parent=self.window, 
                            #flags=gtk.DIALOG_MODAL, 
                            type=gtk.MESSAGE_INFO, 
                            buttons=gtk.BUTTONS_NONE, 
                            message_format=None)
        dialog.set_markup('\n'.join(file_infos))
        dialog.run()
    def io_list_files_local(self, find_cmd, parent_path=False):
        #loader = gtk.image_new_from_animation(gtk.gdk.PixbufAnimation('../res/img/spinner01.gif'))
        #gobject.idle_add(self.button_load_local_projects.set_image, loader)
        gobject.idle_add(self.spinner_local.set_property, 'visible', True)
        gobject.idle_add(self.local_status_label.set_label, 'Listing local files')
        try:
            cmd = find_cmd.replace('<projects>', mistika.projects_folder).replace('<absolute>/', '/')
            if self.is_mac:
                cmd = self.aux_fix_mac_printf(cmd)
            # print repr(cmd)
            try:
                p1 = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                output, stderr = p1.communicate()
                if False and p1.returncode > 0:
                    loader.set_from_stock(gtk.STOCK_APPLY, gtk.ICON_SIZE_BUTTON)
                    gobject.idle_add(self.gui_show_error, stderr)
                    return
                self.lines_local = output.splitlines()
                #self.buffer_add(lines, 'localhost', self.projects_path_local, parent_path)
            except:
                print stderr
                raise
                gobject.idle_add(self.gui_show_error, stderr)
                return
        except:
            raise
        gobject.idle_add(self.spinner_local.set_property, 'visible', False)
        gobject.idle_add(self.local_status_label.set_label, '')
        #gobject.idle_add(loader.set_from_stock, gtk.STOCK_APPLY, gtk.ICON_SIZE_BUTTON)
    def io_list_files_remote(self, find_cmd):
        #loader = gtk.image_new_from_animation(gtk.gdk.PixbufAnimation('../res/img/spinner01.gif'))
        #gobject.idle_add(self.button_load_remote_projects.set_image, loader)
        gobject.idle_add(self.spinner_remote.set_property, 'visible', True)
        gobject.idle_add(self.remote_status_label.set_label, 'Listing remote files')
        cmd = find_cmd.replace('<projects>', self.remote['projects_path']).replace('<absolute>/', self.remote['root'])
        if self.remote['is_mac']:
            cmd = self.aux_fix_mac_printf(cmd)
        ssh_cmd = ['ssh', '-oBatchMode=yes', '-p', str(self.remote['port']), '%s@%s' % (self.remote['user'], self.remote['address']), cmd]
        # print ssh_cmd
        try:
            p1 = subprocess.Popen(ssh_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, stderr = p1.communicate()
            if False and p1.returncode > 0:
                loader.set_from_stock(gtk.STOCK_APPLY, gtk.ICON_SIZE_BUTTON)
                gobject.idle_add(self.gui_show_error, stderr)
                return
            self.lines_remote = output.splitlines()
            #self.buffer_add(lines, self.remote['alias'], self.remote['projects_path'], parent_path)
        except:
            print stderr
            raise
            gobject.idle_add(self.gui_show_error, stderr)
            return
        gobject.idle_add(self.spinner_remote.set_property, 'visible', False)
        gobject.idle_add(self.remote_status_label.set_label, '')
        #self.project_cell.set_property('foreground', '#000000')
        #self.project_cell.set_property('style', 'normal')
        #gobject.idle_add(loader.set_from_stock, gtk.STOCK_APPLY, gtk.ICON_SIZE_BUTTON)
    def buffer_add(self, lines, host, root, parent=None):
        root = root.rstrip('/')
        if not root == '':
            root += '/'
        for file_line in lines:
            # print file_line
            attributes = {
                'virtual' : False,
                'color' : COLOR_DEFAULT,
                'placeholder': False,
            }
            f_inode, f_type, f_size, f_time, full_path = file_line.strip().split(' ', 4)
            full_path, f_link_dest = full_path.split('->')
            f_inode = int(f_inode)
            f_time = int(f_time.split('.')[0])
            f_type.replace('/', 'd').replace('@', 'l') # Convert mac to linux types
            if f_type == 'd':
                f_size = 0
            else:
                f_size = int(f_size)
            # if self.mappings:
            #     if host == 'localhost':
            #         mappings = [(y, x) for (x, y) in self.mappings] # reverse
            #     else:
            #         mappings = self.mappings
            #     for mapping in mappings:
            #         if full_path.startswith(mapping[0]):
            #             full_path.replace(mapping[0], mapping[1], 1)
            f_basename = full_path.strip('/').split('/')[-1]
            # parent_path_to_store = parent_path
            if full_path.startswith(root): # Relative path
                path_id = full_path.replace(root, '', 1).strip('/')
                # if '/' in path_id.strip('/'):
                #     parent_dir, basename = path_id.rsplit('/', 1) # parent_dir will not have trailing slash
                # else:
                #     parent_dir = ''
                #     basename = path_id
            else: # Absolute path
                if self.mappings:
                    if host != 'localhost':
                        full_path = self.remap_to_local(full_path)
                # if host == 'localhost':
                #     if full_path.startswith(self.remote['local_media_root']):
                #         full_path.replace(self.remote['local_media_root'], '/', 1)
                # else:
                #     if full_path.startswith(self.remote['root']):
                #         full_path.replace(self.remote['root'], '/', 1)
                path_id = full_path.rstrip('/')
                # if '/' in path_id.strip('/'):
                #     parent_dir, basename = path_id.rsplit('/', 1) # parent_dir will not have trailing slash
                    #parent_path += parent_dir
            parent_path = os.path.dirname(path_id)
            if path_id == '': # Skip root item
                continue
            if parent_path in self.buffer:
                this_parent = self.buffer[parent_path]
                if f_inode == -1: # This is a virtual folder
                    attributes['alias'] = full_path.replace(parent_path+'/', '', 1) # Prepends the slash to first level, absolute path virtual folders
            elif parent == None:
                this_parent = parent
            else:
                this_parent = self.buffer_get_parent(parent.path+'/'+path_id)
            if f_link_dest == '':
                f_link_dest = False
            elif host != 'localhost':
                f_link_dest = self.remap_to_local(f_link_dest)
            if host == 'localhost':
                attributes['type_local'] = f_type
                attributes['size_local'] = f_size
                attributes['mtime_local'] = f_time
                attributes['link_local'] = f_link_dest
            else:
                attributes['type_remote'] = f_type
                attributes['size_remote'] = f_size
                attributes['mtime_remote'] = f_time
                attributes['link_remote'] = f_link_dest
                attributes['host'] = host
            if not path_id in self.buffer:
                self.buffer[path_id] = File(path_id, this_parent, self.projectsTreeStore, self.projectsTree, attributes)
            else:
                self.buffer[path_id].set_attributes(attributes)
                if this_parent != None:
                        self.buffer[path_id].add_parent(this_parent)

    def buffer_get_parent(self, child_path_id):
        if child_path_id == '/':
            return None
        path_id = os.path.dirname(child_path_id)
        parent_path = os.path.dirname(path_id)
        alias = os.path.basename(path_id)
        if parent_path in self.buffer and not self.buffer[parent_path].virtual:
            if '//' in path_id:
                alias = '/'+alias
            else:
                alias = 'Project: '+alias
        if not path_id in self.buffer:
            attributes = {
                'virtual'    : True,
                'type_local' : 'd',
                'type_remote': 'd',
                'direction'  : 'unknown',
                'alias'      : alias ,
            }
            parent = self.buffer_get_parent(path_id)
            self.buffer[path_id] = File(path_id, parent, self.projectsTreeStore, self.projectsTree, attributes)
        return self.buffer[path_id]
    def daemon_buffer(self):
        q = self.queue_buffer
        self.daemon_buffer_active = True
        while self.daemon_buffer_active:
            try:
                #print 'daemon_buffer.get()'
                item = q.get(True, 5)
                item_len = len(item)
                try:
                    if item_len == 1:
                        item[0]()
                    else:
                        item[0](**item[1])
                    q.task_done()
                except Exception as e:
                    raise
                    print 'Error:'
                    print repr(e)
            except Queue.Empty:
                pass
    def daemon_push(self):
        BATCH_SIZE = 10 * 1000 * 1000
        self.daemon_push_active = True
        q = self.queue_push
        items_absolute = []
        items_relative = []
        queue_size_absolute = 0
        queue_size_relative = 0
        while self.daemon_push_active:
            if not self.allow_push.get_active():
                time.sleep(1)
                continue
            do_now = False
            try:
                item = q.get(True, 1)
                if item.transfer:
                    if item.absolute:
                        # print 'Push absolute path:', repr(item.path)
                        items_absolute.append(item)
                        queue_size_absolute += item.size_local
                    else:
                        # print 'Push relative path:', repr(item.path)
                        items_relative.append(item)
                        queue_size_relative += item.size_local
            except Queue.Empty:
                do_now = True
            if queue_size_absolute > BATCH_SIZE or do_now:
                self.push(items_absolute, absolute=True)
                items_absolute = []
                queue_size_absolute = 0
            if queue_size_relative > BATCH_SIZE or do_now:
                self.push(items_relative)
                items_relative = []
                queue_size_relative = 0
    def daemon_pull(self):
        BATCH_SIZE = 10 * 1000 * 1000
        self.daemon_pull_active = True
        q = self.queue_pull
        items_absolute = []
        items_relative = []
        queue_size_absolute = 0
        queue_size_relative = 0
        while self.daemon_pull_active:
            if not self.allow_pull.get_active():
                time.sleep(1)
                continue
            do_now = False
            try:
                item = q.get(True, 1)
                if item.transfer:
                    if item.absolute:
                        # print 'pull absolute path:', repr(item.path)
                        items_absolute.append(item)
                        queue_size_absolute += item.size_local
                    else:
                        # print 'pull relative path:', repr(item.path)
                        items_relative.append(item)
                        queue_size_relative += item.size_local
            except Queue.Empty:
                do_now = True
            if queue_size_absolute > BATCH_SIZE or do_now:
                self.pull(items_absolute, absolute=True)
                items_absolute = []
                queue_size_absolute = 0
            if queue_size_relative > BATCH_SIZE or do_now:
                self.pull(items_relative)
                items_relative = []
                queue_size_relative = 0
    def push(self, items, absolute=False):
        if len(items) == 0:
            return
        relative_paths = {}
        extra_args = []
        # if False and len(items) == 1:
        #     for item in items:
        #         item.transfer_start()
        #         relative_paths[item.path.lstrip('/')] = item.path
        #         if absolute:
        #             local_path = item.path
        #             remote_path = item.path
        #             extra_args.append('-KO')
        #         else:
        #             local_path = os.path.join(mistika.projects_folder, item.path)
        #             remote_path = os.path.join(self.remote['projects_path'], item.path)
        #         uri_remote = "%s@%s:%s" % (self.remote['user'], self.remote['address'], self.remote['root']+remote_path)
        #         parent_path = os.path.dirname(item.path)
        #         if not parent_path in self.buffer or self.buffer[parent_path].size_remote < 0:
        #             mkdir = 'mkdir -p '
        #             if absolute:
        #                 mkdir += "'%s'" % self.remote['root']+os.path.dirname(remote_path)
        #             else:
        #                 mkdir += "'%s'" % os.path.dirname(remote_path)
        #             cmd = ['ssh', '-oBatchMode=yes', '-p', str(self.remote['port']), '%s@%s' % (self.remote['user'], self.remote['address']), mkdir]
        #             mkdir_return = subprocess.call(cmd)
        #         cmd = ['rsync', '-e', 'ssh -p %i' % self.remote['port'], '-ua'] + extra_args + ['--progress', self.remote['local_media_root']+local_path, uri_remote]
        #         proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        #         # print repr(cmd)
        #         while proc.returncode == None:
        #             if self.abort or item.transfer == False:
        #                 item.transfer_fail('Aborted')
        #                 proc.kill()
        #                 return
        #             output = ''
        #             char = None
        #             while not char in ['\r', '\n']:
        #                 proc.poll()
        #                 if proc.returncode != None:
        #                     break
        #                 char = proc.stdout.read(1)
        #                 output += char
        #             fields = output.split()
        #             if len(fields) >= 4 and fields[1].endswith('%'):
        #                 bytes_done = int(fields[0])
        #                 bytes_done_delta = bytes_done - item.bytes_done
        #                 self.queue_push_size[0] -= bytes_done_delta
        #                 # progress_percent = float(fields[1].strip('%'))
        #                 item.set_bytes_done(bytes_done)
        #             proc.poll()
        #             # print output
        #         if proc.returncode > 0:
        #             item.transfer_fail('Error: %i' % proc.returncode)
        #         else:
        #             item.transfer_end()
        # else:
        for item in items:
            item.transfer_start()
            relative_paths[item.path.lstrip('/')] = item.path
        item = False
        temp_handle = tempfile.NamedTemporaryFile()
        temp_handle.write('\n'.join(relative_paths) + '\n')
        temp_handle.flush()
        if absolute:
            base_path_local = self.remote['local_media_root']
            base_path_remote = self.remote['root']
            # extra_args.append('-O')
        else:
            base_path_local = mistika.projects_folder+'/'
            base_path_remote = self.remote['projects_path']+'/'
        uri_remote = "%s@%s:%s/" % (self.remote['user'], self.remote['address'], base_path_remote)
        cmd = [
            'rsync',
            '-e',
            'ssh -p %i' % self.remote['port'],
            '-uavvKL'
        ] + extra_args + [
            '--no-perms',
            '--progress',
            '--out-format=%b bytes: %n was copied',
            '--files-from=%s' % temp_handle.name,
            base_path_local,
            uri_remote
        ]
        # print repr(cmd)
        # print open(temp_handle.name).read()
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        while proc.returncode == None:
            if item and item.transfer == False:
                item.transfer_fail('Aborted')
                items.remove(item)
                for item in items:
                    queue_push.put(item)
            if self.abort:
                proc.kill()
                temp_handle.close()
                return
            output = ''
            char = None
            while not char in ['\r', '\n']:
                proc.poll()
                if proc.returncode != None:
                    break
                char = proc.stdout.read(1)
                output += char
            fields = output.split()
            # print output,
            if item and len(fields) >= 4 and fields[1].endswith('%'):
                bytes_done = int(fields[0])
                bytes_done_delta = bytes_done - item.bytes_done
                self.queue_push_size[0] -= bytes_done_delta
                # progress_percent = float(fields[1].strip('%'))
                item.set_bytes_done(bytes_done)
            elif output.strip().endswith('is uptodate') or output.strip().endswith('was copied'):
                if output.strip().endswith('was copied'):
                    rel_path = output.split(' ', 2)[2].replace('was copied', '').strip()
                else:
                    rel_path = output.replace('is uptodate', '')
                try:
                    path_id = relative_paths[rel_path.rstrip('/')]
                    self.buffer[path_id].transfer_end()
                    self.queue_push_size[0] -= self.buffer[path_id].size_local
                except KeyError:
                    pass
                item = False
            elif 'rsync: recv_generator: mkdir' in output and 'failed: Permission denied (13)' in output:
                folder = output.split('"', 2)[1]
                for rel_path in relative_paths:
                    path_id = relative_paths[rel_path.rstrip('/')]
                    if path_id.startswith(folder):
                        self.buffer[path_id].transfer_fail('Permission denied')
            else:
                prev_line = output.strip()
                if prev_line in self.buffer:
                    item = self.buffer[item]
            proc.poll()
        temp_handle.close()
        if proc.returncode > 0:
            print 'Error: %i' % proc.returncode
        for item in items:
            if item.is_stack and self.mappings:
                list(Stack(item.path).iter_dependencies(progress_callback=file_object.set_remap_progress, remap=self.mappings))
        self.queue_buffer.put_nowait([self.buffer_list_files, {
                    'paths' : relative_paths.values(),
                    'sync' : False
                    }])
    def pull(self, items, absolute=False):
        if len(items) == 0:
            return
        relative_paths = {}
        relative_paths_remote = {}
        extra_args = []
        # if len(items) == 1:
        #     for item in items:
        #         item.transfer_start()
        #         relative_paths[item.path.lstrip('/')] = item.path
        #         if absolute:
        #             local_path = item.path
        #             remote_path = item.path
        #             extra_args.append('-KO')
        #         else:
        #             local_path = os.path.join(mistika.projects_folder, item.path)
        #             remote_path = os.path.join(self.remote['projects_path'], item.path)
        #         uri_remote = "%s@%s:%s" % (self.remote['user'], self.remote['address'], self.remote['root']+remote_path)
        #         parent_path = os.path.dirname(item.path)
        #         if not parent_path in self.buffer or self.buffer[parent_path].size_local < 0:
        #             cmd = ['mkdir', '-p', self.remote['local_media_root']+os.path.dirname(local_path)]
        #             mkdir_return = subprocess.call(cmd)
        #         cmd = ['rsync', '-e', 'ssh -p %i' % self.remote['port'], '-ua'] + extra_args + ['--progress', uri_remote, self.remote['local_media_root']+local_path]
        #         proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        #         # print repr(cmd)
        #         while proc.returncode == None:
        #             if self.abort or item.transfer == False:
        #                 item.transfer_fail('Aborted')
        #                 proc.kill()
        #                 return
        #             output = ''
        #             char = None
        #             while not char in ['\r', '\n']:
        #                 proc.poll()
        #                 if proc.returncode != None:
        #                     break
        #                 char = proc.stdout.read(1)
        #                 output += char
        #             fields = output.split()
        #             if len(fields) >= 4 and fields[1].endswith('%'):
        #                 bytes_done = int(fields[0])
        #                 bytes_done_delta = bytes_done - item.bytes_done
        #                 self.queue_pull_size[0] -= bytes_done_delta
        #                 # progress_percent = float(fields[1].strip('%'))
        #                 item.set_bytes_done(bytes_done)
        #             proc.poll()
        #             # print output
        #         if proc.returncode > 0:
        #             item.transfer_fail('Error: %i' % proc.returncode)
        #         else:
        #             item.transfer_end()
        # else:
        for item in items:
            item.transfer_start()
            relative_paths[item.path.lstrip('/')] = item.path
            relative_paths_remote[self.remap_to_remote(item.path).lstrip('/')] = item.path
        item = False
        temp_handle = tempfile.NamedTemporaryFile()
        temp_handle.write('\n'.join(relative_paths_remote) + '\n')
        temp_handle.flush()
        if absolute:
            base_path_local = self.remote['local_media_root']
            base_path_remote = self.remote['root']
            # extra_args.append('-O')
        else:
            base_path_local = mistika.projects_folder+'/'
            base_path_remote = self.remote['projects_path']+'/'
        uri_remote = "%s@%s:%s/" % (self.remote['user'], self.remote['address'], base_path_remote)
        cmd = [
            'rsync',
            '-e',
            'ssh -p %i' % self.remote['port'],
            '-u',
            '-a',
            '-v',
            '-v',
            '-K',
            # '-L',
        ] + extra_args + [
            '--no-perms',
            '--progress',
            '--out-format=%b bytes: %n was copied',
            '--files-from=%s' % temp_handle.name,
            uri_remote,
            base_path_local
        ]
        # print repr(cmd)
        # print open(temp_handle.name).read()
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        while proc.returncode == None:
            if item and item.transfer == False:
                item.transfer_fail('Aborted')
                items.remove(item)
                for item in items:
                    queue_push.put(item)
            if self.abort:
                proc.kill()
                temp_handle.close()
                return
            output = ''
            char = None
            while not char in ['\r', '\n']:
                proc.poll()
                if proc.returncode != None:
                    break
                char = proc.stdout.read(1)
                output += char
            fields = output.split()
            print output.strip().ljust(100), repr(item)
            if item and len(fields) >= 4 and fields[1].endswith('%'):
                bytes_done = int(fields[0])
                bytes_done_delta = bytes_done - item.bytes_done
                self.queue_pull_size[0] -= bytes_done_delta
                # progress_percent = float(fields[1].strip('%'))
                item.set_bytes_done(bytes_done)
            elif output.strip().endswith('is uptodate') or output.strip().endswith('was copied'):
                if output.strip().endswith('was copied'):
                    rel_path = output.split(' ', 2)[2].replace('was copied', '').strip()
                else:
                    rel_path = output.replace('is uptodate', '')
                try:
                    path_id = relative_paths_remote[rel_path.rstrip('/')]
                    self.buffer[path_id].transfer_end()
                    self.queue_pull_size[0] -= self.buffer[path_id].size_remote
                except KeyError:
                    pass
                item = False
            elif 'rsync: recv_generator: mkdir' in output and 'failed: Permission denied (13)' in output:
                folder = output.split('"', 2)[1]
                for rel_path in relative_paths_remote:
                    path_id = relative_paths_remote[rel_path.rstrip('/')]
                    if path_id.startswith(folder):
                        self.buffer[path_id].transfer_fail('Permission denied')
            else:
                prev_line = output.strip()
                try:
                    item = self.buffer[relative_paths_remote[prev_line.rstrip('/')]]
                except KeyError:
                    pass
            proc.poll()
        temp_handle.close()
        if proc.returncode > 0:
            print 'Error: %i' % proc.returncode
        for item in items:
            full_path_local = base_path_local+'/'+item.path
            # if item.type_remote == 'l':
            if os.path.islink(full_path_local):
                link_dest = os.readlink(full_path_local)
                link_dest_remapped = self.remap_to_local(link_dest)
                if link_dest_remapped != link_dest:
                    try: 
                        os.unlink(full_path_local)
                        os.symlink(link_dest_remapped, full_path_local)
                    except OSError:
                        print 'Could not link:', link_dest
                link_dest_abs = os.path.join(full_path_local, link_dest_remapped)
                if not os.path.exists(link_dest_abs):
                    try:
                        os.makedirs(link_dest_abs)
                    except OSError:
                        print 'Could not create dir:', link_dest_abs
            elif item.is_stack:
                if not item.path.startswith('/'):
                    project = item.path.split('/', 1)[0]
                    project_structure = []
                    for required_file in mistika.PROJECT_STRUCTURE:
                        project_structure.append(os.path.join(project, required_file))
                    for child in self.buffer[project].children:
                        project_structure.append(child.path)
                    for required_path in project_structure:
                        if required_path in self.buffer:
                            if self.buffer[required_path].size_local < 0:
                                self.queue_buffer.put_nowait([self.buffer[required_path].enqueue, {
                                    'queue_push' : self.queue_push,
                                    'queue_pull':self.queue_pull,
                                    'queue_push_size' : self.queue_push_size,
                                    'queue_pull_size' : self.queue_pull_size,
                                    'recursive' : False
                                }])
                        else:
                            try:
                                os.mkdir(os.path.join(mistika.projects_folder, required_path))
                            except OSError as e:
                                print 'Could not mkdir: ', required_path, e
                self.queue_buffer.put_nowait([self.io_get_associated, {
                    'path_id': item.path,
                    'sync': False,
                    'remap': self.mappings_to_local
                }])
        self.queue_buffer.put_nowait([self.buffer_list_files, {
                    'paths' : relative_paths.values(),
                    'sync' : False
                    }])
    def daemon_remote(self):
        q = self.queue_remote
        q.put_nowait([self.remote_connect])
        self.daemon_remote_active = True
        while self.daemon_remote_active:
            try:
                #print 'daemon_remote.get()'
                item = q.get(True, 10)
                #self.loader_remote = gtk.image_new_from_animation(gtk.gdk.PixbufAnimation('../res/img/spinner01.gif'))
                #gobject.idle_add(self.button_connect.set_image, self.spinner)
                gobject.idle_add(self.spinner_remote.set_property, 'visible', True)
                item_len = len(item)
                try:
                    if item_len == 1:
                        item[0]()
                    else:
                        item[0](**item[1])
                    #gobject.idle_add(self.button_connect.set_image, self.icon_connected)
                    #gobject.idle_add(self.loader_remote.set_from_stock, gtk.STOCK_APPLY, gtk.ICON_SIZE_BUTTON)
                    q.task_done()
                    gobject.idle_add(self.spinner_remote.set_property, 'visible', False)
                except Exception as e:
                    gobject.idle_add(self.spinner_remote.set_property, 'visible', False)
                    print 'Error:'
                    print repr(e)
                    #gobject.idle_add(self.button_connect.set_image, self.icon_stop)
                    #gobject.idle_add(self.loader_remote.set_from_stock, gtk.STOCK_STOP, gtk.ICON_SIZE_BUTTON)
            except Queue.Empty:
                pass
    def daemon_local(self):
        q = self.queue_local
        self.daemon_local_active = True
        while self.daemon_local_active:
            try:
                item = q.get(True, 1)
                item_len = len(item)
                try:
                    if item_len == 1:
                        item[0]()
                    else:
                        item[0](**item[1])
                    q.task_done()
                except Exception as e:
                    print 'Error:'
                    print repr(e)
            except Queue.Empty:
                time.sleep(1)
    def remote_get_projects_path(self):
        cmd = ['ssh', '-oBatchMode=yes', '-p', str(self.remote['port']), '%s@%s' % (self.remote['user'], self.remote['address']), 'cat MISTIKA-ENV/MISTIKA_WORK MAMBA-ENV/MAMBA_WORK']
        p1 = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, stderr = p1.communicate()
        # print output
        if output != '':
            outline1 = output.splitlines()[0]
            outfields = outline1.split(None, 1)
            if outfields[0].endswith('_WORK') and len(outfields) == 2:
                return outfields[1]
        self.remote_status_label.set_markup('Could not get read MISTIKA-ENV/MISTIKA_WORK or MAMBA-ENV/MAMBA_WORK in home directory of user %s' % self.remote['user'])
        return None
    def remote_get_root_path(self):
        cmd = ['ssh', '-oBatchMode=yes', '-p', str(self.remote['port']), '%s@%s' % (self.remote['user'], self.remote['address']), 'cat msync-root.cfg']
        p1 = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, stderr = p1.communicate()
        # print output
        if output != '':
            fake_root = output.splitlines()[0]
            if not fake_root.endswith('/'):
                fake_root += '/'
            return fake_root
        else:
            return '/'
    def remote_disconnect(self):
        self.queue_buffer.put_nowait([self.buffer_clear])
        self.daemon_remote_active = False
        gobject.idle_add(self.gui_disconnected)
        #self.spinner_remote.set_property('visible', False)
    def remote_connect(self):
        #gobject.idle_add(self.button_connect.set_image, self.spinner)
        #selection = self.hostsTree.get_selection()
        #(model, iter) = selection.get_selected()
        #self.spinner_remote.set_property('visible', True)
        self.remote['alias'] = self.entry_host.get_active_text()
        self.remote_status_label.set_markup('Connecting')
        self.remote['address'] = self.entry_address.get_text()
        self.remote['user'] = self.entry_user.get_text()
        self.remote['port'] = self.entry_port.get_value_as_int()
        self.remote['projects_path'] = self.entry_projects_path.get_text().rstrip('/')
        self.remote['local_media_root'] = self.entry_local_media_root.get_text().rstrip('/')+'/'
        #self.remote['projects_path'] = self.remote['projects_path'].rstrip('/')+'/'
        cmd = ['ssh', '-oBatchMode=yes', '-p', str(self.remote['port']), '%s@%s' % (self.remote['user'], self.remote['address']), 'uname']
        p1 = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, stderr = p1.communicate()
        if p1.returncode > 0:
            #gobject.idle_add(self.loader_remote.set_from_stock, gtk.STOCK_STOP, gtk.ICON_SIZE_BUTTON)
            gobject.idle_add(self.button_connect.set_image, self.icon_connect)
            if 'Permission denied' in stderr:
                gobject.idle_add(self.remote_status_label.set_markup, '')
                gobject.idle_add(self.gui_copy_ssh_key, self.remote['user'], self.remote['address'], self.remote['port'])
                return
            else:
                gobject.idle_add(self.gui_show_error, stderr)
                gobject.idle_add(self.remote_status_label.set_markup, 'Connection error.')
                raise 'Connection error'
        else:
            if 'Darwin' in output:
                self.remote['is_mac'] = True
            else:
                self.remote['is_mac'] = False
        if self.remote['projects_path'] == '':
            remote_projects_path = self.remote_get_projects_path()
            if remote_projects_path == None:
                return
            else:
                self.remote['projects_path'] = remote_projects_path
                self.entry_projects_path.set_text(remote_projects_path)
            #self.entry_address.set_property('editable', False)
        self.remote['root'] = self.remote_get_root_path()
        mappings = self.mappings = [
            (self.remote['local_media_root'], self.remote['root']),
            (mistika.projects_folder, self.remote['projects_path'])
        ]
        mappings = [x for x in mappings if not x[0] == x[1]]
        self.mappings_to_local = [(y, x) for (x, y) in mappings]
        gobject.idle_add(self.gui_connected)
        self.queue_buffer.put_nowait([self.buffer_list_files])
    def buffer_clear(self):
        self.buffer = {}
    def gui_connected(self):
            self.remote_status_label.set_markup('')
            self.entry_host.set_sensitive(False)
            self.entry_address.set_sensitive(False)
            self.entry_user.set_sensitive(False)
            self.entry_port.set_sensitive(False)
            self.entry_projects_path.set_sensitive(False)
            self.entry_local_media_root.set_sensitive(False)
            self.entry_local_media_root_button.set_sensitive(False)
            gobject.idle_add(self.button_connect.set_property, 'visible', False)
            gobject.idle_add(self.button_disconnect.set_property, 'visible', True)
            # gobject.idle_add(self.label_active_host.set_markup,
            #     '<span foreground="#888888">Connected to host:</span> %s <span foreground="#888888">(%s)</span>'
            #     % (self.remote['alias'], self.remote['address']))
    def gui_disconnected(self):
        self.projectsTreeStore.clear()
        self.entry_host.set_sensitive(True)
        self.entry_address.set_sensitive(True)
        self.entry_user.set_sensitive(True)
        self.entry_port.set_sensitive(True)
        self.entry_projects_path.set_sensitive(True)
        self.button_disconnect.set_property('visible', False)
        self.button_connect.set_property('visible', True)
        self.spinner_remote.set_property('visible', False)
    def launch_thread(self, target, args=False):
        if args:
            t = threading.Thread(target=target, args=args)
        else:
            t = threading.Thread(target=target)
        self.threads.append(t)
        t.setDaemon(True)
        t.start()
        return t
    def remap_to_remote(self, path):
        for mapping in self.mappings:
            if path.startswith(mapping[0]):
                path = path.replace(mapping[0], mapping[1], 1)
        return path
    def remap_to_local(self, path):
        for mapping in self.mappings_to_local:
            if path.startswith(mapping[0]):
                path = path.replace(mapping[0], mapping[1], 1)
        return path
    def buffer_list_files(self, paths=[''], parent=None, sync=False, maxdepth = 2, pre_allocate=False):
        type_filter = ''
        maxdepth_str = ''
        if paths == ['']:
            type_filter = ' -type d'
        search_paths_local  = ''
        search_paths_remote = ''
        for path in paths:
            if type(path) is tuple:
                f_path, start, end = path
            else:
                f_path = path
            if f_path in self.buffer and self.buffer[f_path].virtual:
                continue
            if f_path.startswith('/'):
                root = '<absolute>'
                pre_alloc_path = f_path
            else:
                root = '<projects>/'
                pre_alloc_path = f_path
            f_path_remote = self.remap_to_remote(f_path)
            if '%' in f_path:
                search_paths_local  += ' "%s%s"' % (root, string_format_to_wildcard(f_path       , wrapping='"'))
                search_paths_remote += ' "%s%s"' % (root, string_format_to_wildcard(f_path_remote, wrapping='"'))
            else:
                search_paths_local  += ' "%s%s"' % (root, f_path       )
                search_paths_remote += ' "%s%s"' % (root, f_path_remote)
            # print 'buffer_list_files()', f_path, 'in buffer:', f_path in self.buffer
            if pre_allocate and not pre_alloc_path in self.buffer:
                # print 'pre_allocate', f_path
                attributes = {
                    'color':COLOR_WARNING,
                    'placeholder':True,
                    'virtual':True,
                    # 'alias' : f_path+':'+f_path_remote
                }
                self.buffer[pre_alloc_path] = File(pre_alloc_path, self.buffer_get_parent(parent.path+'/'+pre_alloc_path), self.projectsTreeStore, self.projectsTree, attributes)
                # gobject.idle_add(self.gui_expand, parent)
        if search_paths_local == '':
            print 'no search paths'
            return
        if maxdepth:
            maxdepth_str = ' -maxdepth %i' % maxdepth
        find_cmd_local  = 'find %s -name PRIVATE -prune -o %s %s -printf "%%i %%y %%s %%T@ %%p->%%l\\\\n"' % (search_paths_local , maxdepth_str, type_filter)
        find_cmd_remote = 'find %s -name PRIVATE -prune -o %s %s -printf "%%i %%y %%s %%T@ %%p->%%l\\\\n"' % (search_paths_remote, maxdepth_str, type_filter)
        self.lines_local = []
        self.lines_remote = []
        thread_local = self.launch_thread(target=self.io_list_files_local, args=[find_cmd_local])
        thread_remote = self.launch_thread(target=self.io_list_files_remote, args=[find_cmd_remote])
        thread_local.join()
        thread_remote.join()
        #print 'Adding local files to buffer'
        self.buffer_add(self.lines_local, 'localhost', mistika.projects_folder, parent)
        # print 'Adding remote files to buffer'
        self.buffer_add(self.lines_remote, self.remote['alias'], self.remote['projects_path'], parent)
        #print 'Adding files to GUI'
        for path in paths:
            if type(path) is tuple:
                path, start, end = path
                path = path.split('%', 1)[0]
            for f_path in sorted(self.buffer):
                #print 'f_path: ' + f_path + ' path: ' + path
                if f_path.startswith(path):
                    if not maxdepth:
                        self.buffer[f_path].deep_searched = True
                    #gobject.idle_add(self.gui_refresh_path, f_path)
            if sync:
                self.buffer[path].enqueue(
                    queue_push = self.queue_push,
                    queue_pull = self.queue_pull,
                    queue_push_size = self.queue_push_size,
                    queue_pull_size = self.queue_pull_size
                )
    def io_hosts_populate(self, tree):
        try:
            hosts = json.loads(open(CFG_HOSTS_PATH).read())
        except IOError as e:
            hosts = {}
        #print repr(hosts)
            #row_iter = tree.append(None, [host, hosts[host]['address'], hosts[host]['user'], hosts[host]['port'], hosts[host]['path']])
        gobject.idle_add(self.gui_host_add, None, hosts)
    def io_hosts_store(self, hosts):
        if not os.path.isdir(CFG_DIR):
            try:
                os.makedirs(CFG_DIR)
            except IOError as e:
                gobject.idle_add(self.gui_show_error, 'Could not create config folder:\n'+CFG_DIR)
                return
        try:
            open(CFG_HOSTS_PATH, 'w').write(json.dumps(hosts, sort_keys=True, indent=4, separators=(',', ': ')))
            status = 'Wrote to %s' % CFG_HOSTS_PATH
            print status
            #gobject.idle_add(self.status_bar.push, self.context_id, status)
        except IOError as e:
            gobject.idle_add(self.gui_show_error, 'Could not write to file:\n'+CFG_HOSTS_PATH)
        except:
            raise
    def gui_periodical_updates(self):
        try:
            self.gui_periodical_updates_history
        except AttributeError:
            self.gui_periodical_updates_history = []
        history = self.gui_periodical_updates_history
        history.append([time.time(), self.queue_push_size[0], self.queue_pull_size[0]])
        del history[:-10]
        push_speed_string = pull_speed_string = ''
        if len(history) > 1:
            push_speed = (history[0][1] - history[-1][1]) / (history[-1][0] - history[0][0])
            if push_speed >= 0:
                push_speed_string = ' rate: %sps' % human.size(push_speed, print_null=True)
                if push_speed > 0:
                    seconds_left = float(self.queue_push_size[0]) / float(push_speed)
                    push_speed_string += ' Estimated time left: ' + human.duration(seconds_left)
            pull_speed = (history[0][2] - history[-1][2]) / (history[-1][0] - history[0][0])
            if pull_speed >= 0:
                pull_speed_string = ' rate: %sps' % human.size(pull_speed, print_null=True)
                if pull_speed > 0:
                    seconds_left = float(self.queue_pull_size[0]) / float(pull_speed)
                    pull_speed_string += ' Estimated time left: ' + human.duration(seconds_left)
        # print 'gui_periodical_updates()'
        if self.queue_push_size[0] > 0:
            self.push_queue_size_label.set_text('Push queue: %s%s' % (human.size(self.queue_push_size[0]), push_speed_string))
        else:
            self.push_queue_size_label.set_text('')
        if self.queue_pull_size[0] > 0:
            self.pull_queue_size_label.set_text('Pull queue: %s%s' % (human.size(self.queue_pull_size[0]), pull_speed_string))
        else:
            self.pull_queue_size_label.set_text('')
        return True




os.environ['LC_CTYPE'] = 'en_US.utf8'
os.environ['LC_ALL'] = 'en_US.utf8'

t = MainThread()
t.start()
gtk.main()
t.quit = True
