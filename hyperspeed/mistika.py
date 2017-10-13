#!/usr/bin/env python

import os
import re
import subprocess
import platform as platform_module
import tempfile

from xml.etree import ElementTree
from distutils.version import LooseVersion

def get_mistika_bin_pids(parent_pid):
    cmd = ['pstree', '-p', str(parent_pid)]
    pstree = subprocess.Popen(cmd, stdout=subprocess.PIPE).communicate()[0]
    try:
        return [int(pid) for pid in re.findall('mistika.bin\((\d+)\)', pstree)]
    except AttributeError:
        return []

def get_rnd_path(rnd_name):
    for root, dirs, files in os.walk(os.path.join(projects_folder, project, 'DATA/RENDER')):
        for basename in files:
            if basename.startswith(rnd_name) and basename.endswith('.rnd'):
                return os.path.join(root, basename)
            
def get_mistikarc_path(env_folder):
    mistikarc_paths = [
    env_folder + '/mistikarc.cfg',
    env_folder + '/.mistikarc',
    env_folder + '/.mambarc',
    ]
    while len(mistikarc_paths) > 0 and not os.path.exists(mistikarc_paths[0]):
        del mistikarc_paths[0]
    if len(mistikarc_paths) == 0:
        print 'Error: mistikarc config not found in %s' % env_folder
        return False
    return mistikarc_paths[0]

def get_mistika_projects_folder(env_folder):
    product_work = '%s_WORK' % product.upper()
    for line in open(os.path.join(env_folder, product_work)):
        if line.startswith(product_work):
            return line.strip().split(' ', 1)[1].strip()

def reload():
    global env_folder, tools_path, shared_folder, version, project, user, settings, product, projects_folder
    global afterscripts_path
    global fonts_config_path
    global scripts_folder
    global glsl_folder
    global lut_folder
    global fonts
    global fonts_folder
    global platform
    env_folder = os.path.realpath(os.path.expanduser("~/MISTIKA-ENV"))
    if os.path.exists(env_folder):
        product = 'Mistika'
    else:
        env_folder = os.path.realpath(os.path.expanduser("~/MAMBA-ENV"))
        if os.path.exists(env_folder):
            product = 'Mamba'
        else:
            product = False
    if 'linux' in platform_module.system().lower():
        platform = 'linux'
        fonts_folder = '/usr/share/fonts/mistika/'
    elif 'darwin' in platform_module.system().lower():
        platform = 'mac'
        fonts_folder = os.path.expanduser('~/Library/Fonts/')
    elif 'windows' in platform_module.system().lower():
        platform = 'windows'
        fonts_folder = 'C:/Windows/Fonts/'
    shared_folder = os.path.join(env_folder, 'shared')
    try:
        version = LooseVersion('.'.join(re.findall(r'\d+',
            subprocess.Popen([product.lower(), '-V'], stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()[0].splitlines()[0])))
    except OSError:
        version = LooseVersion('.'.join(re.findall(r'\d+',
            subprocess.Popen(['/Applications/SGOMambaFX.app/Contents/MacOS/mamba', '-V'], stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()[0].splitlines()[0])))
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
        try:
            project = ElementTree.parse(os.path.join(shared_folder, "users/%s/UIvalues.xml" % user)).getroot().find('project/current').text
        except:
            project = 'None'
    mistikarc_path = get_mistikarc_path(env_folder)
    settings = {}
    for line in open(mistikarc_path):
        try:
            key, value = line.strip().split(' ', 1)
        except ValueError:
            continue
        value = value.strip()
        if value.lower() == 'true':
            value = True
        elif value.lower() == 'false':
            value = False
        settings[key] = value
    projects_folder = get_mistika_projects_folder(env_folder)
    tools_path = os.path.join(shared_folder, 'config/LinuxMistikaTools')
    afterscripts_path = os.path.join(env_folder, 'etc/setup/RenderEndScript.cfg')
    if not os.path.isfile(afterscripts_path):
        try:
            open(afterscripts_path, 'a').write('None')
        except IOError:
            print 'Afterscripts config not available: %s' % afterscripts_path
    scripts_folder = os.path.join(env_folder, 'bin/scripts/')
    if not os.path.exists(scripts_folder):
        bin_folder_mac = '/Applications/SGOMambaFX.app/Contents/MacOS/'
        scripts_folder_mac = '/Applications/SGOMambaFX.app/Contents/MacOS/scripts/'
        if os.path.exists(bin_folder_mac):
            scripts_folder = scripts_folder_mac
    glsl_folder = os.path.join(env_folder, 'etc/GLSL')
    lut_folder = os.path.join(env_folder, 'etc/LUT')
    fonts_config_path = os.path.join(env_folder, 'extern/.fontParseOut')
    fonts = {}
    try:
        for line in open(fonts_config_path):
            font_path, font_name = line.strip().strip('"').split('"   "')
            fonts[font_name] = font_path
    except IOError:
        pass
        #print 'Could not read fonts config: %s' % fonts_config_path

reload()

def set_settings(settings):
    mistika_settings_file = get_mistikarc_path(env_folder)
    with tempfile.NamedTemporaryFile(delete=False) as temp_handle:
        for line in open(mistika_settings_file):
            key = line.split()[0]
            if key in settings:
                line = key.ljust(31)+str(settings[key])+'\n'
            temp_handle.write(line)
            # print line,
        temp_handle.flush()
    os.rename(mistika_settings_file, mistika_settings_file+'.bak')
    os.rename(temp_handle.name, mistika_settings_file)
