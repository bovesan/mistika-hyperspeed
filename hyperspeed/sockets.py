#!/usr/bin/env python

import hyperspeed
import socket
import json
import os
import sys

path         = os.path.join(hyperspeed.config_folder, 'main.socket')
afterscripts = os.path.join(hyperspeed.config_folder, 'afterscripts.socket')

def launch(socket_path, cmd):
    # print 'socket_path: %s' % socket_path
    # print ' '.join(cmd)
    cmd[0] = os.path.abspath(cmd[0])
    if '--force-socket' in cmd:
        cmd.remove('--force-socket')
    if '--no-socket' in cmd:
        # Loop
        return
    cmd.append('--no-socket')
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(5.0)
        s.connect(socket_path)
        message = json.dumps({'launch':cmd}).encode('ascii')
        s.send(message)
        data = s.recv(1024)
        s.close()
        if data == message:
            print 'Launched via socket: %s' % ' '.join(cmd)
            sys.exit(0)
            return True
    except IOError as e:
        pass
        # print e
    return False
