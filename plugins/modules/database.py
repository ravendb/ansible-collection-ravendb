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
    - Supports creating encrypted databases by assigning a secret key (generated or user-provided) and distributing it to all cluster nodes.
    - Supports applying per-database settings (database_settings) and triggering a safe database reload so changes take effect.
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
    encrypted:
        description:
        - Create the database as encrypted.
        - When C(true), the module ensures a secret key is assigned (generated or read from file) and distributed to all cluster nodes before creation.
        - Requires C(certificate_path) to access admin endpoints.
        required: false
        default: false
        type: bool
    encryption_key:
        description:
        - Path to a file that contains the raw encryption key (plain text).
        - Mutually exclusive with C(generate_encryption_key).
        - Used only when C(encrypted=true).
        required: false
        type: str
    generate_encryption_key:
        description:
        - If C(true), asks the server to generate a new encryption key via the admin API.
        - Mutually exclusive with C(encryption_key).
        - Used only when C(encrypted=true).
        required: false
        default: false
        type: bool
    encryption_key_output_path:
        description:
        - When C(generate_encryption_key=true), write the generated key to this local file with safe permissions (0600 umask).
        - Ignored if C(generate_encryption_key=false).
        required: false
        type: str
    database_settings:
        description:
          - Dictionary of database-level settings to apply.
          - Values are normalized to strings and compared against current customized settings.
          - If differences exist, the module updates settings and toggles the database state to reload them safely.
        required: false
        type: dict
        default: {}

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

HAS_REQUESTS = True
try:
    import requests
except ImportError:
    HAS_REQUESTS = False

LIB_IMP_ERR = None
try:
    from ansible_collections.ravendb.ravendb.plugins.module_utils.common_args import ravendb_common_argument_spec
    from ravendb import DocumentStore, GetDatabaseNamesOperation
    from ravendb.serverwide.operations.common import CreateDatabaseOperation, DeleteDatabaseOperation
    from ravendb.serverwide.database_record import DatabaseRecord
    from ravendb.exceptions.raven_exceptions import RavenException
    from ravendb.serverwide.operations.configuration import GetDatabaseSettingsOperation, PutDatabaseSettingsOperation
    from ravendb.documents.operations.server_misc import ToggleDatabasesStateOperation
    from ravendb.serverwide.operations.common import GetDatabaseRecordOperation
    HAS_LIB = True
except ImportError:
    HAS_LIB = False
    LIB_IMP_ERR = traceback.format_exc()


def create_store(url, database_name, certificate_path=None, ca_cert_path=None):
    """Create and initialize a RavenDB DocumentStore with optional client and CA certificates."""
    store = DocumentStore(urls=[url])
    if certificate_path:
        store.certificate_pem_path = certificate_path
    if ca_cert_path:
        store.trust_store_path = ca_cert_path
    store.database = database_name
    store.initialize()
    return store


def get_existing_databases(store):
    """Retrieve the list of existing RavenDB databases from the server."""
    return store.maintenance.server.send(GetDatabaseNamesOperation(0, 128))


def handle_present_state(store, database_name, replication_factor, url, certificate_path, encrypted, generate_encryption_key,
                         encryption_key, encryption_key_output_path, db_settings, check_mode):
    """
    Ensure the specified database exists.
    Returns a tuple: (changed: bool, message: str)
    """
    existing_databases = get_existing_databases(store)

    if database_name not in existing_databases:
        if encrypted:
            if check_mode:
                return True, "Encrypted Database '{}' would be created.".format(database_name)

            ensure_secret_assigned(
                url=url,
                database_name=database_name,
                certificate_path=certificate_path,
                generate_encryption_key=generate_encryption_key,
                encryption_key=encryption_key,
                encryption_key_output_path=encryption_key_output_path,
                check_mode=check_mode
            )

        if check_mode:
            return True, "Database '{}' would be created.".format(database_name)

        create_database(store, database_name, replication_factor, encrypted)
        created = True
        created_msg = "Database '{}' created successfully{}.".format(database_name, " (encrypted)" if encrypted else "")

    else:
        mismatch_result = verify_encryption_or_fail(store, database_name, encrypted, check_mode)
        if mismatch_result is not None:
            return mismatch_result

        created = False
        created_msg = "Database '{}' already exists.".format(database_name)

    reconcile_result = reconcile_db_settings(store, database_name, db_settings, check_mode, created_msg)
    if reconcile_result:
        return reconcile_result

    if created:
        return True, created_msg
    return False, created_msg + " No changes."


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


def create_database(store, database_name, replication_factor, encrypted):
    """
    Create a new database on the server.
    Sets the encrypted flag if requested.
    """
    database_record = DatabaseRecord(database_name)
    if encrypted:
        database_record.encrypted = True

    create_database_operation = CreateDatabaseOperation(
        database_record=database_record,
        replication_factor=replication_factor
    )
    store.maintenance.server.send(create_database_operation)


