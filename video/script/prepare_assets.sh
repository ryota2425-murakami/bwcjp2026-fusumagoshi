#!/usr/bin/env bash
# 動画 v2 の public/ に素材を揃える(縮小・形式をそろえる)。何度実行してもよい。
# 写真・映像は Pexels(assets/CREDITS.md)。収録(rec)は lab/app/scripts/record_demo.py で撮ったもの。
set -euo pipefail
V="$(cd "$(dirname "$0")/.." && pwd)"
LAB="$V/../lab"; [ -d "$LAB/app" ] || LAB="$V/.."     # 検証用(lab/)でもリポジトリの中でも
P="$V/project/public"
mkdir -p "$P"/{img,video,rec,audio,music}
STOCK="$V/assets/stock"

# 実写の写真(幅 2400 まで)
for p in fusuma_ajar_38944471:fusuma_ajar washitsu_dusk_20025763:washitsu_dusk fusuma_scroll_5220083:fusuma_scroll \
         shoji_windowlight_37417304:shoji_windowlight oldroom_light_34619706:oldroom_light engawa_chair_8141380:engawa_chair; do
  ffmpeg -y -loglevel error -i "$STOCK/photo_${p%%:*}.jpg" -vf "scale='min(2400,iw)':-2" -q:v 3 "$P/img/${p##*:}.jpg"
done
# 実写の動画(1920x1080・30fps・音なし)
for n in phone_ringing_1721320 apartment_night_9431584 phone_hands_33942937; do
  ffmpeg -y -loglevel error -i "$STOCK/video_$n.mp4" -vf "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30" -an -c:v libx264 -crf 20 -preset medium -pix_fmt yuv420p "$P/video/${n%_*}.mp4"
done
# 黒電話のダイヤル中央の札(英国の緊急番号 999 の表示)は、日本の家として不自然なのでぼかす(カメラは固定)
BLUR="[0:v]split[a][b];[b]crop=300:300:1085:522,gblur=sigma=10,format=yuva420p,geq=lum='p(X,Y)':cb='p(X,Y)':cr='p(X,Y)':a='if(lte(hypot(X-150,Y-150),104),255,if(lte(hypot(X-150,Y-150),118),255*(118-hypot(X-150,Y-150))/14,0))'[c];[a][c]overlay=1085:522"
mv "$P/video/phone_ringing.mp4" "$P/video/phone_ringing_raw.mp4"
ffmpeg -y -loglevel error -i "$P/video/phone_ringing_raw.mp4" -filter_complex "$BLUR" -an -c:v libx264 -crf 20 -preset medium -pix_fmt yuv420p "$P/video/phone_ringing.mp4"
rm -f "$P/video/phone_ringing_raw.mp4"
# 鳴りやんだ黒電話(同じ映像の 5.4 秒目の一枚)
ffmpeg -y -loglevel error -ss 5.4 -i "$P/video/phone_ringing.mp4" -frames:v 1 -q:v 2 "$P/img/phone_still.jpg"
# Getty Images の素材(作者が用意して assets/getty/ に置いたもの。リポジトリには同梱しない)。無ければ飛ばす
G="$V/assets/getty"
if [ -d "$G" ]; then
  [ -f "$G/GettyImages-147415337.jpg" ] && ffmpeg -y -loglevel error -i "$G/GettyImages-147415337.jpg" -vf "scale=2400:-2" -q:v 3 "$P/img/getty_family_meal.jpg"
  [ -f "$G/GettyImages-1997570001.jpg" ] && ffmpeg -y -loglevel error -i "$G/GettyImages-1997570001.jpg" -vf "scale=2400:-2" -q:v 3 "$P/img/getty_hands_table.jpg"
  for p in 2243613428:getty_doors 2200626707:getty_room_light 2251862155:getty_teishoku; do
    [ -f "$G/GettyImages-${p%%:*}.mov" ] && ffmpeg -y -loglevel error -i "$G/GettyImages-${p%%:*}.mov" -vf "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30" -an -c:v libx264 -crf 19 -preset medium -pix_fmt yuv420p "$P/video/${p##*:}.mp4"
  done
fi
# 画面の録画(通話と便りは同じ回のもの)
for n in call_S05_v4 letter_v4; do d="$V/assets/rec/$n"; [ -f "$d/screen.mp4" ] && mkdir -p "$P/rec/$n" && cp "$d/screen.mp4" "$d/timing.json" "$P/rec/$n/"; done
# 呼出音(合成)。祖母の声・ふすまごしの声は build_timeline_v2.py が lab から写す
cp "$LAB/data/sfx/ring.wav" "$P/audio/ring.wav"
# 効果音と、技術の場面のリズム(数式で合成)
PY="$LAB/.venv/bin/python"; [ -x "$PY" ] || PY=python3      # numpy・scipy・soundfile が要る
"$PY" "$V/script/make_sfx.py"
# 音楽(Mixkit)
cp "$V/assets/music/"*.mp3 "$P/music/"
du -sh "$P"/* | sort -h
