# -*- coding: utf-8 -*-

# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


DEFAULT_API_URL = "https://api.cloud.ravendb.net"
DEFAULT_WAIT_TIMEOUT = 1800


def ravendb_cloud_argument_spec(include_wait=False):
    """Argument-spec fragment shared by every cloud_* module.

    Keeps api_key / api_url declarations in one place so a future default-URL bump
    or no_log change is a single edit instead of six. Modules that make write
    calls opt into the wait/wait_timeout knobs with include_wait=True.
    """
    spec = dict(
        api_key=dict(type='str', required=True, no_log=True),
        api_url=dict(type='str', required=False, default=DEFAULT_API_URL),
    )
    if include_wait:
        spec['wait'] = dict(type='bool', required=False, default=True)
        spec['wait_timeout'] = dict(type='int', required=False, default=DEFAULT_WAIT_TIMEOUT)
    return spec
