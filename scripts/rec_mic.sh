#!/bin/zsh
# 部屋の音(Mac のマイク)を録る。始めた時刻を .t0 に書く。Ctrl+C で止める。
OUT="$1"; python3 -c "import time; print(time.time())" > "$OUT.t0"
exec ffmpeg -hide_banner -loglevel warning -f avfoundation -i ":${MIC:-MacBook Proのマイク}" -ac 1 -ar 48000 -y "$OUT"
