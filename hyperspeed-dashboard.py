#!/usr/bin/python
# -*- coding: utf-8 -*-

import gtk
import gobject
import hashlib
import imp
import json
import os
import sys
import platform
import Queue
import socket
import subprocess
import threading
import xml.etree.ElementTree as ET
import webbrowser
from distutils.spawn import find_executable

VERSION_STRING = '<span color="#ff9900" weight="bold">Development version.</span>'

CONFIG_FOLDER = '~/.mistika-hyperspeed/'
CONFIG_FILE = 'hyperspeed.cfg'
STACK_EXTENSIONS = ['.grp', '.fx', '.env']
THIS_HOST_ALIAS = 'This machine'
OTHER_HOSTS_ALIAS = 'Others'

AUTORUN_TIMES = {
    'Never' :   False,
    'Hourly' :  '0 * * * *',
    'Daily' :   '0 4 * * *',
    'Weekly' :  '0 4 * * 7',
    'Monthly' : '0 4 1 * *'
}

CONFIG_FOLDER = os.path.expanduser(CONFIG_FOLDER)
os.chdir(os.path.dirname(sys.argv[0]))

import hyperspeed.manage
from hyperspeed import stack
from hyperspeed import mistika
from hyperspeed import video
from hyperspeed import human

def config_value_decode(value, parent_folder = False):
    try:
        value = value.replace('$BATCHPATH$', mistika.settings['BATCHPATH'])
    except KeyError:
        pass
    value = value.replace('$HOSTNAME$', socket.gethostname())
    value = value.replace('$MISTIKA-ENV$', mistika.env_folder)
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
class RenderItem(hyperspeed.stack.Stack):
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

