# 各组件安装与配置入口

用户要求：每个组件都要说明怎么安装、配置文件怎么填写，并给出模板。下面锁定已知安装来源与模板入口，未完成的组件流程明确列为待补。**当前现网仅允许只读，不执行本页任何部署或重载操作。** 新环境安装也必须先完成环境参数、版本组合与验收步骤，不能把 upstream quickstart 当作已经验收的生产部署。

## 安装源与目录

基础来源：官方 kube-prometheus `v0.14.0`，采用 manifests / Jsonnet 体系，不是 Helm kube-prometheus-stack。现网 Prometheus 已运行 3.11.3、Operator 已运行 0.91.0，和原始 0.14.0 的组件组合存在差异。新环境需选择“已验证原始组合”或“已验证升级组合”，不能混用两个版本的 CRD、Operator 与 reloader；当前尚未完成升级组合验证。

源码准备（只在本地下载，不安装集群）：

```bash
mkdir -p .local/upstream
git clone --branch v0.14.0 --depth 1 \
  https://github.com/prometheus-operator/kube-prometheus.git \
  .local/upstream/kube-prometheus-v0.14.0
git -C .local/upstream/kube-prometheus-v0.14.0 rev-parse HEAD
```

记录实际 commit SHA；网络不通时由管理机下载同一版本离线包，并验证来源和版本。安装前将源清单复制到独立环境输出目录，所有 patch 在输出/overlay 层处理，不直接维护一份随意改过的上游副本。目前生成器尚待实现，不能把示例参数文件当作已经支持的输入。

## 组件安装顺序和配置表

官方相对路径均相对于上述 kube-prometheus 目录。每组还包含相应 RBAC / ServiceAccount / NetworkPolicy，不能只复制 Deployment 而漏掉依赖。

| 顺序 | 组件 | 官方文件/本项目配置入口 | 环境必核对 | 验证 |
| --- | --- | --- | --- | --- |
| 1 | Namespace / CRD | manifests/setup/ | Kubernetes 兼容性、现有 CRD 与所有权 | 对所需 CRD 等待 Established；不要等待或修改无关 CRD |
| 2 | Prometheus Operator | manifests/prometheusOperator-* | image/reloader 与 CRD 版本，RBAC、监听 namespace | deployment Ready，日志无 reconcile 错误 |
| 3 | node-exporter | manifests/nodeExporter-* | 节点覆盖、host 端口、TLS/RBAC 代理、ServiceMonitor、job 标签 | Linux 节点上的 DaemonSet Ready；Targets UP；node_cpu_seconds_total 等指标存在 |
| 4 | kube-state-metrics | manifests/kubeStateMetrics-* | 对象权限、allowlist、ServiceMonitor 双 endpoint、业务 namespace 标签 | Targets UP；kube_pod_info、kube_deployment_spec_replicas 等指标存在 |
| 5 | Prometheus | manifests/prometheus-* 与 kubernetesControlPlane-*、kubePrometheus-* | replicas、PVC、retention、resources、externalLabels.cluster、各 selector、Alertmanager 目标和入口 | PVC Bound、两个副本各自 Ready；Targets、Rules、记录规则与告警发送正确 |
| 6 | Alertmanager | manifests/alertmanager-* | PVC、replicas、route/group/inhibit、receiver、send_resolved、externalURL | peers、reload、firing/resolved、静默、去重和抑制均验证 |
| 7 | Blackbox | manifests/blackboxExporter-* | modules 配置、探测端口 19115、HTTPS 自监控端口 9115、资源限制与出网 | 自监控 Target UP；另查 probe_success；不能只看 exporter 自身 UP |
| 8 | PrometheusAlert | 独立 Deployment / Service / PVC / app.conf / 模板数据库，待获取现网挂载后补齐固定版本流程 | 版本、持久化、数据库、模板导入、机器人凭据、加签与 @ 策略 | 重建后模板仍在；两个渠道实际收到 firing/resolved |
| 9 | Grafana | 新安装：manifests/grafana-*；已有 Grafana 则仅配置数据源与实际 namespace 的监控 | 数据源、管理员凭据、PVC、域名、与现有 Grafana 的关系 | Explore 可查 Prometheus；Grafana 自身有实际 Target；dashboard 与告警对象链接正确 |
| 10 | Prometheus Adapter（可选） | manifests/prometheusAdapter-* | 是否真的需要 custom metrics / resource metrics，已有 metrics-server 和 APIService 所有权 | APIService Available；实际 HPA/metrics API 正确。不要把它当作告警发送必需组件 |
| 11 | 外部主机 / MySQL / Redis / 业务 exporter（可选） | 每类独立配置与 Monitor，待获取现网对应 exporter 参数后补齐安装模板 | 地址、版本、TLS、最小权限账号、采集器开关、job/namespace/instance 标签与规则覆盖 | Target UP + 指标存在 + 对应规则确实匹配该对象 |

## 各类配置文件具体要填什么

### Prometheus

在 `prometheus-prometheus.yaml` 的 `spec` 中配置：version/image、replicas、resources、retention、storage.volumeClaimTemplate、externalLabels.cluster、serviceMonitorSelector / namespaceSelector、podMonitorSelector / namespaceSelector、probeSelector / namespaceSelector、ruleSelector / namespaceSelector、alerting.alertmanagers。PVC 的 StorageClass、容量和调度从新环境填写，不拷贝现网 IP。

选择器的 `{}`、null、未配置含义不同，按实际 Operator API 验证；当前现网 Monitor / Rule 六个 selector 均为 `{}`，新环境是否全选应成为明确参数。Probe 还需独立验证 probeSelector，不能因 ServiceMonitor 被选中就假定 Probe 被选中。

