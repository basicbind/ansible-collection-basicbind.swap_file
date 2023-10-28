```yaml
# Copyright: (c) 2023, basicbind <https://github.com/basicbind>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

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
                - Sets the size of the swap file in human readable form
                - 1M, 1MB, 1G, 1GB = 1 MiB and 1 GiB
                - Must not use lower case "b" in the suffix unless "b" is
                  the only suffix. In which case the size is interpreted
                  as bytes
                - If suffix is missing. size is assumed to be in GiB
                - is rounded to the nearest MiB
            required: true
            type: str
        state:
            description: Controls whether to create or remove the swap file
            required: false
            type: str
            choices: [ absent, present ]
            default: present
    author:
        - basicbind (https://github.com/basicbind)
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
