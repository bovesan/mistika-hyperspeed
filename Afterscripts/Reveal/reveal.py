#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys, os, time, subprocess

try:
    cwd = os.getcwd()
    os.chdir(os.path.dirname(os.path.realpath(sys.argv[0])))
    sys.path.append("../..")
    import hyperspeed.human
    import hyperspeed.mistika
    import hyperspeed.stack
    import hyperspeed.utils
except ImportError:
    print 'Hyperspeed init error'
    sys.exit(1)

rnd_path = hyperspeed.mistika.get_rnd_path(sys.argv[2])
render = hyperspeed.stack.Render(rnd_path)

output_paths = []
if render.output_video != None:
    if '%' in render.output_video.path:
        video_file_path = render.output_video.path % render.output_video.start
    else:
        video_file_path = render.output_video.path
    output_paths.append(video_file_path)
if render.output_proxy != None:
    if '%' in render.output_proxy.path:
        video_file_path = render.output_proxy.path % render.output_proxy.start
    else:
        video_file_path = render.output_proxy.path
    output_paths.append(video_file_path)
if render.output_audio != None:
    output_paths.append(render.output_audio.path)

hyperspeed.utils.reveal_file(output_paths)
