# 监控配置与运行态核对

观察时间：2026-11-04T16:22:53.111000+08:00（北京时间）；通过维护者提供的 Prometheus NodePort 地址只读获取。未修改配置、重载组件或发送测试消息。
本报告是该入口返回的快照，尚未逐个 Prometheus 副本验证。不要把瞬时健康结论当作持续健康保证。

## 已取得的证据

- 维护者提供的 22 个 ServiceMonitor spec。
- Prometheus 3.11.3 的实际生效抓取配置，32 个 scrape job；原始配置仅保存在本地，不上传公开仓库。
- 当前 130 个活动 Target，均为 UP。UP 表示抓取成功，不代表所有业务指标都存在或 Blackbox 探测目标都成功。
- 实际已加载 151 条告警规则，快照中 health 全部为 ok。执行无错误不代表表达式返回了任何序列。
- 指标名称目录 2915 项；该接口可能包含留存时段内的历史序列，不当作当前实时指标数。另用即时查询确认下列关键指标。
- PodMonitor / Probe / ScrapeConfig 的原始完整对象、PrometheusAlert 存储及所有组件安装源文件仍未拿全，不能声称已经具备完整重建配置。

## 实际采集 job

Target 是采集端点数，不等于机器数；同一 Pod 的不同端口或路径会产生多个 Target。

| job | 活动 Target | UP |
| --- | ---: | ---: |
| alertmanager-main | 6 | 6 |
| apiserver | 2 | 2 |
| bigdata-tracking-gateway | 1 | 1 |
| blackbox-exporter | 1 | 1 |
| blackbox-http-external | 50 | 50 |
| gitlab-process-exporter | 2 | 2 |
| ingress-nginx-controller-metrics | 1 | 1 |
| kube-controller-manager | 2 | 2 |
| kube-dns | 2 | 2 |
| kube-scheduler | 2 | 2 |
| kube-state-metrics | 2 | 2 |
| kubelet | 28 | 28 |
| mysqld-exporter | 1 | 1 |
| mysqld-exporter-241 | 1 | 1 |
| node-export | 8 | 8 |
| node-exporter | 7 | 7 |
| prometheus-adapter | 2 | 2 |
| prometheus-k8s | 4 | 4 |
| prometheus-operator | 1 | 1 |
| redis-cluster-metrics | 6 | 6 |
| sohu-nacos | 1 | 1 |

## ServiceMonitor 与实际 Target 对照

| ServiceMonitor | 活动 Target |
| --- | ---: |
| bigdata-test/bigdata-tracking-gateway | 1 |
| ingress-nginx/ingress-nginx | 1 |
| monitoring/alertmanager-main | 6 |
| monitoring/blackbox-exporter | 1 |
| monitoring/coredns | 2 |
| monitoring/gitlab-process-exporter | 2 |
| monitoring/grafana | 0 |
| monitoring/kube-apiserver | 2 |
| monitoring/kube-controller-manager | 2 |
| monitoring/kube-scheduler | 2 |
| monitoring/kube-state-metrics | 2 |
| monitoring/kubelet | 28 |
| monitoring/mysqld-exporter | 1 |
| monitoring/mysqld-exporter-241 | 1 |
| monitoring/nacos-monitor | 1 |
| monitoring/node-export | 8 |
| monitoring/node-exporter | 7 |
| monitoring/prometheus-adapter | 2 |
| monitoring/prometheus-k8s | 4 |
| monitoring/prometheus-operator | 1 |
| test/redis-cluster-monitor-test | 0 |
| uat/redis-cluster-monitor-uat | 6 |

## 已证实的盲区与配置问题

### 1. Grafana 有采集配置，但没有目标

monitoring/grafana 的 ServiceMonitor 仅在自身 monitoring namespace 选择 Service；当前该 scrape pool 没有活动 Target，也未查到 grafana_http_request_duration_seconds_count 当前序列。结合前面提供的资源清单：旧 monitoring/grafana 为 0 副本，当前运行 Grafana 在 observability。需进一步只读核对 Service 的标签/端口，再为实际 Grafana 设计采集。GrafanaRequestsFailing 虽已加载，却不能据此证明能检测当前 Grafana。

### 2. test Redis 配置没有匹配到活动 Target

