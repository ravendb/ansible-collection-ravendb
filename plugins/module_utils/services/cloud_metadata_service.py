# -*- coding: utf-8 -*-

# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


def list_regions(client, cloud_provider):
    return client.get("/metadata/regions/{}".format(cloud_provider))


def list_instance_types(client, cloud_provider, region):
    return client.get("/metadata/instance-types/{}/{}".format(cloud_provider, region))


def list_release_channels(client):
    return client.get("/metadata/release-channels")
