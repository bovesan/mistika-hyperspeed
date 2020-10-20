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

def prettyPath(path, pattern, prettyname):
    pathParts = path.split('/')
    patternParts = pattern.split('/')
    for i, patternPart in enumerate(patternParts):
        if re.search(r'[^/]*\[_?renderName\][^/]*', patternPart):
            pathParts[i] = prettyname
    return '/'.join(pathParts)

for dependency in render.output_stack.dependencies:
    if (dependency.type in ['highres', 'lowres', 'audio']):
        if (dependency.type == 'audio'):
            new_path = prettyPath(dependency.path, render.audioPath, render.prettyname)
        else:
            new_path = prettyPath(dependency.path, render.mediaPath, render.prettyname)
        folder = os.path.dirname(new_path)
        if not os.path.isdir(folder):
            if os.path.exists(folder):
                subprocess.call(["xmessage", "-nearmouse", "Rename failed:\nTarget path, "+folder+" exists and is not a folder."])
                sys.exit()
            else:
                if not os.path.isdir(archiveFolder):
                    try:
                        os.makedirs(archiveFolder)
                    except Exception as e:
                        subprocess.call(["xmessage", "-nearmouse", "Rename failed:\nCould not create target folder:, "+folder+"\n"+str(e)])
                        raise e
        if '%' in dependency.path:
            i = 0
            for frame_range in dependency.frame_ranges:
                if i == 0:
                    if not os.path.isfile(dependency.path):
                        break
                for frame_n in range(frame_range.start, frame_range.end+1):
                    i += 1
                    try:
                        os.rename(dependency.path % frame_n, new_path % frame_n)
                    except Exception as e:
                        subprocess.call(["xmessage", "-nearmouse", "Rename failed:\nFrom: "+dependency.path+"\nTo: "+new_path+"\n"+str(e)])
                        raise e
            if i == 0:
                continue
            folders.append((dependency.type.capitalize(), folder))
        else:
            if not os.path.isfile(dependency.path):
                continue
            try:
                os.rename(dependency.path, new_path)
            except Exception as e:
                subprocess.call(["xmessage", "-nearmouse", "Rename failed:\nFrom: "+dependency.path+"\nTo: "+new_path+"\n"+str(e)])
                raise e
            folders.append((dependency.type.capitalize(), new_path))
        cleanupFolder = os.path.dirname(dependency.path)
        while cleanupFolder:
            try:
                os.rmdir(cleanupFolder)
                cleanupFolder = os.path.dirname(cleanupFolder)
            except Exception as e:
                break

message = 'Rename complete: \n\
Project: %s\n\
Render:  %s\n\
Name:    %s' % ( render.project, render.name, render.prettyname )

buttons = ''
for i, folder in enumerate(folders):
    buttons += folder[0]+':'+str(i+1)+','
    message += '\n'+folder[0]+': '+folder[1]

nextAction = subprocess.call(["xmessage", "-nearmouse", "-buttons", buttons+"Close:0", message])
if nextAction > 0:
  hyperspeed.utils.reveal_file(folders[nextAction-1][1])
