# tests/unit/test_cluster.py
# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from unittest import TestCase
from unittest.mock import patch, Mock
from ansible_collections.ravendb.ravendb.plugins.modules.node import add_node, is_valid_url, is_valid_tag
import requests


class TestAddNodeWithRavenDB(TestCase):

    def setUp(self):
        self.leader_url = "http://localhost:8080"

    def test_add_node_success(self):
        with patch("requests.get") as mock_get, patch("requests.put") as mock_put:
            mock_get.return_value = Mock(status_code=200)
            mock_get.return_value.json.return_value = {"Topology": {"Members": {}, "Watchers": {}, "Promotables": {}}}

            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_put.return_value = mock_response

            result = add_node(
                tag="B",
                node_type="Member",
                url="http://localhost:8081",
                leader_url=self.leader_url,
                certificate_path=None,
                ca_cert_path=None,
                check_mode=False,
            )
            self.assertTrue(result["changed"])
            self.assertEqual(result["msg"], "Node B added to the cluster as Member.")

    def test_add_node_check_mode(self):
        with patch("requests.get") as mock_get:
            mock_get.return_value = Mock(status_code=200)
            mock_get.return_value.json.return_value = {"Topology": {"Members": {}, "Watchers": {}, "Promotables": {}}}

            result = add_node(
                tag="B",
                node_type="Member",
                url="http://localhost:8081",
                leader_url=self.leader_url,
                certificate_path=None,
                ca_cert_path=None,
                check_mode=True,
            )
            self.assertTrue(result["changed"])
            self.assertEqual(result["msg"], "Node B would be added to the cluster as Member.")

    def test_add_watcher_node(self):
        with patch("requests.get") as mock_get, patch("requests.put") as mock_put:
            mock_get.return_value = Mock(status_code=200)
            mock_get.return_value.json.return_value = {"Topology": {"Members": {}, "Watchers": {}, "Promotables": {}}}

            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_put.return_value = mock_response

            result = add_node(
                tag="D",
                node_type="Watcher",
                url="http://localhost:8083",
                leader_url=self.leader_url,
                certificate_path=None,
                ca_cert_path=None,
                check_mode=False,
            )
            self.assertTrue(result["changed"])
            self.assertEqual(result["msg"], "Node D added to the cluster as Watcher.")

    def test_add_already_added_node(self):
        with patch("requests.get") as mock_get, patch("requests.put") as mock_put:
            mock_get.side_effect = requests.RequestException("ex")

            mock_response = Mock()
            mock_response.raise_for_status.side_effect = requests.HTTPError(
                "System.InvalidOperationException: Can't add a new node")
            mock_put.return_value = mock_response

            result = add_node(
                tag="A",
                node_type="Member",
                url="http://localhost:8081",
                leader_url=self.leader_url,
                certificate_path=None,
                ca_cert_path=None,
                check_mode=False,
            )
            self.assertFalse(result["changed"])
            self.assertIn("Failed to add node A", result["msg"])

    def test_add_node_with_existing_tag_different_url(self):
        with patch("requests.get") as mock_get, patch("requests.put") as mock_put:
            mock_get.side_effect = requests.RequestException("ex")

            mock_response = Mock()
            mock_response.raise_for_status.side_effect = requests.HTTPError(
                "System.InvalidOperationException: Was requested to modify the topology for node...")
            mock_put.return_value = mock_response

            result = add_node(
                tag="A",
                node_type="Member",
                url="http://localhost:9090",
                leader_url=self.leader_url,
                certificate_path=None,
                ca_cert_path=None,
                check_mode=False,
            )
            self.assertFalse(result["changed"])
            self.assertIn("Failed to add node A", result["msg"])


class TestValidationFunctions(TestCase):
    def test_valid_url(self):
        self.assertTrue(is_valid_url("https://example.com"))
        self.assertTrue(is_valid_url("http://localhost:8080"))
        self.assertFalse(is_valid_url("example.com"))
        self.assertFalse(is_valid_url("://invalid-url"))
        self.assertFalse(is_valid_url(123))

    def test_valid_tag(self):
        self.assertTrue(is_valid_tag("A1"))
        self.assertTrue(is_valid_tag("BB"))
        self.assertFalse(is_valid_tag("AAAAA"))
        self.assertFalse(is_valid_tag("node1"))
        self.assertFalse(is_valid_tag("NODE-1"))
        self.assertFalse(is_valid_tag(""))
        self.assertFalse(is_valid_tag(123))
