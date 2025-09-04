# tests/unit/test_database.py
# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

import os
from ravendb_test_driver import RavenTestDriver
from unittest import TestCase
from unittest.mock import patch

from ansible_collections.ravendb.ravendb.plugins.module_utils.core.validation import (
    is_valid_url,
    is_valid_database_name,
    is_valid_replication_factor,
    validate_paths_exist,
    is_valid_state,
)
from ansible_collections.ravendb.ravendb.plugins.module_utils.reconcilers.database_reconciler import (
    DatabaseReconciler,
)
from ansible_collections.ravendb.ravendb.plugins.module_utils.dto.database import (
    DatabaseSpec,
    EncryptionSpec,
)
from ansible_collections.ravendb.ravendb.plugins.module_utils.core.client import StoreContext
from ansible_collections.ravendb.ravendb.plugins.module_utils.core.tls import TLSConfig
from ansible_collections.ravendb.ravendb.plugins.module_utils.services import db_settings_service as setsvc


class TestDBStateValidator(TestCase):
    def setUp(self):
        super().setUp()
        self.test_driver = RavenTestDriver()
        self.url = "http://localhost:8080"

    def _ctx(self, store):
        return StoreContext(store=store)

    def _spec(
        self,
        name,
        *,
        repl=1,
        encrypted=False,
        settings=None,
    ):
        return DatabaseSpec(
            url=self.url,
            name=name,
            replication_factor=repl,
            settings=settings or {},
            encryption=EncryptionSpec(enabled=encrypted),
        )

    def test_create_database(self):
        store = self.test_driver.get_document_store(database="test_create_database")
        self.addCleanup(store.close)
        ctx = self._ctx(store)

        db_name = "test_db"
        rec = DatabaseReconciler(ctx)
        res = rec.ensure_present(self._spec(db_name), TLSConfig(), check_mode=False)

        self.assertTrue(res.changed)
        self.assertIn("Database '{}' created successfully".format(db_name), res.msg)

    def test_create_already_created_database(self):
        store = self.test_driver.get_document_store(database="test_create_already_created_database")
        self.addCleanup(store.close)
        ctx = self._ctx(store)
        db_name = "test_db1"

        rec = DatabaseReconciler(ctx)
        res1 = rec.ensure_present(self._spec(db_name), TLSConfig(), check_mode=False)
        res2 = rec.ensure_present(self._spec(db_name), TLSConfig(), check_mode=False)

        self.assertTrue(res1.changed)
        self.assertFalse(res2.changed)
        self.assertIn("already exists", res2.msg)

    def test_delete_database(self):
        store = self.test_driver.get_document_store(database="test_delete_database")
        self.addCleanup(store.close)
        ctx = self._ctx(store)
        db_name = "test_db2"

        rec = DatabaseReconciler(ctx)
        rec.ensure_present(self._spec(db_name), TLSConfig(), check_mode=False)
        res = rec.ensure_absent(db_name, check_mode=False)

        self.assertTrue(res.changed)
        self.assertIn("Database '{}' deleted successfully".format(db_name), res.msg)

    def test_delete_non_exist_database(self):
        store = self.test_driver.get_document_store(database="test_delete_non_exist_database")
        self.addCleanup(store.close)
        ctx = self._ctx(store)
        db_name = "test_db3"

        rec = DatabaseReconciler(ctx)
        res = rec.ensure_absent(db_name, check_mode=False)

        self.assertFalse(res.changed)
        self.assertIn("Database '{}' does not exist".format(db_name), res.msg)

    def test_apply_database_settings(self):
        store = self.test_driver.get_document_store(database="test_apply_database_settings")
        self.addCleanup(store.close)
        ctx = self._ctx(store)
        db_name = "test_db_settings"

        rec = DatabaseReconciler(ctx)
        rec.ensure_present(self._spec(db_name), TLSConfig(), check_mode=False)

        desired_settings = {"Indexing.MapBatchSize": "64"}

        with patch.object(setsvc, "get_current", return_value={}), patch.object(setsvc, "apply", return_value=None):
            res = rec.ensure_present(self._spec(db_name, settings=desired_settings), TLSConfig(), check_mode=False)

        self.assertTrue(res.changed)
        self.assertIn("Applied settings (Indexing.MapBatchSize) and reloaded", res.msg)

    def test_apply_database_settings_check_mode(self):
        store = self.test_driver.get_document_store(database="test_apply_database_settings_check")
        self.addCleanup(store.close)
        ctx = self._ctx(store)
        db_name = "test_db_settings_check"

        rec = DatabaseReconciler(ctx)
        rec.ensure_present(self._spec(db_name), TLSConfig(), check_mode=False)

        desired_settings = {"Indexing.MapBatchSize": "64"}

        with patch.object(setsvc, "get_current", return_value={}):
            res = rec.ensure_present(self._spec(db_name, settings=desired_settings), TLSConfig(), check_mode=True)

        self.assertTrue(res.changed)
        self.assertIn("Would apply settings (Indexing.MapBatchSize) and reload", res.msg)


class TestValidationFunctions(TestCase):
    def test_valid_url(self):
        self.assertTrue(is_valid_url("https://example.com"))
        self.assertTrue(is_valid_url("http://localhost:8080"))
        self.assertFalse(is_valid_url("example.com"))
        self.assertFalse(is_valid_url("://invalid-url"))

    def test_valid_database_name(self):
        self.assertTrue(is_valid_database_name("valid_db"))
        self.assertTrue(is_valid_database_name("Valid-DB-123"))
        self.assertFalse(is_valid_database_name("Invalid DB!"))
        self.assertFalse(is_valid_database_name(""))

    def test_valid_replication_factor(self):
        self.assertTrue(is_valid_replication_factor(1))
        self.assertTrue(is_valid_replication_factor(5))
        self.assertFalse(is_valid_replication_factor(0))
        self.assertFalse(is_valid_replication_factor(-1))
        self.assertFalse(is_valid_replication_factor("two"))

    def test_valid_certificate_paths(self):
        with open("test_cert.pem", "w") as f:
            f.write("dummy certificate content")
        with open("test_ca.pem", "w") as f:
            f.write("dummy CA content")

        self.assertEqual(validate_paths_exist("test_cert.pem", "test_ca.pem"), (True, None))
        self.assertEqual(
            validate_paths_exist("non_existing.pem"),
            (False, "Path does not exist: non_existing.pem"),
        )

        os.remove("test_cert.pem")
        os.remove("test_ca.pem")

    def test_valid_state(self):
        self.assertTrue(is_valid_state("present"))
        self.assertTrue(is_valid_state("absent"))
        self.assertFalse(is_valid_state("running"))
        self.assertFalse(is_valid_state(""))
