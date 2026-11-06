# 告警通知：Prometheus → 企业微信 全链路

## 文件清单

| 文件 | 说明 |
|---|---|
| `secret.yaml` | Webhook 地址 Secret，存 Alertmanager → PrometheusAlert 的转发 URL |
| `prometheusalert.yaml` | AlertmanagerConfig，把 warning/critical 告警路由到 PrometheusAlert |
| `templates/prometheus-wx.tmpl` | **模板源文件**（Go template 语法，可读可改） |
| `templates/prometheus-alert-template.json` | **导入用 JSON**（从 .tmpl 自动生成，不要手动改） |
| `test.sh` | 全链路测试脚本 |
| `test-payload.json` | 测试用的标准告警 payload |

## 部署

```bash
# 1. 先部署 PrometheusAlert 服务
cd ../prometheusalert && bash install.sh && cd ../notifications

# 2. 部署告警路由（Secret + AlertmanagerConfig）
kubectl apply -f secret.yaml
kubectl apply -f prometheusalert.yaml
```

## 模板管理

**修改模板的方式：**

1. 编辑 `templates/prometheus-wx.tmpl`
2. 执行 `node -e "const t=JSON.parse(require('fs').readFileSync('templates/prometheus-alert-template.json','utf-8'));const n=require('fs').readFileSync('templates/prometheus-wx.tmpl','utf-8');t.find(x=>x.Tplname==='prometheus-wx').Tpl=n;require('fs').writeFileSync('templates/prometheus-alert-template.json',JSON.stringify(t))"`
3. 打开 PrometheusAlert Web UI → **AlertTemplate** → **导入** → 选 `templates/prometheus-alert-template.json`

## 测试

```bash
# 端口转发
kubectl -n monitoring port-forward svc/prometheusalert 18083:8080 &

# 发送测试告警
bash test.sh
```

## 链路架构

```
Prometheus → Alertmanager → PrometheusAlert → 企业微信机器人 → 群消息
    🟢             🟢               🟢                🟢            🟢
```

关键参数：
- `type=wx`：企业微信群机器人 Webhook
- `tpl=prometheus-wx`：使用的模板名
- `wxurl`：企业微信 Webhook URL（**必须 URL 编码**，避免 `?key=` 被误解析）
- `open-weixin=1`：PrometheusAlert 的企业微信开关（在 `../prometheusalert/secret.yaml` 中配置）