#!/usr/bin/env python
# -*- coding: utf-8 -*-

import hyperspeed.afterscript

title          = 'Rewrap to mov'
cmd            = '-vcodec copy -acodec copy'
# Path relative to primary output folder of render:
# output_pattern = '<project>_<render_name>.<codec>.mov'
# Absolute path:
output_pattern = '/Volumes/SAN3/Masters/<project>/<project>_<render_name>/<project>_<render_name>.<codec>.mov'

hyperspeed.afterscript.AfterscriptFfmpeg(__file__, cmd, output_pattern, title)
hyperspeed.afterscript.gtk.main()
