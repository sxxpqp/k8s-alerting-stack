# k8s-alerting-stack

整理现有 Kubernetes 监控告警系统，逐步形成可维护、可验证、可回滚的部署配置。通知渠道为钉钉群机器人和企业微信群机器人。

当前阶段：**现网配置采集与接管准备**。本仓库尚不是全新集群的一键安装包。采集资料中没有完整的选择器、路由、模板和存储定义，不能据此生成声称可直接替换现网的部署清单。

```mermaid
flowchart LR
  E[节点 / kube-state-metrics / 业务指标] --> P[Prometheus k8s ×2]
  SM[ServiceMonitor / PodMonitor] --> P
  R[PrometheusRule] --> P
  P --> A[Alertmanager main ×3]
  A --> C[PrometheusAlert]
  C --> D[钉钉群]
  C --> W[企业微信群]
```

上图是待核实的目标链路；已确认组件存在，实际通知路由和接收目标仍需原配置确认。

## 从这里开始

1. 阅读 [现网基线](docs/01-current-state.md)，核对已知事实与问题。
2. 在现有管理机运行 [采集流程](docs/02-collection.md)，不修改集群。
3. 按 [待补配置](docs/03-open-items.md) 提供经过检查的资料，不提交凭据。
4. 按 [实施与验收流程](docs/04-rollout.md) 核对选择器、规则、模板、通知链路并逐项验收。

```bash
git clone https://github.com/sxxpqp/k8s-alerting-stack.git
cd k8s-alerting-stack
python3 scripts/collect.py
```

脚本要求 Python 3 和已配置权限的 kubectl，只执行读取命令。原始备份存入 `.local/`；它可能包含环境变量和内网信息，不能直接上传。

## 仓库内容

| 路径 | 用途 |
| --- | --- |
| docs/ | 现状、采集、待补项、验证和回滚步骤 |
| scripts/collect.py | 收集现有安装与关联配置，生成受限分享资料 |
| baseline/ingress-nginx-rule.yaml | 已上传规则的清理副本，作为比对基线，不是完整现网备份 |
| proposals/ingress-5xx-rule.yaml | 5xx 规则的候选修复，需要查询真实指标后再采用 |
| templates/prometheusalert-markdown.tmpl | 缺字段时回退的候选消息正文，尚需在现网 v4.9.2 页面测试 |

基线、候选修复和后续已验收配置分开管理。不要同时部署同名告警的旧、新规则。

## 验证状态

- 已有证据：用户提供的资源清单及 Ingress 告警规则（2026-11-04）。
- 本地检查记录见 [验收流程](docs/04-rollout.md)。
- 尚未连接集群、导入模板或发送测试消息；K8s 准入、规则实际加载、消息格式、恢复通知、去重与持久化仍待现网验收。
- 新环境安装与版本选型将在现网完整配置归档后编写；不从资源 labels 猜测运行版本，不使用未经核验的镜像标签。
