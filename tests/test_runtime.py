import contextlib
import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("check_runtime", Path(__file__).resolve().parents[1] / "scripts" / "check_runtime.py")
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


class RuntimeReviewTests(unittest.TestCase):
    def test_alertmanager_config_is_not_printed(self):
        data = {"config": {"original": "secret-token"},
                "cluster": {"status": "ready", "peers": [{}, {}, {}]},
                "versionInfo": {"version": "0.27.0"}}
        out = io.StringIO()
        with patch.object(runtime, "request", return_value=data), \
             patch.object(runtime.sys, "argv", ["check_runtime.py", "am-cluster"]), \
             contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(runtime.main(), 0)
        self.assertNotIn("secret-token", out.getvalue())
        self.assertIn('"peerCount": 3', out.getvalue())

    def test_failed_prometheus_api_is_not_reported_as_success(self):
        with patch.object(runtime, "request", return_value={"status": "error"}), \
             patch.object(runtime.sys, "argv", ["check_runtime.py", "rules"]), \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(runtime.main(), 1)

    def test_only_requested_rule_is_reported(self):
        data = {"status": "success", "data": {"groups": [{"name": "ingress", "rules": [
            {"name": "OtherRule"}, {"name": "IngressNginx5xxRateHigh", "health": "ok"}
        ]}]}}
        out = io.StringIO()
        with patch.object(runtime, "request", return_value=data), \
             patch.object(runtime.sys, "argv", ["check_runtime.py", "rules"]), \
             contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(runtime.main(), 0)
        self.assertNotIn("OtherRule", out.getvalue())
        self.assertIn("IngressNginx5xxRateHigh", out.getvalue())


if __name__ == "__main__":
    unittest.main()
