# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

import os
import sys
from ravendb_test_driver import RavenTestDriver
from unittest import TestCase

from ansible_collections.ravendb.ravendb.plugins.module_utils.core.validation import (
    is_valid_url,
    is_valid_name,
    is_valid_dict,
    validate_paths_exist,
    is_valid_state,
    is_valid_mode,
    is_valid_bool,
    validate_state_optional
)
from ansible_collections.ravendb.ravendb.plugins.module_utils.reconcilers.index_reconciler import (
    IndexReconciler,
)
from ansible_collections.ravendb.ravendb.plugins.module_utils.dto.index import (
    IndexSpec,
    IndexDefinitionSpec,
)
from ansible_collections.ravendb.ravendb.plugins.module_utils.core.client import StoreContext
from ravendb.documents.operations.indexes import GetIndexesOperation


INDEX_DEFINITION = {
    "map": [
        "from c in docs.Users select new { Name = c.name, UserCount = 1, OrderCount = 0, TotalCount = 1 }"
    ]
}

UPDATED_INDEX_DEFINITION = {
    "map": [
        "from c in docs.Users select new { Name = c.name, UserCount = 1, OrderCount = 0, TotalCount = 3 }"
    ]
}

MAP_REDUCE_INDEX_DEFINITION = {
    "map": [
        "from c in docs.Users select new { Name = c.name, UserCount = 1, OrderCount = 0, TotalCount = 1 }"
    ],
    "reduce": """
                from result in results
                group result by result.Name
                into g
                select new
                {
                Name = g.Key,
                UserCount = g.Sum(x => x.UserCount),
                OrderCount = g.Sum(x => x.OrderCount),
                TotalCount = g.Sum(x => x.TotalCount)
                }
            """,
}

MULTI_MAP_INDEX_DEFINITION = {
    "map": [
        "from c in docs.Users select new { Name = c.name, UserCount = 1, OrderCount = 0, TotalCount = 1 }",
        "from o in docs.Orders select new { Name = o.customer, UserCount = 0, OrderCount = 1, TotalCount = 1 }",
    ]
}


class TestReconcileState(TestCase):
    index_name = "test/index"

    def setUp(self):
        super().setUp()
        self.test_driver = RavenTestDriver()

    def _ctx(self, store):
        return StoreContext(store=store)

    def _spec(self, db, name, *, definition=None, mode=None, cluster_wide=False, configuration=None):
        return IndexSpec(
            db_name=db,
            name=name,
            definition=(IndexDefinitionSpec.from_dict(definition) if definition else None),
            mode=mode,
            cluster_wide=cluster_wide,
            configuration=configuration or {},
        )

    def test_create_index(self):
        store = self.test_driver.get_document_store(database="test_create_index")
        self.addCleanup(store.close)
        ctx = self._ctx(store)
        rec = IndexReconciler(ctx, store.database)

        status = rec.ensure_present(self._spec(store.database, "test_index", definition=INDEX_DEFINITION), check_mode=False)
        self.assertEqual(status.changed, True)
        self.assertIn("Index 'test_index' created successfully.", status.msg)

    def test_create_already_exists_index(self):
        store = self.test_driver.get_document_store(database="test_create_already_exists_index")
        self.addCleanup(store.close)
        ctx = self._ctx(store)
        rec = IndexReconciler(ctx, store.database)

        res1 = rec.ensure_present(self._spec(store.database, "myindex", definition=INDEX_DEFINITION), check_mode=False)
        self.assertTrue(res1.changed)
        self.assertIn("Index 'myindex' created successfully.", res1.msg)

        res2 = rec.ensure_present(self._spec(store.database, "myindex", definition=INDEX_DEFINITION), check_mode=False)
        self.assertFalse(res2.changed)
        self.assertIn("Index 'myindex' already exists.", res2.msg)

    def test_update_existing_index_with_modified_map(self):
        store = self.test_driver.get_document_store(database="test_update_existing_index_with_modified_map")
        self.addCleanup(store.close)
        ctx = self._ctx(store)
        rec = IndexReconciler(ctx, store.database)

        r1 = rec.ensure_present(self._spec(store.database, "test/index", definition=INDEX_DEFINITION), check_mode=False)
        self.assertTrue(r1.changed)
        self.assertIn("Index 'test/index' created successfully.", r1.msg)

        r2 = rec.ensure_present(self._spec(store.database, "test/index", definition=UPDATED_INDEX_DEFINITION), check_mode=False)
        self.assertTrue(r2.changed)
        self.assertIn("Index 'test/index' created successfully.", r2.msg)

        database_maintenance = store.maintenance.for_database(store.database)
        existing_indexes = database_maintenance.send(GetIndexesOperation(0, sys.maxsize))
        index = existing_indexes[0]

        existing_maps = list(map(str.strip, index.maps)) if index.maps else []
        expected_map_definition = UPDATED_INDEX_DEFINITION["map"]

        self.assertEqual(existing_maps[0], expected_map_definition[0])

    def test_update_existing_map_index_into_multi_map_index(self):
        store = self.test_driver.get_document_store(database="test_update_existing_map_index_into_multi_map_index")
        self.addCleanup(store.close)
        ctx = self._ctx(store)
        rec = IndexReconciler(ctx, store.database)

        r1 = rec.ensure_present(self._spec(store.database, "test/index", definition=INDEX_DEFINITION), check_mode=False)
        self.assertTrue(r1.changed)
        self.assertIn("Index 'test/index' created successfully.", r1.msg)

        r2 = rec.ensure_present(self._spec(store.database, "test/index", definition=MULTI_MAP_INDEX_DEFINITION), check_mode=False)
        self.assertTrue(r2.changed)
        self.assertIn("Index 'test/index' created successfully.", r2.msg)

        database_maintenance = store.maintenance.for_database(store.database)
        existing_indexes = database_maintenance.send(GetIndexesOperation(0, sys.maxsize))
        index = existing_indexes[0]

        existing_maps = sorted(list(map(str.strip, index.maps)) if index.maps else [])
        expected_map_definition = sorted(MULTI_MAP_INDEX_DEFINITION["map"])

        self.assertEqual(existing_maps[0], expected_map_definition[0])
        self.assertEqual(existing_maps[1], expected_map_definition[1])

    def test_update_existing_map_index_into_map_reduce_index(self):
        store = self.test_driver.get_document_store(database="test_update_existing_map_index_into_map_reduce_index")
        self.addCleanup(store.close)
        ctx = self._ctx(store)
        rec = IndexReconciler(ctx, store.database)

        r1 = rec.ensure_present(self._spec(store.database, "test/index", definition=INDEX_DEFINITION), check_mode=False)
        self.assertTrue(r1.changed)
        self.assertIn("Index 'test/index' created successfully.", r1.msg)

        r2 = rec.ensure_present(self._spec(store.database, "test/index", definition=MAP_REDUCE_INDEX_DEFINITION), check_mode=False)
        self.assertTrue(r2.changed)
        self.assertIn("Index 'test/index' created successfully.", r2.msg)

        database_maintenance = store.maintenance.for_database(store.database)
        existing_indexes = database_maintenance.send(GetIndexesOperation(0, sys.maxsize))
        index = existing_indexes[0]

        existing_maps = list(map(str.strip, index.maps)) if index.maps else []
        existing_reduce = getattr(index, "reduce", None)

        expected_map_definition = MAP_REDUCE_INDEX_DEFINITION["map"]
        expected_reduce_definition = MAP_REDUCE_INDEX_DEFINITION["reduce"]

        self.assertEqual(existing_maps[0], expected_map_definition[0])
        self.assertEqual(existing_reduce, expected_reduce_definition)

    def test_delete_index(self):
        store = self.test_driver.get_document_store(database="test_delete_index")
        self.addCleanup(store.close)
        ctx = self._ctx(store)
        rec = IndexReconciler(ctx, store.database)

        r1 = rec.ensure_present(self._spec(store.database, self.index_name, definition=INDEX_DEFINITION), check_mode=False)
        self.assertTrue(r1.changed)
        self.assertIn("Index 'test/index' created successfully.", r1.msg)

        r2 = rec.ensure_absent(self.index_name, check_mode=False)
        self.assertTrue(r2.changed)
        self.assertIn("Index 'test/index' deleted successfully.", r2.msg)

    def test_delete_nonexistent_index(self):
        store = self.test_driver.get_document_store(database="test_delete_nonexistent_index")
        self.addCleanup(store.close)

        ctx = self._ctx(store)
        rec = IndexReconciler(ctx, store.database)

        r = rec.ensure_absent(self.index_name, check_mode=False)
        self.assertFalse(r.changed)
        self.assertIn("Index 'test/index' is already absent.", r.msg)


