#!/usr/bin/env bash
set -e

REPO_RAW="https://raw.githubusercontent.com/kingsnakerrr/aliyun-traffic-control-multiple-accounts/refs/heads/main"
BASE_DIR="/root/aliyun-traffic-control"
SERVICE_NAME="traffic-control.service"

[ "$(id -u)" -eq 0 ] || { echo "请使用 root 用户运行安装脚本"; exit 1; }

echo "======================================"
echo " 阿里云 CDT 流量控制一键安装（多账号版）"
echo "======================================"
echo "第一次安装只录入 1 个账号。以后新增账号用命令：cdt -> 多账号管理。"
echo

read -r -p "Telegram Bot Token: " TELEGRAM_BOT_TOKEN
read -r -p "Telegram 频道/群组 ID，例如 -100xxxx: " TELEGRAM_CHAT_ID
read -r -p "Telegram 管理员私聊 ID: " ADMIN_USER_ID

echo
echo "===== 第一个阿里云账号 ====="
read -r -p "账号显示名称，例如 zymsdf-香港: " ACCOUNT_NAME
ACCOUNT_NAME=${ACCOUNT_NAME:-zymsdf-香港}
read -r -p "阿里云 ACCESS_KEY_ID: " ACCESS_KEY_ID
read -r -p "阿里云 ACCESS_KEY_SECRET: " ACCESS_KEY_SECRET
read -r -p "ECS 实例 ID: " INSTANCE_ID
read -r -p "ECS 区域，默认 cn-hongkong: " REGION_ID
REGION_ID=${REGION_ID:-cn-hongkong}
read -r -p "账单接口区域，默认 cn-hangzhou: " BILL_REG_ID
BILL_REG_ID=${BILL_REG_ID:-cn-hangzhou}
read -r -p "流量阈值GB，默认 180: " MAX_TRAFFIC_GB
MAX_TRAFFIC_GB=${MAX_TRAFFIC_GB:-180}
read -r -p "是否国际版账号？输入 y 表示国际版，默认国内版: " INTL
if [ "$INTL" = "y" ] || [ "$INTL" = "Y" ]; then
  IS_INTERNATIONAL="true"
else
  IS_INTERNATIONAL="false"
fi
read -r -p "每天日报推送时间，24小时制 HH:MM，默认 09:00。固定按北京时间 UTC+8 发送: " REPORT_TIME
REPORT_TIME=${REPORT_TIME:-09:00}
if ! echo "$REPORT_TIME" | grep -Eq '^([01][0-9]|2[0-3]):[0-5][0-9]$'; then
  echo "日报时间格式错误，请用 HH:MM，例如 09:00"
  exit 1
fi

CRON_CHECK="* * * * * ${BASE_DIR}/venv/bin/python ${BASE_DIR}/traffic_control.py --cron >> ${BASE_DIR}/cron_run.log 2>&1"

if command -v apt >/dev/null 2>&1; then
  apt update
  apt install -y python3 python3-venv python3-pip curl ca-certificates cron
elif command -v yum >/dev/null 2>&1; then
  yum install -y python3 python3-pip curl ca-certificates cronie
fi

if command -v timedatectl >/dev/null 2>&1; then
  timedatectl set-timezone Asia/Shanghai || true
fi

mkdir -p "$BASE_DIR"
curl -fsSL "${REPO_RAW}/traffic_control.py.template" -o "${BASE_DIR}/traffic_control.py.template"
curl -fsSL "${REPO_RAW}/traffic-control.service" -o "/etc/systemd/system/${SERVICE_NAME}"
curl -fsSL "${REPO_RAW}/cdt" -o "/usr/local/bin/cdt"
chmod +x /usr/local/bin/cdt

export BASE_DIR TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID ADMIN_USER_ID
python3 - <<'PYCONF'
from pathlib import Path
import os
base = Path(os.environ.get('BASE_DIR', '/root/aliyun-traffic-control'))
tpl = (base / 'traffic_control.py.template').read_text(encoding='utf-8')
repl = {
    '__TELEGRAM_BOT_TOKEN__': os.environ['TELEGRAM_BOT_TOKEN'],
    '__TELEGRAM_CHAT_ID__': os.environ['TELEGRAM_CHAT_ID'],
    '__ADMIN_USER_ID__': os.environ['ADMIN_USER_ID'],
}
for k, v in repl.items():
    tpl = tpl.replace(k, v)
(base / 'traffic_control.py').write_text(tpl, encoding='utf-8')
PYCONF

export ACCOUNT_NAME ACCESS_KEY_ID ACCESS_KEY_SECRET INSTANCE_ID REGION_ID BILL_REG_ID MAX_TRAFFIC_GB IS_INTERNATIONAL REPORT_TIME
python3 - <<'PYACCOUNTS'
from pathlib import Path
import os, json
base = Path('/root/aliyun-traffic-control')
accounts = [{
    'name': os.environ['ACCOUNT_NAME'],
    'access_key_id': os.environ['ACCESS_KEY_ID'],
    'access_key_secret': os.environ['ACCESS_KEY_SECRET'],
    'region_id': os.environ['REGION_ID'],
    'instance_id': os.environ['INSTANCE_ID'],
    'bill_region_id': os.environ['BILL_REG_ID'],
    'max_traffic_gb': float(os.environ['MAX_TRAFFIC_GB']),
    'is_international': os.environ['IS_INTERNATIONAL'].lower() == 'true',
    'daily_report_time': os.environ['REPORT_TIME'],
    'enabled': True,
}]
accounts_path = base / 'accounts.json'
if accounts_path.exists():
    # 覆盖安装时不要直接丢失旧 accounts.json；备份后再写入第一个安装账号。
    import datetime
    bak = base / ('accounts.json.bak.' + datetime.datetime.now().strftime('%Y%m%d%H%M%S'))
    bak.write_text(accounts_path.read_text(encoding='utf-8'), encoding='utf-8')
accounts_path.write_text(json.dumps(accounts, ensure_ascii=False, indent=2), encoding='utf-8')
os.chmod(accounts_path, 0o600)
PYACCOUNTS

chmod +x "${BASE_DIR}/traffic_control.py"
python3 -m venv "${BASE_DIR}/venv"
"${BASE_DIR}/venv/bin/pip" install --upgrade pip
"${BASE_DIR}/venv/bin/pip" install aliyun-python-sdk-core aliyun-python-sdk-ecs aliyun-python-sdk-bssopenapi requests python-telegram-bot==13.15 APScheduler==3.6.3 pytz

touch "${BASE_DIR}/keepalive_enabled.flag" "${BASE_DIR}/cron_run.log"

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

( crontab -l 2>/dev/null | grep -v "aliyun-traffic-control/traffic_control.py" || true; echo "$CRON_CHECK" ) | crontab -

echo "======================================"
echo "安装完成：多账号版"
echo "第一个账号：${ACCOUNT_NAME}"
echo "每日报告时间：${REPORT_TIME} UTC+8 / 北京时间"
echo "月初自动恢复：每月1号 00:05 UTC+8 后检测，流量低于各账号阈值才开机"
echo "控制菜单命令：cdt"
echo "新增账号：cdt -> 多账号管理 -> 增加账号"
echo "立即测试日报：cdt -> 8"
echo "======================================"
