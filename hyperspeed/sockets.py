#!/usr/bin/env python

import hyperspeed
import socket
import json
import os

path = os.path.join(hyperspeed.config_folder, 'main.socket')

def launch(cmd):
    if '--force-socket' in cmd:
        cmd.remove('--force-socket')
    if '--no-socket' in cmd:
        # Loop
        return
    cmd.append('--no-socket')
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(5.0)
        s.connect(path)
        message = json.dumps({'launch':cmd}).encode('ascii')
        s.send(message)
        data = s.recv(1024)
        s.close()
        if data == message:
            return True
    except IOError as e:
        print e
    return False
