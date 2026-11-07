#!/usr/bin/env bash
# 書き出した動画の音量をそろえて(-16 LUFS 前後、ピークは -1.5 dBTP 以下)、提出用の場所に写す。
# 物語の「間」(静けさ)をつぶさないよう、圧縮(dynamic)ではなく、一律に持ち上げて頭だけリミッターで抑える。
# bash video/script/finalize_video.sh project/out/fusumagoshi_vN.mp4
set -euo pipefail
V="$(cd "$(dirname "$0")/.." && pwd)"
IN="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
OUT="$V/project/out/fusumagoshi_final.mp4"
I=$(ffmpeg -nostats -i "$IN" -af loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json -f null - 2>&1 | sed -n 's/.*"input_i" : "\(-*[0-9.]*\)".*/\1/p')
GAIN=$(python3 -c "print(round(-16.0 - float('$I'), 2))")
echo "measured ${I} LUFS → gain ${GAIN} dB"
ffmpeg -y -loglevel error -i "$IN" -c:v copy -af "volume=${GAIN}dB,alimiter=limit=0.79:attack=4:release=60:level=0" -c:a aac -b:a 192k -movflags +faststart "$OUT"
ffmpeg -nostats -i "$OUT" -af ebur128=peak=true -f null - 2>&1 | grep -E "^\s+(I|Peak):" | tail -2
ROOT="$(cd "$V/.." && pwd)"
cp "$OUT" "$ROOT/fusumagoshi_demo.mp4"
echo "→ $ROOT/fusumagoshi_demo.mp4 ($(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT") s)"
