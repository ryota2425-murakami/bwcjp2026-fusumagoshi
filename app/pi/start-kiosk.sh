#!/bin/sh
# ふすまの中の Claude: Chromium をキオスク表示で起動する(labwc のデスクトップの自動起動から呼ばれる)。
# 中継先は ~/fusuma-lantern/bridge.txt(1 行、カンマ区切り)。deploy_pi.sh が Mac の名前と IP から書く。
DIR="$HOME/fusuma-lantern"
BRIDGE="$(cat "$DIR/bridge.txt" 2>/dev/null | head -1)"
[ -n "$BRIDGE" ] || BRIDGE="ws://mac.local:8781/lantern"          # bridge.txt が無いときの仮の値
ROLE="$(cat "$DIR/role.txt" 2>/dev/null | head -1)"            # kitchen(既定) / family
[ "$ROLE" = "family" ] || ROLE="kitchen"
QX="$(cat "$DIR/query.txt" 2>/dev/null | head -1)"               # 追加の指定(例: night=0)
EXTRA=""
[ -f "$DIR/.debug" ] && EXTRA="--remote-debugging-port=9222"     # 調べるときだけ(Pi の中からだけ繋がる)
sleep 3
exec chromium-browser --kiosk --app="file://$DIR/kiosk.html?bridge=$BRIDGE&role=$ROLE${QX:+&$QX}" \
  --noerrdialogs --disable-infobars --no-first-run --password-store=basic --disable-session-crashed-bubble \
  --disable-features=Translate,TranslateUI --lang=ja --overscroll-history-navigation=0 --disable-pinch --check-for-update-interval=31536000 \
  --user-data-dir="$HOME/.config/fusuma-lantern-chromium" --ozone-platform=wayland $EXTRA