def fetch_db_record(store, database_name):
    """
    Fetch the database record for the specified database.
    Returns a DatabaseRecord or None if not found.
    """
    return store.maintenance.server.send(GetDatabaseRecordOperation(database_name))


def verify_encryption_or_fail(store, database_name, desired_encrypted, check_mode):
    """
    Verify that the encryption status of the database matches what is requested.
    Returns None if status matches.
    Returns (False, message) in check mode if it would fail.
    Raises an Exception if mismatch is detected in normal mode.
    """
    record = fetch_db_record(store, database_name)
    if record is None:
        raise Exception("Database '{}' is listed but its record could not be fetched.".format(database_name))

    actual_flag = getattr(record, "encrypted", False)
    actual_is_encrypted = (actual_flag is True)
    desired_is_encrypted = (desired_encrypted is True)
    if (desired_is_encrypted and not actual_is_encrypted) or (not desired_is_encrypted and actual_is_encrypted):
        msg = (
            "Database '{name}' already exists but encryption status is '{actual}' while requested '{desired}'. "
            "RavenDB does not support toggling encryption on an existing database. "
            "Delete & recreate, or backup and restore with the desired key."
        ).format(
            name=database_name,
            actual=actual_flag,
            desired=desired_encrypted
        )
        if check_mode:
            return (False, "Would fail: " + msg)
        raise Exception(msg)

    return None


def reconcile_db_settings(store, database_name, db_settings, check_mode, prefix_msg):
    """
    Ensure the specified database has the desired settings.
    Return either:
      - a tuple: (changed: bool, message: str)
      - None when no settings or no diffs
    """
    if not db_settings:
        return None

    current_settings = get_current_db_settings(store, database_name)
    to_apply = diff_settings(db_settings, current_settings)

    if not to_apply:
        return None

    keys_str = ", ".join(sorted(to_apply.keys()))

    if check_mode:
        return True, "{} Would apply settings ({}) and reload.".format(prefix_msg, keys_str)

    store.maintenance.send(PutDatabaseSettingsOperation(database_name, to_apply))
    store.maintenance.server.send(ToggleDatabasesStateOperation(database_name, True))
    store.maintenance.server.send(ToggleDatabasesStateOperation(database_name, False))
    return True, "{} Applied settings ({}) and reloaded.".format(prefix_msg, keys_str)


def ensure_secret_assigned(url, database_name, certificate_path, generate_encryption_key, encryption_key, encryption_key_output_path, check_mode):
    """
    Resolve/generate encryption key and POST it.
    Returns a tuple: (changed: bool, message: str)
    """
    if check_mode:
        return True, "Would assign encryption key for database '{}'.".format(database_name)

    if generate_encryption_key:
        key = fetch_generated_secret_key(url, certificate_path)
        if encryption_key_output_path:
            write_key_safe(encryption_key_output_path, key)
    else:
        key = read_from_file(encryption_key)

    if not key:
        raise Exception("Encryption key is empty.")

    assign_secret_key(url, database_name, key, certificate_path)


def write_key_safe(path, key):
    """
    Write the key to 'path'.
    """
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    prev_umask = os.umask(0o177)

    try:
        with open(path, 'w') as f:
            f.write(key + "\n")
    finally:
        os.umask(prev_umask)


def read_from_file(path):
    """
    Read entire file and strip trailing whitespace/newlines.
    """
    with open(path, 'r') as f:
        return f.read().strip()


def fetch_generated_secret_key(base_url, cert_path):
    """
    Ask the server to generate an encryption key.
    """
    url = "{}/admin/secrets/generate".format(base_url.rstrip('/'))
    response = requests.get(
        url,
        cert=cert_path,
        verify=False
    )
    response.raise_for_status()
    return response.text.strip()


def normalize_topology_group(topology_group):
    """
    Convert topology group into a {tag: url} mapping.
    """
    if isinstance(topology_group, dict):
        return topology_group

    mapping = {}
    if isinstance(topology_group, list):
        for item in topology_group:
            if not isinstance(item, dict):
                continue

            tag = item.get("Tag") or item.get("tag")
            url = item.get("Url") or item.get("url")

            if tag and url:
                mapping[tag] = url

    return mapping


