#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import time
import subprocess
import json
import re
import gtk
import gobject
import pango
import threading

import hyperspeed.afterscript
import hyperspeed.mistika
import hyperspeed.stack

title       = 'Rewrap to mov'
cmd         = '-vcodec copy -acodec copy'
output_path = '/Volumes/SAN3/Masters/<project>/<project>_<render_name>.mov'

hyperspeed.afterscript.AfterscriptFfmpeg(__file__, cmd, output_path, title)
gtk.main()
