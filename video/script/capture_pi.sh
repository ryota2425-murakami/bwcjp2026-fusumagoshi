#!/usr/bin/env bash
# Pi の画面を、録画のときのイベントを流し直しながら撮る(動画の「Pi の画面」用。Claude は呼ばない)。
#   bash video/script/capture_pi.sh <timing.json> <録画の何秒目から> <長さ秒> <kitchen|family> <出力.mp4>
# 例: bash video/script/capture_pi.sh video/assets/rec/call_S05_v4/timing.json 330 40 kitchen video/assets/pi/after_call.mp4
# 前提: Pi に SSH の接続(ControlPath)が開いていて、キオスクが配ってあること(lab/scripts/deploy_pi.sh)。
set -euo pipefail
TIMING="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"; FROM="$2"; DUR="$3"; ROLE="$4"; OUT="$5"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PI="${PI:-pi@$(cat "$(cd "$(dirname "$0")" && pwd)/../../lab/logs/pi_ip" 2>/dev/null || echo raspberrypi.local)}"; PI_IP="${PI#*@}"
SSHC=(ssh -o ControlPath="$HOME/.ssh/fsm-pi.sock" -o BatchMode=yes "$PI")
mkdir -p "$(dirname "$OUT")"

# 1) 中継を「流し直し」で起動しなおす(役割は Mac 側で決める)
pkill -f "fusuma.lantern_bridge" 2>/dev/null || true; sleep 1
ROLEARG=(--allow "$PI_IP"); [ "$ROLE" = "family" ] && ROLEARG=(--family "$PI_IP")
( cd "$ROOT/lab/app" && exec nohup ../.venv/bin/python -m fusuma.lantern_bridge "${ROLEARG[@]}" --replay "$TIMING" \
    --replay-from "$FROM" --replay-manual > "$ROOT/lab/logs/lantern_bridge_replay.log" 2>&1 < /dev/null ) > /dev/null 2>&1 &
sleep 2

# 2) キオスクを同じ役割で再起動して、中継につながるまで待つ
"${SSHC[@]}" "echo $ROLE > ~/fusuma-lantern/role.txt && sh ~/fusuma-lantern/restart-kiosk.sh" >/dev/null
for i in $(seq 1 60); do
  n=$(curl -s http://127.0.0.1:8781/status | python3 -c "import json,sys; print(json.load(sys.stdin)['peers'])" 2>/dev/null || echo 0)
  [ "$n" -ge 1 ] && break; sleep 1
done
sleep 4      # 立ち上がりの演技が落ち着くまで

# 3) Mac と Pi の時計の差を測る
m0=$(python3 -c "import time; print(time.time())"); pt=$("${SSHC[@]}" 'date +%s.%N'); m1=$(python3 -c "import time; print(time.time())")
OFF=$(python3 -c "print($pt - ($m0 + $m1) / 2)")          # Pi の時計 − Mac の時計

# 4) Pi で録画を始めて、少しあとに流し直しを始める
"${SSHC[@]}" "export XDG_RUNTIME_DIR=/run/user/\$(id -u) WAYLAND_DISPLAY=wayland-0; rm -f /tmp/fsm_cap.mkv; \
  date +%s.%N > /tmp/fsm_cap.t0; nohup wf-recorder -f /tmp/fsm_cap.mkv -c libx264 -x yuv420p -p preset=veryfast -p crf=14 -r 30 > /tmp/fsm_cap.log 2>&1 < /dev/null &"
sleep 1.5
START=$(curl -s -X POST http://127.0.0.1:8781/replay/start | python3 -c "import json,sys; print(json.load(sys.stdin)['started_at'])")
sleep "$(python3 -c "print($DUR + 1.0)")"
"${SSHC[@]}" 'pkill -INT -f "wf-recorder -f /tmp/fsm_cap.mkv"; sleep 2; cat /tmp/fsm_cap.t0' > /tmp/fsm_cap.t0.local
T0=$(cat /tmp/fsm_cap.t0.local | tail -1)
scp -q -o ControlPath="$HOME/.ssh/fsm-pi.sock" "$PI:/tmp/fsm_cap.mkv" /tmp/fsm_cap.mkv

# 5) 流し直しを始めた瞬間から DUR 秒を切り出し、画面の向き(横)に直す
SKIP=$(python3 -c "print(max(0.0, ($START + $OFF) - $T0))")
ffmpeg -loglevel error -y -ss "$SKIP" -i /tmp/fsm_cap.mkv -t "$DUR" -vf "transpose=1,fps=30,format=yuv420p" -c:v libx264 -crf 14 -preset slow "$OUT"
echo "captured $OUT (skip ${SKIP}s, clock offset ${OFF}s)"

# 6) 中継をふだんの状態に戻す
pkill -f "fusuma.lantern_bridge" 2>/dev/null || true; sleep 1
"${SSHC[@]}" "rm -f ~/fusuma-lantern/role.txt && sh ~/fusuma-lantern/restart-kiosk.sh" >/dev/null
( cd "$ROOT/lab/app" && exec nohup ../.venv/bin/python -m fusuma.lantern_bridge --allow "$PI_IP" > "$ROOT/lab/logs/lantern_bridge.log" 2>&1 < /dev/null ) > /dev/null 2>&1 &
