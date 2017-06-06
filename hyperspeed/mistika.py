#!/usr/bin/env python

import os
import re

from xml.etree import ElementTree
from distutils.version import LooseVersion

def get_mistikarc_path(env_folder):
    mistikarc_paths = [
    env_folder + '/.mistikarc',
    env_folder + '/mistikarc.cfg',
    env_folder + '/.mambarc',
    ]
    while len(mistikarc_paths) > 0 and not os.path.exists(mistikarc_paths[0]):
        del mistikarc_paths[0]
    if len(mistikarc_paths) == 0:
        print 'Error: mistikarc config not found in %s' % env_folder
        return False
    return mistikarc_paths[0]

def get_current_project(shared_folder, user):
    project = None
    latest_project_time = 0
    for line in open(os.path.join(shared_folder, "users/%s/projects.cfg" % user)).readlines():
        try:
            project_name, project_time = line.split()
            if project_time > latest_project_time:
                latest_project_time = project_time
                project = project_name
        except:
            pass
    return project

def reload():
    global env_folder, tools_path, shared_folder, version, project, user, settings, product
    global afterscripts_path
    global scripts_folder
    global glsl_folder
    env_folder = os.path.realpath(os.path.expanduser("~/MISTIKA-ENV"))
    if os.path.exists(env_folder):
        product = 'Mistika'
    else:
        env_folder = os.path.realpath(os.path.expanduser("~/MAMBA-ENV"))
        if os.path.exists(env_folder):
            product = 'Mamba'
        else:
            product = False
    shared_folder = os.path.expanduser("~/MISTIKA-SHARED")
    version = LooseVersion('.'.join(re.findall(r'\d+', os.path.basename(env_folder))[:3]))
    try:
        version.vstring
    except AttributeError:
        version = LooseVersion('0')

    if version < LooseVersion('8.6'):
        project = open(os.path.join(env_folder, '%s_PRJ' % product.upper())).readline().splitlines()[0]
        user = False
    else:
        try:
            user = ElementTree.parse(os.path.join(shared_folder, "users/login.xml")).getroot().find('autoLogin/lastUser').text
        except:
            user = 'MistikaUser'
        project = get_current_project(shared_folder, user)
    mistikarc_path = get_mistikarc_path(env_folder)
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
    tools_path = os.path.join(shared_folder, 'config/LinuxMistikaTools')
    afterscripts_path = os.path.join(env_folder, 'etc/setup/RenderEndScript.cfg')
    if not os.path.isfile(afterscripts_path):
        try:
            open(afterscripts_path, 'a').write('None')
        except OSError:
            print 'Afterscripts config not available: %s' % afterscripts_path
    scripts_folder = os.path.join(env_folder, 'bin/scripts/')
    if not os.path.exists(scripts_folder):
        bin_folder_mac = '/Applications/SGOMambaFX.app/Contents/MacOS/'
        scripts_folder_mac = '/Applications/SGOMambaFX.app/Contents/MacOS/scripts/'
        if os.path.exists(bin_folder_mac):
            scripts_folder = scripts_folder_mac
    glsl_folder = os.path.join(env_folder, 'etc/GLSL')

reload()