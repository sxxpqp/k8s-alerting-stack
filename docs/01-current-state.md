# 现网基线与初步问题

证据来自用户 2026-11-04 提供的 kubectl / helm 输出。未将原始终端记录提交到公开仓库；其中包含内网地址。以下仅记录架构所需事实。

## 已确认

| 项目 | 现状 |
| --- | --- |
| Kubernetes | Server 1.28.0，kubectl 1.28.2 |
| Operator | monitoring/prometheus-operator，运行镜像 v0.91.0 |
| Prometheus | monitoring/k8s，2 副本，运行镜像 v3.11.3 |
| Alertmanager | monitoring/main，3 副本，运行镜像 v0.27.0 |
| PrometheusAlert | monitoring/prometheus-alert-center，单副本，镜像 feiyu563/prometheus-alert:v4.9.2 |
| 节点指标 | node-exporter，7 个就绪实例，运行镜像 v1.8.2 |
| K8s 对象指标 | kube-state-metrics v2.13.0 |
| 探测 | blackbox-exporter v0.25.0 |
| 当前 Grafana | observability/grafana，Helm chart 10.5.15，镜像 12.3.1 |
| 旧 Grafana | monitoring/grafana，0 副本；清单镜像拼写为 grafan/grafana:11.2.0，须回查，不自动修正或删除 |
| AlertmanagerConfig | 查询时没有资源；不代表没有通知配置，可能从 Secret 读取 |
| PodMonitor | 上传的查询结果中没有列出 PodMonitor；不直接推断未使用其他采集方式 |
| 访问 | Prometheus、Alertmanager、PrometheusAlert 已有 NodePort Service；具体 URL 与端口由本地采集结果核对 |

helm list -A 没有 Prometheus / Alertmanager / Operator 的 release。多个资源带 kube-prometheus labels，推测来自 kube-prometheus 清单，但还不能确认最初的仓库、分支和安装命令。不要运行 Helm install 来接管现有同名资源。

## 已看到的配置问题

1. `IngressNginx5xxRateHigh` 使用 `severity: warning`，只有 `summary`，没有 `description`。通知里出现级别和描述 `<no value>`；模板具体读取哪个字段仍需原文确认。
2. 表达式只按 `ingress` 聚合，移除了 instance / namespace；因此该规则不应强制展示“故障主机 IP”，且不同 namespace 同名 Ingress 可能被混算。
3. 当前规则未将触发值写入 annotations，通知层不能自动获得 PromQL 的 `$value`。
4. ServiceMonitor / PrometheusRule 的 labels 混用 `release=prometheus`、`release=kube-prometheus-stack`、`prometheus=k8s,role=alert-rules`。**这是待核对的选择器风险，不等于已证明没有被采集或加载。**
5. `node-export` 与 `node-exporter` 两个 ServiceMonitor 并存。需比较 selector、endpoints 和实际 Targets 后判断是否重复采集。
6. workload 镜像版本与部分资源的 version labels 不同，labels 可能未同步。运行镜像可用作观察证据，不能据此确认原始安装文件版本。
7. Alertmanager 3 副本和 Prometheus 2 副本不自动证明高可用有效。要验证 Prometheus 副本标签去重、Alertmanager 集群连通、PVC 和调度。
8. 原规则的 last-applied annotation 中存在旧拼写 `IngressNginx5xxRateHig`，而当前 spec 是 `IngressNginx5xxRateHigh`。排查以当前 spec 和 Prometheus 实际加载规则为准。

## 不在这轮顺带调整

现有 Loki、Promtail、Grafana、Longhorn 以及业务数据库的安装方式先保持原状。没有真实配置和验收数据前不升级组件、不扩副本、不更换存储、不修改全局选择器。

## 官方核对入口

- [Operator 监控发现](https://prometheus-operator.dev/docs/developer/getting-started/)
- [Operator 告警规则与路由](https://prometheus-operator.dev/docs/developer/alerting/)
- [Prometheus 告警规则与模板变量](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/)
- [PrometheusAlert 自定义模板](https://github.com/feiyu563/PrometheusAlert/blob/master/doc/readme/system-customtpl.md)

这些文档用于解释机制，不代替固定版本和目标集群验证。
