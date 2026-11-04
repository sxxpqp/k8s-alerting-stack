# 逐步核对得到的配置事实

来源：维护者按步骤提供的现网输出；日期 2026-11-04。不含真实机器人 key 或人员信息。

## 安装来源

维护者确认采用 kube-prometheus 0.14.0 manifests 方式安装，不是 kube-prometheus-stack Helm chart。现网运行组件后来是否升级仍需原文件和变更记录确认：原始 v0.14.0 的 Prometheus manifest 为 2.54.1，而已提供的运行镜像是 3.11.3；不能将整套原始 0.14.0 manifests 直接重新 apply 到现网。

[固定版本上游](https://github.com/prometheus-operator/kube-prometheus/tree/v0.14.0) 的兼容性表包含 Kubernetes 1.28；这不代表现网后续升级后的组件组合已经经过该版本上游测试。

## Prometheus 选择器

当前 serviceMonitorSelector、serviceMonitorNamespaceSelector、podMonitorSelector、podMonitorNamespaceSelector、ruleSelector、ruleNamespaceSelector 均为 `{}`。

因此当前这些选择器不会根据 release 标签排除跨 namespace 的 Monitor / Rule。之前记录的混用标签风险在“选择器排除”这一点上已经排除；RBAC、端点发现与实际加载仍需运行态验证。后续生成器明确区分未设置、null 和空对象。

告警目标：`monitoring/alertmanager-main`，Service 端口名 `web`，API v2。

## Alertmanager 配置来源

CR 的 configSecret、alertmanagerConfiguration、alertmanagerConfigSelector、alertmanagerConfigNamespaceSelector 未显式设置。默认配置 Secret `monitoring/alertmanager-main` 已实际确认存在，键为 `alertmanager.yaml`。

脱敏配置保存在 `baseline/alertmanager.yaml`。

- group_by：instance / namespace；没有 alertname。
- group_wait：30s；group_interval：5m；repeat_interval：1h；原配置注释的其他时间值已过期。
- 实际通知 URL 为 type=wx、tpl=prometheus-wx，只看到企业微信机器人接收器；没有钉钉渠道。
- webhook 未显式设置 send_resolved。Alertmanager webhook 默认发送恢复通知，且已观察到恢复消息；后续生成配置显式声明该值。
- critical 子路由与默认路由使用相同接收器；Default / Critical 为未引用的空 receiver。
- Watchdog 被路由到空 receiver，当前没有外部死信/心跳接收动作。
- 抑制规则的 namespace+alertname 等值条件可能跨同 namespace 的不同告警对象抑制；是否调整取决于目标规则标签。

## 模板已确认的根因

实际使用的原文保存在 `baseline/prometheus-wx.tmpl`，包含维护者提供的反斜杠转义形式。是否为实际存储形式或复制展示形式还需页面实测，不擅自当作正常模板语法清理。

| 模板读取 | 已提供的 5xx 规则数据 | 结果 |
| --- | --- | --- |
| labels.level | labels.severity=warning | 级别 `<no value>` |
| labels.instance | 只按 ingress 聚合，instance 已移除 | IP `<no value>` |
| annotations.description | 只有 annotations.summary | 说明 `<no value>` |

这三个缺字段现象不是发送平台无法支持，而是规则数据和固定模板不匹配。候选模板应优先 severity，兼容 level；description 回退 summary；对象按实际标签显示。

原模板从 commonLabels 拼接一个组级屏蔽链接。当前 group_by 不含 alertname，一组可能有不同告警名称，共同标签可能无法限定某条告警；手动拼接也未完整处理值的 URL 编码。应在新模板中明确逐条/逐组静默语义，并验证实际 Alertmanager 外部 URL，不直接复用现有拼接逻辑。

## 下一步只确认一项

读取 PrometheusAlert Deployment 的镜像、volumeMounts 和 volumes，不读取明文 env 值。目标是定位 app.conf 与模板数据库/持久卷。确认存储方式后再提供定点配置备份和模板导入/恢复流程，最终服务于新环境部署复用。
