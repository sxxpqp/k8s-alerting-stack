# 安装基础监控栈

基于 [kube-prometheus-stack](https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack) Helm Chart 部署 Prometheus + Alertmanager + Grafana。

## 安装

确认目标集群和 StorageClass：

```bash
kubectl config current-context
kubectl get nodes,storageclass
helm list -A
```

编辑 [prom-values.yaml](prom-values.yaml)，填写以下配置：

| 配置项 | 说明 | 当前值 |
|--------|------|--------|
| `cluster` | 集群标识 | `kind-kubesphere-341` |
| `storageClassName` | 存储类（3 处） | `standard` |
| `retentionSize` | Prometheus 数据上限 | `18GB` |
| `prometheus.storage.requests` | 每副本 PVC 容量 | `20Gi` |

> `retentionSize` 必须小于 PVC 容量并给 WAL 留余量。本地保留目标 24h，容量或时间先到者生效。

```bash
bash install/install.sh          # 首次安装
bash install/install.sh upgrade  # 后续升级
```

脚本流程：添加 Helm 仓库 → 预览 → 安装/升级 → 等待 Pod 就绪。

> 已有其他 Prometheus Operator 时先核对 CRD 归属，避免冲突。

## 验证

```bash
kubectl -n monitoring get prometheus,alertmanager,pods,pvc
kubectl -n monitoring get events --sort-by=.lastTimestamp
```

预期：Prometheus 2 副本、Alertmanager 3 副本、Grafana 1 副本全部 Ready，PVC 全部 Bound。

### 组件页面

```bash
# Prometheus
kubectl -n monitoring port-forward svc/kps-kube-prometheus-stack-prometheus 9090:9090
# → http://127.0.0.1:9090  检查 Targets 和 Rules

# Alertmanager
kubectl -n monitoring port-forward svc/kps-kube-prometheus-stack-alertmanager 9093:9093
# → http://127.0.0.1:9093  检查状态

# Grafana（默认数据源已配置）
kubectl -n monitoring port-forward svc/kps-grafana 3000:80
# → http://127.0.0.1:3000
```

Grafana 初始账号密码：

```bash
kubectl -n monitoring get secret kps-grafana -o jsonpath='{.data.admin-user}' | base64 -d; echo
kubectl -n monitoring get secret kps-grafana -o jsonpath='{.data.admin-password}' | base64 -d; echo
```

## 默认关闭的采集

Kind/kubeadm 环境中，以下控制面端点通常不可达，默认关闭：

- `kubeEtcd`（etcd 指标）
- `kubeScheduler`（调度器指标）
- `kubeControllerManager`（控制器指标）
- `kubeProxy`（kube-proxy 指标）

同时关闭了对应的内置告警规则和超过 24h 的长窗口 API SLO 规则。生产环境确认端点可达后可在 values 中重新开启。

## 更新与回滚

```bash
bash install/install.sh upgrade
```

脚本保存当前 values 到 `prom-values.before-upgrade.yaml`，预览后升级。

回滚：

```bash
helm history kps -n monitoring
helm rollback kps <REVISION> -n monitoring --wait --timeout 10m
```

> 回滚不还原 CRD、独立管理的 Secret/CR 或 PVC 数据。