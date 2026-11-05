# 部署PrometheusAlert

先完成 [基础监控安装](../install/README.md)。本页采用固定镜像 `feiyu563/prometheus-alert:v4.9.1`、共享MySQL存模板、Kustomize区分test/prod。测试1副本，生产2副本；只在对应集群选择一个overlay，同集群同namespace不能把两个环境都apply到相同资源名。

## 1. 准备MySQL

使用已有MySQL/RDS，创建数据库：

```sql
CREATE DATABASE prometheusalert DEFAULT CHARACTER SET utf8mb4;
```

由数据库管理员创建专用账号并授予该库的建表/变更表及读写权限；程序启动会同步表结构，不需要全局root权限。允许Pod访问数据库，按环境配置备份与恢复验证。此处不部署MySQL。host不带端口，端口单独填db_port。

## 2. 创建配置Secret

```bash
umask 077
cp prometheusalert/app.conf.example app.conf
```

编辑仓库根目录的 `app.conf`，填写登录账号、强密码、MySQL host/user/password；密码按INI格式处理，不保留REPLACE字段。该文件已加入Git忽略列表。umask 077使新建文件仅当前用户可读写。

```bash
# 输出应为空，否则先完成替换
grep -n REPLACE_ app.conf
kubectl -n monitoring create secret generic prometheusalert-config \
  --from-file=app.conf=app.conf \
  --dry-run=client -o yaml | kubectl apply -f -
```

本项目直接挂载app.conf并启动二进制，不使用PA_*覆盖配置。v4.9.1入口脚本会打印覆盖的配置值，因此不把数据库/登录密码经此脚本传入。Pod不需要本地SQLite PVC；两副本共享MySQL。不要切回SQLite后继续开两个副本。

## 3. 预检和部署

以下以prod为例，测试集群改为overlays/test。基础栈已创建monitoring namespace。**首次使用空库时，先把prod/kustomization.yaml的count临时改成1**，完成第4节数据库/模板验证后再恢复为2并重新apply；启动会执行表同步，避免多个副本同时初始化。

```bash
kubectl config current-context
kubectl apply --dry-run=server -k prometheusalert/overlays/prod
kubectl diff -k prometheusalert/overlays/prod
```

diff退出1表示有变更，大于1表示错误。确认后执行：

```bash
kubectl apply -k prometheusalert/overlays/prod
kubectl -n monitoring rollout status deployment/prometheusalert --timeout=5m
kubectl -n monitoring get pods -l app=prometheusalert -o wide
kubectl -n monitoring get svc,pdb -l app=prometheusalert
```

软反亲和尽量分散副本，PDB只约束自愿驱逐，不保证故障时一定有可用副本。初始化期间单副本配minAvailable=1会阻止该Pod的自愿驱逐，初始化完成后恢复2副本。

## 4. 验证健康和模板持久化

```bash
kubectl -n monitoring port-forward svc/prometheusalert 8080:8080
```

另开终端：

```bash
curl --fail-with-body http://127.0.0.1:8080/health
```

预期返回200和Hello。**这只证明HTTP进程存活，不证明MySQL和机器人可用。** 打开 `http://127.0.0.1:8080`，用app.conf中的账号登录，创建模板并重新读取，确认数据库写入正常；查看Pod日志中的数据库错误，不公开包含业务数据的日志。

参考 [通用Markdown模板](../notifications/templates/prometheus-markdown.tmpl)，在网页分别建 `prometheus-dd`、`prometheus-fs`（需要企业微信时建 `prometheus-wx`），用途选Prometheus，渠道分别选对应类型。模板正文可存Git，模板记录存MySQL；空MySQL不会自动包含镜像SQLite里的预置模板。

v4.9.1会在进程内缓存模板。完成创建/修改后让全部副本重新加载，并验证重启后模板仍存在：

```bash
kubectl -n monitoring rollout restart deployment/prometheusalert
kubectl -n monitoring rollout status deployment/prometheusalert --timeout=5m
```

Secret以subPath挂载也不会热更新；修改app.conf并重新创建Secret后同样需要上述restart。若在网页修改渠道等配置，不依赖容器文件写回持久化，统一修改Secret源文件。

## 5. 对接通知

确认Pod到机器人外网API的DNS、HTTPS出口可达，然后按 [通知配置](../notifications/README.md) 设置Webhook URL Secret和AlertmanagerConfig，最后验收触发/恢复。对外只提供ClusterIP，管理页面先通过port-forward访问；有外部入口需求时单独配置认证和访问控制。

## 多环境复用

共用base；环境副本/PDB等放overlays/test或prod；每个集群的app.conf和认证独立创建Secret。不同团队由AlertmanagerConfig按team标签分流，不必复制部署PrometheusAlert。多集群可共用一个PrometheusAlert，但必须有可达地址、唯一cluster标签和明确的模板维护负责人。

## 核对依据与边界

- [v4.9.1发布记录](https://github.com/feiyu563/PrometheusAlert/releases/tag/v4.9.1)：固定参考版本，不宣称为最新版本。
- [Dockerfile](https://github.com/feiyu563/PrometheusAlert/blob/v4.9.1/Dockerfile)、[入口脚本](https://github.com/feiyu563/PrometheusAlert/blob/v4.9.1/docker-entrypoint.sh)：二进制、工作目录及初始化行为。
- [配置字段](https://github.com/feiyu563/PrometheusAlert/blob/v4.9.1/conf/app-example.conf)、[数据库初始化](https://github.com/feiyu563/PrometheusAlert/blob/v4.9.1/main.go)、[HTTP路由](https://github.com/feiyu563/PrometheusAlert/blob/v4.9.1/routers/router.go)。

已核对源码与镜像标签，未在你的MySQL和集群运行；上线仍需验证镜像架构、数据库连接/建表、模板写入与双渠道真实送达。
