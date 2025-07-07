# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible_collections.ravendb.ravendb.plugins.modules.index import (
    enable_index,
    disable_index,
    resume_index,
    pause_index,
    reset_index,
    create_dynamic_index)
from ravendb_test_driver import RavenTestDriver
from unittest import TestCase
from ravendb.documents.indexes.definitions import IndexRunningStatus
from ravendb.documents.operations.indexes import GetIndexingStatusOperation


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

    def create_and_execute_index(self, store):
        DynamicIndexClass = create_dynamic_index(
            self.index_name, self.index_definition)
        index = DynamicIndexClass()
        index.execute(store, store.database)

    def test_disable_index(self):
        cls = self.__class__
        store = self.test_driver.get_document_store(
            database="test_disable_index")
        self.create_and_execute_index(store)

        status, changed, message = disable_index(
            store, cls.index_name, cluster_wide=False, check_mode=False)
        self.assertEqual(status, "ok")
        self.assertTrue(changed)
        self.assertIn(
            "Index '{}' disbaled successfully".format(cls.index_name),
            message)

    def test_enable_index(self):
        cls = self.__class__
        store = self.test_driver.get_document_store(
            database="test_enable_index")
        self.create_and_execute_index(store)

        status, changed, message = disable_index(
            store, cls.index_name, cluster_wide=False, check_mode=False)
        status, changed, message = enable_index(
            store, cls.index_name, cluster_wide=False, check_mode=False)
        self.assertEqual(status, "ok")
        self.assertTrue(changed)
        self.assertIn(
            "Index '{}' enabled successfully".format(cls.index_name),
            message)

    def test_pause_index(self):
        cls = self.__class__
        store = self.test_driver.get_document_store(
            database="test_pause_index")
        self.create_and_execute_index(store)

        resume_index(store, cls.index_name, check_mode=False)
        status, changed, message = pause_index(
            store, cls.index_name, check_mode=False)
        self.assertEqual(status, "ok")
        self.assertTrue(changed)
        self.assertIn("Index '{}' paused successfully".format(cls.index_name), message)

        indexing_status = store.maintenance.send(GetIndexingStatusOperation())
        paused_index = [
            x for x in indexing_status.indexes if x.name == cls.index_name][0]
        self.assertEqual(paused_index.status, IndexRunningStatus.PAUSED)

    def test_pause_already_paused_index(self):
        cls = self.__class__
        store = self.test_driver.get_document_store(
            database="test_pause_already_paused_index")
        self.create_and_execute_index(store)

        pause_index(store, cls.index_name, check_mode=False)
        status, changed, message = pause_index(
            store, cls.index_name, check_mode=False)
        self.assertEqual(status, "ok")
        self.assertFalse(changed)
        self.assertIn("Index '{}' is already paused".format(cls.index_name), message)

        indexing_status = store.maintenance.send(GetIndexingStatusOperation())
        paused_index = [
            x for x in indexing_status.indexes if x.name == cls.index_name][0]
        self.assertEqual(paused_index.status, IndexRunningStatus.PAUSED)

    def test_resume_index(self):
        cls = self.__class__
        store = self.test_driver.get_document_store(
            database="test_resume_index")
        self.create_and_execute_index(store)

        pause_index(store, cls.index_name, check_mode=False)
        status, changed, message = resume_index(
            store, cls.index_name, check_mode=False)
        self.assertEqual(status, "ok")
        self.assertTrue(changed)
        self.assertIn(
            "Index '{}' resumed successfully".format(cls.index_name),
            message)

        indexing_status = store.maintenance.send(GetIndexingStatusOperation())
        resumed_index = [
            x for x in indexing_status.indexes if x.name == cls.index_name][0]
        self.assertEqual(resumed_index.status, IndexRunningStatus.RUNNING)

    def test_resume_already_resumed_index(self):
        cls = self.__class__
        store = self.test_driver.get_document_store(
            database="test_resume_already_resumed_index")
        self.create_and_execute_index(store)

        status, changed, message = resume_index(
            store, cls.index_name, check_mode=False)

        status, changed, message = resume_index(
            store, cls.index_name, check_mode=False)
        self.assertEqual(status, "ok")
        self.assertFalse(changed)
        self.assertIn(
            "Index '{}' is already resumed and executing".format(cls.index_name),
            message)

        indexing_status = store.maintenance.send(GetIndexingStatusOperation())
        resumed_index = [
            x for x in indexing_status.indexes if x.name == cls.index_name][0]
        self.assertEqual(resumed_index.status, IndexRunningStatus.RUNNING)

    def test_reset_index(self):
        cls = self.__class__
        store = self.test_driver.get_document_store(
            database="test_reset_index")
        self.create_and_execute_index(store)

        status, changed, message = reset_index(
            store, cls.index_name, check_mode=False)
        self.assertEqual(status, "ok")
        self.assertTrue(changed)
        self.assertIn("Index '{}' reset successfully".format(cls.index_name), message)
