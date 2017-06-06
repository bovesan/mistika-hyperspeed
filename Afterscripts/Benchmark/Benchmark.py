#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys, os, time, subprocess

userEmpDir = os.path.join(os.path.expanduser('~'), ".emp")
sys.path.append(userEmpDir)
import emp
sys.path.append(emp.modulesDir)
import mistika

RndName = sys.argv[2]
RndInfo = mistika.readrnd(RndName)

videoFile_mtime = os.stat(RndInfo.videoFile).st_mtime
rndFile_mtime = os.stat(RndInfo.RndPath).st_mtime
diff = videoFile_mtime - rndFile_mtime

message = 'Modification time: %s %s\n                   %s %s\nDifference:        %s' % (videoFile_mtime, RndInfo.videoFile, rndFile_mtime, RndInfo.RndPath, diff)

subprocess.call(['xmessage', message])
