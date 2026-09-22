# -*- coding: utf-8 -*-

# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import time

from ansible_collections.ravendb.ravendb.plugins.module_utils.services import cloud_product_service as cps


POLL_INTERVAL_SECONDS = 10
TERMINAL_STATUSES = ("Active", "Terminated", "Error", "AwaitingPayment")


def create_product(client, payload):
    return client.post("/products/create", body=payload)


def terminate_product(client, product_id, hide_in_portal=False):
    return client.post(
        "/products/terminate/{}".format(product_id),
        body={"hideInPortal": hide_in_portal},
    )


def change_instance_type(client, product_id, instance_type):
    return client.post(
        "/products/instance-type",
        body={"productId": product_id, "instanceType": instance_type},
    )


def change_storage(client, product_id, size, storage_type, iops=None, throughput=None):
    body = {
        "productId": product_id,
        "size": size,
        "storageType": storage_type,
    }
    if iops is not None:
        body["iops"] = iops
    if throughput is not None:
        body["throughput"] = throughput
    return client.post("/products/storage", body=body)


def status_of(details):
    return details.get("status")


def is_active(details):
    return status_of(details) == "Active"


def is_terminated(details):
    return status_of(details) == "Terminated"


def is_terminating(details):
    return status_of(details) == "Terminating"


def is_transitional_to_active(details):
    return status_of(details) in ("Creating", "DeployingChanges")


def wait_for_product_status(client, product_id, desired, timeout):
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(POLL_INTERVAL_SECONDS)

        details = cps.get_product_details(client, product_id)
        status = status_of(details)

        if status == desired:
            return details

        if status in TERMINAL_STATUSES and status != desired:
            raise RuntimeError(
                "Product '{}' reached unexpected terminal status '{}' while waiting for '{}'.".format(
                    product_id, status, desired)
            )

    raise RuntimeError(
        "Timed out after {}s waiting for product '{}' to reach status '{}'.".format(
            timeout, product_id, desired)
    )
