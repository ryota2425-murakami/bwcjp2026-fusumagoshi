#!/usr/bin/env bash
# 本番の流れを Mac のマイクで動かす(デモの電話 → 通話中は静かに見守る → 電話のあとに話しかける)。Pi には表情の合図だけ。
#   bash lab/scripts/live.sh            (別のターミナルで: lab/.venv/bin/python lab/scripts/phone_sim.py)
#   INPUT=virtual bash lab/scripts/live.sh  (デモの部屋の音: 合成した通話 P01 などを /api/play で流す)
# 前提: bash lab/scripts/services.sh start(whisper・TTS・AivisSpeech)
set -u
LAB="$(cd "$(dirname "$0")/.." && pwd)"
PI_IPS="${PI_IPS:-$(cat "$LAB/logs/pi_ip" "$LAB/logs/pi_ip_extra" 2>/dev/null | tr "\n" " ")}"     # Pi の IP(Wi-Fi と有線の両方を書いてよい)
pkill -f "fusuma.lantern_bridge" 2>/dev/null; sleep 1
( cd "$LAB/app" && exec nohup ../.venv/bin/python -m fusuma.lantern_bridge --allow $PI_IPS > "$LAB/logs/lantern_bridge.log" 2>&1 < /dev/null ) > /dev/null 2>&1 &
cd "$LAB/app" && FUSUMA_INPUT="${INPUT:-mic}" FUSUMA_AUDIBLE="${AUDIBLE:-1}" FUSUMA_POST_CALL_DELAY="${POST_CALL_DELAY:-8}" FUSUMA_MANAGED="${FUSUMA_MANAGED:-0}" \
  FUSUMA_DB="${FUSUMA_DB:-$LAB/runs/live.sqlite3}" FUSUMA_SAVE_SPEECH=1 PYTHONUNBUFFERED=1 \
  exec ../.venv/bin/uvicorn fusuma.server:app --host 127.0.0.1 --port 8780
