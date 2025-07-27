#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = '''
---
module: database
short_description: Manage RavenDB databases
description:
    - This module allows you to create or delete a RavenDB database.
    - It supports providing a replication factor and secured connections using certificates.
    - Check mode is supported to simulate database creation or deletion without applying changes.
version_added: "1.0.0"
author: "Omer Ratsaby <omer.ratsaby@ravendb.net> (@thegoldenplatypus)"

extends_documentation_fragment:
- ravendb.ravendb.ravendb

options:
    replication_factor:
        description:
            - Number of server nodes to replicate the database to.
            - Must be a positive integer.
            - Only used when creating a database.
        required: false
        default: 1
        type: int
    state:
        description:
            - Desired state of the database.
            - If C(present), the database will be created if it does not exist.
            - If C(absent), the database will be deleted if it exists.
        required: false
        type: str
        choices:
          - present
          - absent
        default: present

seealso:
  - name: RavenDB documentation
    description: Official RavenDB documentation
    link: https://ravendb.net/docs

'''

EXAMPLES = '''
- name: Create a RavenDB database
  ravendb.ravendb.database:
    url: "http://{{ ansible_host }}:8080"
    database_name: "my_database"
    replication_factor: 3
    state: present

- name: Delete a RavenDB database
  ravendb.ravendb.database:
    url: "http://{{ ansible_host }}:8080"
    database_name: "my_database"
    state: absent

- name: Create a RavenDB database (secured server with self-signed certificates)
  become: true
  ravendb.ravendb.database:
    url: "http://{{ ansible_host }}:443"
    database_name: "my_secured_database"
    replication_factor: 1
    certificate_path: "combined_raven_cert.pem"
    ca_cert_path: "ca_certificate.pem"
    state: present

- name: Delete a RavenDB database (secured server with self-signed certificates)
  become: true
  ravendb.ravendb.database:
    url: "http://{{ ansible_host }}:443"
    database_name: "my_secured_database"
    certificate_path: "/etc/ravendb/security/combined_raven_cert.pem"
    ca_cert_path: "/etc/ravendb/security/ca_certificate.pem"
    state: absent

- name: Simulate creating a RavenDB database (check mode)
  ravendb.ravendb.database:
    url: "http://{{ ansible_host }}:8080"
    database_name: "my_database"
    replication_factor: 3
    state: present
  check_mode: yes

- name: Simulate deleting a RavenDB database (check mode)
  ravendb.ravendb.database:
    url: "http://{{ ansible_host }}:8080"
    database_name: "my_database"
    state: absent
  check_mode: yes
'''

RETURN = '''
changed:
    description: Indicates if any change was made (or would have been made in check mode).
    type: bool
    returned: always
    sample: true

msg:
    description: Human-readable message describing the result or error.
    type: str
    returned: always
    sample: Database 'my_database' created successfully.
    version_added: "1.0.0"
