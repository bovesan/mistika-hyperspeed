#!/usr/bin/python2
# -*- coding: utf-8 -*-

import os
import sys

try:
    cwd = os.getcwd()
    os.chdir(os.path.dirname(os.path.realpath(sys.argv[0])))
    sys.path.append("../..")
    from hyperspeed.stack import Stack, DEPENDENCY_TYPES
    from hyperspeed import mistika
    from hyperspeed import human
except ImportError:
    mistika = False

template = '''Group(
groupType(1)
trimDesc( head(0) speed(1) )
D(
    video(3) audio(0) numAudioChannels(2) NumPerFile(2)
    fields(0)
    FirstFrameIndex(0) useFrameIndex(0)
    MediaPath(#:#MR2_0144:#benchmark:%s[frameIndex%6].[ext])
    AudioPath(#:#MR2_0144:#benchmark:/Volumes/SAN3/Limbo/[project][_tapeName][_renderName][_segmentIndex][_eye?Left:Right][.ext])
    tape(A001C013_221202_RNQM)
    Timecode(0@25$0)
    clipRecordTimecode(0@25)
    RenderProject(Benchmark)
    X(3840) Y(2160) JobFrameRate(25.000000) QDropFrame(1) 
    screenRatio(1.777) lowResRatio(2)
    xLiveVideResolution(1920) yLiveVideResolution(1080)
    extendedRange(0) reduceFactor(2)
    btColorSpaceYUV(709)
    DeleteBeforeRender(0)
    WorkType(0)
dFiltersConfig(
    Toggle(1)   Toggle(1)   Toggle(1)   Toggle(1)
    dFilter(name() gui(0) live(0)  scope(0) render(0) Streaming(0) eye(0) comment() active(0) toggle(0))
    dFilter(name() gui(0) live(0)  scope(0) render(0) Streaming(0) eye(0) comment() active(0) toggle(0))
    dFilter(name() gui(0) live(0)  scope(0) render(0) Streaming(0) eye(0) comment() active(0) toggle(0))
    dFilter(name() gui(0) live(0)  scope(0) render(0) Streaming(0) eye(0) comment() active(0) toggle(0))
    dFilter(name() gui(0) live(0)  scope(0) render(0) Streaming(0) eye(0) comment() active(0) toggle(0))
    dFilter(name() gui(0) live(0)  scope(0) render(0) Streaming(0) eye(0) comment() active(0) toggle(0))
    dFilter(name() gui(0) live(0)  scope(0) render(0) Streaming(0) eye(0) comment() active(0) toggle(0))
    dFilter(name() gui(0) live(0)  scope(0) render(0) Streaming(0) eye(0) comment() active(0) toggle(0))
    dFilter(name() gui(0) live(1)  scope(0) render(0) Streaming(0) eye(0) comment() active(1) toggle(0))
    dFilter(name() gui(0) live(0)  scope(0) render(0) Streaming(0) eye(0) comment() active(0) toggle(0))
    dFilter(name() gui(0) live(0)  scope(0) render(0) Streaming(0) eye(0) comment() active(0) toggle(0))
    dFilter(name() gui(0) live(0)  scope(0) render(0) Streaming(0) eye(0) comment() active(0) toggle(0))
    dFilter(name() gui(0) live(0)  scope(0) render(0) Streaming(0) eye(0) comment() active(0) toggle(0))
    dFilter(name() gui(0) live(0)  scope(0) render(0) Streaming(0) eye(0) comment() active(0) toggle(0))
    dFilter(name() gui(0) live(0)  scope(0) render(0) Streaming(0) eye(0) comment() active(0) toggle(0))
    dFilter(name() gui(0) live(0)  scope(0) render(0) Streaming(0) eye(0) comment() active(0) toggle(0))
)
    L(d(Disk.dev) f(DPX.DPX_RGB_10) e(.dpx) i(3))
    H(d(Disk.dev) f(DPX.DPX_RGB_10) e(.dpx) i(3))
    outputFraming(a(1) f(1) w(256) h(256) x(100.000000) y(100.000000) X(0.000000) Y(0.000000) l(0.000000) r(100.000000) u(100.000000) d(0.000000))
    E(
        renderName(BENCHMARK)
        baseName(BENCHMARK)
        preferedClip(0)
        selectiveMode(0) firstSegmentIndex(0)
        tapenameSource(0) TCSource(0)
        onlyUsedClips(1) ignoreJS(0)
        NkWithMedia(0) RndWithMedia(0)      SourceMediaPath()
        gamma(-1) Gamut(-1)
    )
    U(
    v(RED_REDUCE_FACTOR=2)
    )
)
p(
    n(BENCHMARK)
    X(%i) Y(0) W(%i) F(0)
)
'''
# % (tmpFolder, firstFrame, framesTotal)
footer = '''
)
'''

def benchmark(stackPath):
    getTests(stackPath)
    # stack = Stack(stackPath)
    ramdisk = '/dev/shm'
    folder = os.path.join(ramdisk, 'benchmark')

def getTests(stackPath):
    try:
        groups = []
        level_names = []
        fx_type = None
        char_buffer = ''
        char_buffer_store = ''
        ungroup = False
        groupName = ''
        groupStart = 0
        groupLength = 0
        for line in open(stackPath):
            for char in line:
                if char == '(':
                    char_buffer = char_buffer.replace('\n', '').strip()
                    level_names.append(char_buffer)
                    char_buffer = ''
                elif char == ')':
                    f_path = False
                    object_path = '/'.join(level_names)
                    if object_path.endswith('/ungroup') and char_buffer == '1':
                        ungroup = True
                    elif object_path.endswith('Group/D'): # This is a render
                        ungroup = True
                    elif object_path.endswith('Group/p') and level_names.count('Group') == 1:
                        ungroup = False
                        groups.append((groupName, groupStart, groupLength))
                        print groupName, groupStart, groupLength
                    elif object_path.endswith('Group/p/n'):
                        if not ungroup:
                            groupName = char_buffer
                        else:
                            ungroup = False
                    elif object_path.endswith('Group/p/X'):
                        groupStart = int(char_buffer)
                    elif object_path.endswith('Group/p/W'):
                        groupLength = int(char_buffer)
                    char_buffer = ''
                    del level_names[-1]
                elif len(level_names) > 0 and level_names[-1] == 'Shape':
                    continue
                elif char:
                    char_buffer += char
    except IOError as e:
        print 'Could not open ' + stackPath
        raise e

if __name__ == '__main__':
    benchmark(sys.argv[1])