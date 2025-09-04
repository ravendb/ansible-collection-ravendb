# -*- coding: utf-8 -*-

# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

from ansible_collections.ravendb.ravendb.plugins.module_utils.core.configuration import validate_kv, diff_kv
from ansible_collections.ravendb.ravendb.plugins.module_utils.core.client import StoreContext


def validate_database_settings(d: dict) -> tuple:
    """Validate and normalize database_settings."""
    return validate_kv(d, "database_settings", allow_none=True)


def get_current(ctx: StoreContext, db_name: str) -> dict:
    """
    Returns dict of current db settings
    """
    from ravendb.serverwide.operations.configuration import GetDatabaseSettingsOperation
    s = ctx.store.maintenance.send(GetDatabaseSettingsOperation(db_name))
    return (s.settings or {}) if s else {}


def apply(ctx: StoreContext, db_name: str, to_apply: dict) -> None:
    from ravendb.serverwide.operations.configuration import PutDatabaseSettingsOperation
    from ravendb.documents.operations.server_misc import ToggleDatabasesStateOperation
    ctx.store.maintenance.send(PutDatabaseSettingsOperation(db_name, to_apply))
    ctx.maintenance_server().send(ToggleDatabasesStateOperation(db_name, True))
    ctx.maintenance_server().send(ToggleDatabasesStateOperation(db_name, False))


def diff(desired: dict, current: dict) -> dict:
    """
    Compare desired and current settings.
    Returns dict of settings to apply.
    """
    return diff_kv(desired, current)
