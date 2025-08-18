# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

import os
from ravendb_test_driver import RavenTestDriver
from unittest import TestCase
from ansible_collections.ravendb.ravendb.plugins.modules.database import (
    handle_present_state,
    handle_absent_state,
    is_valid_url,
    is_valid_database_name,
    is_valid_replication_factor,
    validate_paths,
    is_valid_state,
    is_valid_database_name,
    is_valid_replication_factor,
    is_valid_state
)


class TestDBStateValidator(TestCase):

    def setUp(self):
        super().setUp()
        self.test_driver = RavenTestDriver()

    def test_create_database(self):

        store = self.test_driver.get_document_store(
            database="test_create_database")

        db_name = "test_db"
        check_mode = False

        changed, message = handle_present_state(store, db_name, 1, "http://localhost:8080", None, False, False, None, None, {}, check_mode)

        self.assertTrue(changed)
        self.assertIn("Database '{}' created successfully.".format(db_name), message)

    def test_create_already_created_database(self):

        store = self.test_driver.get_document_store(
            database="test_create_already_created_database")

        db_name = "test_db1"
        check_mode = False

        changed, message = handle_present_state(store, db_name, 1, "http://localhost:8080", None, False, False, None, None, {}, check_mode)
        changed, message = handle_present_state(store, db_name, 1, "http://localhost:8080", None, False, False, None, None, {}, check_mode)

        self.assertFalse(changed)
        self.assertIn("Database '{}' already exists.".format(db_name), message)

    def test_delete_database(self):

        store = self.test_driver.get_document_store(
            database="test_delete_database")

        db_name = "test_db2"
        replication_factor = 1
        check_mode = False

        changed, message = handle_present_state(store, db_name, 1, "http://localhost:8080", None, False, False, None, None, {}, check_mode)
        changed, message = handle_absent_state(store, db_name, check_mode)

        self.assertTrue(changed)
        self.assertIn("Database '{}' deleted successfully.".format(db_name), message)

    def test_delete_non_exist_database(self):

        store = self.test_driver.get_document_store(
            database="test_delete_non_exist_database")

        db_name = "test_db3"
        check_mode = False

        changed, message = handle_absent_state(store, db_name, check_mode)

        self.assertFalse(changed)
        self.assertIn("Database '{}' does not exist.".format(db_name), message)


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

        self.assertEqual(
            validate_paths(
                "test_cert.pem", "test_ca.pem"), (True, None))
        self.assertEqual(validate_paths("non_existing.pem"),
                         (False, "Path does not exist: non_existing.pem"))

        os.remove("test_cert.pem")
        os.remove("test_ca.pem")

    def test_valid_state(self):
        self.assertTrue(is_valid_state("present"))
        self.assertTrue(is_valid_state("absent"))
        self.assertFalse(is_valid_state("running"))
        self.assertFalse(is_valid_state(""))
