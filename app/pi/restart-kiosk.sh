#!/bin/sh
# Pi の上で: キオスクだけを再起動する(SSH から呼べる)
pkill -f "fusuma-lantern-chromium" 2>/dev/null || true
sleep 1
export XDG_RUNTIME_DIR="/run/user/$(id -u)" WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
nohup "$HOME/fusuma-lantern/start-kiosk.sh" > "$HOME/fusuma-lantern/kiosk.log" 2>&1 &
echo "kiosk restarted"
