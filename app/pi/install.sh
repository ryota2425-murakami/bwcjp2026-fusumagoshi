#!/bin/sh
# Pi の上で 1 回だけ実行: 自動起動を登録する(デスクトップはそのまま。キオスクが全画面で上に出る)。
set -e
DIR="$HOME/fusuma-lantern"
chmod +x "$DIR/start-kiosk.sh"
mkdir -p "$HOME/.config/autostart"
cp "$DIR/fusuma-lantern.desktop" "$HOME/.config/autostart/fusuma-lantern.desktop"
echo "autostart: $HOME/.config/autostart/fusuma-lantern.desktop"
