#!/usr/bin/env python

import re

class Title(object):
    def __init__(self, path):
        self.path = path
        self._fonts = False
        self._string = False
    def __str__(self):
        return self.name
    def __repr__(self):
        return self.name

    @property
    def fonts(self):
        if not self._fonts:
            self.parse_font_dat()
        return self._fonts
    @property
    def string(self):
        if not self._string:
            self.parse_font_dat()
        return self._string
    def parse_font_dat(self):
        self._fonts = []
        float_pattern = '[+-]?[0-9]+\.[0-9]+'
        string = ''
        char_line = 9999
        char = {}
        italic = False
        try:
            for line in open(self.path):
                stripped = line.strip('\n\r')
                char_line += 1
                if re.match('^'+' '.join([float_pattern] * 10)+'$', stripped): # New character: 10 floats
                    # Todo: Insert detection of slanted text here
                    char_line = 0
                    char = {}
                elif char_line == 1:
                    char['font'] = stripped
                    if not char['font'] in self._fonts:
                        self._fonts.append(char['font'])
                    if "italic" in stripped.lower() or "oblique" in stripped.lower():
                        if not italic:
                            string += '<i>'
                            italic = True
                    else:
                        if italic:
                            string += '</i>'
                            italic = False
                elif char_line == 2:
                    char['char'] = stripped
                    string += stripped
                elif char_line < 9999 and re.match('^'+' '.join([float_pattern] * 4)+'$', stripped): # New line: 4 floats
                    if string.endswith('\r\n'): # Break on double line break
                        break
                    string += '\r\n'
            if italic:
                    string += '</i>'
        except IOError:
            print 'Could not read file: %s' % self.path
            return
        self._string = string