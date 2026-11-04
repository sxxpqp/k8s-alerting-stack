#!/usr/bin/env python3
"""Read-only HTTP checks through local kubectl port-forwards. No configuration writes."""
import argparse
import json
import sys
from urllib.parse import urlencode, urlparse
from urllib.request import urlopen


def request(base, path, params=None):
    url = base.rstrip("/") + path
    if params:
        url += "?" + urlencode(params)
    with urlopen(url, timeout=15) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("check", choices=("targets", "rules", "metric-labels", "alerts", "am-cluster"))
    parser.add_argument("--prometheus", default="http://127.0.0.1:19090")
    parser.add_argument("--alertmanager", default="http://127.0.0.1:19093")
    args = parser.parse_args()
    for base in (args.prometheus, args.alertmanager):
        parsed = urlparse(base)
        if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost"):
            parser.error("只支持本机 HTTP port-forward 地址；不要把凭据放进 URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
            parser.error("地址只包含本机主机与端口")
    try:
        if args.check == "am-cluster":
            raw = request(args.alertmanager, "/api/v2/status")
            cluster = raw.get("cluster", {})
            # Never print the API's config.original field: it can contain credentials.
            output = {"version": raw.get("versionInfo", {}).get("version"),
                      "clusterStatus": cluster.get("status"),
                      "peerCount": len(cluster.get("peers", []))}
        else:
            if args.check == "targets":
                raw = request(args.prometheus, "/api/v1/targets", {"state": "active"})
                output = [{"labels": {k: target.get("labels", {}).get(k) for k in
                           ("job", "namespace", "service", "pod", "instance")},
                           "health": target.get("health"), "lastError": target.get("lastError")}
                          for target in raw.get("data", {}).get("activeTargets", [])
                          if any(name in str(target.get("labels", {})).lower() for name in
                                 ("ingress", "node-export", "kube-state"))]
            elif args.check == "rules":
                raw = request(args.prometheus, "/api/v1/rules", {"type": "alert"})
                output = [{"group": group.get("name"), "file": group.get("file"), "rule": rule}
                          for group in raw.get("data", {}).get("groups", [])
                          for rule in group.get("rules", [])
                          if rule.get("name") == "IngressNginx5xxRateHigh"]
            elif args.check == "alerts":
                raw = request(args.prometheus, "/api/v1/alerts")
                output = [alert for alert in raw.get("data", {}).get("alerts", [])
                          if alert.get("labels", {}).get("alertname") in
                          ("IngressNginx5xxRateHigh", "AlertPipelineSmokeTest")]
            else:
                query = 'topk(20, count by (namespace, ingress, controller_class) (nginx_ingress_controller_requests{ingress!=""}))'
                raw = request(args.prometheus, "/api/v1/query", {"query": query})
                output = {"query": query, "sampleLimit": 20,
                          "result": raw.get("data", {}).get("result", [])}
            if raw.get("status") != "success":
                raise ValueError("Prometheus API 返回失败，请本地查看错误，不要公开凭据")
        print(json.dumps(output, ensure_ascii=False, indent=2))
        print("只读请求完成；是否通过请按手册核对内容，空结果不等于验证成功。", file=sys.stderr)
        return 0
    except Exception as exc:
        # Do not print response body or full URL, which could reveal local configuration.
        print("读取失败：" + type(exc).__name__ + "；检查 port-forward、端口和组件状态。", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
