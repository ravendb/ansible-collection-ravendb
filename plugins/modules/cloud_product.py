# -*- coding: utf-8 -*-

# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = '''
---
module: cloud_product
short_description: Manage RavenDB Cloud product lifecycle (create, terminate)
description:
  - Create, terminate, or reconcile a RavenDB Cloud product via the control-plane API.
  - With C(state=present), creates the product if it does not exist; if it exists and is Active,
    reconciles drift on supported fields (C(instance_type) and the storage fields
    C(disk_size), C(storage_type), C(iops), C(throughput)).
  - Storage drift forwards whatever storage fields the user set to the API. The RavenDB Cloud
    API validates the payload and rejects incomplete SsdPremium requests. SsdPremium needs
    C(disk_size), C(storage_type), C(iops), and C(throughput). SsdStandard uses only
    C(disk_size) and C(storage_type); C(iops) and C(throughput) do not apply.
  - With C(state=absent), terminates the product. Requires C(confirm_destroy=true) as an
    explicit safety flag.
  - When C(wait=true) (the default), polls until the product reaches a terminal status
    (Active for create/drift, Terminated for terminate).
  - Immutable fields (C(tier), C(cloud_provider), C(region), C(subdomain)) and fields with
    no change endpoint (C(allowed_ips), C(release_channel)) cause the module to fail loud
    if the user provides a value that differs from the current product state.
  - Node count changes are not handled here - use C(ravendb.ravendb.cloud_node) for
    per-node add/remove/restart operations.
version_added: "1.1.0"
author: "Omer Ratsaby <omer.ratsaby@ravendb.net> (@thegoldenplatypus)"

extends_documentation_fragment:
  - ravendb.ravendb.ravendb_cloud
  - ravendb.ravendb.ravendb_cloud_wait

options:
  state:
    description:
      - Desired state of the product.
    required: true
    type: str
    choices: [present, absent]
  name:
    description:
      - Product display name. Required when C(state=present).
      - For C(state=absent), exactly one of C(name) or C(product_id) must be set.
      - Mutually exclusive with C(product_id).
    required: false
    type: str
  product_id:
    description:
      - Product id. For C(state=absent), exactly one of C(name) or C(product_id) must be set.
      - Mutually exclusive with C(name).
    required: false
    type: str
  confirm_destroy:
    description:
      - Required safety flag when C(state=absent). Must be C(true) for the module to proceed.
    required: false
    type: bool
    default: false
  hide_in_portal:
    description:
      - When C(state=absent), also hide the terminated product from the RavenDB Cloud portal.
    required: false
    type: bool
    default: false
  cloud_provider:
    description:
      - Cloud provider to provision the product on. Required when creating.
    required: false
    type: str
    choices: [aws, azure, gcp]
  instance_type:
    description:
      - Instance type name to use. Required when creating. Discover available types with C(cloud_metadata_info).
    required: false
    type: str
  region:
    description:
      - Cloud region. Required when creating. Discover available regions with C(cloud_metadata_info).
    required: false
    type: str
  release_channel:
    description:
      - RavenDB Cloud release channel. Required when creating. Discover available channels with C(cloud_metadata_info).
    required: false
    type: str
  disk_size:
    description:
      - Disk size in GB. Required when creating.
    required: false
    type: int
  storage_type:
    description:
      - Storage type name. Required when creating.
    required: false
    type: str
    choices: [SsdStandard, SsdPremium]
  tier:
    description:
      - Product tier. Required when creating.
    required: false
    type: str
    choices: [Free, Development, Production]
  allowed_ips:
    description:
      - List of IPs allowed to access the product. Required when creating (may be an empty list).
    required: false
    type: list
    elements: str
  subdomain:
    description:
      - DNS subdomain for the product. Must be short and DNS-safe (lowercase alphanumeric plus hyphen).
      - Required when creating a new product. Ignored on idempotency or drift reruns for
        an existing product (subdomain is immutable after create).
      - Distinct from C(name), which is the display name and may contain arbitrary text.
    required: false
    type: str
  iops:
    description:
      - IOPS allocation. Applies to C(SsdPremium) storage only; ignored for C(SsdStandard).
      - Required (together with C(throughput)) when creating or drift-reconciling C(SsdPremium) storage.
    required: false
    type: int
  throughput:
    description:
      - Storage throughput. Applies to C(SsdPremium) storage only; ignored for C(SsdStandard).
      - Required (together with C(iops)) when creating or drift-reconciling C(SsdPremium) storage.
    required: false
    type: float
  disk_layout:
    description:
      - Optional disk layout name.
    required: false
    type: str
  deployment_type:
    description:
      - Optional deployment type.
    required: false
    type: str

