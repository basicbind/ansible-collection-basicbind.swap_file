# Ansible Collection - basicbind.swap_file

A collection with a role and module to manage swap files

## Installation
`ansible-galaxy collection install basicbind.swap_file`

### Modules
Name | Description
--- | ---
basicbind.swap_file.swap_file | Creates a swap file and makes it available for swapping. Does not create an fstab entry for persistence

### Roles
Name | Description
--- | ---
basicbind.swap_file.swap_file | Uses the basicbind.swap_file.swap_file module to create a swap file and make it available for swapping. Also adds an fstab entry for persistence
