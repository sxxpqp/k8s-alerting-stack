# 业务告警规则与验证

Helm kube-prometheus-stack 的**精简业务增量告警**：本地评估，保留上限6h；Mimir远写可选，通知链路 Alertmanager → PrometheusAlert → 钉钉/飞书。

本目录管理15条增量告警；命令均在仓库根目录执行。基础安装见 [Helm 安装](../install/README.md)，采集配置见 [metrics](../metrics/README.md)，通知对接见 [notifications](../notifications/README.md)。不包含旧0.14基线。

## 1. 规则总览

| 资源 | 告警名 | 条件 | 级别 | for |
| --- | --- | --- | --- | --- |
| discovery | BusinessMetricsTargetsAbsent | 预期 job 的 up 序列完全消失 | warning | 10m |
| containers | ContainerMemoryLimitNear | working set / 正 memory limit >85% | warning | 10m |
| flink | FlinkCheckpointStale | 最后成功 checkpoint 距今 >900s 且曾完成过 | warning | 10m |
| kafka | KafkaInSyncReplicasLow | 副本数>=3 的分区 ISR<2 | critical | 3m |
| kafka | KafkaConsumerLagHigh | 消费组/topic 非负 lag 合计 >10000 | warning | 15m |
| doris | DorisQueryErrorRatioHigh | 5m 查询错误率>5%，总查询速率>=1/s | warning | 10m |
| doris | DorisDiskSpaceCritical | 数据目录可用比例 <3% | critical | 3m |
| mysql | MysqlUnavailable | mysql_up=0 | critical | 3m |
| mysql | MysqlConnectionsHigh | 连接数/正 max_connections >80% | warning | 10m |
| redis | RedisUnavailable | redis_up=0 | critical | 3m |
| redis | RedisMemoryHigh | used_memory/正 maxmemory >85% | warning | 10m |
| redis | RedisClusterStateBad | Cluster 模式 state!=1 | critical | 3m |
| domains | DomainHttpProbeFailed | HTTP Probe 成功标记=0 | critical | 3m |
| domains | DomainCertificateExpiring | 证书剩余天数 [3,14) | warning | 10m |
| domains | DomainCertificateExpiryCritical | 证书剩余天数 <3 | critical | 3m |

节点、PVC、CrashLoop/OOM、Prometheus 自身和通用 `TargetDown` 复用 kps 现有规则，不重复新增。容器仅补 memory limit 容量预警；若现场已有等价规则，再移除本条。

完整可 apply 的资源：[business-alerts.yaml](business-alerts.yaml)。共 15 条规则，按资源分组，包含 `release: kps`、severity、team 及四项必需注解，阈值依据在 YAML 注释中。

## 2. 使用前必须核对

1. 本规则默认放在 `monitoring` namespace；若 Helm 安装在其他 namespace，先修改 metadata.namespace，并确认 Prometheus 的 ruleNamespaceSelector/ruleSelector 包含它及 `release: kps`。
2. **job 是部署契约，不是自动发现的名称。** 缺失检测期望以下 job：`flink-jobmanager`、`flink-taskmanager`、`kafka-exporter`、`doris-fe`、`doris-be`、`mysqld-exporter`、`redis-exporter`、`blackbox-http-external`。用 `count by(job)(up)` 对照；修改缺失检测中的精确名称。未部署组件时，删除相应业务 group 以及公共缺失检测中的对应 absent 分支。不能不核对就整包部署。
3. `absent(up{job="..."})` 只检测该 job 整体从发现中消失，返回 job 标签；不能从空向量恢复 namespace/pod/instance，也不能发现某一个实例在其他实例仍存活时被删掉。精确实例/作业丢失检测必须由真实期望对象清单生成，不虚构 inventory 指标。已有 `TargetDown` 负责 up=0；若 kps 禁用了它，需先明确补齐采集失败检测。
4. exporter 指标及标签需实际存在。所有依赖都列在下一节；未核对的组件规则不要启用。`health=ok` 不代表表达式有数据。
5. 聚合保留 cluster/namespace/pod/instance 以及资源身份标签；缺失标签不会凭空出现。`namespace` 可能是 exporter 所属 namespace，而非数据库业务 namespace，需要核对。`instance` 可以是 URL、域名或 host:port，不能统一当作主机 IP。
6. `external_labels.cluster` 通常只在发送告警/remote_write 时附加，不会自动写入本地原始时间序列。因此 YAML 中 `by(cluster,...)` 不会凭空生成 cluster；告警发送时由 external label 追加。本地 binary matching 两边的标签必须一致，不能一边有 cluster、一边没有而不排查。
7. `team` 的 sre/platform/database/data-platform 是职责示例，改成实际团队值；runbook_url 使用真实官方资料，后续可替换为你们自己的运行手册。对比当前已加载规则，排除自定义规则中的等价重复。

