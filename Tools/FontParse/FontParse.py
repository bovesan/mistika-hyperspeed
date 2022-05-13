#!/usr/bin/env python
# -*- coding: utf-8 -*-

font_folders = [
	'/usr/share/fonts/',
	'/Library/Fonts/',
    '/Volumes/CENTRAL/Projects/*/Graphics/Fonts/'
    '/Volumes/mediaraid/Projects/*/IMPORT/'
]

# from: http://two.pairlist.net/pipermail/reportlab-users/2003-October/002329.html

# Spike TrueType/OpenType subsetting

# Data Type     Description
# ------------- -------------------------------------------------------------
# BYTE          8-bit unsigned integer.
# CHAR          8-bit signed integer.
# USHORT        16-bit unsigned integer.
# SHORT         16-bit signed integer.
# ULONG         32-bit unsigned integer.
# LONG          32-bit signed integer.
# Fixed         32-bit signed fixed-point number (16.16)
# FUNIT         Smallest measurable distance in the em space.
# F2DOT14       16-bit signed fixed number with the low 14 bits of fraction (2.14).
# LONGDATETIME  Date represented in number of seconds since 12:00 midnight, January 1, 1904. The value is represented as a signed 64-bit integer.
# Tag           Array of four uint8s (length = 32 bits) used to identify a script, language system, feature, or baseline
# GlyphID       Glyph index number, same as uint16(length = 16 bits)
# Offset        Offset to a table, same as uint16 (length = 16 bits), NULL offset = 0x0000
#
# NOTE: All numbers are big-endian

# Font file begins with an offset table:
#   Fixed       sfnt version    0x00010000 for TrueType outlines, 'OTTO' for OpenType with CFF outlines (not relevant here)
#   USHORT      numTables       number of tables
#   USHORT      searchRange     16 * max(2^n <= numTables)
#   USHORT      entrySelector   max(n: 2^n <= numTables)
#   USHORT      rangeShift      numTables * 16 - searchRange
#   ------------------------------ (12 bytes)
# Table directory follows.  Each entry is 12 bytes.  Entries are sorted by
# tag in lexicographical order.  Offsets are from the start of the font file.
# Entry format:
#   ULONG       tag             4-byte identifier
#   ULONG       checkSum        CheckSum for this table
#   ULONG       offset          Offset from beginning of font file
#   ULONG       length          length of this table

# Checksum calculation:
#   ULONG
#   CalcTableChecksum(ULONG *Table, ULONG Length)
#   {
#   ULONG Sum = 0L;
#   ULONG *Endptr = Table+((Length+3) & ~3) / sizeof(ULONG);
#
#   while (Table < EndPtr)
#       Sum += *Table++;
#       return Sum;
#   }
#
# Note: This function implies that the length of a table must be a multiple of
# four bytes. In fact, a font is not considered structurally proper without the
# correct padding. All tables must begin on four byte boundries, and any
# remaining space between tables is padded with zeros. The length of all tables
# should be recorded in the table directory with their actual length (not their
# padded length).

import os
from glob import glob

output_paths = [
'~/MAMBA-ENV/extern/.fontParseOut',
'~/MISTIKA-ENV/extern/.fontParseOut',
'/home/mistika/SGO AppData/localshared/extern/.fontParseOut',
'/home/mistika/SGO AppData/localshared/extern/fonts.cfg',
]
FontParseBins = [
	'/home/mistika/MISTIKA-ENV/bin/FontParse',
	'/home/mistika/SGO Apps/Mistika Ultima/bin/FontParse'
]
for FontParseBinCandidate in FontParseBins:
  if os.path.exists(FontParseBinCandidate):
    FontParseBin = FontParseBinCandidate
    break

