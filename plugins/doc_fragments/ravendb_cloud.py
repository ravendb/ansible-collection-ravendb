# -*- coding: utf-8 -*-

# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


class ModuleDocFragment(object):
    # RavenDB Cloud documentation fragment
    DOCUMENTATION = '''
    options:
        api_key:
            description:
                - API key used to authenticate against the RavenDB Cloud control-plane API.
                - Sent in the C(X-Api-Key) header on every request.
            required: true
            type: str
        api_url:
            description:
                - Base URL of the RavenDB Cloud control-plane API.
                - Override only when targeting a non-production environment such as a sandbox.
            required: false
            type: str
            default: https://api.cloud.ravendb.net

    attributes:
        check_mode:
            support: full
            description:
                - Can run in check_mode. Read operations always execute so predictions are based
                  on real state. Write operations (create, terminate, change) are predicted and
                  never sent to the Cloud API.

    notes:
    - Authenticates against the RavenDB Cloud control-plane API using C(X-Api-Key).
    - Does not require the ravendb python client or the .NET runtime.

    requirements:
    - python >= 3.9
    - requests
    '''
