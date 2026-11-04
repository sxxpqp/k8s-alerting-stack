# 逐步验证操作手册

适用当前集群：monitoring/Prometheus k8s、Alertmanager main、prometheus-alert-center。按现有配置接管，不重装、不升级。本文先完成现状核验；涉及未知路由和模板的修改必须等原配置归档后填写具体文件名，不能跳过。

**每次只做当前一步。未达到“通过标准”就停止，把该步输出发给协作者，不继续后续改动。** 所有时间记录使用北京时间，并保留原告警的 UTC 时间，避免混淆。

## 0. 获取本阶段文件

执行位置：可访问 GitHub 的管理机。仓库 PR 未合并时，需拉取工作分支：

```bash
git clone --branch setup/existing-stack-inventory https://github.com/sxxpqp/k8s-alerting-stack.git
cd k8s-alerting-stack
python3 --version
kubectl config current-context
```

GitHub 无法直连时，从 Windows `D:\code\k8s-alerting-stack` 将本项目文件复制到 Linux 管理机，勿复制 `.git`、`__pycache__` 或 `.local`。以下命令在 Linux 管理机项目根目录执行，不是在 Windows Python 中连接集群。

通过标准：Python 3 可运行，context 与本次目标集群一致。检查不一致时先切换到正确 context；不要根据本手册猜测生产集群名。

## 1. 采集现有配置（只读）

```bash
python3 scripts/collect.py
```

预期：打印 context、private 和 review 目录，最后 `采集失败数：0`。

如果失败数非 0：查看 review/errors.json 的失败项目，再在本机查看 private 中对应 `.error.txt`；排除权限或资源类型问题。错误文件可能含内部地址，不整段公开。

需要发给协作者：人工检查后的 review 文件，特别是两个 selection、center-references 和 ingress-nginx-rule。**不要发整个 .local 或 private。**

通过标准：Prometheus / Alertmanager 配置来源与 selector 可确认；原始规则、工作负载和存储配置已在本地留存。配置引用指向 Secret / 数据库的，下一步另行备份，不把此次采集当成完整密钥/数据备份。

## 2. 建立本机只读访问

在管理机新开两个终端，分别执行，并保持进程运行：

终端 A：

```bash
kubectl -n monitoring port-forward --address 127.0.0.1 svc/prometheus-k8s 19090:9090
```

终端 B：

```bash
kubectl -n monitoring port-forward --address 127.0.0.1 svc/alertmanager-main 19093:9093
```

预期：看到 `Forwarding from 127.0.0.1:19090` 和 `127.0.0.1:19093`。仅绑定本机，不修改现有 Service 或开放公网端口。

失败处理：端口占用时用其他本机端口，并给后续脚本传 `--prometheus http://127.0.0.1:新端口` 或 `--alertmanager http://127.0.0.1:新端口`；Pod 重建导致断开时重启 port-forward。Pod 转发依赖现有权限，出现 Forbidden 发权限错误，不修改 RBAC 来绕过。

通过标准：两个转发保持运行；在第三个终端执行后续命令。

## 3. 检查监控采集对象

```bash
python3 scripts/check_runtime.py targets
```

预期：Ingress、node-exporter、kube-state-metrics 对应 Targets 的 `health` 为 `up`，`lastError` 为空。脚本仅按常见名称筛选，不显示不等于端点一定不存在；名称自定义时在 Prometheus Targets 页面核对完整列表。

检查 node-export 与 node-exporter 是否指向相同地址、端口和 path。相同端点被两个 job 抓取需要分析用途，不能立即删除。

通过标准：关键目标存在且正常；实际 endpoint 与 ServiceMonitor / PodMonitor 预期一致。

失败处理：没有 Target，查 Prometheus selector / namespaceSelector、Monitor selector 与 Service/Pod labels；有 Target 但 down，查 Service endpoint、port 名、path、scheme、TLS / 认证及网络。返回当前步骤的目标 labels、health 和脱敏后的 lastError。

## 4. 检查实际加载的告警规则

```bash
python3 scripts/check_runtime.py rules
```

预期：输出当前 Prometheus 实际加载的 `IngressNginx5xxRateHigh`，能看到 query、duration、labels、annotations、health、lastError、file/group。

通过标准：在该 Prometheus 实例中只有一个预期定义；health 为 ok，lastError 为空。当前应能确认 severity=warning、for=5m、只有 summary 的原配置。

若输出 `[]`：规则没有加载或命名已改变，先回查选择器及 Rules 页面，不能只因为 CR 存在就判定已生效。若存在多个定义，先去重规划，不新增第三条。

两副本检查：Service 转发只访问其中一个 Pod。记录第一次结果后，结束终端 A 的转发，依次将目标换成 `pod/prometheus-k8s-0`、`pod/prometheus-k8s-1`，端口仍为 `19090:9090`，各重复本步骤。两个副本均应加载同一规则，健康正常。

## 5. 核对指标标签，决定候选规则能否使用

```bash
python3 scripts/check_runtime.py metric-labels
```

预期：最多 20 个样本，metric 中包含业务 namespace 和 ingress；脚本也展示 controller_class（若指标存在）。这些是样本，不代表全量已经检查。

通过标准：确认 namespace 的含义是业务 Ingress 所属 namespace，而不是采集器 namespace；不同 namespace 的同名 Ingress 能区分。必要时在 Prometheus 页面查询具体 Ingress 样本或查看最终 relabel 标签。

失败处理：namespace 缺失、为空或是采集器 namespace 时，停止使用 proposals 中候选规则，先确定正确标签（例如 relabel 后的 exported_namespace）。多控制器/多集群需要确认额外聚合维度。

## 6. 核对 Alertmanager 集群和原始告警（只读）

