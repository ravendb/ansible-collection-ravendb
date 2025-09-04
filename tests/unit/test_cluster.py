# tests/unit/test_cluster.py
# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from unittest import TestCase
from unittest.mock import patch, Mock
from types import SimpleNamespace

from ansible_collections.ravendb.ravendb.plugins.module_utils.core.validation import (
    is_valid_url, is_valid_tag
)

from ansible_collections.ravendb.ravendb.plugins.module_utils.reconcilers.node_reconciler import NodeReconciler
from ansible_collections.ravendb.ravendb.plugins.module_utils.dto.node import NodeSpec
from ansible_collections.ravendb.ravendb.plugins.module_utils.core.tls import TLSConfig


class TestAddNodeWithRavenDB(TestCase):

    def setUp(self):
        self.leader_url = "http://localhost:8080"

    def _ctx(self):
        return SimpleNamespace(store=SimpleNamespace(urls=[self.leader_url]))

    def _empty_topology(self):
        return {"Topology": {"Members": {}, "Watchers": {}, "Promotables": {}}}

    def test_add_node_success(self):
        with patch("requests.get") as mock_get, patch("requests.put") as mock_put:
            mock_get.return_value = Mock(status_code=200)
            mock_get.return_value.json.return_value = self._empty_topology()

            mock_put.return_value = Mock(status_code=200)

            spec = NodeSpec(tag="B", node_type="Member", url="http://localhost:8081", leader_url=self.leader_url)
            rec = NodeReconciler(self._ctx())
            res = rec.ensure_present(spec, TLSConfig(), check_mode=False)

            self.assertTrue(res.changed)
            self.assertEqual(res.msg, "Node 'B' added as Member.")

    def test_add_node_check_mode(self):
        with patch("requests.get") as mock_get:
            mock_get.return_value = Mock(status_code=200)
            mock_get.return_value.json.return_value = self._empty_topology()

            spec = NodeSpec(tag="B", node_type="Member", url="http://localhost:8081", leader_url=self.leader_url)
            rec = NodeReconciler(self._ctx())
            res = rec.ensure_present(spec, TLSConfig(), check_mode=True)

            self.assertTrue(res.changed)
            self.assertEqual(res.msg, "Node 'B' would be added as Member.")

    def test_add_watcher_node(self):
        with patch("requests.get") as mock_get, patch("requests.put") as mock_put:
            mock_get.return_value = Mock(status_code=200)
            mock_get.return_value.json.return_value = self._empty_topology()

            mock_put.return_value = Mock(status_code=200)

            spec = NodeSpec(tag="D", node_type="Watcher", url="http://localhost:8083", leader_url=self.leader_url)
            rec = NodeReconciler(self._ctx())
            res = rec.ensure_present(spec, TLSConfig(), check_mode=False)

            self.assertTrue(res.changed)
            self.assertEqual(res.msg, "Node 'D' added as Watcher.")

    def test_add_already_added_node(self):
        with patch("requests.get") as mock_get, patch("requests.put") as mock_put:
            mock_get.return_value = Mock(status_code=200)
            mock_get.return_value.json.return_value = self._empty_topology()

            err_resp = Mock(status_code=400)
            err_resp.json.return_value = {"Message": "System.InvalidOperationException: Can't add a new node"}
            err_resp.text = "System.InvalidOperationException: Can't add a new node"
            mock_put.return_value = err_resp

            spec = NodeSpec(tag="A", node_type="Member", url="http://localhost:8081", leader_url=self.leader_url)
            rec = NodeReconciler(self._ctx())
            res = rec.ensure_present(spec, TLSConfig(), check_mode=False)

            self.assertFalse(res.changed)
            self.assertIn("Failed to add node 'A'", res.msg)

    def test_add_node_with_existing_tag_different_url(self):
        with patch("requests.get") as mock_get, patch("requests.put") as mock_put:
            mock_get.return_value = Mock(status_code=200)
            mock_get.return_value.json.return_value = self._empty_topology()

            err_resp = Mock(status_code=409)
            err_resp.json.side_effect = Exception("no json")
            err_resp.text = "System.InvalidOperationException: Was requested to modify the topology for node..."
            mock_put.return_value = err_resp

            spec = NodeSpec(tag="A", node_type="Member", url="http://localhost:9090", leader_url=self.leader_url)
            rec = NodeReconciler(self._ctx())
            res = rec.ensure_present(spec, TLSConfig(), check_mode=False)

            self.assertFalse(res.changed)
            self.assertIn("Failed to add node 'A'", res.msg)

    def test_node_already_present(self):
        with patch("requests.get") as mock_get:
            mock_get.return_value = Mock(status_code=200)
            mock_get.return_value.json.return_value = {
                "Topology": {
                    "Members": {"B": "http://localhost:8081"},
                    "Watchers": {},
                    "Promotables": {}
                }
            }

            spec = NodeSpec(tag="B", node_type="Member", url="http://localhost:8081", leader_url=self.leader_url)
            rec = NodeReconciler(self._ctx())
            res = rec.ensure_present(spec, TLSConfig(), check_mode=False)

            self.assertFalse(res.changed)
            self.assertEqual(res.msg, "Node 'B' already present as Member at http://localhost:8081.")


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
