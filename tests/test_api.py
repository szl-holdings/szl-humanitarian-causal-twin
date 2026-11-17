"""Loopback HTTP and field-deployment refusal tests."""
from __future__ import annotations

import copy
import http.client
import json
import threading
import unittest
from pathlib import Path

from szl_causal_twin.api import make_server
from szl_causal_twin.core import verify_receipt

BASE = Path(__file__).resolve().parents[1] / "examples" / "healthy-synthetic-water.json"


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = make_server(0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        if headers is None:
            headers = {}
        conn.request(method, path, body=body, headers=headers)
        rsp = conn.getresponse()
        content = rsp.read()
        conn.close()
        return rsp.status, json.loads(content)

    def post(self, obj, headers=None):
        body = json.dumps(obj).encode("utf-8") if not isinstance(obj, bytes) else obj
        h = {"Content-Type": "application/json"}
        h.update(headers or {})
        return self.request("POST", "/api/causal-twin/v1/evaluate", body, h)

    def test_frontend_returns_security_policy(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        conn.request("GET", "/")
        res = conn.getresponse()
        html = res.read().decode("utf-8")
        self.assertEqual(res.status, 200)
        self.assertIn("Content-Security-Policy", res.headers)
        self.assertIn("Not a physical safety system", html)
        conn.close()

    def test_frontend_javascript_is_local_and_read_only(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        conn.request("GET", "/ui.js")
        res = conn.getresponse()
        js = res.read().decode("utf-8")
        self.assertEqual(res.status, 200)
        self.assertIn("textContent", js)
        self.assertNotIn("innerHTML", js)
        conn.close()

    def test_example_endpoint_is_allowlisted(self):
        status, fixture = self.request("GET", "/api/causal-twin/v1/examples/imbalance")
        self.assertEqual(status, 200)
        self.assertIs(fixture["synthetic"], True)
        status, value = self.request("GET", "/api/causal-twin/v1/examples/../../private")
        self.assertEqual(status, 404)

    def test_health_is_liveness_not_qualification(self):
        status, value = self.request("GET", "/healthz")
        self.assertEqual(status, 200)
        self.assertFalse(value["field_qualified"])
        self.assertEqual(value["actuation"], "DENIED")

    def test_field_ready_refuses(self):
        status, value = self.request("GET", "/readyz")
        self.assertEqual(status, 503)
        self.assertFalse(value["ready"])

    def test_valid_evaluate_response_integrity(self):
        status, value = self.post(json.loads(BASE.read_text("utf-8")))
        self.assertEqual(status, 200)
        self.assertTrue(verify_receipt(value))
        self.assertEqual(value["decision"]["automated_actuation"], "DENIED")

    def test_disallowed_real_data_denied(self):
        x = json.loads(BASE.read_text("utf-8"))
        x["synthetic"] = False
        status, value = self.post(x)
        self.assertEqual(status, 400)
        self.assertEqual(value["error"], "invalid_or_unadmitted_evidence")

    def test_duplicate_json_keys_denied(self):
        status, value = self.post(b'{"schema_version":"good","schema_version":"evil"}')
        self.assertEqual(status, 400)

    def test_nonfinite_denied(self):
        status, value = self.post(b'{"schema_version":NaN}')
        self.assertEqual(status, 400)

    def test_invalid_host_denied(self):
        status, value = self.request("GET", "/healthz", headers={"Host": "evil.example"})
        self.assertEqual(status, 403)

    def test_mutation_invalid_host_denied(self):
        status, value = self.request("DELETE", "/api/causal-twin/v1/evaluate", headers={"Host": "evil.example"})
        self.assertEqual(status, 403)

    def test_mutation_refused(self):
        status, value = self.request("DELETE", "/api/causal-twin/v1/evaluate")
        self.assertEqual(status, 405)

    def test_large_body_refused(self):
        status, value = self.post(b"{" + b" "*131072 + b"}")
        self.assertEqual(status, 413)

    def test_unsupported_media_type_refused(self):
        status, value = self.post(b"{}", headers={"Content-Type": "text/plain"})
        self.assertEqual(status, 415)

    def test_query_path_not_accepted(self):
        status, value = self.request("GET", "/healthz?anything=1")
        self.assertEqual(status, 404)

    def test_capabilities_never_infer_model_training(self):
        status, value = self.request("GET", "/api/causal-twin/v1/capabilities")
        self.assertEqual(status, 200)
        self.assertFalse(value["model_trained"])
        self.assertFalse(value["real_facility_data_admitted"])


if __name__ == "__main__":
    unittest.main()
