#!/usr/bin/env python3

import os
import sys
import subprocess
import glob
import time

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

timeLimit = 0
if maxMinutes:
	timeLimit = time.time() + 60*maxMinutes

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
			os.makedirs(os.path.join(dst, relPath))
		except:
			pass
		cmd = ['cp', '--update', '--recursive', '--archive', srcPath, dstPath]
		print(cmd)
		if not dryRun:
			subprocess.call(cmd)


# cd /Volumes/mediaraid-2/Projects && cp --verbose --update --recursive --archive --parents */Media /Volumes/mediaraid/temp/