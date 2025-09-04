# -*- coding: utf-8 -*-

# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

from dataclasses import dataclass


@dataclass
class NodeSpec:
    tag: str
    url: str
    leader_url: str
    node_type: str = "Member"

    @property
    def is_watcher(self) -> bool:
        return self.node_type == "Watcher"
