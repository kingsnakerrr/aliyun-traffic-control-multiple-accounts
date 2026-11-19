# 阿里云 CDT 流量控制 - 多账号版

完整操作步骤见 [GUIDE.md](GUIDE.md)，升级后也可向机器人私聊发送 `/guide` 下载教程文件。

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

## 区域怎么填

新增或编辑账号时有两个区域字段：

- `ECS 区域`：填实例真实所在地域。香港填 `cn-hongkong`，日本东京填 `ap-northeast-1`。
- `账单接口区域`：它和 ECS 所在地域不是同一个概念。国内版账号默认填 `cn-hangzhou`，国际版账号默认填 `ap-southeast-1`。

常见 ECS 区域：

```text
香港：cn-hongkong
日本东京：ap-northeast-1
新加坡：ap-southeast-1
美国硅谷：us-west-1
美国弗吉尼亚：us-east-1
杭州：cn-hangzhou
上海：cn-shanghai
北京：cn-beijing
深圳：cn-shenzhen
```

示例：

```text
国内版账号，ECS 在香港：
ECS 区域：cn-hongkong
账单接口区域：cn-hangzhou

国际版账号，ECS 在日本东京：
ECS 区域：ap-northeast-1
账单接口区域：ap-southeast-1
```

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
x. 一键升级程序
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

`x. 一键升级程序` 会更新主程序、`cdt` 菜单、systemd service 和教程，保留 `accounts.json`、Telegram 配置、通知状态、日志和 venv。旧机器如果菜单里还没有 `x`，先执行一次：

```bash
curl -fsSL https://raw.githubusercontent.com/kingsnakerrr/aliyun-traffic-control-multiple-accounts/main/cdt -o /usr/local/bin/cdt && chmod +x /usr/local/bin/cdt
```

之后运行 `cdt`，选择 `x. 一键升级程序` 即可。

## 状态显示

账号状态报告使用简约格式，Telegram 和 `cdt` 里的单账号状态一致。多账号 `/status`、`/report` 和手动日报会按账号分别发送，一台机器一条消息：

```text
📊 zymasd-香港

⏰ 时间：2026-07-30 10:20:04 UTC+8
📡 当前流量：82.17 GB / 180 GB（流量控制：🟢 正常）
🖥 实例状态：🟢 Running
⚡ 保活运行：🟢 正常
💰 账户现金余额：93.11 元（本月消费：5.20 元）
🌍 ECS区域：cn-hongkong
🆔 实例：i-xxxxxxxxxxxxxxxxx
```

状态徽标含义：

```text
🟢 正常
🟡 接近阈值 / 查询失败 / 启停中 / 已暂停
🔴 超限 / 异常 / Unknown
⚫ Stopped / 熔断停机 / 手动停机
```

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
/changeip
/cfconfig
/guide
/cancel
/help
```

机器人启动时会刷新 Telegram 左下角命令菜单。`/changeip` 可选单个账号或批量换 IP。单账号缺少 Cloudflare 配置时会逐项询问；批量只选择已启用、配置完整、CF 与当前直绑 EIP 的 A 记录一致且只读预检通过的账号，逐台列出跳过原因，不进入配置问答。预检不能验证 EIP 写权限或配额。Token 消息会尝试删除，但 Telegram 平台仍可能留有记录，建议使用仅限目标 Zone 的 DNS 编辑权限 Token，不要使用 Global API Key。

填错配置时发送 `/cfconfig`，选择账号后可单独修改域名、区域 ID（Zone ID）或 API 令牌；“验证配置”只读检查区域和 DNS，不会换 IP。输入过程中发送 `/cancel` 可退出。换 IP 前也会先确认区域 ID 对应的区域包含该账号域名，避免把账户 ID 误当成区域 ID。

换 IP 仅支持直绑 ECS、未加入共享带宽的按量付费 EIP。固定公网 IP、辅助网卡 EIP、包年包月 EIP 暂不支持，机器人会拒绝操作。每台账号对应一个域名和一个 Zone ID，配置保存在权限为 `0600` 的 `accounts.json` 中；`cdt` 的“查看 accounts.json”会隐藏密钥。

操作顺序：校验旧 EIP 与 CF A 记录（单账号模式若无 A 记录会先创建指向旧 IP 的 DNS-only 记录；批量模式会跳过）→ 申请同地域、同带宽和计费方式的新 EIP → 解绑旧 EIP → 绑定并确认新 EIP → 更新并回读 CF A 记录 → 释放旧 EIP。阿里云不允许同一 ECS 主网卡同时绑定两个 EIP，因此解绑到绑定之间会短暂断网。新 EIP 可能产生费用；如中途失败，机器人会报告保留的 EIP ID 和需要人工核查的状态，不会在 CF 更新失败时释放旧 EIP。Cloudflare 代理设置对已有记录保持不变。

阿里云 AccessKey 除原有 ECS/CDT/账单权限外，还需 `vpc:DescribeEipAddresses`、`vpc:AllocateEipAddress`、`vpc:UnassociateEipAddress`、`vpc:AssociateEipAddress`、`vpc:ReleaseEipAddress`。Cloudflare Token 需要对应 Zone 的 DNS 编辑权限。若账号 AccessKey 无效，换 IP 会失败，需先修正该账号密钥。

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
ip_rotation.lock
.accounts-*
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
GUIDE.md
```