test/redis-cluster-monitor-test 活动 Target 为 0，uat/redis-cluster-monitor-uat 为 6。不能直接判定 Redis 故障，也不能仅凭这份配置声称 test Redis 已被监控。下一步应看 test 的 Service / endpoints / exporter 是否仍部署或已经下线。当前 redis_up、redis_cluster_enabled、redis_cluster_state 的即时查询在 redis-cluster-metrics job 中均有 6 个序列，尚需逐一确认 namespace 标签归属。

### 3. MySQL 内存规则当前引用了无数据指标

mysql_global_status_innodb_buffer_pool_pages_data 当前没有序列，名称目录中也未找到；mysql_global_status_innodb_buffer_pool_bytes_data 和 mysql_global_variables_innodb_buffer_pool_size 在两个 MySQL job 中各有一个序列。现有规则不但页数/字节数单位不一致，而且分子指标当前无数据，会导致规则不触发而不是报执行错误。候选修复需要使用实际同单位指标，并重审阈值及“buffer pool 数据占用”与“主机内存占用”的语义，未应用任何修改。

MySQL 复制规则依赖的 mysql_slave_status_* 三个指标当前也没有序列。若这两个 MySQL 本来就是独立实例，可能只是未部署该功能；若期望监控复制链路，则是盲区。应把复制告警作为按实例角色选择的规则组。

### 4. TCP 探测规则当前没有依赖指标

probe_tcp_connection_success 即时查询无数据，名称目录中亦未找到。当前抓取配置发现的是 probe/monitoring/blackbox-http-external，50 个 Target；probe_success 有对应 50 个当前序列。不能把 HTTP Probe 当成已配置 TCP Probe，下一步获取 Probe 原始 spec 和 Blackbox 模块定义。

### 5. 两套节点采集并非同一批机器，告警覆盖不同

node-export 有 8 个地址，node-exporter 有 7 个 Kubernetes 节点，两组目标主机地址在本快照没有重合，之前“可能重复采集”的推测在这两组地址上未成立。不要删除其中一个 Monitor。
25 条 node-exporter-rules 告警中，24 条表达式显式限定 job="node-exporter"，没有匹配额外 node-export 的 8 个目标。NodeBondingDegraded 没有该 job 限制，通用 TargetDown 也可能覆盖抓取失败，但这不等于外部 8 台机器具有完整 CPU/内存/磁盘等告警。新环境需要区分 K8s 节点和外部主机，并明确两者的采集与规则覆盖。

### 6. Ingress 跨 namespace 混算已有真实样本

即时样本确认 nginx_ingress_controller_requests 含真实业务 namespace；同一个 ingress 名存在于不同 namespace。当前规则只 by(ingress)，确实会合并这些 namespace 的数据。候选至少保留 namespace/ingress；是否再保留 controller_class/cluster 由多控制器/多集群边界决定。当前仅查了样本，未改规则。

## 对当前告警状态的解释

快照中 Watchdog 和 InfoInhibitor 为 firing，是常驻链路检查/抑制机制，不应直接算作两项业务故障。KubeDeploymentReplicasMismatch 有一个 pending 告警；pending 表示尚未满足 for 时长，不等于已达到持续副本不一致的告警条件。状态会随评估变化。

## 当前还差的原始配置

下一项只拿 Probe：monitoring/blackbox-http-external。Prometheus 生效配置里已确认该 job 来源，但还需 declarative spec 用于重建与参数化。后续再逐项核对 Blackbox 模块、业务 exporter 的 Service/Endpoints、Prometheus 存储/外部标签、PrometheusAlert 存储与模板导入。

```bash
kubectl -n monitoring get probe blackbox-http-external -o jsonpath='{.spec}{"\n"}'
```

字段中若包含目标 URL 的 token 或认证参数，分享前脱敏；不要导出 Secret。当前不部署候选配置。

## 后续确认：HTTP Probe 原始配置已取得

维护者已提供 monitoring/blackbox-http-external 的 spec：interval=30s、scrapeTimeout=10s、module=http_2xx、prober=blackbox-exporter:19115、path=/probe，staticConfig 共 50 个目标，现有标签 env=prod、type=external-service。公开仓库不列出完整业务 URL；通用模板使用示例目标和待替换的 cluster/env。下一步核对真实 Blackbox 模块 ConfigMap，再核对通知中心配置。
