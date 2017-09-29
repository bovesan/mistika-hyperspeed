#!/usr/bin/env python
#-*- coding:utf-8 -*-

import copy
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

workdir = cwd = os.path.dirname(os.path.abspath(sys.argv[0]))
while not 'hyperspeed' in os.listdir(workdir) and not workdir == '/':
    workdir = os.path.dirname(workdir)
os.chdir(workdir)
try:
    sys.path.append('.')
    import hyperspeed.stack
    import hyperspeed.ui
    from hyperspeed import mistika
    from hyperspeed import human
except ImportError as e:
    print 'Could not load hyperspeed modules'
    print e
    sys.exit(1)

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
ICON_FOLDER = gtk.gdk.pixbuf_new_from_file_at_size('res/img/folder.png', 16, 16)
ICON_LIST = gtk.gdk.pixbuf_new_from_file_at_size('res/img/list.png', 16, 16)
PIXBUF_SEARCH = gtk.gdk.pixbuf_new_from_file_at_size('res/img/search.png', 16, 16)
PIXBUF_EQUAL = gtk.gdk.pixbuf_new_from_file_at_size('res/img/equal.png', 16, 16)
ICON_FILE = gtk.gdk.pixbuf_new_from_file_at_size('res/img/file.png', 16, 16)
ICON_LINK = gtk.gdk.pixbuf_new_from_file_at_size('res/img/link.png', 16, 16)
ICON_LEFT = gtk.gdk.pixbuf_new_from_file_at_size('res/img/left.png', 16, 16)
ICON_RIGHT = gtk.gdk.pixbuf_new_from_file_at_size('res/img/right.png', 16, 16)
ICON_BIDIR = gtk.gdk.pixbuf_new_from_file_at_size('res/img/reset.png', 16, 16)
ICON_INFO = gtk.gdk.pixbuf_new_from_file_at_size('res/img/info.png', 16, 16)
ICON_HELP = gtk.gdk.pixbuf_new_from_file_at_size('res/img/info.png', 12, 12)
PIXBUF_PLUS = gtk.gdk.pixbuf_new_from_file_at_size('res/img/plus.png', 16, 16)
PIXBUF_MINUS = gtk.gdk.pixbuf_new_from_file_at_size('res/img/minus.png', 16, 16)
PIXBUF_CANCEL = gtk.gdk.pixbuf_new_from_file_at_size('res/img/cancel.png', 16, 16)
PIXBUF_RESET = gtk.gdk.pixbuf_new_from_file_at_size('res/img/reset.png', 16, 16)

