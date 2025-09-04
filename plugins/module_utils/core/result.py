# -*- coding: utf-8 -*-

# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function, annotations
__metaclass__ = type
from dataclasses import dataclass, field


@dataclass
class ModuleResult:
    changed: bool = False
    failed: bool = False
    msg: str = ""
    extras: dict = field(default_factory=dict)

    @classmethod
    def ok(cls, msg: str = "", changed: bool = False, **extras) -> ModuleResult:
        return cls(changed=changed, failed=False, msg=msg, extras=extras)

    @classmethod
    def error(cls, msg: str, **extras) -> ModuleResult:
        return cls(changed=False, failed=True, msg=msg, extras=extras)

    def to_ansible(self) -> dict:
        data = dict(changed=self.changed, msg=self.msg)
        if self.failed:
            data["failed"] = True
        if self.extras:
            data.update(self.extras)
        return data
