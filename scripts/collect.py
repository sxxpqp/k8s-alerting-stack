#!/usr/bin/env python3
"""Read-only Kubernetes inventory. Private exports are never safe to share wholesale."""
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def select_spec(resource, keys):
    # Missing fields remain absent; explicit {} and null are preserved.
    spec = resource.get("spec", {})
    return {key: spec[key] for key in keys if key in spec}


def center_references(resource):
    pod = resource.get("spec", {}).get("template", {}).get("spec", {})
    containers = []
    for item in pod.get("containers", []) + pod.get("initContainers", []):
        env = []
        for value in item.get("env", []):
            entry = {"name": value.get("name")}
            if "valueFrom" in value:
                entry["valueFrom"] = value["valueFrom"]
            elif "value" in value:
                entry["value"] = "REDACTED"
            env.append(entry)
        containers.append({
            "name": item.get("name"), "image": item.get("image"), "env": env,
            "envFrom": item.get("envFrom", []),
            "volumeMounts": item.get("volumeMounts", []),
        })
    volumes = []
    for volume in pod.get("volumes", []):
        entry = {"name": volume.get("name")}
        # Only reference names, no projected/downwardAPI values or hostPath paths.
        for kind, field in (("configMap", "name"), ("secret", "secretName"),
                            ("persistentVolumeClaim", "claimName")):
            if kind in volume:
                entry[kind] = {field: volume[kind].get(field)}
        volumes.append(entry)
    return {"containers": containers, "volumes": volumes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--namespace", default="monitoring")
    parser.add_argument("--prometheus", default="k8s")
    parser.add_argument("--alertmanager", default="main")
    parser.add_argument("--center", default="prometheus-alert-center")
    args = parser.parse_args()
    os.umask(0o077)
    if not shutil.which("kubectl"):
        parser.error("kubectl 不在 PATH")
    root = Path(__file__).resolve().parents[1] / ".local"
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out = root / ("inventory-" + stamp)
    private, review = out / "private", out / "review"
    private.mkdir(parents=True, mode=0o700)
    review.mkdir(mode=0o700)
    errors = []

    def run(name, command, structured=True):
        try:
            result = subprocess.run(command, capture_output=True, text=True,
                                    encoding="utf-8", timeout=45, check=True)
            data = json.loads(result.stdout) if structured else result.stdout
            if structured:
                save(private / (name + ".json"), data)
            else:
                (private / (name + ".txt")).write_text(data, encoding="utf-8")
            return data
        except (subprocess.SubprocessError, OSError, ValueError) as exc:
            # Detailed stderr stays private; it can include endpoints or proxy errors.
            errors.append({"name": name, "status": "failed", "error_type": type(exc).__name__})
            (private / (name + ".error.txt")).write_text(
                str(exc) + "\n" + (getattr(exc, "stderr", "") or ""), encoding="utf-8")
            return {}

    def get(name, kind, resource=None, namespace=None, all_ns=False):
        command = ["kubectl", "--request-timeout=30s", "get", kind]
        if resource:
            command.append(resource)
        if all_ns:
            command.append("-A")
        elif namespace:
            command += ["-n", namespace]
        return run(name, command + ["-o", "json"])

    context = run("context", ["kubectl", "config", "current-context"], False)
    if not context:
        save(review / "errors.json", errors)
        print("无法获取当前 context。详情仅保存在：", private)
        return 1
    print("只读采集 context:", context.strip())
    version = run("versions", ["kubectl", "--request-timeout=30s", "version", "-o", "json"])
    if shutil.which("helm"):
        run("helm-releases", ["helm", "list", "-A", "-o", "json"])
    else:
        errors.append({"name": "helm-releases", "status": "skipped", "reason": "helm not installed"})
    prom = get("prometheus", "prometheus.monitoring.coreos.com", args.prometheus, args.namespace)
    am = get("alertmanager", "alertmanager.monitoring.coreos.com", args.alertmanager, args.namespace)
    center = get("center", "deployment", args.center, args.namespace)
    for name, kind in (
        ("workloads", "deployment,statefulset,daemonset"), ("pods", "pods"),
        ("services", "services"), ("endpoints", "endpoints"),
        ("endpoint-slices", "endpointslices.discovery.k8s.io"), ("pvcs", "pvc"),
        ("service-monitors", "servicemonitors.monitoring.coreos.com"),
        ("pod-monitors", "podmonitors.monitoring.coreos.com"),
        ("rules", "prometheusrules.monitoring.coreos.com"),
        ("am-configs", "alertmanagerconfigs.monitoring.coreos.com"),
    ):
        get(name, kind, all_ns=True)
    get("storage-classes", "storageclasses.storage.k8s.io")
    ingress = get("ingress-rule", "prometheusrule.monitoring.coreos.com", "ingress-nginx", "ingress-nginx")
    for kind in ("configmap", "secret"):
        # No Secret or ConfigMap data is saved. Only their names are written.
        run(kind + "-names", ["kubectl", "--request-timeout=30s", "get", kind,
                             "-n", args.namespace, "-o", "name"], False)
    if prom:
        save(review / "prometheus-selection.json", select_spec(prom, (
            "serviceMonitorSelector", "serviceMonitorNamespaceSelector",
            "podMonitorSelector", "podMonitorNamespaceSelector",
            "ruleSelector", "ruleNamespaceSelector", "scrapeConfigSelector",
            "scrapeConfigNamespaceSelector", "externalLabels", "replicaExternalLabelName",
            "alerting", "additionalAlertRelabelConfigs", "additionalScrapeConfigs",
            "storage", "replicas", "version", "externalUrl", "routePrefix",
        )))
    if am:
        save(review / "alertmanager-selection.json", select_spec(am, (
            "configSecret", "alertmanagerConfigSelector", "alertmanagerConfigNamespaceSelector",
            "alertmanagerConfiguration", "replicas", "version", "externalUrl", "routePrefix", "storage",
        )))
    if center:
        save(review / "center-references.json", center_references(center))
    if ingress:
        metadata = ingress.get("metadata", {})
        save(review / "ingress-nginx-rule.json", {
            "metadata": {key: metadata[key] for key in ("name", "namespace", "labels") if key in metadata},
            "spec": ingress.get("spec", {}),
        })
    save(review / "inventory.json", {"context": context.strip(), "versions": version,
         "resources": {"namespace": args.namespace, "prometheus": args.prometheus,
                       "alertmanager": args.alertmanager, "center": args.center}})
    save(review / "errors.json", errors)
    print("原始备份（不要上传）：", private)
    print("字段白名单资料（人工检查后再分享）：", review)
    failures = [item for item in errors if item["status"] == "failed"]
    print("采集失败数：", len(failures), "；失败不等于资源不存在。")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
