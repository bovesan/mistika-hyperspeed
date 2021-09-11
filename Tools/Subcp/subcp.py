#!/usr/bin/env python3

import datetime
import os
import sys
import subprocess
import glob
import time

def sizeof_fmt(num, suffix='B'):
    if num == 0:
        return '0 %s' % suffix
    for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
        if abs(num) < 1024.0:
            return "%3.1f %s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)

def duration_fmt(duration):
    tdelta = datetime.timedelta(seconds=duration)
    d = dict(days=tdelta.days)
    d['hrs'], rem = divmod(tdelta.seconds, 3600)
    d['min'], d['sec'] = divmod(rem, 60)

    if d['min'] is 0:
        fmt = '{sec} sec'
    elif d['hrs'] is 0:
        fmt = '{min} min {sec} sec'
    elif d['days'] is 0:
        fmt = '{hrs} hr(s) {min} min {sec} sec'
    else:
        fmt = '{days} day(s) {hrs} hr(s) {min} min {sec} sec'

    return fmt.format(**d)

usage = '''
Copies a subset of files or directories from src to destination using standard cp, because rsync can be slow on high performance storage.

Usage: %s folder1 [folder2, folder3 ...] [--maxminutes=0] [--dry-run] 'src/*' dst

Remember quotes to avoid shell expansion on src wildcard.
''' % os.path.basename(sys.argv[0])

maxMinutes = 0
dryRun = False
paths = []
for arg in sys.argv[1:]:
    if arg.startswith('-'):
        if arg.startswith('--maxminutes='):
            maxMinutes = float(arg.split('=')[1])
        elif arg == '--dry-run':
            dryRun = True
        else:
            print('Invalid argument: %s' % arg)
            print(usage)
            sys.exit(4)
        continue
    paths.append(arg)

print('maxMinutes: %i' % maxMinutes)

if len(paths) < 3:
    print(usage)
    sys.exit(1)

src = paths[-2]
dst = paths[-1]
folders = paths[0:-2]

srcPreGlob = src.split('*')[0]

startTime = time.time()
timeLimit = 0
if maxMinutes:
    timeLimit = startTime + 60*maxMinutes


byteIncrease = 0
projectsModified = 0
filesCopied = 0

for srcGlob in glob.glob(src):
    relPath = os.path.relpath(srcGlob, srcPreGlob)
    for folder in folders:
        if timeLimit and time.time() > timeLimit:
            print('Reached time limit (%i minutes)' % maxMinutes)
            sys.exit(3)
        srcPath = os.path.join(srcPreGlob, relPath, folder)
        dstPath = os.path.join(dst, relPath)
        if not os.path.exists(srcPath):
            continue
        try:
            os.makedirs(dstPath)
        except:
            pass
        duCmd = ['du', '-bs', dstPath]
        try:
            sizeBefore = int(subprocess.Popen(duCmd, stdout=subprocess.PIPE).communicate()[0].split()[0])
        except:
            sizeBefore = 0
        cmd = ['cp', '--verbose', '--update', '--recursive', '--archive', srcPath, dstPath]
        print(cmd)
        if not dryRun:
            output = subprocess.Popen(cmd, stdout=subprocess.PIPE).communicate()[0]
            lines = output.splitlines()
            if len(lines) > 0:
                projectsModified += 1
                filesCopied += len(lines)
                sys.stdout.buffer.write(output)
            try:
                sizeAfter = int(subprocess.Popen(duCmd, stdout=subprocess.PIPE).communicate()[0].split()[0])
            except:
                sizeAfter = 0
            byteIncrease += sizeAfter - sizeBefore

elapsed = time.time() - startTime
avgSpeed = float(byteIncrease) / elapsed

print()
print('Time elapsed: %s' % duration_fmt(elapsed))
print('Projects modified: %i' % projectsModified)
print('Files/directories copied: %i' % filesCopied)
print('Destination folders increased by: %s' % sizeof_fmt(byteIncrease))
print('Average speed: %sps' % sizeof_fmt(avgSpeed))

# cd /Volumes/mediaraid-2/Projects && cp --verbose --update --recursive --archive --parents */Media /Volumes/mediaraid/temp/
