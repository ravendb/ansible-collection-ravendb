#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = '''
---
module: node
short_description: Add a RavenDB node to an existing cluster
description:
    - This module adds a RavenDB node to a cluster, either as a member or a watcher.
    - Requires specifying the leader node's URL.
    - Supports check mode to simulate the addition without applying changes.
version_added: "1.0.0"
author: "Omer Ratsaby <omer.ratsaby@ravendb.net> (@thegoldenplatypus)"

attributes:
  check_mode:
    support: full
  diff_mode:
    support: none
  idempotent:
    support: full

options:
    node:
        description:
            - Dictionary containing the node details to add.
            - Must include C(tag), C(url), and C(leader_url).
            - Optionally, set C(type) to "Watcher" to add the node as a watcher instead of a full member.
        required: true
        type: dict
requirements:
    - python >= 3.9
    - requests
    - Role ravendb.ravendb.ravendb_python_client_prerequisites must be installed before using this module.
seealso:
  - name: RavenDB documentation
    description: Official RavenDB documentation
    link: https://ravendb.net/docs
notes:
    - The node C(tag) must be an uppercase, non-empty alphanumeric string.
    - URLs must be valid HTTP or HTTPS addresses.
    - Check mode is fully supported and simulates joining the node without actually performing the action.
'''

EXAMPLES = '''
- name: Join Node B as a Watcher
  ravendb.ravendb.node:
    node:
      tag: B
      type: "Watcher"
      url: "http://192.168.118.120:8080"
      leader_url: "http://192.168.117.90:8080"

- name: Join Node C as a Member
  ravendb.ravendb.node:
    node:
      tag: C
      url: "http://192.168.118.77:8080"
      leader_url: "http://192.168.117.90:8080"

- name: Simulate adding Node D (check mode)
  ravendb.ravendb.node:
    node:
      tag: D
      url: "http://192.168.118.200:8080"
      leader_url: "http://192.168.117.90:8080"
  check_mode: yes
'''

RETURN = '''
changed:
    description: Indicates if the cluster topology was changed or would have changed (check mode).
    type: bool
    returned: always
    sample: true

msg:
    description: Human-readable message describing the result or error.
    type: str
    returned: always
    sample: Node B added to the cluster
    version_added: "1.0.0"
'''

from urllib.parse import urlparse
from ansible.module_utils.basic import AnsibleModule


def is_valid_url(url):
    """Return True if the given URL is a string with a valid HTTP or HTTPS scheme and a network location."""
    if not isinstance(url, str):
        return False
    parsed = urlparse(url)
    return all([parsed.scheme in ["http", "https"], parsed.netloc])


def is_valid_tag(tag):
    """Return True if the tag is a non-empty uppercase alphanumeric string."""
    return isinstance(tag, str) and tag.isalnum() and tag.isupper()


def add_node(node, check_mode):
    """
    Add a new node to a RavenDB cluster by making an HTTP PUT request to the leader node.

    Args:
        node (dict): Dictionary containing 'url', 'tag', 'leader_url', and 'type' fields.
        check_mode (bool): If True, simulate adding the node without making changes.

    Returns:
        dict: Result dictionary with keys 'changed', 'msg', and optionally 'error'.
    """
    import requests
    url = node.get("url")
    tag = node.get("tag")
    leader_url = node.get("leader_url")
    is_watcher = node.get("type") == "Watcher"

    if not leader_url:
        return {"changed": False, "msg": "Leader URL must be specified"}

    if not is_valid_url(leader_url):
        return {"changed": False, "msg": f"Invalid Leader URL: {leader_url}"}

    if not is_valid_tag(tag):
        return {
            "changed": False,
            "msg": "Invalid tag: Node tag must be an uppercase non-empty alphanumeric string"}

    if not is_valid_url(url):
        return {
            "changed": False,
            "msg": "Invalid URL: must be a valid HTTP(S) URL"}

    headers = {"Content-Type": "application/json"}

    if check_mode:
        return {
            "changed": True,
            "msg": f"Node {tag} would be added to the cluster"}
    try:

        add_url = f"{leader_url}/admin/cluster/node?url={url}&tag={tag}"
        if is_watcher:
            add_url += "&watcher=true"

        response = requests.put(add_url, headers=headers)
        response.raise_for_status()

    except requests.HTTPError as e:
        error_message = response.json().get(
            "Message", response.text) if response.content else str(e)
        return {
            "changed": False,
            "msg": f"Failed to add node {tag}",
            "error": error_message}

    except requests.RequestException as e:
        return {
            "changed": False,
            "msg": f"Failed to add node {tag}",
            "error": str(e)}

    return {"changed": True, "msg": f"Node {tag} added to the cluster"}


def main():
    module_args = {
        "node": {"type": "dict", "required": True},
    }

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)
    node = module.params["node"]

    try:
        changed, message = add_node(node, module.check_mode)
        module.exit_json(changed=changed, msg=message)

    except Exception as e:
        module.fail_json(msg=f"An error occurred: {str(e)}")


if __name__ == '__main__':
    main()
