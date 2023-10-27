swap_file
=========

Creates a swap file and adds an fstab entry for persistence

Requirements
------------

Listed in requirements.yml

Role Variables
--------------

```yaml
---
# Full path to swap file
swap_file_path: '/swapfile'

# "present" creates the swap file, "absent" removes it
swap_file_state: 'present'

# Size in human readable form as is understood by filter "human_to_bytes"
# eg: 1G, 1M. Defaults to G
swap_file_size: '1G'

# Priority for the swap file. "Higher values indicate higher priority".
swap_file_priority: -1 
```

Dependencies
------------

None

Example Playbook
----------------
```yaml
---
- hosts: servers
  vars:
    swap_file_path: '/swapfile'
    swap_file_state: 'present'
    swap_file_size: '2G'

  roles:
    - basicbind.swap_file.swap_file
```

License
-------

GPL-3.0-only

Author Information
------------------
basicbind - https://github.com/basicbind
