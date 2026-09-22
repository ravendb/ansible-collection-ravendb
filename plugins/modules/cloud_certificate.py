# -*- coding: utf-8 -*-

# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = '''
---
module: cloud_certificate
short_description: Download a RavenDB Cloud product client certificate to a local file
description:
  - Fetches the client certificate for a RavenDB Cloud product from C(/api/v1/products/security/certificate/{id})
    and writes it to a local file at C(dest).
  - Idempotent by byte comparison if the file at C(dest) already matches the certificate returned by
    the API, no write is performed and C(changed=false).
  - The certificate is treated as sensitive its bytes are never returned in the module result.
  - The file is created with restrictive permissions (umask 0o177 -> 0o600).
version_added: "1.1.0"
author: "Omer Ratsaby <omer.ratsaby@ravendb.net> (@thegoldenplatypus)"

extends_documentation_fragment:
  - ravendb.ravendb.ravendb_cloud

options:
  product_id:
    description:
      - The RavenDB Cloud product id whose certificate should be downloaded.
    required: true
    type: str
  dest:
    description:
      - Absolute path to the local file where the certificate will be written.
    required: true
    type: path

seealso:
  - name: RavenDB Cloud documentation
    description: Official RavenDB Cloud documentation
    link: https://docs.ravendb.net/cloud
'''

EXAMPLES = '''
- name: Download RavenDB Cloud product certificate
  ravendb.ravendb.cloud_certificate:
    api_key: "{{ ravendb_cloud_api_key }}"
    product_id: "your-product-id"
    dest: "/etc/ravendb/cloud/admin.client.pfx"
'''

RETURN = '''
changed:
  description: Whether the file at C(dest) was created or updated.
  type: bool
  returned: always
  sample: true

dest:
  description: Absolute path the certificate was written to (or would have been written to in check mode).
  type: str
  returned: always

bytes_written:
  description: Size in bytes of the certificate written (or that would be written in check mode).
  type: int
  returned: always
'''

import traceback
from ansible.module_utils.basic import AnsibleModule, missing_required_lib

LIB_ERR = None
try:
    from ansible_collections.ravendb.ravendb.plugins.module_utils.cloud.client import RavenDBCloudClient
    from ansible_collections.ravendb.ravendb.plugins.module_utils.cloud.validation import (
        validate_api_key, validate_api_url, validate_product_id,
    )
    from ansible_collections.ravendb.ravendb.plugins.module_utils.core.validation import collect_errors
    from ansible_collections.ravendb.ravendb.plugins.module_utils.services import cloud_certificate_service as ccs
    HAS_LIB = True
except ImportError:
    HAS_LIB = False
    LIB_ERR = traceback.format_exc()


def main():
    argument_spec = dict(
        api_key=dict(type='str', required=True, no_log=True),
        api_url=dict(type='str', required=False, default='https://api.cloud.ravendb.net'),
        product_id=dict(type='str', required=True),
        dest=dict(type='path', required=True),
    )

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)

    if not HAS_LIB:
        module.fail_json(msg=missing_required_lib("requests"), exception=LIB_ERR)

    api_key = module.params['api_key']
    api_url = module.params['api_url']
    product_id = module.params['product_id']
    dest = module.params['dest']

    checks = [
        validate_api_key(api_key),
        validate_api_url(api_url),
        validate_product_id(product_id),
    ]

    ok, err = collect_errors(*checks)
    if not ok:
        module.fail_json(msg=err)

    try:
        client = RavenDBCloudClient(api_key=api_key, api_url=api_url)
        content = ccs.download_certificate(client, product_id)
        existing = ccs.read_local(dest)

        if existing is not None and existing == content:
            module.exit_json(
                changed=False,
                dest=dest,
                bytes_written=len(content),
            )

        if module.check_mode:
            module.exit_json(
                changed=True,
                dest=dest,
                bytes_written=len(content),
            )

        ccs.write_local(dest, content)
        module.exit_json(
            changed=True,
            dest=dest,
            bytes_written=len(content),
        )
    except Exception as e:
        module.fail_json(msg="Failed to download RavenDB Cloud certificate: {}".format(str(e)))


if __name__ == '__main__':
    main()
