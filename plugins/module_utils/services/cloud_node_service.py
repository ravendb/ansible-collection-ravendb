# -*- coding: utf-8 -*-

# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


def add_node(client, product_id):
    return client.post(
        "/products/additional-node/add",
        body={"productId": product_id},
    )


def remove_node(client, product_id, node_tag):
    return client.post(
        "/products/additional-node/remove",
        body={"productId": product_id, "nodeTag": node_tag},
    )


def restart_node(client, product_id, node_tag):
    return client.post(
        "/products/restart-node",
        body={"productId": product_id, "nodeTag": node_tag},
    )
