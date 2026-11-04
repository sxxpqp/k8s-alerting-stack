# 全量告警规则静态审查（2026-11-04）

输入：维护者提供的 alert.txt；只分析文件，没有修改现网。
范围：12 个 PrometheusRule，151 条告警定义（137 个不同告警名），86 条记录规则。已完成全量结构、标签和注解字段统计；不等于全部 PromQL 已通过解析器或运行态验证。
运行态只读查询因连接超时未成功，因此不宣称这些规则均已加载、依赖指标均存在或通知均可送达。

## 规则覆盖

| 资源 | 告警定义 | 记录规则 |
| --- | ---: | ---: |
| ingress-nginx/ingress-nginx | 3 | 0 |
| monitoring/alertmanager-main-rules | 10 | 0 |
| monitoring/blackbox-exporter-rules | 8 | 0 |
| monitoring/grafana-rules | 1 | 1 |
| monitoring/kube-prometheus-rules | 4 | 8 |
| monitoring/kube-state-metrics-rules | 4 | 0 |
| monitoring/kubernetes-monitoring-rules | 54 | 66 |
| monitoring/mysql-alerts | 8 | 0 |
| monitoring/node-exporter-rules | 25 | 11 |
| monitoring/prometheus-k8s-prometheus-rules | 23 | 0 |
| monitoring/prometheus-operator-rules | 9 | 0 |
| monitoring/redis-cluster-alerts-uat | 2 | 0 |

## 已确认问题与含义

1. **级别模板不匹配**：151 条均有 severity（critical 45、warning 98、info 6、none 2），仅 10 条有 level。当前模板只读 level，141 条定义不提供该字段。none 用于 Watchdog / InfoInhibitor，不应盲目当作错误级别改掉。
2. **说明字段并不统一**：IngressNginx5xxRateHigh、IngressNginxSslExpirySoon 没有 description，但有 summary；GrafanaRequestsFailing 只有 message 和 runbook_url，没有 description / summary。现有模板和之前仅回退 summary 的候选模板都不能覆盖 Grafana。通用正文需 description → summary → message。
3. **instance 不能等同主机 IP**：Kubernetes 工作负载、PVC、全局 SLO、Ingress 等聚合告警不保证保留 instance；Blackbox 的 instance 还可能是 URL / 域名。展示实际对象与所有必要标签，不能统一强制“故障主机 IP”。
4. **MySQLHighMemoryUsage 量纲错误**：表达式用 mysql_global_status_innodb_buffer_pool_pages_data / mysql_global_variables_innodb_buffer_pool_size，比的是页数与字节数，不能直接与 0.85 比作内存利用率。先核实 exporter 的实际指标名；当前官方 exporter 还存在以 state 标签表示 pages 分类的实现。修复需使用同单位的分子/分母，并重新确认这是 buffer pool 数据占用告警还是整机内存告警，二者含义不同。
5. **Ingress 5xx 聚合对象不足**：当前只按 ingress 分组，会丢失 namespace；同名 Ingress 可能混算。真实指标 namespace 是否为业务 namespace、是否需 controller_class / cluster，必须通过采集标签确认。
6. **探测规则命名误导**：BlackboxHTTPErrorRate 的表达式是 probe_http_status_code >= 500，检测状态码而非错误率。若保留该语义应调整名称/说明；若要错误率需另行定义业务指标和窗口，不能直接替换阈值。
7. **文档链接仍为占位符**：BlackboxProbeFailed、SSLCertExpiringSoon、SSLCertExpiringCritical 使用 wiki.example.com 链接，不是本项目已验证的运行手册。

## 待运行态确认，暂不判错