ttf_tables = {
# Required Tables
    'cmap': "Character to glyph mapping",
    'head': "Font header",
    'hhea': "Horizontal header",
    'hmtx': "Horizontal metrics",
    'maxp': "Maximum profile",
    'name': "Naming table",
    'OS/2': "OS/2 and Windows specific metrics",
    'post': "PostScript information",
# Tables Related to TrueType Outlines
    'cvt ': "Control Value Table",
    'fpgm': "Font program",
    'glyf': "Glyph data",
    'loca': "Index to location",
    'prep': "CVT program",
# Tables Related to PostScript Outlines
    'CFF ': "PostScript font program (compact font format)",
# Obsolete Multiple Master support
    'fvar': "obsolete",
    'MMSD': "obsolete",
    'MMFX': "obsolete",
# Advanced Typographic Tables
    'BASE': 'Baseline data',
    'GDEF': 'Glyph definition data',
    'GPOS': 'Glyph positioning data',
    'GSUB': 'Glyph substitution data',
    'JSTF': 'Justification data',
# Tables Related to Bitmap Glyphs
    'EBDT': 'Embedded bitmap data',
    'EBLC': 'Embedded bitmap location data',
    'EBSC': 'Embedded bitmap scaling data',
# Other OpenType Tables
    'DSIG': 'Digital signature',
    'gasp': 'Grid-fitting/Scan-conversion',
    'hdmx': 'Horizontal device metrics',
    'kern': 'Kerning',
    'LTSH': 'Linear threshold data',
    'PCLT': 'PCL 5 data',
    'VDMX': 'Vertical device metrics',
    'vhea': 'Vertical Metrics header',
    'vmtx': 'Vertical Metrics',
    'VORG': 'Vertical Origin',
}


def sanitize(s):
    return s.replace('\x00', '')

class TTFParser:

    def __init__(self, file):
        "Creates a TrueType font file parser.  File can be a file name, or a file object."
        if type(file) == type(""):
            file = open(file, "rb")
        self.file = file
        version = self.read_ulong()
        if version == 0x4F54544F:
            pass
            #raise 'TTFError', 'OpenType fonts with PostScript outlines are not supported'
        elif version != 0x00010000:
            raise 'TTFError', 'Not a TrueType font'
        self.numTables = self.read_ushort()
        self.searchRange = self.read_ushort()
        self.entrySelector = self.read_ushort()
        self.rangeShift = self.read_ushort()

        self.table = {}
        self.tables = []
        for n in range(self.numTables):
            record = {}
            record['tag'] = self.read_tag()
            record['checkSum'] = self.read_ulong()
            record['offset'] = self.read_ulong()
            record['length'] = self.read_ulong()
            self.tables.append(record)
            self.table[record['tag']] = record

    def get_table_pos(self, tag):
        tag = (tag + "    ")[:4]
        offset = self.table[tag]['offset']
        length = self.table[tag]['length']
        return (offset, length)

    def get_table(self, tag):
        offset, length = self.get_table_pos(tag)
        self.file.seek(offset)
        return self.file.read(length)

    def tell(self):
        return self.file.tell()

    def seek(self, pos):
        self.file.seek(pos)

    def skip(self, delta):
        self.file.seek(pos, 1)

    def seek_table(self, tag, offset_in_table = 0):
        pos = self.get_table_pos(tag)[0] + offset_in_table
        self.file.seek(pos)
        return pos

    def read_tag(self):
        return self.file.read(4)

    def read_ushort(self):
        s = self.file.read(2)
        return (ord(s[0]) << 8) + ord(s[1])
        
    def read_short(self):
        us = self.read_ushort()
        if us >= 0x8000:
            return us - 0x10000
        else:
            return us
        
    def read_variable(self, length):
        return self.file.read(length)

    def read_ulong(self):
        s = self.file.read(4)
        return (ord(s[0]) << 24) + (ord(s[1]) << 16) + (ord(s[2]) << 8) + ord(s[3])

    def debug_printHeader(self):
        print "sfnt version: 1.0"
        print "numTables: %d" % self.numTables
        print "searchRange: %d" % self.searchRange
        print "entrySelector: %d" % self.entrySelector
        print "rangeShift: %d" % self.rangeShift

    def debug_printIndex(self):
        print "Tag   Offset       Length    Checksum"
        print "----  -----------  --------  ----------"
        for record in self.tables:
            print "%(tag)4s  +0x%(offset)08X  %(length)8d  0x%(checkSum)08x" % record,
            if ttf_tables.has_key(record['tag']):
                print "", ttf_tables[record['tag']],
            print

    def get_names(self):
        postScriptName = ''
        family = ''
        style = ''
        start = self.seek_table("name")
        nameFormat = self.read_ushort()
        numTables = self.read_ushort()
        nameStringOffset = self.read_ushort()
        for n in range(numTables):
            platformID = self.read_ushort()
            platformSpecificID = self.read_ushort()
            languageID = self.read_ushort()
            nameID = self.read_ushort()
            length = self.read_ushort()
            offset = self.read_ushort()
            pos = self.tell()
            self.seek(start + nameStringOffset + offset)
            name = sanitize(self.read_variable(length))
            # print nameID, name
            self.seek(pos)
            if nameID == 1:
                family = name
            if nameID == 2:
                style = name
            if nameID == 6:
                postScriptName = name
        return {
            'name': postScriptName,
            'family': family,
            'style': style,
        }

