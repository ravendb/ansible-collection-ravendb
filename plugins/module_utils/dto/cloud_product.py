# -*- coding: utf-8 -*-

# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


class CloudProductSpec(object):
    def __init__(self,
                 name,
                 product_id=None,
                 cloud_provider=None,
                 instance_type=None,
                 region=None,
                 release_channel=None,
                 disk_size=None,
                 storage_type=None,
                 tier=None,
                 allowed_ips=None,
                 subdomain=None,
                 iops=None,
                 throughput=None,
                 disk_layout=None,
                 deployment_type=None,
                 hide_in_portal=False,
                 wait=True,
                 wait_timeout=1800):
        self.name = name
        self.product_id = product_id
        self.cloud_provider = cloud_provider
        self.instance_type = instance_type
        self.region = region
        self.release_channel = release_channel
        self.disk_size = disk_size
        self.storage_type = storage_type
        self.tier = tier
        self.allowed_ips = allowed_ips
        self.subdomain = subdomain
        self.iops = iops
        self.throughput = throughput
        self.disk_layout = disk_layout
        self.deployment_type = deployment_type
        self.hide_in_portal = hide_in_portal
        self.wait = wait
        self.wait_timeout = wait_timeout

    def to_create_payload(self):
        payload = {
            "displayName": self.name,
            "cloudProvider": self.cloud_provider,
            "instanceTypeName": self.instance_type,
            "region": self.region,
            "releaseChannel": self.release_channel,
            "diskSize": self.disk_size,
            "storageTypeName": self.storage_type,
            "tier": self.tier,
            "allowedIps": self.allowed_ips,
        }
        if self.subdomain is not None:
            payload["subdomainName"] = self.subdomain
        if self.iops is not None:
            payload["iops"] = self.iops
        if self.disk_layout is not None:
            payload["diskLayout"] = self.disk_layout
        if self.deployment_type is not None:
            payload["deploymentType"] = self.deployment_type
        return payload
