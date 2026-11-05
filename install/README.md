# 安装 Prometheus、Alertmanager、Grafana

本页完成基础监控栈安装。Mimir和PrometheusAlert不作为安装前置条件；基础采集验收通过后再接入。命令使用Linux bash，在仓库根目录执行。

固定参数：Chart `92.17.1`、Helm release `kps`、namespace `monitoring`。

## 1. 检查环境

```bash
kubectl config current-context
kubectl get nodes
kubectl get storageclass
helm version
helm list -A
```

确认目标集群正确、StorageClass可用。本例Prometheus有两个副本并强制分散到不同节点，至少需要两个满足资源、污点及存储约束的可调度节点。已有kps release时使用本页第7节更新，不重复install；已有其他Operator时先核对CRD归属和监听范围。Chart声明Kubernetes >=1.25，仍需在目标集群验收。

## 2. 准备配置文件

```bash
cp install/prom-values.example.yaml prom-values.yaml
```

编辑 `prom-values.yaml`，先替换：

| 参数 | 填什么 |
| --- | --- |
| `externalLabels.cluster` | 唯一集群名，例如test-a |
| 三处 `storageClassName` | 实际StorageClass，例如standard；分别用于Prometheus、Alertmanager和Grafana |

检查是否还有未替换的参数，输出应为空：

```bash
grep -n REPLACE_ prom-values.yaml
```

默认资源和开关已写在values注释中。Prometheus每副本20Gi，Alertmanager每副本2Gi，Grafana 5Gi。默认没有remoteWrite，无需Mimir地址或认证Secret。

## 3. 添加Helm仓库

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
```

## 4. 预览并安装

```bash
helm install kps prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace \
  -f prom-values.yaml --version 92.17.1 \
  --dry-run=client
```

确认无报错后安装：

```bash
helm install kps prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace \
  -f prom-values.yaml --version 92.17.1
```

Chart负责首次安装所需CRD。client dry-run不验证Pod调度、存储或网络，安装后继续验证组件就绪状态。

## 5. 验证安装

```bash
helm status kps -n monitoring
kubectl -n monitoring get prometheus,alertmanager,pods,pvc,svc
kubectl -n monitoring get events --sort-by=.lastTimestamp
```

等到以下状态满足再继续：Prometheus两个副本Ready，Alertmanager三个副本Ready，Grafana一个副本Ready，相关PVC全部Bound。Pending先看Events中的资源、调度和存储错误；CrashLoop查看对应Pod日志。Helm显示deployed不等于组件已就绪。

以下Service名适用于本例release和默认命名；覆盖了nameOverride/fullnameOverride时以 `kubectl get svc` 为准。分别在独立终端执行：

```bash
kubectl -n monitoring port-forward svc/kps-kube-prometheus-stack-prometheus 9090:9090
```

打开 `http://127.0.0.1:9090`，查询 `up`，查看Targets和Rules页面。基础采集应有数据，规则health正常；DOWN目标先排查，不直接认定为业务故障。

```bash
kubectl -n monitoring port-forward svc/kps-kube-prometheus-stack-alertmanager 9093:9093
```

打开 `http://127.0.0.1:9093`，确认Alertmanager可访问。**当前默认接收器为空，不会发送群消息**；通知对接见第6节。

### 登录Grafana

在自己的终端获取初始账号和密码：

```bash
kubectl -n monitoring get secret kps-grafana -o jsonpath='{.data.admin-user}' | base64 -d; echo
kubectl -n monitoring get secret kps-grafana -o jsonpath='{.data.admin-password}' | base64 -d; echo
kubectl -n monitoring port-forward svc/kps-grafana 3000:80
```

打开 `http://127.0.0.1:3000`，登录后修改初始密码；检查默认Prometheus数据源和Kubernetes仪表盘有数据。以上地址指运行port-forward的电脑，远程服务器上执行时需用SSH隧道转发到自己的电脑。需要NodePort/Ingress时另配实际端口或域名/TLS。

## 6. 基础安装通过后做什么

1. 按 [metrics](../metrics/README.md) 接入实际业务采集，先确认目标和指标存在。
2. 按 [alerts](../alerts/README.md) 选择已部署组件的告警，校验后apply。
3. 按 [prometheusalert](../prometheusalert/README.md) 部署通知服务，使用共享MySQL保存模板，再按 [notifications](../notifications/README.md) 接通钉钉/飞书，验收触发和恢复消息。
4. 需要远程存储时，按 [可选：对接Mimir](mimir.md) 开启remote_write；不影响前面步骤独立完成。

本Chart不安装业务exporter、Blackbox、MySQL或Mimir。PrometheusAlert使用本项目单独提供的Kustomize清单部署；各组件部署完成后再创建相应采集/通知CR。

## 7. 后续更新与回滚

采集、告警、通知分别修改对应CR文件并apply。只有核心栈参数变化时修改 `prom-values.yaml` 并Helm upgrade。先备份当前values：

```bash
umask 077
helm get values kps -n monitoring > prom-values.before-upgrade.yaml
helm history kps -n monitoring
```

预览变更：

```bash
helm upgrade kps prometheus-community/kube-prometheus-stack \
  -n monitoring -f prom-values.yaml --version 92.17.1 --dry-run=client
```

确认后更新，再重复第5节验收：

```bash
helm upgrade kps prometheus-community/kube-prometheus-stack \
  -n monitoring -f prom-values.yaml --version 92.17.1 --wait --timeout 10m
```

需要回滚时，从history选择升级前的revision，替换下面的编号再执行：

```bash
helm rollback kps REPLACE_REVISION -n monitoring --wait --timeout 10m
```

回滚不自动还原CRD、独立管理的CR/Secret或PVC数据。更换Chart版本前按 [上游升级说明](https://github.com/prometheus-community/helm-charts/tree/kube-prometheus-stack-92.17.1/charts/kube-prometheus-stack#upgrading-chart) 检查CRD升级要求。
