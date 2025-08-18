#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = '''
---
module: index
short_description: Manage RavenDB indexes
description:
    - This module allows you to create, delete, pause, resume, enable, disable, or reset RavenDB indexes.
    - Supports check mode to simulate changes without applying them.
    - Can create dynamic single-map and multi-map indexes based on a provided index definition.
version_added: "1.0.0"
author: "Omer Ratsaby <omer.ratsaby@ravendb.net> (@thegoldenplatypus)"

extends_documentation_fragment:
- ravendb.ravendb.ravendb

options:
    url:
        description:
            - URL of the RavenDB server.
            - Must include the scheme (http or https), hostname and port.
        required: true
        type: str
    database_name:
        description:
            - Name of the database where the index resides/should be reside.
        required: true
        type: str
    index_name:
        description:
            - Name of the index to create, delete, or modify.
            - Must consist only of letters, numbers, dashes, and underscores.
        required: true
        type: str
    index_definition:
        description:
            - Dictionary defining the index (maps and optional reduce).
            - Required when creating a new index.
        required: false
        type: dict
    certificate_path:
        description:
            - Path to a client certificate (PEM format) for secured communication.
        required: false
        type: str
    ca_cert_path:
        description:
            - Path to a trusted CA certificate file to verify the RavenDB server's certificate.
        required: false
        type: str
    state:
        description:
            - Desired state of the index.
            - If C(present), the index will be created if it does not exist.
            - If C(absent), the index will be deleted if it exists.
        required: false
        type: str
        choices:
          - present
          - absent
    mode:
        description:
            - Operational mode to apply to an existing index.
        required: false
        type: str
        choices:
          - resumed
          - paused
          - enabled
          - disabled
          - reset
    cluster_wide:
        description:
            - Whether to apply enable/disable operations cluster-wide.
        required: false
        type: bool
        default: false

seealso:
    - name: RavenDB documentation
      description: Official RavenDB documentation
      link: https://ravendb.net/docs
'''

EXAMPLES = '''
- name: Create a RavenDB index with map and reduce
  ravendb.ravendb.index:
    url: "http://{{ ansible_host }}:8080"
    database_name: "my_database"
    index_name: "UsersByName"
    index_definition:
      map:
        - "from c in docs.Users select new { c.name, count = 5 }"
      reduce: >
        from result in results
        group result by result.name
        into g
        select new
        {
          name = g.Key,
          count = g.Sum(x => x.count)
        }
    state: present

- name: Create a RavenDB multi-map index
  ravendb.ravendb.index:
    url: "http://{{ ansible_host }}:8080"
    database_name: "my_database"
    index_name: "UsersAndOrdersByName"
    index_definition:
      map:
        - "from c in docs.Users select new { Name = c.name, UserCount = 1, OrderCount = 0, TotalCount = 1 }"
        - "from o in docs.Orders select new { Name = o.customer, UserCount = 0, OrderCount = 1, TotalCount = 1 }"
      reduce: >
        from result in results
        group result by result.Name
        into g
        select new
        {
          Name = g.Key,
          UserCount = g.Sum(x => x.UserCount),
          OrderCount = g.Sum(x => x.OrderCount),
          TotalCount = g.Sum(x => x.TotalCount)
        }
    state: present

- name: Delete a RavenDB index
  ravendb.ravendb.index:
    url: "http://{{ ansible_host }}:8080"
    database_name: "my_database"
    index_name: "UsersByName"
    state: absent

- name: Disable a RavenDB index (cluster-wide)
  ravendb.ravendb.index:
    url: "http://{{ ansible_host }}:8080"
    database_name: "my_database"
    index_name: "Orders/ByCompany"
    mode: disabled
    cluster_wide: true

- name: Enable a RavenDB index
  ravendb.ravendb.index:
    url: "http://{{ ansible_host }}:8080"
    database_name: "my_database"
    index_name: "Orders/ByCompany"
    mode: enabled

- name: Pause a RavenDB index
  ravendb.ravendb.index:
    url: "http://{{ ansible_host }}:8080"
    database_name: "my_database"
    index_name: "Orders/ByCompany"
    mode: paused

- name: Resume a RavenDB index
  ravendb.ravendb.index:
    url: "http://{{ ansible_host }}:8080"
    database_name: "my_database"
    index_name: "Orders/ByCompany"
    mode: resumed

- name: Reset a RavenDB index
  ravendb.ravendb.index:
    url: "http://{{ ansible_host }}:8080"
    database_name: "my_database"
    index_name: "Orders/ByCompany"
    mode: reset

