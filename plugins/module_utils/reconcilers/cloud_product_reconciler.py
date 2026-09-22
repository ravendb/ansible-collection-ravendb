# -*- coding: utf-8 -*-

# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

from ansible_collections.ravendb.ravendb.plugins.module_utils.core.result import ModuleResult
from ansible_collections.ravendb.ravendb.plugins.module_utils.services import cloud_product_service as cps
from ansible_collections.ravendb.ravendb.plugins.module_utils.services import cloud_product_lifecycle_service as cpls


REQUIRED_CREATE_FIELDS = (
    "cloud_provider", "instance_type", "region", "release_channel",
    "disk_size", "storage_type", "tier", "allowed_ips", "subdomain",
)
STORAGE_FIELDS = ("disk_size", "storage_type", "iops", "throughput")
IMMUTABLE_FIELDS = (
    ("tier", "tier"),
    ("cloud_provider", "cloudProvider"),
    ("region", "region"),
    ("subdomain", "subdomainName"),
)

PRESENT_BLOCKED_STATUSES = {
    "Terminating": "is currently terminating; cannot ensure present.",
    "Terminated": "was terminated; choose a different name.",
    "Error": "is in Error state; investigate in the portal.",
    "AwaitingPayment": "requires payment; resolve billing in the portal.",
}


