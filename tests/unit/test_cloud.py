# tests/unit/test_cloud.py
# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from unittest import TestCase
from unittest.mock import patch, Mock

from ansible_collections.ravendb.ravendb.plugins.module_utils.cloud.validation import (
    is_valid_api_key, validate_api_key,
    validate_api_url,
    is_valid_product_id, validate_product_id,
    is_valid_cloud_provider, validate_cloud_provider,
)

from ansible_collections.ravendb.ravendb.plugins.module_utils.dto.cloud_product import CloudProductSpec
from ansible_collections.ravendb.ravendb.plugins.module_utils.reconcilers.cloud_product_reconciler import CloudProductReconciler


class TestCloudValidation(TestCase):

    def test_api_key(self):
        self.assertTrue(is_valid_api_key("abc"))
        self.assertFalse(is_valid_api_key(""))
        self.assertFalse(is_valid_api_key(None))
        self.assertFalse(is_valid_api_key(123))

        ok, err = validate_api_key("abc")
        self.assertTrue(ok)
        self.assertIsNone(err)

        ok, err = validate_api_key("")
        self.assertFalse(ok)
        self.assertIn("api_key", err)

    def test_api_url(self):
        ok, _err = validate_api_url("https://api.cloud.ravendb.net")
        self.assertTrue(ok)

        ok, err = validate_api_url("not-a-url")
        self.assertFalse(ok)
        self.assertIn("Invalid api_url", err)

    def test_product_id(self):
        self.assertTrue(is_valid_product_id("abc-123"))
        self.assertFalse(is_valid_product_id(""))
        self.assertFalse(is_valid_product_id(None))

        ok, _err = validate_product_id("abc-123")
        self.assertTrue(ok)

        ok, err = validate_product_id("")
        self.assertFalse(ok)
        self.assertIn("product_id", err)

    def test_cloud_provider(self):
        self.assertTrue(is_valid_cloud_provider("aws"))
        self.assertTrue(is_valid_cloud_provider("azure"))
        self.assertTrue(is_valid_cloud_provider("gcp"))
        self.assertFalse(is_valid_cloud_provider("oracle"))

        ok, _err = validate_cloud_provider("aws")
        self.assertTrue(ok)

        ok, err = validate_cloud_provider("oracle")
        self.assertFalse(ok)
        self.assertIn("Invalid cloud_provider", err)


CPS = "ansible_collections.ravendb.ravendb.plugins.module_utils.services.cloud_product_service"
CPLS = "ansible_collections.ravendb.ravendb.plugins.module_utils.services.cloud_product_lifecycle_service"


def _active_details(product_id="prod1", **overrides):
    details = {
        "id": product_id,
        "displayName": "my-prod",
        "subdomainName": None,
        "instanceType": "Free",
        "cloudProvider": "aws",
        "status": "Active",
        "tier": "Free",
        "region": "us-east-1",
        "releaseChannel": "stable",
        "nodeTags": ["A"],
        "hardwareInfo": {
            "storage": {
                "size": 10,
                "iops": 3000,
                "throughput": 125.0,
                "type": "SsdStandard",
            }
        },
        "security": {"allowedIps": ["0.0.0.0/0"]},
    }
    details.update(overrides)
    return details


