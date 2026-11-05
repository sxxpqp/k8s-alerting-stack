# 安装 Prometheus、Alertmanager 与 Grafana

适用新环境：Helm release `kps`，namespace `monitoring`，Prometheus 本地6h、远程写入Mimir。以下命令使用 Linux bash，在仓库根目录执行。先完成本页，再按 [采集](../metrics/README.md) → [告警](../alerts/README.md) → [通知](../notifications/README.md) 验收。

## 1. 检查目标环境

```bash
kubectl config current-context
kubectl version
helm version
helm list -A
kubectl get crd prometheuses.monitoring.coreos.com alertmanagers.monitoring.coreos.com
kubectl get storageclass
kubectl get nodes
```

确认当前context正确；具备创建CRD、ClusterRole、namespace和PVC的权限；StorageClass可动态供给存储。CRD不存在时上述get报NotFound属预期。已有Prometheus Operator/同名release时停止新装，先导出现有values并确定由谁管理集群级CRD，不能同时安装两个Operator争用资源。

本例固定Chart **92.17.1 / Operator 0.94.2**，Chart声明Kubernetes >=1.25；仍需在实际目标版本做dry-run。容量是起点而非容量承诺：Prometheus每副本20Gi/1Gi内存请求、2Gi内存上限，共2副本；Alertmanager每副本2Gi，共3副本；Grafana单副本5Gi。按采集序列数、采集频率、WAL积压、节点资源和存储能力调整；跨节点/可用区调度策略按环境补齐。

## 2. 准备环境参数与认证

```bash
mkdir -p .local .generated
chmod 700 .local
cp install/prom-values.example.yaml prom-values.yaml
```

编辑 `prom-values.yaml` 的全部 `REPLACE_*`：集群唯一名称、StorageClass、Mimir网关HTTPS域名、租户。检查容量和副本数。Mimir需已独立安装并提供 `/api/v1/push`；本项目不安装Mimir。示例假设网关BasicAuth+多租户header；如果实际用BearerToken、mTLS或单租户，修改对应认证字段/header，不要保留错误认证。凭证仅存Secret，不提交Git。

```bash
kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -
umask 077
read -r -p 'Mimir username: ' MIMIR_USER
read -r -s -p 'Mimir password: ' MIMIR_PASS; printf '\n'
printf '%s' "$MIMIR_USER" > .local/mimir-username
printf '%s' "$MIMIR_PASS" > .local/mimir-password
unset MIMIR_USER MIMIR_PASS
kubectl -n monitoring create secret generic mimir-remote-write \
  --from-file=username=.local/mimir-username \
  --from-file=password=.local/mimir-password \
  --dry-run=client -o yaml | kubectl apply -f -
rm -f .local/mimir-username .local/mimir-password
if grep -n REPLACE_ prom-values.yaml; then echo '先替换以上参数'; exit 1; fi
```

**HA前置条件：** 两个Prometheus都会remote_write同一批指标。Mimir必须启用HA tracker，并为对应租户启用 `accept_ha_samples`；HA标签匹配 `cluster` 和 `__replica__`。本例将副本标签明确设为 `__replica__`。未配置Mimir去重时先用1副本，不能宣称2副本已实现去重。Mimir保留期由Mimir另设，和本地6h无关。

### 参考配置中的注意事项

