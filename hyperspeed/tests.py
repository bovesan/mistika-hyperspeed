#!/usr/bin/env python

import unittest
import sys
import os
import subprocess
import time
import xml.etree.ElementTree as ET

import hyperspeed
import hyperspeed.afterscript
import hyperspeed.human
import hyperspeed.mistika
import hyperspeed.sockets
import hyperspeed.stack
import hyperspeed.text
import hyperspeed.tools
import hyperspeed.ui
import hyperspeed.utils
import hyperspeed.video

os.chdir(hyperspeed.folder)

class ToolsTests(unittest.TestCase):
    def test_launch(self):
        for root, dirs, filenames in os.walk(os.path.join(hyperspeed.folder, 'Tools')):
            for name in dirs:
                if name.startswith('.'):
                    continue
                path = os.path.join(root, name)
                if 'config.xml' in os.listdir(path):
                    tree = ET.parse(os.path.join(path, 'config.xml'))
                    treeroot = tree.getroot()
                    path = os.path.join(path, treeroot.find('executable').text)
                    p = subprocess.Popen([path])
                    time.sleep(1)
                    p.poll()
                    if p.returncode > 0:
                        self.fail('Crashed: %s' % program_path)
                    else:
                        try:
                            p.kill()
                        except OSError:
                            pass # Program was closed but had returncode 0. Should be ok.

class StackTests(unittest.TestCase):
    def test_dependencies_attribute(self):
    	stack = hyperspeed.stack.Stack('Samples/hill14.env')
    	self.maxDiff = None
    	# print stack.dependencies
    def test_names(self):
        stack = hyperspeed.stack.Stack('Samples/160912-1745_Gourmet_15sek_tekstet_HF_Delivery_IN_JS422_8B.rnd')
        correct_name = 'Gourmet_15sek_tekstet#noupload'
        correct_title = 'Gourmet_15sek_tekstet'
        correct_tags = ['noupload']
        # print 'Group name: ', repr(stack.groupname)
        # print 'Correct name: ', repr(correct_name)
        # print 'Group title: ', repr(stack.title)
        # print 'Correct title: ', repr(correct_title)
        # print 'Group tags: ', repr(stack.tags)
        # print 'Correct tags: ', repr(correct_tags)
        if correct_name != stack.groupname or correct_title != stack.title or correct_tags != stack.tags:
            self.fail('Mismatch')


if __name__ == '__main__':
    unittest.main()