#!/usr/bin/env bash
# =============================================================================
# 全链路告警通知测试
# =============================================================================
# 支持三种测试模式：
#   bash notifications/test.sh webhook    — 直连 PrometheusAlert 测试
#   bash notifications/test.sh am         — 通过 Alertmanager 完整链路测试
#   bash notifications/test.sh all        — 全部测一遍
# =============================================================================
source "$(dirname -- "${BASH_SOURCE[0]}")/../scripts/common.sh"
require curl python3

MODE="${1:-webhook}"
NS="monitoring"
PA_SVC="prometheusalert"
AM_SVC="kps-kube-prometheus-stack-alertmanager"

# 临时端口
PA_PORT="${PA_PORT:-18080}"
AM_PORT="${AM_PORT:-19093}"

# ----- 测试 Payload 生成 ---------------------------------------
gen_payload() {
  local status="$1"
  local alertname="${2:-${status^^}Test}"
  python3 - "$status" "$alertname" <<'PY'
import json, sys
from datetime import datetime, timedelta, timezone
now = datetime.now(timezone.utc)
status = sys.argv[1]
alertname = sys.argv[2]
if status == "firing":
    ends_at = "0001-01-01T00:00:00Z"
else:
    starts_at = (now - timedelta(minutes=10)).isoformat()
    ends_at = now.isoformat()
    status_name = "resolved"

payload = {
    "receiver": "notify-workwechat",
    "status": status,
    "alerts": [{
        "status": status,
        "labels": {
            "alertname": alertname,
            "severity": "critical",
            "cluster": "kind-kubesphere-341",
            "namespace": "monitoring",
            "pod": "test-pod-abc123",
            "container": "test-container",
            "node": "kind-worker",
            "instance": "192.168.1.100:9100",
            "service": "kube-prometheus-stack",
            "job": "external-node-exporter",
        },
        "annotations": {
            "description": "全链路连通性测试：Prometheus → Alertmanager → PrometheusAlert → 企业微信",
            "summary": "通知链路测试告警",
            "value": "100%",
            "threshold": "90%",
            "suggestion": "此为测试告警，无需处理。若在群内收到此消息则链路正常。",
            "runbook_url": "https://wiki.example.com/alerting/test"
        },
        "startsAt": (now - timedelta(minutes=5)).isoformat(),
        "endsAt": ends_at,
        "generatorURL": "http://prometheus:9090/graph?g0.expr=vector%281%29",
        "fingerprint": "test123"
    }],
    "groupLabels": {"alertname": alertname},
    "commonLabels": {"severity": "critical"},
    "commonAnnotations": {},
    "externalURL": "http://alertmanager:9093",
    "version": "4",
    "groupKey": '{}:{alertname="' + alertname + '"}'
}
print(json.dumps(payload))
PY
}

# ----- 模式 1：直连 PrometheusAlert webhook ----------------------
test_webhook() {
  echo "=== 测试 1：直连 PrometheusAlert Webhook ==="
  echo "发送 firing 告警..."
  local firing_payload
  firing_payload=$(gen_payload "firing" "WebhookFiringTest")
  curl -s --fail-with-body --show-error -X POST \
    -H 'Content-Type: application/json' \
    --data "$firing_payload" \
    "http://127.0.0.1:${PA_PORT}/prometheusalert?type=workwechat&tpl=prometheus-wx&wxurl=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test-only"
  echo ""

  sleep 1

  echo "发送 resolved 恢复告警..."
  local resolved_payload
  resolved_payload=$(gen_payload "resolved" "WebhookResolvedTest")
  curl -s --fail-with-body --show-error -X POST \
    -H 'Content-Type: application/json' \
    --data "$resolved_payload" \
    "http://127.0.0.1:${PA_PORT}/prometheusalert?type=workwechat&tpl=prometheus-wx&wxurl=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test-only"
  echo ""
  echo ""
  echo "✅ 直连测试完成。查看 PrometheusAlert 日志确认："
  echo "   kubectl -n monitoring logs deploy/prometheusalert --tail=10"
}

# ----- 模式 2：通过 Alertmanager API（全链路）------------------
test_am() {
  echo "=== 测试 2：Alertmanager 全链路 ==="
  echo "发送 firing 告警到 Alertmanager ..."

  local firing_payload
  firing_payload=$(gen_payload "firing" "AMFiringTest")
  curl -s --fail-with-body --show-error -X POST \
    -H 'Content-Type: application/json' \
    --data "[$(echo "$firing_payload" | python3 -c 'import sys,json; print(json.dumps(json.load(sys.stdin)["alerts"]))')]" \
    "http://127.0.0.1:${AM_PORT}/api/v2/alerts"
  echo ""

  sleep 2

  echo "发送 resolved 恢复告警到 Alertmanager（立即触发恢复通知）..."
  local resolved_payload
  resolved_payload=$(gen_payload "resolved" "AMResolvedTest")
  curl -s --fail-with-body --show-error -X POST \
    -H 'Content-Type: application/json' \
    --data "[$(echo "$resolved_payload" | python3 -c 'import sys,json; print(json.dumps(json.load(sys.stdin)["alerts"]))')]" \
    "http://127.0.0.1:${AM_PORT}/api/v2/alerts"
  echo ""
  echo ""
  echo "✅ 全链路测试完成。Alertmanager 已接收，等待 groupWait(30s) 后下发。"
  echo "   确认：kubectl -n monitoring logs deploy/prometheusalert --tail=20"
  echo "   注意：需填写真实企业微信 webhook URL 后才能在群内收到消息。"
}

# ----- 端口转发 ------------------------------------------------
setup_port_forward() {
  local svc="$1" local_port="$2"
  local remote_port="$3"
  if nc -z 127.0.0.1 "$local_port" 2>/dev/null; then
    return 0
  fi
  kubectl -n "$NS" port-forward "svc/${svc}" "${local_port}:${remote_port}" --address 0.0.0.0 &>/dev/null &
  sleep 2
}

cleanup() {
  pkill -f "port-forward.*svc/prometheusalert.*${PA_PORT}" 2>/dev/null
  pkill -f "port-forward.*svc/${AM_SVC}.*${AM_PORT}" 2>/dev/null
}
trap cleanup EXIT

# ----- 主逻辑 ------------------------------------------------
case "$MODE" in
  webhook)
    setup_port_forward "$PA_SVC" "$PA_PORT" 8080
    test_webhook
    ;;
  am)
    setup_port_forward "$PA_SVC" "$PA_PORT" 8080
    setup_port_forward "$AM_SVC" "$AM_PORT" 9093
    test_am
    ;;
  all)
    setup_port_forward "$PA_SVC" "$PA_PORT" 8080
    setup_port_forward "$AM_SVC" "$AM_PORT" 9093
    test_webhook
    echo ""
    echo "-----------------------------------------------"
    echo ""
    test_am
    ;;
  *)
    echo "用法：bash notifications/test.sh <webhook|am|all>"
    echo ""
    echo "  webhook — 直连 PrometheusAlert 测试（跳过 Alertmanager）"
    echo "  am      — 通过 Alertmanager 完整链路测试"
    echo "  all     — 两种都测"
    exit 1
    ;;
esac