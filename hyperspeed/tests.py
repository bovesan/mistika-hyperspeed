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
    	stack = hyperspeed.Stack('Samples/hill14.env')
    	self.maxDiff = None
    	print stack.dependencies

if __name__ == '__main__':
    unittest.main()