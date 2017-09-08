#!/usr/bin/env python

import platform
import subprocess
import os

def reveal_file(path):
    if isinstance(path, basestring): # Single path
        paths = [path]
    else: # Multiple paths
        paths = path
    folders = {}
    for path in paths:
        folder = os.path.dirname(path)
        folders[folder] = path
    for folder, path in folders.iteritems():
        print 'Reveal: ', folder
        if platform.system() == "Windows":
            subprocess.Popen(["explorer", "/select,", path])
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", '-R', path])
        else:
            try:
                os.setsid()
            except OSError:
                pass
            dolphinEnv = os.environ.copy()
            try:
                del dolphinEnv["LD_LIBRARY_PATH"]
            except KeyError:
                pass
            try:
                if os.path.isdir(path):
                    subprocess.Popen(["dolphin", path], env=dolphinEnv)
                else:
                    subprocess.Popen(["dolphin", '--select', path], env=dolphinEnv)
            except OSError:
                subprocess.Popen(["xdg-open", folder])
                

def mac_app_link(executable_path, app_path, icon_path=False):
    info_plist_template = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>%s</string>
    <key>CFBundleExecutable</key>
    <string>%s</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
</dict>
</plist>
'''
    bundle_name = os.path.basename(app_path)
    basename = bundle_name
    if not app_path.endswith('.app'):
        app_path += '.app'
    if os.path.exists(app_path):
        print 'File already exists:', app_path
        return
    MacOS_folder = os.path.join(app_path, 'Contents/MacOS')
    link_path = os.path.join(MacOS_folder, basename)
    info_plist_path = os.path.join(app_path, 'Contents/Info.plist')
    try:
        os.makedirs(MacOS_folder)
        os.symlink(executable_path, link_path)
        if icon_path:
            Resources_folder = os.path.join(app_path, 'Contents/Resources')
            os.makedirs(Resources_folder)
            icon_link = os.path.join(Resources_folder, os.path.basename(icon_path))
            os.symlink(icon_path, icon_link)
            icon_name = os.path.basename(icon_link)
        else:
            icon_name = 'AppIcon'
        open(info_plist_path, 'w').write(info_plist_template % (bundle_name, basename))
    except OSError as e:
        print 'Could not create app link:', e
