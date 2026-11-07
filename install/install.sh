#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/../scripts/common.sh"
action=${1:-install}
case "$action" in
  install|upgrade) ;;
  *) echo '用法：bash install/install.sh [install|upgrade]' >&2; exit 1 ;;
esac
require helm
configured install/prom-values.yaml
context
if ! helm repo list 2>/dev/null | grep -q '^prometheus-community'; then
  helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
fi
helm repo update prometheus-community
if [[ "$action" == upgrade ]]; then
  helm get values kps -n monitoring > prom-values.before-upgrade.yaml
fi
helm "$action" kps prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace -f install/prom-values.yaml \
  --version 92.17.1 --dry-run=client >/dev/null
helm "$action" kps prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace -f install/prom-values.yaml \
  --version 92.17.1 --wait --timeout 10m
kubectl -n monitoring get prometheus,alertmanager,pods,pvc,svc