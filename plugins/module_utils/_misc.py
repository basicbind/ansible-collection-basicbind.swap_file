# Copyright (c), Michael DeHaan <michael.dehaan@gmail.com>, 2012-2013
# Copyright (c), Toshio Kuratomi <tkuratomi@ansible.com> 2016
# Copyright (c), D.T <https://github.com/basicbind> 2023 
# Simplified BSD License (see licenses/simplified_bsd.txt or https://opensource.org/licenses/BSD-2-Clause)
# get_path_filesystem Modified from the AnsibleModule.is_special_selinux_path method
# find_mount_point is from AnsibleModule.find_mount_point

import os
from ansible.module_utils.common.text.converters import to_bytes, to_text

def find_mount_point(path):
    '''
        Takes a path and returns its mount point

    :param path: a string type with a filesystem path
    :returns: the path to the mount point as a text type
    '''

    b_path = os.path.realpath(to_bytes(os.path.expanduser(os.path.expandvars(path)), errors='surrogate_or_strict'))
    while not os.path.ismount(b_path):
        b_path = os.path.dirname(b_path)

    return to_text(b_path, errors='surrogate_or_strict')

def get_path_filesystem(path):
    """Returns the type of filesystem the given path resides on"""
    try:
        f = open('/proc/mounts', 'r')
        mount_data = f.readlines()
        f.close()
    except Exception:
        return None

    path_mount_point = find_mount_point(path)

    for line in mount_data:
        (device, mount_point, fstype, options, rest) = line.split(' ', 4)
        if to_bytes(path_mount_point) == to_bytes(mount_point):
            return fstype
    
    return None
