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
    	# print stack.dependencies
    	correct_dependencies = {'/Users/bove/MATERIAL/WORK/RnD/DATA/noun_17067_4k.lnk': {'type': 'lnk'}, '/Users/bove/Dropbox/Projects/2016/Hill/Input/hair02.0000.png': {'type': 'media'}, '/Users/bove/MATERIAL/WORK/RnD/DATA/Trek_Bicycle_Corporation_logo.svg.lnk': {'type': 'lnk'}, '/Users/bove/Dropbox/Projects/2016/Hill/Work/hill_0003/_%06d.tif': {'Start frame': 0, 'type': 'media', 'End frame': 249}, '/Users/bove/MATERIAL/DELIVERY/DI/RnD/js/RENDER_0008/RENDER_0008.js': {'type': 'media'}, '/Users/bove/MATERIAL/WORK/RnD/DATA/RENDER/RENDER_0008/RENDER_0008_hill5.clp': {'type': 'lnk'}, '/Users/bove/Dropbox/Projects/2016/Hill/Input/noun_17067_4k.tif': {'type': 'media'}, '/Users/bove/MATERIAL/WORK/RnD/DATA/RENDER/hill_0004/hill_0004_blue_summer_skies_by_perbear42-d3loh0v.clp': {'type': 'lnk'}, '/Users/bove/Dropbox/Projects/2016/Hill/Input/BOS_0099_no-sharpen.tif': {'type': 'media'}, '/Users/bove/MATERIAL/WORK/RnD/DATA/0002_Snow.lnk': {'type': 'lnk'}, '/Users/bove/MATERIAL/DELIVERY/DI/RnD/exr/RENDER_0009/RENDER_0009_%06d.exr': {'Start frame': 0, 'type': 'media', 'End frame': 249}, '/Users/bove/MATERIAL/DELIVERY/DI/RnD/js/RENDER_0007/RENDER_0007.js': {'type': 'media'}, '/Users/bove/MATERIAL/WORK/RnD/DATA/hair02.lnk': {'type': 'lnk'}, '/Users/bove/MATERIAL/WORK/RnD/DATA/BOS_0099_no-sharpen.lnk': {'type': 'lnk'}, '/Users/bove/MATERIAL/WORK/RnD/DATA/RENDER/hill_0003/hill_0003_blue_summer_skies_by_perbear42-d3loh0v.clp': {'type': 'lnk'}, '/Users/bove/Dropbox/Projects/2016/Hill/Input/blue_summer_skies_by_perbear42-d3loh0v.jpg': {'type': 'media'}, '/Users/bove/Dropbox/Projects/2016/Hill/Work/hill_0004/hill_0004_%06d.tif': {'Start frame': 0, 'type': 'media', 'End frame': 249}, '/Users/bove/Dropbox/Projects/2016/Hill/Input/Trek_Bicycle_Corporation_logo.svg.png': {'type': 'media'}, '/Users/bove/MATERIAL/WORK/RnD/DATA/RENDER/RENDER_0009/RENDER_0009_hill9.clp': {'type': 'lnk'}, '/Users/bove/MATERIAL/WORK/RnD/DATA/RENDER/RENDER_0007/RENDER_0007_BOS_0099_no-sharpen.clp': {'type': 'lnk'}, '/Users/bove/MATERIAL/WORK/RnD/DATA/blue_summer_skies_by_perbear42-d3loh0v.lnk': {'type': 'lnk'}, 'RnD/PRIVATE/006hill14_env_003e9a00.dat': {'type': 'dat'}, '/Users/bove/Dropbox/Projects/2016/Hill/Input/Snow/0002_Snow.mov': {'type': 'media'}, 'RnD/PRIVATE/006hill14_env_001ed300.dat': {'type': 'dat'}}
        self.assertEqual(stack.dependencies_detailed, correct_dependencies)

if __name__ == '__main__':
    unittest.main()