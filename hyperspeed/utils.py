#!/usr/bin/env python

import platform
import subprocess
import os

def reveal_file(path):
    folder = os.path.dirname(path)
    print 'Reveal: ', folder
    if platform.system() == "Windows":
        subprocess.Popen(["explorer", "/select,", path])
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", '-R', path])
    else:
        os.setsid()
        try:
            subprocess.Popen(["dolphin", '--select', path])
        except OSError:
            subprocess.Popen(["xdg-open", folder])