seealso:
  - name: RavenDB Cloud documentation
    description: Official RavenDB Cloud documentation
    link: https://docs.ravendb.net/cloud
'''

EXAMPLES = '''
- name: Create a product (default wait - up to 30 min for Active)
  ravendb.ravendb.cloud_product:
    api_key: "{{ ravendb_cloud_api_key }}"
    state: present
    name: "my-product"
    subdomain: "my-prod"
    cloud_provider: aws
    instance_type: "Dev10"
    region: "us-east-1"
    release_channel: "Stable62"
    disk_size: 10
    storage_type: "SsdStandard"
    tier: "Development"
    allowed_ips: ["203.0.113.10/32"]

- name: Create with shorter wait_timeout (give up after 5 min)
  ravendb.ravendb.cloud_product:
    api_key: "{{ ravendb_cloud_api_key }}"
    state: present
    name: "short-wait-product"
    subdomain: "swp"
    cloud_provider: aws
    instance_type: "Dev10"
    region: "us-east-1"
    release_channel: "Stable62"
    disk_size: 10
    storage_type: "SsdStandard"
    tier: "Development"
    allowed_ips: ["203.0.113.10/32"]
    wait_timeout: 300

- name: Fire-and-forget create (return as soon as API accepts the POST)
  ravendb.ravendb.cloud_product:
    api_key: "{{ ravendb_cloud_api_key }}"
    state: present
    name: "later-product"
    subdomain: "later"
    cloud_provider: aws
    instance_type: "Dev10"
    region: "us-east-1"
    release_channel: "Stable62"
    disk_size: 10
    storage_type: "SsdStandard"
    tier: "Development"
    allowed_ips: ["203.0.113.10/32"]
    wait: false

- name: Terminate a product (default wait - up to 30 min for Terminated)
  ravendb.ravendb.cloud_product:
    api_key: "{{ ravendb_cloud_api_key }}"
    state: absent
    name: "my-product"
    confirm_destroy: true

- name: Terminate with shorter wait_timeout and hide from portal
  ravendb.ravendb.cloud_product:
    api_key: "{{ ravendb_cloud_api_key }}"
    state: absent
    name: "my-product"
    confirm_destroy: true
    hide_in_portal: true
    wait_timeout: 600

- name: Fire-and-forget terminate (return as soon as API accepts the POST)
  ravendb.ravendb.cloud_product:
    api_key: "{{ ravendb_cloud_api_key }}"
    state: absent
    product_id: "abc123"
    confirm_destroy: true
    wait: false
'''

RETURN = '''
changed:
  description: Whether the product state was changed.
  type: bool
  returned: always

msg:
  description: Human-readable message describing the outcome.
  type: str
  returned: always

product:
  description: Full product details dict as returned by the Cloud API. Present when the product exists or was created.
  type: dict
  returned: when product exists
