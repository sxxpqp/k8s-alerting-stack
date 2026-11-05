# 安装 Prometheus 与 Alertmanager

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

本例固定Chart **92.18.0 / Operator 0.94.2**，Chart声明Kubernetes >=1.25；仍需在实际目标版本做dry-run。容量是起点而非容量承诺：Prometheus每副本50Gi/2Gi内存请求，共2副本；Alertmanager每副本2Gi，共3副本。按采集序列数、采集频率、WAL积压、节点资源和存储能力调整；跨节点/可用区调度策略按环境补齐。

## 2. 准备环境参数与认证

```bash
mkdir -p .local .generated
chmod 700 .local
cp install/kps-values.example.yaml .local/kps-values.yaml
```

编辑 `.local/kps-values.yaml` 的全部 `REPLACE_*`：集群唯一名称、StorageClass、Mimir网关HTTPS域名、租户。检查容量和副本数。Mimir需已独立安装并提供 `/api/v1/push`；本项目不安装Mimir。示例假设网关BasicAuth+多租户header；如果实际用BearerToken、mTLS或单租户，修改对应认证字段/header，不要保留错误认证。凭证仅存Secret，不提交Git。

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
if grep -n REPLACE_ .local/kps-values.yaml; then echo '先替换以上参数'; exit 1; fi
```

**HA前置条件：** 两个Prometheus都会remote_write同一批指标。Mimir必须启用HA tracker，并为对应租户启用 `accept_ha_samples`；HA标签匹配 `cluster` 和 `__replica__`。本例将副本标签明确设为 `__replica__`。未配置Mimir去重时先用1副本，不能宣称2副本已实现去重。Mimir保留期由Mimir另设，和本地6h无关。

## 3. 下载固定Chart并安装CRD

```bash
mkdir -p .local/chart
helm pull oci://ghcr.io/prometheus-community/charts/kube-prometheus-stack \
  --version 92.18.0 --untar --untardir .local/chart
helm show chart .local/chart/kube-prometheus-stack
helm show crds .local/chart/kube-prometheus-stack > .local/crds.yaml
kubectl apply --server-side -f .local/crds.yaml
kubectl wait --for=condition=Established --timeout=120s \
  crd/prometheuses.monitoring.coreos.com \
  crd/alertmanagers.monitoring.coreos.com \
  crd/servicemonitors.monitoring.coreos.com \
  crd/podmonitors.monitoring.coreos.com \
  crd/probes.monitoring.coreos.com \
  crd/prometheusrules.monitoring.coreos.com \
  crd/alertmanagerconfigs.monitoring.coreos.com
```

本次下载OCI digest：`sha256:bf0af6052d5e38a59118bb14f1cb5db1705a45d18799836d699e0a21d6ff5b76`。下载时核对输出。已有CRD发生字段所有权冲突时先查原管理者，不直接加force-conflicts。升级Chart前备份并按目标版本更新CRD；不要假设Helm upgrade一定代管CRD升级。

## 4. 渲染、预检和安装

```bash
helm lint .local/chart/kube-prometheus-stack -f .local/kps-values.yaml
# 将1.30.0替换为目标集群版本
helm template kps .local/chart/kube-prometheus-stack -n monitoring \
  --kube-version 1.30.0 -f .local/kps-values.yaml > .generated/kps.yaml
helm upgrade --install kps .local/chart/kube-prometheus-stack -n monitoring \
  -f .local/kps-values.yaml --dry-run=server
# 确认预检无误后执行实际安装
helm upgrade --install kps .local/chart/kube-prometheus-stack -n monitoring \
  -f .local/kps-values.yaml --wait --timeout 10m
```

预检不能证明镜像可拉取、PVC能绑定或远端认证正确。失败时检查Events和Pod日志，不能只看Helm返回。dry-run输出也可能含Secret，`.generated/`禁止提交。

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

**通知此时默认丢弃。** 这是后续接入PrometheusAlert前的分阶段安装：先验收采集与规则，再按notifications文档建立Secret和路由，完成真实测试才算完整告警链路可用。Grafana、业务exporter、Blackbox和PrometheusAlert需独立部署，Chart不会替本项目安装这些业务依赖。

## 6. 后续更新与回滚

核心Prometheus/Alertmanager CR由Helm管理：改 `.local/kps-values.yaml`，重复lint/template/server dry-run/upgrade，不手改生成CR。指标与规则变更分别走metrics和alerts的CRD流程，无需每次重装Helm。

```bash
helm get values kps -n monitoring > .local/values-backup.yaml
helm history kps -n monitoring
helm rollback kps REPLACE_REVISION -n monitoring --wait --timeout 10m
```

回滚不会自动回滚CRD schema、外部Secret或数据；升级前备份values/自管CR和受控Secret。不要为排障直接删PVC、CRD或卸载整个栈。

依据：[固定Chart](https://github.com/prometheus-community/helm-charts/tree/kube-prometheus-stack-92.18.0/charts/kube-prometheus-stack)、[Mimir HA去重](https://grafana.com/docs/mimir/latest/configure/configure-high-availability-deduplication/)。
