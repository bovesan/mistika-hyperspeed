#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
# try:
#     os.setsid()
# except OSError as e:
#     print e

import hyperspeed
import hyperspeed.afterscript

title          = 'Rewrap to mov'
cmd            = '-vcodec copy -acodec copy'
# Path relative to primary output folder of render:
# output_pattern = '<project>_<render_name>.<codec>.mov'
# Absolute path:
output_pattern = '/Volumes/SAN3/Masters/<project>/<project>_<render_name>/<project>_<render_name>.<codec>.mov'

hyperspeed.afterscript.AfterscriptFfmpeg(__file__, cmd, output_pattern, title)
hyperspeed.afterscript.gtk.main()

# env = os.environ.copy()
# env.clear()
# env = {
# 	'LESS': '-M -I',
#     'CPU': 'x86_64',
#     'KDE_FULL_SESSION': 'true',
#     'INFOPATH': '/usr/local/info:/usr/share/info:/usr/info',
#     'SHELL': '/bin/tcsh',

# }
# cmd = [
# 	os.path.join(hyperspeed.folder, 'hyperspeed/afterscript.py'),
# 	'AfterscriptFfmpeg',
# 	__file__,
# 	cmd,
# 	output_pattern,
# 	title
# ]
# subprocess.call(cmd, env=env)
