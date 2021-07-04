#!/usr/bin/env python
# -*- coding: utf-8 -*-

import hyperspeed.afterscript

title          = 'Rewrap to mov'
cmd            = '-vcodec copy -acodec copy'
# Path relative to primary output folder of render:
# default_output = '[project]_[render_name].[codec].mov'
# Absolute path:
default_output = '/Volumes/SAN3/Masters/[project]/[project]_[rendername]/[project]_[rendername].[codec].mov'

hyperspeed.afterscript.AfterscriptFfmpeg(__file__, cmd, default_output, title)
hyperspeed.afterscript.gtk.main()
