# -*- coding: utf-8 -*-

# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = '''
---
module: cloud_node
short_description: Manage additional RavenDB Cloud product nodes (add / remove / restart)
description:
  - Manage additional nodes on a RavenDB Cloud product.
  - C(action=add) calls C(/products/additional-node/add). The Cloud API assigns the new node tag.
    Not idempotent each call adds a node.
  - C(action=remove) calls C(/products/additional-node/remove) for the given C(node_tag).
    Fails loud if the tag is not in the product's current nodeTags.
  - C(action=restart) calls C(/products/restart-node) for the given C(node_tag). Fails loud
    if the tag is not in the product's current nodeTags.
  - When C(wait=true) (the default), polls until the product status returns to C(Active).
version_added: "1.1.0"
author: "Omer Ratsaby <omer.ratsaby@ravendb.net> (@thegoldenplatypus)"

extends_documentation_fragment:
  - ravendb.ravendb.ravendb_cloud
  - ravendb.ravendb.ravendb_cloud_wait

options:
  product_id:
    description:
      - The RavenDB Cloud product id whose nodes are being managed.
    required: true
    type: str
  action:
    description:
      - Which node operation to perform.
    required: true
    type: str
    choices: [add, remove, restart]
  node_tag:
    description:
      - The node tag to operate on. Required for C(action=remove) and C(action=restart).
    required: false
    type: str

seealso:
  - name: RavenDB Cloud documentation
    description: Official RavenDB Cloud documentation
    link: https://docs.ravendb.net/cloud
'''

EXAMPLES = '''
- name: Add an additional node (default wait - up to 30 min for Active)
  ravendb.ravendb.cloud_node:
    api_key: "{{ ravendb_cloud_api_key }}"
    product_id: "abc123"
    action: add

- name: Add a node with shorter wait_timeout (give up after 5 min)
  ravendb.ravendb.cloud_node:
    api_key: "{{ ravendb_cloud_api_key }}"
    product_id: "abc123"
    action: add
    wait_timeout: 300

- name: Fire-and-forget add (return as soon as API accepts the POST)
  ravendb.ravendb.cloud_node:
    api_key: "{{ ravendb_cloud_api_key }}"
    product_id: "abc123"
    action: add
    wait: false

- name: Remove a specific node (default wait)
  ravendb.ravendb.cloud_node:
    api_key: "{{ ravendb_cloud_api_key }}"
    product_id: "abc123"
    action: remove
    node_tag: "C"

- name: Remove a node with shorter wait_timeout
  ravendb.ravendb.cloud_node:
    api_key: "{{ ravendb_cloud_api_key }}"
    product_id: "abc123"
    action: remove
    node_tag: "C"
    wait_timeout: 600

- name: Fire-and-forget remove
  ravendb.ravendb.cloud_node:
    api_key: "{{ ravendb_cloud_api_key }}"
    product_id: "abc123"
    action: remove
    node_tag: "C"
    wait: false

- name: Restart a node (default wait)
  ravendb.ravendb.cloud_node:
    api_key: "{{ ravendb_cloud_api_key }}"
    product_id: "abc123"
    action: restart
    node_tag: "B"

- name: Restart with shorter wait_timeout
  ravendb.ravendb.cloud_node:
    api_key: "{{ ravendb_cloud_api_key }}"
    product_id: "abc123"
    action: restart
    node_tag: "B"
    wait_timeout: 300

- name: Fire-and-forget restart
  ravendb.ravendb.cloud_node:
    api_key: "{{ ravendb_cloud_api_key }}"
    product_id: "abc123"
    action: restart
    node_tag: "B"
    wait: false
'''

RETURN = '''
changed:
  description: Whether a node operation was performed.
  type: bool
  returned: always

msg:
  description: Human-readable message describing the outcome.
  type: str
  returned: always

product:
  description: Full product details dict from the Cloud API after the action completes.
  type: dict
  returned: when applicable
