# 告警通知：Prometheus → 企业微信 全链路

## 文件清单

| 文件 | 说明 |
|---|---|
| [secret.yaml](secret.yaml) | Alertmanager → PrometheusAlert 转发 URL |
| [prometheusalert.yaml](prometheusalert.yaml) | AlertmanagerConfig，将 warning/critical 路由到 PrometheusAlert |
| [templates/prometheus-wx.tmpl](templates/prometheus-wx.tmpl) | 模板源文件（Go template 语法，可读可改） |
| [templates/prometheus-alert-template.json](templates/prometheus-alert-template.json) | 导入用 JSON（从 .tmpl 生成，不要手动改） |
| [test.sh](test.sh) | 全链路测试脚本 |
| [test-payload.json](test-payload.json) | 测试用的标准告警 payload |

## 部署

```bash
bash notifications/apply.sh
```

脚本流程：检查占位符 → 服务端预检 → apply Secret + AlertmanagerConfig。

> 部署前需确保 PrometheusAlert 已安装：`bash prometheusalert/install.sh test`

## 模板管理

修改模板的方式：

1. 编辑 [templates/prometheus-wx.tmpl](templates/prometheus-wx.tmpl)
2. 将内容同步到 `templates/prometheus-alert-template.json`：
   ```bash
   node -e "const t=JSON.parse(require('fs').readFileSync('templates/prometheus-alert-template.json','utf-8'));const n=require('fs').readFileSync('templates/prometheus-wx.tmpl','utf-8');t.find(x=>x.Tplname==='prometheus-wx').Tpl=n;require('fs').writeFileSync('templates/prometheus-alert-template.json',JSON.stringify(t))"
   ```
3. 打开 PrometheusAlert Web UI → **AlertTemplate** → **导入** → 选择 `templates/prometheus-alert-template.json`

## 测试

```bash
# 端口转发 PrometheusAlert
kubectl -n monitoring port-forward svc/prometheusalert 18083:8080 &

# 发送测试告警
bash notifications/test.sh
```

## 链路架构

```
Prometheus → Alertmanager → PrometheusAlert → 企业微信机器人 → 群消息
```

关键参数：

| 参数 | 值 | 说明 |
|------|-----|------|
| `type` | `wx` | 企业微信群机器人 |
| `tpl` | `prometheus-wx` | 使用的模板名 |
| `wxurl` | 企业微信 Webhook URL | **必须 URL 编码**，避免 `?key=` 被误解析 |
| `open-weixin` | `1` | PrometheusAlert 企业微信开关（在 [prometheusalert/secret.yaml](../prometheusalert/secret.yaml) 中配置） |

Alertmanager webhook URL（集群内访问）：

```
http://prometheusalert.monitoring.svc:8080/prometheusalert?type=wx&tpl=prometheus-wx&wxurl=<URL编码的企业微信机器人地址>
```