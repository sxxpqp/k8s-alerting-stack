# 新环境复用：最终交付目标

最终目标：新集群维护者不用阅读或修改大量 YAML，只填写一份环境参数和本地凭据，按手册逐步生成、检查、安装、验证和回滚完整告警系统。当前现网是验证配置和排查历史问题的样本，不把内网 IP、真实域名、固定节点名或机器人 token 烙在通用模板里。

## 两种使用路径

| 路径 | 安装行为 | 适用 |
| --- | --- | --- |
| fresh：新环境 | 固定已核验的发行源和版本，安装 Operator / CRD、Prometheus、Alertmanager、指标组件和通知中心，再加载通用规则与模板 | 没有监控系统的新集群 |
| existing：已有环境 | 读取资源引用和 selectors，生成局部差异，不安装第二个 Operator、不重建同名资源、不擅自接管 Helm 所有权 | 当前集群及其他已有 Prometheus 的集群 |

两条路径分别提供步骤，不能用一条 apply 覆盖两类环境。安装路径需确认后，生成器再实现；当前不提供名为 install 的空壳脚本。

## 参数化边界

| 分类 | 每个环境填写或选择 | 通用项目提供 |
| --- | --- | --- |
| 环境标识 | 唯一 cluster 名、目标 Kubernetes 版本、安装路径、namespace | 参数校验和 externalLabels 约定 |
| 版本 | 已验证的版本组合或明确的升级选择 | 固定发行源、chart/manifest 版本、镜像引用及兼容性记录；不能只用 latest |
| 存储和调度 | StorageClass、容量、保留时间、副本、资源配额和必要的调度约束 | PVC 和有状态服务模板、容量/备份说明 |
| 访问方式 | ClusterIP / NodePort / Ingress、域名、IngressClass、TLS Secret 引用 | 按选择生成入口；不假定集群装有 nginx 或 cert-manager |
| 监控发现 | 哪些 namespace、哪些标签、已有 Service 的 metrics 端口与认证引用 | ServiceMonitor / PodMonitor 示例、selector 对应关系及检查流程 |
| 告警 | 启用规则组、阈值、for、业务归属 | 节点、K8s 对象、采集与告警链路自身健康规则；Ingress/数据库等按需启用 |
| 通知 | 群名称、分级接收器、@策略、通知间隔、凭据引用 | 稳定的 severity / annotations 规范、分组/抑制策略、两个渠道模板 |
| 运行手册链接 | 各环境实际可访问的 Prometheus、Alertmanager、Grafana URL | 正确的告警来源和屏蔽链接构造与验收 |

不强制给每种告警补 IP。Ingress 告警保留 namespace/ingress，Pod 告警保留 namespace/pod，节点告警展示 node/instance。触发值写 annotations，不写会改变告警身份的 labels。

## 预计配置产物

```text
environments/<name>/config.yaml    环境参数，非 Kubernetes 资源
templates/                        通用配置与消息模板
.local/secrets/<name>/             本地凭据，不入库
.generated/<name>/                 后续生成器的输出，不自动 apply、不入库
docs/                             新安装 / 已有环境 / 验收 / 回滚
```

`environments/example/config.yaml` 目前只是参数草案，**不是已经可用的生成器配置**。现网 selectors、Alertmanager config 来源、PrometheusAlert 数据库/模板格式确认后再冻结参数结构。`.generated/` 在生成器实现后才产生，不承诺已有命令。

## 新环境安装手册必须具有的步骤

1. **前置检查**：Kubernetes 版本、权限、DNS/出网、StorageClass、端口与现有监控资源冲突。
2. **填写环境参数**：逐字段说明必填/默认/可选，给出有效示例，不让用户猜 namespace 或 selector。
3. **生成与离线校验**：展示文件清单、固定版本、渲染结果和 promtool/amtool 检查；不自动部署。
4. **安装 CRD / Operator**：固定版本和来源，等待 CRD Established 与 Operator Ready，再创建 CR；更新 CRD 的回滚限制单独说明。
5. **安装数据组件**：Prometheus、Alertmanager、指标采集、通知中心，依次检查 PVC、Pod、Service、endpoints 和配置 reload。
6. **配置采集与规则**：先 Targets，再 Rules，确认选择器和 RBAC；可选业务规则只有依赖指标存在时启用。
7. **导入模板与配置凭据**：精确描述 PrometheusAlert 对应版本的导入、持久化、备份和页面测试过程；不能只启动一个空通知中心 Pod。
8. **接通知路由**：使用测试群验证两个渠道，检查签名/关键词/@人员/频控；凭据不出现在 Git 和公开日志。
9. **端到端验收**：独立测试告警，验证 firing、resolved、去重、静默、抑制、链接及时间显示。
10. **交付与回滚**：记录实际版本、参数与结果，删除测试配置，提供备份恢复和逐组件回滚方式。

每步必须写执行位置、完整命令、所需权限、预期结果、通过/停止条件、失败定位与回传内容。需要页面操作的步骤必须写出页面入口及填写内容，不能留“自行配置机器人”一句话。

## 完成标准

- 在独立环境中从参数生成完整配置，替换环境参数无需手工搜索替换模板里的 IP 和域名。
- 用第二份不同 cluster / namespace / 存储 / 入口的参数再次生成，验证产物没有串用第一份环境值。
- 基础集群和可选 Ingress / 数据库监控分开启用，没有对应组件时不产生大量无数据告警。
- 相同输入生成结果可重复，已有配置不被静默覆盖；密钥仅引用或写受控本地文件。
- 分别记录离线校验、server dry-run、运行态和两渠道送达结果，不能把前两项标作已经上线。
- 当前环境有完整配置归档、新环境有逐步安装说明，未完成部分明确标为待实现/待验证。

目前距离该目标仍缺：完整源配置、发行源和兼容性锁定、生成器、完整新环境部署清单、真实通知联调。第一阶段 PR 交付的是采集与验收基础，不是宣称这些工作已经完成。
