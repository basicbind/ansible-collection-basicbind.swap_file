#!/usr/bin/python

# Copyright: (c) 2023, D.T <https://github.com/basicbind>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = r'''
---
module: swap_file
short_description: Creates a swap file
version_added: "1.0.0"
description:
    - Creates a swap file and makes it available for swapping.
    - Does not create an fstab entry for persistence.
options:
    path:
        description:
            - The absolute path of the swap file
            - Intermediate directories will not be created if they do
              not exist
        required: true
        type: str
    priority:
        description:
            - Sets the swap priority of the swap file.
            - Must be between -1 and 32767
            - -1 indicates that the system is responsible for setting the
              priority. Therefore the resulting priority could be any
              number < 0
        required: false
        type: int
        default: -1
    size:
        description:
            - required if state == present
            - Sets the size of the swap file in human readable form
            - Valid size suffixes = Y, Z, E, P, T, G, M, K, B
            - 1M/1MB = 1 Mebibyte. 1G/1GB = 1 Gibibyte
            - Must not use lower case "b" in the suffix unless "b" is
              the only suffix. In which case the size is interpreted
              as bytes
            - If suffix is missing. size is assumed to be in Gibibytes
            - Given size is rounded to the nearest MiB
        required: false
        type: str
        default: null
    state:
        description:
            - Controls whether to create or remove the swap file
        required: false
        type: str
        choices: [ absent, present ]
        default: present
    create_cmd:
        description:
            - 'By default the module does a best effort guess based on
              the filesystem and kernel version to determine if
              "fallocate" can be used to create a swap file at the
              specified path. "dd" is used if it determines that it
              cannot. You can explicitly choose the command with this
              option. Feel free to report any issues with the module
              automatically choosing or not choosing fallocate'
            - 'fallocate is faster but "Preallocated files created by
              fallocate(1) may be interpreted as files with holes too
              depending of the filesystem." which can cause swapon
              to fail. man swapon'
            - When creating a swap file on btrfs you will also need to
              have the "chattr" utility installed on the target system.'
        required: false
        type: str
        choices: [ dd, fallocate ]
        default: null
attributes:
    check_mode:
        description:
            - Can run in check_mode and return changed status
              prediction without modifying target
        support: full
notes:
    - The swap file is first created temporarily in the same directory
      it will live, with the name prefix ".ansible_swap_file". This
      file will be removed if a failure/interruption occurs or when it
      is moved into place
