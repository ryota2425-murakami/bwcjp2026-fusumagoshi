#!/usr/bin/env bash
# Mac から Pi へ、行灯のキオスクを配る(画面のファイル + 起動スクリプト)して、キオスクを再起動する。
#   PI=pi@<Pi の IP> bash scripts/deploy_pi.sh
#   中継先は BRIDGE(既定: この Mac の名前.local と IP の 2 つ)を Pi の ~/fusuma-lantern/bridge.txt に書く
# SSH は鍵か、先に開いた接続(ControlPath)を使う。パスワードはこのスクリプトに書かない。
set -euo pipefail
LAB="$(cd "$(dirname "$0")/.." && pwd)"
PI="${PI:-pi@$(cat "$(cd "$(dirname "$0")" && pwd)/../../lab/logs/pi_ip" 2>/dev/null || echo raspberrypi.local)}"
SSH_OPTS="${SSH_OPTS:--o ControlPath=$HOME/.ssh/fsm-pi.sock}"
rsync -a --delete -e "ssh $SSH_OPTS" --exclude '.debug' --exclude 'bridge.txt' --exclude 'role.txt' --exclude 'query.txt' --exclude 'kiosk.log' \
  "$LAB/app/web/lantern/" "$LAB/app/pi/" "$PI:fusuma-lantern/"
if [ -z "${BRIDGE:-}" ]; then
  HOST="$(scutil --get LocalHostName 2>/dev/null || hostname -s)"
  IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)"
  BRIDGE="ws://$HOST.local:8781/lantern${IP:+,ws://$IP:8781/lantern}"
fi
ssh $SSH_OPTS "$PI" "echo '$BRIDGE' > ~/fusuma-lantern/bridge.txt && sh ~/fusuma-lantern/install.sh && sh ~/fusuma-lantern/restart-kiosk.sh"
