#!/usr/bin/env python

import os
import site
import sys
import subprocess

try:
    import gtk
except ImportError:
    gtk = False

def msg(message, error=False):
    try:
        if error:
            message_type = gtk.MESSAGE_ERROR
        else:
            message_type = gtk.MESSAGE_INFO
        dialog = gtk.MessageDialog(
            parent=None,
            flags=0,
            type=message_type,
            buttons=gtk.BUTTONS_CLOSE,
            message_format=message
        )
        dialog.set_position(gtk.WIN_POS_CENTER)
        response = dialog.run()
        dialog.grab_focus()
        dialog.destroy()
    except:
        print message
def confirm(question):
    try:
        dialog = gtk.MessageDialog(
            parent=None,
            flags=0,
            type=gtk.MESSAGE_QUESTION,
            buttons=gtk.BUTTONS_YES_NO,
            message_format=question
        )
        dialog.set_position(gtk.WIN_POS_CENTER)
        response = dialog.run()
        dialog.grab_focus()
        dialog.destroy()
        if response == -8:
            return True
        else:
            return False
    except:
        answer = raw_input(question + ' [y/n?]')
        if answer.lower().startswith('y'):
            return True
        else:
            return False

install = True
hyperspeed_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'hyperspeed')
link_path = os.path.join(site.USER_SITE, 'hyperspeed')
if os.path.realpath(link_path) == os.path.realpath(hyperspeed_path):
    install = False
    # msg('Hyperspeed is already installed')
elif os.path.islink(link_path):
    if os.path.exists(link_path):
        if not confirm('Hyperspeed is already poiting to %s\nPoint to %s?' % (
            os.path.realpath(link_path), hyperspeed_path)):
            sys.exit(0)
    print 'Removing old link to %s' % os.path.realpath(link_path)
    try:
        os.remove(link_path)
    except OSError as e:
        msg('Could not remove old link: %s\n%s' % (link_path, e))
        sys.exit(1)
if install:
    if not os.path.isdir(site.USER_SITE):
        try:
            os.makedirs(site.USER_SITE)
        except OSError as e:
            msg('Could not create python modules basedir: %s\n%s' % (site.USER_SITE, e))
            sys.exit(2)
    try:
        os.symlink(hyperspeed_path, link_path)
    except OSError as e:
        msg('Could not install hyperspeed in %s\n%s' % (link_path, e))
        sys.exit(3)
    if gtk:
        msg('Hyperspeed module was installed successfully')
    else:
        msg('Hyperspeed module was installed successfully, but gtk is missing.\n\
            Graphical user interfaces will not be available.')

import hyperspeed.tools

hyperspeed_dashboard_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'Tools/Hyperspeed-dashboard/hyperspeed-dashboard.py')
desktop_link = confirm('Hyperspeed Dashboard on desktop? ')
hyperspeed.tools.desktop_link(
        alias='Hyperspeed Dashboard',
        activated=desktop_link,
        file_path=hyperspeed_dashboard_path
    )
mistika_link = confirm("Hyperspeed Dashboard in Mistika Extras panel? ")
hyperspeed.tools.mistika_link(
        alias='Hyperspeed Dashboard',
        activated=mistika_link,
        file_path=hyperspeed_dashboard_path
    )

subprocess.call([hyperspeed_dashboard_path])
