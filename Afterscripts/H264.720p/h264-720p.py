#!/usr/bin/env python
# -*- coding: utf-8 -*-

import hyperspeed.afterscript

title          = 'H264.720p'
cmd            = '-vsync 0 -movflags faststart -crf 20 -minrate 0 -maxrate 4M -bufsize 15M -filter_complex "scale=1280:720:out_color_matrix=bt709,setsar=1" -pix_fmt yuv420p -vcodec libx264 -c:a aac -b:a 160k -strict -2 -ac 2 -ar 44100 -acodec aac -af pan=stereo:c0=c0:c1=c1'
# Path relative to primary output folder of render:P
# default_output = '[project]_[render_name].[codec].mov'
# Absolute path:
default_output = '/Volumes/SAN3/Masters/[project]/[project]_[rendername]/[project]_[rendername].h264.720p.mov'

hyperspeed.afterscript.AfterscriptFfmpeg(__file__, cmd, default_output, title)
hyperspeed.afterscript.gtk.main()