class PyApp(gtk.Window):

    def __init__(self):


        super(PyApp, self).__init__()

        self.config_rw()
        self.threads = []
        self.queue_io = Queue.Queue()
        self.files = {}
        screen = self.get_screen()
        self.set_title("Hyperspeed")
        self.set_size_request(screen.get_width()/2, screen.get_height()-200)
        self.set_border_width(20)
        self.set_position(gtk.WIN_POS_CENTER)
        if 'darwin' in platform.system().lower():
            self.set_resizable(False) # Because resizing crashes the app on Mac
        self.set_icon_from_file("res/img/hyperspeed_1024px.png")
        gtkrc = '''
        style "theme-fixes" {
            font_name = "sans normal %i"
        }
        class "*" style "theme-fixes"''' % (screen.get_width()/300)
        gtk.rc_parse_string(gtkrc)
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
        versionLabel = gtk.Label(versionStr)
        versionLabel.set_use_markup(True)
        versionBox.pack_start(versionLabel, False, False, 5)
        updateButton = gtk.Button('Update')
        #versionBox.pack_start(updateButton, False, False, 5)
        toolbarBox.pack_end(versionBox, False, False)
        return toolbarBox
    def init_tools_window(self):
        tree        = self.tools_tree      = gtk.TreeView()
        treestore   = self.tools_treestore = gtk.TreeStore(str, bool, bool, str, str, str) # Name, show in Mistika, is folder, autorun, file_path, description
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
        tree.connect('row-activated', self.on_tools_run, tree)
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(tree)
        self.launch_thread(self.io_populate_tools)
        return scrolled_window
    def init_afterscripts_window(self):
        tree        = self.afterscripts_tree      = gtk.TreeView()
        treestore   = self.afterscripts_treestore = gtk.TreeStore(str, bool, bool, str) # Name, show in Mistika, is folder, file path
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
        tree.connect('row-activated', self.on_afterscripts_run, tree)
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
        treestore   = self.stacks_treestore = gtk.TreeStore(str, bool, bool, str, bool) # Name, installed, is folder, file path, requires installation (has dependencies)
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
    def io_populate_tools(self):
        file_type = 'Tools'
        file_type_defaults = {
            'Autorun' : 'Never',
            'Show in Mistika' : False,
            'description' : 'No description available'
        }
        if not file_type in self.files:
            self.files[file_type] = {}
        files = self.files[file_type]
        # Installed tools
        tools_installed = []
        if hyperspeed.mistika.product == 'Mistika':
            for line in open(mistika.tools_path):
                line_alias, line_path = line.strip().split(' ', 1)
                tools_installed.append(line_path)
        # Crontab
        crontab = get_crontab_lines()
        for root, dirs, filenames in os.walk(os.path.join(self.config['app_folder'], file_type)):
            for name in dirs:
                path = os.path.join(root, name)
                if 'config.xml' in os.listdir(path):
                    tree = ET.parse(os.path.join(path, 'config.xml'))
                    treeroot = tree.getroot()
                    path = os.path.join(path, treeroot.find('executable').text)
                    files[path] = {'isdir' : False}
                    for child in treeroot:
                        files[path][child.tag] = child.text
                else:
                    files[path] = {'isdir' : True}
                    files[path]['description'] = "Folder"
        for path in files:
            if not os.path.exists(path):
                del files[path]
                continue
            if files[path]['isdir']:
                continue
            for key, value in file_type_defaults.iteritems():
                files[path].setdefault(key, value)
            if path in tools_installed:
                files[path]['Show in Mistika'] = True
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
        afterscripts_installed = []
        for line in open(mistika.afterscripts_path):
            alias = line.strip()
            link_path = os.path.join(mistika.scripts_folder, alias)
            afterscripts_installed.append(os.path.realpath(link_path))
        for root, dirs, filenames in os.walk(os.path.join(self.config['app_folder'], file_type)):
            for name in dirs:
                path = os.path.join(root, name)
                if 'config.xml' in os.listdir(path):
                    tree = ET.parse(os.path.join(path, 'config.xml'))
                    root = tree.getroot()
                    path = os.path.join(path, root.find('executable').text)
                    files[path] = {
                        'isdir' : False,
                        'alias' : name
                    }
                    for key, value in file_type_defaults.iteritems():
                        files[path].setdefault(key, value)
                    for child in root:
                        files[path][child.tag] = child.text
                else:
                    files[path] = {'isdir' : True}
        for path in files:
            if not os.path.exists(path):
                del files[path]
                continue
            if files[path]['isdir']:
                continue
            if path in afterscripts_installed:
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
                path = os.path.join(root, name)
                files[path] = {'isdir' : True}
            for name in filenames:
                path = os.path.join(root, name)
                if os.path.splitext(name)[1].lower() in STACK_EXTENSIONS:
                    files[path] = {'isdir' : False}
        for path in files:
            if not os.path.exists(path):
                del files[path]
                continue
            if files[path]['isdir']:
                continue
            if not 'dependencies' in files[path]:
                files[path]['dependencies'] = hyperspeed.Stack(path).dependencies
            if len(files[path]['dependencies']) > 0:
                files[path]['Dependent'] = True
            for dependency in files[path]['dependencies']:
                if not dependency.check():
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
        treestore = self.tools_treestore # Name, show in Mistika, is folder, autorun, file path, description
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
                parent_row_reference = row_references[dir_name]
                parent_row_path = parent_row_reference.get_path()
                parent_row_iter = treestore.get_iter(parent_row_path)
            except KeyError:
                parent_row_iter = None
            if not item_path in row_references:
                row_iter = treestore.append(parent_row_iter, [alias, False, True, '', item_path, ''])
                row_path = treestore.get_path(row_iter)
                row_references[item_path] = gtk.TreeRowReference(treestore, row_path)
            else:
                row_path = row_references[item_path].get_path()
            if item['isdir']:
                treestore[row_path] = (alias, False, True, '', item_path, '')
            else:
                treestore[row_path] = (alias, item['Show in Mistika'], False, item['Autorun'], item_path, item['description'])
    def gui_update_afterscripts(self):
        treestore = self.afterscripts_treestore # Name, show in Mistika, is folder
        row_references = self.row_references_afterscripts
        items = self.files['Afterscripts']
        for item_path in sorted(items):
            item = items[item_path]
            dir_name = os.path.dirname(item_path)
            if 'alias' in items[item_path]:
                alias = items[item_path]['alias']
            else:
                alias = os.path.basename(item_path)
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
                row_iter = treestore.append(parent_row_iter, [alias, False, True, item_path])
                row_path = treestore.get_path(row_iter)
                row_references[item_path] = gtk.TreeRowReference(treestore, row_path)
            else:
                row_path = row_references[item_path].get_path()
            if item['isdir']:
                treestore[row_path] = (alias, False, True, item_path)
            else:
                treestore[row_path] = (alias, item['Show in Mistika'], False, item_path)
    def gui_update_stacks(self):
        treestore = self.stacks_treestore # Name, installed, is folder, file path, requires installation (has dependencies)
        row_references = self.row_references_stacks
        items = self.files['Stacks']
        for item_path in sorted(items):
            item = items[item_path]
            dir_name = os.path.dirname(item_path)
            base_name = os.path.basename(item_path)
            try:
                parent_row_reference = row_references[dir_name]
                parent_row_path = parent_row_reference.get_path()
                parent_row_iter = treestore.get_iter(parent_row_path)
            except KeyError:
                parent_row_iter = None
            if not item_path in row_references:
                row_iter = treestore.append(parent_row_iter, [base_name, False, True, item_path, False])
                row_path = treestore.get_path(row_iter)
                row_references[item_path] = gtk.TreeRowReference(treestore, row_path)
            else:
                row_path = row_references[item_path].get_path()
            if item['isdir']:
                treestore[row_path] = (base_name, False, True, item_path, False)
            else:
                treestore[row_path] = (base_name, item['Installed'], False, item_path, item['Dependent'])
    def gui_update_configs(self):
        treestore = self.configs_treestore # Name, show in Mistika, is folder
        row_references = self.row_references_configs
        items = self.files['Configs']
        for item_path in sorted(items):
            item = items[item_path]
            dir_name = os.path.dirname(item_path)
            if 'alias' in items[item_path]:
                alias = items[item_path]['alias']
            else:
                alias = os.path.basename(item_path)
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
        config_defaults = {
            'app_folder' : os.path.dirname(os.path.realpath(sys.argv[0]))
        }
        try:
            self.config
        except AttributeError:
            self.config = {}
        config_path = os.path.join(CONFIG_FOLDER, CONFIG_FILE) 
        try:
            stored_config = json.loads(open(config_path).read())
        except IOError as e:
            stored_config = {}
        if write:
            if stored_config != self.config:
                if not os.path.isdir(CONFIG_FOLDER):
                    os.makedirs(CONFIG_FOLDER)
                try:
                    open(config_path, 'w').write(json.dumps(self.config, sort_keys=True, indent=4, separators=(',', ': ')))
                    stored_config = self.config
                except IOError as e:
                    error('Could not write config file')
        else:
            if stored_config != self.config:
                self.config = stored_config
        for config_item in config_defaults:
            if not config_item in self.config.keys():
                self.config[config_item] = config_defaults[config_item]
                self.config_rw(write=True)
    def on_quit(self, widget):
        print 'Closed by: ' + repr(widget)
        gtk.main_quit()
    def on_filter(self, widget, event):
        #print widget.get_text()
        self.toolsFilter.refilter();
        self.afterscriptsFilter.refilter();
        self.sharedFilter.refilter();
        self.linksFilter.refilter();
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
        new_config = ''
        alias = treestore[path][0]
        alias = alias.replace(' ', '_')
        activated = not treestore[path][1]
        file_path = treestore[path][4]
        stored = False
        for line in open(mistika.tools_path):
            print repr(line)
            line_alias, line_path = line.strip().split()[:2]
            print repr(line_alias)
            print repr(line_path)
            if file_path == line_path:
                if activated:
                    new_config += '%s %s\n' % (alias, file_path)
                    stored = True
                else:
                    continue
            else:
                line_path = find_executable(line_path)
                if line_path == None or not os.path.exists(line_path):
                    continue
            new_config += line
        if activated and not stored:
            new_config += '%s %s\n' % (alias, file_path)
        print '\nNew config:'
        print new_config
        open(mistika.tools_path, 'w').write(new_config)
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
        activated = not treestore[path][1]
        file_path = treestore[path][3]
        linked = False
        for link in os.listdir(mistika.scripts_folder):
            link_path = os.path.join(mistika.scripts_folder, link)
            if os.path.realpath(link_path) == os.path.realpath(file_path):
                if activated:
                    linked = True
        if activated and not linked:
            link_path = os.path.join(mistika.scripts_folder, alias)
            if os.path.islink(link_path):
                os.remove(link_path)
            os.symlink(file_path, link_path)
        stored = False
        new_config = 'None\n'
        for line in open(mistika.afterscripts_path):
            line_alias = line.strip()
            line_path = os.path.join(mistika.scripts_folder, line_alias)
            if alias == line_alias:
                if activated:
                    stored = True
                else:
                    continue
            elif not os.path.exists(line_path):
                continue
            new_config += line
        if activated and not stored:
            new_config += '%s\n' % alias
        print '\nNew config:'
        print new_config
        open(mistika.afterscripts_path, 'w').write(new_config)
        self.launch_thread(self.io_populate_afterscripts)
    def on_stacks_toggle(self, cellrenderertoggle, path, *ignore):
        print 'Not yet implemented'
        self.launch_thread(self.io_populate_stacks)
    def on_configs_toggle(self, cellrenderertoggle, treepath, *ignore):
        tree = self.configs_treestore
        name = tree[treepath][0]
        state = not tree[treepath][1]
        path = tree[treepath][3]
        f_item = self.files['Configs'][path]
        links = f_item['links']
        if state: # Install
            for link_target, link, link_copy in links:
                state = state and hyperspeed.manage.install(link_target, link, link_copy)
        else: # remove
            for link_target, link, link_copy in links:
                hyperspeed.manage.remove(link_target, link, link_copy)
        self.launch_thread(self.io_populate_configs)
    def on_tools_run(self, treeview, path, view_column, *ignore):

        file_path = self.tools_treestore[path][4]
        print file_path
        try:
            subprocess.Popen(['konsole', '-e', os.path.join(self.config['app_folder'], 'res/scripts/bash_wrapper.sh'), file_path])
            return
        except OSError as e:
            try:
                subprocess.Popen(['xterm', '-e', os.path.join(self.config['app_folder'], 'res/scripts/bash_wrapper.sh'), file_path])
                return
            except OSError as e:
                try:
                    subprocess.Popen([file_path])
                    return
                except:
                    pass
        print 'Failed to execute %s' % file_path
    def on_afterscripts_run(self, treeview, path, view_column, *ignore):
        print 'Not yet implemented'
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

os.environ['LC_CTYPE'] = 'en_US.utf8'
os.environ['LC_ALL'] = 'en_US.utf8'
gobject.threads_init()
PyApp()
gtk.main()