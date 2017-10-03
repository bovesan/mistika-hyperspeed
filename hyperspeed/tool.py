#!/usr/bin/env python

import os
import platform
import hyperspeed.utils
import shutil
from distutils.spawn import find_executable

from hyperspeed import mistika

def desktop_link(alias, file_path, activated=True):
    file_path = os.path.normpath(file_path)
    stored = False
    desktop_folder_path = os.path.expanduser('~/Desktop/')
    for basename in os.listdir(desktop_folder_path):
        abs_path = os.path.join(desktop_folder_path, basename)
        real_path = os.path.normpath(os.path.realpath(abs_path))
        if platform.system() == 'Darwin':
            darwin_executable_path = os.path.join(abs_path, 'Contents/MacOS', os.path.splitext(basename)[0])
            if os.path.isfile(darwin_executable_path) and os.path.normpath(os.path.realpath(darwin_executable_path)) == file_path:
                if activated:
                    stored = True
                    break
                else:
                    print 'Removing app:', abs_path
                    try:
                        shutil.rmtree(abs_path)
                    except shutil.Error as e:
                        print 'Could not remove app:', e
        else:
            if os.path.islink(abs_path) and real_path == os.path.realpath(file_path):
                if activated:
                    stored = True
                    break
                else:
                    print 'Removing link:', abs_path
                    os.remove(abs_path)
    if activated and not stored:
        abs_path = os.path.join(desktop_folder_path, alias)
        print 'Creating link:', abs_path
        if platform.system() == 'Darwin':
            hyperspeed.utils.mac_app_link(file_path, abs_path,
                icon_path=os.path.abspath("res/img/hyperspeed_1024px.png"))
        else:
            try:
                os.symlink(file_path, abs_path)
            except OSError as e:
                print e

def mistika_link(alias, file_path, activated=True):
    file_path = os.path.normpath(file_path)
    new_config = ''
    stored = False
    for line in open(mistika.tools_path):
        line_alias, line_path = line.strip().split()[:2]
        line_path = os.path.normpath(line_path)
        if os.path.realpath(file_path) == os.path.realpath(line_path):
            if activated:
                new_config += '%s %s %%a\n' % (alias, file_path)
                stored = True
            else:
                continue
        else:
            line_path = find_executable(line_path)
            if line_path == None or not os.path.exists(line_path):
                continue
        new_config += line
    if activated and not stored:
        new_config += '%s %s %%a\n' % (alias, file_path)
    print '\nNew config:'
    print new_config
    open(mistika.tools_path, 'w').write(new_config)