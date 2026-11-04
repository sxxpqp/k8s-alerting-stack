# 待确认配置台账

用户已选择：以现网配置为样本，最终生成新环境可复用的完整部署项目；先采集并核实原配置，再参数化生成与编写全新环境流程；钉钉群 + 企业微信群机器人。现有部署参数是参考值，不应固定为所有环境默认值。

不要求用户重新设计 namespace、容量或域名，先从运行配置提取。只有配置缺失或需要变更时再提出具体选择。

| 配置 | 当前证据 | 下一步 |
| --- | --- | --- |
| 安装来源和原始清单仓库 | 已确认 kube-prometheus v0.14.0 manifests；现网组件有升级差异 | 对照原始清单与当前镜像，补充升级记录 |
| Prometheus rule / monitor selectors | 已取得六个空对象选择器；151 条告警实际加载 | 后续补 Probe selector 与完整 CR、存储参数 |
| 跨 namespace 发现与 RBAC | Monitor 分布多个 namespace | 对照 selector、Service / Pod 标签、Targets 和权限 |
| 告警发送与双副本去重 | 只有副本数量 | 查 alerting 目标、externalLabels、alert_relabel_configs；注入单条测试验收 |
| Alertmanager route / inhibit / group / receiver | 已取得默认 Secret 中配置并脱敏保存，只有企微渠道 | 保留现网只读，生成两渠道候选并评审分组/抑制边界 |
| PrometheusAlert 模板 | 已取得 prometheus-wx 正文与调用参数 | 补持久化配置和未来导入/恢复步骤 |
| 两个机器人配置 | 渠道已选定，实际配置未知 | 凭据只保存在本地/受控 Secret；确认 keyword / 加签 / @人员 / 频率限制 |
| 模板及数据库持久化 | Deployment 未提供 | 查挂载卷、SQLite / 外部数据库、备份方式；先备份再更改 |
| PVC / StorageClass / 资源容量 | 未提供 | 从现有 CR / PVC 提取，确认可恢复性；不预设容量 |
| 公网入口和消息里的链接 | NodePort 已存在 | 沿用现有访问方式，核对 Prometheus / Alertmanager / Grafana 外部 URL 和屏蔽链接 |
| 规则对象标签 | 实际样本已确认业务 namespace/ingress/controller_class；存在跨 namespace 同名 Ingress | 生成保留对象边界的候选，不修改现网 |
| 阈值与窗口 | 5xx >5%，rate 2m，for 5m | 第一轮保持；是否增加最低请求量由实际业务流量决定 |

发布前必须完成：选择器可证明命中、规则可证明加载、原始 JSON 与模板字段一致、两个群各收到 firing/resolved、无重复发送、恢复时间和时区显示正确。未完成的项保留“待验证”，不能标为已上线。
