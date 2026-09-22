# -*- coding: utf-8 -*-

# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = '''
---
module: cloud_product_info
short_description: List or look up RavenDB Cloud products
description:
  - Retrieves RavenDB Cloud products from the control-plane API.
  - With no filter, returns all products on the account.
  - Filters C(product_id) and C(name) are mutually exclusive.
  - When multiple products match a non-id filter, all matches are returned.
  - When no product matches a filter, an empty list is returned (not an error).
  - When C(include_details=true), each returned product is enriched with full details via C(/products/details/{id}).
version_added: "1.1.0"
author: "Omer Ratsaby <omer.ratsaby@ravendb.net> (@thegoldenplatypus)"

extends_documentation_fragment:
  - ravendb.ravendb.ravendb_cloud

options:
  product_id:
    description:
      - Look up a single product by its Cloud product id.
      - Mutually exclusive with C(name).
    required: false
    type: str
  name:
    description:
      - Look up products by product name (the C(name) field on the listing endpoint). Multiple matches are returned.
      - Mutually exclusive with C(product_id).
    required: false
    type: str
  include_details:
    description:
      - When C(true), enrich each returned product with full details from C(/products/details/{id}).
      - Adds one API call per matching product.
    required: false
    type: bool
    default: false

seealso:
  - name: RavenDB Cloud documentation
    description: Official RavenDB Cloud documentation
    link: https://docs.ravendb.net/cloud
'''

EXAMPLES = '''
- name: List all RavenDB Cloud products
  ravendb.ravendb.cloud_product_info:
    api_key: "{{ ravendb_cloud_api_key }}"

- name: Look up a product by id, with full details
  ravendb.ravendb.cloud_product_info:
    api_key: "{{ ravendb_cloud_api_key }}"
    product_id: "abc123"
    include_details: true

- name: Look up products by name
  ravendb.ravendb.cloud_product_info:
    api_key: "{{ ravendb_cloud_api_key }}"
    name: "production-cluster"
'''

RETURN = '''
changed:
  description: Always false; this module is read-only.
  type: bool
  returned: always
  sample: false

count:
  description: Number of products returned.
  type: int
  returned: always
  sample: 2

products:
  description: List of product dicts as returned by the RavenDB Cloud API.
  type: list
  elements: dict
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
    from ansible_collections.ravendb.ravendb.plugins.module_utils.services import cloud_product_service as cps
    HAS_LIB = True
except ImportError:
    HAS_LIB = False
    LIB_ERR = traceback.format_exc()


def main():
    argument_spec = dict(
        api_key=dict(type='str', required=True, no_log=True),
        api_url=dict(type='str', required=False, default='https://api.cloud.ravendb.net'),
        product_id=dict(type='str', required=False),
        name=dict(type='str', required=False),
        include_details=dict(type='bool', default=False),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        mutually_exclusive=[("product_id", "name")],
    )

    if not HAS_LIB:
        module.fail_json(msg=missing_required_lib("requests"), exception=LIB_ERR)

    api_key = module.params['api_key']
    api_url = module.params['api_url']
    product_id = module.params.get('product_id')
    name = module.params.get('name')
    include_details = module.params['include_details']

    checks = [
        validate_api_key(api_key),
        validate_api_url(api_url),
    ]
    if product_id is not None:
        checks.append(validate_product_id(product_id))

    ok, err = collect_errors(*checks)
    if not ok:
        module.fail_json(msg=err)

    try:
        client = RavenDBCloudClient(api_key=api_key, api_url=api_url)
        products = cps.list_products(client)
        filtered = cps.filter_products(products, product_id=product_id, name=name)

        if include_details and filtered:
            filtered = cps.enrich_with_details(client, filtered)

        module.exit_json(changed=False, count=len(filtered), products=filtered)
    except Exception as e:
        module.fail_json(msg="Failed to list RavenDB Cloud products: {}".format(str(e)))


if __name__ == '__main__':
    main()
