#!/usr/bin/env python
from __future__ import print_function

import os
import sys
import subprocess
import glob

try:
    import __builtin__
except ImportError:
    # Python 3
    import builtins as __builtin__

try:
    cwd = os.getcwd()
    os.chdir(os.path.dirname(os.path.realpath(sys.argv[0])))
    sys.path.append("../..")
    import hyperspeed.ui
except ImportError:
    print('Could not load Hyperspeed modules')
    sys.exit(1)

USAGE = '''Strips source tc from all media in fcp xml file and saves to a new file.
Usage: %s sequence.xml [sequence2.xml ...]''' % os.path.basename(sys.argv[0])

def add_files_dialog():
    if mistika:
        folder = os.path.join(mistika.projects_folder, mistika.project)
    else:
        folder = '/'
    dialog = gtk.FileChooserDialog(title="Select .xml files", parent=None, action=gtk.FILE_CHOOSER_ACTION_OPEN, buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK), backend=None)
    # if 'darwin' in platform.system().lower():
    #     dialog.set_resizable(False) # Because resizing crashes the app on Mac
    dialog.set_select_multiple(True)
    #dialog.add_filter(filter)
    dialog.set_current_folder(folder)
    filter = gtk.FileFilter()
    filter.set_name("Xml files")
    filter.add_pattern("*.xml")
    response = dialog.run()
    if response == gtk.RESPONSE_OK:
        files = dialog.get_filenames()
        dialog.destroy()
        return files
    elif response == gtk.RESPONSE_CANCEL:
        print('Closed, no files selected')
        dialog.destroy()
        return

class xmlfix(object):
    def __init__(self, file_paths_in, prnt=False):
        if prnt:
            print = prnt
        for file_path_in in file_paths_in:
            file_path_out = file_path_in.replace('.xml', '.0tc.xml')
            open(file_path_out, 'w').write('')
            parseTC = False
            for line in open(file_path_in):
                outline = line
                if line.strip() == '<timecode>':
                    parseTC = True
                    print('Parsing TC section')
                elif line.strip() == '</timecode>':
                    parseTC = False
                elif parseTC:
                    if line.strip().startswith('<string>'):
                        outline = '<string>00:00:00:00</string>\n'
                        print( line.strip() + ' -> ' + outline.strip() )
                    elif line.strip().startswith('<frame>'):
                        outline = '<frame>0</frame>\n'
                        print( line.strip() + ' -> ' + outline.strip() )
                with open(file_path_out, 'a') as outfile:
                    outfile.write(outline)
            print( 'Wrote %s' % file_path_out )

if __name__ == "__main__":
    if len(sys.argv) < 2:
        hyperspeed.ui.gobject.threads_init()
        hyperspeed.ui.TerminalReplacement(xmlfix, ['XML input file'])
        hyperspeed.ui.gtk.main()
    else:
        input_files = sys.argv[1:]
        xmlfix(input_files)
