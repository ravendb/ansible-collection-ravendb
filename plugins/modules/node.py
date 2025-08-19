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
    - Supports secured clusters with HTTPS, client certificates (PEM format), and optional CA bundle for verification.
    - The module inspects cluster topology first and skips adding if the node is already present.
version_added: "1.0.0"
author: "Omer Ratsaby <omer.ratsaby@ravendb.net> (@thegoldenplatypus)"

attributes:
  check_mode:
    support: full
    description: Can run in check_mode and return changed status prediction without modifying target. If not supported, the action will be skipped.


options:
    tag:
        description:
            - The unique tag for the node (uppercase alphanumeric).
        required: true
        type: str
    type:
        description:
            - Node type. Use "Watcher" to add the node as a watcher instead of a full member.
        required: false
        type: str
        default: Member
        choices: [Member, Watcher]
    url:
        description:
            - The HTTP/HTTPS URL of the node being added.
        required: true
        type: str
    leader_url:
        description:
            - The HTTP/HTTPS URL of the cluster leader.
        required: true
        type: str
    certificate_path:
        description:
        - Path to a client certificate in PEM format (combined certificate and key).
        - Required for secured clusters (HTTPS with client authentication).
        required: false
        type: str
    ca_cert_path:
        description:
            - Path to a CA certificate bundle to verify the server certificate.
        required: false
        type: str

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
    - If the node is already part of the cluster (by tag or URL), the task is a no-op.
    - Supports both unsecured (HTTP) and secured (HTTPS) RavenDB clusters.
'''

EXAMPLES = '''
- name: Join Node B as a Watcher (HTTP, no cert)
  ravendb.ravendb.node:
    tag: B
    type: "Watcher"
    url: "http://192.168.118.120:8080"
    leader_url: "http://192.168.117.90:8080"

- name: Join Node B as Watcher (HTTPS)
  ravendb.ravendb.node:
    tag: B
    type: "Watcher"
    url: "https://b.ravendbansible.development.run"
    leader_url: "https://a.ravendbansible.development.run"
    certificate_path: /etc/ravendb/security/admin.client.combined.pem

- name: Simulate adding Node D (check mode)
  ravendb.ravendb.node:
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

import os
try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse
from ansible.module_utils.basic import AnsibleModule

HAS_REQUESTS = True
try:
    import requests
except ImportError:
    HAS_REQUESTS = False


def is_valid_url(url):
    """Return True if the given URL is a string with a valid HTTP or HTTPS scheme."""
    if not isinstance(url, str):
        return False
    parsed = urlparse(url)
    return all([parsed.scheme in ["http", "https"], parsed.netloc])


def is_valid_tag(tag):
    """Return True if the tag is a non-empty uppercase alphanumeric string of max 4 chars."""
    return isinstance(tag, str) and tag.isalnum() and tag.isupper() and 1 <= len(tag) <= 4


def validate_paths(*paths):
    """Check that all non-empty paths exist as files."""
    for p in paths:
        if p and not os.path.isfile(p):
            return False, "Path does not exist: {}".format(p)
    return True, None


def build_requests_tls_options(certificate_path, ca_cert_path):
    """
    Decide what to pass to requests for TLS.
    Returns a tuple: (cert, verify)
    """
    cert = None
    verify = True

    if certificate_path:
        cert = certificate_path
        if ca_cert_path:
            verify = ca_cert_path
        else:
            verify = False
    elif ca_cert_path:
        verify = ca_cert_path

    return cert, verify