## 3. 指标与版本风险

| 指标 | 来源 | 必须核对的风险 |
| --- | --- | --- |
| up | Prometheus 抓取状态 | job 命名和服务发现；up=1 不证明业务正常 |
| container_memory_working_set_bytes | kubelet / cAdvisor | container/image/namespace/pod/instance 标签，重复抓取；不是进程 RSS |
| kube_pod_container_resource_limits{resource="memory",unit="byte"} | kube-state-metrics | 新旧版本可能使用不同名字；需核对 unit 和 container 标签；没有/为0的 limit 不计算比例 |
| flink_jobmanager_job_lastCheckpointCompletedTimestamp | Flink Prometheus reporter | **需核对**完整 metric scope/name、job_name/job_id、毫秒单位；仅用于已完成过 checkpoint 的持续流作业，不覆盖从未完成或已从指标中消失的作业 |
| kafka_topic_partition_in_sync_replica / kafka_topic_partition_replicas | danielqsj/kafka_exporter | topic/partition 标签、exporter 权限、Kafka/Exporter 版本；不可直接套 JMX Exporter 的指标名 |
| kafka_consumergroup_lag | 同上 | consumergroup/topic/partition；排除未知负 offset；无活动消费组时可能不导出该指标 |
| doris_fe_query_err / doris_fe_query_total | Doris FE 内置 /metrics | **需核对**部署版本中的名称、Counter 语义及 labels；查询错误含业务 SQL/权限错误，不一律代表系统故障 |
| doris_be_disks_avail_capacity / doris_be_disks_total_capacity | Doris BE 内置 /metrics | **需核对** path 标签、字节单位；这不是通用 PVC 告警 |
| mysql_up / mysql_global_status_threads_connected / mysql_global_variables_max_connections | prometheus/mysqld_exporter | 账号权限、采集器开关、版本；mysql_up=0 也可能是监控账号失败，必须独立核验业务连接 |
| redis_up / redis_memory_used_bytes / redis_memory_max_bytes | oliver006/redis_exporter | maxmemory=0 表示未设上限，排除比例告警；该场景另看容器/主机容量 |
| redis_cluster_state / redis_cluster_enabled | 同上，Redis Cluster | **需核对**是否导出及 1=正常语义；standalone 不适用该规则 |
| probe_success / probe_ssl_earliest_cert_expiry | prometheus/blackbox_exporter | job/module、TLS 校验和 HTTPS 证书链；HTTP 无证书指标；TLS 握手失败可能使到期指标消失，由 probe_success 兜底 |

分母使用 `> 0` 过滤后参与除法，避免零分母/Inf 伪高利用率。Flink 时间戳毫秒转换为秒，证书 epoch 秒转换为剩余天数。

本包最长 range selector 为 **5m**，for 最大15m，均小于6h。证书剩余14天是未来到期时间计算，不是 `[14d]` 历史查询。**本包没有需迁往 Mimir Ruler 的长窗口规则**；以后增加 `[24h]`、`[7d]` 等规则应单独放入 Mimir Ruler，不放在本地6h评估包。remote_write 本身不会使本地自动拥有 Mimir 的历史数据。

## 4. 校验与部署

在管理机使用与实际 Prometheus 版本匹配的 promtool。本包不自动操作集群。

