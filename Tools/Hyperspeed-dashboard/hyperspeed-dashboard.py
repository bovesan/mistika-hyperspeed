#!/usr/bin/python
# -*- coding: utf-8 -*-

import datetime
import gobject
import gtk
import hashlib
import imp
import json
import os
import platform
import Queue
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib
import urllib2
import warnings
import webbrowser
import xml.etree.ElementTree as ET
import zipfile

import hyperspeed
import hyperspeed.tools
import hyperspeed.manage
import hyperspeed.utils
import hyperspeed.stack
import hyperspeed.sockets
from hyperspeed import mistika
from hyperspeed import video
from hyperspeed import human

VERSION_STRING = ''

CONFIG_FOLDER = '~/.mistika-hyperspeed/'
CONFIG_FILE = 'hyperspeed.cfg'
STACK_EXTENSIONS = ['.grp', '.fx', '.env']
THIS_HOST_ALIAS = 'Submitted by this machine'
OTHER_HOSTS_ALIAS = 'Submitted by others'

AUTORUN_TIMES = {
    'Never' :   False,
    'Hourly' :  '0 * * * *',
    'Daily' :   '0 4 * * *',
    'Weekly' :  '0 4 * * 7',
    'Monthly' : '0 4 1 * *'
}

CONFIG_FOLDER = os.path.expanduser(CONFIG_FOLDER)
os.chdir(hyperspeed.folder)

try:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(5.0)
    s.connect(hyperspeed.sockets.path)
    message = b'ping'
    s.send(message)
    data = s.recv(1024*1024)
    s.close()
    if data == message:
        print('Another instance is already running')
        sys.exit(0)
except socket.error as e:
    print e

s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
try:
    os.remove(hyperspeed.sockets.path)
except OSError as e:
    print e
try:
    print 'Binding socket'
    s.bind(hyperspeed.sockets.path)
    print 'Socket bound'
except socket.error as e:
    print e

def config_value_decode(value, parent_folder = False):
    try:
        value = value.replace('$BATCHPATH$', mistika.settings['BATCHPATH'])
    except KeyError:
        pass
    value = value.replace('$HOSTNAME$', socket.gethostname())
    value = value.replace('$MISTIKA-ENV$', mistika.env_folder)
    value = value.replace('$MISTIKA-SHARED$', mistika.shared_folder)
    value = os.path.expanduser(value)
    if parent_folder and not value.startswith('/'):
        value = os.path.join(parent_folder, value)
    value = os.path.abspath(value)
    return value

