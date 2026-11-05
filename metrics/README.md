# 指标采集：用CRD添加与更新

本目录管理采集目标，不管理告警阈值。先安装 [基础栈](../install/README.md)。ServiceMonitor采集Service端点，PodMonitor直接采集Pod，Probe通过Blackbox探测外部目标。它们不会自动安装被采集组件或exporter。

| 对象 | 采集方式 | 告警匹配的job |
| --- | --- | --- |
| Flink JM/TM | 开启Flink Prometheus reporter及命名metrics端口；PodMonitor分别采集 | flink-jobmanager / flink-taskmanager |
| Kafka | 独立kafka-exporter Service + ServiceMonitor | kafka-exporter |
| Doris FE/BE | 实际部署暴露的metrics端点 + ServiceMonitor，需核对版本 | doris-fe / doris-be |
| MySQL | mysqld-exporter Service + ServiceMonitor | mysqld-exporter |
| Redis | redis-exporter Service + ServiceMonitor | redis-exporter |
| 域名HTTP/证书 | Blackbox Exporter + Probe | blackbox-http-external |
| 节点、K8s对象、PVC、容器 | KPS自带node-exporter/kube-state-metrics/kubelet采集 | 保留KPS默认，不重复创建 |

每个业务exporter要按其版本配置认证/权限及目标连接信息，再检查 `/metrics`。此处提供通用接入模板，不包含各中间件或exporter的完整安装包；尚未部署的组件不要创建假的监控对象，也要从alerts缺失检测中移除对应job。

## 1. 查清实际标签、端口和目标

```bash
kubectl -n REPLACE_APP_NAMESPACE get svc,pods --show-labels
kubectl -n REPLACE_APP_NAMESPACE get svc REPLACE_EXPORTER_SERVICE -o yaml
kubectl -n REPLACE_APP_NAMESPACE get pod REPLACE_EXPORTER_POD -o yaml
```

ServiceMonitor.selector匹配**Service标签**，endpoint.port匹配**Service端口名称**，不是Pod标签/端口数字。PodMonitor匹配Pod标签和Pod命名端口。监控CR本身放monitoring，被采集目标由namespaceSelector选择。NetworkPolicy必须允许Prometheus访问目标端口。

## 2. 复制需要的模板并修改

```bash
mkdir -p .local/metrics
cp metrics/servicemonitor.example.yaml .local/metrics/mysql.yaml
# 按需复制另外两种，不能不改参数就全部apply
# cp metrics/podmonitor.example.yaml .local/metrics/flink-jm.yaml
# cp metrics/probe-http.example.yaml .local/metrics/domains.yaml
```

编辑新文件：唯一metadata.name、目标namespace、真实selector和命名端口、路径/协议、job。元数据保留 `release: kps` 才能被本例Prometheus选中。通过endpoint.relabelings设置job与alerts规则约定一致，克隆其他组件时一起改job。Flink JM/TM要分别建对象，Doris FE/BE亦然。

Probe需先独立部署Blackbox。填真实Service DNS与端口、模块和目标列表；例如Exporter配置中的http_2xx模块需存在。证书指标依赖HTTPS成功建立TLS连接。保留TLS校验，目标认证/重定向/期望状态按需求在Blackbox模块配置。模块配置属于Blackbox自身ConfigMap，Probe CR只引用模块。

## 3. 预检、部署与更新

```bash
# 此命令输出应为空；若仍有占位符，先编辑文件
grep -n REPLACE_ .local/metrics/mysql.yaml
kubectl apply --dry-run=server -f .local/metrics/mysql.yaml
kubectl diff -f .local/metrics/mysql.yaml
```

diff退出1表示有变更，退出>1才是错误。确认差异后执行：

```bash
kubectl apply -f .local/metrics/mysql.yaml
kubectl -n monitoring get servicemonitor,podmonitor,probe -l release=kps
```

以后修改同一文件并重复预检/diff/apply即可，Operator自动更新采集配置，不需要重启Prometheus或Helm upgrade。删除目标则审查后delete具体CR，同时调整对应缺失告警。不要对整个示例目录直接apply。

## 4. 验收

在Prometheus Targets确认该job的实际目标数量、labels、UP及Last Error；查询 `up{job="mysqld-exporter"}` 和 `mysql_up{job="mysqld-exporter"}`，二者分别反映抓取成功与数据库连接成功。其他组件按 [告警指标依赖](../alerts/README.md) 查询实际指标。CR存在不代表被选中，up=1也不代表所有业务指标都存在。

确认版本对应的指标名、单位和label后再启用告警。聚合会删掉未保留的label，某些指标本来没有IP；模板只能显示已有标签，不能补出不存在的IP。额外metricRelabel过滤可能删除告警依赖，变更后重新验收Rules页面。
