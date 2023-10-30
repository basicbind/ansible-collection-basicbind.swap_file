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
            - 'By default the module uses dd to create the swap file on
              all filesystems except btrfs, where it uses the btrfs
              command. You can override this behaviour by choosing the
              command with this option.'
            - 'fallocate is faster but "Preallocated files created by
              fallocate(1) may be interpreted as files with holes too
              depending of the filesystem." which would cause swapon
              to fail. man swapon'
            - 'If you choose either "dd" or "fallocate" when creating
              a swap file on btrfs you will also need to have the "chattr"
              utility installed on the target system.'
        required: false
        type: str
        choices: [ dd, fallocate ]
        default: null
notes:
    - The swap file is first created temporarily in the same directory
      it will live, with the name prefix ".ansible_swap_file". This
      file will normally be removed if a failure occurs or when it
      is moved into place.
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

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.common.text import formatters, converters
import os
import tempfile

class SwapFileModule():
    
    _PRIORITY_MIN = -1
    _PRIORITY_MAX = 32767
    _SIZE_DEFAULT_UNIT = 'G'
    _TMP_SWAP_FILE_PREFIX = '.ansible_swap_file'

    def __init__(self, module):
        self.changed = False
        self.module = module
        self.path = module.params['path']
        self.priority = module.params['priority']
        self.state = module.params['state']
        self.size = module.params['size']
        self.create_cmd = module.params.get('create_cmd', None)


    @property
    def path(self):
        """Returns the _path attribute"""
        return self._path
    

    @path.setter
    def path(self, path):
        """Sets the _path attribute and validates it"""
        # We verify that the path is an absolute path and that if the 
        # swap file path exists, it is a regular file
        if os.path.isabs(path):
            path = os.path.realpath(path)
            if os.path.exists(path) and not os.path.isfile(path):
                self.fail('%s exists but is not a regular file' % path)
            else:
                self._path = path
        else:
            self.fail('Path must be an absolute path')


    @property
    def priority(self):
        """Returns the _priority attribute"""
        return self._priority


    @priority.setter
    def priority(self, priority):
        """Sets the _priority attribute and validates it"""
        priority = int(priority)
        if (priority >= self._PRIORITY_MIN and priority <= self._PRIORITY_MAX):
            self._priority = priority
        else:
            self.fail('priority is not between %s and %s'
                      % (self._PRIORITY_MIN, self._PRIORITY_MAX))


    @property
    def size(self):
        """Returns the _size attribute"""
        return self._size


    @size.setter
    def size(self, size):
        """Sets the _size attribute and validates it"""
        size_in_m = None
        size_in_bytes = None

        if size is not None or self.state == 'present':
            try:
                size_in_bytes = formatters.human_to_bytes(size,
                                                                default_unit=self._SIZE_DEFAULT_UNIT,
                                                                isbits=False)

            except ValueError as e:
                self.fail(converters.to_text(e))
            else:
                # We ensure the size is a multiple of 1Mebibyte
                MB = 1024*1024

                size_in_m = int(round(size_in_bytes/MB))
                size_in_bytes = int(size_in_m * MB)

        self._size = size
        self._size_in_m = size_in_m
        self._size_in_bytes = size_in_bytes
            
    @property
    def create_cmd(self):
        return self._create_cmd

    
    @create_cmd.setter
    def create_cmd(self, create_cmd):
        create_cmd_opts = ['dd', 'fallocate']
        if create_cmd is not None:
            if create_cmd in create_cmd_opts:
                self._create_cmd = create_cmd
            else:
                self.fail('create_cmd must be one of [%s]' % ','.join(create_cmd_opts))
        else:
            self._create_cmd = None

    def absent(self):
        """Deactivates and removes swap file"""
        self.remove()


    def create(self):
        """Creates the swap file based on the filesystem it is being created on"""
        # We create the swap file if the file doesn't exist
        # or the size isn't correct
        if ((not self.get_status('exists'))
                or not (self.get_status('size') == self._size_in_bytes)):
            # We create the temporary swap file in the same location
            # the swap file will ultimately reside to ensure there will
            # be no changes to the file on atomic_move()
            (tmpfd, tmpfile) = tempfile.mkstemp(
                prefix=self._TMP_SWAP_FILE_PREFIX,
                dir=os.path.dirname(self.path)
            )
            self.module.add_cleanup_file(tmpfile)
            
            args_dict = dict(
                dd=dict(
                    cmd='dd',
                    opts=[
                        'if=/dev/zero',
                        'of=%s' % tmpfile,
                        'bs=1MiB',
                        'count=%s' % self._size_in_m
                    ]
                ),
                fallocate=dict(
                    cmd='fallocate',
                    opts=[
                        '--length',
                        '%sMiB' % self._size_in_m,
                        tmpfile
                    ]
                ),
                btrfs=dict(
                    cmd='btrfs',
                    opts=[
                        'filesystem',
                        'mkswapfile',
                        '--size',
                        '%sm' % self._size_in_m,
                        tmpfile
                    ]
                )
            )

            create_args_dict = args_dict['dd']
            
            #["ext4", "xfs", "btrfs"]
            fs = self.get_path_filesystem(self.path)
            
            nocow = False
            if fs == 'btrfs':
                create_args_dict = args_dict['btrfs']
                nocow = True
            
            if self.create_cmd is not None:
                create_args_dict = args_dict[self.create_cmd]

            if create_args_dict['cmd'] == 'btrfs':
                try:
                    os.close(tmpfd)
                    os.remove(tmpfile)
                except OSError as e:
                    self.fail(converters.to_text(e))
            elif nocow:
                chattr_bin = self.module.get_bin_path('chattr')
                chattr_args = [chattr_bin, '+C', tmpfile]
                rc, out, err = self.module.run_command(chattr_args)
                if rc != 0:
                    self.fail('Unable to set No_COW attribute on swap file')
            
            args = [ self.module.get_bin_path(create_args_dict['cmd']) ]
            args += create_args_dict['opts']
            
            rc, out, err = self.module.run_command(args)
            if rc == 0:
                # The create operation can succeed but still fail to
                # create a properly sized swap file. Particularly when
                # using the btrfs command. If there is not enough
                # capacity for the file, btrfs will exit cleanly but
                # create a 0 byte file. We test the size here to ensure
                # it was properly created
                if (os.path.getsize(tmpfile) == self._size_in_bytes):
                    self.swap_off()
                    self.module.atomic_move(tmpfile, self.path)
                    self.changed = True
                else:
                    msg = 'Size of temp swap file is not correct. You'
                    msg += ' must have <swap file size> of free space'
                    self.fail(msg)
            else:
                self.fail(err)


    def fail(self, msg):
        """Responsible for handling module failures"""
        fail_result = dict(
                msg=msg
        )
        self.module.fail_json(**fail_result)
   

    def get_path_filesystem(self, path):
        """Returns the type of filesystem the given path resides on"""
        stat_bin = self.module.get_bin_path('stat', required=True)
        path_dir = os.path.dirname(path)
        cmd = [
            stat_bin,
            '-f',
            '-c',
            '%T',
            path_dir
        ]
        rc, out, err = self.module.run_command(cmd)
        if rc == 0:
            return out.rstrip()
        self.fail(err)
    

    def get_status(self, opt):
        """Returns the current status of the on disk swap file"""
        default_status = dict(
            exists=False,
            is_on=False,
            priority=None,
            size=None,
            is_formatted=False
        )
        
        status = default_status[opt]
        
        # Unless the swap file exists there
        # is no status to retrieve
        if os.path.exists(self.path):
            # Determine if the swap file exists
            # If we get to this point, the file
            # must exist
            if opt == 'exists':
                    status = True
                    
            # Determine swap file size
            elif opt == 'size':
                try:
                    status = os.path.getsize(self.path)
                except OSError as e:
                    self.fail(converters.to_text(e))
                    
            # Determine if swap area is on file
            elif opt == 'is_formatted':
                blkid_bin = self.module.get_bin_path('blkid')
                blkid_args = [
                    blkid_bin,
                    '-s',
                    'TYPE',
                    '-o',
                    'value',
                    self.path
                ]
                rc, out, err = self.module.run_command(blkid_args)
                if rc != 0 and rc != 2:
                    self.fail(err)
                else:
                    if out.rstrip() == 'swap':
                        status = True
            
            # Determine if swap file is activated or its current priority
            elif opt == 'is_on' or opt == 'priority':
                swapon_bin = self.module.get_bin_path('swapon')
                swapon_args = [
                    swapon_bin,
                    '--show=NAME,PRIO',
                    '--noheadings',
                ]
                rc, out, err = self.module.run_command(swapon_args)
                if rc == 0:
                    swapon_lines = out.splitlines()
                    for swapon_line in swapon_lines:
                        (path, priority) = swapon_line.split()
                        if path == self.path:
                            if opt == 'is_on':
                                status = True
                            elif opt == 'priority':
                                status = priority

        return status


    def mkswap(self):
        """Creates a swap area on swap file"""
        mkswap_bin = self.module.get_bin_path('mkswap', required=True)
        mkswap_args = [mkswap_bin, self.path]

        if not self.get_status('is_formatted'):
            rc, out, err = self.module.run_command(mkswap_args)
        
            if rc == 0:
                self.changed = True
            else:
                self.fail(err)
    

    def present(self):
        """Ensures swap file is created and activated"""      
        self.create()
        self.mkswap()
        self.set_perms()
        self.swap_on()

    
    def remove(self):
        """Removes the swap file"""
        self.swap_off()
        # Remove swap file if it exists
        if self.get_status('exists'):
            try:
                os.unlink(self.path)
            except OSError as e:
                fail(converters(e))
            else:
                self.changed = True
                
    
    def run(self):
        if self.state == 'present':
            self.present()
        elif self.state == 'absent':
            self.absent()
        else:
            self.fail('Unimplemented state')
        
        result = dict(
            changed=self.changed,
            path=self.path,
            size=self.get_status('size'),
            priority=self.get_status('priority')
        )
        self.module.exit_json(**result)
    
    def set_perms(self):
        changed = False
        file_args = {
                'path': self.path,
                'owner': 'root',
                'group': 'root',
                'secontext': [None, None, 'swapfile_t'],
                'mode': '0600',
                'attributes': None
        }
        if self.module.set_fs_attributes_if_different(file_args, changed):
            self.changed = True

    def swap_on(self):
        """Enables swapping on swap file and ensures priority is set correctly"""
        
        is_on = self.get_status('is_on')
        current_priority = self.get_status('priority')
        requested_priority = self.priority

        # Any priority below 0 asks the system to handle
        # setting the priority. So we only change the priority
        # if the current priority and the requested priority
        # differs and either one is >= 0
        if ((not is_on) or (current_priority is None)
                        or ((int(requested_priority) != int(current_priority))
                            and (int (requested_priority) >= 0 or int(current_priority) >= 0))):
            # We could be running swapon to change the priority on a currently
            # enabled swap. If this is the case we want to swapoff first
            if (is_on):
                self.swap_off()
       
            swapon_bin = self.module.get_bin_path('swapon')
            swapon_args = [swapon_bin, '-p', str(requested_priority), self.path]

            rc, out, err = self.module.run_command(swapon_args)
            if rc == 0:
                self.changed = True
            else:
                self.fail(err)

    def swap_off(self):
        swapoff_bin = self.module.get_bin_path('swapoff')
        swapoff_args = [swapoff_bin, self.path]
        
        if self.get_status('is_on'):
            rc, out, err = self.module.run_command(swapoff_args)
            if rc == 0:
                self.changed = True
            else:
                self.fail(err)

    
def main():
   
    # The arguments which can be sent by the user
    module_args = dict(
        path=dict(type='str', required=True),
        priority=dict(type='int', required=False, default=-1),
        size=dict(type='str', required=False),
        state=dict(type='str', required=False, choices=['absent', 'present'], default='present'),
        create_cmd=dict(type='str', required=False, choices=['dd', 'fallocate'])
    )

    # TODO Support check mode
    module = AnsibleModule(
        argument_spec=module_args,
        required_if=[('state', 'present', ('size',))],
        supports_check_mode=False
    )

    swap_file = SwapFileModule(module=module)
    swap_file.run()

if __name__ == '__main__':
    main()