```bash
# 已安装 PyYAML 可跳过虚拟环境准备
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install PyYAML==6.0.2

# promtool 接受 groups，不接受 Kubernetes PrometheusRule 外壳
mkdir -p .generated
python3 - <<'PY'
from pathlib import Path
import yaml
doc = yaml.safe_load(Path('alerts/business-alerts.yaml').read_text())
Path('.generated/rules.yaml').write_text(yaml.safe_dump(doc['spec'], allow_unicode=True, sort_keys=False))
PY
cp tests/rules.test.yaml .generated/rules.test.yaml
(
  cd .generated
  promtool check rules rules.yaml
  promtool test rules rules.test.yaml
)

```

以上单测验证完整规则包的边界行为，不要求每个环境都部署全部组件。测试覆盖Redis零分母/高利用率、MySQL零分母、Kafka单副本例外和Doris零容量。

复制一份本环境的规则，再按第2节删除未部署组件的group和缺失检测分支、调整job/team等；未部署任何业务组件时可先跳过业务规则：

```bash
mkdir -p .local/alerts
cp alerts/business-alerts.yaml .local/alerts/business-alerts.yaml
# 编辑上述文件，只保留本环境适用的规则
```

编辑后对实际部署文件再次检查语法，再预检和应用：

```bash
python3 - <<'PY'
from pathlib import Path
import yaml
doc = yaml.safe_load(Path('.local/alerts/business-alerts.yaml').read_text())
Path('.generated/selected-rules.yaml').write_text(yaml.safe_dump(doc['spec'], allow_unicode=True, sort_keys=False))
PY
promtool check rules .generated/selected-rules.yaml
kubectl apply --dry-run=server -f .local/alerts/business-alerts.yaml
kubectl diff -f .local/alerts/business-alerts.yaml
```

`kubectl diff` 退出码1表示存在差异，大于1才是错误。确认差异后执行：

```bash
kubectl apply -f .local/alerts/business-alerts.yaml
```

应用后在Prometheus Rules页面确认**所选规则**已加载、health正常，并核对原始指标有数据及for状态；不是固定要求15条。修改表达式或阈值时还需补充相应单测，不能只凭完整规则包原有测试通过就认为改动已验证。

注意：导出给 promtool 的 groups 文件与 CR 源自同一 YAML。语法测试不证明 exporter 指标存在、标签匹配或通知成功。当前会话不对现网执行 apply/通知测试。

## 5. info 只记录不通知

精简规则当前只含 warning/critical；未来新增 info 时，**标签本身不阻止发送**。本项目Helm values已包含info空路由，通知CR仅匹配warning/critical，不需重复添加。其他独立环境可参考以下原生Alertmanager配置片段，通过其配置管理方式合并，不覆盖其他路由：

```yaml
# route.routes 的第一条
- receiver: info-null
  matchers: ['severity="info"']
  continue: false

# receivers 中新增
- name: info-null
```

info 仍可在 Prometheus/Alertmanager 查询；需要长期事件留存时要另有存储策略。PrometheusAlert 模板按 `description → summary → message` 回退，并展示 suggestion / runbook_url，不能只读 level 或要求每条都有主机IP。

## 6. 三条 curl 通知测试样例

只对**测试 Alertmanager / 专用测试路由**执行。先约定测试群，不能把示例直接发到生产群。本项目未执行这些 POST。它们绕过 Prometheus，**不能验证表达式与 for**，只验证 Alertmanager → PrometheusAlert → 钉钉/飞书与恢复通知。两个 webhook receiver 必须显式 `send_resolved: true`。

准备变量（Linux GNU date）：

```bash
AM_URL=http://127.0.0.1:19093
START=$(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%SZ)
END=$(date -u -d '10 minutes' +%Y-%m-%dT%H:%M:%SZ)
```

① critical：

```bash
curl --fail-with-body -sS -X POST "$AM_URL/api/v2/alerts" \
  -H 'Content-Type: application/json' -d @- <<JSON
[{"labels":{"alertname":"TestMysqlUnavailable","cluster":"test-cluster","namespace":"alert-test","instance":"mysql-test:3306","severity":"critical","team":"database","alert_test":"true"},"annotations":{"summary":"测试 MySQL mysql-test 不可连接","description":"测试当前值=0，正常阈值=1","suggestion":"1. 确认这是测试消息；2. 检查通知模板","runbook_url":"https://github.com/prometheus/mysqld_exporter"},"startsAt":"$START","endsAt":"$END"}]
JSON
```

