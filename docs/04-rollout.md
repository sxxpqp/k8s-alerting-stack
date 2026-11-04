# 实施、验收和回滚

每一步保存操作者、时间、命令/页面、结果和下一步。只把脱敏后的配置与结果摘要提交到 Git。采集脚本是只读；本页涉及写入的操作需在配置核对完、备份完成后由维护者执行。

## 阶段 0：保存基线

运行采集脚本，保留 private。另行备份实际 Alertmanager Secret、PrometheusAlert app.conf、模板数据库及持久卷，备份放受控位置，不进仓库。核对备份能读且包含模板，而不只是目录存在。

退出条件：配置来源、运行版本、PVC 和模板存储位置可明确指出；未知项进入台账。不删除现有组件、不通过 Helm 覆盖同名资源。

## 阶段 1：证明监控和规则被选中

对照 Prometheus CR 的各 selector、namespaceSelector 与资源标签。selector 未设置和 `{}` 的含义需按当前 Operator API 核实，不能擅自统一改成全选。

ServiceMonitor：selector 选 Service 的 labels，endpoint.port 对应 **Service 端口名称**，Service selector 再选 Pod；PodMonitor：selector 直接选 Pod 的 labels，端口对应 Pod 端口名称。两者均核对 path、scheme、TLS、认证、namespace 和实际 Targets。

对照 `node-export` / `node-exporter` 的 Targets，先确认是否同一端点重复采集；不要只看资源名字删其中一个。

退出条件：Ingress 指标可查询，标签确认，Prometheus Rules 页面能看到当前规则且 health 正常。若 API 资源存在但未加载，先修选择器/RBAC，不继续改通知模板来掩盖问题。

## 阶段 2：修一条规则

`baseline/` 是上传片段的清理副本，不是完整备份。`proposals/` 中只有 5xx 候选规则；不要直接 apply 成另一份同名告警。需把候选表达式、annotations 合并进实际完整 `ingress-nginx` PrometheusRule，并保留配置 reload / 证书到期规则及原 labels。

候选表达式使用 `(namespace, ingress)`；只有在实际请求指标含对应 namespace 标签时才能采用。多控制器场景决定是否再保留 controller_class，多集群场景保持 cluster 隔离。

保留当前 5% / 2m / 5m 业务参数，增加 summary、description、value、threshold。数值放 annotations，不放 labels；否则数值变化会改变告警身份。

验证顺序：用与现网 Prometheus 相同版本的 promtool 检查抽取的 rule groups；查询表达式；`kubectl diff -f 本地完整修复文件`；`kubectl apply --dry-run=server -f 本地完整修复文件`；核对 diff 只包含预期规则后再 apply。PrometheusRule CR 验证不等于表达式已成功加载，必须回到 Rules 页面核对。

退出条件：表达式返回合理结果，labels 保留实际对象，annotations 包含触发值，其他规则不丢失。

## 阶段 3：修消息正文

先复制现有模板为测试模板，保留原模板及实际路由。候选 `templates/prometheusalert-markdown.tmpl` 使用 PrometheusAlert 小写 JSON 字段，不是 Alertmanager 自身大写模板。

用真实 webhook JSON 和以下变体在现网 PrometheusAlert 模板测试页面检查：

| 样例 | 预期 |
| --- | --- |
| severity 存在 / 只有 level / 两者缺失 | 优先 severity，回退 level，最后显示“未设置” |
| instance 缺失 | 不显示虚构的“主机 IP”；显示 namespace / ingress / pod / node 等真实标签 |
| description 缺失 / 只有 summary | 回退 summary，不出现 `<no value>` |
| annotations 为空 | 显示缺少说明提示，可用 labels 排查 |
| 一组中有 firing 和 resolved | 每条按自身 status 标识，不能全组只显示一种状态 |
| value 缺失 / 为字符串 0 | 缺失隐藏，字符串 0 正常显示 |

候选正文不包含时区转换、手机号、@人员和自动生成屏蔽 URL。保留现有渠道的 @ 策略，验证后再合并。不要把 UTC 字符串简单加“北京时间”字样；未转换时明确保留原始时区。

退出条件：钉钉与企业微信各自的页面测试成功。测试页面可能立刻发消息，应使用明确约定的测试群。

## 阶段 4：验证整个链路

新增临时独立测试 PrometheusRule（选中的 namespace / labels；severity warning；例如 `alert: AlertPipelineSmokeTest`、`expr: vector(1)`、`for: 1m`），单独路由到测试群，保留默认业务路由。不要降低真实生产阈值来触发告警。

1. 观察 pending → firing，记录 Prometheus 实际标签和 annotations。
2. Alertmanager 能看到测试告警，经过预期 route / group 等待到 PrometheusAlert。
3. 钉钉与企业微信都收到，级别、对象、说明、触发值、链接正确。
4. 将测试表达式改为 `vector(0) > 1`，确认不再产生序列；等待 resolved，两个群都收到恢复消息。确认 receiver 配置 `send_resolved: true`，并给评估与 group_interval 留足时间。
5. 测试双 Prometheus / 三 Alertmanager 是否只产生预期数量的通知。检查是否去除了 Prometheus 副本标签、保留 cluster 标签，以及 Alertmanager 集群 peers 是否一致；不能从副本数直接判断去重。
6. 单独验证静默、critical 抑制 warning 及 repeat_interval，不把“收到一条”当作全部验收。
7. 经过维护者确认后清理测试规则与测试路由，检查业务路由仍在。

退出条件：记录两个渠道的 firing / resolved 时间、去重结果、静默结果及清理结果。发送成功 HTTP 状态也不能代替业务回执与群中实际可见。

## 回滚

仅回滚本轮改动：恢复备份的完整 PrometheusRule；切回原模板名称和 webhook 参数；如改过路由，恢复原 Alertmanager 配置并检查配置 reload 是否成功。不要回滚整个集群，不删除 PVC。

回滚后再次核对 Rules 页面、Alertmanager 路由以及两个渠道的一条测试消息。模板数据库若变更，要用对应数据库备份恢复，不能只 rollout undo Deployment。

## 检查分层

| 层次 | 当前状态 | 能证明什么 |
| --- | --- | --- |
| 本地 Python CLI / 单元测试 | 已通过 CLI help 和单元测试；未访问集群 | 采集与导出逻辑可运行；不能证明集群权限 |
| 候选 YAML 本地结构解析 | 待本次执行记录 | 能解析；不能证明实际指标标签或阈值正确 |
| promtool / amtool 固定版本检查 | 待执行 | 表达式、规则/路由配置语法 |
| server dry-run 与运行态加载 | 待现网执行 | 集群接受配置，组件实际加载 |
| 模板与两个真实群通知 | 待现网执行 | 模板兼容性和实际送达 |

本地复查：`python3 -m unittest discover -s tests -v`，`python3 scripts/collect.py --help`。测试使用虚构数据，覆盖 selector 的 absent / null / 空对象区别、明文 env 不进入分享文件、只读命令调用及完整采集输出。
