# 安装 PrometheusAlert

部署 PrometheusAlert 告警中间件，从 Alertmanager 接收 webhook，转为企业微信消息发送。内置 SQLite 存储模板，无需外部数据库。

## 安装

编辑 [secret.yaml](secret.yaml)，填写登录账号和密码。数据库已配置为内置 SQLite（`/app/data/prometheusalert.db`），通过 PVC 持久化，不需要修改数据库连接。

```bash
bash prometheusalert/install.sh test
```

脚本流程：apply Secret → apply base overlay → 等待 Pod Ready。

> `test` 部署单副本用于验证；`prod` 部署双副本、PDB 和 NetworkPolicy，需要至少两个可调度节点。

## 验证

```bash
kubectl -n monitoring port-forward svc/prometheusalert 8080:8080
```

访问 `http://127.0.0.1:8080`，使用 secret.yaml 中配置的账号登录。

### 创建企业微信模板

登录后进入「告警模板」→「新建」，填写：

| 字段 | 值 |
|------|-----|
| 模板名称 | `prometheus-wx` |
| 模板用途 | `Prometheus` |
| 模板类型 | `企业微信` |

模板内容使用 [notifications/templates/prometheus-markdown.tmpl](../notifications/templates/prometheus-markdown.tmpl)。创建后重启 Pod 验证模板持久化：

```bash
kubectl -n monitoring rollout restart deployment/prometheusalert
kubectl -n monitoring rollout status deployment/prometheusalert --timeout=5m
```

重启后重新登录，确认模板仍存在。

## 测试告警送达

模板创建并存在后，配置并执行[通知测试](../notifications/README.md)发送真实告警到企业微信群。

## 切换到生产模式

验证通过后：

```bash
bash prometheusalert/install.sh prod
```

生产 overlay 包含：
- **双副本** Deployment（多节点防单点）
- **PDB**（minAvailable: 1，允许驱逐一个副本）
- **NetworkPolicy**（只允许 monitoring 命名空间入站）

## 配置修改

修改 `secret.yaml`（如更换密码）后重新执行：

```bash
bash prometheusalert/install.sh prod
```

## 端口

| 端口 | 用途 |
|------|------|
| 8080 | Web UI + Alertmanager webhook 接收端 |

Alertmanager webhook URL（集群内访问）：

```
http://prometheusalert.monitoring.svc:8080/prometheusalert?type=workwechat&tpl=prometheus-wx&wxurl=<企业微信机器人URL>
```