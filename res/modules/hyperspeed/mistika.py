#!/usr/bin/env python

import os
import re

from xml.etree import ElementTree
from distutils.version import LooseVersion


def get_mistikarc_path(mistika_env_path):
    mistikarc_paths = [
    mistika_env_path + '/.mistikarc',
    mistika_env_path + '/mistikarc.cfg',
    ]
    while len(mistikarc_paths) > 0 and not os.path.exists(mistikarc_paths[0]):
        del mistikarc_paths[0]
    if len(mistikarc_paths) == 0:
        print 'Error: mistikarc config not found in %s' % mistika_env_path
        return False
    return mistikarc_paths[0]

def get_current_project(mistika_shared_path, user):
    project = None
    latest_project_time = 0
    for line in open(os.path.join(mistika_shared_path, "users/%s/projects.cfg" % user)).readlines():
        try:
            project_name, project_time = line.split()
            if project_time > latest_project_time:
                latest_project_time = project_time
                project = project_name
        except:
            pass
    return project

mistika_env_path = os.path.realpath(os.path.expanduser("~/MISTIKA-ENV"))
mistika_shared_path = os.path.expanduser("~/MISTIKA-SHARED")

version = LooseVersion('.'.join(re.findall(r'\d+', os.path.basename(mistika_env_path))[:3]))

if version < LooseVersion('8.6'):
    project = open(os.path.join(mistika_env_path, '/MISTIKA_PRJ')).readline().splitlines()[0]
    user = False
else:
    try:
        user = ElementTree.parse(os.path.join(mistika_shared_path, "users/login.xml")).getroot().find('autoLogin/lastUser').text
    except:
        user = 'MistikaUser'
    project = get_current_project(mistika_shared_path, user)



mistikarc_path = get_mistikarc_path(mistika_env_path)
settings = {}
for line in open(mistikarc_path):
    if line.strip() == '':
        continue
    key, value = line.strip().split(' ', 1)
    settings[key] = value