author:
    - D.T (https://github.com/basicbind)
'''

EXAMPLES = r'''
- name: Create a swap file 4G big
  basicbind.swap_file.swap_file:
    path: '/swapfile'
    size: '4G'

- name: Create a swap file and set the priority to 1
  basicbind.swap_file.swap_file:
    path: '/swapfile'
    size: 2G
    priority: 1

- name: Remove a swap file
  basicbind.swap_file.swap_file:
    path: /swapfile
    state: absent

- name: Use fallocate to create swap file
  basicbind.swap_file.swap_file:
    path: /swapfile
    size: 2G
    create_cmd: fallocate
'''

RETURN = r'''
path:
    description: The canonical path of the the swap file
    type: str
    returned: always
    sample: '/swapfile'
size:
    description: The size in bytes of the created swap file
    type: int
    returned: When state == present
    sample: '1073741824'
priority:
    description:
        - The priority of the swap file.
        - Will return the priority set by the system if passed "-1" for
          priority. Otherwise should be the priority passed by the user
    type: int
    returned: When state == present
    sample: -1
'''

import os
import tempfile
import errno
import signal
import sys
import platform

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.common.text import formatters, converters
from ansible.module_utils.compat.version import LooseVersion
from ansible_collections.basicbind.swap_file.plugins.module_utils._misc import get_path_filesystem

class SwapFile():

    def __init__(self, module, path):
        self._module = module
        self._path = path

    def allocate(self, size_in_mib, create_cmd=None):
        """Creates the swap file based on the filesystem it is being created on"""
        # We currently assume the file exists at the set path.
        # Since we are currently only called with a pre-existing file
        # it's fine, but this may change

        args_dict = {
            'dd': {
                'cmd': 'dd',
                'opts': [
                    'if=/dev/zero',
                    'of=%s' % self._path,
                    'bs=1MiB',
                    'count=%s' % size_in_mib
                ]
            },
            'fallocate': {
                'cmd': 'fallocate',
                'opts': [
                    '--length',
                    '%sMiB' % size_in_mib,
                    self._path
                ]
            }
        }

        create_args_dict = args_dict['dd']
 
        #["ext4", "xfs", "btrfs"]
        fs = get_path_filesystem(self._path)
        nocow = False
        kernel_loose_version = LooseVersion(platform.release())

        if fs == 'btrfs':
            if kernel_loose_version >= LooseVersion('5'):
                nocow = True
                create_args_dict = args_dict['fallocate']
            else:
                err = 'Kernel version >= 5 needed for swap file support'
                err += ' on btrfs'
                raise RuntimeError(err)
        elif fs == 'xfs':
            if kernel_loose_version >= LooseVersion('4.18'):
                create_args_dict = args_dict['fallocate']
        elif fs == 'ext4':
            # There should be support for using fallocated swap files on
            # ext4 on earlier kernel versions, but some versions around 5.7
            # to 5.8 appear to have a bug. For now we'll default to only
            # using fallocate when the kernel version is above 5.11
            if kernel_loose_version >= LooseVersion('5.11'):
                create_args_dict = args_dict['fallocate']

        if create_cmd is not None:
            create_args_dict = args_dict[create_cmd]
        
        if nocow:
            chattr_bin = self._module.get_bin_path('chattr')
            chattr_args = [chattr_bin, '+C', self._path]
            rc, out, err = self._module.run_command(chattr_args)
            if rc != 0:
                raise RuntimeError('Unable to set No_COW attribute on swap file')

        args = [ self._module.get_bin_path(create_args_dict['cmd']) ]
        args += create_args_dict['opts']

        rc, out, err = self._module.run_command(args)
        if rc == 0:
            # The create operation can succeed but still fail to
            # create a properly sized swap file. Particularly when
            # using the btrfs command. If there is not enough
            # capacity for the file, btrfs will exit cleanly but
            # create a 0 byte file. We test the size here to ensure
            # it was properly created.
            # We're no longer using the btrfs command but I see no
            # reason to remove this test 
            if os.path.getsize(self._path) == formatters.human_to_bytes('%sM' % size_in_mib):
                return
            else:
                msg = 'Size of temp swap file is not correct. You'
                msg += ' must have <swap file size> of free space'
                raise RuntimeError(msg)
        else:
            raise RuntimeError(err)


    def get_status(self, opt):
        """Returns the current status of the on disk swap file"""
        default_status = {
            'exists': False,
            'is_on': False,
            'priority': None,
            'size': None,
            'is_formatted': False
        }

        status = default_status[opt]

        # Unless the swap file exists there
        # is no status to retrieve
        if os.path.exists(self._path):
            # Determine if the swap file exists
            # If we get to this point, the file
            # must exist
            if opt == 'exists':
                status = True

            # Determine swap file size
            elif opt == 'size':
                status = os.path.getsize(self._path)

            # Determine if swap area is on file
            elif opt == 'is_formatted':
                blkid_bin = self._module.get_bin_path('blkid')
                blkid_args = [
                    blkid_bin,
                    '-s',
                    'TYPE',
                    '-o',
                    'value',
                    self._path
                ]
                rc, out, err = self._module.run_command(blkid_args)
                if rc not in [0, 2]:
                    raise RuntimeError(err)
                else:
                    if out.rstrip() == 'swap':
                        status = True

            # Determine if swap file is activated or its current priority
            elif opt == 'is_on' or opt == 'priority':
                swapon_bin = self._module.get_bin_path('swapon')
                swapon_args = [
                    swapon_bin,
                    '--show=NAME,PRIO',
                    '--noheadings',
                ]
                rc, out, err = self._module.run_command(swapon_args)
                if rc == 0:
                    swapon_lines = out.splitlines()
                    for swapon_line in swapon_lines:
                        (path, priority) = swapon_line.split()
                        if path == self._path:
                            if opt == 'is_on':
                                status = True
                            elif opt == 'priority':
                                status = priority

        return status


    def mkswap(self):
        """Creates a swap area on swap file"""
        changed = False
        mkswap_bin = self._module.get_bin_path('mkswap', required=True)
        mkswap_args = [mkswap_bin, self._path]

        if not self.get_status('is_formatted'):
            if self._module.check_mode:
                rc = 0
            else:
                rc, out, err = self._module.run_command(mkswap_args)
            if rc == 0:
                changed = True
            else:
                raise RuntimeError(err)

        return changed


    def remove(self):
        """Removes the swap file"""
        changed = False
        if self.get_status('exists'):
            if not self._module.check_mode:
                try:
                    os.unlink(self._path)
                except EnvironmentError as e:
                    # We only need to raise an exception if the error
                    # isn't a file not found error. Since we don't want
                    # the file to exist in the first place. The file
                    # would of course have had to be removed between
                    # the time we checked if it exists and us trying to
                    # remove it. 
                    if not e.errno == errno.ENOENT:
                        raise
            changed = True
        return changed


    def set_perms(self):
        changed = False
        file_args = {
            'path': self._path,
            'owner': 'root',
            'group': 'root',
            'secontext': [None, None, 'swapfile_t'],
            'mode': '0600',
            'attributes': None
        }
        changed |= self._module.set_fs_attributes_if_different(file_args, changed)

        return changed


    def swap_on(self, priority):
        """Enables swapping on swap file and ensures priority is set correctly"""
        changed = False
        is_on = self.get_status('is_on')
        current_priority = self.get_status('priority')
        requested_priority = priority

        # Any priority below 0 asks the system to handle
        # setting the priority. So we only change the priority
        # if the current priority and the requested priority
        # differs and either one is >= 0
        if ((not is_on) or (current_priority is None)
                or ((int(requested_priority) != int(current_priority))
                    and (int (requested_priority) >= 0 or int(current_priority) >= 0))):
            # We could be running swapon to change the priority on a currently
            # enabled swap. If this is the case we want to swapoff first
            if is_on:
                self.swap_off()

            swapon_bin = self._module.get_bin_path('swapon')
            swapon_args = [swapon_bin, '-p', str(requested_priority), self._path]

            if self._module.check_mode:
                rc = 0
            else:
                rc, out, err = self._module.run_command(swapon_args)
            if rc == 0:
                changed = True
            else:
                raise RuntimeError(err)

        return changed

    def swap_off(self):
        changed = False
        swapoff_bin = self._module.get_bin_path('swapoff')
        swapoff_args = [swapoff_bin, self._path]

        if self.get_status('is_on'):
            if self._module.check_mode:
                rc = 0
            else:
                rc, out, err = self._module.run_command(swapoff_args)
            if rc == 0:
                changed = True
            else:
                err_msg = 'Could not deactivate swap file. Was it'
                err_msg += ' mounted over? Is the path to it accessible?'
                err_msg += ' %s' % err
                raise RuntimeError(err_msg)

        return changed


class SwapFileModule():

    _SIZE_DEFAULT_UNIT = 'G'
    _PRIORITY_MIN = -1
    _PRIORITY_MAX = 32767
    _TMP_SWAP_FILE_PREFIX = '.ansible_swap_file'

    def __init__(self, module):
        self._changed = False
        self._module = module
        self._desired_state = module.params['state']
        self._desired_path = module.params['path']
        self._desired_size = module.params['size']
        self._desired_priority = module.params['priority']
        self._desired_create_cmd = module.params['create_cmd']
        self._swap_file = SwapFile(module=self._module, path=self._desired_path)


    @property
    def _desired_path(self):
        """Returns the _path attribute"""
        return self.__desired_path


    @_desired_path.setter
    def _desired_path(self, path):
        """Sets the _path attribute and validates it"""
        # We verify that the path is an absolute path and that if the
        # swap file path exists, it is a regular file
        if os.path.isabs(path):
            path = os.path.realpath(path)
            if os.path.exists(path) and not os.path.isfile(path):
                self._fail('%s exists but is not a regular file' % path)
            else:
                self.__desired_path = path
        else:
            self._fail('Path must be an absolute path')


    @property
    def _desired_priority(self):
        """Returns the __priority attribute"""
        return self.__desired_priority


    @_desired_priority.setter
    def _desired_priority(self, priority):
        """Sets the __priority attribute and validates it"""
        priority = int(priority)
        if (priority >= self._PRIORITY_MIN and priority <= self._PRIORITY_MAX):
            self.__desired_priority = priority
        else:
            self._fail('priority is not between %s and %s'
                        % (self._PRIORITY_MIN, self._PRIORITY_MAX))


    @property
    def _desired_size_in_mib(self):
        return self.__desired_size_in_mib


    @property
    def _desired_size_in_bytes(self):
        return self.__desired_size_in_bytes


    @property
    def _desired_size(self):
        """Returns the _size attribute"""
        return self.__desired_size


    @_desired_size.setter
    def _desired_size(self, size):
        """Sets the _size attribute and validates it"""
        size_in_mib = None
        size_in_bytes = None

        if size is not None or self._desired_state == 'present':
            try:
                size_in_bytes = formatters.human_to_bytes(
                    size,
                    default_unit=self._SIZE_DEFAULT_UNIT,
                    isbits=False
                )
            except ValueError as e:
                self._fail(converters.to_text(e))
            else:
                # We ensure the size is a multiple of 1Mebibyte
                MB = 1024*1024
                size_in_mib = int(round(size_in_bytes/MB))
                size_in_bytes = int(size_in_mib * MB)

        self.__desired_size = size
        self.__desired_size_in_mib = size_in_mib
        self.__desired_size_in_bytes = size_in_bytes


    @property
    def _desired_create_cmd(self):
        return self.__desired_create_cmd


    @_desired_create_cmd.setter
    def _desired_create_cmd(self, create_cmd):
        create_cmd_opts = ['dd', 'fallocate']
        if ((create_cmd in create_cmd_opts)
                or (create_cmd is None)):
            self.__desired_create_cmd = create_cmd
        else:
            self._fail('create_cmd must be one of [%s]' % ','.join(create_cmd_opts))


    def _absent(self):
        """Deactivates and removes swap file"""
        try:
            self._changed |= self._swap_file.swap_off()
            self._changed |= self._swap_file.remove()
        except Exception as e:
            self._fail(converters.to_text(e))


    def _fail(self, msg):
        """Responsible for handling module failures"""
        fail_result = {'msg': msg}
        self._module.fail_json(**fail_result)


    def _present(self):
        """Ensures swap file is created and activated""" 
        dir_path = os.path.dirname(self._desired_path)
        if not os.path.isdir(dir_path):
            self._fail('Directory "%s" does not exist' % dir_path)

        # If the swap file doesn't exist  or the size isn't correct
        # we create it
        if ((not self._swap_file.get_status('exists'))
                or not self._swap_file.get_status('size') == self._desired_size_in_bytes):
            if not self._module.check_mode:
                # We create the temporary swap file in the same location
                # the swap file will ultimately reside.
                try:
                    (tmpfd, tmp_swap_file_path) = tempfile.mkstemp(
                        prefix=self._TMP_SWAP_FILE_PREFIX,
                        dir=os.path.dirname(self._desired_path)
                    )
                except Exception as e:
                    self._fail(converters.to_text(e))
                try:
                    os.close(tmpfd)
                except Exception:
                    pass

                self._module.add_cleanup_file( tmp_swap_file_path)
                try:
                    tmp_swap_file = SwapFile(self._module, path=tmp_swap_file_path)
                    tmp_swap_file.allocate(
                        size_in_mib=self._desired_size_in_mib,
                        create_cmd=self._desired_create_cmd
                    )
                    tmp_swap_file.mkswap()
                    tmp_swap_file.swap_on(priority=self._desired_priority)
                    tmp_swap_file.swap_off()
                except Exception as e:
                    self._fail('Swap file creation failed: %s' % converters.to_text(e))
                try:
                    self._swap_file.swap_off()
                except Exception as e:
                    self._fail(converters.to_text(e))

                self._module.atomic_move(tmp_swap_file_path, self._desired_path)

            self._changed = True

        try:
            self._changed |= self._swap_file.mkswap()
            self._changed |= self._swap_file.set_perms()
            self._changed |= self._swap_file.swap_on(priority=self._desired_priority)
        except Exception as e:
            self._fail(converters.to_text(e))


    def run(self):
        """Responsible for running the function responsible for each state"""
        def _sig_handler(signum, frame):
            self._module.do_cleanup_files()
            signal.signal(signum, original_sig_handlers[signum])
            # If we caught SIGINT, we should exit with SIGINT
            if signum == signal.SIGINT:
                os.kill(os.getpid(), signal.SIGINT)
            else:
                sys.exit(1)


        # Ensure we cleanup if killed/interrupted
        cleanup_sigs = [
                signal.SIGTERM,
                signal.SIGHUP,
                signal.SIGINT
        ]
        original_sig_handlers = {}
        for signum in cleanup_sigs:
            original_sig_handlers[signum] = signal.signal(signum, _sig_handler)

        if self._desired_state == 'present':
            self._present()
        elif self._desired_state == 'absent':
            self._absent()
        else:
            self._fail('Unimplemented state')

        result = {
            'changed': self._changed,
            'path': self._desired_path,
            'size': self._swap_file.get_status('size'),
            'priority': self._swap_file.get_status('priority')
        }
        self._module.exit_json(**result)


def main():

    # The arguments which can be sent by the user
    module_args = dict(
        path=dict(type='str', required=True),
        priority=dict(type='int', required=False, default=-1),
        size=dict(type='str', required=False),
        state=dict(type='str', required=False, choices=['absent', 'present'], default='present'),
        create_cmd=dict(type='str', required=False, choices=['dd', 'fallocate'])
    )

    module = AnsibleModule(
        argument_spec=module_args,
        required_if=[('state', 'present', ('size',))],
        supports_check_mode=True
    )

    swap_file = SwapFileModule(module=module)
    swap_file.run()

if __name__ == '__main__':
    main()
