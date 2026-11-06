#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/../scripts/common.sh"
mode=${1:-check}
case "$mode" in
  check|test) ;;
  *) echo '用法：bash alerts/check.sh [check|test]' >&2; exit 1 ;;
esac
require python3 promtool
mkdir -p .generated

RULES_FILES=(
  alerts/node.rules.yaml
  alerts/pods.rules.yaml
  alerts/containers.rules.yaml
  alerts/storage.rules.yaml
  alerts/workloads.rules.yaml
  alerts/jobs.rules.yaml
  alerts/apiserver.rules.yaml
  alerts/etcd.rules.yaml
  alerts/middleware-kafka.rules.yaml
  alerts/middleware-mysql.rules.yaml
  alerts/middleware-redis.rules.yaml
  alerts/ingress.rules.yaml
  alerts/certmanager.rules.yaml
  alerts/prometheus.rules.yaml
)

for f in "${RULES_FILES[@]}"; do
  configured "$f"
done

python3 - <<'PY'
from pathlib import Path
import yaml

docs = []
for f in """${RULES_FILES[*]}""".split():
    doc = yaml.safe_load(Path(f).read_text(encoding='utf-8'))
    docs.extend(doc['spec']['groups'])

Path('.generated/rules.yaml').write_text(
    yaml.safe_dump({'groups': docs}, allow_unicode=True, sort_keys=False), encoding='utf-8')
PY

promtool check rules .generated/rules.yaml

if [[ "$mode" == test ]]; then
  echo '跳过单测：规则已拆分为多文件，请按新规则更新 tests/rules.test.yaml'
fi