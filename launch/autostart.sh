#!/usr/bin/env bash
# Start Robo's control panel by itself when you log in to the Jetson's desktop (the same
# as running robo.sh: the arm, camera, detection, and the panel with talking and games).
#
#   ~/Documents/Open_manipulator_x/launch/autostart.sh on       turn it on
#   ~/Documents/Open_manipulator_x/launch/autostart.sh off      turn it off
#   ~/Documents/Open_manipulator_x/launch/autostart.sh status   is it on?
#
# It opens a terminal window called "Robo" that runs robo.sh, so you can see what it's
# doing (Ctrl+C there stops everything; hold the real arm first). If the arm isn't
# switched on yet, it waits for it. Turning it on only adds one file,
# ~/.config/autostart/robo.desktop; "off" deletes that file again.
#
# The panel opens after you log in. To have it open with no one logging in, also turn
# on automatic login: Settings > Users > Unlock > Automatic Login.

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENTRY="$HOME/.config/autostart/robo.desktop"
PORT="${ROBO_ARM_PORT:-/dev/ttyACM0}"   # the OpenCR's USB port

case "$1" in
  on)
    mkdir -p "$(dirname "$ENTRY")"
    cat > "$ENTRY" <<EOF
[Desktop Entry]
Type=Application
Name=Robo
Comment=Start Robo's control panel (OpenMANIPULATOR-X)
Exec=gnome-terminal --title=Robo -- bash -ic "$HERE/autostart.sh run"
Terminal=false
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=5
EOF
    echo "Robo will start by itself after you log in to the desktop."
    echo "(Added $ENTRY. To turn it off: $HERE/autostart.sh off)"
    ;;
  off)
    rm -f "$ENTRY"
    echo "Robo won't start by itself any more."
    ;;
  status)
    if [ -f "$ENTRY" ]; then echo "On: Robo starts after you log in."
    else echo "Off: start Robo with $HERE/robo.sh"; fi
    ;;
  run)
    # What runs at login (in the "Robo" terminal window)
    echo "Starting Robo ..."
    if [ ! -e "$PORT" ]; then
      echo "Waiting for the arm: turn on its 12 V power and check the OpenCR's USB cable."
      until [ -e "$PORT" ]; do sleep 2; done
      echo "Arm found."
      sleep 3   # let the board finish starting
    fi
    "$HERE/robo.sh"
    echo
    read -r -p "Robo has stopped. Press Enter to close this window." _
    ;;
  *)
    echo "Use: $0 on | off | status"
    exit 1
    ;;
esac
