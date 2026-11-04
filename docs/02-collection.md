# 只读采集现网配置

## 1. 确认管理机与上下文

需要 Python 3、kubectl；Helm 可选。先确认当前 context 是目标集群：

```bash
kubectl config current-context
python3 --version
python3 scripts/collect.py
```

脚本打印当前 context 并在本地创建唯一时间目录，不修改集群，不 exec 进入容器，不发送通知。所有 kubectl 调用设置超时，采集失败写入错误记录，不能把缺权限当作没有资源。

默认读取 namespace `monitoring`，Prometheus `k8s`、Alertmanager `main`、Deployment `prometheus-alert-center`；这些名称来自现网记录。其他环境可通过 `--namespace`、`--prometheus`、`--alertmanager`、`--center` 指定。

## 2. 输出是什么

`.local/inventory-<时间>/private/`：工作负载、Prometheus / Alertmanager CR、所有 namespace 的规则和 Monitor、Service、Endpoints、PVC / StorageClass、ConfigMap / Secret 名称、Helm release 清单等。**原始资源可能包含明文环境变量和 last-applied annotation，只做本地备份，不能整目录发送或提交。**没有读取 Secret data、ConfigMap data 或 Helm values。

`.local/inventory-<时间>/review/`：

- `inventory.json`：版本、资源名称、状态与待补配置引用。
- `prometheus-selection.json`：仅导出 externalLabels、rule / monitor 选择器与告警目标等白名单字段；保留缺失字段，避免把 null 和空对象混淆。
- `alertmanager-selection.json`：配置来源及 selector 的白名单字段。
- `ingress-nginx-rule.json`：当前规则 spec 与必要 metadata，不包含 last-applied。
- `center-references.json`：只列 env 名称、valueFrom 引用、卷引用及挂载位置；不输出明文 env 值或命令行参数。
- `errors.json`：采集失败的命令和错误。

分享前检查 review 中的内部域名、业务名称、标签和注解。脚本通过字段白名单限制输出，**不宣称自动识别并脱敏所有业务敏感内容**。确认后把 review 文件提供给协作者，勿发送 private。

## 3. 还需要人工补哪些内容

先发送 review。根据 Secret / ConfigMap 名称引用，再定点导出 Alertmanager 路由配置；不能从名称猜测 Secret 名字。需要的内容是 `route`、`receivers`、`inhibit_rules`、模板文件引用、`send_resolved`。机器人 URL 中的 token、sign、key，以及加签 secret、账号密码统一替换为 `REDACTED`。

PrometheusAlert v4.9.2：从现有页面导出/复制实际在用的钉钉和企业微信模板正文、模板名称、对应 webhook 的模板选择参数；URL 里的凭据脱敏。补充 app.conf 的存储类型及启用渠道配置，凭据留空或脱敏。模板可能存数据库，不能只备份 Deployment 就认为备份完整。

最后补一条真实 `IngressNginx5xxRateHigh` 的原始 webhook JSON（或 Alertmanager 单条告警的 labels / annotations / status / startsAt / endsAt），删除不需要的人员和地址。恢复消息中的数值可能是最后一次告警评估值，不能标成“恢复后实时值”。

## 4. 运行态核验

使用现有 NodePort 或域名打开 Prometheus：

1. Status / Configuration：确认生效的 scrape、rule 文件和 alerting 配置。
2. Targets：查 Ingress、node-exporter、kube-state-metrics 的 up 状态、最终标签和 scrape URL。
3. Rules：搜索完整告警名，记录实际表达式、健康状态和最近一次错误。
4. 查询 `nginx_ingress_controller_requests`，确认 namespace、ingress、controller_class 标签确实存在，再决定新的聚合维度。

运行态配置和 Targets 也可能包含内部地址或凭据引用；本地保存后定点提取，不把整个配置页面公开。