- 保留Prometheus 2副本、Alertmanager 3副本；Prometheus请求200m CPU/1Gi内存、内存上限2Gi、每副本20Gi PVC；Grafana 5Gi PVC。它们是起始配置，需按实际序列量和查询负载调整。
- `retention: 6h` 与 `retentionSize: 10GB` 同时设置，先达到的条件生效，容量受限时保留可能短于6h；容量限制不包含所有WAL/临时空间开销，20Gi PVC仍需监控剩余空间，不能保证任何负载下都不满盘。
- `prometheusExternalLabelName: cluster` 会占用cluster保留键，使 `externalLabels.cluster: test-a` 被Operator忽略。本例改为 `prometheusExternalLabelName: prometheus`，`externalLabels.cluster` 按环境填test-a等唯一集群名称。[Operator生成逻辑](https://github.com/prometheus-operator/prometheus-operator/blob/v0.94.2/pkg/prometheus/promcfg.go)
- 强制反亲和需要至少两个可调度节点（含污点、资源、存储拓扑限制）；不足时副本Pending。使用Chart内置 `podAntiAffinity: hard` 自动匹配本实例，避免自定义affinity与默认soft策略生成重复podAntiAffinity键；单节点测试环境可降低副本或改为preferred，不能宣称获得同等HA。
- 参考环境暂关闭etcd/scheduler/controller-manager/kube-proxy采集及对应默认规则。不是所有kind/kubeadm集群都必须关闭；先检查端点可达性，生产应按实际安全端点恢复采集及规则，否则这些组件没有监控覆盖。
- selector继续使用显式 `release: kps`，配合NilUsesHelmValues=false；它不表示接受全部无标签CR。metrics/alerts模板必须保留该标签。
- 不写死Grafana adminPassword。Chart生成初始Secret，按下文获取；已有企业凭证可使用Grafana的admin.existingSecret引用，按该Chart版本字段配置。

## 3. 添加Helm仓库

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm show chart prometheus-community/kube-prometheus-stack --version 92.17.1
```

新环境首次安装由Chart安装所需CRD，无需额外下载OCI包或手动逐个安装CRD。已有Operator/CRD时先核对管理关系；升级CRD按目标Chart说明处理，不假设Helm自动升级所有CRD。

## 4. 预览并安装

```bash
# 保存完整预览，成功后查看前30行；不要用head截断作为成功依据
helm install kps prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace \
  -f prom-values.yaml --version 92.17.1 \
  --dry-run=client > .generated/kps-dry-run.txt
head -30 .generated/kps-dry-run.txt

# 确认参数及预览无误后实际安装
helm install kps prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace \
  -f prom-values.yaml --version 92.17.1
```

client dry-run只验证客户端渲染，不验证集群准入、镜像拉取、PVC绑定或远端认证。首次CRD尚未存在时不强制server dry-run；安装后按下列命令检查就绪状态。预览可能含Secret，禁止提交.generated。已有kps release时使用第6节的upgrade，不重复install。

```bash
helm status kps -n monitoring
kubectl -n monitoring get prometheus,alertmanager,pods,pvc,svc
kubectl -n monitoring get events --sort-by=.lastTimestamp
kubectl -n monitoring get prometheus -o yaml
```

核对Prometheus CR的retention=6h、externalLabels.cluster、remoteWrite、各采集/rule selector的 `release: kps`；Alertmanager为3副本。PVC应Bound、Pod应Ready。无可用指标时不要急着加告警。

## 5. 验收采集与远程写入

从 `get svc` 输出找到本release的Prometheus Service名，再执行（替换服务名）：

```bash
kubectl -n monitoring port-forward svc/REPLACE_PROMETHEUS_SERVICE 9090:9090
```

另开终端访问 `http://127.0.0.1:9090`：Status/Targets查看基础采集UP，Status/Rules确认默认规则加载；查询 `up`、`prometheus_remote_storage_samples_pending`、`rate(prometheus_remote_storage_samples_failed_total[5m])` 和 `time() - prometheus_remote_storage_queue_highest_sent_timestamp_seconds`。这些自监控指标需按实际Prometheus版本核对；同时检查remote_write日志和Mimir接收指标。积压/失败持续增长即未验收通过。再从Mimir查询该cluster的 `up`，确认数据新鲜、HA去重正常；仅本地up正常不能证明已写到Mimir。

externalLabels用于对外发送，并不自动加入本地所有原始序列。集群内规则不要假设原始指标必有cluster标签。本地评估不依赖Mimir查询；远写中断期间WAL缓冲有限，不能把6h保留期视为无限远写补偿保障。

本地保留仅6h，示例关闭包含长窗口的上游 `kubeApiserverAvailability`、`kubeApiserverBurnrate`、`kubeApiserverSlos` 组。长窗口规则须另行部署到有足够历史数据的Mimir Ruler，并配置Ruler通知链路；当前未提供或声称完成该迁移。每次Chart升级都重新审查渲染规则的range/subquery/offset，不只检查自定义规则。

**通知此时默认丢弃。** 这是后续接入PrometheusAlert前的分阶段安装：先验收采集与规则，再按notifications文档建立Secret和路由，完成真实测试才算完整告警链路可用。Grafana随本Chart安装并启用持久化；业务exporter、Blackbox和PrometheusAlert仍需独立部署。

### Grafana访问与验收

默认启用单副本Grafana、5Gi持久化PVC、ClusterIP，先不暴露公网。上面的StorageClass也要替换Grafana.persistence.storageClassName。

```bash
kubectl -n monitoring get pods,svc,pvc -l app.kubernetes.io/name=grafana
# release名kps且未覆盖name时默认如下；如实际名称不同以get svc/secret为准
kubectl -n monitoring get secret kps-grafana -o jsonpath='{.data.admin-user}' | base64 -d; echo
kubectl -n monitoring get secret kps-grafana -o jsonpath='{.data.admin-password}' | base64 -d; echo
kubectl -n monitoring port-forward svc/kps-grafana 3000:80
```

在运行port-forward的电脑打开 `http://127.0.0.1:3000`；远程服务器执行时通过SSH本地转发访问。密码仅在自己的终端查看，不粘贴到工单或Git。登录后修改初始密码，检查默认Prometheus数据源查询成功、Kubernetes仪表盘有数据、PVC为Bound。NodePort/Ingress域名和TLS按实际环境另配，不默认开放外网。

## 6. 后续更新与回滚

核心Prometheus/Alertmanager CR由Helm管理：改 `prom-values.yaml`，预览后执行Helm upgrade，不手改生成CR。指标与规则变更分别走metrics和alerts的CRD流程，无需每次重装Helm。

```bash
# 同一release后续变更values（版本保持固定，升级版本另行评审）
helm upgrade kps prometheus-community/kube-prometheus-stack \
  -n monitoring -f prom-values.yaml --version 92.17.1 --dry-run=client
helm upgrade kps prometheus-community/kube-prometheus-stack \
  -n monitoring -f prom-values.yaml --version 92.17.1 --wait --timeout 10m
helm get values kps -n monitoring > .local/values-backup.yaml
helm history kps -n monitoring
helm rollback kps REPLACE_REVISION -n monitoring --wait --timeout 10m
```

回滚不会自动回滚CRD schema、外部Secret或数据；升级前备份values/自管CR和受控Secret。不要为排障直接删PVC、CRD或卸载整个栈。

依据：[固定Chart](https://github.com/prometheus-community/helm-charts/tree/kube-prometheus-stack-92.17.1/charts/kube-prometheus-stack)、[Mimir HA去重](https://grafana.com/docs/mimir/latest/configure/configure-high-availability-deduplication/)。
