# 阿里云 CDT 流量控制 - 多账号版

适合多个阿里云账号分别控制 ECS 流量。程序每分钟检查一次 CDT 流量，超过阈值自动关机；每月 1 号 00:05 UTC+8 后，如果该账号 CDT 流量低于阈值，自动开机。

## 安装

```bash
curl -sSL https://raw.githubusercontent.com/kingsnakerrr/aliyun-traffic-control-multiple-accounts/refs/heads/main/install.sh -o install.sh && bash install.sh
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
g. 服务 / 日志 / 工具
u. 完全卸载程序
0. 退出
```

`g. 服务 / 日志 / 工具` 只管理 TG Bot 服务、日志、crontab、系统时间、配置文件，不做账号业务控制。账号业务控制全部进入对应账号后操作。

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
