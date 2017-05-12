#!/bin/env python

import os
import sys

BACKUP_SUFFIX = '.bak'

def detect(link_target, link):
	try:
		if os.path.realpath(link) == os.path.realpath(link_target):
			return True
	except OSError:
		return False

def install(link_target, link):
	if detect():
		print 'This configuration is already installed.'
		sys.exit(0)
	else:
		backup_path = link+BACKUP_SUFFIX
		desc = '%s -> %s' % (link, link_target)
		try:
			os.rename(link, backup_path)
			print 'Moved %s to %s' % (link, backup_path)
			os.symlink(link_target, link)
			print 'Created link: %s' % desc
			sys.exit(0)
		except OSError:
			print 'Could not create link: %s' % desc
			sys.exit(1)

def remove(link):
	if not detect():
		print 'This configuration is not installed.'
		sys.exit(0)
	else:
		backup_path = link+BACKUP_SUFFIX
		if not os.path.islink(link):
			print 'Not a link: %s' % link
			sys.exit(1)
		if not os.path.exists(backup_path):
			print 'Backup file not found: %s' % backup_path
			print 'Aborting'
			sys.exit(1)
		try:
			os.unlink(link)
			print 'Removed link: %s' % link
		except OSError:
			print 'Error: Cannot remove link: %s' % link
			sys.exit(1)
		try:
			os.rename(backup_path, link)
			print 'Moved %s to %s' % (backup_path, link)
			sys.exit(0)
		except OSError:
			print 'Cannot restore backup: %s' % backup_path
			sys.exit(1)