def parse(font_path):
    if font_path in postscript_names:
        name = postscript_names[font_path]
    else:
        try:
            ttf = TTFParser(font_path)
            info = ttf.get_names()
        except:
            print e
            print 'Could not parse %s. Trying the native way:' % font_path,
            output_path_temp = '/tmp/FontParseTemp.ls'
            cmd = [FontParseBin, '-f', font_path, output_path_temp]
            try:
                if os.path.isfile(output_path_temp):
                    os.remove(output_path_temp)
                print ' '.join(cmd)
                subprocess.call(cmd)
                name = open(output_path_temp).readline().strip().strip('"').split('"   "')[1]
                [family, style] = name.rsplit('-', 1)
                info = {
                    "name": name,
                    "family": family,
                    "style": style,
                }
            except:
                print 'Could not parse %s' % font_path
                return
            
    if info['name'] == '':
        name = os.path.basename(font_path)
    return info

def test():
    info = parse(os.path.join(os.path.dirname(__file__), 'Samples/27 Sans-Regular.otf'))
    assert info['name'] == '27Sans'
    assert info['family'] == '27 Sans'
    assert info['style'] == 'Regular'

if __name__ == "__main__":
    import sys, subprocess
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            ttf = TTFParser(arg)
            print ttf.get_name_PostScript()
    else:
        postscript_names = {}
        for output_path in output_paths:
            output_path = os.path.expanduser(output_path)
            if os.path.isfile(output_path):
                print 'Loading existing font list: ' + output_path
                for line in open(output_path):
                    try:
                        strings = line.strip().strip('"').split('"   "')
                        postscript_names[strings[0]] = strings[1]
                    except:
                        continue
        font_lines = {}
        font_config_lines = {}
        font_paths = []
        test()
        for font_folder in reversed(font_folders):
            print 'Searching for fonts in: ' + font_folder
            for font_folder_glob in glob(os.path.expanduser(font_folder)):
                for root, dirs, files in os.walk(font_folder_glob):
                    for basename in files:
                        if basename.startswith('.'):
                            continue
                        if basename.lower().endswith('.otf') or basename.lower().endswith('.ttf'):
                            font_path = os.path.join(root, basename)
                            font_info = parse(font_path)
                            if not font_info:
                                continue
                            name = font_info['name']
                            font_lines[name] = '"%s"   "%s"' %(font_path, name)
                            print font_lines[name]
                            font_config_lines[name] = 'p#%s f#%s [%s]' %(font_path, font_info['family'], font_info['style'])
                            print font_config_lines[name]
        output_string = ''
        for name in sorted(font_lines):
            output_string += font_lines[name] + '\n'
        output_string_cfg = ''
        for name in sorted(font_config_lines):
            output_string_cfg += font_config_lines[name] + '\n'
        for output_path in output_paths:
            output_path = os.path.expanduser(output_path)
            if os.path.isfile(output_path):
                print '\nUpdating %s ...' % output_path,
                try:
                    os.remove(output_path)
                    if output_path.endswith('.cfg'):
                        open(output_path, 'w').write(output_string_cfg)
                    else:
                        open(output_path, 'w').write(output_string)
                    success = True
                except:
                    success = False
                if success:
                    print 'SUCCESS!'
                    print('Font list was updated. Restart Mistika/Mamba if necessary.')
                else:
                    print 'UNKNOWN ERROR'


