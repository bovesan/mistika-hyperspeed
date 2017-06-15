#!/bin/env python

import os
import shutil
import sys

BACKUP_SUFFIX = '.bak'

def detect(link_target, link, copy=False):
	if copy:
		try:
			return os.path.exists(link)
		except OSError:
			return False
	else:
		try:
			return os.path.realpath(link) == os.path.realpath(link_target)
		except OSError:
			return False

def install(link_target, link, copy=False):
	if detect(link_target, link, copy):
		print 'This configuration is already installed.'
		return True
	else:
		backup_path = link+BACKUP_SUFFIX
		if copy:
			desc = '%s -> %s' % (link_target, link)
			try:
				if os.path.exists(link):
					os.rename(link, backup_path)
					print 'Moved %s to %s' % (link, backup_path)
				if os.path.isdir(link_target):
					shutil.copytree(link_target, link)
				else:
					shutil.copy2(link_target, link)
				print 'Copied item: %s' % desc
				return True
			except OSError:
				print 'Could not copy item: %s' % desc
				return False
		else:
			desc = '%s -> %s' % (link, link_target)
			try:
				if os.path.exists(link):
					os.rename(link, backup_path)
					print 'Moved %s to %s' % (link, backup_path)
				os.symlink(link_target, link)
				print 'Created link: %s' % desc
				return True
			except OSError:
				print 'Could not create link: %s' % desc
				return False

def remove(link_target, link, copy=False):
	if not detect(link_target, link, copy):
		print 'This configuration is not installed.'
		return True
	else:
		backup_path = link+BACKUP_SUFFIX
		if copy:
			try:
				os.remove(link)
				print 'Removed item: %s' % link
			except OSError:
				print 'Error: Cannot remove item: %s' % link
				return False
			if os.path.exists(backup_path):
				try:
					os.rename(backup_path, link)
					print 'Moved %s to %s' % (backup_path, link)
					return True
				except OSError:
					print 'Cannot restore backup: %s' % backup_path
					return False
		else:
			if not os.path.islink(link):
				print 'Not a link: %s' % link
				return False
			try:
				os.unlink(link)
				print 'Removed link: %s' % link
			except OSError:
				print 'Error: Cannot remove link: %s' % link
				return False
			if os.path.exists(backup_path):
				try:
					os.rename(backup_path, link)
					print 'Moved %s to %s' % (backup_path, link)
					return True
				except OSError:
					print 'Cannot restore backup: %s' % backup_path
					return False