'''

import traceback
from ansible.module_utils.basic import AnsibleModule, missing_required_lib

LIB_ERR = None
try:
    from ansible_collections.ravendb.ravendb.plugins.module_utils.cloud.client import RavenDBCloudClient
    from ansible_collections.ravendb.ravendb.plugins.module_utils.cloud.validation import (
        validate_api_key, validate_api_url, validate_product_id, validate_positive_int,
    )
    from ansible_collections.ravendb.ravendb.plugins.module_utils.core.validation import collect_errors
    from ansible_collections.ravendb.ravendb.plugins.module_utils.services import cloud_product_service as cps
    from ansible_collections.ravendb.ravendb.plugins.module_utils.services import cloud_product_lifecycle_service as cpls
    from ansible_collections.ravendb.ravendb.plugins.module_utils.services import cloud_node_service as cns
    HAS_LIB = True
except ImportError:
    HAS_LIB = False
    LIB_ERR = traceback.format_exc()


def main():
    argument_spec = dict(
        api_key=dict(type='str', required=True, no_log=True),
        api_url=dict(type='str', required=False, default='https://api.cloud.ravendb.net'),
        wait=dict(type='bool', default=True),
        wait_timeout=dict(type='int', default=1800),
        product_id=dict(type='str', required=True),
        action=dict(type='str', required=True, choices=['add', 'remove', 'restart']),
        node_tag=dict(type='str', required=False),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_if=[
            ('action', 'remove', ['node_tag']),
            ('action', 'restart', ['node_tag']),
        ],
    )

    if not HAS_LIB:
        module.fail_json(msg=missing_required_lib("requests"), exception=LIB_ERR)

    api_key = module.params['api_key']
    api_url = module.params['api_url']
    product_id = module.params['product_id']
    action = module.params['action']
    node_tag = module.params.get('node_tag')
    wait = module.params['wait']
    wait_timeout = module.params['wait_timeout']

    checks = [
        validate_api_key(api_key),
        validate_api_url(api_url),
        validate_product_id(product_id),
        validate_positive_int("wait_timeout", wait_timeout),
    ]
    ok, err = collect_errors(*checks)
    if not ok:
        module.fail_json(msg=err)

    try:
        client = RavenDBCloudClient(api_key=api_key, api_url=api_url)
        details = cps.get_product_details(client, product_id)
        current_tags = details.get("nodeTags") or []

        if action == 'add':
            if module.check_mode:
                module.exit_json(
                    changed=True,
                    msg="Would add a node to product '{}'.".format(product_id),
                    product=details,
                )
            cns.add_node(client, product_id)
            if not wait:
                module.exit_json(
                    changed=True,
                    msg="Add-node initiated on product '{}' (wait=false).".format(product_id),
                    product=details,
                )
            final = cpls.wait_for_product_status(client, product_id, "Active", wait_timeout)
            module.exit_json(
                changed=True,
                msg="Node added to product '{}'.".format(product_id),
                product=final,
            )

        if action == 'remove':
            if node_tag not in current_tags:
                module.fail_json(
                    msg="Cannot remove node '{}' on product '{}': tag not in current nodeTags {}.".format(
                        node_tag, product_id, current_tags)
                )
            if module.check_mode:
                module.exit_json(
                    changed=True,
                    msg="Would remove node '{}' from product '{}'.".format(node_tag, product_id),
                    product=details,
                )
            cns.remove_node(client, product_id, node_tag)
            if not wait:
                module.exit_json(
                    changed=True,
                    msg="Remove-node '{}' initiated on product '{}' (wait=false).".format(node_tag, product_id),
                    product=details,
                )
            final = cpls.wait_for_product_status(client, product_id, "Active", wait_timeout)
            module.exit_json(
                changed=True,
                msg="Node '{}' removed from product '{}'.".format(node_tag, product_id),
                product=final,
            )

        if action == 'restart':
            if node_tag not in current_tags:
                module.fail_json(
                    msg="Cannot restart node '{}' on product '{}': tag not in current nodeTags {}.".format(
                        node_tag, product_id, current_tags)
                )
            if module.check_mode:
                module.exit_json(
                    changed=True,
                    msg="Would restart node '{}' on product '{}'.".format(node_tag, product_id),
                    product=details,
                )
            cns.restart_node(client, product_id, node_tag)
            if not wait:
                module.exit_json(
                    changed=True,
                    msg="Restart-node '{}' initiated on product '{}' (wait=false).".format(node_tag, product_id),
                    product=details,
                )
            final = cpls.wait_for_product_status(client, product_id, "Active", wait_timeout)
            module.exit_json(
                changed=True,
                msg="Node '{}' restarted on product '{}'.".format(node_tag, product_id),
                product=final,
            )

    except Exception as e:
        module.fail_json(msg="Failed cloud_node action '{}': {}".format(action, str(e)))


if __name__ == '__main__':
    main()
