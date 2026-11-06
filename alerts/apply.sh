#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/../scripts/common.sh"
bash alerts/check.sh
context
apply_files \
  alerts/node.rules.yaml \
  alerts/pods.rules.yaml \
  alerts/containers.rules.yaml \
  alerts/storage.rules.yaml \
  alerts/workloads.rules.yaml \
  alerts/jobs.rules.yaml \
  alerts/apiserver.rules.yaml \
  alerts/etcd.rules.yaml \
  alerts/middleware-kafka.rules.yaml \
  alerts/middleware-mysql.rules.yaml \
  alerts/middleware-redis.rules.yaml \
  alerts/ingress.rules.yaml \
  alerts/certmanager.rules.yaml \
  alerts/prometheus.rules.yaml
kubectl -n monitoring get prometheusrule -l release=kps