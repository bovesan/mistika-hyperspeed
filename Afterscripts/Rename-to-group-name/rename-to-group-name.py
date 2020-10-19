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
except ImportError:
    sys.exit()

rnd_path = hyperspeed.mistika.get_rnd_path(sys.argv[2])
render = hyperspeed.stack.Render(rnd_path)
render.archive('renamed')

folders = []

for dependency in render.output_stack.dependencies:
    if (dependency.type in ['highres', 'lowres', 'audio']):
        if '%' in dependency.path:
            sequence_files = []
            folder = os.path.dirname(dependency.path)
            new_path = os.path.join(folder, render.prettyname+'_%06d'+os.path.splitext(dependency.path)[1])
            i = 0
            for frame_range in dependency.frame_ranges:
                for frame_n in range(frame_range.start, frame_range.end+1):
                    i += 1
                    sequence_files.append(basename % frame_n)
                    os.rename(dependency.path % frame_n, new_path % frame_n)
            if len(os.listdir(folder)) == i:
                new_folder = os.path.join(os.path.dirname(folder), render.project+'_'+render.prettyname+os.path.splitext(dependency.path)[1])
                os.rename(folder, new_folder)
                folders.append((dependency.type, new_folder))
            else:
                folders.append((dependency.type, os.path.dirname(dependency.path)))
        else:
            new_path = os.path.join(os.path.dirname(dependency.path), render.project+'_'+render.prettyname+os.path.splitext(dependency.path)[1])
            os.rename(dependency.path, new_path)
            folders.append((dependency.type, os.path.dirname(dependency.path)))

buttons = ''
for i, folder in folders.enumerate():
    buttons += folder[0]+' '+folder[1]+':'+i+','

message = 'Rename complete: \n\
Project: %s\n\
Render:  %s\n\
Name:    %s' % ( render.project, render.name, render.prettyname )

nextAction = subprocess.call(["xmessage", "-nearmouse", "-buttons", buttons+"Close:0", message])