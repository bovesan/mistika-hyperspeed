#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys

try:
    cwd = os.getcwd()
    os.chdir(os.path.dirname(os.path.realpath(sys.argv[0])))
    sys.path.append("../..")
    from hyperspeed import mistika
    import hyperspeed.utils
    print 'Revealing project:', mistika.project
    hyperspeed.utils.reveal_file(os.path.join(mistika.projects_folder, mistika.project))
except ImportError:
    print "Could not load Hyperspeed modules"