class MainThread(threading.Thread):
    def __init__(self):
        super(MainThread, self).__init__()
        self.threads = []
        self.buffer = {}
        self.inodes_local_to_remote = {}
        self.inodes_remote_to_local = {}
        self.inodes_dump_frequency = 10.0
        self.inodes_last_dump = 0.0
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
        self.connection = {}
        self.is_mac = False
        self.is_mamba = False
        self.transfer_queue = {}
        self.abort = False
        self.window = gtk.Window()
        self.log_level = 4
        self.line_log_level = 0
        self.prev_stdout_string = '\n'
        window = self.window
        screen = self.window.get_screen()
        monitor = screen.get_monitor_geometry(0)
        window.set_title("Mistika sync")
        window.set_size_request(monitor.width-200, monitor.height-200)
        window.set_border_width(20)
        window.set_icon_list(
            gtk.gdk.pixbuf_new_from_file_at_size('res/img/msync_icon.png', 16, 16),
            gtk.gdk.pixbuf_new_from_file_at_size('res/img/msync_icon.png', 32, 32),
            gtk.gdk.pixbuf_new_from_file_at_size('res/img/msync_icon.png', 64, 64),
            gtk.gdk.pixbuf_new_from_file_at_size('res/img/msync_icon.png', 128, 128),
            gtk.gdk.pixbuf_new_from_file_at_size('res/img/msync_icon.png', 256, 256),
        )
        window.set_position(gtk.WIN_POS_CENTER)
        if 'darwin' in platform.system().lower():
            self.is_mac = True
            self.window.set_resizable(False) # Because resizing crashes the app on Mac
            self.window.maximize()

        self.markup = {
            'h3'    : '<span foreground="#333333" size="large">%s</span>',
            'label' : '<span foreground="#888888">%s</span>'
        }
        tooltips = self.tooltips = gtk.Tooltips()

        self.init_gfx()

        vbox = gtk.VBox()
        vbox.pack_start(self.init_connection_panel(), expand=False, fill=False, padding=0)
        vbox.pack_start(self.init_settings_panel(), expand=False, fill=False, padding=0)

        vpane = gtk.VPaned()
        vpane.pack1(self.init_log_panel(), resize=False, shrink=False)
        vpane.pack2(self.init_files_panel(), resize=True, shrink=False)
        vbox.pack_start(vpane, expand=True, fill=True, padding=0)

        footer = gtk.HBox(False, 10)
        quitButton = gtk.Button('Quit')
        quitButton.set_size_request(70, 30)
        quitButton.connect("clicked", self.on_quit)
        footer.pack_end(quitButton, False, False)

        vbox.pack_end(footer, False, False, 10)

        window.add(vbox)

        window.show_all()
        window.connect("destroy", self.on_quit)
        self.window.connect("key-press-event",self.on_key_press_event)
        self.quit = False
        gobject.timeout_add(1000, self.gui_periodical_updates)
    def init_gfx(self):
        self.icon_connect = gtk.image_new_from_stock(gtk.STOCK_CONNECT,  gtk.ICON_SIZE_BUTTON)
        self.icon_disconnect = gtk.image_new_from_stock(gtk.STOCK_DISCONNECT,  gtk.ICON_SIZE_BUTTON)
        self.icon_connected = gtk.image_new_from_stock(gtk.STOCK_APPLY,  gtk.ICON_SIZE_BUTTON)
        self.icon_stop = gtk.image_new_from_stock(gtk.STOCK_STOP,  gtk.ICON_SIZE_BUTTON)
        self.icon_folder = gtk.gdk.pixbuf_new_from_file_at_size('res/img/folder.png', 16, 16)
        self.icon_list = gtk.gdk.pixbuf_new_from_file_at_size('res/img/list.png', 16, 16)
        self.pixbuf_search = gtk.gdk.pixbuf_new_from_file_at_size('res/img/search.png', 16, 16)
        self.pixbuf_equal = gtk.gdk.pixbuf_new_from_file_at_size('res/img/equal.png', 16, 16)
        self.icon_file = gtk.gdk.pixbuf_new_from_file_at_size('res/img/file.png', 16, 16)
        self.icon_left = gtk.gdk.pixbuf_new_from_file_at_size('res/img/left.png', 16, 16)
        self.icon_right = gtk.gdk.pixbuf_new_from_file_at_size('res/img/right.png', 16, 16)
        self.icon_info = gtk.gdk.pixbuf_new_from_file_at_size('res/img/info.png', 16, 16)
        self.pixbuf_plus = gtk.gdk.pixbuf_new_from_file_at_size('res/img/plus.png', 32, 32)
        self.pixbuf_plus_recursive = gtk.gdk.pixbuf_new_from_file_at_size('res/img/plus_recursive.png', 32, 32)
        self.pixbuf_plus_children = gtk.gdk.pixbuf_new_from_file_at_size('res/img/plus_children.png', 32, 32)
        self.pixbuf_minus = gtk.gdk.pixbuf_new_from_file_at_size('res/img/minus.png', 32, 32)
        self.pixbuf_minus_recursive = gtk.gdk.pixbuf_new_from_file_at_size('res/img/minus_recursive.png', 32, 32)
        self.pixbuf_minus_children = gtk.gdk.pixbuf_new_from_file_at_size('res/img/minus_children.png', 32, 32)
        self.pixbuf_cancel = gtk.gdk.pixbuf_new_from_file_at_size('res/img/cancel.png', 16, 16)
        self.pixbuf_reset = gtk.gdk.pixbuf_new_from_file_at_size('res/img/reset.png', 16, 16)
        self.spinner = gtk.Image()
        self.spinner.set_from_file('res/img/spinner01.gif')
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
        label_markup = self.markup['label']

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
        # entry.connect('activate', self.on_host_connect)
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
        entry.connect('activate', self.on_host_connect)
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
        entry.connect('activate', self.on_host_connect)
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
        entry.connect('activate', self.on_host_connect)
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
        entry.connect('key-release-event', self.on_host_update)
        entry.connect('button-release-event', self.on_host_update)
        # entry.connect('event', self.on_any_event)
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
        entry.connect('key-release-event', self.on_host_update)
        entry.connect('button-release-event', self.on_host_update)
        # entry.connect('event', self.on_any_event)
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
        entry.connect('activate', self.on_host_connect)
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
        entry.connect('activate', self.on_host_connect)
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
        spinner.set_from_file('res/img/spinner01.gif')
        #self.spinner_remote = gtk.Spinner()
        #self.spinner_remote.start()
        #self.spinner_remote.set_size_request(20, 20)
        spinner.set_no_show_all(True)
        hbox.pack_start(spinner, False, False)
        label = self.remote_status_label = gtk.Label()
        hbox.pack_start(label, False, False)

        # Local status
        spinner = self.spinner_local = gtk.Image()
        spinner.set_from_file('res/img/spinner01.gif')
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
    def init_settings_panel(self):
        tooltips = self.tooltips
        markup = self.markup
        expander = gtk.Expander('Settings')
        vbox = gtk.VBox()
        hbox = gtk.HBox()
        label = gtk.Label(markup['h3'] % 'Rename/move detection')
        label.set_use_markup(True)
        hbox.pack_start(label, False, False, 20)
        vbox.pack_start(hbox, False, False, 10)
        padding_hbox = gtk.HBox()
        padding_hbox.pack_start(gtk.Label(''), False, False, 20)
        setting_block = gtk.VBox()
        hbox = gtk.HBox()
        description = "These settings control how renamed or moved files are detected."
        description += "\nThis is triggered if a file's inode number used to belong to a file with a different path."
        description += "\nThe conditions can be set either as absolute requirements, or as 'weights' for the algorithm."
        label = gtk.Label(description)
        hbox.pack_start(label, False, False, 0)
        setting_block.pack_start(hbox, False, False, 10)
        rows = []
        weights = gtk.Adjustment(value=1, lower=-99, upper=99, step_incr=1)
        rows.append([
            None,
            gtk.Label('Required'),
            gtk.Label('Match significance'),
            gtk.Label('Mismatch significance'),
        ])
        label = gtk.Label('Size')
        label_box = gtk.HBox()
        label_box.pack_start(label, False, False, 0)
        toggle = self.setting_size_toggle = gtk.CheckButton()
        tooltips.set_tip(toggle, "The file has the same size as the counterpart.")
        match = self.setting_size_match = gtk.SpinButton(gtk.Adjustment(value=1, lower=0, upper=99, step_incr=1))
        match.set_value(1)
        mismatch = self.setting_size_mismatch = gtk.SpinButton(gtk.Adjustment(value=-1, lower=-99, upper=0, step_incr=1))
        mismatch.set_value(-1)
        rows.append([
            label_box,
            toggle,
            match,
            mismatch
        ])
        label = gtk.Label('Extension')
        label_box = gtk.HBox()
        label_box.pack_start(label, False, False, 0)
        toggle = self.setting_ext_toggle = gtk.CheckButton()
        tooltips.set_tip(toggle, "The file has the same extension as the counterpart.")
        match = self.setting_ext_match= gtk.SpinButton(gtk.Adjustment(value=1, lower=0, upper=99, step_incr=1))
        match.set_value(1)
        mismatch = self.setting_ext_mismatch = gtk.SpinButton(gtk.Adjustment(value=-1, lower=-99, upper=0, step_incr=1))
        mismatch.set_value(-1)
        rows.append([
            label_box,
            toggle,
            match,
            mismatch
        ])
        label = gtk.Label('Folder')
        label_box = gtk.HBox()
        label_box.pack_start(label, False, False, 0)
        toggle = self.setting_folder_toggle = gtk.CheckButton()
        tooltips.set_tip(toggle, "The file is in the same folder as the counterpart.")
        match = self.setting_folder_match = gtk.SpinButton(gtk.Adjustment(value=1, lower=0, upper=99, step_incr=1))
        match.set_value(1)
        mismatch = self.setting_folder_mismatch = gtk.SpinButton(gtk.Adjustment(value=-1, lower=-99, upper=0, step_incr=1))
        mismatch.set_value(-1)
        rows.append([
            label_box,
            toggle,
            match,
            mismatch
        ])
        label = gtk.Label('Folder or subfolder')
        label_box = gtk.HBox()
        label_box.pack_start(label, False, False, 0)
        toggle = self.setting_subfolder_toggle = gtk.CheckButton()
        tooltips.set_tip(toggle, "The file is in the same folder or a subfolder from the counterpart.")
        match = self.setting_subfolder_match = gtk.SpinButton(gtk.Adjustment(value=1, lower=0, upper=99, step_incr=1))
        match.set_value(1)
        mismatch = self.setting_subfolder_mismatch = gtk.SpinButton(gtk.Adjustment(value=-1, lower=-99, upper=0, step_incr=1))
        mismatch.set_value(-1)
        rows.append([
            label_box,
            toggle,
            match,
            mismatch
        ])
        label = gtk.Label('Filename')
        label_box = gtk.HBox()
        label_box.pack_start(label, False, False, 0)
        toggle = self.setting_filename_toggle = gtk.CheckButton()
        tooltips.set_tip(toggle, "The file itself has the same name as the counterpart.")
        match = self.setting_filename_match = gtk.SpinButton(gtk.Adjustment(value=1, lower=0, upper=99, step_incr=1))
        match.set_value(1)
        mismatch = self.setting_filename_mismatch = gtk.SpinButton(gtk.Adjustment(value=-1, lower=-99, upper=0, step_incr=1))
        mismatch.set_value(-1)
        rows.append([
            label_box,
            toggle,
            match,
            mismatch
        ])
        label = gtk.Label('Total confidence required:')
        confidence_requirement = gtk.SpinButton(gtk.Adjustment(value=2, lower=0, upper=999, step_incr=1))
        confidence_requirement.set_value(2)
        rows.append([
            label,
            None,
            confidence_requirement,
            None,
        ])
        table = gtk.Table(len(rows)+1, len(rows[0]))
        table.set_col_spacings(10)
        for row_number, row in enumerate(rows):
            for cell_number, widget in enumerate(row):
                if widget != None:
                    table.attach(
                        widget,
                        left_attach=cell_number,
                        right_attach=cell_number+1,
                        top_attach=row_number,
                        bottom_attach=row_number+1,
                        xoptions=gtk.FILL,
                        yoptions=gtk.FILL
                    )
        setting_block.pack_start(table)
        # radio = gtk.RadioButton(None, 'Allways follow local file')
        # setting_block.pack_start(radio, False, False, 5)
        # radio = gtk.RadioButton(radio, 'Allways follow remote file')
        # setting_block.pack_start(radio, False, False, 5)
        padding_hbox.pack_start(setting_block)
        vbox.pack_start(padding_hbox)
        expander.add(vbox)
        return expander
    def init_log_panel(self):
        vbox = gtk.VBox()
        hbox = gtk.HBox()
        label = gtk.Label('Log')
        hbox.pack_start(label, False, False, 0)
        controls = self.log_control = gtk.HBox()
        label = gtk.Label(' level:')
        controls.pack_start(label, False, False, 0)
        entry = self.entry_log_level = gtk.SpinButton(gtk.Adjustment(value=22, lower=0, upper=9999999, step_incr=1))
        entry.set_value(self.log_level)
        entry.connect('key-release-event', self.on_log_level_change)
        entry.connect('button-release-event', self.on_log_level_change)
        controls.pack_start(entry, False, False, 0)
        controls.show_all()
        controls.set_visible(False)
        controls.set_no_show_all(True)
        hbox.pack_start(controls, False, False, 0)
        vbox.pack_start(hbox, False, False, 10)
        textview = self.console = gtk.TextView()
        fontdesc = pango.FontDescription("monospace")
        textview.modify_font(fontdesc)
        textview.set_editable(False)
        textview.set_cursor_visible(False)
        textbuffer = self.console_buffer = textview.get_buffer()
        self.tags = {
            'lvl1': textbuffer.create_tag(None, foreground='#000000', size=pango.SCALE_X_LARGE),
            'lvl2': textbuffer.create_tag(None, foreground='#000000', weight=pango.WEIGHT_BOLD),
            'lvl3': textbuffer.create_tag(None, foreground='#000000'),
            'lvl4': textbuffer.create_tag(None, foreground='#888888'),
            'lvl5': textbuffer.create_tag(None, foreground='#888888', size=pango.SCALE_X_SMALL),
        }
        scroll = gtk.ScrolledWindow()
        scroll.add(textview)
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        expander = gtk.Expander("Log")
        expander.set_label_widget(vbox)
        expander.add(scroll)
        size = self.log_size = [None]
        expander.connect('activate', self.on_log_show, size, controls)
        # expander.connect("expose-event", self.on_expander_expose)
        return expander
    def init_files_panel(self):
        tooltips = self.tooltips
        vbox = self.files_panel = gtk.VBox(False, 10)
        entry = self.entry_filter = hyperspeed.ui.PlaceholderEntry('Filter')
        entry.modify_font(pango.FontDescription('light 16.0'))
        entry.add_events(gtk.gdk.KEY_RELEASE_MASK)
        entry.connect("activate", self.on_filter)
        entry.connect("key-release-event", self.on_filter)
        vbox.pack_start(entry, False, False, 0)
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
        # tree_view.set_search_equal_func(func=self.on_search)
        tree_filter = self.files_filter = tree_store.filter_new()
        tree_filter.set_visible_func(self.filter_tree, (self.entry_filter, tree_view))
        tree_view.set_model(tree_filter)
        # tree_view.set_search_column(0)
        tree_view.connect("row-expanded", self.on_expand)

        tree_store.set_sort_column_id(0, gtk.SORT_ASCENDING)
        #self.projectsTree.expand_all()

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

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(tree_view)
        vbox.pack_start(scrolled_window)

        hbox0 = gtk.HBox(False, 0)
        hbox = gtk.HBox(False, 0)
        
        button = gtk.Button()
        button.set_image(gtk.image_new_from_pixbuf(self.pixbuf_plus))
        button.connect("clicked", self.on_sync_selected, 'single')
        tooltips.set_tip(button, 'Sync selected file(s)')
        hbox.pack_start(button, False, False, 0)
        
        button = gtk.Button()
        button.set_image(gtk.image_new_from_pixbuf(self.pixbuf_plus_recursive))
        button.connect("clicked", self.on_sync_selected, 'recursive')
        tooltips.set_tip(button, 'Sync selected file(s) and all children')
        hbox.pack_start(button, False, False, 0)
        
        button = gtk.Button()
        button.set_image(gtk.image_new_from_pixbuf(self.pixbuf_plus_children))
        button.connect("clicked", self.on_sync_selected, 'children')
        tooltips.set_tip(button, 'Sync all children')
        hbox.pack_start(button, False, False, 0)

        hbox0.pack_start(hbox, False, False, 0)
        hbox = gtk.HBox(False, 0)

        button = gtk.Button()
        #self.button_sync_files.set_image(gtk.image_new_from_stock(gtk.STOCK_REFRESH,  gtk.ICON_SIZE_BUTTON))
        button.connect("clicked", self.on_file_info)
        button.set_image(gtk.image_new_from_pixbuf(self.icon_info))
        tooltips.set_tip(button, 'Show more information on selected file(s)')
        hbox.pack_start(button, False, False, 0)

        # hbox.pack_start(gtk.Label('Override action:'), False, False, 5)

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

        hbox0.pack_start(hbox, True, False, 0)
        hbox = gtk.HBox(False, 0)
        
        button = gtk.Button()
        button.set_image(gtk.image_new_from_pixbuf(self.pixbuf_minus))
        button.connect("clicked", self.on_sync_selected_abort, 'single')
        tooltips.set_tip(button, 'Remove selected file(s) from sync queue')
        hbox.pack_start(button, False, False, 0)
        
        button = gtk.Button()
        button.set_image(gtk.image_new_from_pixbuf(self.pixbuf_minus_recursive))
        button.connect("clicked", self.on_sync_selected_abort, 'recursive')
        tooltips.set_tip(button, 'Remove selected file(s) and all children from sync queue')
        hbox.pack_start(button, False, False, 0)
        
        button = gtk.Button()
        button.set_image(gtk.image_new_from_pixbuf(self.pixbuf_minus_children))
        button.connect("clicked", self.on_sync_selected_abort, 'children')
        tooltips.set_tip(button, 'Remove all children from sync queue')
        hbox.pack_start(button, False, False, 0)

        hbox0.pack_start(hbox, False, False, 0)

        vbox.pack_start(hbox0, False, False, 0)
        vbox.show_all()
        vbox.set_no_show_all(True)
        vbox.set_visible(False)
        return vbox
    def run(self):
        self.io_hosts_populate(self.hostsTreeStore)
        treeselection = self.projectsTree.get_selection()
        treeselection.set_mode(gtk.SELECTION_MULTIPLE)
    def on_filter(self, widget, event):
        print 4, 'Refilter'
        self.files_filter.refilter()
    def filter_tree(self, model, iter, user_data, seek_up=True, seek_down=True, filter_string=False):
        widget, tree = user_data
        # print 6, 'filter_tree() model: %s widget: %s tree: %s' % (model, widget, tree)
        # tree.expand_all()
        if not filter_string:
            # print 6, 'Reading filter from entry'
            filter_string = widget.get_text().lower()
        if filter_string == '':
            return True
        # print 6, repr(filter_string)
        row = model.get_value(iter, 0)
        if row == None:
            return False
        name = model.get_value(iter, 0).lower()
        parent = model.iter_parent(iter)
        has_child = model.iter_has_child(iter)
        for word in filter_string.split():
            # print 4, word
            if word in name:
                continue
            relative_match = False
            if seek_down and has_child:
                #print 'Seeking children'
                for n in range(model.iter_n_children(iter)):
                    if self.filter_tree(model, model.iter_nth_child(iter, n), user_data, seek_up=False, filter_string=word):
                        #print 'Child matches!'
                        relative_match = True
            if seek_up and parent != None:
                #print 'Seeking parents'
                if self.filter_tree(model, parent, user_data, seek_down=False, filter_string=word):
                    #print 'Parent matches!'
                    relative_match = True
            if relative_match:
                continue
            return False

        return True
    def start_daemon(self, daemon):
        t = threading.Thread(target=daemon)
        self.threads.append(t)
        t.setDaemon(True)
        t.start()
    def on_log_show(self, expander, size, controls):
        parent = expander.get_parent()
        if not expander.get_expanded():
            print 4, 'Expanding log'
            controls.set_visible(True)
            if size[0] == None:
                return
                # parent.set_position(-1)
            else:
                parent.set_position(size[0])
        else:
            print 4, 'Collapsing log'
            controls.set_visible(False)
            expander.set_expanded(True) # Because the hiding the controls triggered expose on the expander, which might have revealed it again.
            size[0] = parent.get_position()
            parent.set_position(-1)
    def on_log_level_change(self, widget, user_data):
        self.log_level = widget.get_value()
        print 1, 'Set log level: %i' % self.log_level
    def on_expander_expose(self, expander, event, **user_data):
        height = event.area[3]
        if height > 90 and not expander.get_expanded():
            expander.set_expanded(True)
    def on_any_event(self, widget, event, **user_data):
        print 4, 'Widget:', repr(widget), 'event:', repr(event)
    def aux_fix_mac_printf(self, str):
        return str.replace('-printf',  '-print0 | xargs -0 stat -f').replace('%T@', '%m').replace('%s', '%z').replace('%y', '%T').replace('%p', '%N').replace('%l', '%Y').replace('\\\\n', '')
    def aux_mistika_object_path(self, level_names):
        #print repr(level_names)
        return '/'.join(level_names)
    def on_quit(self, widget):
        print 1, 'Closed by: ' + repr(widget)
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
        treestore = treeview.get_model()
        try: # If there is a filter in the middle
            treestore = treestore.get_model()
        except AttributeError:
            pass
        treestore = treeview.get_model()
        print 4, repr(treestore), repr(iter), repr(treestore[iter][1])
        file_path = treestore[iter][1]
        # print 'Expanding ' + file_path
        file_item = self.buffer[file_path]
        if file_path.rsplit('.', 1)[-1] in hyperspeed.stack.EXTENSIONS: # Should already be loaded
            t = threading.Thread(target=self.io_get_associated, args=[file_path])
            self.threads.append(t)
            t.setDaemon(True)
            t.start()
            return
        if file_item.virtual:
            # print 'Virtual item'
            if treestore.iter_n_children(iter) == 1:
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
        print 4, 'on_search(%s, %s, %s, %s, %s, %s)' % (self, model, column, key, iter, user_data)
    def on_host_edit(self, cell, path, new_text, user_data):
        tree, column = user_data
        print 4, 'on_host_edit() %s' % tree[path][column]
        row_reference = gtk.TreeRowReference(tree, path)
        gobject.idle_add(self.gui_set_value, tree, row_reference, column, new_text)
        #tree[path][column] = new_text
        # print '-> ' + tree[path][column]
        t = threading.Thread(target=self.io_hosts_store)
        self.threads.append(t)
        t.setDaemon(True)
        t.start()
    def on_host_update(self, widget, *user_data):
        print 4, 'on_host_update(%s, %s)' % (widget, user_data)
        #print model[iter][0]
        model = self.hostsTreeStore
        # print repr(self.entry_host.get_active_iter())
        selected_row_iter = self.entry_host.get_active_iter()
        if selected_row_iter == None:
            try:
                selected_row_path = self.selected_host_row_reference.get_path()
                selected_row_iter = model.get_iter(selected_row_path)
            except AttributeError:
                selected_row_iter = self.hostsTreeStore.append(None, ['new', '', '', 0, ''])
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
            # for value in row:
            #     print value,
            # print ''
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
        # print 'hosts: ' + repr(hosts)
        t = threading.Thread(target=self.io_hosts_store, args=[hosts])
        self.threads.append(t)
        t.setDaemon(True)
        t.start()
        try:
            if gtk.gdk.keyval_name(user_data[0].keyval) == 'Return':
                self.on_host_connect(widget)
        except (IndexError, AttributeError):
            pass
    def on_host_connect(self, widget):
        self.launch_thread(self.remote_connect)
    def on_host_disconnect(self, widget):
        self.remote_disconnect()
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
        item = self.buffer[path_id]
        abs_path = os.path.join(mistika.projects_folder, path_id)
        stack = item.stack = hyperspeed.stack.Stack(abs_path)
        files_chunk_max_size = 100
        files_chunk = []
        parent_file_path = path_id
        if remap:
            progress_callback = item.set_remap_progress
        else:
            progress_callback = item.set_parse_progress
        progress_callback(progress_float=0.0)
        for dependency in stack.iter_dependencies(progress_callback=progress_callback, remap=remap):
            search_path = dependency.path
            if search_path.startswith(mistika.projects_folder):
                search_path = search_path.replace(mistika.projects_folder+'/', '', 1)
            # elif search_path.startswith(self.connection['projects_path']):
            #     search_path = search_path.replace(self.connection['projects_path']+'/', '', 1)
            # print 'search_path:', search_path
            files_chunk.append(search_path)
            if len(files_chunk) >= files_chunk_max_size:
                self.queue_buffer.put_nowait([self.buffer_list_files, {
                    'paths' : files_chunk,
                    'parent' : item,
                    'sync' : False,
                    'pre_allocate' : True,
                    'maxdepth' : 0,
                    }])
                files_chunk = []
        if len(files_chunk) > 0:
            self.queue_buffer.put_nowait([self.buffer_list_files, {
                'paths' : files_chunk,
                'parent' : item,
                'sync' : False,
                'pre_allocate' : True,
                'maxdepth' : 0,
            }])
            files_chunk = []
        self.queue_buffer.put_nowait([progress_callback, {'progress_float':1.0}])
        # self.queue_buffer.put_nowait([self.buffer_get_virtual_details, {
        #     'item' : item,
        #     'real_parent' : item
        #     }])
        if sync:
            self.queue_buffer.put_nowait([self.buffer[path_id].enqueue, {
                'push_allow' : self.allow_push.get_active(),
                'pull_allow' : self.allow_pull.get_active(), 
                'queue_push' : self.queue_push,
                'queue_pull' : self.queue_pull,
                'queue_push_size' : self.queue_push_size,
                'queue_pull_size' : self.queue_pull_size,
                }])
    def buffer_get_virtual_details(self, item, real_parent):
        # Blocks buffer to complete before sync starts
        print 4, 'buffer_get_virtual_details(%s, %s)' % (item.path_id, real_parent.path_id)
        paths = []
        if len(item.children) > 0:
            for child in item.children:
                paths += self.buffer_get_virtual_details(item=child, real_parent=real_parent)
        if item.virtual:
            f_path = item.path_id.replace(real_parent.path_id+'/', '', 1)
            paths.append(f_path)
            # print 'Virtual:', item.path_id, 'parent:', real_parent.path_id, 'real_path:', f_path
        if item == real_parent or len(paths) > 20:
            # print repr(paths),
            self.buffer_list_files(
                    paths = copy.deepcopy(paths),
                    parent = real_parent,
                    maxdepth = 0,
            )
            gobject.idle_add(item.gui_update)
            paths = []
            # print repr(paths)
        return paths
    def on_sync_selected(self, widget, mode='recursive'):
        # mode = 'single' or 'recursive' or 'children'
        selection = self.projectsTree.get_selection()
        (model, pathlist) = selection.get_selected_rows()
        for row_path in pathlist:
            row_reference = gtk.TreeRowReference(model, row_path)
            path_id = model[row_path][1]
            item = self.buffer[path_id]
            parent_id = os.path.dirname(path_id)
            print 3, 'on_sync_selected()', path_id
            if mode == 'single':
                self.queue_buffer.put_nowait([item.enqueue, {
                    'push_allow' : self.allow_push.get_active(),
                    'pull_allow' : self.allow_pull.get_active(), 
                    'queue_push' : self.queue_push,
                    'queue_pull' : self.queue_pull,
                    'queue_push_size' : self.queue_push_size,
                    'queue_pull_size' : self.queue_pull_size,
                    'recursive' : False
                    }])
            elif mode == 'recursive':
                self.queue_buffer.put_nowait([item.enqueue, {
                    'push_allow' : self.allow_push.get_active(),
                    'pull_allow' : self.allow_pull.get_active(), 
                    'queue_push' : self.queue_push,
                    'queue_pull' : self.queue_pull,
                    'queue_push_size' : self.queue_push_size,
                    'queue_pull_size' : self.queue_pull_size,
                    'recursive' : False
                    }])
                if len(item.children) > 0 and not item.deep_searched and not item.virtual:
                    if item.direction == 'pull':
                        continue
                    if item.is_stack:
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
            elif mode == 'children':
                if len(item.children) > 0:
                    if not item.virtual and not item.deep_searched:
                        paths = []
                        for child in item.children:
                            paths.append(child.path_id)
                        self.queue_buffer.put_nowait([self.buffer_list_files, {
                            'paths': paths,
                            'sync': True,
                            'maxdepth': False
                        }])
                    else:
                        for child in item.children:
                            self.queue_buffer.put_nowait([child.enqueue, {
                                'push_allow' : self.allow_push.get_active(),
                                'pull_allow' : self.allow_pull.get_active(), 
                                'queue_push' : self.queue_push,
                                'queue_pull' : self.queue_pull,
                                'queue_push_size' : self.queue_push_size,
                                'queue_pull_size' : self.queue_pull_size,
                                'recursive' : True
                            }])



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
            print 3, 'Loaded connection:', host
            #, alias='New host', address='', user='mistika', port=22, path='', selected=False
            if hosts[host]['selected']:
                self.entry_host.set_active_iter(row_iter)
                #selection.select_iter(row_iter)
                # self.on_host_selected(None)
        row_values = [
                default_connection['alias'],
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
        model = self.hostsTreeStore
        selected_row_iter = self.entry_host.get_active_iter()
        selected_row_path = model.get_path(selected_row_iter)
        self.selected_host_row_reference = gtk.TreeRowReference(model, selected_row_path)
        self.entry_address.set_text(model[selected_row_iter][1])
        self.entry_user.set_text(model[selected_row_iter][2])
        self.entry_port.set_value(model[selected_row_iter][3])
        self.entry_projects_path.set_text(model[selected_row_iter][4])
        self.entry_local_media_root.set_text(model[selected_row_iter][5])
        self.allow_push.set_active(model[selected_row_iter][6])
        self.allow_pull.set_active(model[selected_row_iter][7])
        print 1, 'Selected connection:', model[selected_row_iter][0]
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
            print 2, 'No folder selected'
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
        treestore = self.projectsTreeStore.get_model()
        try: # If there is a filter in the middle
            treestore = treestore.get_model()
        except AttributeError:
            pass
        file_infos = []
        if row_path == None:
            selection = treestore.get_selection()
            (treestore, pathlist) = selection.get_selected_rows()
        else:
            pathlist = [row_path]
        for row_path in pathlist:
            row_iter = treestore.get_iter(row_path)
            path_id = treestore[row_path][1]
            if action == 'pull':
                self.buffer[path_id].direction = 'pull'
            elif action == 'push':
                self.buffer[path_id].direction = 'push'
            elif action == 'nothing':
                self.buffer[path_id].direction = 'nothing'
            elif action == 'reset':
                self.buffer[path_id].direction_update()
            gobject.idle_add(self.buffer[path_id].gui_update)
            child_iter = treestore.iter_children(row_iter)
            while child_iter != None:
                row_path_child = treestore.get_path(child_iter)
                path_str_child = treestore[row_path_child][1]
                if not path_str_child == '': self.on_force_action(None, action, row_path_child) # Avoid placeholders
                child_iter = treestore.iter_next(child_iter)
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
        print 2, '\n'.join(file_infos)
        dialog = gtk.MessageDialog(parent=self.window, 
                            #flags=gtk.DIALOG_MODAL, 
                            type=gtk.MESSAGE_INFO, 
                            buttons=gtk.BUTTONS_NONE, 
                            message_format=None)
        dialog.set_markup('\n'.join(file_infos))
        dialog.run()
    def io_list_files_local(self, find_cmd, parent_path=False):
        gobject.idle_add(self.spinner_local.set_property, 'visible', True)
        gobject.idle_add(self.local_status_label.set_label, 'Listing local files')
        cmd = find_cmd.replace('<projects>', mistika.projects_folder).replace('<absolute>/', '/')
        if self.is_mac:
            cmd = self.aux_fix_mac_printf(cmd)
        print 3, cmd
        try:
            p1 = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, stderr = p1.communicate()
            if False and p1.returncode > 0:
                loader.set_from_stock(gtk.STOCK_APPLY, gtk.ICON_SIZE_BUTTON)
                gobject.idle_add(self.gui_show_error, stderr)
                return
            self.lines_local = output.splitlines()
        except:
            print 1, stderr
            raise
            gobject.idle_add(self.gui_show_error, stderr)
            return
        gobject.idle_add(self.spinner_local.set_property, 'visible', False)
        gobject.idle_add(self.local_status_label.set_label, '')
        #gobject.idle_add(loader.set_from_stock, gtk.STOCK_APPLY, gtk.ICON_SIZE_BUTTON)
    def io_list_files_remote(self, find_cmd):
        #gobject.idle_add(self.button_load_remote_projects.set_image, loader)
        gobject.idle_add(self.spinner_remote.set_visible, True)
        gobject.idle_add(self.remote_status_label.set_label, 'Listing remote files')
        cmd = find_cmd.replace('<projects>', self.connection['projects_path']).replace('<absolute>/', self.connection['root'])
        if self.connection['is_mac']:
            cmd = self.aux_fix_mac_printf(cmd)
        ssh_cmd = ['ssh', '-oBatchMode=yes', '-p', str(self.connection['port']), '%s@%s' % (self.connection['user'], self.connection['address']), cmd]
        print 3, ' '.join(ssh_cmd)
        try:
            p1 = subprocess.Popen(ssh_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, stderr = p1.communicate()
            if False and p1.returncode > 0:
                loader.set_from_stock(gtk.STOCK_APPLY, gtk.ICON_SIZE_BUTTON)
                gobject.idle_add(self.gui_show_error, stderr)
                return
            self.lines_remote = output.splitlines()
        except KeyError:
            print 1, stderr
            raise
            gobject.idle_add(self.gui_show_error, stderr)
            return
        gobject.idle_add(self.remote_status_label.set_label, '')
        gobject.idle_add(self.spinner_remote.set_visible, False)
        #self.project_cell.set_property('foreground', '#000000')
        #self.project_cell.set_property('style', 'normal')
        #gobject.idle_add(loader.set_from_stock, gtk.STOCK_APPLY, gtk.ICON_SIZE_BUTTON)
    def buffer_add(self, lines, host, root, parent=None):
        # lines : raw lines from find command's stdout
        # host  : either localhost or the connection alias for a remote host
        # root  : prefix to be removed from full path when determing path_id
        root = root.rstrip('/')
        if not root == '':
            root += '/'
        for file_line in lines:
            print 5, file_line
            attributes = {
                'real_parent' : parent,
                # 'virtual' : False,
                'color' : COLOR_DEFAULT,
                'placeholder': False,
            }
            try:
                f_inode, f_type, f_size, f_time, full_path = file_line.strip().split(' ', 4)
                full_path, f_link_dest = full_path.split('->')
            except ValueError:
                print 1, 'Error line:', file_line
                continue
            f_inode = int(f_inode)
            f_time = int(f_time.split('.')[0])
            f_type.replace('/', 'd').replace('@', 'l') # Converts mac to linux types
            if f_type == 'd':
                f_size = 0
            else:
                f_size = int(f_size)
            f_basename = full_path.strip('/').split('/')[-1]
            if full_path.startswith(root): # Relative path
                path_id = full_path.replace(root, '', 1).strip('/')
            else: # Absolute path
                path_id = full_path
                if self.mappings:
                    if host != 'localhost':
                        path_id = self.remap_to_local(path_id)
                path_id = path_id.rstrip('/')
            if parent != None and f_type != 'f':
                path_id = parent.path_id+'/'+path_id
            parent_path = os.path.dirname(path_id)
            if path_id == '': # Skip root item
                continue
            if parent_path in self.buffer:
                this_parent = self.buffer[parent_path]
                if f_inode == -1: # This is a virtual folder
                    attributes['alias'] = path_id.replace(parent_path+'/', '', 1) # Prepends the slash to first level, absolute path virtual folders
            elif parent == None:
                this_parent = None
            else:
                this_parent = self.buffer_get_parent(parent.path_id+'/'+path_id)
            if f_link_dest == '':
                f_link_dest = False
            if host == 'localhost':
                attributes['path_local'] = full_path
                attributes['inode_local'] = f_inode
                attributes['type_local'] = f_type
                attributes['size_local'] = f_size
                attributes['mtime_local'] = f_time
                attributes['link_local'] = f_link_dest
            else:
                attributes['path_remote'] = full_path
                attributes['inode_remote'] = f_inode
                attributes['type_remote'] = f_type
                attributes['size_remote'] = f_size
                attributes['mtime_remote'] = f_time
                attributes['link_remote'] = f_link_dest
            if not path_id in self.buffer:
                if path_id.endswith('Exports'):
                    print 4, 'new Item(%s)' % path_id
                item = self.buffer[path_id] = Item(path_id, this_parent, self.projectsTreeStore, self.projectsTree, attributes)
            else:
                item = self.buffer[path_id]
                if path_id.endswith('Exports'):
                    print 4, 'New attributes for:', path_id
                    print 4, repr(attributes)
                item.set_attributes(attributes)
                if this_parent != None and not this_parent in item.parents:
                    if path_id.endswith('Exports'):
                            print 4, 'New parent for:', path_id, this_parent.path_id
                    # print 'this_parent:', this_parent.path_id
                    item.add_parent(this_parent)
            if item.inode_local and item.inode_remote:
                self.inodes_local_to_remote[item.inode_local] = item.inode_remote
                self.inodes_remote_to_local[item.inode_remote] = item.inode_local
                self.queue_buffer.put_nowait([self.buffer_inodes_cache_dump])


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
            # real_parent_path = parent_path
            # while not (real_parent_path in self.buffer and not self.buffer[real_parent_path].virtual):
            #     real_parent_path = os.path.dirname(real_parent_path)
            parent = self.buffer_get_parent(path_id)
            if path_id.endswith('Exports'):
                print 4, 'New virtual file:', path_id, parent.path_id
            self.buffer[path_id] = Item(path_id, parent, self.projectsTreeStore, self.projectsTree, attributes)
            # real_path = path_id.replace(real_parent_path, '', 1)
            # self.queue_buffer.put_nowait([self.buffer_list_files, {
            #         'paths' : [real_path],
            #         'parent' : self.buffer[real_parent_path],
            #         'maxdepth' : 1,
            #         }])
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
                    print 3, 'Error:'
                    print 3, repr(e)
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
                    if item.virtual:
                        pass
                    elif item.absolute:
                        # print 'Push absolute path:', repr(item.path_id)
                        items_absolute.append(item)
                        queue_size_absolute += item.size_local
                    else:
                        # print 'Push relative path:', repr(item.path_id)
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
    def push_rename(self, item):
        pass
    def push_link(self, item):
        pass
    def push_dir(self, item):
        pass
    def push_file(self, item):
        pass
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
                    if item.type_remote == 'l':
                        self.pull_link(item)
                    elif item.type_remote == 'd':
                        self.pull_dir(item)
                    elif item.absolute:
                        print 4, 'pull absolute path:', repr(item.path_id)
                        items_absolute.append(item)
                        queue_size_absolute += item.size_local
                    else:
                        print 4, 'pull relative path:', repr(item.path_id)
                        items_relative.append(item)
                        queue_size_relative += item.size_local
            except Queue.Empty:
                do_now = True
            if queue_size_absolute > BATCH_SIZE or do_now:
                self.pull_file(items_absolute, absolute=True)
                items_absolute = []
                queue_size_absolute = 0
            if queue_size_relative > BATCH_SIZE or do_now:
                self.pull_file(items_relative)
                items_relative = []
                queue_size_relative = 0
    def pull_rename(self, item):
        pass
    def pull_link(self, item):
        real_path = item.path_id
        print 4, 'pull_link():', real_path
        if item.virtual and item.real_parent != None:
            print 4, 'real parent path:', item.real_parent.path_id
            if real_path.startswith(item.real_parent.path_id):
                real_path = real_path.replace(item.real_parent.path_id+'/', '', 1)
                print 4, 'updated link path:', real_path
        if not os.path.isabs(real_path):
            real_path = os.path.join(mistika.projects_folder, real_path)
            print 4, 'Absolute link path:', real_path
        if os.path.exists(real_path):
            item.transfer_fail('File exists: '+ real_path)
            self.queue_pull_size[0] -= item.size_remote
            return
        else:
            print 4, 'link target:', item.link_remote
            target = self.remap_to_local(item.link_remote)
            print 4, 'remapped link target:', target
            try:
                os.symlink(target, real_path)
                print 2, 'Created symlink:', '%s -> %s' % (real_path, target)
            except OSError as e:
                print 1, 'Could not create symlink: %s -> %s' % (real_path, target)
                item.transfer_fail('Could not create symlink: %s -> %s' % (real_path, target))
                self.queue_pull_size[0] -= item.size_remote
                print 2, e
                return
            link_target_abs = os.path.join(os.path.dirname(real_path), target)
            if not os.path.exists(link_target_abs):
                try:
                    os.makedirs(link_target_abs)
                    print 2, 'Created folder:', link_target_abs
                except OSError as e:
                    print 1, 'Could not create dir:', link_target_abs
                    item.transfer_fail('Could not create dir: '+ link_target_abs)
                    self.queue_pull_size[0] -= item.size_remote
                    print 2, e
                    return
        item.transfer_end()
        self.queue_pull_size[0] -= item.size_remote
    def pull_dir(self, item):
        real_path = item.path_id
        print 4, 'pull_dir():', real_path
        if item.virtual and item.real_parent != None:
            print 4, 'real parent path:', item.real_parent.path_id
            if real_path.startswith(item.real_parent.path_id):
                real_path = real_path.replace(item.real_parent.path_id+'/', '', 1)
                print 4, 'updated dir path:', real_path
        if not os.path.isabs(real_path):
            real_path = os.path.join(mistika.projects_folder, real_path)
            print 4, 'Absolute dir path:', real_path
        if os.path.exists(real_path):
            item.transfer_fail('File exists: '+ real_path)
            self.queue_pull_size[0] -= item.size_remote
            return
        else:
            try:
                os.makedirs(real_path)
                print 2, 'Created folder:', real_path
                item.transfer_end()
                self.queue_pull_size[0] -= item.size_remote
            except OSError as e:
                print 1, 'Could not create dir:', real_path
                item.transfer_fail('Could not create dir: '+ link_target_abs)
                self.queue_pull_size[0] -= item.size_remote
                print 2, e
    def pull_file(self, items, absolute=False):
        if len(items) == 0:
            return
        for item in items:
            item.transfer_start()
        relative_paths_local = {}
        relative_paths_remote = {}
        extra_args = []
        if absolute:
            base_path_local = self.connection['local_media_root']
            base_path_remote = self.connection['root']
            for item in items:
                relative_paths_local[self.remap_to_local(item.path_remote).strip('/')] = item
                relative_paths_remote[item.path_remote.strip('/')] = item
            # extra_args.append('-O')
        else:
            base_path_local = mistika.projects_folder+'/'
            base_path_remote = self.connection['projects_path']+'/'
            for item in items:
                relative_paths_local[item.path_id.strip('/')] = item
                relative_paths_remote[item.path_id.strip('/')] = item
        item = False
        temp_handle = tempfile.NamedTemporaryFile()
        temp_handle.write('\n'.join(relative_paths_remote) + '\n')
        temp_handle.flush()
        uri_remote = "%s@%s:%s/" % (self.connection['user'], self.connection['address'], base_path_remote)
        cmd = [
            'rsync',
            '-e',
            'ssh -p %i' % self.connection['port'],
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
        print 3, ' '.join(cmd)
        print 4, open(temp_handle.name).read()
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
            print 5, output.strip().ljust(100)
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
                    path_id = relative_paths_remote[rel_path]
                    item = self.buffer[path_id]
                    item.transfer_end()
                    self.queue_pull_size[0] -= item.size_remote
                except KeyError:
                    pass
                item = False
            # elif 'rsync: recv_generator: mkdir' in output and 'failed: Permission denied (13)' in output:
            #     folder = output.split('"', 2)[1]
            #     for rel_path in relative_paths_remote:
            #         path_id = relative_paths_remote[rel_path.rstrip('/')]
            #         if path_id.startswith(folder):
            #             self.buffer[path_id].transfer_fail('Permission denied')
            else:
                rel_path = output.strip()
                try:
                    item = self.buffer[relative_paths_remote[rel_path]]
                except KeyError:
                    pass
            proc.poll()
        temp_handle.close()
        if proc.returncode > 0:
            print 1, 'Error: %i' % proc.returncode
        for item in items:
            full_path_local = base_path_local+'/'+item.path_id
            if item.is_stack:
                if not item.path_id.startswith('/'):
                    project = item.path_id.split('/', 1)[0]
                    project_structure = []
                    for required_file in mistika.PROJECT_STRUCTURE:
                        project_structure.append(os.path.join(project, required_file))
                    for child in self.buffer[project].children:
                        project_structure.append(child.path_id)
                    for required_path in project_structure:
                        if required_path in self.buffer:
                            if self.buffer[required_path].size_local < 0:
                                self.queue_buffer.put_nowait([self.buffer[required_path].enqueue, {
                                    'push_allow' : self.allow_push.get_active(),
                                    'pull_allow' : self.allow_pull.get_active(), 
                                    'queue_push' : self.queue_push,
                                    'queue_pull' : self.queue_pull,
                                    'queue_push_size' : self.queue_push_size,
                                    'queue_pull_size' : self.queue_pull_size,
                                    'recursive' : False
                                }])
                        else:
                            try:
                                os.mkdir(os.path.join(mistika.projects_folder, required_path))
                            except OSError as e:
                                print 1, 'Could not mkdir: ', required_path, e
                self.queue_buffer.put_nowait([self.io_get_associated, {
                    'path_id': item.path_id,
                    'sync': False,
                    'remap': self.mappings_to_local
                }])
        self.queue_buffer.put_nowait([self.buffer_list_files, {
                    'paths' : [item.path_id for item in relative_paths_local.values()],
                    'sync' : False,
                    'maxdepth' : 0,
                    }])
    def push_old(self, items, absolute=False):
        if len(items) == 0:
            return
        relative_paths = {}
        extra_args = []
        # if False and len(items) == 1:
        #     for item in items:
        #         item.transfer_start()
        #         relative_paths[item.path_id.lstrip('/')] = item.path_id
        #         if absolute:
        #             local_path = item.path_id
        #             remote_path = item.path_id
        #             extra_args.append('-KO')
        #         else:
        #             local_path = os.path.join(mistika.projects_folder, item.path_id)
        #             remote_path = os.path.join(self.connection['projects_path'], item.path_id)
        #         uri_remote = "%s@%s:%s" % (self.connection['user'], self.connection['address'], self.connection['root']+remote_path)
        #         parent_path = os.path.dirname(item.path_id)
        #         if not parent_path in self.buffer or self.buffer[parent_path].size_remote < 0:
        #             mkdir = 'mkdir -p '
        #             if absolute:
        #                 mkdir += "'%s'" % self.connection['root']+os.path.dirname(remote_path)
        #             else:
        #                 mkdir += "'%s'" % os.path.dirname(remote_path)
        #             cmd = ['ssh', '-oBatchMode=yes', '-p', str(self.connection['port']), '%s@%s' % (self.connection['user'], self.connection['address']), mkdir]
        #             mkdir_return = subprocess.call(cmd)
        #         cmd = ['rsync', '-e', 'ssh -p %i' % self.connection['port'], '-ua'] + extra_args + ['--progress', self.connection['local_media_root']+local_path, uri_remote]
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
            relative_paths[item.path_id.lstrip('/')] = item.path_id
        item = False
        temp_handle = tempfile.NamedTemporaryFile()
        temp_handle.write('\n'.join(relative_paths) + '\n')
        temp_handle.flush()
        if absolute:
            base_path_local = self.connection['local_media_root']
            base_path_remote = self.connection['root']
            # extra_args.append('-O')
        else:
            base_path_local = mistika.projects_folder+'/'
            base_path_remote = self.connection['projects_path']+'/'
        uri_remote = "%s@%s:%s/" % (self.connection['user'], self.connection['address'], base_path_remote)
        cmd = [
            'rsync',
            '-e',
            'ssh -p %i' % self.connection['port'],
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
            print 1, 'Error: %i' % proc.returncode
        for item in items:
            if item.is_stack and self.mappings:
                list(hyperspeed.stack.Stack(item.path_id).iter_dependencies(progress_callback=file_object.set_remap_progress, remap=self.mappings))
        self.queue_buffer.put_nowait([self.buffer_list_files, {
                    'paths' : relative_paths.values(),
                    'sync' : False,
                    'maxdepth' : 0,
                    }])
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
                    print 1, 'Error:', repr(e)
            except Queue.Empty:
                time.sleep(1)
    def local_inodes_cache_write(self, inodes_local_to_remote_json):
        dir_path = os.path.dirname(self.connection['inodes_map_cache_path'])
        if not os.path.isdir(dir_path):
            try:
                os.makedirs(dir_path)
                print 2, 'Created directory for inode map cache: %s' % dir_path
            except OSError as e:
                print 1, 'Could not create inode map cache director: %s %s' % (dir_path, e)
        start_time = time.time()
        try:
            open(self.connection['inodes_map_cache_path'], 'w').write(inodes_local_to_remote_json)
            print 4, 'Wrote inode map cache to disk'
        except IOError as e:
            print 1, 'Could not write inode map cache to disk. Will not be able to detect renamed/moved files in the future.\n%s' % e
            return
        self.inodes_dump_time = time.time() - start_time
        print 4, 'Inode map cache write time: %s' % human.duration(self.inodes_dump_time)
        self.inodes_dump_frequency = max(self.inodes_dump_frequency, self.inodes_dump_time+10)
        print 4, 'Adjusted inodes_dump_frequency: %s' % self.inodes_dump_frequency
    def buffer_inodes_cache_dump(self):
        if time.time() - self.inodes_last_dump < self.inodes_dump_frequency:
            return
        # Send to local daemon so we don't have to wait for I/O
        print 4, 'Dumping inode map cache'
        self.queue_local.put_nowait([self.local_inodes_cache_write, {
            'inodes_local_to_remote_json': json.dumps(self.inodes_local_to_remote)
            }])
        self.inodes_last_dump = time.time()
    def buffer_inodes_cache_read(self):
        # This blocks intentionally
        print 1, 'Reading inode map cache'
        try:
            self.inodes_local_to_remote = json.loads(open(self.connection['inodes_map_cache_path']).read())
            self.inodes_remote_to_local = { y : x for x, y in self.inodes_local_to_remote.iteritems() }
            print 3, 'Loaded inode map cache'
        except IOError as e:
            if e.errno == 2:
                print 3, 'No cache found'
            else:
                print 1, e
    def remote_get_projects_path(self):
        cmd = ['ssh', '-oBatchMode=yes', '-p', str(self.connection['port']), '%s@%s' % (self.connection['user'], self.connection['address']), 'cat MISTIKA-ENV/MISTIKA_WORK MAMBA-ENV/MAMBA_WORK']
        p1 = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, stderr = p1.communicate()
        # print output
        if output != '':
            outline1 = output.splitlines()[0]
            outfields = outline1.split(None, 1)
            if outfields[0].endswith('_WORK') and len(outfields) == 2:
                return outfields[1]
        self.remote_status_label.set_markup('Could not get read MISTIKA-ENV/MISTIKA_WORK or MAMBA-ENV/MAMBA_WORK in home directory of user %s' % self.connection['user'])
        return None
    def remote_get_root_path(self):
        cmd = ['ssh', '-oBatchMode=yes', '-p', str(self.connection['port']), '%s@%s' % (self.connection['user'], self.connection['address']), 'cat msync-root.cfg']
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
        self.daemon_buffer_active = False
        self.daemon_local_active = False
        self.daemon_push_active = False
        self.daemon_pull_active = False
        self.abort = True
        gobject.idle_add(self.gui_disconnected)
    def remote_connect(self):
        #gobject.idle_add(self.button_connect.set_image, self.spinner)
        #selection = self.hostsTree.get_selection()
        #(model, iter) = selection.get_selected()
        #self.spinner_remote.set_property('visible', True)
        gobject.idle_add(self.gui_connection_panel_lock)
        alias = self.connection['alias'] = self.entry_host.get_active_text()
        gobject.idle_add(self.spinner_remote.set_visible, True)
        gobject.idle_add(self.remote_status_label.set_markup, 'Connecting')
        print 1, 'Connecting to %s' % self.connection['alias']
        address = self.connection['address'] = self.entry_address.get_text()
        user = self.connection['user'] = self.entry_user.get_text()
        port = self.connection['port'] = self.entry_port.get_value_as_int()
        self.connection['projects_path'] = self.entry_projects_path.get_text().rstrip('/')
        self.connection['local_media_root'] = self.entry_local_media_root.get_text().rstrip('/')+'/'
        self.connection['inodes_map_cache_path'] = os.path.join(CFG_DIR, 'inodes_cache_%s%s%s.map' % (address, user, port))
        #self.connection['projects_path'] = self.connection['projects_path'].rstrip('/')+'/'
        cmd = ['ssh', '-oBatchMode=yes', '-p', str(self.connection['port']), '%s@%s' % (self.connection['user'], self.connection['address']), 'uname']
        p1 = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, stderr = p1.communicate()
        if p1.returncode > 0:
            #gobject.idle_add(self.loader_remote.set_from_stock, gtk.STOCK_STOP, gtk.ICON_SIZE_BUTTON)
            gobject.idle_add(self.button_connect.set_image, self.icon_connect)
            if 'Permission denied' in stderr:
                print 1, 'Permission denied. Attempting to copy ssh key ...'
                gobject.idle_add(self.remote_status_label.set_markup, '')
                gobject.idle_add(self.gui_copy_ssh_key, self.connection['user'], self.connection['address'], self.connection['port'])
                gobject.idle_add(self.gui_connection_panel_lock, False)
                return
            else:
                print 1, 'Connection error'
                gobject.idle_add(self.gui_show_error, stderr)
                gobject.idle_add(self.remote_status_label.set_markup, 'Connection error.')
                gobject.idle_add(self.gui_connection_panel_lock, False)
                raise 'Connection error'
        else:
            print 1, 'Connected to %s' % self.connection['alias']
            if 'Darwin' in output:
                print 3, '%s is identified as a Mac' % self.connection['address']
                self.connection['is_mac'] = True
            else:
                self.connection['is_mac'] = False
        if self.connection['projects_path'] == '':
            print 2, 'Getting projects path ...'
            remote_projects_path = self.remote_get_projects_path()
            if remote_projects_path == None:
                print 1, 'Could not get remote projects path.'
                gobject.idle_add(self.gui_connection_panel_lock, False)
                return
            else:
                self.connection['projects_path'] = remote_projects_path
                print 1, 'Remote projects path: %s' % remote_projects_path
                self.entry_projects_path.set_text(remote_projects_path)
            #self.entry_address.set_property('editable', False)
        self.connection['root'] = self.remote_get_root_path()
        mappings = self.mappings = {
            'projects' : (mistika.projects_folder, self.connection['projects_path']),
            'media'    : (self.connection['local_media_root'], self.connection['root']),
        }
        self.mappings_to_local = {}
        for map_id, mapping in mappings.iteritems():
            if mapping[0] == mapping[1]:
                del mappings[map_id]
            else:
                print 2, 'Mapping local %s to remote %s' % (mapping[0], mapping[1])
                self.mappings_to_local[map_id] = (mapping[1], mapping[0])
        gobject.idle_add(self.gui_connected)
        self.queue_buffer.put_nowait([self.buffer_list_files])
        self.start_daemon(self.daemon_buffer)
        self.start_daemon(self.daemon_local)
        self.start_daemon(self.daemon_push)
        self.start_daemon(self.daemon_pull)
    def buffer_clear(self):
        self.buffer = {}
    def gui_connection_panel_lock(self, lock=True):
        state = not lock
        self.entry_host.set_sensitive(state)
        self.entry_address.set_sensitive(state)
        self.entry_user.set_sensitive(state)
        self.entry_port.set_sensitive(state)
        self.entry_projects_path.set_sensitive(state)
        self.entry_local_media_root.set_sensitive(state)
        self.entry_local_media_root_button.set_sensitive(state)
    def gui_connected(self):
        self.remote_status_label.set_markup('')
        self.button_connect.set_visible(False)
        self.button_disconnect.set_visible(True)
        self.files_panel.set_visible(True)
    def gui_disconnected(self):
        self.gui_connection_panel_lock(False)
        self.button_disconnect.set_property('visible', False)
        self.button_connect.set_property('visible', True)
        self.files_panel.set_property('visible', False)
        self.spinner_remote.set_property('visible', False)
        self.projectsTreeStore.clear()
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
        mappings = self.mappings
        for map_id in ['projects', 'media']:
            mapping = mappings[map_id]
            if path.startswith(mapping[0]):
                # print 'Remap:', path,
                path = path.replace(mapping[0], mapping[1], 1)
                # print '>', path
                break
        return path
    def remap_to_local(self, path):
        mappings = self.mappings_to_local
        for map_id in ['projects', 'media']:
            mapping = mappings[map_id]
            if path.startswith(mapping[0]):
                # print 'Remap:', path,
                path = path.replace(mapping[0], mapping[1], 1)
                # print '>', path
                break
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
                self.buffer[pre_alloc_path] = Item(pre_alloc_path, self.buffer_get_parent(parent.path_id+'/'+pre_alloc_path), self.projectsTreeStore, self.projectsTree, attributes)
                # gobject.idle_add(self.gui_expand, parent)
        if search_paths_local == '':
            print 3, 'buffer_list_files(): no search paths'
            return
        if type(maxdepth) == int:
            maxdepth_str = ' -maxdepth %i' % maxdepth
        find_cmd_local  = 'find %s -name PRIVATE -prune -o %s %s -printf "%%i %%y %%s %%T@ %%p->%%l\\\\n"' % (search_paths_local , maxdepth_str, type_filter)
        find_cmd_remote = 'find %s -name PRIVATE -prune -o %s %s -printf "%%i %%y %%s %%T@ %%p->%%l\\\\n"' % (search_paths_remote, maxdepth_str, type_filter)
        # print find_cmd_local
        # print find_cmd_remote
        self.lines_local = []
        self.lines_remote = []
        thread_local = self.launch_thread(target=self.io_list_files_local, args=[find_cmd_local])
        thread_remote = self.launch_thread(target=self.io_list_files_remote, args=[find_cmd_remote])

        # Use the wait to load inodes cache
        if len(self.inodes_local_to_remote) == 0:
            self.buffer_inodes_cache_read()

        # Waiting here to limit the time between showing local and remote files
        thread_local.join()
        thread_remote.join()
        self.buffer_add(
            lines = self.lines_local,
            host = 'localhost',
            root = mistika.projects_folder,
            parent = parent
        )
        self.buffer_add(
            lines = self.lines_remote,
            host = self.connection['alias'],
            root = self.connection['projects_path'],
            parent = parent
        )
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
                    push_allow = self.allow_push.get_active(),
                    pull_allow = self.allow_pull.get_active(), 
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
            print 2, status
            #gobject.idle_add(self.status_bar.push, self.context_id, status)
        except IOError as e:
            msg = 'Could not write to file:\n'+CFG_HOSTS_PATH
            print 1, msg
            gobject.idle_add(self.gui_show_error,msg)
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
        return True # Must return true to keep repeating
    def write(self, string):
        # sys.__stdout__.write(repr(string)+'\n')
        # sys.__stdout__.flush()
        if len(string) == 1 and string.isdigit() and self.prev_stdout_string == '\n':
            self.line_log_level = int(string)
            self.prev_stdout_string = None
            return
        elif self.prev_stdout_string == None and string == ' ':
            self.prev_stdout_string = ' '
            return
        elif string.endswith('\n'):
            if self.line_log_level > self.log_level:
                self.line_log_level = 0
                return
            else:
                self.line_log_level = 0
        elif self.line_log_level > self.log_level:
            # sys.__stdout__.write('line_log_level %i > log_level %i\n' % (self.line_log_level, self.log_level))
            # sys.__stdout__.flush()
            self.prev_stdout_string = '\n'
            return
        sys.__stdout__.write(string)
        sys.__stdout__.flush()
        self.prev_stdout_string = string
        markup = '%s'
        tag = False
        if self.line_log_level <= 1:
            tag = self.tags['lvl1']
        elif self.line_log_level == 2:
            tag = self.tags['lvl2']
        elif self.line_log_level == 3:
            tag = self.tags['lvl3']
        elif self.line_log_level == 4:
            tag = self.tags['lvl4']
        elif self.line_log_level == 5:
            tag = self.tags['lvl5']
        gobject.idle_add(self.gui_log_append, markup % string, tag)
    def flush(self, **args):
        pass
    def gui_log_append(self, string, tag):
        if tag:
            self.console_buffer.insert_with_tags(self.console_buffer.get_end_iter(), string, tag)
        else:
            self.console_buffer.insert(self.console_buffer.get_end_iter(), string)

class Item(object):
    def __init__(self, path, parent, treestore, treeview, attributes=False):
        self._parents = []
        self._icon = False
        self.row_references = []
        self.path_id = path
        self.path_id_local = False
        self.path_id_remote = False
        self.inode_local = False
        self.inode_remote = False
        self.absolute = path.startswith('/')
        self.alias = os.path.basename(self.path_id)
        if self.alias == '':
            self.alias = '/'
        self.is_stack = self.path_id.rsplit('.', 1)[-1] in hyperspeed.stack.EXTENSIONS
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
        self.real_parent = None
        if attributes:
            for key, value in attributes.iteritems():
                key_private = '_'+key
                if hasattr(self, key_private):
                    setattr(self, key_private, value)
                else:
                    setattr(self, key, value)
        self.on_top_level = False
        self.direction_update()
        self.add_parent(parent) # Adds to view
    def __getitem__(self, key):
        return getattr(self, key)
    def set_attributes(self, attributes):
        for key, value in attributes.iteritems():
            if self.path_id.endswith('Exports'):
                print '%s setattr(%s, %s)' % (self.path_id, key, value)
            setattr(self, key, value)
        if self.path_id.endswith('Exports'):
            print 'type_remote:', self.type_remote
        self.direction_update()
        self._icon = False
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
        if not self.placeholder_child:
            self.add_fetcher()
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
        size_local_str = '' if self.type_local == 'd' else human.size(self.size_local)
        size_remote_str = '' if self.type_remote == 'd' else human.size(self.size_remote)
        return [
            self.alias, # 0
            self.path_id, # 1
            human.time(self.mtime_local), # 2
            self.direction_icon, # 3
            human.time(self.mtime_remote), # 4
            int(self.progress_percent), # 5
            self.progress_string, # 6
            self.progress_visibility, # 7
            '', # 8
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
        if self.size_local >= 0 > self.size_remote:
            self.direction = 'push'
        elif self.size_local < 0 <= self.size_remote:
            self.direction = 'pull'
        elif self.type_local in ['d', 'l'] and self.type_remote in ['d', 'l']:
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
            elif 'l' in [self.type_local, self.type_remote]:
                self._icon = ICON_LINK
            elif 'd' in [self.type_local, self.type_remote]:
                self._icon = ICON_FOLDER
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
            # print self.path_id, 'add_parent()', parent.path_id
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
    def path_id(self):
        return self._path_id
    @path_id.setter
    def path_id(self, value):
        self._path_id = value
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
            self.add_fetcher()
    def add_fetcher(self):
        dependency_fetcher_path = '%s dependency fetcher' % self.path_id
        attributes = {
            'alias': ' <i>Getting dependencies ...</i>',
            'icon' : PIXBUF_SEARCH,
            'placeholder' : True,
            'progress_visibility' : True
        }
        self.placeholder_child = Item(dependency_fetcher_path, self, self.treestore, self.treeview, attributes)
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
    def enqueue(self, push_allow, pull_allow, queue_push, queue_pull, queue_push_size, queue_pull_size, recursive=True, parents=True):
        print 3, 'Enqueing:', self.path_id
        if recursive and len(self.children) > 0:
            for child in self.children:
                child.enqueue(push_allow, pull_allow, queue_push, queue_pull, queue_push_size, queue_pull_size, parents=False)
        # We do parents first to allow creation of missing folders/links
        if parents and len(self.parents) > 0:
            for parent in self.parents:
                if not 'f' in [parent.type_local, parent.type_remote]:
                    parent.enqueue(push_allow, pull_allow, queue_push, queue_pull, queue_push_size, queue_pull_size, recursive=False)
        if not self.transfer:
            # print 'Enqueing:', self.path_id
            bytes_total_before = self.bytes_total
            if self.placeholder:
                return
            if self.direction == 'push':
                if not push_allow:
                    print 3, 'Push is disabled, skipping', self.path_id
                    return
                self.bytes_total = self.size_local
                queue_push_size[0] += self.size_local
                print 4, 'Put in queue_push:', self.path_id
                queue_push.put(self)
                self.progress_string = 'Queued'
                self.progress_visibility = True
                self.status_visibility = False
            elif self.direction == 'pull':
                if not pull_allow:
                    print 3, 'Pull is disabled, skipping', self.path_id
                    return
                self.bytes_total = self.size_remote
                queue_pull_size[0] += self.size_remote
                print 4, 'Put in queue_pull:', self.path_id
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
            print 'Already in transfer queue:', self.path_id
    def gui_remove(self):
        for row_reference in self.row_references:
            row_path = row_reference.get_path()
            try:
                del self.treestore[row_path]
            except TypeError:
                pass

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

os.environ['LC_CTYPE'] = 'en_US.utf8'
os.environ['LC_ALL'] = 'en_US.utf8'

gobject.threads_init()
t = MainThread()
t.start()
sys.stdout = t
gtk.main()
t.quit = True
