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
            del dolphinEnv["LD_LIBRARY_PATH"]
            try:
                subprocess.Popen(["dolphin", '--select', path], env=dolphinEnv)
            except OSError:
                subprocess.Popen(["xdg-open", folder])
                