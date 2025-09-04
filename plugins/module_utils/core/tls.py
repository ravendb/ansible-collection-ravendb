# -*- coding: utf-8 -*-

# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type
from dataclasses import dataclass


@dataclass
class TLSConfig:
    certificate_path: str = None
    ca_cert_path: str = None

    def to_requests_tuple(self) -> tuple:
        """
        Decide what to pass to requests for TLS.
        Returns a tuple: (cert, verify)
        """
        cert = None
        verify = True

        if self.certificate_path:
            cert = self.certificate_path
            verify = self.ca_cert_path if self.ca_cert_path else False
        elif self.ca_cert_path:
            verify = self.ca_cert_path

        return cert, verify
