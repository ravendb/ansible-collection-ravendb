# tests/unit/test_cloud.py
# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from unittest import TestCase
from unittest.mock import patch, Mock

from ansible_collections.ravendb.ravendb.plugins.module_utils.cloud.client import RavenDBCloudClient
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

        self.assertFalse(is_valid_product_id("abc-123\n"))
        self.assertFalse(is_valid_product_id("abc/../foo"))
        self.assertFalse(is_valid_product_id("abc 123"))

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


CLIENT_MOD = "ansible_collections.ravendb.ravendb.plugins.module_utils.cloud.client"


class TestCloudClient(TestCase):

    def _mock_response(self, status_code, text="", content=b"", reason=""):
        resp = Mock()
        resp.status_code = status_code
        resp.text = text
        resp.content = content
        resp.reason = reason
        resp.ok = 200 <= status_code < 400
        resp.json = Mock(return_value={})
        return resp

    def test_client_treats_3xx_as_error_not_success(self):
        with patch(CLIENT_MOD + "._requests") as req_mod:
            req_mod.return_value.request.return_value = self._mock_response(
                302, text="Redirected", reason="Found",
            )
            client = RavenDBCloudClient(api_key="k")
            with self.assertRaises(RuntimeError) as ctx:
                client.get("/products/list")
            self.assertIn("302", str(ctx.exception))

    def test_client_retries_on_429_then_succeeds(self):
        with patch(CLIENT_MOD + "._requests") as req_mod, \
             patch(CLIENT_MOD + ".time.sleep") as sleep_mock:
            ok = self._mock_response(200, content=b"{}")
            ok.json = Mock(return_value={"result": "ok"})
            req_mod.return_value.request.side_effect = [
                self._mock_response(429, text="rate limited", reason="Too Many Requests"),
                self._mock_response(429, text="rate limited", reason="Too Many Requests"),
                ok,
            ]
            client = RavenDBCloudClient(api_key="k")
            self.assertEqual(client.get("/x"), {"result": "ok"})
            self.assertEqual(sleep_mock.call_count, 2)

    def test_client_gives_up_after_max_retries_on_429(self):
        with patch(CLIENT_MOD + "._requests") as req_mod, \
             patch(CLIENT_MOD + ".time.sleep"):
            req_mod.return_value.request.return_value = self._mock_response(
                429, text="rate limited", reason="Too Many Requests",
            )
            client = RavenDBCloudClient(api_key="k")
            with self.assertRaises(RuntimeError) as ctx:
                client.get("/x")
            self.assertIn("429", str(ctx.exception))

    def test_client_accepts_2xx(self):
        with patch(CLIENT_MOD + "._requests") as req_mod:
            resp = self._mock_response(200, content=b"{}")
            resp.json = Mock(return_value={"ok": True})
            req_mod.return_value.request.return_value = resp
            client = RavenDBCloudClient(api_key="k")
            self.assertEqual(client.get("/x"), {"ok": True})


CPS = "ansible_collections.ravendb.ravendb.plugins.module_utils.services.cloud_product_service"
CPLS = "ansible_collections.ravendb.ravendb.plugins.module_utils.services.cloud_product_lifecycle_service"


