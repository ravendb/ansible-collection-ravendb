# -*- coding: utf-8 -*-

# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

from dataclasses import dataclass, field


@dataclass
class EncryptionSpec:
    enabled: bool = False
    certificate_path: str = None
    ca_cert_path: str = None
    generate_key: bool = False
    key_path: str = None
    output_path: str = None


@dataclass
class DatabaseSpec:
    url: str
    name: str
    replication_factor: int = 1
    settings: dict = field(default_factory=dict)
    encryption: EncryptionSpec = field(default_factory=EncryptionSpec)
    members: list = field(default_factory=list)
