#!/usr/bin/env python
#-*- coding:utf-8 -*-

import threading
import time
import gobject
import gtk
import platform

gobject.threads_init()

class MyThread(threading.Thread):
    def __init__(self):
        super(MyThread, self).__init__()
        self.window = gtk.Window()
        window = self.window
        screen = self.window.get_screen()
        window.set_title("Mistika remote sync")
        window.set_size_request(screen.get_height()-200, screen.get_height()-200)
        window.set_border_width(20)
        window.set_position(gtk.WIN_POS_CENTER)
        if 'darwin' in platform.system().lower():
            self.set_resizable(False) # Because resizing crashes the app on Mac


        self.label = gtk.Label()
        window.add(self.label)
        window.show_all()
        window.connect("destroy", lambda _: gtk.main_quit())
        self.quit = False

    def update_label(self, counter):
        self.label.set_text("Counter: %i" % counter)
        return False

    def run(self):
        counter = 0
        while not self.quit:
            counter += 1
            gobject.idle_add(self.update_label, counter)
            time.sleep(0.1)


t = MyThread()
t.start()
gtk.main()
t.quit = True