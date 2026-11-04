import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import json
import subprocess
import tempfile

spec = importlib.util.spec_from_file_location("collect", Path(__file__).resolve().parents[1] / "scripts" / "collect.py")
collect = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collect)


class ReviewExportTests(unittest.TestCase):
    def test_read_only_collection_writes_review_without_inline_secrets(self):
        def fake_run(command, **kwargs):
            if command[0] == "helm":
                output = []
            elif command[1:3] == ["config", "current-context"]:
                return subprocess.CompletedProcess(command, 0, "test-cluster\n", "")
            elif "version" in command:
                output = {"serverVersion": {"gitVersion": "v1.28.0"}}
            else:
                self.assertIn("get", command)
                if command[-2:] == ["-o", "name"]:
                    return subprocess.CompletedProcess(command, 0, "secret/example\n", "")
                if "deployment" in command:
                    output = {"spec": {"template": {"spec": {"containers": [{
                        "name": "center", "env": [{"name": "TOKEN", "value": "NEVER_SHARE"}]
                    }]}}}}
                else:
                    output = {"spec": {"ruleSelector": {}, "replicas": 2}, "items": []}
            return subprocess.CompletedProcess(command, 0, json.dumps(output), "")

        with tempfile.TemporaryDirectory() as directory:
            with patch.object(collect, "__file__", str(Path(directory) / "scripts" / "collect.py")), \
                 patch.object(collect.shutil, "which", return_value="mock"), \
                 patch.object(collect.subprocess, "run", side_effect=fake_run), \
                 patch.object(collect.sys, "argv", ["collect.py"]):
                self.assertEqual(collect.main(), 0)
            reviews = list(Path(directory).glob(".local/inventory-*/review/*.json"))
            self.assertEqual(len(reviews), 6)
            self.assertNotIn("NEVER_SHARE", "".join(path.read_text(encoding="utf-8") for path in reviews))

    def test_missing_null_empty_selectors_remain_distinct(self):
        self.assertEqual(collect.select_spec({"spec": {"a": None, "b": {}}}, ("a", "b", "c")),
                         {"a": None, "b": {}})

    def test_center_export_does_not_copy_plaintext_secrets_or_args(self):
        resource = {"spec": {"template": {"spec": {
            "containers": [{"name": "center", "args": ["--token=SECRET"],
                "env": [{"name": "TOKEN", "value": "SECRET"},
                        {"name": "DB", "valueFrom": {"secretKeyRef": {"name": "db", "key": "url"}}}]}],
            "volumes": [{"name": "host", "hostPath": {"path": "/private"}},
                        {"name": "config", "configMap": {"name": "center-config"}}],
        }}}}
        output = collect.center_references(resource)
        self.assertNotIn("SECRET", str(output))
        self.assertNotIn("/private", str(output))
        self.assertEqual(output["containers"][0]["env"][1]["valueFrom"]["secretKeyRef"]["name"], "db")
        self.assertEqual(output["volumes"][1]["configMap"]["name"], "center-config")


if __name__ == "__main__":
    unittest.main()
