# 后续对接PrometheusAlert

本页管理 Alertmanager → PrometheusAlert 路由，不安装PrometheusAlert。先完成采集和规则验收；准备已部署、版本明确、集群内可访问的PrometheusAlert，以及已测试的钉钉/飞书模板和机器人。**完整URL应指向PrometheusAlert接收接口，不是直接填聊天机器人URL。** 不同版本的参数/模板名称不同，从实际PrometheusAlert界面或对应版本文档取得完整调用URL，不猜参数。

## 1. 先验证模板字段

Alertmanager发送 `.alerts` 数组，每条有labels/annotations/status；逐条遍历并分别判断firing/resolved，不能只读commonLabels展示全部对象。

- 级别用 `labels.severity`，兼容旧规则时再回退level，仍缺失显示“未设置”。
- 对象依次显示namespace/pod/instance/service/job等存在的字段，不把instance固定叫主机IP。聚合告警可能没有instance。
- 内容优先description，缺失回退summary/message，再显示通用提示；补充suggestion、runbook_url。
- 当前值来自规则渲染到description的 `{{ $value }}`，webhook本身没有统一的value字段。恢复消息显示startsAt和endsAt；时间格式按实际模板函数能力转换。
- generatorURL、externalURL及静默链接要能从接收者网络访问；尚未配置实际入口时不要生成不可用链接。

模板函数属于PrometheusAlert版本能力，不能直接假设Prometheus/Alertmanager模板函数全部可用。先用包含缺标签、聚合对象和恢复状态的样例预览，保证不出现 `<no value>`。模板内容及持久化/导入方式由PrometheusAlert自身管理，不属于Prometheus Operator CRD。

## 2. 安全保存两条PrometheusAlert URL

Linux bash，仓库根目录执行；不要把机器人密钥或完整URL提交Git，也不要开shell xtrace。

```bash
mkdir -p .local
chmod 700 .local
umask 077
read -r -s -p '钉钉对应PrometheusAlert完整URL: ' PA_DING; printf '\n'
read -r -s -p '飞书对应PrometheusAlert完整URL: ' PA_FEISHU; printf '\n'
printf '%s' "$PA_DING" > .local/pa-dingtalk-url
printf '%s' "$PA_FEISHU" > .local/pa-feishu-url
unset PA_DING PA_FEISHU
kubectl -n monitoring create secret generic prometheusalert-webhooks \
  --from-file=dingtalk-url=.local/pa-dingtalk-url \
  --from-file=feishu-url=.local/pa-feishu-url \
  --dry-run=client -o yaml | kubectl apply -f -
rm -f .local/pa-dingtalk-url .local/pa-feishu-url
```

只用一个渠道时复制路由到.local并删除另一个webhookConfigs项和Secret键；不能留空URL。两个webhook会分别发送，两边应收到相同告警生命周期。

## 3. 创建通知CR

```bash
kubectl apply --dry-run=server -f notifications/prometheusalert.example.yaml
kubectl diff -f notifications/prometheusalert.example.yaml
kubectl apply -f notifications/prometheusalert.example.yaml
kubectl -n monitoring get alertmanagerconfig prometheusalert -o yaml
kubectl -n monitoring get pods -l app.kubernetes.io/name=prometheus-operator
```

选择实际Operator Pod查看日志，确认无配置生成/Secret引用错误；查看Alertmanager Status及配置reload结果。不要导出含URL密钥的生成配置到公共日志。基础values只选择monitoring namespace内带 `release=kps,alert-routing=prometheusalert` 的配置；matcher策略None使集中路由也接收其他业务namespace的告警。**有权写该namespace/标签的用户能更改全局通知路由**，应仅授予运维管理员。默认namespace强制匹配会漏掉业务namespace告警，所以不能省略这一点。

warning/critical匹配双渠道，sendResolved=true；info、Watchdog、InfoInhibitor保留空接收器。本例按cluster/namespace/alertname分组；各告警自身label仍在alerts数组内。基础配置在接入前默认null，不会自动通知。后续只改路由CR重复apply，改核心选择器则仍需Helm upgrade。

## 4. 联调与验收

按 [告警文档的三条curl样例](../alerts/README.md) 将测试发送到**测试Alertmanager**或只连接测试群的独立路由。curl直接写Alertmanager仅验证通知链路，不验证PromQL能触发；规则求值用promtool单测和Prometheus Rules页验收。未隔离测试接收器前不要往生产Alertmanager注入测试。

检查：触发消息、缺字段降级、聚合多对象、恢复消息、钉钉与飞书分别到达、info不通知。受group_wait/group_interval影响，恢复不会保证立即到达；检查Alertmanager和PrometheusAlert日志定位失败层。机器人密钥泄露后先在平台轮换，再更新Secret。对接成功后记录PrometheusAlert版本、模板名称、路由负责人及验收时间，不在记录中保存密钥。

依据：[Operator告警配置](https://prometheus-operator.dev/docs/developer/alerting/)、[PrometheusAlert项目](https://github.com/feiyu563/PrometheusAlert)。