class TestValidationFunctions(TestCase):
    def test_valid_url(self):
        self.assertTrue(is_valid_url("https://example.com"))
        self.assertTrue(is_valid_url("http://localhost:8080"))
        self.assertFalse(is_valid_url("example.com"))
        self.assertFalse(is_valid_url("://invalid-url"))

    def test_valid_database_name(self):
        self.assertTrue(is_valid_name("valid_db"))
        self.assertTrue(is_valid_name("Valid-DB-123"))
        self.assertFalse(is_valid_name("Invalid DB!"))
        self.assertFalse(is_valid_name(""))

    def test_valid_index_name(self):
        self.assertTrue(is_valid_name("valid_index"))
        self.assertTrue(is_valid_name("Index-123"))
        self.assertFalse(is_valid_name("Invalid Index!"))
        self.assertFalse(is_valid_name(""))

    def test_valid_index_definition(self):
        self.assertTrue(is_valid_dict({"field": "value"}))
        self.assertTrue(is_valid_dict(None))
        self.assertFalse(is_valid_dict("not a dict"))
        self.assertFalse(is_valid_dict(["list"]))

    def test_valid_certificate_paths(self):
        with open("test_cert.pem", "w") as f:
            f.write("dummy certificate content")
        with open("test_ca.pem", "w") as f:
            f.write("dummy CA content")

        self.assertEqual(validate_paths_exist("test_cert.pem", "test_ca.pem"), (True, None))
        self.assertEqual(validate_paths_exist("non_existing.pem"), (False, "Path does not exist: non_existing.pem"))

        os.remove("test_cert.pem")
        os.remove("test_ca.pem")

    def test_valid_state(self):
        self.assertTrue(is_valid_state("present"))
        self.assertTrue(is_valid_state("absent"))
        self.assertFalse(is_valid_state("running"))
        ok, x = validate_state_optional(None)
        self.assertTrue(ok)

    def test_valid_mode(self):
        self.assertTrue(is_valid_mode("resumed"))
        self.assertTrue(is_valid_mode("paused"))
        self.assertTrue(is_valid_mode("enabled"))
        self.assertTrue(is_valid_mode("disabled"))
        self.assertTrue(is_valid_mode("reset"))
        self.assertTrue(is_valid_mode(None))
        self.assertFalse(is_valid_mode("invalid_mode"))

    def test_valid_cluster_wide(self):
        self.assertTrue(is_valid_bool(True))
        self.assertTrue(is_valid_bool(False))
        self.assertFalse(is_valid_bool(1))
        self.assertFalse(is_valid_bool("true"))
