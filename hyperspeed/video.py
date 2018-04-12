#!/usr/bin/env python
import sys, os, subprocess, string, re, math

def tc2frames(tc, Framerate):
    frames = int(tc.split(':')[3])
    frames += int(tc.split(':')[2]) * Framerate
    frames += int(tc.split(':')[1]) * Framerate * 60
    frames += int(tc.split(':')[0]) * Framerate * 60 * 60
    return frames

def frames2tc(frames, Framerate, strip=False):
    # print frames
    # print Framerate
    (frames, Framerate) = (float(frames), float(Framerate))
    # print frames
    # print Framerate
    hours = math.floor(frames / ( Framerate * 60 * 60 ))
    # print hours
    framesleft = frames - (hours * Framerate * 60 * 60)
    
    minutes = math.floor(framesleft / ( Framerate * 60 ))
    framesleft -= ( minutes * Framerate * 60 )
    
    seconds = math.floor(framesleft / ( Framerate ))
    framesleft -= ( seconds * Framerate )
    
    tc = "%02d:%02d:%02d:%02d" % ( hours, minutes, seconds, framesleft )
    if strip and frames > 0:
        tc = tc.lstrip(':0')
    # print tc 
    return tc

def frames2tc_float(frames, Framerate):
    frames = float(frames)
    Framerate = float(Framerate)
    (frames, Framerate) = (float(frames), float(Framerate))
    hours = math.floor(frames / ( Framerate * 60 * 60 ))
    framesleft = frames - (hours * Framerate * 60 * 60)
    
    minutes = math.floor(framesleft / ( Framerate * 60 ))
    framesleft -= ( minutes * Framerate * 60 )
    
    seconds = math.floor(framesleft / ( Framerate ))
    framesleft -= ( seconds * Framerate )
    
    tc = "%02d:%02d:%02d,%03d" % ( hours, minutes, seconds, (framesleft / float(Framerate)) * 1000)
    return tc
    
def time2frames(tc, Framerate):
    frames = ( int(tc.split(':')[2].split('.')[0]) + 1 ) * Framerate
    frames += int(tc.split(':')[1]) * Framerate * 60
    frames += int(tc.split(':')[0]) * Framerate * 60 * 60
    return frames