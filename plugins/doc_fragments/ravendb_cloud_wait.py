# -*- coding: utf-8 -*-

# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


class ModuleDocFragment(object):
    # Wait/poll options for asynchronous RavenDB Cloud lifecycle operations.
    DOCUMENTATION = '''
    options:
        wait:
            description:
                - Whether to wait for the Cloud operation to reach a terminal state.
            required: false
            type: bool
            default: true
        wait_timeout:
            description:
                - Maximum time in seconds to wait for the Cloud operation to reach a terminal state.
            required: false
            type: int
            default: 1800
    '''
