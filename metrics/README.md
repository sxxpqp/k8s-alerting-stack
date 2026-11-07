# 接入指标采集

先安装基础监控栈和业务 exporter（如 mysqld_exporter、redis_exporter、kafka_exporter），再创建对应的采集 CRD。

## 采集方式

| 文件 | 用途 | 要填写的内容 |
|------|------|-------------|
| [servicemonitor.yaml](servicemonitor.yaml) | 采集 Service | 资源名、目标 namespace、Service 标签、端口名、job |
| [podmonitor.yaml](podmonitor.yaml) | 采集 Pod | 资源名、目标 namespace、Pod 标签、端口名、job |
| [probe-http.yaml](probe-http.yaml) | HTTP/证书探测 | Blackbox Exporter 地址、模块、目标 URL |

> `release: kps` 标签保留不动；job 名必须与告警规则中的 job 标签一致。

## 部署

```bash
# 部署节点增强采集（node_exporter / system / kubelet）
bash metrics/apply.sh node

# 部署单个采集资源
bash metrics/apply.sh metrics/servicemonitor.yaml
bash metrics/apply.sh metrics/podmonitor.yaml
bash metrics/apply.sh metrics/probe-http.yaml
```

脚本流程：检查占位符 → 服务端预检 → apply。更新时修改文件后重新执行即可，无需重启 Prometheus。

## 验证

在 Prometheus Targets（`http://127.0.0.1:9090/targets`）确认：

- 目标数量和 job 正确
- State 为 UP
- Last Error 为空

以 MySQL 为例查询验证：

```promql
up{job="mysqld-exporter"}
mysql_up{job="mysqld-exporter"}
```

两者都应为 1，分别表示采集成功和数据库连通。

> `up=1` 不代表业务指标完整，需进一步核对具体业务指标。

## 示例：添加 MySQL Exporter 采集

```bash
cp metrics/servicemonitor.yaml metrics/mysqld-exporter.yaml
```

编辑 `metrics/mysqld-exporter.yaml`：

```yaml
metadata:
  name: mysqld-exporter
spec:
  namespaceSelector:
    matchNames: [database]
  selector:
    matchLabels:
      app.kubernetes.io/name: mysqld-exporter
  endpoints:
    - port: metrics
      relabelings:
        - targetLabel: job
          replacement: mysqld-exporter
```

部署：

```bash
bash metrics/apply.sh metrics/mysqld-exporter.yaml
```