# -*- coding: utf-8 -*-

# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


def _enc_suffix(encrypted: bool) -> str:
    return " (encrypted)" if encrypted else ""


def db_exists(n: str) -> str:
    return "Database '{}' already exists.".format(n)


def db_not_exists(n: str) -> str:
    return "Database '{}' does not exist.".format(n)


def db_created(n: str, encrypted: bool = False) -> str:
    return "Database '{}' created successfully{}.".format(n, _enc_suffix(encrypted))


def db_would_create(n: str, encrypted: bool = False) -> str:
    return "Database '{}' would be created{}.".format(n, _enc_suffix(encrypted))


def db_deleted(n: str) -> str:
    return "Database '{}' deleted successfully.".format(n)


def db_would_delete(n: str) -> str:
    return "Database '{}' would be deleted.".format(n)


def db_no_changes(base: str) -> str:
    return "{} No changes.".format(base)


def settings_applied(prefix: str, keys) -> str:
    ks = ", ".join(sorted(keys)) if not isinstance(keys, str) else keys
    return "{} Applied settings ({}) and reloaded.".format(prefix, ks)


def settings_would_apply(prefix: str, keys) -> str:
    ks = ", ".join(sorted(keys)) if not isinstance(keys, str) else keys
    return "{} Would apply settings ({}) and reload.".format(prefix, ks)


def would_assign_encryption_key(db: str) -> str:
    return "Would assign encryption key for database '{}'.".format(db)


def assigned_encryption_key(db: str) -> str:
    return "Assigned encryption key for database '{}'.".format(db)


def encryption_mismatch(name: str, actual, desired) -> str:
    return (
        "Database '{}' already exists but encryption status is '{}' while requested '{}'. "
        "RavenDB does not support toggling encryption on an existing database. "
        "Delete & recreate, or backup and restore with the desired key."
    ).format(name, actual, desired)


def _cluster_suffix(cluster_wide: bool) -> str:
    return " cluster-wide" if cluster_wide else ""


def idx_cfg_applied(index_name: str, keys_str: str) -> str:
    return "Applied configuration for index '{}' (keys: {}).".format(index_name, keys_str)


def idx_cfg_would_apply(index_name: str, keys_str: str) -> str:
    return "Would apply configuration for index '{}' (keys: {}).".format(index_name, keys_str)


def idx_would_enable(name: str, cluster_wide: bool = False) -> str:
    return "Index '{}' would be enabled{}.".format(name, _cluster_suffix(cluster_wide))


def idx_would_disable(name: str, cluster_wide: bool = False) -> str:
    return "Index '{}' would be disabled{}.".format(name, _cluster_suffix(cluster_wide))


def idx_created(name: str) -> str:
    return "Index '{}' created successfully.".format(name)


def idx_would_create(name: str) -> str:
    return "Index '{}' would be created.".format(name)


def idx_deleted(name: str) -> str:
    return "Index '{}' deleted successfully.".format(name)


def idx_would_delete(name: str) -> str:
    return "Index '{}' would be deleted.".format(name)


def idx_enabled(name: str, *, cluster_wide: bool = False) -> str:
    return "Index '{}' enabled successfully{}.".format(name, _cluster_suffix(cluster_wide))


def idx_disabled(name: str, *, cluster_wide: bool = False) -> str:
    return "Index '{}' disabled successfully{}.".format(name, _cluster_suffix(cluster_wide))


def idx_already_enabled(name: str) -> str:
    return "Index '{}' is already enabled.".format(name)


def idx_already_disabled(name: str) -> str:
    return "Index '{}' is already disabled.".format(name)


def idx_resumed(name: str) -> str:
    return "Index '{}' resumed successfully.".format(name)


def idx_already_resumed(name: str) -> str:
    return "Index '{}' is already running.".format(name)


def idx_would_resume(name: str) -> str:
    return "Index '{}' would be resumed.".format(name)


def idx_paused(name: str) -> str:
    return "Index '{}' paused successfully.".format(name)


def idx_already_paused(name: str) -> str:
    return "Index '{}' is already paused.".format(name)


def idx_would_pause(name: str) -> str:
    return "Index '{}' would be paused.".format(name)


def idx_reset(name: str) -> str:
    return "Index '{}' reset successfully.".format(name)


def idx_would_reset(name: str) -> str:
    return "Index '{}' would be reset.".format(name)


def idx_exists(name: str) -> str:
    return "Index '{}' already exists.".format(name)


def idx_already_absent(name: str) -> str:
    return "Index '{}' is already absent.".format(name)


def idx_not_exist_cannot_apply_mode(name: str) -> str:
    return "Index '{}' does not exist. Cannot apply mode.".format(name)


def node_already_present(tag: str, role: str, url: str) -> str:
    return "Node '{}' already present as {} at {}.".format(tag, role, url)


def node_would_add(tag: str, node_type: str) -> str:
    return "Node '{}' would be added as {}.".format(tag, node_type)


def node_added(tag: str, node_type: str) -> str:
    return "Node '{}' added as {}.".format(tag, node_type)


def failed_add_node(tag: str, error: str) -> str:
    return "Failed to add node '{}': {}".format(tag, error)


def _fmt_tags(tags) -> str:
    return ", ".join(tags) if tags else ""


def members_would_reconcile(db: str, to_add: list, to_remove: list) -> str:
    if to_add and to_remove:
        return "Database '{}' would reconcile members: add [{}]; remove [{}].".format(db, _fmt_tags(to_add), _fmt_tags(to_remove))
    if to_add:
        return "Database '{}' would add members: [{}].".format(db, _fmt_tags(to_add))
    if to_remove:
        return "Database '{}' would remove members: [{}].".format(db, _fmt_tags(to_remove))
    return "Database '{}' membership already matches.".format(db)


def members_reconciled(db: str, to_add: list, to_remove: list) -> str:
    if to_add and to_remove:
        return "Database '{}' reconciled members: added [{}]; removed [{}].".format(db, _fmt_tags(to_add), _fmt_tags(to_remove))
    if to_add:
        return "Database '{}' added members: [{}].".format(db, _fmt_tags(to_add))
    if to_remove:
        return "Database '{}' removed members: [{}].".format(db, _fmt_tags(to_remove))
    return "Database '{}' membership already matched.".format(db)
