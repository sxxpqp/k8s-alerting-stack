# 告警规则验证

离线检查告警规则的语法。

## 运行

需要 [promtool](https://github.com/prometheus/prometheus/releases)（匹配实际 Prometheus 版本）。

```bash
bash alerts/check.sh
```

脚本流程：合并规则文件 → promtool 语法检查。退出 0 表示通过。

> 日常部署直接 `bash alerts/apply.sh` 即可，已内置 `kubectl --dry-run=server` 服务端校验，比离线检查更准确。