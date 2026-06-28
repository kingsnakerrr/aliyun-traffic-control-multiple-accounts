# 阿里云 CDT 流量控制脚本（多账号版）

这个版本支持多个阿里云账号：第一次安装只录入 1 个账号，后续通过 `cdt` 菜单增加、删除、编辑、启用、禁用账号。

## 主要逻辑

- 每分钟 cron 执行一次 `traffic_control.py --cron`。
- 程序遍历 `/root/aliyun-traffic-control/accounts.json` 里所有启用账号。
- 每个账号独立查询 CDT 流量、ECS 状态、账单消费。
- 每个账号独立阈值，默认 180GB。
- 超过阈值：自动关机，只通知一次。
- 低于阈值且普通保活开启：自动开机。
- 如果是因为流量熔断关机：必须等到每月 1 号 00:05 UTC+8 以后，并且该账号 CDT 流量低于阈值，才自动开机。
- 日报固定按 UTC+8 / 北京时间判断，不依赖服务器时区。

## 安装

上传本仓库文件到 GitHub 后执行：

```bash
curl -sSL https://raw.githubusercontent.com/kingsnakerrr/aliyun-traffic-control-multiple-accounts/refs/heads/main/install.sh -o install.sh && bash install.sh
```

第一次安装只输入一个阿里云账号的信息。安装完成后运行：

```bash
cdt
```

进入：

```text
15. 多账号管理
```

可以继续增加第二个、第三个账号。

## 多账号配置文件

配置文件位置：

```text
/root/aliyun-traffic-control/accounts.json
```

示例：

```json
[
  {
    "name": "zymsdf-香港",
    "access_key_id": "xxx",
    "access_key_secret": "xxx",
    "region_id": "cn-hongkong",
    "instance_id": "i-xxxx",
    "bill_region_id": "cn-hangzhou",
    "max_traffic_gb": 180,
    "is_international": true,
    "daily_report_time": "09:00",
    "enabled": true
  }
]
```

`accounts.json` 是服务器上的敏感文件，不要上传 GitHub。

## Telegram 命令

- `/status` 查看所有账号完整状态
- `/traffic` 查看所有账号 CDT 流量
- `/bill` 查看所有账号余额/本月消费
- `/report` 立即发送所有账号报告到频道
- `/startvps 账号名或序号` 指定账号开机，不填默认第 1 个
- `/stopvps 账号名或序号` 指定账号关机，不填默认第 1 个
- `/keepon` 开启全局自动保活
- `/keepoff` 关闭全局自动保活
- `/help` 查看帮助

## 不要上传的文件

```text
accounts.json
traffic_control.py
__pycache__/
*.pyc
venv/
.env
*.log
cron_run.log
last_notify_state.json
keepalive_enabled.flag
```
