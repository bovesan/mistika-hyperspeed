#!/usr/bin/env python
# -*- coding: utf-8 -*-

import subprocess
import os
import sys

BLOCK_SIZE_MAX = 100

def rreplace(s, old, new, occurrence):
    li = s.rsplit(old, occurrence)
    return new.join(li)

batches = []
for batch in sys.argv[1:]:
    if batch.endswith('.batch'):
        batches.append(batch)

if len(batches) == 0:
    for batch in os.listdir('.'):
        if batch.endswith('.batch'):
            batches.append(batch)

if len(batches) == 0:
    print 'No .batch files provided'
    sys.exit(1)

# mistika -r /Volumes/SLOW_HF/PROJECTS/18945_OBOS/DATA/RENDER/auto_0019/auto_0019_0000_000.rnd 0 13309 66545 0 5
# mistika -r /Volumes/SLOW_HF/PROJECTS/18945_OBOS/DATA/RENDER/auto_0019/auto_0019_0001_000.rnd 13309 13309 66545 1 5
# mistika -r /Volumes/SLOW_HF/PROJECTS/18945_OBOS/DATA/RENDER/auto_0019/auto_0019_0002_000.rnd 26618 13309 66545 2 5
# mistika -r /Volumes/SLOW_HF/PROJECTS/18945_OBOS/DATA/RENDER/auto_0019/auto_0019_0003_000.rnd 39927 13309 66545 3 5
# mistika -r /Volumes/SLOW_HF/PROJECTS/18945_OBOS/DATA/RENDER/auto_0019/auto_0019_0004_000.rnd 53236 13309 66545 4 5

for batch in batches:
    for line in open(batch):
        segment_file = line.split()[2]
        segment_length = int(line.split()[4])
        parsed_frames = 0
        block_i = -1
        while parsed_frames < segment_length:
            block_i += 1
            block_file = rreplace(segment_file, '.rnd', '.%06d.rnd' % block_i, 1)
            print 'Setting up %s' % block_file
            block_id = os.path.basename(segment_file.rsplit('.', 1)[0]) + '%06d' % block_i
            block_content = ''
            block_in_point = block_i * BLOCK_SIZE_MAX
            block_length = min(BLOCK_SIZE_MAX, segment_length - block_in_point)
            parsing = True
            parsing_p = False
            for rnd_line in open(segment_file):
                if parsing:
                    if rnd_line.startswith('trimDesc( head('):
                        rnd_line = rnd_line.replace('head(0)', 'head(%s)' % block_in_point)
                        print rnd_line,
                    elif rnd_line.strip().startswith('MediaPath('):
                        rnd_line = rreplace(rnd_line, '/', '/%s/' % block_id, 1)
                        print rnd_line,
                    elif rnd_line.strip().startswith('AudioPath('):
                        rnd_line = rreplace(rnd_line, '/', '/%s/' % block_id, 1)
                        print rnd_line,
                    elif rnd_line.startswith('p('):
                        print rnd_line,
                        parsing_p = True
                    elif parsing_p and rnd_line.strip().startswith('X('):
                        rnd_line = rnd_line.replace('W(%s)' % segment_length, 'W(%s)' % block_length)
                        print rnd_line,
                        parsing = False
                block_content += rnd_line
            open(block_file, 'w').write(block_content)
            parsed_frames += block_length