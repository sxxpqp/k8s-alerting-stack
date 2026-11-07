# 部署业务告警

28 组生产级告警规则，按组件拆分到独立文件，覆盖节点、Pod、容器、存储、工作负载、任务、API Server、etcd、Kafka、MySQL、Redis、Ingress 和证书。

## 规则清单

| 规则组 | 文件 | 指标来源 | 关键条件 |
|--------|------|---------|---------|
| node | [node.rules.yaml](node.rules.yaml) | node_exporter | CPU >90%, 内存 >90%, 磁盘 <15%/<5% |
| pods | [pods.rules.yaml](pods.rules.yaml) | kube-state-metrics | CrashLoopBackOff, NotReady>3m, Pending>10m |
| containers | [containers.rules.yaml](containers.rules.yaml) | cAdvisor | CPU 限流 >10%, 内存/limit >85%, OOMKilled |
| storage | [storage.rules.yaml](storage.rules.yaml) | kubelet | PVC 使用 >80%/>95% |
| workloads | [workloads.rules.yaml](workloads.rules.yaml) | kube-state-metrics | Deployment/StatefulSet/DaemonSet 副本异常 |
| jobs | [jobs.rules.yaml](jobs.rules.yaml) | kube-state-metrics | Job 失败, CronJob >5m 未完成 |
| apiserver | [apiserver.rules.yaml](apiserver.rules.yaml) | apiserver | 5xx 率 >3%, P99 延迟 >3s |
| etcd | [etcd.rules.yaml](etcd.rules.yaml) | etcd | Leader 切换, fsync P99 >500ms, DB >8GB |
| kafka | [middleware-kafka.rules.yaml](middleware-kafka.rules.yaml) | JMX/Kafka exporter | Broker 下线 >3m, ISR 不足, consumer lag >10000 |
| mysql | [middleware-mysql.rules.yaml](middleware-mysql.rules.yaml) | mysqld_exporter | 不可达, 连接数 >80%, 主从延迟 >30s, 慢查询 >50/min |
| redis | [middleware-redis.rules.yaml](middleware-redis.rules.yaml) | redis_exporter | 不可达, 内存 >85%, 连接拒绝, 集群异常 |
| ingress | [ingress.rules.yaml](ingress.rules.yaml) | nginx-ingress | 5xx 率 >5%, P99 延迟 >5s |
| certmanager | [certmanager.rules.yaml](certmanager.rules.yaml) | cert-manager | 证书 <30d 过期, 签发失败 |
| prometheus | [prometheus.rules.yaml](prometheus.rules.yaml) | 内部 | 采集目标下线 >5m, 规则评估失败, Alertmanager 失联 |

## 部署

```bash
bash alerts/apply.sh
```

脚本流程：YAML 语法检查（Python3 + PyYAML）→ `kubectl --dry-run=server` 预检 → `kubectl apply`。

依赖特定 exporter 的规则（kafka/mysql/redis 等）仅在对应指标存在时触发，未部署对应中间件不影响其他规则。

## 验证

转发 Prometheus 页面：

```bash
kubectl -n monitoring port-forward svc/kps-kube-prometheus-stack-prometheus 9090:9090
```

访问 `http://127.0.0.1:9090/rules`，确认各组规则 health=ok，有数据的规则显示绿色。无可查询指标的规则（如 kafka/mysql 未部署时）状态为空属于正常。

### 排查告警不触发

1. **规则不存在** → 确认 `apply.sh` 无报错
2. **规则存在但无数据** → 在 Rules 页面点击规则表达式跳转 Graph 查询，确认原始指标有值
3. **指标有值但没触发** → 检查比较阈值和 `for` 时长是否满足
4. **触发后未收到通知** → 检查 Alertmanager 路由和[通知链路](../notifications/README.md)

## 修改规则

每个规则组对应一个独立文件，直接编辑后重新 apply：

```bash
# 修改节点告警阈值
vim alerts/node.rules.yaml
bash alerts/apply.sh
```

### 未部署某些中间件

删除对应的规则文件，同时从 `apply.sh` 的 `apply_files` 列表中移除该行。以 kafka 为例：

1. 删除 `alerts/middleware-kafka.rules.yaml`
2. 在 `apply.sh` 中删除 `alerts/middleware-kafka.rules.yaml` 行

### 调整阈值

在规则表达式中修改数值即可。常见调整：

| 规则 | 文件 | 调整点 |
|------|------|--------|
| node-memory-pressure | [node.rules.yaml](node.rules.yaml) | `> 90` 内存告警阈值 |
| pvc-usage-high | [storage.rules.yaml](storage.rules.yaml) | `> 80` 磁盘告警阈值 |
| container-memory-near-limit | [containers.rules.yaml](containers.rules.yaml) | `> 85` 容器内存比例 |
| mysql-connections-high | [middleware-mysql.rules.yaml](middleware-mysql.rules.yaml) | `> 80` MySQL 连接比例 |
| redis-memory-high | [middleware-redis.rules.yaml](middleware-redis.rules.yaml) | `> 85` Redis 内存比例 |
| ingress-nginx-5xx-rate | [ingress.rules.yaml](ingress.rules.yaml) | `> 0.05` 5xx 错误率 |

## 离线检查

```bash
bash alerts/check.sh test
```

需要 Python3、PyYAML 和 promtool，详见 [tests/README.md](../tests/README.md)。