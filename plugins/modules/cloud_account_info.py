# -*- coding: utf-8 -*-

# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = '''
---
module: cloud_account_info
short_description: Get RavenDB Cloud account info
description:
  - Retrieves account-level information from the RavenDB Cloud control-plane API.
version_added: "1.1.0"
author: "Omer Ratsaby <omer.ratsaby@ravendb.net> (@thegoldenplatypus)"

extends_documentation_fragment:
  - ravendb.ravendb.ravendb_cloud

seealso:
  - name: RavenDB Cloud documentation
    description: Official RavenDB Cloud documentation
    link: https://docs.ravendb.net/cloud
'''

EXAMPLES = '''
- name: Get RavenDB Cloud account info
  ravendb.ravendb.cloud_account_info:
    api_key: "{{ ravendb_cloud_api_key }}"
  register: result

- name: Show account domain
  ansible.builtin.debug:
    msg: "{{ result.account.domainName }}"
'''

RETURN = '''
changed:
  description: Always false; this module is read-only.
  type: bool
  returned: always
  sample: false

account:
  description: Account info dict as returned by the RavenDB Cloud API.
  type: dict
  returned: always
'''

import traceback
from ansible.module_utils.basic import AnsibleModule, missing_required_lib

LIB_ERR = None
try:
    from ansible_collections.ravendb.ravendb.plugins.module_utils.cloud.client import RavenDBCloudClient
    from ansible_collections.ravendb.ravendb.plugins.module_utils.cloud.validation import (
        validate_api_key, validate_api_url,
    )
    from ansible_collections.ravendb.ravendb.plugins.module_utils.core.validation import collect_errors
    from ansible_collections.ravendb.ravendb.plugins.module_utils.services import cloud_account_service as cas
    HAS_LIB = True
except ImportError:
    HAS_LIB = False
    LIB_ERR = traceback.format_exc()


def main():
    argument_spec = dict(
        api_key=dict(type='str', required=True, no_log=True),
        api_url=dict(type='str', required=False, default='https://api.cloud.ravendb.net'),
    )

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)

    if not HAS_LIB:
        module.fail_json(msg=missing_required_lib("requests"), exception=LIB_ERR)

    api_key = module.params['api_key']
    api_url = module.params['api_url']

    checks = [
        validate_api_key(api_key),
        validate_api_url(api_url),
    ]

    ok, err = collect_errors(*checks)
    if not ok:
        module.fail_json(msg=err)

    try:
        client = RavenDBCloudClient(api_key=api_key, api_url=api_url)
        info = cas.get_account_info(client)
        module.exit_json(changed=False, account=info)
    except Exception as e:
        module.fail_json(msg="Failed to fetch RavenDB Cloud account info: {}".format(str(e)))


if __name__ == '__main__':
    main()
