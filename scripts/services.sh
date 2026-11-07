#!/usr/bin/env bash
# ふすまごし ローカルサービスの起動/停止
#   whisper-server (whisper large-v3-turbo q8_0, Metal) : 127.0.0.1:8765
#   tts server     (Qwen3-TTS / MLX)            : 127.0.0.1:8766
#   AivisSpeech    (行灯の声「まお」。あれば)       : 127.0.0.1:10101   AIVIS_ENGINE_DIR で場所を変えられる
set -u
LAB="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$LAB/logs"; mkdir -p "$LOG"
WHISPER_BIN="$LAB/vendor/whisper.cpp-1.7.6/build/bin/whisper-server"
# kotoba-whisper-v2.0 は 2 秒未満の発話で空文字を返したため(実測)、large-v3-turbo を採用
WHISPER_MODEL="${WHISPER_MODEL:-$LAB/models/whisper/ggml-large-v3-turbo-q8_0.bin}"

start_whisper() {
  if curl -s -o /dev/null http://127.0.0.1:8765/ ; then echo "whisper: already running"; return; fi
  nohup "$WHISPER_BIN" -m "$WHISPER_MODEL" -l ja -nc --host 127.0.0.1 --port 8765 -t 6 > "$LOG/whisper_server.log" 2>&1 &
  echo $! > "$LOG/whisper_server.pid"; echo "whisper: started pid $(cat "$LOG/whisper_server.pid")"
}
start_tts() {
  if curl -s -o /dev/null http://127.0.0.1:8766/health ; then echo "tts: already running"; return; fi
  ( cd "$LAB/app/tts_server" && exec nohup "$LAB/.venv-tts/bin/python" tts_engine.py serve --port 8766 > "$LOG/tts_server.log" 2>&1 ) &
  echo $! > "$LOG/tts_server.pid"
  echo "tts: started pid $(cat "$LOG/tts_server.pid")"
}
AIVIS_DIR="${AIVIS_ENGINE_DIR:-$HOME/video-as-code/engines/aivisspeech}"
start_aivis() {     # 行灯の声。入っていなければ何もしない(TTS は Qwen3-TTS の声で話す)
  if curl -s -o /dev/null http://127.0.0.1:10101/version ; then echo "aivisspeech: already running"; return; fi
  [ -x "$AIVIS_DIR/run" ] || { echo "aivisspeech: not installed ($AIVIS_DIR) — lamp falls back to Qwen3-TTS"; return; }
  ( cd "$AIVIS_DIR" && exec nohup ./run --host 127.0.0.1 --port 10101 --disable_sentry --output_log_utf8 > "$LOG/aivisspeech.log" 2>&1 < /dev/null ) &
  echo $! > "$LOG/aivisspeech.pid"; echo "aivisspeech: started pid $(cat "$LOG/aivisspeech.pid")"
}
stop_all() {
  for n in whisper_server tts_server aivisspeech; do
    [ -f "$LOG/$n.pid" ] && kill "$(cat "$LOG/$n.pid")" 2>/dev/null && echo "$n: stopped"; rm -f "$LOG/$n.pid"
  done
  for port in 8765 8766 10101; do        # pid ファイルが古いときも、ポートで聞いているものを止める
    pid=$(lsof -ti tcp:$port -sTCP:LISTEN 2>/dev/null) && [ -n "$pid" ] && kill $pid && echo "port $port: stopped"
  done
  return 0
}
wait_ready() {   # 起動してから、聞けるようになるまで待つ(TTS はモデルの読み込みに 1〜2 分かかる)
  for i in $(seq 1 420); do       # 初回はモデルの読み込み・取得で数分かかることがある
    w=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8765/ || true)
    t=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8766/health || true)
    if [ "$w" = "200" ] && [ "$t" = "200" ]; then echo "ready (whisper :8765, tts :8766)"; return 0; fi
    sleep 1
  done
  echo "not ready after 420s — logs: $LOG"; return 1
}
status() {
  curl -s -o /dev/null -w "whisper: %{http_code}\n" http://127.0.0.1:8765/ || echo "whisper: down"
  curl -s -w "\n" http://127.0.0.1:8766/health || echo "tts: down"
  curl -s -o /dev/null -w "aivisspeech: %{http_code}\n" http://127.0.0.1:10101/version || echo "aivisspeech: down"
}
case "${1:-start}" in
  start) start_whisper; start_tts; start_aivis; wait_ready ;;
  stop) stop_all ;;
  status) status ;;
  *) echo "usage: $0 start|stop|status" ;;
esac