- BlackboxTCPConnectionFailed 使用 probe_tcp_connection_success。固定 v0.25.0 的官方 TCP prober 源文件中未发现该名称，需核对是否为自定义指标/记录规则；不能据此直接声称现场不存在。若指标不存在，表达式可能一直返回空，不会自动报规则错误。
- MySQLHighMemoryUsage 的 pages_data 指标名是否存在；mysqld_exporter 不同版本的指标结构可能不同。
- Grafana 当前运行在 observability，旧 monitoring/grafana 为 0 副本；需确认是否真正采集了当前 Grafana 指标。
- SSLCertExpiringSoon 和 SSLCertExpiringCritical 使用不同 alertname；现有按 namespace+alertname 抑制的规则不能使这两个名称互相抑制。如要求紧急级覆盖普通提醒，需定点设计抑制条件。
- MySQL / Redis 表达式没有统一的环境过滤条件；需要通过实际 Target 标签确认作用范围，而不能由 PrometheusRule 所在 namespace 推断。
- 同名告警不自动等于重复配置：共 137 个不同名称，存在多级阈值和 SLO 窗口变体；按告警名+静态标签+表达式文本比较，未发现完全相同的重复定义。不据此保证不存在语义等价或运行态重复序列。
- 没有规则提供独立 annotations.value，但 84 条定义已在其他 annotations 中引用 $value。不能把“没有 value 字段”解释为“都没显示触发值”。新规范可统一追加，但应逐条判断单位与实际含义。

## 通用模板与新环境复用要求

- severity 为主，level 仅兼容；description / summary / message 按顺序回退。
- 按对象显示 cluster、业务 namespace、Ingress、workload、Pod、node、PVC、探测目标、数据库实例等；未知业务标签仍有展示入口。
- 展示实例不能将 URL、域名、host:port、IPv6 都强制转换为 IPv4。
- 保留 firing/resolved 每条状态；数值为告警评估值，不冒充恢复后的实时值。
- 安装版本与依赖指标核验后再生成新环境参数化规则；可选 exporter 未安装时不默认启用其规则。
- 当前仅归档问题，不应用候选修复，不切换生产通知模板，不发测试消息。

## 下一步：只读检查实际加载规则

由可连接集群的管理机执行以下 GET，保存为本地文件后提供审查。若服务代理权限不足，返回错误即可，不调整 RBAC。

```bash
kubectl --request-timeout=30s get --raw '/api/v1/namespaces/monitoring/services/http:prometheus-k8s:9090/proxy/api/v1/rules?type=alert' > /tmp/prometheus-runtime-rules.json
```

此 API 用于查看已加载规则、health、lastError、state 和活动告警。它不证明每个无告警表达式都拥有底层指标；指标存在性/Targets 是下一步。

## 官方指标核对来源

