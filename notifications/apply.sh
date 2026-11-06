#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/../scripts/common.sh"
if [[ $# -ne 0 ]]; then
  echo '用法：bash notifications/apply.sh' >&2
  exit 1
fi
configured notifications/secret.yaml notifications/prometheusalert.yaml
context
apply_files notifications/secret.yaml notifications/prometheusalert.yaml
kubectl -n monitoring get alertmanagerconfig -l release=kps