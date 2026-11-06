#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/../scripts/common.sh"
environment=${1:-test}
case "$environment" in
  test|prod) ;;
  *) echo '用法：bash prometheusalert/install.sh [test|prod]' >&2; exit 1 ;;
esac
configured prometheusalert/secret.yaml
context
apply_files prometheusalert/secret.yaml
kubectl apply --dry-run=server -k "prometheusalert/overlays/$environment" >/dev/null
kubectl apply -k "prometheusalert/overlays/$environment"
kubectl -n monitoring rollout restart deployment/prometheusalert
kubectl -n monitoring rollout status deployment/prometheusalert --timeout=5m
kubectl -n monitoring get pods -l app=prometheusalert -o wide