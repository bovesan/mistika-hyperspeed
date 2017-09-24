#!/usr/bin/env python

import os
import mistika
import manage
from stack import Stack


folder = os.getcwd()
while not 'hyperspeed-dashboard.py' in os.listdir(folder) and not folder == '/':
    folder = os.path.dirname(folder)
