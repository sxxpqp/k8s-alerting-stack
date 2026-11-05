# 可选：Prometheus远程写入Mimir

仅在已有Mimir、需要远程存储时执行。没有Mimir时跳过本页，不影响本地采集、告警评估或PrometheusAlert通知。

## 1. 确认接入信息

- Mimir网关的完整写入地址，例如 `https://实际域名/api/v1/push`。
- 租户和实际认证方式。本示例使用BasicAuth及 `X-Scope-OrgID`；单租户、BearerToken或mTLS环境需按网关要求修改。
- 两个Prometheus副本都写入时，Mimir启用HA tracker，租户启用 `accept_ha_samples`，HA标签为 `cluster` 和 `__replica__`。若去重尚未配置，先不启用远写，或明确用单副本写入；基础安装的两个本地副本不依赖Mimir去重。

## 2. 创建认证Secret

以下适用于本示例BasicAuth。基础安装已创建monitoring namespace，凭证不写入Git：

```bash
mkdir -p .local
chmod 700 .local
umask 077
read -r -p 'Mimir username: ' MIMIR_USER
read -r -s -p 'Mimir password: ' MIMIR_PASS; printf '\n'
printf '%s' "$MIMIR_USER" > .local/mimir-username
printf '%s' "$MIMIR_PASS" > .local/mimir-password
unset MIMIR_USER MIMIR_PASS
kubectl -n monitoring create secret generic mimir-remote-write \
  --from-file=username=.local/mimir-username \
  --from-file=password=.local/mimir-password \
  --dry-run=client -o yaml | kubectl apply -f -
```

确认Secret创建成功后删除临时文件：

```bash
rm -f .local/mimir-username .local/mimir-password
```

## 3. 合并配置并更新

将 [mimir-values.example.yaml](mimir-values.example.yaml) 中的 `remoteWrite` 段合并到本环境 `prom-values.yaml` 的 `prometheus.prometheusSpec` 下，替换地址和租户。不要创建第二个顶层prometheus键，也不要用此片段替换整份基础values。后续更新统一保留一份完整环境values。

按 [基础安装第7节](README.md#7-后续更新与回滚) 先备份、预览，再upgrade，命令仍使用 `-f prom-values.yaml`。

## 4. 验收

检查Prometheus日志是否有写入认证/连接错误；在本地Prometheus查询：

```promql
prometheus_remote_storage_samples_pending
rate(prometheus_remote_storage_samples_failed_total[5m])
time() - prometheus_remote_storage_queue_highest_sent_timestamp_seconds
```

这些自监控指标按实际版本核对。失败、积压或延迟持续增长时先排查远写；再在Mimir查询 `up{cluster="实际集群名"}`，确认数据持续更新、租户正确、HA去重生效。本地up正常不代表已写入Mimir。

Mimir保留期单独设置。remote_write不会让本地查询自动读取Mimir历史；远写故障时WAL缓冲有限。超过本地保留期的规则应单独部署到Mimir Ruler，不能只因开启远写就放在本地评估。

依据：[Mimir HA去重](https://grafana.com/docs/mimir/latest/configure/configure-high-availability-deduplication/)、[Prometheus远程写入](https://prometheus.io/docs/practices/remote_write/)。
