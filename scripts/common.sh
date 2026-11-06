#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

require() {
  local tool
  for tool in "$@"; do
    command -v "$tool" >/dev/null || { echo "缺少命令：$tool" >&2; exit 1; }
  done
}

configured() {
  local file
  for file in "$@"; do
    [[ -f "$file" ]] || { echo "文件不存在：$file" >&2; exit 1; }
    if grep -q 'REPLACE_' "$file"; then
      echo "请先填写 $file 中的 REPLACE_ 字段" >&2
      exit 1
    fi
  done
}

context() {
  require kubectl
  printf '目标集群：'
  kubectl config current-context
}

apply_files() {
  local file
  configured "$@"
  for file in "$@"; do
    kubectl apply --dry-run=server -f "$file" >/dev/null
  done
  for file in "$@"; do
    kubectl apply -f "$file"
  done
}