class TestCloudProductReconciler(TestCase):

    def setUp(self):
        self.client = Mock()
        self.reconciler = CloudProductReconciler(self.client)

    def _spec(self, **overrides):
        defaults = dict(
            name="my-prod",
            product_id=None,
            cloud_provider=None,
            instance_type=None,
            region=None,
            release_channel=None,
            disk_size=None,
            storage_type=None,
            tier=None,
            allowed_ips=None,
            subdomain=None,
            iops=None,
            throughput=None,
            disk_layout=None,
            deployment_type=None,
            hide_in_portal=False,
            wait=True,
            wait_timeout=1800,
        )
        defaults.update(overrides)
        return CloudProductSpec(**defaults)

    def _create_spec(self, **overrides):
        return self._spec(
            cloud_provider="aws",
            instance_type="Free",
            region="us-east-1",
            release_channel="stable",
            disk_size=10,
            storage_type="SsdStandard",
            tier="Free",
            allowed_ips=["0.0.0.0/0"],
            subdomain="my-prod",
            **overrides,
        )

    # ---------- create paths ----------

    def test_create_when_not_exists(self):
        with patch(CPS + ".list_products") as list_p, \
             patch(CPLS + ".create_product") as create_p, \
             patch(CPS + ".get_product_details") as get_d:
            list_p.return_value = []
            create_p.return_value = {"productId": "new-id"}
            get_d.return_value = _active_details("new-id")

            res = self.reconciler.ensure_present(self._create_spec(), check_mode=False)

            self.assertTrue(res.changed)
            self.assertIn("created", res.msg.lower())
            create_p.assert_called_once()

    def test_create_check_mode_does_not_call_api(self):
        with patch(CPS + ".list_products") as list_p, \
             patch(CPLS + ".create_product") as create_p:
            list_p.return_value = []

            res = self.reconciler.ensure_present(self._create_spec(), check_mode=True)

            self.assertTrue(res.changed)
            self.assertIn("would be created", res.msg.lower())
            create_p.assert_not_called()

    def test_create_missing_required_fields_fails(self):
        with patch(CPS + ".list_products") as list_p, \
             patch(CPLS + ".create_product") as create_p:
            list_p.return_value = []
            # missing region, release_channel, etc.
            spec = self._spec(cloud_provider="aws", instance_type="Free")

            res = self.reconciler.ensure_present(spec, check_mode=False)

            self.assertTrue(res.failed)
            self.assertIn("missing required fields", res.msg.lower())
            create_p.assert_not_called()

    # ---------- drift paths ----------

    def test_present_active_no_drift_is_noop(self):
        with patch(CPS + ".list_products") as list_p, \
             patch(CPS + ".get_product_details") as get_d:
            list_p.return_value = [{"id": "prod1", "name": "my-prod"}]
            get_d.return_value = _active_details("prod1")

            # spec with no drift-able fields set
            res = self.reconciler.ensure_present(self._spec(), check_mode=False)

            self.assertFalse(res.changed)
            self.assertIn("no drift", res.msg.lower())

    def test_present_storage_drift_applies(self):
        with patch(CPS + ".list_products") as list_p, \
             patch(CPS + ".get_product_details") as get_d, \
             patch(CPLS + ".change_storage") as chg_s:
            list_p.return_value = [{"id": "prod1", "name": "my-prod"}]
            get_d.return_value = _active_details("prod1")

            spec = self._spec(
                disk_size=20,            # was 10
                storage_type="SsdStandard",
                iops=3000,
                throughput=125.0,
            )
            res = self.reconciler.ensure_present(spec, check_mode=False)

            self.assertTrue(res.changed)
            self.assertIn("storage", res.msg.lower())
            chg_s.assert_called_once()

    def test_present_partial_storage_spec_calls_api(self):
        with patch(CPS + ".list_products") as list_p, \
             patch(CPS + ".get_product_details") as get_d, \
             patch(CPLS + ".change_storage") as chg_s, \
             patch(CPLS + ".wait_for_product_status") as wait_p:
            list_p.return_value = [{"id": "prod1", "name": "my-prod"}]
            get_d.return_value = _active_details("prod1")
            wait_p.return_value = _active_details("prod1")

            spec = self._spec(iops=5000)  # only iops set; module forwards to API
            res = self.reconciler.ensure_present(spec, check_mode=False)

            chg_s.assert_called_once()

    def test_present_instance_type_drift_applies(self):
        with patch(CPS + ".list_products") as list_p, \
             patch(CPS + ".get_product_details") as get_d, \
             patch(CPLS + ".change_instance_type") as chg_i:
            list_p.return_value = [{"id": "prod1", "name": "my-prod"}]
            get_d.return_value = _active_details("prod1")

            spec = self._spec(instance_type="PB10")  # was Free
            res = self.reconciler.ensure_present(spec, check_mode=False)

            self.assertTrue(res.changed)
            self.assertIn("instance_type", res.msg.lower())
            chg_i.assert_called_once()

    def test_present_immutable_field_drift_fails(self):
        with patch(CPS + ".list_products") as list_p, \
             patch(CPS + ".get_product_details") as get_d:
            list_p.return_value = [{"id": "prod1", "name": "my-prod"}]
            get_d.return_value = _active_details("prod1")

            spec = self._spec(region="eu-west-1")  # was us-east-1
            res = self.reconciler.ensure_present(spec, check_mode=False)

            self.assertTrue(res.failed)
            self.assertIn("immutable", res.msg.lower())

    def test_present_no_endpoint_field_drift_fails(self):
        with patch(CPS + ".list_products") as list_p, \
             patch(CPS + ".get_product_details") as get_d:
            list_p.return_value = [{"id": "prod1", "name": "my-prod"}]
            get_d.return_value = _active_details("prod1")

            spec = self._spec(release_channel="nightly")  # was stable
            res = self.reconciler.ensure_present(spec, check_mode=False)

            self.assertTrue(res.failed)
            self.assertIn("not supported", res.msg.lower())

    # ---------- absent paths ----------

    def test_absent_when_not_exists_is_noop(self):
        with patch(CPS + ".list_products") as list_p, \
             patch(CPLS + ".terminate_product") as term:
            list_p.return_value = []

            res = self.reconciler.ensure_absent(self._spec(), check_mode=False)

            self.assertFalse(res.changed)
            self.assertIn("already absent", res.msg.lower())
            term.assert_not_called()

    def test_absent_when_active_terminates(self):
        with patch(CPS + ".list_products") as list_p, \
             patch(CPS + ".get_product_details") as get_d, \
             patch(CPLS + ".terminate_product") as term:
            list_p.return_value = [{"id": "prod1", "name": "my-prod"}]
            get_d.side_effect = [
                _active_details("prod1"),                     # initial status read
                _active_details("prod1", status="Terminated"),  # after terminate, in wait loop
            ]

            res = self.reconciler.ensure_absent(self._spec(), check_mode=False)

            self.assertTrue(res.changed)
            self.assertIn("terminated", res.msg.lower())
            term.assert_called_once()

    def test_absent_when_already_terminated_is_noop(self):
        with patch(CPS + ".list_products") as list_p, \
             patch(CPS + ".get_product_details") as get_d, \
             patch(CPLS + ".terminate_product") as term:
            list_p.return_value = [{"id": "prod1", "name": "my-prod"}]
            get_d.return_value = _active_details("prod1", status="Terminated")

            res = self.reconciler.ensure_absent(self._spec(), check_mode=False)

            self.assertFalse(res.changed)
            self.assertIn("already terminated", res.msg.lower())
            term.assert_not_called()
