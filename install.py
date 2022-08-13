#!/usr/bin/env python2

import os
import site
import sys
import subprocess

try:
    import gtk
except ImportError:
    gtk = False

os_symlink = getattr(os, "symlink", None)
if callable(os_symlink):
    pass
else:
    print "Patching windows symlink support"
    def symlink_ms(source, link_name):
        import ctypes
        import ctypes.wintypes as wintypes
        if os.path.exists(link_name):
            df = ctypes.windll.kernel32.DeleteFileW
            if df(link_name) == 0:
                print "Could not remove existing file:", link_name
                print "You should remove the file manually through Explorer or an elevated cmd process."
                raise ctypes.WinError()
        csl = ctypes.windll.kernel32.CreateSymbolicLinkW
        csl.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32)
        csl.restype = ctypes.c_ubyte
        flags = 1 if os.path.isdir(source) else 0
        flags += 2 # For unprivileged mode. Requires Developer Mode to be activated.
        if csl(link_name, source, flags) == 0:
            raise ctypes.WinError()
    os.symlink = symlink_ms

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

import hyperspeed
open(hyperspeed.folderConfigFile, 'w').write(os.path.dirname(os.path.realpath(__file__)))

import hyperspeed.tools

hyperspeed_dashboard_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'Tools/Hyperspeed-dashboard/hyperspeed-dashboard.py')
desktop_link = confirm('Hyperspeed Dashboard on desktop? ')
hyperspeed.tools.desktop_link(
        alias='Hyperspeed Dashboard',
        activated=desktop_link,
        file_path=hyperspeed_dashboard_path
    )
if hyperspeed.mistika.product == 'Mistika':
    mistika_link = confirm("Hyperspeed Dashboard in Mistika Extras panel? ")
    hyperspeed.tools.mistika_link(
            alias='Hyperspeed Dashboard',
            activated=mistika_link,
            file_path=hyperspeed_dashboard_path
        )

subprocess.Popen([hyperspeed_dashboard_path], shell=True)
