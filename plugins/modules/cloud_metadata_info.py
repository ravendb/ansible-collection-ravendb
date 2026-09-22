# -*- coding: utf-8 -*-

# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = '''
---
module: cloud_metadata_info
short_description: Retrieve metadata from RavenDB Cloud
description:
  - Retrieves metadata from the RavenDB Cloud control-plane API.
  - C(query=regions) lists regions available for the given C(cloud_provider).
  - C(query=instance_types) lists instance types available for the given C(cloud_provider) and C(region).
  - C(query=release_channels) lists product release channels (no extra args required).
version_added: "1.1.0"
author: "Omer Ratsaby <omer.ratsaby@ravendb.net> (@thegoldenplatypus)"

extends_documentation_fragment:
  - ravendb.ravendb.ravendb_cloud

options:
  query:
    description:
      - Which metadata endpoint to query.
    required: true
    type: str
    choices: [regions, instance_types, release_channels]
  cloud_provider:
    description:
      - Cloud provider. Required when C(query=regions) or C(query=instance_types).
    required: false
    type: str
    choices: [aws, azure, gcp]
  region:
    description:
      - Cloud region. Required when C(query=instance_types).
    required: false
    type: str

seealso:
  - name: RavenDB Cloud documentation
    description: Official RavenDB Cloud documentation
    link: https://docs.ravendb.net/cloud
'''

EXAMPLES = '''
- name: List AWS regions
  ravendb.ravendb.cloud_metadata_info:
    api_key: "{{ ravendb_cloud_api_key }}"
    query: regions
    cloud_provider: aws

- name: List GCP instance types in us-central1
  ravendb.ravendb.cloud_metadata_info:
    api_key: "{{ ravendb_cloud_api_key }}"
    query: instance_types
    cloud_provider: gcp
    region: us-central1

- name: List release channels
  ravendb.ravendb.cloud_metadata_info:
    api_key: "{{ ravendb_cloud_api_key }}"
    query: release_channels
'''

RETURN = '''
changed:
  description: Always false; this module is read-only.
  type: bool
  returned: always
  sample: false

query:
  description: The query value echoed back from the input.
  type: str
  returned: always
  sample: regions

result:
  description: Raw response from the queried metadata endpoint. Shape varies by query.
  type: dict
  returned: always
'''

import traceback
from ansible.module_utils.basic import AnsibleModule, missing_required_lib

LIB_ERR = None
try:
    from ansible_collections.ravendb.ravendb.plugins.module_utils.cloud.client import RavenDBCloudClient
    from ansible_collections.ravendb.ravendb.plugins.module_utils.cloud.validation import (
        validate_api_key, validate_api_url, validate_cloud_provider,
    )
    from ansible_collections.ravendb.ravendb.plugins.module_utils.core.validation import collect_errors
    from ansible_collections.ravendb.ravendb.plugins.module_utils.services import cloud_metadata_service as cms
    HAS_LIB = True
except ImportError:
    HAS_LIB = False
    LIB_ERR = traceback.format_exc()


def main():
    argument_spec = dict(
        api_key=dict(type='str', required=True, no_log=True),
        api_url=dict(type='str', required=False, default='https://api.cloud.ravendb.net'),
        query=dict(type='str', required=True, choices=['regions', 'instance_types', 'release_channels']),
        cloud_provider=dict(type='str', required=False, choices=['aws', 'azure', 'gcp']),
        region=dict(type='str', required=False),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_if=[
            ('query', 'regions', ['cloud_provider']),
            ('query', 'instance_types', ['cloud_provider', 'region']),
        ],
    )

    if not HAS_LIB:
        module.fail_json(msg=missing_required_lib("requests"), exception=LIB_ERR)

    api_key = module.params['api_key']
    api_url = module.params['api_url']
    query = module.params['query']
    cloud_provider = module.params.get('cloud_provider')
    region = module.params.get('region')

    checks = [
        validate_api_key(api_key),
        validate_api_url(api_url),
    ]
    if cloud_provider is not None:
        checks.append(validate_cloud_provider(cloud_provider))

    ok, err = collect_errors(*checks)
    if not ok:
        module.fail_json(msg=err)

    if query == 'release_channels' and (cloud_provider is not None or region is not None):
        module.fail_json(msg="query=release_channels does not accept cloud_provider or region.")
    if query == 'regions' and region is not None:
        module.fail_json(msg="query=regions does not accept region (only cloud_provider).")

    try:
        client = RavenDBCloudClient(api_key=api_key, api_url=api_url)

        if query == 'regions':
            result = cms.list_regions(client, cloud_provider)
        elif query == 'instance_types':
            result = cms.list_instance_types(client, cloud_provider, region)
        else:
            result = cms.list_release_channels(client)

        module.exit_json(changed=False, query=query, result=result)
    except Exception as e:
        module.fail_json(msg="Failed to fetch RavenDB Cloud metadata ({}): {}".format(query, str(e)))


if __name__ == '__main__':
    main()
