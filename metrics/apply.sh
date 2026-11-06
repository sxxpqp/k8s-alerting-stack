#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/../scripts/common.sh"
if [[ $# -eq 0 ]]; then
  echo '用法：bash metrics/apply.sh <yaml文件 | node | all>' >&2
  echo '  单个文件:  bash metrics/apply.sh metrics/servicemonitor.yaml' >&2
  echo '  节点监控:  bash metrics/apply.sh node' >&2
  echo '  全部部署:  bash metrics/apply.sh all' >&2
  exit 1
fi

context
case "$1" in
  all)
    FILES=(
      metrics/node-exporter-enhanced.yaml
      metrics/node-system-metrics.yaml
      metrics/node-kubelet-enhanced.yaml
    )
    ;;
  node)
    FILES=(
      metrics/node-exporter-enhanced.yaml
      metrics/node-system-metrics.yaml
      metrics/node-kubelet-enhanced.yaml
    )
    ;;
  *)
    FILES=("$1")
    ;;
esac

configured "${FILES[@]}"
apply_files "${FILES[@]}"
kubectl -n monitoring get servicemonitor,podmonitor,probe -l release=kps