class CloudProductReconciler(object):

    def __init__(self, client):
        self.client = client

    def ensure_present(self, spec, check_mode):
        existing = self._find_existing(spec)

        if existing is None:
            return self._create(spec, check_mode)

        details = cps.get_product_details(self.client, existing["id"])

        if cpls.is_active(details):
            return self._reconcile_drift(spec, details, check_mode)

        if cpls.is_transitional_to_active(details):
            if not spec.wait:
                return ModuleResult.ok(
                    msg="Product '{}' is {} (wait=false).".format(spec.name, cpls.status_of(details)),
                    changed=False, product=details,
                )
            final = cpls.wait_for_product_status(self.client, existing["id"], "Active", spec.wait_timeout)
            return ModuleResult.ok(
                msg="Product '{}' reached Active.".format(spec.name),
                changed=False, product=final,
            )

        status = cpls.status_of(details)
        reason = PRESENT_BLOCKED_STATUSES.get(status, "has unknown status: {}".format(status))
        return ModuleResult.error(msg="Product '{}' {}".format(spec.name, reason))

    def ensure_absent(self, spec, check_mode):
        existing = self._find_existing(spec)
        label = spec.name or spec.product_id

        if existing is None:
            return ModuleResult.ok(
                msg="Product '{}' is already absent.".format(label),
                changed=False,
            )

        details = cps.get_product_details(self.client, existing["id"])

        if cpls.is_terminated(details):
            return ModuleResult.ok(
                msg="Product '{}' is already Terminated.".format(label),
                changed=False, product=details,
            )

        if cpls.is_terminating(details):
            if not spec.wait:
                return ModuleResult.ok(
                    msg="Product '{}' is Terminating (wait=false).".format(label),
                    changed=True, product=details,
                )
            final = cpls.wait_for_product_status(self.client, existing["id"], "Terminated", spec.wait_timeout)
            return ModuleResult.ok(
                msg="Product '{}' reached Terminated.".format(label),
                changed=True, product=final,
            )

        if check_mode:
            return ModuleResult.ok(
                msg="Product '{}' would be terminated.".format(label),
                changed=True, product=details,
            )

        cpls.terminate_product(self.client, existing["id"], hide_in_portal=spec.hide_in_portal)

        if not spec.wait:
            return ModuleResult.ok(
                msg="Product '{}' termination initiated (wait=false).".format(label),
                changed=True, product=details,
            )

        final = cpls.wait_for_product_status(self.client, existing["id"], "Terminated", spec.wait_timeout)
        return ModuleResult.ok(
            msg="Product '{}' terminated.".format(label),
            changed=True, product=final,
        )

    def _find_existing(self, spec):
        listing = cps.list_products(self.client)

        if spec.product_id is not None:
            return next((p for p in listing if p.get("id") == spec.product_id), None)

        return next((p for p in listing if p.get("name") == spec.name), None)

    def _reconcile_drift(self, spec, current, check_mode):
        product_id = current["id"]

        for spec_attr, details_key in IMMUTABLE_FIELDS:
            desired = getattr(spec, spec_attr)
            cur_val = current.get(details_key)
            if desired is None:
                continue
            if spec_attr == "cloud_provider":
                if str(desired).lower() != str(cur_val or "").lower():
                    return ModuleResult.error(
                        msg="{} is immutable; current='{}', desired='{}'. Recreate the product to change it.".format(
                            spec_attr, cur_val, desired
                        )
                    )
            elif desired != cur_val:
                return ModuleResult.error(
                    msg="{} is immutable; current='{}', desired='{}'. Recreate the product to change it.".format(
                        spec_attr, cur_val, desired
                    )
                )

        if spec.allowed_ips is not None:
            cur_ips = (current.get("security") or {}).get("allowedIps") or []
            if set(spec.allowed_ips) != set(cur_ips):
                return ModuleResult.error(
                    msg=(
                        "allowed_ips drift detected (current={}, desired={}) - changing "
                        "allowed_ips is not supported by this module. Update it in the "
                        "RavenDB Cloud portal."
                    ).format(list(cur_ips), list(spec.allowed_ips))
                )

        if spec.release_channel is not None and spec.release_channel != current.get("releaseChannel"):
            return ModuleResult.error(
                msg=(
                    "release_channel drift detected (current='{}', desired='{}') - changing "
                    "release_channel is not supported by this module. Update it in the "
                    "RavenDB Cloud portal."
                ).format(current.get("releaseChannel"), spec.release_channel)
            )

        applied = []
        latest_details = None

        user_set_any_storage = any(getattr(spec, f) is not None for f in STORAGE_FIELDS)
        if user_set_any_storage:
            cur_storage = (current.get("hardwareInfo") or {}).get("storage") or {}
            if (spec.disk_size != cur_storage.get("size")
                    or spec.storage_type != cur_storage.get("type")
                    or spec.iops != cur_storage.get("iops")
                    or spec.throughput != cur_storage.get("throughput")):
                if check_mode:
                    applied.append("storage (would change)")
                else:
                    try:
                        cpls.change_storage(self.client, product_id, spec.disk_size, spec.storage_type, spec.iops, spec.throughput)
                        latest_details = cpls.wait_for_product_status(self.client, product_id, "Active", spec.wait_timeout)
                        applied.append("storage")
                    except Exception as e:
                        return ModuleResult.error(
                            msg="Drift partial: applied={}; storage FAILED: {}.".format(applied or ["none"], str(e))
                        )

        if spec.instance_type is not None and spec.instance_type != current.get("instanceType"):
            if check_mode:
                applied.append("instance_type (would change)")
            else:
                try:
                    cpls.change_instance_type(self.client, product_id, spec.instance_type)
                    latest_details = cpls.wait_for_product_status(self.client, product_id, "Active", spec.wait_timeout)
                    applied.append("instance_type")
                except Exception as e:
                    return ModuleResult.error(
                        msg="Drift partial: applied={}; instance_type FAILED: {}.".format(applied or ["none"], str(e))
                    )

        if not applied:
            return ModuleResult.ok(
                msg="Product '{}' already active; no drift.".format(spec.name),
                changed=False, product=current,
            )

        final = current if check_mode else (latest_details or current)
        return ModuleResult.ok(
            msg="Product '{}' drift reconciled: {}.".format(spec.name, ", ".join(applied)),
            changed=True, product=final,
        )

    def _create(self, spec, check_mode):
        missing = [f for f in REQUIRED_CREATE_FIELDS if getattr(spec, f) is None]
        if missing:
            return ModuleResult.error(
                msg="Cannot create product '{}': missing required fields: {}".format(
                    spec.name, ", ".join(missing)),
            )

        if check_mode:
            return ModuleResult.ok(
                msg="Product '{}' would be created.".format(spec.name),
                changed=True,
            )

        response = cpls.create_product(self.client, spec.to_create_payload())
        product_id = response.get("productId")
        if not product_id:
            return ModuleResult.error(
                msg="Create response missing productId: {}".format(response),
            )

        if not spec.wait:
            return ModuleResult.ok(
                msg="Product '{}' creation initiated (wait=false).".format(spec.name),
                changed=True, product={"id": product_id},
            )

        final = cpls.wait_for_product_status(self.client, product_id, "Active", spec.wait_timeout)
        return ModuleResult.ok(
            msg="Product '{}' created and Active.".format(spec.name),
            changed=True, product=final,
        )
