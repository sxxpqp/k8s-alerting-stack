# 安装 PrometheusAlert

部署 PrometheusAlert 告警中间件，从 Alertmanager 接收 webhook，转为企业微信消息发送。内置 SQLite 存储模板，通过 PVC 持久化。

## 安装

编辑 [secret.yaml](secret.yaml)，填写登录账号、密码和企业微信开关。数据库已配置为内置 SQLite（`/app/data/prometheusalert.db`），不需要修改数据库连接。

```bash
bash prometheusalert/install.sh test
```

脚本流程：apply Secret → kustomize build overlay → apply → 等待 Pod Ready。

| 环境 | 命令 | 副本数 | 额外配置 |
|------|------|--------|---------|
| test | `bash prometheusalert/install.sh test` | 1 | — |
| prod | `bash prometheusalert/install.sh prod` | 2 | PDB + NetworkPolicy |

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

模板内容使用 [notifications/templates/prometheus-wx.tmpl](../notifications/templates/prometheus-wx.tmpl)。

也可以直接通过 Web UI 导入 [notifications/templates/prometheus-alert-template.json](../notifications/templates/prometheus-alert-template.json)。

创建后重启 Pod 验证模板持久化：

```bash
kubectl -n monitoring rollout restart deployment/prometheusalert
kubectl -n monitoring rollout status deployment/prometheusalert --timeout=5m
```

重启后重新登录，确认模板仍存在。

## 测试告警送达

模板创建后，执行[通知测试](../notifications/README.md#测试)发送真实告警到企业微信群。

## 配置修改

修改 `secret.yaml`（如更换密码）后重新执行安装脚本即可：

```bash
bash prometheusalert/install.sh prod
```

## 端口

| 端口 | 用途 |
|------|------|
| 8080 | Web UI + Alertmanager webhook 接收端 |