② warning：

```bash
curl --fail-with-body -sS -X POST "$AM_URL/api/v2/alerts" \
  -H 'Content-Type: application/json' -d @- <<JSON
[{"labels":{"alertname":"TestRedisMemoryHigh","cluster":"test-cluster","namespace":"alert-test","instance":"redis-test:6379","severity":"warning","team":"database","alert_test":"true"},"annotations":{"summary":"测试 Redis redis-test 内存接近上限","description":"测试当前值=90%，阈值>85%","suggestion":"1. 确认这是测试消息；2. 检查分组和级别","runbook_url":"https://github.com/oliver006/redis_exporter"},"startsAt":"$START","endsAt":"$END"}]
JSON
```

等待两个渠道收到 firing 后执行③，labels 必须与前面完全相同，显式结束两条测试告警：

```bash
RESOLVED=$(date -u +%Y-%m-%dT%H:%M:%SZ)
curl --fail-with-body -sS -X POST "$AM_URL/api/v2/alerts" \
  -H 'Content-Type: application/json' -d @- <<JSON
[
 {"labels":{"alertname":"TestMysqlUnavailable","cluster":"test-cluster","namespace":"alert-test","instance":"mysql-test:3306","severity":"critical","team":"database","alert_test":"true"},"annotations":{"summary":"MySQL 测试结束","description":"测试恢复值=1，正常阈值=1","suggestion":"1. 确认恢复通知；2. 核对原测试告警已结束","runbook_url":"https://github.com/prometheus/mysqld_exporter"},"startsAt":"$START","endsAt":"$RESOLVED"},
 {"labels":{"alertname":"TestRedisMemoryHigh","cluster":"test-cluster","namespace":"alert-test","instance":"redis-test:6379","severity":"warning","team":"database","alert_test":"true"},"annotations":{"summary":"Redis 测试结束","description":"测试恢复值=50%，阈值>85%","suggestion":"1. 确认恢复通知；2. 核对原测试告警已结束","runbook_url":"https://github.com/oliver006/redis_exporter"},"startsAt":"$START","endsAt":"$RESOLVED"}
]
JSON
```

等待时间按真实 group_wait/group_interval/repeat_interval 判断；Alertmanager 返回2xx不等于群里实际送达。测试时记录两渠道 firing/resolved，并确认告警列表中测试项已结束。

## 已执行的离线验证

- 使用 Prometheus 官方 Go 模块 `github.com/prometheus/prometheus v0.47.2` 源码构建的 promtool；构建未注入发布版 ldflags，`--version` 的版本字符串为空，来源版本以构建模块为准。
- `promtool check rules`：SUCCESS，15 rules found。
- `promtool test rules`：SUCCESS，5 组测试通过。
- 所有 range selector 均不超过6h，实际最大为5m；必需 labels/annotations 与两条 suggestion 的结构检查通过。
- 未执行集群 server dry-run、apply 或 curl POST；上线前仍用现场 Prometheus 对应版本的 promtool 复查，并核对 job/指标/标签。

## 官方依据

- [Flink 指标](https://nightlies.apache.org/flink/flink-docs-stable/docs/ops/metrics/)与[Prometheus reporter](https://nightlies.apache.org/flink/flink-docs-stable/docs/deployment/metric_reporters/)
- [Kafka exporter](https://github.com/danielqsj/kafka_exporter)
- [Doris 3.x 指标](https://doris.apache.org/docs/3.x/admin-manual/maint-monitor/metrics/)
- [mysqld_exporter](https://github.com/prometheus/mysqld_exporter)、[redis_exporter](https://github.com/oliver006/redis_exporter)、[blackbox_exporter](https://github.com/prometheus/blackbox_exporter)
- [Prometheus 规则测试](https://prometheus.io/docs/prometheus/latest/configuration/unit_testing_rules/)
