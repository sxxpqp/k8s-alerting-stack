# 待确认配置台账

用户已选择：先接管现网配置，再补新环境安装流程；钉钉群 + 企业微信群机器人；现有部署参数优先。

不要求用户重新设计 namespace、容量或域名，先从运行配置提取。只有配置缺失或需要变更时再提出具体选择。

| 配置 | 当前证据 | 下一步 |
| --- | --- | --- |
| 安装来源和原始清单仓库 | Helm 没有对应 release | 提供已有 manifest / Jsonnet / 脚本位置；找不到则记录为未知，逐项重建 |
| Prometheus rule / monitor selectors | 未提供 CR spec | 发采集脚本 review 文件 |
| 跨 namespace 发现与 RBAC | Monitor 分布多个 namespace | 对照 selector、Service / Pod 标签、Targets 和权限 |
| 告警发送与双副本去重 | 只有副本数量 | 查 alerting 目标、externalLabels、alert_relabel_configs；注入单条测试验收 |
| Alertmanager route / inhibit / group / receiver | 未提供，AlertmanagerConfig 列表为空 | 由 Alertmanager CR configSecret / workload 引用定位，脱敏后保存 |
| PrometheusAlert 模板 | 只看到渲染消息 | 提供实际模板正文、名称和脱敏后的模板选择参数 |
| 两个机器人配置 | 渠道已选定，实际配置未知 | 凭据只保存在本地/受控 Secret；确认 keyword / 加签 / @人员 / 频率限制 |
| 模板及数据库持久化 | Deployment 未提供 | 查挂载卷、SQLite / 外部数据库、备份方式；先备份再更改 |
| PVC / StorageClass / 资源容量 | 未提供 | 从现有 CR / PVC 提取，确认可恢复性；不预设容量 |
| 公网入口和消息里的链接 | NodePort 已存在 | 沿用现有访问方式，核对 Prometheus / Alertmanager / Grafana 外部 URL 和屏蔽链接 |
| 规则对象标签 | 5xx 规则只有 ingress | 查询实际指标；namespace 可能受采集 relabel 影响，核实最终标签 |
| 阈值与窗口 | 5xx >5%，rate 2m，for 5m | 第一轮保持；是否增加最低请求量由实际业务流量决定 |

发布前必须完成：选择器可证明命中、规则可证明加载、原始 JSON 与模板字段一致、两个群各收到 firing/resolved、无重复发送、恢复时间和时区显示正确。未完成的项保留“待验证”，不能标为已上线。