```bash
python3 scripts/check_runtime.py am-cluster
python3 scripts/check_runtime.py alerts
```

预期：Alertmanager clusterStatus 为 ready，peerCount 与实际 3 副本成员关系相符。是否计入自身以该版本返回值和集群成员页面为准；不要仅凭一个数字认定三副本互通。

alerts 输出只包含 Ingress 5xx 或测试告警；当前没有触发时允许为空。空输出不能用于验证消息模板，需要下一步补一条历史原始 JSON 或测试告警。

通过标准：集群状态正常；已取得一条实际告警的 labels、annotations、status、时间，或明确记录当前无样本。脚本不会输出 Alertmanager status API 中可能含凭据的 config.original。

## 7. 归档通知配置和模板——当前需要补充的关口

此步骤不能靠资源清单自动补齐。先把步骤 1 的 review 发给协作者，再由真实引用确定具体 Secret / ConfigMap / 数据库位置，给出对应的定点备份命令。不要猜测 Secret 名称，也不要一次导出全部 Secret。

需要归档并脱敏的内容：

1. 实际 Alertmanager 的 route、receivers、inhibit_rules、send_resolved、group_wait / group_interval / repeat_interval 和模板引用。
2. PrometheusAlert 两个渠道的模板正文、模板名称、对应 tpl 参数，以及加签/关键词/@人员的配置方式（凭据不发）。
3. PrometheusAlert 数据库类型、挂载位置和备份恢复方式；确认重建 Pod 后模板仍存在。
4. 一条原始 webhook JSON，与群消息逐字段对比。

通过标准：能指出“每个接收器使用哪个模板、由哪个路由触发、存在哪里、怎样恢复”。在本步通过前，不切换生产 receiver、不改现网模板、不部署一整套新组件。

## 8. 单条规则与模板的局部修复

先在本地完整原资源中合并修复，保留现有其他规则和 metadata labels。候选规则不是完整 Kubernetes 资源，**不能直接 kubectl apply proposals/ingress-5xx-rule.yaml**。

修复完整文件命名约定：`.local/change/ingress-nginx-rule.yaml`。从中抽取的 Prometheus rule groups 文件为 `.local/change/ingress-groups.yaml`。这两个文件须等第 7 步资料齐全后生成，不能创建空文件跳过。

使用与现网 Prometheus 一致版本的 promtool：

```bash
promtool --version
promtool check rules .local/change/ingress-groups.yaml
kubectl diff -f .local/change/ingress-nginx-rule.yaml
kubectl apply --dry-run=server -f .local/change/ingress-nginx-rule.yaml
```

预期：promtool 验证成功；diff 仅包含预期 5xx 规则改动；server dry-run 成功。`kubectl diff` 有差异时退出码 1 是正常结果，退出码大于 1 才是错误。

PrometheusAlert 先复制模板为测试模板，用原始 JSON 分别测试 severity/level 缺失、description 缺失、无 instance、firing、resolved；钉钉和企微的模板测试会真实发消息，先约定测试群。

通过标准：语法、对象字段、缺字段回退、两种渠道显示都正确，没有 `<no value>`。通过后再安排局部 apply 和切换模板参数；执行后重复步骤 4，确认两个副本实际加载新定义。具体写入命令随实际生成文件一同核对。

## 9. 整条通知链路测试

使用独立告警 `AlertPipelineSmokeTest`，先根据现有路由生成只发测试群的测试规则和路由，不修改业务告警阈值。两个 Prometheus 副本使用同一测试规则，用来验证去重。

| 操作 | 必须观察到的结果 |
| --- | --- |
| 测试 expr=vector(1)，for=1m | pending → firing；Alertmanager 出现对应测试告警 |
| 等待实际 group_wait / group_interval | 钉钉与企业微信均收到 firing，字段正确 |
| 检查两副本去重 | 不因两个 Prometheus / 三个 Alertmanager 产生多份重复通知 |
| 测试 expr 改为 vector(0) > 1 | Prometheus 不再返回测试序列，随后两个渠道收到 resolved |
| 对测试告警设置一次短静默 | 静默有效，过期后按预期恢复通知；屏蔽链接能打开实际 Alertmanager |
| 维护者确认后移除测试配置 | 测试规则和专用路由清理，业务路由仍存在 |

每条通知等待时间按第 7 步现有路由参数计算，不固定宣称“1 分钟一定到达”。记录两个渠道的实际消息时间和数量，不只看 HTTP 200。

通过标准：两渠道 firing + resolved、去重、静默、消息对象、说明、触发值和链接均有证据。未执行的项写“待验证”。

## 10. 回滚与归档

失败时只恢复本轮改动：完整原 PrometheusRule、旧模板名/tpl 参数、原 Alertmanager route。若改了模板数据库，用对应备份恢复，Deployment rollout undo 不等于模板数据回滚。不删除 PVC。

恢复后重复步骤 4、6，并验证一条测试通知。将脱敏的最终配置、版本、原始文件位置与验收记录提交到仓库，再编写全新环境安装流程。

填写记录：

| 步骤 | 操作者 / 时间 | 结果与证据 | 问题 / 下一步 |
| --- | --- | --- | --- |
| 1 配置采集 | 待填 | 待验证 | |
| 3 Targets | 待填 | 待验证 | |
| 4 双副本规则 | 待填 | 待验证 | |
| 5 指标标签 | 待填 | 待验证 | |
| 6 AM 集群 | 待填 | 待验证 | |
| 7 通知配置归档 | 待填 | 待补 | |
| 8 局部修复 | 待填 | 待验证 | |
| 9 两渠道 firing / resolved / 去重 / 静默 | 待填 | 待验证 | |
| 10 回滚可执行性 | 待填 | 待验证 | |
