# Copyright: (c) 2023, D.T <https://github.com/basicbind>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
```yaml
DOCUMENTATION:
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
```

```yaml
EXAMPLES:
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
```

```yaml
RETURN:
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
```