- name: Update an existing RavenDB index definition
  ravendb.ravendb.index:
    url: "http://{{ ansible_host }}:8080"
    database_name: "my_database"
    index_name: "UsersByName"
    index_definition:
      map:
        - "from c in docs.Users select new { c.name, count = 13 }"
      reduce: >
        from result in results
        group result by result.name
        into g
        select new
        {
          name = g.Key,
          count = g.Sum(x => x.count)
        }
    state: present
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
    sample: Index 'Products_ByName' created successfully.
    version_added: "1.0.0"
'''

import traceback
try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse
import re
import os
import sys
from ansible.module_utils.basic import AnsibleModule, missing_required_lib

LIB_IMP_ERR = None
try:
    from ansible_collections.ravendb.ravendb.plugins.module_utils.common_args import ravendb_common_argument_spec
    from ravendb import DocumentStore, AbstractIndexCreationTask
    from ravendb.documents.indexes.abstract_index_creation_tasks import AbstractMultiMapIndexCreationTask
    from ravendb.documents.operations.indexes import (
        GetIndexesOperation,
        DeleteIndexOperation,
        EnableIndexOperation,
        DisableIndexOperation,
        StartIndexOperation,
        StopIndexOperation,
        GetIndexingStatusOperation,
        ResetIndexOperation,
        GetIndexStatisticsOperation)
    from ravendb.documents.indexes.definitions import IndexRunningStatus, IndexState
    from ravendb.exceptions.raven_exceptions import RavenException
    HAS_LIB = True
except ImportError:
    HAS_LIB = False
    LIB_IMP_ERR = traceback.format_exc()


def create_dynamic_index(name, definition):
    """Dynamically create a single-map index class based on the given definition."""
    class DynamicIndex(AbstractIndexCreationTask):
        def __init__(self):
            super(DynamicIndex, self).__init__()
            self.map = definition.get("map")[0]
            reduce_def = definition.get("reduce")
            if reduce_def:
                self.reduce = reduce_def

    DynamicIndex.__name__ = name
    return DynamicIndex


def create_dynamic_multimap_index(name, definition):
    """Dynamically create a multi-map index class based on the given definition."""
    class DynamicIndex(AbstractMultiMapIndexCreationTask):
        def __init__(self):
            super(DynamicIndex, self).__init__()
            maps_def = definition.get("map")

            for map_def in maps_def:
                self._add_map(map_def)

            reduce_def = definition.get("reduce")
            if reduce_def:
                self.reduce = reduce_def

    DynamicIndex.__name__ = name
    return DynamicIndex


def initialize_ravendb_store(params):
    """Create and initialize a RavenDB DocumentStore from Ansible module parameters."""
    url = params['url']
    database_name = params['database_name']
    certificate_path = params.get('certificate_path')
    ca_cert_path = params.get('ca_cert_path')

    store = DocumentStore(urls=[url], database=database_name)
    if certificate_path:
        store.certificate_pem_path = certificate_path
    if ca_cert_path:
        store.trust_store_path = ca_cert_path

    store.initialize()
    return store


def reconcile_state(store, params, check_mode):
    """
    Determine and apply the required state (present, absent, or mode-only) to an index.
    Returns a tuple: (status, changed, message)
    """
    database_name = params['database_name']
    index_name = params['index_name']
    desired_state = params.get('state')
    desired_mode = params.get('mode')
    cluster_wide = params['cluster_wide']

    database_maintenance = store.maintenance.for_database(database_name)
    existing_indexes = database_maintenance.send(
        GetIndexesOperation(0, sys.maxsize))
    existing_index_names = [i.name for i in existing_indexes]

    if desired_state == 'absent':
        return handle_absent_state(
            database_maintenance,
            index_name,
            existing_index_names,
            check_mode)

    if desired_state == 'present':
        return handle_present_state(
            store,
            database_name,
            params,
            index_name,
            existing_indexes,
            existing_index_names,
            check_mode)

    if desired_mode and desired_state is None:
        return handle_mode_only(
            store,
            index_name,
            desired_mode,
            cluster_wide,
            check_mode,
            existing_index_names)

    return "error", False, "Invalid state or mode combination."


def handle_absent_state(
        database_maintenance,
        index_name,
        existing_index_names,
        check_mode):
    """Delete the index if it exists. Respect Ansible check mode."""
    if index_name not in existing_index_names:
        return "ok", False, "Index '{}' is already absent.".format(index_name)

    if check_mode:
        return "ok", True, "Index '{}' would be deleted.".format(index_name)

    database_maintenance.send(DeleteIndexOperation(index_name))
    return "ok", True, "Index '{}' deleted successfully.".format(index_name)


def handle_present_state(
        store,
        database_name,
        params,
        index_name,
        existing_indexes,
        existing_index_names,
        check_mode):
    """Create or update the index if needed. Respect Ansible check mode."""
    index_definition = params.get('index_definition')
    desired_mode = params.get('mode')
    cluster_wide = params['cluster_wide']

    if index_name in existing_index_names:
        existing_index = next(
            i for i in existing_indexes if i.name == index_name)
        if index_matches(existing_index, index_definition):
            if desired_mode:
                return apply_mode(
                    store,
                    index_name,
                    desired_mode,
                    cluster_wide,
                    check_mode)
            return "ok", False, "Index '{}' already exists and matches definition.".format(index_name)

    if check_mode:
        return "ok", True, "Index '{}' would be created.".format(index_name)

    create_index(store, database_name, index_name, index_definition)
    if desired_mode:
        apply_mode(store, index_name, desired_mode, cluster_wide, check_mode)

    return "ok", True, "Index '{}' created successfully.".format(index_name)


def handle_mode_only(
        store,
        index_name,
        desired_mode,
        cluster_wide,
        check_mode,
        existing_index_names):
    """Apply only the desired index mode if the index already exists."""
    if index_name not in existing_index_names:
        return "error", False, "Index '{}' does not exist. Cannot apply mode.".format(index_name)

    return apply_mode(
        store,
        index_name,
        desired_mode,
        cluster_wide,
        check_mode)


def create_index(store, database_name, index_name, index_definition):
    """Create an index, handling both single-map and multi-map definitions."""
    if len(index_definition.get("map")) > 1:
        DynamicIndexClass = create_dynamic_multimap_index(
            index_name, index_definition)
    else:
        DynamicIndexClass = create_dynamic_index(index_name, index_definition)
    index = DynamicIndexClass()
    index.execute(store, database_name)


def index_matches(existing_index, index_definition):
    """Check if an existing index matches the expected definition (map/reduce)."""
    existing_maps = set(map(str.strip, existing_index.maps)
                        ) if existing_index.maps else set()
    existing_reduce = getattr(existing_index, 'reduce', None)

    expected_maps = set(map(str.strip, index_definition.get("map", [])))
    normalized_existing_reduce = existing_reduce.strip() if existing_reduce else None
    normalized_expected_reduce = (index_definition.get("reduce") or "").strip()
    if not normalized_expected_reduce:
        normalized_expected_reduce = None

    return existing_maps == expected_maps and normalized_existing_reduce == normalized_expected_reduce


def enable_index(store, index_name, cluster_wide, check_mode):
    """Enable a RavenDB index, optionally cluster-wide. Respect check mode."""
    current = get_index_state(store, index_name)
    if current != IndexState.DISABLED:
        return "ok", False, "Index '{}' is already enabled.".format(index_name)

    if check_mode:
        return "ok", True, "Index '{}' would be enabled{}.".format(index_name, ' cluster-wide' if cluster_wide else '')

    enable_index_operation = EnableIndexOperation(index_name, cluster_wide)
    store.maintenance.send(enable_index_operation)

    return "ok", True, "Index '{}' enabled successfully{}.".format(index_name, ' cluster-wide' if cluster_wide else '')


def disable_index(store, index_name, cluster_wide, check_mode):
    """Disable a RavenDB index, optionally cluster-wide. Respect check mode."""
    current = get_index_state(store, index_name)
    if current == IndexState.DISABLED:
        return "ok", False, "Index '{}' is already disabled.".format(index_name)

    if check_mode:
        return "ok", True, "Index '{}' would be disabled{}.".format(index_name, ' cluster-wide' if cluster_wide else '')

    disable_index_operation = DisableIndexOperation(index_name, cluster_wide)
    store.maintenance.send(disable_index_operation)

    return "ok", True, "Index '{}' disbaled successfully{}.".format(index_name, ' cluster-wide' if cluster_wide else '')


def resume_index(store, index_name, check_mode):
    """Resume a paused RavenDB index. Respect check mode."""
    indexing_status = store.maintenance.send(GetIndexingStatusOperation())
    index = [x for x in indexing_status.indexes if x.name == index_name][0]
    if index.status == IndexRunningStatus.RUNNING:
        return "ok", False, "Index '{}' is already resumed and executing.".format(index_name)

    if check_mode:
        return "ok", True, "Index '{}' would be resumed.".format(index_name)

    resume_index_operation = StartIndexOperation(index_name)
    store.maintenance.send(resume_index_operation)

    return "ok", True, "Index '{}' resumed successfully.".format(index_name)


def pause_index(store, index_name, check_mode):
    """Pause a running RavenDB index. Respect check mode."""
    indexing_status = store.maintenance.send(GetIndexingStatusOperation())
    index = [x for x in indexing_status.indexes if x.name == index_name][0]
    if index.status == IndexRunningStatus.PAUSED:
        return "ok", False, "Index '{}' is already paused.".format(index_name)

    if check_mode:
        return "ok", True, "Index '{}' would be paused.".format(index_name)

    pause_index_operation = StopIndexOperation(index_name)
    store.maintenance.send(pause_index_operation)

    return "ok", True, "Index '{}' paused successfully.".format(index_name)


def reset_index(store, index_name, check_mode):
    """Reset an existing index. Respect check mode."""
    if check_mode:
        return "ok", True, "Index '{}' would be reset.".format(index_name)

    reset_index_operation = ResetIndexOperation(index_name)
    store.maintenance.send(reset_index_operation)

    return "ok", True, "Index '{}' reset successfully.".format(index_name)


def get_index_state(store, index_name):
    """Return the logical index state"""
    stats = store.maintenance.send(GetIndexStatisticsOperation(index_name))
    return stats.state


def apply_mode(store, index_name, mode, cluster_wide, check_mode):
    """Dispatch index mode operation based on the given mode string."""
    if mode == 'enabled':
        return enable_index(store, index_name, cluster_wide, check_mode)
    elif mode == 'disabled':
        return disable_index(store, index_name, cluster_wide, check_mode)
    elif mode == 'resumed':
        return resume_index(store, index_name, check_mode)
    elif mode == 'paused':
        return pause_index(store, index_name, check_mode)
    elif mode == 'reset':
        return reset_index(store, index_name, check_mode)
    else:
        return "error", False, "Unsupported mode '{}' specified.".format(mode)


def is_valid_url(url):
    """Return True if the URL has a valid scheme and network location."""
    parsed = urlparse(url)
    return all([parsed.scheme, parsed.netloc])


def is_valid_name(name):
    """Return True if the name contains only alphanumeric characters, dashes, or underscores."""
    return bool(re.match(r"^[a-zA-Z0-9_-]+$", name))


def is_valid_dict(value):
    """Return True if the value is a dictionary or None."""
    return isinstance(value, dict) or value is None


def is_valid_bool(value):
    """Return True if the value is a boolean."""
    return isinstance(value, bool)


def validate_paths(*paths):
    """Check if all provided file paths exist. Return (True, None) or (False, error message)."""
    for path in paths:
        if path and not os.path.isfile(path):
            return False, "Path does not exist: {}".format(path)
    return True, None


def is_valid_state(state):
    """Return True if the state is one of: None, 'present', 'absent'."""
    return state in [None, 'present', 'absent']


def is_valid_mode(mode):
    """Return True if the mode is one of: None, 'resumed', 'paused', 'enabled', 'disabled', 'reset'."""
    return mode in [None, 'resumed', 'paused', 'enabled', 'disabled', 'reset']


def main():
    module_args = ravendb_common_argument_spec()
    module_args.update(
        index_name=dict(type='str', required=True),
        index_definition=dict(type='dict', required=False),
        state=dict(type='str', choices=['present', 'absent'], required=False),
        mode=dict(type='str', choices=['resumed', 'paused', 'enabled', 'disabled', 'reset'], required=False),
        cluster_wide=dict(type='bool', default=False)
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
    index_name = module.params['index_name']
    index_definition = module.params.get('index_definition')
    certificate_path = module.params.get('certificate_path')
    ca_cert_path = module.params.get('ca_cert_path')
    state = module.params.get('state')
    mode = module.params.get('mode')
    cluster_wide = module.params['cluster_wide']

    if not is_valid_url(url):
        module.fail_json(msg="Invalid URL: {}".format(url))

    if not is_valid_name(database_name):
        module.fail_json(
            msg="Invalid database name: {}. Only letters, numbers, dashes, and underscores are allowed.".format(database_name))

    if not is_valid_name(index_name):
        module.fail_json(
            msg="Invalid index name: {}. Only letters, numbers, dashes, and underscores are allowed.".format(index_name))

    if not is_valid_dict(index_definition):
        module.fail_json(
            msg="Invalid index definition: Must be a dictionary.")

    valid, error_msg = validate_paths(certificate_path, ca_cert_path)
    if not valid:
        module.fail_json(msg=error_msg)

    if not is_valid_state(state):
        module.fail_json(
            msg="Invalid state: {}. Must be 'present' or 'absent'.".format(state))

    if not is_valid_mode(mode):
        module.fail_json(
            msg="Invalid mode: {}. Must be one of 'resumed', 'paused', 'enabled', 'disabled', 'reset'.".format(mode))

    if not is_valid_bool(cluster_wide):
        module.fail_json(
            msg="Invalid cluster_wide flag: {}. Must be a boolean.".format(cluster_wide))

    try:
        store = initialize_ravendb_store(module.params)
        check_mode = module.check_mode

        type, changed, message = reconcile_state(
            store, module.params, check_mode)

        if type == "error":
            module.fail_json(changed=changed, msg=message)
        else:
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
