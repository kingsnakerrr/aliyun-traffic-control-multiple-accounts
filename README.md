# 阿里云 CDT 流量控制 - 多账号版

适合多个阿里云账号分别控制 ECS 流量。程序每分钟检查一次 CDT 流量，超过阈值自动关机；每月 1 号 00:05 UTC+8 后，如果该账号 CDT 流量低于阈值，自动开机。

## 安装

```bash
curl -sSL https://raw.githubusercontent.com/kingsnakerrr/aliyun-traffic-control-multiple-accounts/main/install.sh -o install.sh && bash install.sh
```

首次安装只录入 Telegram 配置和第一个阿里云账号。

## cdt 菜单逻辑

运行：

```bash
cdt
```

进入后先看到账号列表：

```text
1. 账号A | 启用 | 保活开 | 国际版 | cn-hongkong | i-xxx | 阈值 180GB | 日报 09:00 UTC+8
2. 账号B | 启用 | 保活关 | 国内版 | cn-hongkong | i-yyy | 阈值 180GB | 日报 09:00 UTC+8
```

输入账号序号进入这个账号的单独控制：

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

主菜单还支持：

```text
a. 增加账号
d. 删除账号
g. 选择账号操作
s. 服务 / 日志 / 工具
u. 完全卸载程序
0. 退出
```

`g. 选择账号操作
s. 服务 / 日志 / 工具` 只管理 TG Bot 服务、日志、crontab、系统时间、配置文件，不做账号业务控制。账号业务控制全部进入对应账号后操作。

## 不要上传到 GitHub 的文件

这些文件可能包含密钥或运行状态，不要上传：

```text
accounts.json
traffic_control.py
__pycache__/
*.pyc
venv/
*.log
cron_run.log
last_notify_state.json
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


### cdt 菜单说明

首页可以直接输入账号序号进入该账号单独控制，也可以输入 `g` 进入“选择账号操作”。开机、关机、日报、检查、保活、编辑、启用、禁用、删除都在单账号菜单里执行。服务、日志、crontab、卸载相关工具在 `s` 菜单。


## cdt 菜单说明

新版菜单只保留账号级操作：

```text
账号列表：
1. 账号A | 机器在线运行中 | 启用 | 保活开 | 国内版 | cn-hongkong | i-xxx | 阈值 180GB | 日报 09:00 UTC+8

输入账号序号：进入该账号单独控制
a. 增加账号
d. 删除账号
t. TG Bot / 日志
u. 完全卸载程序
0. 退出
```

进入账号后才会显示开机、关机、日报、检查、保活、编辑、启用、禁用、删除等控制项。


## Telegram 配置说明

- Telegram Bot Token、频道/群组 ID、管理员私聊 ID 是全局配置，不跟随单个阿里云账号重复填写。
- 第一次安装会要求输入这 3 项。
- 后续新增阿里云账号只需要填写阿里云账号信息；Telegram 仍使用同一个机器人和频道。
- 需要修改或测试 Telegram 时，运行 `cdt`，选择 `t. TG Bot / 日志`。
- `t` 菜单支持查看/修改 Telegram 配置、发送测试消息到频道/群组、发送测试消息到管理员私聊、启停/重启 Bot 服务、查看日志。
