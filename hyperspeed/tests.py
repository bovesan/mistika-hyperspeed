#!/usr/bin/env python

import unittest
import sys
import os
import subprocess
import time

root_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, root_folder)
import hyperspeed
os.chdir(root_folder)

class DashboardTests(unittest.TestCase):
    def test_launch(self):
    	program_path = './hyperspeed-dashboard.py'
    	p = subprocess.Popen(['./hyperspeed-dashboard.py'])
    	time.sleep(1)
    	p.poll()
    	if p.returncode > 0:
    		self.fail('Crashed: %s' % program_path)
    	else:
    		p.kill()

class StackTests(unittest.TestCase):
    def test_dependencies_attribute(self):
    	stack = hyperspeed.stack.Stack('Samples/hill14.env')
    	self.maxDiff = None
    	print stack.dependencies
    def test_names(self):
        stack = hyperspeed.stack.Stack('Samples/160912-1745_Gourmet_15sek_tekstet_HF_Delivery_IN_JS422_8B.rnd')
        correct_name = 'Gourmet_15sek_tekstet#noupload'
        correct_title = 'Gourmet_15sek_tekstet'
        correct_tags = ['noupload']
        print 'Group name: ', repr(stack.groupname)
        print 'Correct name: ', repr(correct_name)
        print 'Group title: ', repr(stack.title)
        print 'Correct title: ', repr(correct_title)
        print 'Group tags: ', repr(stack.tags)
        print 'Correct tags: ', repr(correct_tags)
        if correct_name != stack.groupname or correct_title != stack.title or correct_tags != stack.tags:
            self.fail('Mismatch')


if __name__ == '__main__':
    unittest.main()