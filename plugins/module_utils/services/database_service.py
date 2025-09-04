# -*- coding: utf-8 -*-

# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type
from ansible_collections.ravendb.ravendb.plugins.module_utils.core.client import StoreContext
from ansible_collections.ravendb.ravendb.plugins.module_utils.core.tls import TLSConfig
from ansible_collections.ravendb.ravendb.plugins.module_utils.services import encryption_service as encsvc


def list_databases(ctx, start=0, max=128):
    """Return a list of database names from the server."""
    from ravendb.serverwide.operations.common import GetDatabaseNamesOperation
    return ctx.maintenance_server().send(GetDatabaseNamesOperation(start, max))


def get_record(ctx, db_name):
    """
    Fetch the database record for the specified database.
    """
    from ravendb.serverwide.operations.common import GetDatabaseRecordOperation
    return ctx.maintenance_server().send(GetDatabaseRecordOperation(db_name))


def create_database(ctx, db_name, replication_factor, encrypted, members=None, tls=None):
    if members:
        import requests
        body = {
            "DatabaseName": db_name,
            "ReplicationFactor": len(members),
            "Encrypted": bool(encrypted),
            "DisableDynamicNodesDistribution": True,
            "Topology": {
                "Members": list(members),
                "ReplicationFactor": len(members),
                "DynamicNodesDistribution": False,
            },
        }
        base = ctx.store.urls[0].rstrip("/")
        url = base + "/admin/databases"  # todo: move to client operation when it will be supported
        cert, verify = (tls or TLSConfig()).to_requests_tuple()
        r = requests.put(url, json=body, cert=cert, verify=verify, timeout=30)
        r.raise_for_status()
        return

    from ravendb.serverwide.database_record import DatabaseRecord
    from ravendb.serverwide.operations.common import CreateDatabaseOperation
    rec = DatabaseRecord(db_name)
    if encrypted:
        rec.encrypted = True
    ctx.maintenance_server().send(CreateDatabaseOperation(rec, replication_factor))


def delete_database(
    ctx,
    db_name,
    from_nodes=None,
    hard_delete=None,
    tls=None,
    time_to_wait_sec=None,
):
    if not from_nodes and hard_delete is None and time_to_wait_sec is None:
        from ravendb.serverwide.operations.common import DeleteDatabaseOperation
        ctx.maintenance_server().send(DeleteDatabaseOperation(db_name))
        return

    import requests
    base = ctx.store.urls[0].rstrip("/")
    url = base + "/admin/databases"  # todo: move to client operation when it will be supported
    params = {}
    if hard_delete is True:
        params["hardDelete"] = "true"
    elif hard_delete is False:
        params["hardDelete"] = "false"
    if time_to_wait_sec is not None:
        params["timeToWaitForConfirmationInSec"] = str(int(time_to_wait_sec))

    payload = {"DatabaseNames": [db_name]}
    if from_nodes:
        payload["FromNodes"] = list(from_nodes)

    cert, verify = (tls or TLSConfig()).to_requests_tuple()
    r = requests.delete(url, params=params, json=payload, cert=cert, verify=verify, timeout=30)
    r.raise_for_status()


def add_member_if_needed(ctx, db_name, node_tag, tls=None):
    try:
        rec = get_record(ctx, db_name)
        if node_tag in set(_extract_members_from_record(rec)):
            return False
    except Exception:
        pass

    from ravendb.serverwide.operations.common import AddDatabaseNodeOperation
    try:
        ctx.maintenance_server().send(AddDatabaseNodeOperation(db_name, node_tag))
        return True
    except Exception as e:
        try:
            rec = get_record(ctx, db_name)
            if node_tag in set(_extract_members_from_record(rec)):
                return False
        except Exception:
            pass
        if _already_member_error(e):
            return False
        raise


def _already_member_error(e):
    s = str(e).lower()
    return ("already part of" in s or "already in its topology" in s or "already part of it" in s)


def _extract_members_from_record(record):
    topo = (
        getattr(record, "topology", None) or getattr(record, "Topology", None)
        if record and not isinstance(record, dict)
        else (record or {}).get("topology") or (record or {}).get("Topology")
    )
    if not topo:
        return []

    def _group(name):
        if isinstance(topo, dict):
            return topo.get(name) or topo.get(name.capitalize())
        return getattr(topo, name, None) or getattr(topo, name.capitalize(), None)

    tags = []
    for name in ("members", "promotables", "rehabs"):
        tags.extend(_pluck_tags(_group(name)))

    # filter out falsy values and keep order unique
    return list(dict.fromkeys(t for t in tags if t))


def _pluck_tags(group):
    if not group:
        return []

    if isinstance(group, dict):
        return [str(k).strip() for k in group.keys()]

    if isinstance(group, str):
        return [group.strip()]
    try:
        items = list(group)
    except TypeError:
        return []

    out = []
    for item in items:
        if isinstance(item, str):
            out.append(item.strip())
            continue
        if isinstance(item, dict):
            t = item.get("NodeTag") or item.get("node_tag")
        else:
            t = getattr(item, "NodeTag", None) or getattr(item, "node_tag", None)
        if t:
            out.append(str(t).strip())

    return list(dict.fromkeys(out))


def members_delta(record, wanted):
    cur = set(str(x).strip() for x in _extract_members_from_record(record))
    want = set(str(x).strip() for x in (wanted or []))
    to_add = sorted(list(want - cur))
    to_remove = sorted(list(cur - want))
    return to_add, to_remove


def reconcile_membership(
    ctx,
    db_name,
    record,
    wanted_members,
    encrypted,
    enc_key_path=None,
    tls=None,
    check_mode=False,
):
    try:
        record = get_record(ctx, db_name)
    except Exception:
        pass

    to_add, to_remove = members_delta(record, wanted_members)
    if not to_add and not to_remove:
        return False, [], []

    if check_mode:
        return True, to_add, to_remove

    changed_any = False

    if encrypted and to_add:
        if not enc_key_path:
            raise RuntimeError(
                "Database '{}' is encrypted. Adding nodes requires 'encryption_key' for key distribution.".format(db_name)
            )
        key = encsvc.read_key(enc_key_path)
        encsvc.distribute_key(ctx, db_name, key, tls or TLSConfig(), only_tags=to_add)

    for t in list(to_add):
        if add_member_if_needed(ctx, db_name, t, tls=tls):
            changed_any = True

    if to_remove:
        delete_database(ctx, db_name, from_nodes=to_remove, hard_delete=False, tls=tls, time_to_wait_sec=30)
        changed_any = True

    return changed_any, to_add, to_remove