两个 Prometheus 副本的告警必须去除副本身份标签后再由同一 Alertmanager 集群去重，同时保留唯一 cluster 标签；实际配置/测试后再验收，不根据 replicas=2 推断已完成。

### Alertmanager

`alertmanager-secret.yaml` 承载 `alertmanager.yaml`；本项目 `baseline/alertmanager.yaml` 是脱敏比对样本，不是最终生产模板。新环境最终模板必须包含 route、group、inhibit、钉钉/企微 receiver 和明确 `send_resolved: true`，凭据由本地 Secret 流程提供。

Webhook 最终使用 PrometheusAlert 的模板名和接收渠道配置；不能把当前只存在的企业微信 receiver 当成两渠道已经配置。不要盲目沿用 group_by(instance,namespace) 或把其他 namespace 的同名资源合并；抑制条件也须匹配实际对象边界。

### Blackbox 模块与 Probe

- 模块正文参考 `templates/blackbox-modules.example.yaml`：`http_2xx` 用于 HTTP 状态/TLS 检查；`tcp_connect` 用于 TCP 建连。
- HTTP Probe：`templates/probe-http.example.yaml`。
- TCP Probe：`templates/probe-tcp.example.yaml`，探测成功判断用 `probe_success{job="blackbox-tcp"}`，不使用当前无数据的 probe_tcp_connection_success。
- `prober.url` 沿用本套发行版 Service 的 `blackbox-exporter:19115`；这不是所有发行版通用端口，换发行源要重新核对。
- 例子模块 timeout=8s、Probe scrapeTimeout=10s；模块超时小于采集超时。现网模块真实配置仍需获取，不推断当前 timeout 与例子相同。
- 目标列表、env、cluster、分组标签按环境填写。example.com 仅为占位目标，模板含 REPLACE 字段时禁止部署。
- 机器人/业务认证 Token 不放在公开目标列表；有认证模块时用受控 Secret，分享前脱敏。

新环境配置完成后的验证顺序：CR 被 Prometheus 选中 → Targets 出现 probe job → exporter 抓取 UP → probe_success 反映真实目标 → 故障测试产生专属告警 → 两渠道收到恢复。Pod/Service 正常只是其中一步。

### ServiceMonitor / PodMonitor

分别参考 `templates/servicemonitor-app.example.yaml`、`templates/podmonitor-app.example.yaml`。

ServiceMonitor：先确认业务 Service 的 labels、命名端口、selector 与 endpoints，然后填写 Monitor 的 selector、namespaceSelector、endpoints.port/path/scheme/interval。port 是 Service 端口名，不能填 NodePort。

PodMonitor：直接匹配 Pod labels 和容器端口名。两者都需要被 Prometheus 的相应 selector 选中；涉及 TLS/认证时不关闭验证来掩盖证书问题。已有告警规则必须与最终采集标签一致。

### PrometheusAlert

需提供固定版本的 Deployment、Service、PVC、app.conf、钉钉/企微模板及导入步骤。当前还缺实际 app.conf、SQLite/外部数据库与挂载定义，所以不虚构容器目录和导入 API。

最终步骤必须覆盖：本地生成凭据 → Secret 引用 → 启动 → 配置存储 → 导入两个渠道模板 → 测试缺字段/混合状态 → 配置 receiver → firing/resolved 联调 → 备份/重建恢复。单个 Deployment Running 不算部署完整。

### 外部主机 / 数据库

外部主机和 K8s 节点的 job 当前不同，基础规则匹配范围须显式处理。MySQL exporter 的实际指标名、采集器开关和 MySQL 主从角色必须确认后提供模板；Redis 的 test / uat 两套 Monitor 也要分别核对实际 Service。数据库账号使用最小权限且凭据不入 Git。

## 每个组件文档的交付格式

所有组件分册都要有以下八项，不能只给一个 apply 命令：

1. 组件用途、是否必选、依赖与端口。
2. 固定来源/版本和兼容性证据。
3. 文件清单和每个文件的作用。
4. 必改/可选/保持默认字段及可复制模板。
5. 从准备、渲染、dry-run 到部署的分步命令，注明仅新环境还是已有环境。
6. 各步预期结果和失败后停止条件。
7. 最小真实功能验收，而不只是 Pod Ready。
8. 数据/配置备份、回滚、卸载范围与数据保留约定。

## 当前完成与未完成

已确认：基础安装来源；HTTP Probe 真实配置结构；22 个 ServiceMonitor 与运行态对照；基础采集模板与模块/Probe 参考；逐步只读检查与问题归档。

尚未完成：完整参数化生成器、固定版本全组件渲染、PrometheusAlert 持久化/导入、外部 exporter 安装参数、两渠道联调及新环境全流程测试。不能将本页称为已验收的一键安装手册。

## 官方固定版本参考

- [v0.14.0 资源清单索引](https://github.com/prometheus-operator/kube-prometheus/blob/v0.14.0/kustomization.yaml)
- [Blackbox Deployment 和配置文件挂载](https://github.com/prometheus-operator/kube-prometheus/blob/v0.14.0/manifests/blackboxExporter-deployment.yaml)
- [Blackbox Service 的两个端口](https://github.com/prometheus-operator/kube-prometheus/blob/v0.14.0/manifests/blackboxExporter-service.yaml)
- [原始模块配置](https://github.com/prometheus-operator/kube-prometheus/blob/v0.14.0/manifests/blackboxExporter-configuration.yaml)