def _active_details(product_id="prod1", **overrides):
    details = {
        "id": product_id,
        "displayName": "my-prod",
        "subdomainName": None,
        "instanceType": "Dev10",
        "cloudProvider": "aws",
        "status": "Active",
        "tier": "Development",
        "region": "us-east-1",
        "releaseChannel": "Stable62",
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
        self._wait_patcher = patch(CPLS + ".wait_for_product_status")
        self._wait_mock = self._wait_patcher.start()
        self._wait_mock.side_effect = lambda client, pid, target, timeout: _active_details(pid, status=target)
        self.addCleanup(self._wait_patcher.stop)

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
            instance_type="Dev10",
            region="us-east-1",
            release_channel="Stable62",
            disk_size=10,
            storage_type="SsdStandard",
            tier="Development",
            allowed_ips=["203.0.113.10/32"],
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

    def test_create_payload_includes_throughput_and_iops(self):
        with patch(CPS + ".list_products") as list_p, \
             patch(CPLS + ".create_product") as create_p, \
             patch(CPS + ".get_product_details") as get_d:
            list_p.return_value = []
            create_p.return_value = {"productId": "new-id"}
            get_d.return_value = _active_details("new-id")

            spec = self._spec(
                cloud_provider="aws", instance_type="PB10", region="us-east-1",
                release_channel="Stable62", disk_size=100, storage_type="SsdPremium",
                tier="Production", allowed_ips=["192.0.2.1/32"], subdomain="my-prod",
                iops=4000, throughput=250.0,
            )
            self.reconciler.ensure_present(spec, check_mode=False)

            payload = create_p.call_args[0][1]
            self.assertEqual(payload.get("iops"), 4000)
            self.assertEqual(payload.get("throughput"), 250.0)

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

    def test_find_existing_is_case_insensitive(self):
        with patch(CPS + ".list_products") as list_p, \
             patch(CPS + ".get_product_details") as get_d, \
             patch(CPLS + ".create_product") as create_p:
            list_p.return_value = [{"id": "prod1", "name": "myprod"}]
            get_d.return_value = _active_details("prod1")

            spec = self._spec(name="MyProd")
            res = self.reconciler.ensure_present(spec, check_mode=False)

            self.assertFalse(res.changed)
            create_p.assert_not_called()

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

    def test_present_partial_storage_spec_fails_locally(self):
        with patch(CPS + ".list_products") as list_p, \
             patch(CPS + ".get_product_details") as get_d, \
             patch(CPLS + ".change_storage") as chg_s:
            list_p.return_value = [{"id": "prod1", "name": "my-prod"}]
            get_d.return_value = _active_details("prod1")

            spec = self._spec(iops=5000)
            res = self.reconciler.ensure_present(spec, check_mode=False)

            self.assertTrue(res.failed)
            self.assertIn("missing", res.msg.lower())
            self.assertIn("disk_size", res.msg)
            self.assertIn("storage_type", res.msg)
            chg_s.assert_not_called()

    def test_present_ssdpremium_without_throughput_fails_locally(self):
        with patch(CPS + ".list_products") as list_p, \
             patch(CPS + ".get_product_details") as get_d, \
             patch(CPLS + ".change_storage") as chg_s:
            list_p.return_value = [{"id": "prod1", "name": "my-prod"}]
            get_d.return_value = _active_details("prod1")

            spec = self._spec(disk_size=100, storage_type="SsdPremium", iops=5000)
            res = self.reconciler.ensure_present(spec, check_mode=False)

            self.assertTrue(res.failed)
            self.assertIn("throughput", res.msg)
            chg_s.assert_not_called()

    def test_present_single_data_disk_no_drift_is_noop(self):
        details = _active_details("prod1")
        details["hardwareInfo"] = {
            "storage": {"size": 8, "iops": None, "throughput": None, "type": "SsdStandard"},
            "additionalStorage": {"size": 50, "iops": 3000, "throughput": 125.0, "type": "SsdStandard"},
        }
        with patch(CPS + ".list_products") as list_p, \
             patch(CPS + ".get_product_details") as get_d, \
             patch(CPLS + ".change_storage") as chg_s:
            list_p.return_value = [{"id": "prod1", "name": "my-prod"}]
            get_d.return_value = details

            spec = self._spec(
                disk_layout="SingleDataDisk",
                disk_size=50,
                storage_type="SsdStandard",
                iops=3000,
                throughput=125.0,
            )
            res = self.reconciler.ensure_present(spec, check_mode=False)

            self.assertFalse(res.changed)
            self.assertIn("no drift", res.msg.lower())
            chg_s.assert_not_called()

    def test_present_single_data_disk_size_bump_applies(self):
        details = _active_details("prod1")
        details["hardwareInfo"] = {
            "storage": {"size": 8, "iops": None, "throughput": None, "type": "SsdStandard"},
            "additionalStorage": {"size": 50, "iops": 3000, "throughput": 125.0, "type": "SsdStandard"},
        }
        with patch(CPS + ".list_products") as list_p, \
             patch(CPS + ".get_product_details") as get_d, \
             patch(CPLS + ".change_storage") as chg_s, \
             patch(CPLS + ".wait_for_product_status") as wait_p:
            list_p.return_value = [{"id": "prod1", "name": "my-prod"}]
            get_d.return_value = details
            wait_p.return_value = details

            spec = self._spec(
                disk_layout="SingleDataDisk",
                disk_size=100,  # was 50
                storage_type="SsdStandard",
                iops=3000,
                throughput=125.0,
            )
            res = self.reconciler.ensure_present(spec, check_mode=False)

            self.assertTrue(res.changed)
            self.assertIn("storage", res.msg.lower())
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

    def test_allowed_ips_host_bits_normalized(self):
        details = _active_details("prod1")
        details["security"] = {"allowedIps": ["10.1.2.0/24"]}
        with patch(CPS + ".list_products") as list_p, \
             patch(CPS + ".get_product_details") as get_d:
            list_p.return_value = [{"id": "prod1", "name": "my-prod"}]
            get_d.return_value = details

            spec = self._spec(allowed_ips=["10.1.2.3/24"])
            res = self.reconciler.ensure_present(spec, check_mode=False)

            self.assertFalse(res.failed)
            self.assertFalse(res.changed)

    def test_allowed_ips_genuine_drift_still_detected(self):
        details = _active_details("prod1")
        details["security"] = {"allowedIps": ["10.1.2.0/24"]}
        with patch(CPS + ".list_products") as list_p, \
             patch(CPS + ".get_product_details") as get_d:
            list_p.return_value = [{"id": "prod1", "name": "my-prod"}]
            get_d.return_value = details

            spec = self._spec(allowed_ips=["10.9.9.0/24"])
            res = self.reconciler.ensure_present(spec, check_mode=False)

            self.assertTrue(res.failed)
            self.assertIn("allowed_ips", res.msg.lower())

    def test_subdomain_immutable_compare_is_case_insensitive(self):
        details = _active_details("prod1")
        details["subdomainName"] = "myprod"
        with patch(CPS + ".list_products") as list_p, \
             patch(CPS + ".get_product_details") as get_d:
            list_p.return_value = [{"id": "prod1", "name": "my-prod"}]
            get_d.return_value = details

            spec = self._spec(subdomain="MyProd")
            res = self.reconciler.ensure_present(spec, check_mode=False)

            self.assertFalse(res.failed)
            self.assertFalse(res.changed)

    def test_region_immutable_compare_is_case_insensitive(self):
        with patch(CPS + ".list_products") as list_p, \
             patch(CPS + ".get_product_details") as get_d:
            list_p.return_value = [{"id": "prod1", "name": "my-prod"}]
            get_d.return_value = _active_details("prod1")  # region="us-east-1"

            spec = self._spec(region="US-East-1")
            res = self.reconciler.ensure_present(spec, check_mode=False)

            self.assertFalse(res.failed)
            self.assertFalse(res.changed)

    def test_instance_type_drift_compare_is_case_insensitive(self):
        with patch(CPS + ".list_products") as list_p, \
             patch(CPS + ".get_product_details") as get_d, \
             patch(CPLS + ".change_instance_type") as chg_i:
            list_p.return_value = [{"id": "prod1", "name": "my-prod"}]
            get_d.return_value = _active_details("prod1")  # instanceType="Dev10"

            spec = self._spec(instance_type="dev10")
            res = self.reconciler.ensure_present(spec, check_mode=False)

            self.assertFalse(res.changed)
            chg_i.assert_not_called()

    def test_drift_with_wait_false_does_not_poll(self):
        with patch(CPS + ".list_products") as list_p, \
             patch(CPS + ".get_product_details") as get_d, \
             patch(CPLS + ".change_storage") as chg_s, \
             patch(CPLS + ".wait_for_product_status") as wait_p:
            list_p.return_value = [{"id": "prod1", "name": "my-prod"}]
            get_d.return_value = _active_details("prod1")

            spec = self._spec(
                wait=False,
                disk_size=20,
                storage_type="SsdStandard",
                iops=3000,
                throughput=125.0,
            )
            res = self.reconciler.ensure_present(spec, check_mode=False)

            self.assertTrue(res.changed)
            self.assertIn("wait=false", res.msg.lower())
            chg_s.assert_called_once()
            wait_p.assert_not_called()

    def test_drift_shares_one_deadline_across_storage_and_instance(self):
        with patch(CPS + ".list_products") as list_p, \
             patch(CPS + ".get_product_details") as get_d, \
             patch(CPLS + ".change_storage"), \
             patch(CPLS + ".change_instance_type"), \
             patch(CPLS + ".wait_for_product_status") as wait_p:
            list_p.return_value = [{"id": "prod1", "name": "my-prod"}]
            get_d.return_value = _active_details("prod1")
            wait_p.return_value = _active_details("prod1")

            spec = self._spec(
                wait=True, wait_timeout=600,
                disk_size=20, storage_type="SsdStandard", iops=3000, throughput=125.0,
                instance_type="PB10",
            )
            res = self.reconciler.ensure_present(spec, check_mode=False)

            self.assertTrue(res.changed)
            self.assertEqual(wait_p.call_count, 2)
            first_timeout = wait_p.call_args_list[0][0][3]
            second_timeout = wait_p.call_args_list[1][0][3]
            self.assertLessEqual(first_timeout, 600)
            self.assertLess(second_timeout, first_timeout + 0.001)

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

    def test_release_channel_compare_is_case_insensitive(self):
        details = _active_details("prod1")
        details["releaseChannel"] = "Stable62"
        with patch(CPS + ".list_products") as list_p, \
             patch(CPS + ".get_product_details") as get_d:
            list_p.return_value = [{"id": "prod1", "name": "my-prod"}]
            get_d.return_value = details

            spec = self._spec(release_channel="stable62")
            res = self.reconciler.ensure_present(spec, check_mode=False)

            self.assertFalse(res.failed)
            self.assertFalse(res.changed)

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
