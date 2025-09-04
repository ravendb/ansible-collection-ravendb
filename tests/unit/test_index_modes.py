# tests/unit/test_index_modes.py
# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from ravendb_test_driver import RavenTestDriver
from unittest import TestCase

from ansible_collections.ravendb.ravendb.plugins.module_utils.core.client import StoreContext
from ansible_collections.ravendb.ravendb.plugins.module_utils.reconcilers.index_reconciler import IndexReconciler
from ansible_collections.ravendb.ravendb.plugins.module_utils.dto.index import IndexSpec, IndexDefinitionSpec


class TestIndexModes(TestCase):
    index_name = "TestIndex"
    index_definition = {
        "map": [
            "from c in docs.Users select new { c.name, count = 1 }"
        ],
        "reduce": """
               from result in results
               group result by result.name
               into g
               select new
               {
                     name = g.Key,
                     count = g.Sum(x => x.count)
               }
        """
    }

    def setUp(self):
        super().setUp()
        self.test_driver = RavenTestDriver()

    def _ctx(self, store):
        return StoreContext(store=store)

    def _rec(self, store):
        return IndexReconciler(self._ctx(store), store.database)

    def _create_index(self, store):
        spec = IndexSpec(
            db_name=store.database,
            name=self.index_name,
            definition=IndexDefinitionSpec.from_dict(self.index_definition),
            mode=None,
            cluster_wide=False,
            configuration={}
        )
        res = self._rec(store).ensure_present(spec, check_mode=False)
        self.assertFalse(res.failed)

    def test_disable_index(self):
        store = self.test_driver.get_document_store(database="test_disable_index")
        self.addCleanup(store.close)
        self._create_index(store)

        spec = IndexSpec(db_name=store.database, name=self.index_name, mode="disabled", cluster_wide=False)
        res = self._rec(store).ensure_present(spec, check_mode=False)
        self.assertTrue(res.changed)
        self.assertIn("disabled successfully", res.msg.lower())

    def test_enable_index(self):
        store = self.test_driver.get_document_store(database="test_enable_index")
        self.addCleanup(store.close)
        self._create_index(store)

        spec = IndexSpec(db_name=store.database, name=self.index_name, mode="disabled", cluster_wide=False)
        res = self._rec(store).ensure_present(spec, check_mode=False)
        self.assertTrue(res.changed)

        spec = IndexSpec(db_name=store.database, name=self.index_name, mode="enabled", cluster_wide=False)
        res = self._rec(store).ensure_present(spec, check_mode=False)
        self.assertTrue(res.changed)
        self.assertIn("enabled successfully", res.msg.lower())

    def test_pause_already_paused_index(self):
        store = self.test_driver.get_document_store(database="test_pause_already_paused_index")
        self.addCleanup(store.close)
        self._create_index(store)

        spec = IndexSpec(db_name=store.database, name=self.index_name, mode="paused")
        res = self._rec(store).ensure_present(spec, check_mode=False)
        self.assertTrue(res.changed)
        self.assertIn("paused successfully", res.msg.lower())

        res = self._rec(store).ensure_present(spec, check_mode=False)
        self.assertFalse(res.changed)
        self.assertIn("already paused", res.msg.lower())

    def test_resume_index(self):
        store = self.test_driver.get_document_store(database="test_resume_index")
        self.addCleanup(store.close)
        self._create_index(store)

        pause_spec = IndexSpec(db_name=store.database, name=self.index_name, mode="paused")
        self._rec(store).ensure_present(pause_spec, check_mode=False)

        spec = IndexSpec(db_name=store.database, name=self.index_name, mode="resumed")
        res = self._rec(store).ensure_present(spec, check_mode=False)
        self.assertTrue(res.changed)
        self.assertIn("resumed successfully", res.msg.lower())

    def test_resume_already_resumed_index(self):
        store = self.test_driver.get_document_store(database="test_resume_already_resumed_index")
        self.addCleanup(store.close)
        self._create_index(store)

        spec = IndexSpec(db_name=store.database, name=self.index_name, mode="resumed")
        res = self._rec(store).ensure_present(spec, check_mode=False)
        self.assertFalse(res.changed)
        self.assertIn("already running", res.msg.lower())

    def test_reset_index(self):
        store = self.test_driver.get_document_store(database="test_reset_index")
        self.addCleanup(store.close)
        self._create_index(store)

        spec = IndexSpec(db_name=store.database, name=self.index_name, mode="reset")
        res = self._rec(store).ensure_present(spec, check_mode=False)
        self.assertTrue(res.changed)
        self.assertIn("reset successfully", res.msg.lower())
