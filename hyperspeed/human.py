#!/usr/bin/env python

from datetime import datetime

def size(num, suffix='B'):
    for unit in ['','K','M','G','T','P','E','Z']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Y', suffix)

def reltime(d):
    if type(d) != datetime:
        d = datetime.fromtimestamp(d)
    diff = datetime.now() - d
    s = diff.seconds
    if diff.days > 7 or diff.days < 0:
        return d.strftime('%d %b %y')
    elif diff.days == 1:
        return '1 day ago'
    elif diff.days > 1:
        return '{} days ago'.format(diff.days)
    elif s <= 1:
        return 'just now'
    elif s < 60:
        return '{} seconds ago'.format(s)
    elif s < 120:
        return '1 minute ago'
    elif s < 3600:
        return '{} minutes ago'.format(s/60)
    elif s < 7200:
        return '1 hour ago'
    else:
        return '{} hours ago'.format(s/3600)
        
def time(d):
    return '%s, %s' % (datetime.fromtimestamp(d).strftime("%H:%M"), reltime(d))

def duration(s):
    parts = []
    units = [
        (1, 'second', 'seconds'),
        (60, 'minute', 'minutes'),
        (60*60, 'hour', 'hours'),
        (24*60*60, 'day', 'days'),
    ]
    while len(units) > 0:
        unit_size, unit_singular, unit_plural = units.pop()
        unit_count = s // unit_size
        if unit_size == 1:
            parts.append('%3.1f %s' % (s, unit_plural))
        elif unit_count == 1:
            parts.append('%i %s' % (unit_count, unit_singular))
        elif unit_count > 1:
            parts.append('%i %s' % (unit_count, unit_plural))
        s = s - unit_count * unit_size
    return ', '.join(parts)