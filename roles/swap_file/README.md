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

# Choose between using "fallocate" and "dd" to create the swap file.
# When creating a swap file on btrfs you will also need to
# have the "chattr" utility installed on the target system.
swap_file_create_cmd: '{{ omit }}'
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

# Create a swap file using the "fallocate" command
- hosts: servers
  vars:
    swap_file_path: '/swapfile'
    swap_file_state: 'present'
    swap_file_size: '2G'
    swap_file_create_cmd: 'fallocate'
  roles:
    - basicbind.swap_file.swap_file
    
```

License
-------

GPL-3.0-only

Author Information
------------------
D.T - https://github.com/basicbind
