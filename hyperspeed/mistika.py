#!/usr/bin/env python

import os
import re

from xml.etree import ElementTree
from distutils.version import LooseVersion

def get_mistikarc_path(mistika_env_path):
    mistikarc_paths = [
    mistika_env_path + '/.mistikarc',
    mistika_env_path + '/mistikarc.cfg',
    mistika_env_path + '/.mambarc',
    ]
    while len(mistikarc_paths) > 0 and not os.path.exists(mistikarc_paths[0]):
        del mistikarc_paths[0]
    if len(mistikarc_paths) == 0:
        print 'Error: mistikarc config not found in %s' % mistika_env_path
        return False
    return mistikarc_paths[0]

def get_current_project(shared_path, user):
    project = None
    latest_project_time = 0
    for line in open(os.path.join(shared_path, "users/%s/projects.cfg" % user)).readlines():
        try:
            project_name, project_time = line.split()
            if project_time > latest_project_time:
                latest_project_time = project_time
                project = project_name
        except:
            pass
    return project

def reload():
    global mistika_env_path, shared_path, version, project, user, settings, product
    mistika_env_path = os.path.realpath(os.path.expanduser("~/MISTIKA-ENV"))
    if os.path.exists(mistika_env_path):
        product = 'Mistika'
    else:
        mistika_env_path = os.path.realpath(os.path.expanduser("~/MAMBA-ENV"))
        if os.path.exists(mistika_env_path):
            product = 'Mamba'
        else:
            product = False
    shared_path = os.path.expanduser("~/MISTIKA-SHARED")
    version = LooseVersion('.'.join(re.findall(r'\d+', os.path.basename(mistika_env_path))[:3]))
    try:
        version.vstring
    except AttributeError:
        version = LooseVersion('0')

    if version < LooseVersion('8.6'):
        project = open(os.path.join(mistika_env_path, '%s_PRJ' % product.upper())).readline().splitlines()[0]
        user = False
    else:
        try:
            user = ElementTree.parse(os.path.join(shared_path, "users/login.xml")).getroot().find('autoLogin/lastUser').text
        except:
            user = 'MistikaUser'
        project = get_current_project(shared_path, user)
    mistikarc_path = get_mistikarc_path(mistika_env_path)
    settings = {}
    for line in open(mistikarc_path):
        if line.strip() == '':
            continue
        key, value = line.strip().split(' ', 1)
        value = value.strip()
        if value.lower() == 'true':
            value = True
        elif value.lower() == 'false':
            value = False
        settings[key] = value

reload()