'''

import traceback
import os
import re
try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse
from ansible.module_utils.basic import AnsibleModule, missing_required_lib

LIB_IMP_ERR = None
try:
    from ansible_collections.ravendb.ravendb.plugins.module_utils.common_args import ravendb_common_argument_spec
    from ravendb import DocumentStore, GetDatabaseNamesOperation
    from ravendb.serverwide.operations.common import CreateDatabaseOperation, DeleteDatabaseOperation
    from ravendb.serverwide.database_record import DatabaseRecord
    from ravendb.exceptions.raven_exceptions import RavenException
    HAS_LIB = True
except ImportError:
    HAS_LIB = False
    LIB_IMP_ERR = traceback.format_exc()


def create_store(url, certificate_path, ca_cert_path):
    """Create and initialize a RavenDB DocumentStore with optional client and CA certificates."""
    store = DocumentStore(urls=[url])
    if certificate_path and ca_cert_path:
        store.certificate_pem_path = certificate_path
        store.trust_store_path = ca_cert_path
    store.initialize()
    return store


def get_existing_databases(store):
    """Retrieve the list of existing RavenDB databases from the server."""
    return store.maintenance.server.send(GetDatabaseNamesOperation(0, 128))


def handle_present_state(store, database_name, replication_factor, check_mode):
    """
    Ensure the specified database exists.

    Returns a tuple: (changed: bool, message: str)
    """
    existing_databases = get_existing_databases(store)

    if database_name in existing_databases:
        return False, "Database '{}' already exists.".format(database_name)

    if check_mode:
        return True, "Database '{}' would be created.".format(database_name)

    database_record = DatabaseRecord(database_name)
    create_database_operation = CreateDatabaseOperation(
        database_record=database_record,
        replication_factor=replication_factor
    )
    store.maintenance.server.send(create_database_operation)
    return True, "Database '{}' created successfully.".format(database_name)


def handle_absent_state(store, database_name, check_mode):
    """
    Ensure the specified database is absent.
    Returns a tuple: (changed: bool, message: str)
    """
    existing_databases = get_existing_databases(store)

    if database_name not in existing_databases:
        return False, "Database '{}' does not exist.".format(database_name)

    if check_mode:
        return True, "Database '{}' would be deleted.".format(database_name)

    delete_database_operation = DeleteDatabaseOperation(database_name)
    store.maintenance.server.send(delete_database_operation)
    return True, "Database '{}' deleted successfully.".format(database_name)


def is_valid_url(url):
    """Return True if the given URL contains a valid scheme and netloc."""
    parsed = urlparse(url)
    return all([parsed.scheme, parsed.netloc])


def is_valid_database_name(name):
    """Check if the database name is valid (letters, numbers, dashes, underscores)."""
    return bool(re.match(r"^[a-zA-Z0-9_-]+$", name))


def is_valid_replication_factor(factor):
    """Return True if replication factor is a positive integer."""
    return isinstance(factor, int) and factor > 0


def is_valid_bool(value):
    """Return True if the value is a boolean."""
    return isinstance(value, bool)


def validate_paths(*paths):
    """
    Validate that all given file paths exist on the filesystem.
    Returns a tuple: (valid: bool, error_msg: Optional[str])
    """
    for path in paths:
        if path and not os.path.isfile(path):
            return False, "Path does not exist: {}".format(path)
    return True, None


def is_valid_state(state):
    """Return True if the state is either 'present' or 'absent'."""
    return state in ['present', 'absent']


def main():
    module_args = ravendb_common_argument_spec()
    module_args.update(
        replication_factor=dict(type='int', default=1),
        state=dict(type='str', choices=['present', 'absent'], default='present')
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    if not HAS_LIB:
        module.fail_json(
            msg=missing_required_lib("ravendb"),
            exception=LIB_IMP_ERR)

    url = module.params['url']
    database_name = module.params['database_name']
    replication_factor = module.params['replication_factor']
    certificate_path = module.params.get('certificate_path')
    ca_cert_path = module.params.get('ca_cert_path')
    desired_state = module.params['state']

    if not is_valid_url(url):
        module.fail_json(msg="Invalid URL: {}".format(url))

    if not is_valid_database_name(database_name):
        module.fail_json(
            msg="Invalid database name: {}. Only letters, numbers, dashes, and underscores are allowed.".format(database_name))

    if not is_valid_replication_factor(replication_factor):
        module.fail_json(
            msg="Invalid replication factor: {}. Must be a positive integer.".format(replication_factor))

    valid, error_msg = validate_paths(certificate_path, ca_cert_path)
    if not valid:
        module.fail_json(msg=error_msg)

    if not is_valid_state(desired_state):
        module.fail_json(
            msg="Invalid state: {}. Must be 'present' or 'absent'.".format(desired_state))

    try:
        store = create_store(url, certificate_path, ca_cert_path)
        check_mode = module.check_mode

        if desired_state == 'present':
            changed, message = handle_present_state(
                store, database_name, replication_factor, check_mode)
        elif desired_state == 'absent':
            changed, message = handle_absent_state(
                store, database_name, check_mode)

        module.exit_json(changed=changed, msg=message)

    except RavenException as e:
        module.fail_json(msg="RavenDB operation failed: {}".format(str(e)))
    except Exception as e:
        module.fail_json(msg="An unexpected error occurred: {}".format(str(e)))
    finally:
        if 'store' in locals():
            store.close()


if __name__ == '__main__':
    main()
