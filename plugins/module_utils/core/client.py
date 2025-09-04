# -*- coding: utf-8 -*-

# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

from dataclasses import dataclass
from typing import TYPE_CHECKING
from .deps import require_ravendb

if TYPE_CHECKING:
    from ravendb import DocumentStore


@dataclass
class StoreContext:
    store: "DocumentStore"

    def maintenance_server(self):
        return self.store.maintenance.server

    def maintenance_for_db(self, db_name):
        return self.store.maintenance.for_database(db_name)

    def close(self):
        try:
            self.store.close()
        except Exception as e:
            raise e


class DocumentStoreFactory:
    @staticmethod
    def create(url, database=None, certificate_path=None, ca_cert_path=None):
        require_ravendb()
        from ravendb import DocumentStore

        s = DocumentStore(urls=[url], database=database)
        if certificate_path:
            s.certificate_pem_path = certificate_path
        if ca_cert_path:
            s.trust_store_path = ca_cert_path
        s.initialize()
        return StoreContext(store=s)
