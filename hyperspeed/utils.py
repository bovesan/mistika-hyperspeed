#!/usr/bin/env python

import platform
import subprocess
import os

def reveal_file(path):
    folder = os.path.dirname(path)
    if platform.system() == "Windows":
        subprocess.Popen(["explorer", "/select,", path])
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", '-R', path])
    else:
        subprocess.Popen(["xdg-open", folder])