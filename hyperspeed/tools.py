#!/usr/bin/env python

import os
import platform
import hyperspeed.utils
import shutil
from distutils.spawn import find_executable

import hyperspeed
import hyperspeed.utils
from hyperspeed import mistika

desktop_template = '''[Desktop Entry]
Categories=Multimedia;Mistika;
Exec=%s %%f
Icon=%s
MimeType=
Name=%s
Path=%s
StartupNotify=true
Terminal=%s
TerminalOptions=
Type=Application
Version=1.0
X-DBUS-ServiceName=
X-DBUS-StartupType=
X-KDE-SubstituteUID=false
X-KDE-Username=
'''

def get_desktop_links():
    tools = []
    desktop_folder_path = os.path.expanduser('~/Desktop/')
    for basename in os.listdir(desktop_folder_path):
        abs_path = os.path.join(desktop_folder_path, basename)
        if platform.system() == 'Darwin':
            darwin_executable_path = os.path.join(abs_path, 'Contents/MacOS', os.path.splitext(basename)[0])
            if os.path.isfile(darwin_executable_path):
                tools.append(os.path.realpath(darwin_executable_path))
        elif basename.endswith('.desktop'):
            for line in open(abs_path):
                if line.lower().startswith('exec='):
                    executable = line.split('=', 1)[1].split('%')[0].strip()
                    tools.append(os.path.realpath(executable))
        else:
            tools.append(os.path.realpath(abs_path))
    return tools
def get_mistika_links():
    tools = []
    if not os.path.isfile(mistika.tools_path):
        return tools
    for line in open(mistika.tools_path):
        line_alias, line_path = line.strip().split()[:2]
        line_path = os.path.realpath(os.path.normpath(line_path))
        tools.append(line_path)
    return tools

def desktop_link(alias, file_path, activated=True, icon_path=False):
    file_path = os.path.normpath(file_path)
    file_folder = os.path.dirname(file_path)
    if not icon_path:
        if 'icon.png' in os.listdir(file_folder):
            icon_path = os.path.join(file_folder, 'icon.png')
        else:
            icon_path = 'res/img/hyperspeed_1024px.png'
    icon_path = os.path.abspath(icon_path)
    stored = False
    desktop_folder_path = os.path.expanduser('~/Desktop/')
    for basename in os.listdir(desktop_folder_path):
        abs_path = os.path.join(desktop_folder_path, basename)
        real_path = os.path.normpath(os.path.realpath(abs_path))
        if platform.system() == 'Darwin':
            darwin_executable_path = os.path.join(abs_path, 'Contents/MacOS', os.path.splitext(basename)[0])
            if os.path.isfile(darwin_executable_path) and os.path.realpath(darwin_executable_path) == file_path:
                if activated:
                    stored = True
                    break
                else:
                    print 'Removing app:', abs_path
                    try:
                        shutil.rmtree(abs_path)
                    except shutil.Error as e:
                        print 'Could not remove app:', e
        else: # Linux
            if os.path.islink(abs_path) and real_path == os.path.realpath(file_path):
                if activated:
                    stored = True
                    break
                else:
                    print 'Removing link:', abs_path
                    os.remove(abs_path)
            elif basename.endswith('.desktop'):
                for line in open(abs_path):
                    if line.lower().startswith('exec='):
                        executable = line.split('=', 1)[1].split('%')[0].strip()
                        if os.path.realpath(executable) == os.path.realpath(file_path):
                            if activated:
                                stored = True
                                break
                            else:
                                print 'Removing desktop entry:', abs_path
                                os.remove(abs_path)
    if activated and not stored:
        desktop_file_path = os.path.join(desktop_folder_path, alias)
        if platform.system() == 'Darwin':
            print 'Creating desktop entry:', desktop_file_path
            hyperspeed.utils.mac_app_link(
                file_path,
                desktop_file_path,
                icon_path=icon_path
            )
        else:
            desktop_file_path += '.desktop'
            print 'Creating desktop entry:', desktop_file_path
            terminal = False
            desktop_file = desktop_template % (file_path, icon_path, alias, os.path.dirname(file_path), terminal)
            try:
                open(desktop_file_path, 'w').write(desktop_file)
            except IOError as e:
                print e
                return False
    return True
def mistika_link(alias, file_path, activated=True):
    if not os.path.exists(mistika.tools_path):
        return False
    file_path = os.path.normpath(file_path)
    new_config = ''
    stored = False
    for line in open(mistika.tools_path):
        if len(line.strip().split()) < 2:
            continue
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
    return True

