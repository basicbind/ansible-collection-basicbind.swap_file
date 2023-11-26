# Copyright (c), Michael DeHaan <michael.dehaan@gmail.com>, 2012-2013
# Copyright (c), Toshio Kuratomi <tkuratomi@ansible.com> 2016
# Simplified BSD License (see licenses/simplified_bsd.txt or https://opensource.org/licenses/BSD-2-Clause)
# get_path_filesystem Modified from the AnsibleModule.is_special_selinux_path method
from __future__ import (absolute_import, division, print_function)

import os
from ansible.module_utils.common.text.converters import to_bytes, to_text

def get_path_filesystem(path):
    """Returns the type of filesystem the given path resides on"""
    try:
        f = open('/proc/mounts', 'r')
        mount_data = f.readlines()
        f.close()
    except Exception:
        return None
    
    prev_path = ''
    while path != prev_path:
        for line in mount_data:
            (device, mount_point, fstype, options, rest) = line.split(' ', 4)
            if to_bytes(path) == to_bytes(mount_point):
                return fstype
        prev_path = path
        path = os.path.dirname(path)
    return None