- [MySQL pages_data 为页计数](https://dev.mysql.com/doc/refman/8.4/en/telemetry-metrics-meter-metrics.html)
- [MySQL buffer_pool_size 单位为 bytes](https://dev.mysql.com/doc/refman/8.0/en/innodb-parameters.html)
- [mysqld_exporter 指标转换实现（main，实际部署版本另查）](https://github.com/prometheus/mysqld_exporter/blob/main/collector/global_status.go)
- [blackbox_exporter v0.25.0 TCP 实现](https://github.com/prometheus/blackbox_exporter/blob/v0.25.0/prober/tcp.go)

## 全部告警字段清单

下表为静态字段检查，不表示该指标在运行态存在或告警已经通过验收。

| 资源 | 告警 | severity | level | 说明注解 | 引用 $value |
| --- | --- | --- | --- | --- | --- |
| ingress-nginx/ingress-nginx | IngressNginxConfigReloadFailed | critical | — | description, summary | 否 |
| ingress-nginx/ingress-nginx | IngressNginx5xxRateHigh | warning | — | summary | 否 |
| ingress-nginx/ingress-nginx | IngressNginxSslExpirySoon | warning | — | summary | 否 |
| monitoring/alertmanager-main-rules | KubeControllerManagerDown | critical | — | description, summary | 否 |
| monitoring/alertmanager-main-rules | KubeSchedulerDown | critical | — | description, summary | 否 |
| monitoring/alertmanager-main-rules | AlertmanagerFailedReload | critical | — | description, summary | 否 |
| monitoring/alertmanager-main-rules | AlertmanagerMembersInconsistent | critical | — | description, summary | 是 |
| monitoring/alertmanager-main-rules | AlertmanagerFailedToSendAlerts | warning | — | description, summary | 是 |
| monitoring/alertmanager-main-rules | AlertmanagerClusterFailedToSendAlerts | critical | — | description, summary | 是 |
| monitoring/alertmanager-main-rules | AlertmanagerClusterFailedToSendAlerts | warning | — | description, summary | 是 |
| monitoring/alertmanager-main-rules | AlertmanagerConfigInconsistent | critical | — | description, summary | 否 |
| monitoring/alertmanager-main-rules | AlertmanagerClusterDown | critical | — | description, summary | 是 |
| monitoring/alertmanager-main-rules | AlertmanagerClusterCrashlooping | critical | — | description, summary | 是 |
| monitoring/blackbox-exporter-rules | BlackboxProbeFailed | critical | — | description, summary | 否 |
| monitoring/blackbox-exporter-rules | BlackboxHTTPErrorRate | warning | — | description, summary | 是 |
| monitoring/blackbox-exporter-rules | BlackboxHTTPClientError | info | — | description, summary | 是 |
| monitoring/blackbox-exporter-rules | SSLCertExpiringSoon | warning | — | description, summary | 是 |
| monitoring/blackbox-exporter-rules | SSLCertExpiringCritical | critical | — | description, summary | 否 |
| monitoring/blackbox-exporter-rules | BlackboxSlowResponse | warning | — | description, summary | 是 |
| monitoring/blackbox-exporter-rules | BlackboxSlowDNS | warning | — | description, summary | 是 |
| monitoring/blackbox-exporter-rules | BlackboxTCPConnectionFailed | critical | — | description, summary | 否 |
| monitoring/grafana-rules | GrafanaRequestsFailing | warning | — | message | 是 |
| monitoring/kube-prometheus-rules | TargetDown | warning | — | description, summary | 是 |
| monitoring/kube-prometheus-rules | Watchdog | none | — | description, summary | 否 |
| monitoring/kube-prometheus-rules | InfoInhibitor | none | — | description, summary | 否 |
| monitoring/kube-prometheus-rules | NodeNetworkInterfaceFlapping | warning | — | description, summary | 否 |
| monitoring/kube-state-metrics-rules | KubeStateMetricsListErrors | critical | — | description, summary | 否 |
| monitoring/kube-state-metrics-rules | KubeStateMetricsWatchErrors | critical | — | description, summary | 否 |
| monitoring/kube-state-metrics-rules | KubeStateMetricsShardingMismatch | critical | — | description, summary | 否 |
| monitoring/kube-state-metrics-rules | KubeStateMetricsShardsMissing | critical | — | description, summary | 否 |
| monitoring/kubernetes-monitoring-rules | KubePodCrashLooping | warning | — | description, summary | 否 |
| monitoring/kubernetes-monitoring-rules | KubePodNotReady | warning | — | description, summary | 否 |
| monitoring/kubernetes-monitoring-rules | KubeDeploymentGenerationMismatch | warning | — | description, summary | 否 |
| monitoring/kubernetes-monitoring-rules | KubeDeploymentReplicasMismatch | warning | — | description, summary | 否 |
| monitoring/kubernetes-monitoring-rules | KubeDeploymentRolloutStuck | warning | — | description, summary | 否 |
| monitoring/kubernetes-monitoring-rules | KubeStatefulSetReplicasMismatch | warning | — | description, summary | 否 |
| monitoring/kubernetes-monitoring-rules | KubeStatefulSetGenerationMismatch | warning | — | description, summary | 否 |
| monitoring/kubernetes-monitoring-rules | KubeStatefulSetUpdateNotRolledOut | warning | — | description, summary | 否 |
| monitoring/kubernetes-monitoring-rules | KubeDaemonSetRolloutStuck | warning | — | description, summary | 否 |
| monitoring/kubernetes-monitoring-rules | KubeContainerWaiting | warning | — | description, summary | 否 |
| monitoring/kubernetes-monitoring-rules | KubeDaemonSetNotScheduled | warning | — | description, summary | 是 |
| monitoring/kubernetes-monitoring-rules | KubeDaemonSetMisScheduled | warning | — | description, summary | 是 |
| monitoring/kubernetes-monitoring-rules | KubeJobNotCompleted | warning | — | description, summary | 否 |
| monitoring/kubernetes-monitoring-rules | KubeJobFailed | warning | — | description, summary | 否 |
| monitoring/kubernetes-monitoring-rules | KubeHpaReplicasMismatch | warning | — | description, summary | 否 |
| monitoring/kubernetes-monitoring-rules | KubeHpaMaxedOut | warning | — | description, summary | 否 |
| monitoring/kubernetes-monitoring-rules | KubeCPUOvercommit | warning | — | description, summary | 是 |
| monitoring/kubernetes-monitoring-rules | KubeMemoryOvercommit | warning | — | description, summary | 是 |
| monitoring/kubernetes-monitoring-rules | KubeCPUQuotaOvercommit | warning | — | description, summary | 否 |
| monitoring/kubernetes-monitoring-rules | KubeMemoryQuotaOvercommit | warning | — | description, summary | 否 |
| monitoring/kubernetes-monitoring-rules | KubeQuotaAlmostFull | info | — | description, summary | 是 |
| monitoring/kubernetes-monitoring-rules | KubeQuotaFullyUsed | info | — | description, summary | 是 |
| monitoring/kubernetes-monitoring-rules | KubeQuotaExceeded | warning | — | description, summary | 是 |
| monitoring/kubernetes-monitoring-rules | CPUThrottlingHigh | info | — | description, summary | 是 |
| monitoring/kubernetes-monitoring-rules | KubePersistentVolumeFillingUp | critical | — | description, summary | 是 |
| monitoring/kubernetes-monitoring-rules | KubePersistentVolumeFillingUp | warning | — | description, summary | 是 |
| monitoring/kubernetes-monitoring-rules | KubePersistentVolumeInodesFillingUp | critical | — | description, summary | 是 |
| monitoring/kubernetes-monitoring-rules | KubePersistentVolumeInodesFillingUp | warning | — | description, summary | 是 |
| monitoring/kubernetes-monitoring-rules | KubePersistentVolumeErrors | critical | — | description, summary | 否 |
| monitoring/kubernetes-monitoring-rules | KubeVersionMismatch | warning | — | description, summary | 是 |
| monitoring/kubernetes-monitoring-rules | KubeClientErrors | warning | — | description, summary | 是 |
| monitoring/kubernetes-monitoring-rules | KubeAPIErrorBudgetBurn | critical | — | description, summary | 否 |
| monitoring/kubernetes-monitoring-rules | KubeAPIErrorBudgetBurn | critical | — | description, summary | 否 |
| monitoring/kubernetes-monitoring-rules | KubeAPIErrorBudgetBurn | warning | — | description, summary | 否 |
| monitoring/kubernetes-monitoring-rules | KubeAPIErrorBudgetBurn | warning | — | description, summary | 否 |
| monitoring/kubernetes-monitoring-rules | KubeClientCertificateExpiration | warning | — | description, summary | 否 |
| monitoring/kubernetes-monitoring-rules | KubeClientCertificateExpiration | critical | — | description, summary | 否 |
| monitoring/kubernetes-monitoring-rules | KubeAggregatedAPIErrors | warning | — | description, summary | 是 |
| monitoring/kubernetes-monitoring-rules | KubeAggregatedAPIDown | warning | — | description, summary | 是 |
| monitoring/kubernetes-monitoring-rules | KubeAPIDown | critical | — | description, summary | 否 |
| monitoring/kubernetes-monitoring-rules | KubeAPITerminatedRequests | warning | — | description, summary | 是 |
| monitoring/kubernetes-monitoring-rules | KubeNodeNotReady | warning | — | description, summary | 否 |
| monitoring/kubernetes-monitoring-rules | KubeNodeUnreachable | warning | — | description, summary | 否 |
| monitoring/kubernetes-monitoring-rules | KubeletTooManyPods | info | — | description, summary | 是 |
| monitoring/kubernetes-monitoring-rules | KubeNodeReadinessFlapping | warning | — | description, summary | 是 |
| monitoring/kubernetes-monitoring-rules | KubeletPlegDurationHigh | warning | — | description, summary | 是 |
| monitoring/kubernetes-monitoring-rules | KubeletPodStartUpLatencyHigh | warning | — | description, summary | 是 |
| monitoring/kubernetes-monitoring-rules | KubeletClientCertificateExpiration | warning | — | description, summary | 是 |
| monitoring/kubernetes-monitoring-rules | KubeletClientCertificateExpiration | critical | — | description, summary | 是 |
| monitoring/kubernetes-monitoring-rules | KubeletServerCertificateExpiration | warning | — | description, summary | 是 |
| monitoring/kubernetes-monitoring-rules | KubeletServerCertificateExpiration | critical | — | description, summary | 是 |
| monitoring/kubernetes-monitoring-rules | KubeletClientCertificateRenewalErrors | warning | — | description, summary | 是 |
| monitoring/kubernetes-monitoring-rules | KubeletServerCertificateRenewalErrors | warning | — | description, summary | 是 |
| monitoring/kubernetes-monitoring-rules | KubeletDown | critical | — | description, summary | 否 |
| monitoring/mysql-alerts | MySQLDown | critical | 4 | description, summary | 否 |
| monitoring/mysql-alerts | MySQLTooManyConnections | critical | 3 | description, summary | 是 |
| monitoring/mysql-alerts | MySQLReplicationDown | critical | 3 | description, summary | 否 |
| monitoring/mysql-alerts | MySQLReplicationLag | critical | 3 | description, summary | 是 |
| monitoring/mysql-alerts | MySQLHighThreadsRunning | critical | 3 | description, summary | 是 |
| monitoring/mysql-alerts | MySQLSlowQueries | warning | 2 | description, summary | 是 |
| monitoring/mysql-alerts | MySQLHighMemoryUsage | warning | 2 | description, summary | 是 |
| monitoring/mysql-alerts | MySQLRestarted | warning | 2 | description, summary | 否 |
| monitoring/node-exporter-rules | NodeFilesystemSpaceFillingUp | warning | — | description, summary | 是 |
| monitoring/node-exporter-rules | NodeFilesystemSpaceFillingUp | critical | — | description, summary | 是 |
| monitoring/node-exporter-rules | NodeFilesystemAlmostOutOfSpace | warning | — | description, summary | 是 |
| monitoring/node-exporter-rules | NodeFilesystemAlmostOutOfSpace | critical | — | description, summary | 是 |
| monitoring/node-exporter-rules | NodeFilesystemFilesFillingUp | warning | — | description, summary | 是 |
| monitoring/node-exporter-rules | NodeFilesystemFilesFillingUp | critical | — | description, summary | 是 |
| monitoring/node-exporter-rules | NodeFilesystemAlmostOutOfFiles | warning | — | description, summary | 是 |
| monitoring/node-exporter-rules | NodeFilesystemAlmostOutOfFiles | critical | — | description, summary | 是 |
| monitoring/node-exporter-rules | NodeNetworkReceiveErrs | warning | — | description, summary | 是 |
| monitoring/node-exporter-rules | NodeNetworkTransmitErrs | warning | — | description, summary | 是 |
| monitoring/node-exporter-rules | NodeHighNumberConntrackEntriesUsed | warning | — | description, summary | 是 |
| monitoring/node-exporter-rules | NodeTextFileCollectorScrapeError | warning | — | description, summary | 否 |
| monitoring/node-exporter-rules | NodeClockSkewDetected | warning | — | description, summary | 否 |
| monitoring/node-exporter-rules | NodeClockNotSynchronising | warning | — | description, summary | 否 |
| monitoring/node-exporter-rules | NodeRAIDDegraded | critical | — | description, summary | 否 |
| monitoring/node-exporter-rules | NodeRAIDDiskFailure | warning | — | description, summary | 否 |
| monitoring/node-exporter-rules | NodeFileDescriptorLimit | warning | — | description, summary | 是 |
| monitoring/node-exporter-rules | NodeFileDescriptorLimit | critical | — | description, summary | 是 |
| monitoring/node-exporter-rules | NodeCPUHighUsage | info | — | description, summary | 是 |
| monitoring/node-exporter-rules | NodeSystemSaturation | warning | — | description, summary | 是 |
| monitoring/node-exporter-rules | NodeMemoryMajorPagesFaults | warning | — | description, summary | 是 |
| monitoring/node-exporter-rules | NodeMemoryHighUtilization | warning | — | description, summary | 是 |
| monitoring/node-exporter-rules | NodeDiskIOSaturation | warning | — | description, summary | 是 |
| monitoring/node-exporter-rules | NodeSystemdServiceFailed | warning | — | description, summary | 否 |
| monitoring/node-exporter-rules | NodeBondingDegraded | warning | — | description, summary | 否 |
| monitoring/prometheus-k8s-prometheus-rules | PrometheusBadConfig | critical | — | description, summary | 否 |
| monitoring/prometheus-k8s-prometheus-rules | PrometheusSDRefreshFailure | warning | — | description, summary | 否 |
| monitoring/prometheus-k8s-prometheus-rules | PrometheusKubernetesListWatchFailures | warning | — | description, summary | 是 |
| monitoring/prometheus-k8s-prometheus-rules | PrometheusNotificationQueueRunningFull | warning | — | description, summary | 否 |
| monitoring/prometheus-k8s-prometheus-rules | PrometheusErrorSendingAlertsToSomeAlertmanagers | warning | — | description, summary | 是 |
| monitoring/prometheus-k8s-prometheus-rules | PrometheusNotConnectedToAlertmanagers | warning | — | description, summary | 否 |
| monitoring/prometheus-k8s-prometheus-rules | PrometheusTSDBReloadsFailing | warning | — | description, summary | 是 |
| monitoring/prometheus-k8s-prometheus-rules | PrometheusTSDBCompactionsFailing | warning | — | description, summary | 是 |
| monitoring/prometheus-k8s-prometheus-rules | PrometheusNotIngestingSamples | warning | — | description, summary | 否 |
| monitoring/prometheus-k8s-prometheus-rules | PrometheusDuplicateTimestamps | warning | — | description, summary | 是 |
| monitoring/prometheus-k8s-prometheus-rules | PrometheusOutOfOrderTimestamps | warning | — | description, summary | 是 |
| monitoring/prometheus-k8s-prometheus-rules | PrometheusRemoteStorageFailures | critical | — | description, summary | 是 |
| monitoring/prometheus-k8s-prometheus-rules | PrometheusRemoteWriteBehind | critical | — | description, summary | 是 |
| monitoring/prometheus-k8s-prometheus-rules | PrometheusRemoteWriteDesiredShards | warning | — | description, summary | 是 |
| monitoring/prometheus-k8s-prometheus-rules | PrometheusRuleFailures | critical | — | description, summary | 是 |
| monitoring/prometheus-k8s-prometheus-rules | PrometheusMissingRuleEvaluations | warning | — | description, summary | 是 |
| monitoring/prometheus-k8s-prometheus-rules | PrometheusTargetLimitHit | warning | — | description, summary | 是 |
| monitoring/prometheus-k8s-prometheus-rules | PrometheusLabelLimitHit | warning | — | description, summary | 是 |
| monitoring/prometheus-k8s-prometheus-rules | PrometheusScrapeBodySizeLimitHit | warning | — | description, summary | 是 |
| monitoring/prometheus-k8s-prometheus-rules | PrometheusScrapeSampleLimitHit | warning | — | description, summary | 是 |
| monitoring/prometheus-k8s-prometheus-rules | PrometheusTargetSyncFailure | critical | — | description, summary | 是 |
| monitoring/prometheus-k8s-prometheus-rules | PrometheusHighQueryLoad | warning | — | description, summary | 否 |
| monitoring/prometheus-k8s-prometheus-rules | PrometheusErrorSendingAlertsToAnyAlertmanager | critical | — | description, summary | 是 |
| monitoring/prometheus-operator-rules | PrometheusOperatorListErrors | warning | — | description, summary | 否 |
| monitoring/prometheus-operator-rules | PrometheusOperatorWatchErrors | warning | — | description, summary | 否 |
| monitoring/prometheus-operator-rules | PrometheusOperatorSyncFailed | warning | — | description, summary | 是 |
| monitoring/prometheus-operator-rules | PrometheusOperatorReconcileErrors | warning | — | description, summary | 是 |
| monitoring/prometheus-operator-rules | PrometheusOperatorStatusUpdateErrors | warning | — | description, summary | 是 |
| monitoring/prometheus-operator-rules | PrometheusOperatorNodeLookupErrors | warning | — | description, summary | 否 |
| monitoring/prometheus-operator-rules | PrometheusOperatorNotReady | warning | — | description, summary | 否 |
| monitoring/prometheus-operator-rules | PrometheusOperatorRejectedResources | warning | — | description, summary | 是 |
| monitoring/prometheus-operator-rules | ConfigReloaderSidecarErrors | warning | — | description, summary | 否 |
| monitoring/redis-cluster-alerts-uat | RedisInstanceDown | critical | 4 | description, summary | 否 |
| monitoring/redis-cluster-alerts-uat | RedisClusterStateNotOk | critical | 4 | description, summary | 否 |
