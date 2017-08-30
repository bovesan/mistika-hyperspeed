#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys, os, time, subprocess

try:
    cwd = os.getcwd()
    os.chdir(os.path.dirname(sys.argv[0]))
    sys.path.append("../..")
    import hyperspeed.human
    import hyperspeed.mistika
    import hyperspeed.stack
except ImportError:
    sys.exit()

rnd_path = hyperspeed.mistika.get_rnd_path(sys.argv[2])
render = hyperspeed.stack.Render(rnd_path)

if '%' in render.output_video.path:
	video_file_path = render.output_video.path % render.output_video.end
else:
	video_file_path = render.output_video.path
videoFile_mtime = os.stat(video_file_path).st_mtime
rndFile_mtime = os.stat(render.path).st_mtime
diff = videoFile_mtime - rndFile_mtime

message = '%s %s\n%s %s\n%s difference' % ( hyperspeed.human.time_of_day(rndFile_mtime), render.path, hyperspeed.human.time_of_day(videoFile_mtime), video_file_path, hyperspeed.human.duration(diff))

subprocess.call(['xmessage', message])
