#!/usr/bin/env python	

import gtk

class DragImage(gtk.Image):
    def __init__(self,image,layout):
        gtk.Image.__init__(self)
        self.drag = False
        self.drag_x = 0
        self.drag_y = 0
        self.layout = layout
        self.x = 0
        self.y = 0
        self.set_from_file(image)
        self.event_box = gtk.EventBox()
        self.event_box.set_visible_window(False)
        self.event_box.add(self)
        self.event_box.add_events(gtk.gdk.POINTER_MOTION_MASK | gtk.gdk.BUTTON_PRESS_MASK | gtk.gdk.BUTTON_RELEASE_MASK)
        self.event_box.connect("button-press-event", self.click)
        self.event_box.connect("button-release-event", self.release)
        self.event_box.connect("motion-notify-event", self.mousemove)
        self.layout.put( self.event_box, 0, 0 )

    def click(self, widget, event):
        self.drag =  True
        self.drag_x =  event.x
        self.drag_y =  event.y
        print(self.drag_x, self.drag_y)

    def release(self, widget, event):
        self.drag =  False

    def mousemove(self,widget,event):
        if self.drag:
            self.layout.move(self.event_box,self.x+int(event.x-self.drag_x),self.y+int(event.y-self.drag_y))
            self.x, self.y = self.layout.child_get(self.event_box,'x','y')

class DragBox(gtk.HBox):
    def __init__(self,label_text,layout):
        gtk.HBox.__init__(self)
        #self.modify_bg(gtk.STATE_PRELIGHT, gtk.gdk.Color("#0c0"))
        self.drag = False
        self.drag_x = 0
        self.drag_y = 0
        self.layout = layout
        self.x = 0
        self.y = 0
        #self.set_from_file(image)
        label = gtk.Label()
        label.set_markup('<span size="40000">%s</span>' % 'Read .rnd')
        vbox = gtk.VBox(False, 10)
        vbox.pack_start(label)
        vbox.pack_start(gtk.Button('...'))
        combo = gtk.combo_box_entry_new_text()
        combo.append_text('Strings')
        vbox.pack_start(combo)
        self.pack_start(vbox)
        vbox = gtk.VBox(False, 5)
        output = gtk.HBox(False, 5)
        output.pack_start(gtk.image_new_from_stock(gtk.STOCK_REMOVE, gtk.ICON_SIZE_SMALL_TOOLBAR))
        label = gtk.Label()
        label.set_markup('<span size="20000">File path, picture</span>')
        output.pack_start(label)
        output.pack_start(gtk.image_new_from_stock(gtk.STOCK_GO_FORWARD, gtk.ICON_SIZE_SMALL_TOOLBAR))
        vbox.pack_start(output)
        self.pack_end(vbox)
        self.event_box = gtk.EventBox()
        self.event_box.set_visible_window(False)
        self.event_box.add(self)
        self.event_box.modify_bg(gtk.STATE_NORMAL, gtk.gdk.Color('#6e6'))
        self.event_box.add_events(gtk.gdk.POINTER_MOTION_MASK | gtk.gdk.BUTTON_PRESS_MASK | gtk.gdk.BUTTON_RELEASE_MASK)
        self.event_box.connect("button-press-event", self.click)
        self.event_box.connect("button-release-event", self.release)
        self.event_box.connect("motion-notify-event", self.mousemove)
        self.layout.put( self.event_box, 0, 0 )

    def click(self, widget, event):
        self.drag =  True
        self.drag_x =  event.x
        self.drag_y =  event.y
        print(self.drag_x, self.drag_y)

    def release(self, widget, event):
        self.drag =  False

    def mousemove(self,widget,event):
        if self.drag:
            self.layout.move(self.event_box,self.x+int(event.x-self.drag_x),self.y+int(event.y-self.drag_y))
            self.x, self.y = self.layout.child_get(self.event_box,'x','y')

class move_test(object):
    def __init__(self):
        window =  gtk.Window()
        layout =  gtk.Layout()
        img1 = DragImage('../res/img/spinner01.gif',layout)
        img2 = DragImage('../res/img/search.png',layout)
        box1 = DragBox('Hello',layout)
        window.add(layout)
        window.show_all()
        window.connect("destroy", gtk.main_quit)
        window.set_title("Hyperspeed render")
        window.maximize()
        #screen = window.get_screen()
        #window.set_size_request(800, screen.get_height()-200)

move_test()
gtk.main()