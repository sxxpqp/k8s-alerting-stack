# 后续对接PrometheusAlert

本页管理Alertmanager → PrometheusAlert路由。先完成 [基础安装](../install/README.md)、采集和规则验收，再按 [PrometheusAlert部署](../prometheusalert/README.md) 准备服务和模板。已有PrometheusAlert可复用，先核对版本和模板名称。完整URL指向PrometheusAlert接收接口，不能直接把聊天机器人URL填到Alertmanager webhook。

## 1. 先验证模板字段

Alertmanager发送 `.alerts` 数组，每条有labels/annotations/status；逐条遍历并分别判断firing/resolved，不能只读commonLabels展示全部对象。

- 级别用 `labels.severity`，兼容旧规则时再回退level，仍缺失显示“未设置”。
- 对象依次显示namespace/pod/instance/service/job等存在的字段，不把instance固定叫主机IP。聚合告警可能没有instance。
- 内容优先description，缺失回退summary/message，再显示通用提示；补充suggestion、runbook_url。
- 当前值来自规则渲染到description的 `{{ $value }}`，webhook本身没有统一的value字段。恢复消息显示startsAt和endsAt；时间格式按实际模板函数能力转换。
- generatorURL、externalURL及静默链接要能从接收者网络访问；尚未配置实际入口时不要生成不可用链接。

模板函数属于PrometheusAlert版本能力，不能直接假设Prometheus/Alertmanager模板函数全部可用。先用包含缺标签、聚合对象和恢复状态的样例预览，保证不出现 `<no value>`。模板内容及持久化/导入方式由PrometheusAlert自身管理，不属于Prometheus Operator CRD。

## 2. 生成通知URL并保存Secret

Linux bash，仓库根目录执行；不要把机器人密钥或完整URL提交Git，也不要开shell xtrace。

```bash
mkdir -p .local
chmod 700 .local
umask 077
# 适用于本项目v4.9.1部署及已创建的prometheus-dd/prometheus-fs模板
python3 - <<'PY'
from getpass import getpass
from pathlib import Path
from urllib.parse import urlencode
base = 'http://prometheusalert.monitoring.svc:8080/prometheusalert'
for channel, kind, key, tpl in [
    ('dingtalk', 'dd', 'ddurl', 'prometheus-dd'),
    ('feishu', 'fs', 'fsurl', 'prometheus-fs'),
]:
    robot = getpass(f'{channel}机器人完整URL: ')
    if not robot:
        raise SystemExit('URL不能为空，尚未创建Secret')
    query = urlencode({'type': kind, 'tpl': tpl, key: robot, 'split': 'false'})
    Path(f'.local/pa-{channel}-url').write_text(base + '?' + query)
PY
```

确认两个文件都已生成后创建Secret；Python的URL编码会保护嵌套机器人URL中的 `?`、`&` 和签名参数，不能直接拼接未编码的嵌套URL。复用外部服务时修改base/模板名：

```bash
kubectl -n monitoring create secret generic prometheusalert-webhooks \
  --from-file=dingtalk-url=.local/pa-dingtalk-url \
  --from-file=feishu-url=.local/pa-feishu-url \
  --dry-run=client -o yaml | kubectl apply -f -
```

创建成功后清理临时URL文件：

```bash
rm -f .local/pa-dingtalk-url .local/pa-feishu-url
```

只用一个渠道时复制路由到.local并删除另一个webhookConfigs项和Secret键；不能留空URL。两个webhook会分别发送，两边应收到相同告警生命周期。

可选企业微信使用 `type=wx`、`wxurl`、对应的 `prometheus-wx` 模板，以相同方式编码URL，新增Secret键和webhookConfigs引用。钉钉启用加签时，按v4.9.1要求在机器人URL中提供签名secret并设置app.conf的open-dingding-secret=1，再更新配置Secret和重启；不把secret写进Git。

## 3. 创建通知CR

```bash
kubectl apply --dry-run=server -f notifications/prometheusalert.example.yaml
kubectl diff -f notifications/prometheusalert.example.yaml
kubectl apply -f notifications/prometheusalert.example.yaml
kubectl -n monitoring get alertmanagerconfig prometheusalert -o yaml
kubectl -n monitoring get pods -l app.kubernetes.io/name=prometheus-operator
```

选择实际Operator Pod查看日志，确认无配置生成/Secret引用错误；查看Alertmanager Status及配置reload结果。不要导出含URL密钥的生成配置到公共日志。基础values只选择monitoring namespace内带 `release=kps,alert-routing=prometheusalert` 的配置；matcher策略None使集中路由也接收其他业务namespace的告警。**有权写该namespace/标签的用户能更改全局通知路由**，应仅授予运维管理员。默认namespace强制匹配会漏掉业务namespace告警，所以不能省略这一点。

warning/critical匹配双渠道，sendResolved=true；info保留空接收器。本例按cluster/namespace/alertname分组；各告警自身label仍在alerts数组内，URL的split=false保留分组消息。基础配置在接入前默认null，不会自动通知。后续只改路由CR重复apply，改核心选择器则仍需Helm upgrade。

### 按团队分流（可选）

在同一个通知CR的spec.route.routes中添加team匹配子路由，并在spec.receivers中添加对应接收器；Secret按团队分别存URL。示例结构：

```yaml
# 合并到现有spec.route，继承父级warning|critical过滤
routes:
  - receiver: team-a
    matchers:
      - name: team
        matchType: '='
        value: a
```

team-a接收器使用与notify-both相同的webhookConfigs结构，但引用团队自己的Secret键，并保留sendResolved=true。未匹配团队时使用默认notify-both；不要再新增一个全匹配通知CR导致重复发送，也不要把含token的原生配置写回Helm values。

## 4. 联调与验收

按 [告警文档的三条curl样例](../alerts/README.md) 将测试发送到**测试Alertmanager**或只连接测试群的独立路由。curl直接写Alertmanager仅验证通知链路，不验证PromQL能触发；规则求值用promtool单测和Prometheus Rules页验收。未隔离测试接收器前不要往生产Alertmanager注入测试。

检查：触发消息、缺字段降级、聚合多对象、恢复消息、钉钉与飞书分别到达、info不通知。受group_wait/group_interval影响，恢复不会保证立即到达；检查Alertmanager和PrometheusAlert日志定位失败层。机器人密钥泄露后先在平台轮换，再更新Secret。对接成功后记录PrometheusAlert版本、模板名称、路由负责人及验收时间，不在记录中保存密钥。

## 5. 沿链路排查

1. Prometheus Rules/Alerts：规则是否已加载、有数据、进入firing；查CR的release标签和selector。
2. Prometheus → Alertmanager：KPS默认已配置，不手写prometheus.yml。可查 `kubectl -n monitoring get prometheus -o yaml` 中的spec.alerting，并在Prometheus端口转发后执行 `curl --fail-with-body http://127.0.0.1:9090/api/v1/alertmanagers`；正常应发现全部就绪副本。
3. Alertmanager：是否收到告警、被静默/抑制、进了null接收器；Status中配置和集群成员是否正常。
4. PrometheusAlert：查看 `kubectl -n monitoring logs deployment/prometheusalert --all-pods=true --tail=100`（旧kubectl不支持时逐Pod查看）；核对MySQL、模板名、渠道开关及出口。/health=200和通知请求HTTP 2xx均不能代替群消息送达验收。

依据：[Operator告警配置](https://prometheus-operator.dev/docs/developer/alerting/)、[PrometheusAlert项目](https://github.com/feiyu563/PrometheusAlert)。