def assign_secret_key(base_url, database_name, key, cert_path):
    """
    Distribute the encryption key to ALL nodes in the cluster.
    """
    topology_url = "{}/cluster/topology".format(base_url.rstrip('/'))
    topology_response = requests.get(
        topology_url,
        cert=cert_path,
        verify=False
    )
    topology_response.raise_for_status()
    data = topology_response.json()
    topology = data.get("Topology") or data

    all_nodes = normalize_topology_group(topology.get("AllNodes", {}))
    members = normalize_topology_group(topology.get("Members", {}))
    promotables = normalize_topology_group(topology.get("Promotables", {}))
    watchers = normalize_topology_group(topology.get("Watchers", {}))

    if all_nodes:
        tags = sorted(all_nodes.keys())
    else:
        tags = sorted(set(list(members.keys()) + list(promotables.keys()) + list(watchers.keys())))

    if not tags:
        raise Exception("No nodes found in cluster topology.")

    params = [("name", database_name)]
    for t in tags:
        params.append(("node", t))

    distribute_url = "{}/admin/secrets/distribute".format(base_url.rstrip("/"))
    headers = {"Content-Type": "text/plain"}

    response = requests.post(
        distribute_url,
        params=params,
        data=key,
        headers=headers,
        cert=cert_path,
        verify=False
    )
    if response.status_code not in (200, 201, 204):
        raise Exception("Assigning encryption key failed: HTTP {} - {}".format(response.status_code, response.text))
    return {"distributed_to": tags, "status": response.status_code}


def get_current_db_settings(store, db_name):
    """
    Returns dict of customized settings
    """
    s = store.maintenance.send(GetDatabaseSettingsOperation(db_name))
    return (s.settings or {}) if s else {}


def diff_settings(desired, current):
    """
    Compare desired and current settings.
    Returns dict of settings to apply.
    """
    to_apply = {}
    for k, v in (desired or {}).items():
        dv = "" if v is None else str(v)
        cv = current.get(k)
        if cv != dv:
            to_apply[k] = dv
    return to_apply


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


def validate_encryption_params(module, desired_state, certificate_path, encrypted, encryption_key,
                               generate_encryption_key, encryption_key_output_path):
    """
    Validate parameters when creating an encrypted database.
    """
    if desired_state == 'present' and encrypted:
        if not certificate_path:
            module.fail_json(msg="encrypted=true requires certificate_path for admin endpoints.")

        if not (generate_encryption_key or encryption_key):
            module.fail_json(msg="encrypted=true requires either generate_encryption_key=true or encryption_key=<path>.")

        if generate_encryption_key and encryption_key:
            module.fail_json(msg="generate_encryption_key and encryption_key are mutually exclusive.")

        if encryption_key_output_path and not generate_encryption_key:
            module.fail_json(msg="encryption_key_output_path can only be used when generate_encryption_key=true.")

        if encryption_key:
            valid, error_msg = validate_paths(encryption_key)
            if not valid:
                module.fail_json(msg=error_msg)


def validate_database_settings(module, db_settings):
    """Validate and normalize database_settings."""
    if not isinstance(db_settings, dict):
        module.fail_json(msg="database_settings must be a dict.")
    normalized = {}
    for k, v in db_settings.items():
        if not isinstance(k, str):
            module.fail_json(msg="database_settings keys must be strings. Bad key: {!r}".format(k))
        normalized[k] = "" if v is None else str(v)
    return normalized


def main():
    module_args = ravendb_common_argument_spec()
    module_args.update(
        replication_factor=dict(type='int', default=1),
        state=dict(type='str', choices=['present', 'absent'], default='present'),
        encrypted=dict(type='bool', default=False),
        encryption_key=dict(type='str', required=False, no_log=True),
        generate_encryption_key=dict(type='bool', default=False),
        encryption_key_output_path=dict(type='str', required=False, no_log=True),
        database_settings=dict(type='dict', default={}),
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
        mutually_exclusive=[('generate_encryption_key', 'encryption_key')]
    )

    if not HAS_LIB:
        module.fail_json(
            msg=missing_required_lib("ravendb"),
            exception=LIB_IMP_ERR)

    if module.params.get('encrypted') and not HAS_REQUESTS:
        module.fail_json(msg="Python 'requests' library is required for encrypted databases. Please install it.")

    url = module.params['url']
    database_name = module.params['database_name']
    replication_factor = module.params['replication_factor']
    certificate_path = module.params.get('certificate_path')
    ca_cert_path = module.params.get('ca_cert_path')
    desired_state = module.params['state']
    encrypted = module.params['encrypted']
    encryption_key = module.params.get('encryption_key')
    generate_encryption_key = module.params.get('generate_encryption_key')
    encryption_key_output_path = module.params.get('encryption_key_output_path')
    db_settings = module.params.get('database_settings')

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

    validate_encryption_params(module, desired_state, certificate_path, encrypted, encryption_key, generate_encryption_key, encryption_key_output_path)

    settings = validate_database_settings(module, db_settings)

    try:
        store = create_store(url, database_name, certificate_path, ca_cert_path)
        check_mode = module.check_mode

        if desired_state == 'present':
            changed, message = handle_present_state(
                store, database_name, replication_factor, url, certificate_path, encrypted, generate_encryption_key,
                encryption_key, encryption_key_output_path, settings, check_mode=check_mode)
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