'''

import traceback
from ansible.module_utils.basic import AnsibleModule, missing_required_lib

LIB_ERR = None
try:
    from ansible_collections.ravendb.ravendb.plugins.module_utils.cloud.client import RavenDBCloudClient
    from ansible_collections.ravendb.ravendb.plugins.module_utils.cloud.validation import (
        validate_api_key, validate_api_url, validate_cloud_provider,
        validate_positive_int, validate_product_id,
    )
    from ansible_collections.ravendb.ravendb.plugins.module_utils.core.validation import collect_errors
    from ansible_collections.ravendb.ravendb.plugins.module_utils.dto.cloud_product import CloudProductSpec
    from ansible_collections.ravendb.ravendb.plugins.module_utils.reconcilers.cloud_product_reconciler import CloudProductReconciler
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

        state=dict(type='str', required=True, choices=['present', 'absent']),
        name=dict(type='str', required=False),
        product_id=dict(type='str', required=False),
        confirm_destroy=dict(type='bool', default=False),
        hide_in_portal=dict(type='bool', default=False),

        cloud_provider=dict(type='str', required=False, choices=['aws', 'azure', 'gcp']),
        instance_type=dict(type='str', required=False),
        region=dict(type='str', required=False),
        release_channel=dict(type='str', required=False),
        disk_size=dict(type='int', required=False),
        storage_type=dict(type='str', required=False, choices=['SsdStandard', 'SsdPremium']),
        tier=dict(type='str', required=False, choices=['Free', 'Development', 'Production']),
        allowed_ips=dict(type='list', elements='str', required=False),
        subdomain=dict(type='str', required=False),
        iops=dict(type='int', required=False),
        throughput=dict(type='float', required=False),
        disk_layout=dict(type='str', required=False),
        deployment_type=dict(type='str', required=False),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_if=[
            ('state', 'present', ['name']),
        ],
        mutually_exclusive=[('name', 'product_id')],
        required_one_of=[('name', 'product_id')],
    )

    if not HAS_LIB:
        module.fail_json(msg=missing_required_lib("requests"), exception=LIB_ERR)

    api_key = module.params['api_key']
    api_url = module.params['api_url']
    state = module.params['state']
    name = module.params.get('name')
    product_id = module.params.get('product_id')
    confirm_destroy = module.params['confirm_destroy']
    hide_in_portal = module.params['hide_in_portal']
    wait = module.params['wait']
    wait_timeout = module.params['wait_timeout']

    cloud_provider = module.params.get('cloud_provider')
    instance_type = module.params.get('instance_type')
    region = module.params.get('region')
    release_channel = module.params.get('release_channel')
    disk_size = module.params.get('disk_size')
    storage_type = module.params.get('storage_type')
    tier = module.params.get('tier')
    allowed_ips = module.params.get('allowed_ips')
    subdomain = module.params.get('subdomain')
    iops = module.params.get('iops')
    throughput = module.params.get('throughput')
    disk_layout = module.params.get('disk_layout')
    deployment_type = module.params.get('deployment_type')

    checks = [
        validate_api_key(api_key),
        validate_api_url(api_url),
        validate_positive_int("wait_timeout", wait_timeout),
    ]
    if cloud_provider is not None:
        checks.append(validate_cloud_provider(cloud_provider))
    if product_id is not None:
        checks.append(validate_product_id(product_id))
    if disk_size is not None:
        checks.append(validate_positive_int("disk_size", disk_size))
    if iops is not None:
        checks.append(validate_positive_int("iops", iops))

    ok, err = collect_errors(*checks)
    if not ok:
        module.fail_json(msg=err)

    if state == 'absent' and not confirm_destroy:
        module.fail_json(msg="Refusing to terminate product: set confirm_destroy=true to proceed.")

    try:
        client = RavenDBCloudClient(api_key=api_key, api_url=api_url)
        spec = CloudProductSpec(
            name=name,
            product_id=product_id,
            cloud_provider=cloud_provider,
            instance_type=instance_type,
            region=region,
            release_channel=release_channel,
            disk_size=disk_size,
            storage_type=storage_type,
            tier=tier,
            allowed_ips=allowed_ips,
            subdomain=subdomain,
            iops=iops,
            throughput=throughput,
            disk_layout=disk_layout,
            deployment_type=deployment_type,
            hide_in_portal=hide_in_portal,
            wait=wait,
            wait_timeout=wait_timeout,
        )
        reconciler = CloudProductReconciler(client)

        if state == 'present':
            res = reconciler.ensure_present(spec, module.check_mode)
        else:
            res = reconciler.ensure_absent(spec, module.check_mode)

        if res.failed:
            module.fail_json(**res.to_ansible())
        else:
            module.exit_json(**res.to_ansible())
    except Exception as e:
        module.fail_json(msg="Unexpected error: {}".format(str(e)))


if __name__ == '__main__':
    main()
