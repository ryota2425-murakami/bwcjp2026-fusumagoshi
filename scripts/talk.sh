#!/usr/bin/env bash
# ふすまの中の Claude と話す(会話デモ)。Mac のマイク・Mac の処理・Mac のスピーカー。Pi には表情の合図だけ。
#   bash lab/scripts/talk.sh [talk_demo の引数…]      例: bash lab/scripts/talk.sh --save --idle 45
# 前提: bash lab/scripts/services.sh start(whisper・AivisSpeech)。中継は talk モードで起動しなおす。
set -u
LAB="$(cd "$(dirname "$0")/.." && pwd)"
PI_IP="${PI_IP:-$(cat "$LAB/logs/pi_ip" "$LAB/logs/pi_ip_extra" 2>/dev/null | tr "\n" " ")}"   # Pi の IP(Wi-Fi と有線の両方を書いてよい)
pkill -f "fusuma.lantern_bridge" 2>/dev/null; sleep 1
( cd "$LAB/app" && exec nohup ../.venv/bin/python -m fusuma.lantern_bridge --talk --allow $PI_IP > "$LAB/logs/lantern_bridge.log" 2>&1 < /dev/null ) > /dev/null 2>&1 &
sleep 2
cd "$LAB/app" && PYTHONUNBUFFERED=1 exec ../.venv/bin/python -W ignore -m fusuma.talk_demo "$@"
