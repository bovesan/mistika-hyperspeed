#!/usr/bin/env python
#-*- coding:utf-8 -*-

import threading
import time
import gobject
import gtk
import platform
import subprocess


gobject.threads_init()

class MyThread(threading.Thread):
    def __init__(self):
        super(MyThread, self).__init__()
        self.threads = []
        self.window = gtk.Window()
        window = self.window
        screen = self.window.get_screen()
        window.set_title("Mistika remote sync")
        window.set_size_request(screen.get_height()-200, screen.get_height()-200)
        window.set_border_width(20)
        window.set_position(gtk.WIN_POS_CENTER)
        if 'darwin' in platform.system().lower():
            self.window.set_resizable(False) # Because resizing crashes the app on Mac

        vbox = gtk.VBox(False, 10)

        self.status_bar = gtk.Statusbar()     
        vbox.pack_end(self.status_bar, False, False, 0)
        self.status_bar.show()
        self.context_id = self.status_bar.get_context_id("Statusbar example")

        self.label1 = gtk.Label()
        vbox.pack_start(self.label1, False, False, 10)

        self.label2 = gtk.Label("Label 2")
        vbox.pack_start(self.label2, False, False, 10)

        button = gtk.Button("Click me")
        button.connect("clicked", self.button_click)
        vbox.pack_start(button, False, False, 10)

        window.add(vbox)
        window.show_all()
        window.connect("destroy", self.on_quit)
        self.quit = False

    def on_quit(self, widget):
        print 'Closed by: ' + repr(widget)
        for thread in self.threads:
            pass
        gtk.main_quit()

    def update_label(self, counter, label):
        label.set_text(counter)
        return False

    def run(self):
        counter = 0
        while not self.quit:
            counter += 1
            counter_str = "Counter: %i" % counter
            gobject.idle_add(self.update_label, counter_str, self.label1)
            time.sleep(0.1)

    def worker(self, *task):
        task[0](task[1:])

    def ping(self, widget):
        self.p1 = subprocess.Popen(['ping', 'vg.no'], stdout=subprocess.PIPE)
        while self.p1.returncode == None:
            line = self.p1.stdout.readline()
            self.p1.poll()
            print line
            gobject.idle_add(self.update_label, line, self.label2)

    def button_click(self, widget):
        t = threading.Thread(target=self.ping, args=[widget])
        self.threads.append(t)
        t.setDaemon(True)
        t.start()

t = MyThread()
t.start()
gtk.main()
t.quit = True