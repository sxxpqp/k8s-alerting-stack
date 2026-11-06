# 告警规则验证

离线检查告警规则的语法和单元测试。

## 环境

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install PyYAML==6.0.2
```

还需要[匹配实际 Prometheus 版本的 promtool](https://github.com/prometheus/prometheus/releases)。

## 运行

```bash
bash alerts/check.sh test
```

脚本流程：
1. 导出 built-in 规则和业务规则到 `.generated/`
2. 用 promtool 检查 YAML 语法
3. 运行 [rules.test.yaml](rules.test.yaml) 中的单元测试

退出 0 表示离线检查通过。

## 单元测试覆盖

| 测试用例 | 覆盖场景 |
|---------|---------|
| `TestRedisMemoryHighZeroMaxmemory` | Redis 零 maxmemory 不触发除零 |
| `TestMysqlConnectionsHighZeroMax` | MySQL 零 max_connections 不触发除零 |
| `TestKafkaISRZeroReplicas` | Kafka 零副本不触发 |
| `TestKafkaISRSingleReplica` | Kafka 单副本分区不告警 |
| `TestDorisZeroCapacity` | Doris 零容量不触发 |

修改或裁剪规则时同步更新测试。单测不证明真实指标存在或通知送达。