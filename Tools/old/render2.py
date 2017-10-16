#!/usr/bin/python

# ZetCode PyGTK tutorial 
#
# This code example draws a circle
# using the cairo library
#
# author: jan bodnar
# website: zetcode.com 
# last edited: February 2009


import gtk
import math

def rounded_rectangle(cr, x, y, w, h, r=20):
    # This is just one of the samples from 
    # http://www.cairographics.org/cookbook/roundedrectangles/
    #   A****BQ
    #  H      C
    #  *      *
    #  G      D
    #   F****E

    cr.move_to(x+r,y)                      # Move to A
    cr.line_to(x+w-r,y)                    # Straight line to B
    cr.curve_to(x+w,y,x+w,y,x+w,y+r)       # Curve to C, Control points are both at Q
    cr.line_to(x+w,y+h-r)                  # Move to D
    cr.curve_to(x+w,y+h,x+w,y+h,x+w-r,y+h) # Curve to E
    cr.line_to(x+r,y+h)                    # Line to F
    cr.curve_to(x,y+h,x,y+h,x,y+h-r)       # Curve to G
    cr.line_to(x,y+r)                      # Line to H
    cr.curve_to(x,y,x,y,x+r,y)             # Curve to A

class PyApp(gtk.Window):

    def __init__(self):
        super(PyApp, self).__init__()

        self.set_title("Simple drawing")
        self.resize(800, 800)
        self.set_position(gtk.WIN_POS_CENTER)

        self.connect("destroy", gtk.main_quit)

        darea = gtk.DrawingArea()
        darea.set_size_request(400, 400)
        darea.connect("expose-event", self.expose)
        self.add(darea)

        self.show_all()
    
    def expose(self, widget, event):

        cr = widget.window.cairo_create()

        cr.set_line_width(9)
        cr.set_source_rgb(0.7, 0.2, 0.0)
                
        w = self.allocation.width
        h = self.allocation.height

        rounded_rectangle(cr, 200, 200, 400, 400)
        #cr.translate(w/2, h/2)
        #cr.arc(0, 0, 50, 0, 2*math.pi)
        #cr.stroke_preserve()
        
        cr.set_source_rgb(0.3, 0.4, 0.6)
        cr.fill()


PyApp()
gtk.main()