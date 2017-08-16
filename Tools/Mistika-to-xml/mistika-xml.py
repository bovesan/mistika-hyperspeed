#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2016 Bengt Ove Sannes
# bengtove@bovesan.com


import sys, os, xml.dom.minidom, time, xml.sax
from xml.sax.saxutils import escape

if len(sys.argv) < 2:
    print '''
This script converts SGO Mistika structures to xml.
Script version: 17 March 2016
(c) 2016 Bengt Ove Sannes
bengtove@bovesan.com

Usage: %s [-s] [-v] [-y] inputfile1 [inputfile2 ...]

The xml file will be stored next to the input file.

-a Validate output file
-s Write output to stdout instead of to file
-v Verbose output (written to stderr)
-y Overwrite existing files without interaction
''' % os.path.basename(sys.argv[0])

def sizeof_fmt(num, suffix='B'):
    for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)

verbose = False
overwrite = False
pipeMode = False
validate = False

for inPath in sys.argv[1:]:
    if inPath == '-a':
        validate = True
        continue
    if inPath == '-s':
        pipeMode = True
        continue
    if inPath == '-v':
        verbose = True
        continue
    if inPath == '-y':
        overwrite = True
        continue
    inSize = os.path.getsize(inPath)
    if pipeMode:
        outPath = 'STDOUT'
    else:
        outPath = inPath + '.xml'
    if verbose:
        sys.stderr.write('Input:               %s\nInput size:          %s\nOutput:              %s\n' % (inPath, sizeof_fmt(inSize), outPath))
        sys.stderr.flush()
    if not pipeMode and os.path.isfile(outPath):
        if not overwrite:
                print 'Overwrite existing? ',
                if overwrite:
                    choice = 'y'
                else:
                    # raw_input returns the empty string for "enter"
                    yes = set(['yes','y', 'ye', ''])
                    no = set(['no','n'])
                    choice = raw_input().lower()
                if not choice in yes:
                    continue
    if verbose:
        sys.stderr.write('Conversion           ...')
        sys.stderr.flush()
    startTime = time.time()
    bal = 0
    processed = 0
    outSize = 0
    activeObjects = list()
    inHandle = open(inPath)
    if not pipeMode: outHandle = open(outPath, 'w')
    buffer = ''
    for inLine in inHandle:
        outLine = ''
        #line.split('(', 1)
        for char in escape(inLine):
            if char == '(':
                if not buffer.strip().isalnum():
                    buffer += char
                    bal += 1
                    continue
                tag = buffer.strip()
                outLine += buffer.split(tag)[0]
                outLine += '<%s>' % buffer.strip()
                outLine += buffer.split(tag)[-1]
                activeObjects.append(buffer.strip())
                buffer = ''
            elif char == ')':
                if bal > 0:
                    buffer += char
                    bal -= 1
                    continue
                outLine += buffer
                outLine += '</%s>' % activeObjects.pop()
                buffer = ''
            else:
                buffer += char
        if pipeMode:
            sys.stdout.write(outLine)
            sys.stdout.flush()
            outSize += len(outLine)
        else:
            outHandle.write(outLine)
        if verbose:
            processed += len(inLine)
            sys.stderr.write('\rConversion           %.2f%%'%(float(processed*100)/float(inSize)))
            sys.stderr.flush()
    if not pipeMode: outHandle.close()
    inHandle.close()
    if verbose:
        sys.stderr.write('\r')
        sys.stderr.write('Conversion:          100%   \n')
        sys.stderr.flush()
    #xml = xml.dom.minidom.parse(outPath)
    #open(outPath, 'w').write(xml.toprettyxml())
    if not pipeMode: outSize = os.path.getsize(outPath)
    endTime = time.time()
    if verbose:
        sys.stderr.write('Output size:         %s\nConversion time:     %.2f seconds\n' % (sizeof_fmt(outSize), endTime-startTime))
        sys.stderr.flush()
    validation = ''
    valid = True
    if validate:
        if pipeMode:
            sys.stderr.write('Cannot validate in STDOUT mode')
            sys.stderr.flush()
        else:
            if verbose:
                sys.stderr.write('Validating:          ')
                sys.stderr.flush()
            try:
                xml.sax.parse(outPath, xml.sax.handler.ContentHandler())
                validation = '\rValidation:          Success\n'
            except Exception, e:
                valid = False
                validation = '\rValidation:          %s\n' % e
        validationTime = time.time()
        if verbose or not valid:
            sys.stderr.write(validation+'Validation time:     %.2f seconds\n' % (validationTime-endTime))
            sys.stderr.flush()