def md5(fname):
    hash_md5 = hashlib.md5()
    if os.path.isdir(fname):
        fnames = []
        for root, dirs, files in os.walk(fname):
            for fname in files:
                fnames.append(os.path.join(root, fname))
    else:
        fnames = [fname]
    for fname in fnames:
        try:
            with open(fname, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
        except OSError:
            pass
    return hash_md5.hexdigest()

def get_crontab_lines():
    try:
        crontab = subprocess.Popen(['crontab', '-l'], stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()[0].splitlines()
    except subprocess.CalledProcessError:
        crontab = []
    return crontab
        
def download_file(url, destination):
    if os.path.isdir(destination):
        destination = os.path.join(destination, os.path.basename(url))
    response = urllib2.urlopen(url)
    CHUNK = 256 * 1024
    with open(destination, 'wb') as f:
        while True:
            chunk = response.read(CHUNK)
            if not chunk:
                break
            f.write(chunk)
        return True

def get_zip_members(zip):
    parts = []
    # get all the path prefixes
    for name in zip.namelist():
        # only check files (not directories)
        if not name.endswith('/'):
            # keep list of path elements (minus filename)
            parts.append(name.split('/')[:-1])
    # now find the common path prefix (if any)
    prefix = os.path.commonprefix(parts)
    if prefix:
        # re-join the path elements
        prefix = '/'.join(prefix) + '/'
    # get the length of the common prefix
    offset = len(prefix)
    # now re-set the filenames
    for zipinfo in zip.infolist():
        name = zipinfo.filename
        # only check files (not directories)
        if len(name) > offset:
            # remove the common prefix
            zipinfo.filename = name[offset:]
            yield zipinfo

class PyApp(gtk.Window):
    quit = False
    subprocesses = []
    def __init__(self):
        super(PyApp, self).__init__()
        self.config_rw()
        self.threads = []
        self.queue_io = Queue.Queue()
        self.files = {}
        self.updated = False
        self.version = None
        self.change_log = []
        screen = self.get_screen()
        monitor = screen.get_monitor_geometry(0)
        self.set_title("Hyperspeed")
        self.set_default_size(monitor.width-200, monitor.height-200)
        self.set_border_width(20)
        self.set_position(gtk.WIN_POS_CENTER)
        if 'darwin' in platform.system().lower():
            self.set_resizable(False) # Because resizing crashes the app on Mac
        self.connect("key-press-event",self.on_key_press_event)
        self.set_icon_list(
            gtk.gdk.pixbuf_new_from_file_at_size('res/img/hyperspeed_1024px.png', 16, 16),
            gtk.gdk.pixbuf_new_from_file_at_size('res/img/hyperspeed_1024px.png', 32, 32),
            gtk.gdk.pixbuf_new_from_file_at_size('res/img/hyperspeed_1024px.png', 64, 64),
            gtk.gdk.pixbuf_new_from_file_at_size('res/img/hyperspeed_1024px.png', 128, 128),
            gtk.gdk.pixbuf_new_from_file_at_size('res/img/hyperspeed_1024px.png', 256, 256),
        )
        gtkrc = '''
        style "theme-fixes" {
            font_name = "sans normal 12"
        }
        class "*" style "theme-fixes"'''
        # gtk.rc_parse_string(gtkrc)
        vbox = gtk.VBox(False, 10)
        self.filterEntry = gtk.Entry()
        vbox.pack_start(self.init_toolbar(), False, False, 10)
        self.iters = {}
        self.row_references_tools = {}
        self.row_references_afterscripts = {}
        self.row_references_stacks = {}
        self.row_references_configs = {}
        self.row_references_links = {}

        self.afterscripts_model = gtk.ListStore(str)
        self.afterscripts_model.append(['None'])

        notebook = gtk.Notebook()

        notebook.append_page(self.init_tools_window(), gtk.Label('Tools'))
        notebook.append_page(self.init_afterscripts_window(), gtk.Label('Afterscripts'))
        notebook.append_page(self.init_stacks_window(), gtk.Label('Stacks'))
        notebook.append_page(self.init_configs_window(), gtk.Label('Configs'))
        notebook.append_page(self.init_links_window(), gtk.Label('Web links'))
        vbox.pack_start(notebook)

        footer = gtk.HBox(False, 10)
        button = self.refresh_button = gtk.Button(label=None, stock=gtk.STOCK_REFRESH)
        button.connect('clicked', self.on_refresh)
        footer.pack_start(button, False, False)
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
        self.launch_thread(self.io_get_release_status)
        self.launch_thread(self.socket_listen)
    def bring_to_front(self):
        self.present()
    def init_toolbar(self):
        filterEntry = self.filterEntry
        toolbarBox = gtk.HBox(False, 10)
        filterBox = gtk.HBox(False, 10)
        filterLabel = gtk.Label('Filter: ')
        filterBox.pack_start(filterLabel, False, False,)
        filterEntry.add_events(gtk.gdk.KEY_RELEASE_MASK)
        filterEntry.connect("activate", self.on_filter)
        filterEntry.connect("key-release-event", self.on_filter)
        filterEntry.grab_focus()
        filterBox.pack_start(filterEntry, False, False)
        toolbarBox.pack_start(filterBox, False, False)
        versionBox = gtk.HBox(False, 2)
        versionStr = VERSION_STRING
        label = self.versionLabel = gtk.Label(versionStr)
        label.set_use_markup(True)
        # label.connect("clicked", self.gui_about_dialog)
        versionBox.pack_start(label, False, False, 5)
        button = self.updateButton = gtk.Button('Update')
        button.set_no_show_all(True)
        button.connect("clicked", self.on_update)
        versionBox.pack_start(button, False, False, 5)
        button = self.infoButton = gtk.Button('i')
        button.set_no_show_all(True)
        button.connect("clicked", self.gui_about_dialog)
        versionBox.pack_start(button, False, False, 5)
        spinner = self.spinner_update = gtk.Image()
        spinner.set_no_show_all(True)
        try:
            spinner.set_from_file('res/img/spinner01.gif')
        except:
            pass
        versionBox.pack_start(spinner, False, False, 5)
        toolbarBox.pack_end(versionBox, False, False)
        return toolbarBox
    def init_tools_window(self):
        tree        = self.tools_tree      = gtk.TreeView()
        treestore   = self.tools_treestore = gtk.TreeStore(str, bool, bool, str, str, str, bool) # Name, show in Mistika, is folder, autorun, file_path, description, Show on desktop
        tree.set_tooltip_column(5)
        tree_filter = self.tools_filter    = treestore.filter_new();
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn('', cell, text=0)
        column.set_resizable(True)
        column.set_expand(True)
        tree.append_column(column)
        autorunStates = gtk.ListStore(str)
        for autorun_time in AUTORUN_TIMES:
            autorunStates.append([autorun_time])
        cell = gtk.CellRendererCombo()
        cell.set_property("editable", True)
        cell.set_property("has-entry", False)
        cell.set_property("text-column", 0)
        cell.set_property("model", autorunStates)
        cell.connect('changed', self.on_combo_changed)
        cell.connect('editing-started', self.on_editing_started)
        cell.connect("edited", self.on_autorun_set)
        toolsTreeAutorunColumn = gtk.TreeViewColumn("Autorun", cell, text=3)
        toolsTreeAutorunColumn.set_resizable(True)
        toolsTreeAutorunColumn.set_expand(False)
        toolsTreeAutorunColumn.set_cell_data_func(cell, self.hide_if_parent)
        tree.append_column(toolsTreeAutorunColumn)
        # Show on desktop
        cell = gtk.CellRendererToggle()
        cell.connect("toggled", self.on_tools_desktop_toggle, tree)
        column = gtk.TreeViewColumn("Show on desktop", cell, active=6)
        column.set_cell_data_func(cell, self.hide_if_parent)
        column.set_expand(False)
        column.set_resizable(True)
        tree.append_column(column)
        # Show in Mistika
        if hyperspeed.mistika.product == 'Mistika':
            cell = gtk.CellRendererToggle()
            cell.connect("toggled", self.on_tools_toggle, tree)
            toolsTreeInMistikaColumn = gtk.TreeViewColumn("Show in %s" % mistika.product, cell, active=1)
            toolsTreeInMistikaColumn.set_cell_data_func(cell, self.hide_if_parent)
            toolsTreeInMistikaColumn.set_expand(False)
            toolsTreeInMistikaColumn.set_resizable(True)
            tree.append_column(toolsTreeInMistikaColumn)
        tree_filter.set_visible_func(self.filter_tree, (self.filterEntry, tree));
        tree.set_model(tree_filter)
        tree.expand_all()
        tree.set_rules_hint(True)
        tree.connect('row-activated', self.on_tools_run, tree)
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(tree)
        self.launch_thread(self.io_populate_tools)
        return scrolled_window
    def init_afterscripts_window(self):
        tree        = self.afterscripts_tree      = gtk.TreeView()
        treestore   = self.afterscripts_treestore = gtk.TreeStore(
            str, # 00 Name
            bool,# 01 Show in Mistika
            bool,# 02 Is Folder
            str, # 03 File path
            str  # 04 Description
        )
        tree.set_tooltip_column(4)
        tree_filter = self.afterscripts_filter    = treestore.filter_new();
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn('', cell, text=0)
        column.set_resizable(True)
        column.set_expand(True)
        tree.append_column(column)
        cell = gtk.CellRendererToggle()
        cell.connect("toggled", self.on_afterscripts_toggle, tree)
        toolsTreeInMistikaColumn = gtk.TreeViewColumn("Show in %s" % mistika.product, cell, active=1)
        toolsTreeInMistikaColumn.set_cell_data_func(cell, self.hide_if_parent)
        toolsTreeInMistikaColumn.set_expand(False)
        toolsTreeInMistikaColumn.set_resizable(True)
        tree.append_column(toolsTreeInMistikaColumn)
        tree_filter.set_visible_func(self.filter_tree, (self.filterEntry, tree));
        tree.set_model(tree_filter)
        tree.expand_all()
        tree.set_rules_hint(True)
        tree.connect('row-activated', self.on_afterscripts_run, tree, 3)
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(tree)
        t = threading.Thread(target=self.io_populate_afterscripts)
        self.threads.append(t)
        t.setDaemon(True)
        t.start()
        return scrolled_window
    def init_stacks_window(self):
        tree        = self.stacks_tree      = gtk.TreeView()
        treestore   = self.stacks_treestore = gtk.TreeStore(str, bool, bool, str, bool, str) # Name, installed, is folder, file path, requires installation (has dependencies), description
        tree.set_tooltip_column(5)
        tree_filter = self.stacks_filter    = treestore.filter_new();
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn('', cell, text=0)
        column.set_resizable(True)
        column.set_expand(True)
        tree.append_column(column)
        cell = gtk.CellRendererToggle()
        cell.connect("toggled", self.on_stacks_toggle, tree)
        toolsTreeInMistikaColumn = gtk.TreeViewColumn("Installed", cell, active=1)
        toolsTreeInMistikaColumn.set_cell_data_func(cell, self.hide_if_parent)
        toolsTreeInMistikaColumn.add_attribute(cell, 'activatable', 4)
        #linksTreeUrlColumn.add_attribute(cell2, 'underline-set', 3)
        toolsTreeInMistikaColumn.set_expand(False)
        toolsTreeInMistikaColumn.set_resizable(True)
        tree.append_column(toolsTreeInMistikaColumn)
        tree_filter.set_visible_func(self.filter_tree, (self.filterEntry, tree));
        tree.set_model(tree_filter)
        tree.expand_all()
        tree.set_rules_hint(True)
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(tree)
        t = threading.Thread(target=self.io_populate_stacks)
        self.threads.append(t)
        t.setDaemon(True)
        t.start()
        return scrolled_window
    def init_configs_window(self):
        tree        = self.configs_tree      = gtk.TreeView()
        treestore   = self.configs_treestore = gtk.TreeStore(str, bool, bool, str, str) # Name, active, is folder, path, description
        tree.set_tooltip_column(4)
        tree_filter = self.configs_filter    = treestore.filter_new();
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn('', cell, text=0)
        column.set_resizable(True)
        column.set_expand(True)
        tree.append_column(column)
        cell = gtk.CellRendererToggle()
        cell.connect("toggled", self.on_configs_toggle, tree)
        column = gtk.TreeViewColumn("Active", cell, active=1)
        column.set_cell_data_func(cell, self.hide_if_parent)
        column.set_expand(False)
        column.set_resizable(True)
        tree.append_column(column)
        tree.set_tooltip_column(4)
        tree_filter.set_visible_func(self.filter_tree, (self.filterEntry, tree));
        tree.set_model(tree_filter)
        tree.expand_all()
        tree.set_rules_hint(True)
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(tree)
        t = threading.Thread(target=self.io_populate_configs)
        self.threads.append(t)
        t.setDaemon(True)
        t.start()
        return scrolled_window
    def init_links_window(self):
        tree        = self.links_tree      = gtk.TreeView()
        treestore   = self.links_treestore = gtk.TreeStore(str, str) # Name, url
        tree_filter = self.links_filter    = treestore.filter_new();
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn('', cell, text=0)
        column.set_resizable(True)
        column.set_expand(True)
        tree.append_column(column)
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn('URL', cell, text=1)
        column.set_resizable(True)
        column.set_expand(True)
        cell.set_property('foreground', '#0000ff')
        cell.set_property('underline', 'single')
        tree.append_column(column)
        tree_filter.set_visible_func(self.filter_tree, (self.filterEntry, tree));
        tree.set_model(tree_filter)
        tree.expand_all()
        tree.connect('row-activated', self.on_links_run, tree)
        tree.set_rules_hint(True)
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(tree)
        t = threading.Thread(target=self.io_populate_links)
        self.threads.append(t)
        t.setDaemon(True)
        t.start()
        return scrolled_window
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
    def socket_listen(self):
        s.listen(1)
        while s and not self.quit:
            conn, addr = s.accept()
            # data = conn.recv(1024*1024)
            try:
                data = conn.recv(1024)
            except IOError as e:
                print e
                continue
            if not data: break
            # conn.send(data)
            try:
                for k, v in json.loads(data).iteritems():
                    if k == 'launch':
                        print 'Launch: %s' % ' '.join(v)
                        self.subprocesses.append(subprocess.Popen(v))
            except ValueError as e:
                gobject.idle_add(self.bring_to_front)
            conn.send(data)
        conn.close()
    def io_populate_tools(self):
        file_type = 'Tools'
        file_type_defaults = {
            'Autorun' : 'Never',
            'Show in Mistika' : False,
            'Show on desktop' : False,
            'description' : 'No description available'
        }
        if not file_type in self.files:
            self.files[file_type] = {}
        files = self.files[file_type]
        tools_installed = hyperspeed.tools.get_mistika_links()
        tools_on_desktop = hyperspeed.tools.get_desktop_links()
        # Crontab
        crontab = get_crontab_lines()
        for root, dirs, filenames in os.walk(os.path.join(self.config['app_folder'], file_type)):
            for name in dirs:
                if name.startswith('.'):
                    continue
                path = os.path.join(root, name)
                if 'config.xml' in os.listdir(path):
                    tree = ET.parse(os.path.join(path, 'config.xml'))
                    treeroot = tree.getroot()
                    wrapper_path = os.path.join(path, 'wrapper')
                    if os.path.exists(wrapper_path):
                        path = wrapper_path
                    else:
                        path = os.path.join(path, treeroot.find('executable').text)
                    files[path] = {'isdir' : False}
                    for child in treeroot:
                        files[path][child.tag] = child.text
                else:
                    files[path] = {'isdir' : True}
                    files[path]['description'] = "Folder"
        for path in files:
            real_path = os.path.realpath(path)
            if not os.path.exists(path):
                del files[path]
                continue
            if files[path]['isdir']:
                continue
            for key, value in file_type_defaults.iteritems():
                files[path].setdefault(key, value)
            if real_path in tools_installed:
                files[path]['Show in Mistika'] = True
            if real_path in tools_on_desktop:
                files[path]['Show on desktop'] = True
            for line in crontab:
                line = line.strip()
                if line.endswith(path):
                    for autorun_alias, autorun_value in AUTORUN_TIMES.iteritems():
                        if autorun_value == False:
                            continue
                        if line.startswith(autorun_value):
                            files[path]['Autorun'] = autorun_alias
        gobject.idle_add(self.gui_update_tools)
    def io_populate_afterscripts(self):
        file_type = 'Afterscripts'
        file_type_defaults = {
            'Show in Mistika' : False
        }
        if not file_type in self.files:
            self.files[file_type] = {}
        files = self.files[file_type]
        # Installed afterscripts
        self.afterscripts_installed = []
        for line in open(mistika.afterscripts_path):
            alias = line.strip()
            link_path = os.path.join(mistika.scripts_folder, alias)
            self.afterscripts_installed.append(alias)
        for root, dirs, filenames in os.walk(os.path.join(self.config['app_folder'], file_type)):
            for name in dirs:
                if name.startswith('.'):
                    continue
                path = os.path.join(root, name)
                if 'config.xml' in os.listdir(path):
                    tree = ET.parse(os.path.join(path, 'config.xml'))
                    xml_root = tree.getroot()
                    wrapper_path = os.path.join(path, 'wrapper')
                    if os.path.exists(wrapper_path):
                        path = wrapper_path
                    else:
                        path = os.path.join(path, xml_root.find('executable').text)
                    files[path] = {
                        'isdir' : False,
                        'alias' : name
                    }
                    for key, value in file_type_defaults.iteritems():
                        files[path].setdefault(key, value)
                    for child in xml_root:
                        files[path][child.tag] = child.text
                    files[path]['alias_safe'] = files[path]['alias'].replace(' ', '_')
                else:
                    files[path] = {'isdir' : True}
        for path in files:
            if not os.path.exists(path):
                del files[path]
                continue
            if files[path]['isdir']:
                continue
            if files[path]['alias_safe'] in self.afterscripts_installed:
                files[path]['Show in Mistika'] = True
        gobject.idle_add(self.gui_update_afterscripts)
    def io_populate_stacks(self):
        file_type = 'Stacks'
        file_type_defaults = {
            'Installed' : True,
            'Dependent' : False
        }
        if not file_type in self.files:
            self.files[file_type] = {}
        files = self.files[file_type]
        for root, dirs, filenames in os.walk(os.path.join(self.config['app_folder'], file_type)):
            for name in dirs:
                if name.startswith('.'):
                    continue
                path = os.path.join(root, name)
                files[path] = {'isdir' : True}
            for name in filenames:
                if name.startswith('.'):
                    continue
                path = os.path.join(root, name)
                if os.path.splitext(name)[1].lower() in STACK_EXTENSIONS:
                    files[path] = {'isdir' : False}
        # stack.Stack(path).relink_dependencies()
        for path in files:
            if not os.path.exists(path):
                del files[path]
                continue
            if files[path]['isdir']:
                continue
            stack = hyperspeed.stack.Stack(path)
            for dependency in stack.dependencies:
                if not dependency.complete:
                    stack.relink_dependencies()
                    break
            if stack.comment:
                files[path]['comment'] = stack.comment
            files[path]['dependencies'] = stack.dependencies
            if len(files[path]['dependencies']) > 0:
                files[path]['Dependent'] = True
            for dependency in files[path]['dependencies']:
                if not dependency.type == 'lowres' and not dependency.complete:
                    files[path]['Installed'] = False
            for key, value in file_type_defaults.iteritems():
                files[path].setdefault(key, value)
            if files[path]['isdir']:
                continue
        gobject.idle_add(self.gui_update_stacks)
    def io_populate_configs(self):
        file_type = 'Configs'
        file_type_defaults = {
            'Active' : False,
            'Description' : 'No description available'
        }
        if not file_type in self.files:
            self.files[file_type] = {}
        files = self.files[file_type]
        for root, dirs, filenames in os.walk(os.path.join(self.config['app_folder'], file_type)):
            for name in dirs:
                path = os.path.join(root, name)
                if 'config.xml' in os.listdir(path):
                    tree = ET.parse(os.path.join(path, 'config.xml'))
                    treeroot = tree.getroot()
                    files[path] = {'isdir' : False}
                    for child in treeroot:
                        if child.tag == 'links':
                            files[path][child.tag] = []
                            for link in child:
                                link_target = config_value_decode(link.find('target').text, path)
                                link_location = config_value_decode(link.find('location').text)
                                try:
                                    link_copy = link.attrib['copy'].lower() == 'yes'
                                except KeyError:
                                    link_copy = False
                                files[path][child.tag].append((link_target, link_location, link_copy))
                                
                        elif child.tag == 'manage':
                            files[path][child.tag] = child.text.lower() == 'true'
                        else:
                            files[path][child.tag] = child.text
                else:
                    files[path] = {'isdir' : True}
        for path in files:
            if not os.path.exists(path):
                del files[path]
                continue
            if files[path]['isdir']:
                continue
            detected = True
            if files[path]['manage']:
                try:
                    if subprocess.call([os.path.join(path, 'manage'), 'detect']) > 0:
                        detected = False
                except OSError as e:
                    detected = False
            if 'links' in files[path]:
                for link_target, link, link_copy in files[path]['links']:
                    if not hyperspeed.manage.detect(link_target, link, link_copy):
                        detected = False
            files[path]['Active'] = detected
            for key, value in file_type_defaults.iteritems():
                files[path].setdefault(key, value)
        gobject.idle_add(self.gui_update_configs)
    def io_populate_links(self):
        file_type = 'Links'
        if not file_type in self.files:
            self.files[file_type] = {}
        files = self.files[file_type]
        for root, dirs, filenames in os.walk(os.path.join(self.config['app_folder'], file_type)):
            for name in dirs:
                path = os.path.join(root, name)
                files[path] = {'isdir' : True}
            for name in filenames:
                if name.endswith('.xml'):
                    path = os.path.join(root, name)
                    files[path] = {'isdir' : False}
                    tree = ET.parse(path)
                    treeroot = tree.getroot()
                    for child in treeroot:
                        if child.tag == 'link':
                            if not 'children' in files[path]:
                                files[path]['children'] = []
                            files[path]['children'].append(self.add_link(child))
                        else:
                            files[path][child.tag] = child.text
        gobject.idle_add(self.gui_update_links)
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
    def gui_update_tools(self):
        treestore = self.tools_treestore # Name, show in Mistika, is folder, autorun, file path, description, show on desktop
        row_references = self.row_references_tools
        items = self.files['Tools']
        for item_path in sorted(items):
            item = items[item_path]
            dir_name = os.path.dirname(item_path)
            if 'alias' in items[item_path]:
                alias = items[item_path]['alias']
            else:
                alias = os.path.basename(item_path)
            try:
                description = item['description']
            except KeyError:
                description = alias
            try:
                parent_row_reference = row_references[dir_name]
                parent_row_path = parent_row_reference.get_path()
                parent_row_iter = treestore.get_iter(parent_row_path)
            except KeyError:
                parent_row_iter = None
            if not item_path in row_references:
                row_iter = treestore.append(parent_row_iter, [alias, False, True, '', item_path, description, False])
                row_path = treestore.get_path(row_iter)
                row_references[item_path] = gtk.TreeRowReference(treestore, row_path)
            else:
                row_path = row_references[item_path].get_path()
            if item['isdir']:
                treestore[row_path] = (alias, False, True, '', item_path, description, False)
            else:
                treestore[row_path] = (alias, item['Show in Mistika'], False, item['Autorun'], item_path, description, item['Show on desktop'])
    def gui_update_afterscripts(self):
        treestore = self.afterscripts_treestore # Name, show in Mistika, is folder
        row_references = self.row_references_afterscripts
        items = self.files['Afterscripts']
        for item_path in sorted(items):
            item = items[item_path]
            dir_name = os.path.dirname(item_path)
            try:
                alias = items[item_path]['alias']
            except KeyError:
                alias = os.path.basename(item_path)
            try:
                description = item['description']
            except KeyError:
                description = alias
            in_model = False
            for model_row in self.afterscripts_model:
                if model_row[0] == alias:
                    in_model = True
                    break
            if not in_model:
                self.afterscripts_model.append([alias])
            try:
                parent_row_reference = row_references[dir_name]
                parent_row_path = parent_row_reference.get_path()
                parent_row_iter = treestore.get_iter(parent_row_path)
            except KeyError:
                parent_row_iter = None
            if not item_path in row_references:
                row_iter = treestore.append(parent_row_iter, [alias, False, True, item_path, description])
                row_path = treestore.get_path(row_iter)
                row_references[item_path] = gtk.TreeRowReference(treestore, row_path)
            else:
                row_path = row_references[item_path].get_path()
            if item['isdir']:
                treestore[row_path] = (alias, False, True, item_path, description)
            else:
                treestore[row_path] = (alias, item['Show in Mistika'], False, item_path, description)
        for alias in self.afterscripts_installed:
            if alias == 'None2':
                continue
            double_break = False
            for item_path in sorted(items):
                if items[item_path]['alias'] == alias:
                    double_break = True
                    break
            if double_break:
                break
            row_iter = treestore.append(None, [alias, True, True, '', ''])
    def gui_update_stacks(self):
        treestore = self.stacks_treestore # Name, installed, is folder, file path, requires installation (has dependencies)
        row_references = self.row_references_stacks
        items = self.files['Stacks']
        for item_path in sorted(items):
            item = items[item_path]
            dir_name = os.path.dirname(item_path)
            base_name = os.path.basename(item_path)
            try:
                description = item['comment']
            except KeyError:
                description = base_name
            try:
                if item['Dependent']:
                    dependency_lines = []
                    description += '\n\nDependencies:\n'
                    for dependency in item['dependencies']:
                        dependency_line = '* '+dependency.type+': '+dependency.path
                        if not dependency.complete:
                            dependency_line += ' <b>missing</b>'
                        dependency_lines.append(dependency_line)
                    description += '\n'.join(sorted(dependency_lines))
            except KeyError:
                pass
            try:
                parent_row_reference = row_references[dir_name]
                parent_row_path = parent_row_reference.get_path()
                parent_row_iter = treestore.get_iter(parent_row_path)
            except KeyError:
                parent_row_iter = None
            if not item_path in row_references:
                row_iter = treestore.append(parent_row_iter, [base_name, False, True, item_path, False, description])
                row_path = treestore.get_path(row_iter)
                row_references[item_path] = gtk.TreeRowReference(treestore, row_path)
            else:
                row_path = row_references[item_path].get_path()
            if item['isdir']:
                treestore[row_path] = (base_name, False, True, item_path, False, description)
            else:
                treestore[row_path] = (base_name, item['Installed'], False, item_path, item['Dependent'], description)
        # self.gui_hide_empty_folders(treestore)
    def gui_update_configs(self):
        treestore = self.configs_treestore # Name, show in Mistika, is folder
        row_references = self.row_references_configs
        items = self.files['Configs']
        item_paths = []
        for item_path in sorted(items):
            if os.path.basename(item_path) == 'Hyperspeed':
                item_paths.insert(0, item_path)
            else:
                item_paths.append(item_path)
        for item_path in item_paths:
            item = items[item_path]
            dir_name = os.path.dirname(item_path)
            try:
                alias = items[item_path]['alias']
            except KeyError:
                alias = os.path.basename(item_path)
            try:
                description = items[item_path]['description']
            except KeyError:
                description = ''
            try:
                parent_row_reference = row_references[dir_name]
                parent_row_path = parent_row_reference.get_path()
                parent_row_iter = treestore.get_iter(parent_row_path)
            except KeyError:
                parent_row_iter = None
            if not item_path in row_references:
                row_iter = treestore.append(parent_row_iter, [alias, False, True, item_path, ''])
                row_path = treestore.get_path(row_iter)
                row_references[item_path] = gtk.TreeRowReference(treestore, row_path)
            else:
                row_path = row_references[item_path].get_path()
            if item['isdir']:
                treestore[row_path] = (alias, False, True, item_path, 'Folder')
            else:
                treestore[row_path] = (alias, item['Active'], False, item_path, items[item_path]['description'])
    def gui_update_links(self):
        treestore = self.links_treestore # Name, show in Mistika, is folder
        iters = self.iters
        row_references = self.row_references_links
        items = self.files['Links']
        for item_path in sorted(items):
            item = items[item_path]
            parent_row_iter = None
            if 'alias' in items[item_path]:
                alias = items[item_path]['alias']
            else:
                alias = os.path.basename(item_path)
            url = ''
            try:
                url = item['url']
            except KeyError:
                pass
            if not item_path in row_references:
                row_iter = treestore.append(parent_row_iter, [alias, url])
                row_path = treestore.get_path(row_iter)
                row_references[item_path] = gtk.TreeRowReference(treestore, row_path)
            else:
                row_path = row_references[item_path].get_path()
                row_iter = treestore.get_iter(row_path)
                treestore[row_path] = (alias, url)
            if 'children' in item:
                parent_row_iter = row_iter
                for child in item['children']:
                    child_path = item_path+'/'+child['alias']
                    if not child_path in row_references:
                        row_iter = treestore.append(parent_row_iter, [child['alias'], child['url']])
                        row_path = treestore.get_path(row_iter)
                        row_references[child_path] = gtk.TreeRowReference(treestore, row_path)
                    else:
                        row_path = row_references[item_path].get_path()
                        treestore[row_path] = (child['alias'], child['url'])
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
    def add_link(self, xmlobject):
        link_dict = {}
        for child in xmlobject:
            if child.tag == 'alias':
                link_dict['alias'] = child.text
            elif child.tag == 'url':
                link_dict['url'] =  child.text
            elif child.tag == 'link':
                link_dict['children'] = add_link(child)
        return link_dict
    def error(self, msg):
        print msg
    def config_rw(self, write=False):
        config_force = {
            'app_folder' : os.path.realpath(os.path.dirname('.'))
        }
        config_defaults = {
        }
        try:
            self.config
            self.config.update(config_force)
        except AttributeError:
            self.config = config_force
        config_path = os.path.join(CONFIG_FOLDER, CONFIG_FILE) 
        try:
            stored_config = json.loads(open(config_path).read())
        except IOError as e:
            stored_config = {}
        if write:
            if stored_config != self.config:
                print 'Writing config'
                if not os.path.isdir(CONFIG_FOLDER):
                    os.makedirs(CONFIG_FOLDER)
                    print 'Created config folder: ', CONFIG_FOLDER
                try:
                    open(config_path, 'w').write(json.dumps(self.config, sort_keys=True, indent=4, separators=(',', ': ')))
                    stored_config = self.config
                    print 'Wrote config file: ', CONFIG_FILE
                except IOError as e:
                    error('Could not write config file')
        else:
            if stored_config != self.config:
                self.config = stored_config
        for config_item in config_defaults:
            if not config_item in self.config.keys():
                print 'New default config item: ', config_item
                self.config[config_item] = config_defaults[config_item]
                self.config_rw(write=True)
        for config_item in config_force:
             if not config_item in self.config or self.config[config_item] != config_force[config_item]:
                print 'Reset config item: ', config_item
                self.config[config_item] = config_force[config_item]
                self.config_rw(write=True)
    def on_quit(self, widget):
        self.quit = True
        if type(widget) is gtk.Button:
            widget_name = widget.get_label() + ' button'
        else:
            widget_name = str(widget)
        print 'Closed by: ' + widget_name
        gtk.main_quit()
        # try:
        #     os.remove(PID_FILE)
        # except OSError as e:
        #     pass
    def on_filter(self, widget, event):
        #print widget.get_text()
        self.tools_filter.refilter();
        self.afterscripts_filter.refilter();
        self.stacks_filter.refilter();
        self.configs_filter.refilter();
        self.links_filter.refilter();
        #self.toolsTreestore.foreach(self.row_match, widget.get_text())
    def row_match(self, model, path, iter, data):
        name = self.toolsTreestore[path][0]
        match = True
        for word in data.split():
            if not word in name:
                match = False
        if match:
            self.toolsTreestore[path][0]
        # if self.myView.row_expanded(path):
        #    self.expandedLines.append(path)
        #visible_func(model, iter, user_data):
    def folder_is_empty(self, model, iter):
        is_empty = True
        for n in range(model.iter_n_children(iter)):
            child_iter = model.iter_nth_child(iter, n)
            child_has_child = model.iter_has_child(child_iter)
            child_is_folder = model.get_value(child_iter, 2)
            if not child_is_folder:
                is_empty = False
                break
            elif child_has_child:
                if not self.folder_is_empty(model, child_iter):
                    is_empty = False
        return is_empty
    def filter_tree(self, model, iter, user_data, seek_up=True, seek_down=True, filter=False):
        widget, tree = user_data
        tree.expand_all()
        if not filter:
            filter = widget.get_text().lower()
        row = model.get_value(iter, 0)
        if row == None:
            return False
        name = model.get_value(iter, 0).lower()
        parent = model.iter_parent(iter)
        has_child = model.iter_has_child(iter)
        if model.get_n_columns() > 2:
            is_folder = model.get_value(iter, 2)
            if seek_down and is_folder:
                if self.folder_is_empty(model, iter):
                    return False
            # print name + ' has child'
            # return True
        #print 'Seeking ' + name
        for word in filter.split():
            if word in name:
                continue
            relative_match = False
            if seek_down and has_child:
                #print 'Seeking children'
                for n in range(model.iter_n_children(iter)):
                    if self.filter_tree(model, model.iter_nth_child(iter, n), user_data, seek_up=False, filter=word):
                        #print 'Child matches!'
                        relative_match = True
            if seek_up and parent != None:
                #print 'Seeking parents'
                if self.filter_tree(model, parent, user_data, seek_down=False, filter=word):
                    #print 'Parent matches!'
                    relative_match = True
            if relative_match:
                continue
            return False

        return True
    def hide_if_parent(self, column, cell, model, iter):
        has_child = model.iter_has_child(iter)
        is_folder = model[iter][2]
        if is_folder:
            cell.set_property('visible', False)
            #print model[iter][0] + ' ' + model[model.iter_children(iter)][0]
        else:
            cell.set_property('visible', True)
    def on_tools_toggle(self, cellrenderertoggle, path, treeview, *ignore):
        treestore = treeview.get_model()
        try: # If there is a filter in the middle
            treestore = treestore.get_model()
        except AttributeError:
            pass
        alias = treestore[path][0]
        alias = alias.replace(' ', '_')
        activated = not treestore[path][1]
        file_path = treestore[path][4]
        hyperspeed.tools.mistika_link(
            alias=alias,
            activated=activated,
            file_path=file_path
        )
        self.launch_thread(self.io_populate_tools)
    def on_tools_desktop_toggle(self, cellrenderertoggle, path, treeview, *ignore):
        treestore = treeview.get_model()
        try: # If there is a filter in the middle
            treestore = treestore.get_model()
        except AttributeError:
            pass
        alias = treestore[path][0]
        activated = not treestore[path][6]
        file_path = treestore[path][4]
        hyperspeed.tools.desktop_link(
            alias=alias,
            activated=activated,
            file_path=file_path
        )
        self.launch_thread(self.io_populate_tools)
    def on_autorun_set(self, widget, path, text):
        temp_config_path = '/tmp/mistika-hyperspeed-crontab'
        treestore = self.tools_treestore
        alias = treestore[path][0]
        autorun = text # Never, Hourly, Daily, Weekly, Monthly
        file_path = treestore[path][4]
        stored = False
        new_config = ''
        cron_time = AUTORUN_TIMES[autorun]
        if cron_time:
            cron_line = '%s %s\n' % (cron_time, file_path)
        else:
            cron_line = ''
        try:
            for line in get_crontab_lines():
                fields = line.split(' ', 5)
                if len(fields) == 6:
                    minute, hour, date, month, weekday, cmd = fields
                    if cmd == file_path:
                        continue
                new_config += line + '\n'
            if cron_line != '':
                new_config += cron_line
        except:
            raise
        print '\nNew crontab:'
        print new_config
        open(temp_config_path, 'w').write(new_config)
        subprocess.Popen(['crontab', temp_config_path])
        print new_config
        self.launch_thread(self.io_populate_tools)
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
    def on_afterscripts_toggle(self, cellrenderertoggle, path, treeview, *ignore):
        treestore = treeview.get_model()
        try: # If there is a filter in the middle
            treestore = treestore.get_model()
        except AttributeError:
            pass
        alias = treestore[path][0]
        alias_safe = alias.replace(' ', '_')
        activated = not treestore[path][1]
        file_path = treestore[path][3]
        basename = os.path.basename(file_path)
        linked = False
        duplicates = []
        for link in os.listdir(mistika.scripts_folder):
            link_path = os.path.join(mistika.scripts_folder, link)
            if os.path.realpath(link_path) == os.path.realpath(file_path) and alias_safe == link:
                if not link == alias_safe:
                    duplicates.append(alias_safe)
                elif activated:
                    linked = True
        if activated and not linked:
            link_path = os.path.join(mistika.scripts_folder, alias_safe)
            if os.path.islink(link_path):
                os.remove(link_path)
            os.symlink(file_path, link_path)
        stored = False
        new_config = 'None\n'
        print mistika.afterscripts_path
        for line in open(mistika.afterscripts_path):
            line_alias = line.strip()
            line_path = os.path.join(mistika.scripts_folder, line_alias)
            # print 'alias:', alias, 'line_alias:', line_alias
            if line_alias in duplicates:
                continue
            if alias_safe == line_alias:
                if activated:
                    stored = True
                else:
                    continue
            elif not os.path.exists(line_path):
                continue
            new_config += line
        if activated and not stored:
            new_config += '%s\n' % alias_safe
        print '\nNew config:'
        print new_config
        open(mistika.afterscripts_path, 'w').write(new_config)
        self.launch_thread(self.io_populate_afterscripts)
    def on_stacks_toggle(self, cellrenderertoggle, treepath, *ignore):
        tree = self.stacks_treestore
        name = tree[treepath][0]
        state = not tree[treepath][1]
        path = tree[treepath][3]
        if state:
            hyperspeed.stack.Stack(path).relink_dependencies()
        self.launch_thread(self.io_populate_stacks)
    def on_configs_toggle(self, cellrenderertoggle, treepath, *ignore):
        tree = self.configs_treestore
        name = tree[treepath][0]
        state = not tree[treepath][1]
        path = tree[treepath][3]
        f_item = self.files['Configs'][path]
        if f_item['manage']:
            if state:
                if subprocess.call([os.path.join(path, 'manage'), 'install']) > 1:
                    self.gui_error_dialog('Install failed')
            else:
                if subprocess.call([os.path.join(path, 'manage'), 'remove']) > 1:
                    self.gui_error_dialog('Removal failed')
        else:
            links = f_item['links']
            if state: # Install
                for link_target, link, link_copy in links:
                    state = state and hyperspeed.manage.install(link_target, link, link_copy)
            else: # remove
                for link_target, link, link_copy in links:
                    hyperspeed.manage.remove(link_target, link, link_copy)
        self.launch_thread(self.io_populate_configs)
    def launch_subprocess(self, exec_args, terminal=False):
        print repr(exec_args)
        if terminal:
            if platform.system() == 'Linux':
                try:
                    self.subprocesses.append(subprocess.Popen([
                        'konsole',
                        '-e',
                        os.path.join(self.config['app_folder'], 'res/scripts/bash_wrapper.sh')
                        ] + exec_args))
                    return
                except OSError as e:
                    try:
                        self.subprocesses.append(subprocess.Popen([
                            'xterm',
                            '-e',
                            os.path.join(self.config['app_folder'], 'res/scripts/bash_wrapper.sh')
                            ] + exec_args))
                        return
                    except OSError as e:
                        try:
                            self.subprocesses.append(subprocess.Popen([exec_args]))
                            return
                        except:
                            pass
            elif platform.system() == 'Darwin':
                # Mac terminal will allways remain open when process quits.
                subprocess.Popen(['open', '-a', 'Terminal.app'] + exec_args)
                return
        else:
            self.subprocesses.append(subprocess.Popen(exec_args))
            return
        print 'Failed to execute %s' % repr(exec_args)
    def on_tools_run(self, treeview, path, view_column, *ignore):
        file_path = treeview.get_model()[path][4]
        self.launch_subprocess([file_path], terminal=False)
    def on_afterscripts_run(self, treeview, path, view_column, treeview_obj, cmd_column):
        model = treeview.get_model()
        print 'Not yet implemented'
        file_path = model[path][cmd_column]
        self.launch_subprocess([file_path], terminal=False)
    def on_links_run(self, treeview, path, view_column, *ignore):
        treestore = treeview.get_model()
        try: # If there is a filter in the middle
            treestore = treestore.get_model()
        except AttributeError:
            pass
        url = treestore[path][1]
        print url
        webbrowser.get('firefox').open(url)
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
    def gui_error_dialog(self, message):
        dialog = gtk.MessageDialog(self, gtk.DIALOG_DESTROY_WITH_PARENT, type=gtk.MESSAGE_ERROR, buttons=gtk.BUTTONS_CLOSE, message_format=message)
        dialog.set_position(gtk.WIN_POS_CENTER)
        response = dialog.run()
        dialog.grab_focus()
        dialog.destroy()
        if response == -8:
            return True
        else:
            return False
    def io_get_release_status(self):
        user = 'bovesan'
        repo = 'mistika-hyperspeed'
        branch = 'master'
        update_available = False
        self.version = datetime.datetime.utcfromtimestamp(float(open('RELEASE').read().strip()))
        git = os.path.isdir('.git')
        if git:
            cmd = ['git', 'config', '--get', 'remote.origin.url']
            for line in subprocess.Popen(cmd, stdout=subprocess.PIPE).communicate()[0].splitlines():
                user, repo = line.split('/')[-2:]
                if repo.endswith('.git'):
                    repo = repo[:-4]
                # print 'User:', user
                # print 'Repo:', repo
            cmd = ['git', 'branch']
            for line in subprocess.Popen(cmd, stdout=subprocess.PIPE).communicate()[0].splitlines():
                if line.startswith('*'):
                    branch = line.strip('*').strip()
                    # print 'Branch:', branch
            cmd = ['git', 'ls-remote', 'origin', '-h', 'refs/heads/'+branch]
            for line in subprocess.Popen(cmd, stdout=subprocess.PIPE).communicate()[0].splitlines():
                head = line.split()[0]
            cmd = ['git', 'rev-list', 'HEAD...'+head, '--count']
            response = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).communicate()
            if response[0].startswith('0'):
                version_string = '<span color="#00aa00" weight="bold">Branch: %s (up to date)</span>' % branch
            else:
                version_string = '<span color="#ff9900" weight="bold">Branch: %s (update available)</span>' % branch
                update_available = True
        else:
            try:
                remote_release = float(urllib2.urlopen('https://raw.githubusercontent.com/%s/%s/%s/RELEASE' % (user, repo, branch)).read())
            except urllib2.HTTPError as e:
                print e.reason
                remote_release = False
            local_release_date = human.time(self.version)
            if not remote_release:
                version_string = '<span color="#000000">Last updated: %s</span>' % local_release_date
            elif self.version == remote_release:
                version_string = '<span color="#00aa00" weight="bold">Last updated: %s (up to date)</span>' % local_release_date
            else:
                version_string = '<span color="#ff9900" weight="bold">Last updated: %s (update available)</span>' % local_release_date
                update_available = True
        server = 'https://api.github.com'
        headers = {
            'Accept': 'application/vnd.github.v3+json'
        }
        values = {
            'sha' : branch
        }
        path = '/repos/%s/%s/commits' % (user, repo)
        data = urllib.urlencode(values)
        # print repr(data)
        req = urllib2.Request(server+path+'?'+data, headers=headers)
        # print req.get_full_url()
        # print req.header_items()
        try:
            response = urllib2.urlopen(req)
            commits = json.loads(response.read())
            commits.sort(key=lambda commit: commit['commit']["committer"]['date'], reverse=True)
            self.change_log = []
            for commit in commits:
                if len(self.change_log) > 20:
                    break
                lines = commit['commit']['message'].splitlines()
                if not lines[0].startswith('Merge branch'):
                    self.change_log.append(commit)
            gobject.idle_add(self.infoButton.show)
        except urllib2.URLError as e:
            print e.reason
        if update_available:
            gobject.idle_add(self.updateButton.show)
            if git:
                gobject.idle_add(self.updateButton.set_label, 'Update (git pull)')
        gobject.idle_add(self.versionLabel.set_markup, version_string)
        time.sleep(60)
        if not self.updated:
            self.launch_thread(self.io_get_release_status)
    def on_update(self, widget=False):
        self.launch_thread(self.io_update)
    def io_update(self):
        gobject.idle_add(self.updateButton.hide)
        gobject.idle_add(self.spinner_update.show)
        pre_update_checksum = md5(os.path.realpath(sys.argv[0]))
        git = os.path.isdir(os.path.join(self.config['app_folder'], '.git'))
        if git:
            print 'git pull'
            self.launch_subprocess([os.path.join(self.config['app_folder'], 'res/scripts/gitpull.sh')])
        else:
            print 'Downloading latest version ...'
            archive = 'https://github.com/bovesan/mistika-hyperspeed/archive/master.zip'
            download_path = os.path.join(CONFIG_FOLDER, 'mistika-hyperspeed-master.zip')
            if download_file(archive, download_path):
                extract_to = self.config['app_folder']
                print 'Extract to:', extract_to
                with zipfile.ZipFile(download_path) as zf:
                    zf.extractall(extract_to, get_zip_members(zf))
            else:
                print 'Update failed'
                gobject.idle_add(self.gui_error_dialog, 'Update failed')
                gobject.idle_add(self.spinner_update.hide)
                gobject.idle_add(self.updateButton.show)
                return
            # run update script
        post_update_checksum = md5(os.path.realpath(sys.argv[0]))
        if True or pre_update_checksum != post_update_checksum:
            version_string = '<span color="#ff9900" weight="bold">Restart to complete update</span>'
            gobject.idle_add(self.versionLabel.set_markup, version_string)
            self.updated = True
        # else:
        #     version_string = '<span color="#00aa00" weight="bold">Updated</span>'
        #     gobject.idle_add(self.versionLabel.set_markup, version_string)
        self.on_refresh()
        gobject.idle_add(self.spinner_update.hide)
    def on_refresh(self, widget=False):
        self.launch_thread(self.io_populate_tools)
        self.launch_thread(self.io_populate_afterscripts)
        self.launch_thread(self.io_populate_stacks)
        self.launch_thread(self.io_populate_configs)
        self.launch_thread(self.io_populate_links)
    def gui_about_dialog(self, widget):
        dialog = gtk.MessageDialog(self, gtk.DIALOG_DESTROY_WITH_PARENT, type=gtk.MESSAGE_INFO, buttons=gtk.BUTTONS_OK)
        dialog.set_position(gtk.WIN_POS_CENTER)
        width, height = self.get_size()
        # print repr(width), repr(height)
        dialog.set_default_size(width, -1)
        date_line = False
        message = 'Change log:\n\n'
        for commit in self.change_log:
            # "2011-04-14T16:00:49Z"
            date = datetime.datetime.strptime(commit['commit']["committer"]['date'].replace('Z', 'UTC'), "%Y-%m-%dT%H:%M:%S%Z")
            if not date_line and date <= self.version:
                message = '<b>Current version: %s</b>\n\n' % self.version
                date_line = True
            message += '<span color="#555">%s</span> %s <i>%s</i>\n' % (date, commit['commit']['message'].splitlines()[0], commit['commit']["committer"]['name'])
        dialog.set_markup(message)
        dialog.run()
        dialog.resize(width, -1)
        dialog.grab_focus()
        dialog.destroy()

warnings.filterwarnings("ignore")
os.environ['LC_CTYPE'] = 'en_US.utf8'
os.environ['LC_ALL'] = 'en_US.utf8'
gobject.threads_init()
PyApp()
gtk.main()

