#!/usr/bin/env python

import xml.etree.ElementTree as ET
import os
import sys
import time

USAGE = '''Attempts to fix certain problems with mixed framerate projects from Adobe Premiere.
Writes the new sequence to a separate file.
Usage: %s sequence.xml [sequence2.xml ...]''' % os.path.basename(sys.argv[0])

def tc2frames(tc, Framerate):
    frames = int(tc.split(':')[3])
    frames += int(tc.split(':')[2]) * Framerate
    frames += int(tc.split(':')[1]) * Framerate * 60
    frames += int(tc.split(':')[0]) * Framerate * 60 * 60
    return frames

def frames2tc(frames, Framerate):
    (frames, Framerate) = (float(frames), float(Framerate))
    hours = math.floor(frames / ( Framerate * 60 * 60 ))
    framesleft = frames - (hours * Framerate * 60 * 60)
    minutes = math.floor(framesleft / ( Framerate * 60 ))
    framesleft -= ( minutes * Framerate * 60 )
    seconds = math.floor(framesleft / ( Framerate ))
    framesleft -= ( seconds * Framerate )
    tc = "%02d:%02d:%02d:%02d" % ( hours, minutes, seconds, framesleft )
    return tc

class xmlfix:
    def __init__(self, file_path, verbose=False):
        self.tree = ET.parse(file_path)
        root = self.tree.getroot()
        for clip in root.iter('clipitem'):
            try:
                clip_file_name = clip.find('file/name').text
                clip_duration = clip.find('duration').text
                clip_file_duration = clip.find('file/duration').text
                clip_start = clip.find('start').text
                clip_end = clip.find('end').text
                clip_in = clip.find('in').text
                clip_out = clip.find('out').text
                clip_frames_int = int(clip.find('out').text) - int(clip.find('in').text)
                clip_timebase = clip.find('rate/timebase').text
                clip_file_timebase = clip.find('file/rate/timebase').text
                clip_file_timecode_string = clip.find('file/timecode/string').text
                clip_file_timecode_timebase = clip.find('file/timecode/rate/timebase').text
                clip_file_timecode_frame = clip.find('file/timecode/frame').text
                if ';' in clip_file_timecode_string: # Not supported
                    pass
                elif clip_duration == clip_file_duration and clip_timebase != clip_file_timebase : # Interpreted to project rate
                    if verbose: print "[%s-%s] %s\n Source timebase:    %s\n Interpret timebase: %s" % (clip_start, clip_end, clip_file_name, clip_file_timebase, clip_timebase)
                    clip.find('file/rate/timebase').text = clip_timebase
                    if verbose: print ' Source file timebase modified: %s -> %s' % (clip_file_timebase, clip_timebase)
                    corrected_tc_frame = ( tc2frames(clip_file_timecode_string, int(clip_timebase)) * int(clip_file_timecode_timebase) ) / int(clip_timebase)
                    clip.find('file/timecode/frame').text = "%i" % corrected_tc_frame
                    if verbose: print ' Source timecode start frame modified: %s -> %s' % (clip_file_timecode_frame, clip.find('file/timecode/frame').text)
                    clip.find('file/timecode/rate/timebase').text = clip_timebase
                    if verbose: print ' Source timecode timebase modified: %s -> %s' % (clip_file_timecode_timebase, clip_timebase)
                elif clip_duration != clip_file_duration: # Different framerate
                    estimated_frame_rate = float(clip_timebase) * float(clip_file_duration) / float(clip_duration)
                    if verbose: print "[%s-%s] %s\n Stated framerate: %s Estimated framerate: %s" % (clip_start, clip_end, clip_file_name, clip_file_timebase, estimated_frame_rate)
                    if abs(float(clip_file_timebase) - estimated_frame_rate) > 1.0: # Interpreted as something else ...
                        """ Have yet to find a perfect fix for this """
                        if verbose: print ' Interpreted as: %5.3f' % estimated_frame_rate
                        estimated_frame_rate_str = "%5.3f" % estimated_frame_rate
                        clip.find('file/rate/timebase').text = estimated_frame_rate_str
                        if verbose: print ' Source file timebase modified: %s -> %s' % (clip_file_timebase, estimated_frame_rate_str)
                        #clip.find('file/timecode/rate/timebase').text = estimated_frame_rate_str
                        #if verbose: print ' Source timecode timebase modified: %s -> %s' % (clip_file_timecode_timebase, estimated_frame_rate_str)
                        #if verbose: print ' Source in point modified: %s' % clip.find('in').text,
                        #modified_in_point = float(clip.find('in').text) * float(clip_file_timecode_timebase) / float(clip_timebase)
                        #clip.find('in').text = "%i" % int(round(modified_in_point))
                        #if verbose: print clip.find('in').text
                        #if verbose: print ' Source out point modified: %s' % clip.find('out').text,
                        #modified_out_point_int = int(clip.find('in').text) + clip_frames_int
                        #clip.find('out').text = "%i" % modified_out_point_int
                        #if verbose: print clip.find('out').text
                        #corrected_tc_frame = float(tc2frames(clip_file_timecode_string, int(clip_timebase)) * estimated_frame_rate ) / float(clip_timebase)
                        corrected_tc_frame = ( float(tc2frames(clip_file_timecode_string, int(clip_timebase)) * float(clip_file_timecode_timebase) )) / float(clip_timebase)
                        corrected_tc_frame_int = int(round(corrected_tc_frame))
                        # tc_frame_diff = int(corrected_tc_frame) - corrected_tc_frame_int
                        # real_diff = float(tc_frame_diff) / float(clip_file_timecode_timebase) * estimated_frame_rate
                        # real_corrected_tc_frame_int = int(round(real_diff)) + 
                        clip.find('file/timecode/frame').text = "%i" % corrected_tc_frame_int
                        if verbose: print ' Source timecode start frame modified: %s -> %s' % (clip_file_timecode_frame, clip.find('file/timecode/frame').text)
            except AttributeError:
                pass
    def write(self, out_path, verbose=False):
        try:
            self.tree.write(out_path)
            if verbose: print 'Wrote %s' % out_path
        except:
            raise

if __name__ == "__main__":
    if len(sys.argv) < 2:
        import subprocess
        try:
            zenityArgs = ["zenity", "--title=Select .xml files", "--file-selection", "--multiple", "--separator=|", '--file-filter=*.xml']
            input_files = subprocess.Popen(zenityArgs, stdout=subprocess.PIPE).communicate()[0].splitlines()[0].split("|")
        except:
            print USAGE
            sys.exit(1)
    else:
        input_files = sys.argv[1:]
    for file_path in input_files:
        print file_path
        #render = 
        xmlfix(file_path, verbose=True).write(file_path+'.fix.xml', verbose=True)