def normalize_topology_group(topology_group):
    """
    Convert  topology group into a {tag: url} mapping.
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


def fetch_topology(leader_url, certificate_path=None, ca_cert_path=None):
    """
    Query the leader node for cluster topology and return normalized groups.
    """
    cert, verify = build_requests_tls_options(certificate_path, ca_cert_path)

    url = "{}/cluster/topology".format(leader_url.rstrip('/'))
    response = requests.get(url, cert=cert, verify=verify)
    response.raise_for_status()

    data = response.json()
    topology = data.get("Topology") or data

    return {
        "Members": normalize_topology_group(topology.get("Members", {})),
        "Watchers": normalize_topology_group(topology.get("Watchers", {})),
        "Promotables": normalize_topology_group(topology.get("Promotables", {})),
    }


def find_node_in_topology(topology, search_tag, search_url):
    """
    Return (present, role, existing_tag, existing_url) where role in {"Member","Watcher","Promotable"} or None.
    Match by tag OR by url.
    """
    roles = [
        ("Members", "Member"),
        ("Watchers", "Watcher"),
        ("Promotables", "Promotable"),
    ]
    for group_key, role_name in roles:
        group = topology.get(group_key, {}) or {}

        for tag, url in group.items():
            if tag == search_tag or url == search_url:
                return True, role_name, tag, url

    return False, None, None, None


def add_node(tag, node_type, url, leader_url, certificate_path, ca_cert_path, check_mode):
    """
    Add a new node to a RavenDB cluster by making an HTTP(S) PUT request to the leader node.
    Supports client certificate (PEM) and optional CA bundle.
    """
    is_watcher = (node_type == "Watcher")

    if not leader_url:
        return {"changed": False, "msg": "Leader URL must be specified"}

    if not is_valid_url(leader_url):
        return {"changed": False, "msg": "Invalid Leader URL: {}".format(leader_url)}

    if not is_valid_tag(tag):
        return {
            "changed": False,
            "msg": "Invalid tag: Node tag must be an uppercase non-empty alphanumeric string"
        }

    if not is_valid_url(url):
        return {"changed": False, "msg": "Invalid URL: must be a valid HTTP(S) URL"}

    valid, err = validate_paths(certificate_path, ca_cert_path)
    if not valid:
        return {"changed": False, "msg": err}

    try:
        topology = fetch_topology(leader_url, certificate_path, ca_cert_path)
        present, role, existing_tag, existing_url = find_node_in_topology(topology, tag, url)
        if present:
            return {
                "changed": False,
                "msg": "Node {} already present in the cluster as {} ({}).".format(existing_tag, role, existing_url),
            }

    except requests.RequestException:
        pass

    if check_mode:
        return {"changed": True, "msg": "Node {} would be added to the cluster as {}.".format(tag, node_type)}

    params = {"url": url, "tag": tag}
    if is_watcher:
        params["watcher"] = "true"

    endpoint = "{}/admin/cluster/node".format(leader_url.rstrip("/"))
    cert, verify = build_requests_tls_options(certificate_path, ca_cert_path)

    try:
        response = requests.put(
            endpoint,
            params=params,
            headers={"Content-Type": "application/json"},
            cert=cert,
            verify=verify,
        )
        response.raise_for_status()

    except requests.HTTPError as e:
        response = e.response
        if response is not None:
            try:
                error_message = response.json().get("Message", response.text)
            except ValueError:
                error_message = response.text
        else:
            error_message = str(e)
        return {"changed": False, "msg": "Failed to add node {}".format(tag), "error": error_message}

    except requests.RequestException as e:
        return {"changed": False, "msg": "Failed to add node {}".format(tag), "error": str(e)}

    return {"changed": True, "msg": "Node {} added to the cluster as {}.".format(tag, node_type)}


def main():
    module_args = {
        "tag": {"type": "str", "required": True},
        "type": {"type": "str", "default": "Member", "choices": ["Member", "Watcher"]},
        "url": {"type": "str", "required": True},
        "leader_url": {"type": "str", "required": True},
        "certificate_path": {"type": "str", "required": False, "default": None},
        "ca_cert_path": {"type": "str", "required": False, "default": None},
    }

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)

    if not HAS_REQUESTS:
        module.fail_json(msg="Python 'requests' library is required. Please install it.")
    try:
        result = add_node(
            tag=module.params["tag"],
            node_type=module.params["type"],
            url=module.params["url"],
            leader_url=module.params["leader_url"],
            certificate_path=module.params.get("certificate_path"),
            ca_cert_path=module.params.get("ca_cert_path"),
            check_mode=module.check_mode,
        )
        if result.get("error"):
            module.fail_json(**result)
        else:
            module.exit_json(**result)
    except Exception as e:
        module.fail_json(msg="An error occurred: {}".format(str(e)))


if __name__ == '__main__':
    main()
