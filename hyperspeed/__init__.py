#!/usr/bin/env python

import os

folder = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))
config_folder = os.path.expanduser('~/.mistika-hyperspeed/')

# unwanted_env_vars = ['LIBQUICKTIME_PLUGIN_DIR', "LD_LIBRARY_PATH"]
# for unwanted_env_var in unwanted_env_vars:
# 	if unwanted_env_var in os.environ:
# 		del os.environ[unwanted_env_var]
# 		print 'Unset: %s' % unwanted_env_var

# mydll = ctypes.CDLL('/usr/lib64/libxcb-xlib.so.0')
# handle = mydll._handle
# del mydll
# while isLoaded('/usr/lib64/libxcb-xlib.so.0'):
#     dlclose(handle)

# import ctypes
# ctypes.cdll.LoadLibrary("/lib64/libc.so.6")

# ctypes.CDLL("/usr/lib64/libxcb-xlib.so.0", mode = ctypes.RTLD_GLOBAL)
# ctypes.CDLL("/usr/lib64/libX11.so.6", mode = ctypes.RTLD_GLOBAL)
# ctypes.CDLL("/usr/lib64/libxcb.so.1", mode = ctypes.RTLD_GLOBAL)
# ctypes.CDLL("/usr/lib64/libXau.so.6", mode = ctypes.RTLD_GLOBAL)
# ctypes.CDLL("/lib64/libc.so.6", mode = ctypes.RTLD_GLOBAL)
# ctypes.CDLL("/lib64/ld-linux-x86-64.so.2", mode = ctypes.RTLD_GLOBAL)
# ctypes.CDLL("/lib64/libc.so.6", mode = ctypes.RTLD_GLOBAL)


