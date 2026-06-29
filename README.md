# 阿里云 CDT 流量控制 - 多账号版

适合多个阿里云账号分别控制 ECS 流量。程序每分钟检查一次 CDT 流量，超过账号阈值后自动关机；每月 1 号 00:05 UTC+8 后，如果该账号 CDT 流量低于阈值，自动开机。

为避免误操作，当前版本在 CDT 流量查询失败时不会把流量当成 `0GB`，而是跳过本轮自动开关机并发送一次告警。

## 安装

```bash
curl -sSL https://raw.githubusercontent.com/kingsnakerrr/aliyun-traffic-control-multiple-accounts/main/install.sh -o install.sh && bash install.sh
```

首次安装会录入 Telegram 全局配置和第一个阿里云账号。后续新增账号运行：

```bash
cdt
```

然后选择 `a. 增加账号`。

## cdt 菜单

运行：

```bash
cdt
```

首页会显示账号列表：

```text
1. 账号A | 机器在线运行中 | 启用 | 保活开 | 国内版 | cn-hongkong | i-xxx | 阈值 180GB | 日报 09:00 UTC+8
2. 账号B | 已关机（保活关闭） | 启用 | 保活关 | 国际版 | cn-hongkong | i-yyy | 阈值 180GB | 日报 09:00 UTC+8
```

首页支持：

```text
输入账号序号：进入该账号单独控制
a. 增加账号
d. 删除账号
t. TG Bot / 日志
u. 完全卸载程序
0. 退出
```

进入单个账号后支持：

```text
1. 查看这个账号状态
2. 立即发送这个账号日报到频道
3. 手动开机这个账号实例
4. 手动关机这个账号实例
5. 立即执行一次这个账号检查
6. 开启这个账号自动保活
7. 关闭这个账号自动保活
8. 编辑这个账号
9. 启用这个账号
10. 禁用这个账号
11. 删除这个账号
0. 返回账号列表
```

`t. TG Bot / 日志` 用于查看/修改 Telegram 配置、发送测试消息、启停/重启 Bot 服务、查看日志、查看 crontab、备份或手动编辑配置。

## Telegram 配置

- Telegram Bot Token、频道/群组 ID、管理员私聊 ID 是全局配置，不跟随单个阿里云账号重复填写。
- 后续新增阿里云账号只需要填写阿里云账号信息；Telegram 仍使用同一个机器人和频道。
- 修改或测试 Telegram：运行 `cdt`，选择 `t. TG Bot / 日志`。

Bot 命令：

```text
/status
/traffic
/bill
/report
/startvps 账号名或序号
/stopvps 账号名或序号
/keepon 账号名或序号
/keepoff 账号名或序号
/help
```

## 安全逻辑

- CDT 查询失败：跳过本轮自动开机/关机，避免误判为 `0GB`。
- 因流量熔断关机：记录 `traffic_stop` 状态。
- 月初恢复：只有每月 1 号 00:05 UTC+8 后，且 CDT 查询成功并低于阈值，才会自动开机。
- 自动保活：每个账号独立控制，关闭某个账号保活后，该账号不会因外部关机而自动开机；但超过流量阈值仍会自动关机。
- 状态文件写入：通知状态使用锁和原子写，减少 cron 与 Bot 并发写入导致的状态丢失。

## 不要上传到 GitHub 的文件

这些文件可能包含密钥或运行状态，不要上传：

```text
accounts.json
traffic_control.py
last_notify_state.json
last_notify_state.lock
keepalive_enabled.flag
cron_run.log
*.log
venv/
__pycache__/
*.pyc
*.bak.*
```

应该上传：

```text
.gitignore
traffic_control.py.template
install.sh
cdt
traffic-control.service
README.md
CHANGELOG.md
```
