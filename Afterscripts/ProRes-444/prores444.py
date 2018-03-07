#!/usr/bin/env python
# -*- coding: utf-8 -*-

import hyperspeed.afterscript

title          = 'ProRes 444'
executable     = '/opt/ffmbc/FFmbc-0.7-rc8-rec709/ffmbc'
cmd            = '-vsync 0 -vcodec prores -pix_fmt yuv444p10le -color_primaries bt709 -ar 48000 -acodec pcm_s24le'
# Path relative to primary output folder of render:
# default_output = '[project]_[render_name].[codec].mov'
# Absolute path:
default_output = '/Volumes/SAN3/Masters/[project]/[project]_[rendername]/[project]_[rendername].ProRes444.mov'

hyperspeed.afterscript.AfterscriptFfmpeg(__file__, cmd, default_output, title, executable)
hyperspeed.afterscript.gtk.main()
