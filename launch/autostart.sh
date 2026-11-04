#!/usr/bin/env bash
# Start Robo by itself when you log in to the Jetson's desktop: the control panel (the
# same as running robo.sh: the arm, camera, detection, and the panel with talking and
# games), or straight into one game, full screen.
#
#   ~/Documents/Open_manipulator_x/launch/autostart.sh on           the control panel
#   ~/Documents/Open_manipulator_x/launch/autostart.sh on claw      Chocolate Catcher
#   ~/Documents/Open_manipulator_x/launch/autostart.sh on balls     Ball Carry
#   ~/Documents/Open_manipulator_x/launch/autostart.sh on puppet    Puppet Master
#   ~/Documents/Open_manipulator_x/launch/autostart.sh on hand      hand control (no game)
#   ~/Documents/Open_manipulator_x/launch/autostart.sh off          turn it off
#   ~/Documents/Open_manipulator_x/launch/autostart.sh status       is it on, and what?
#
# It opens a terminal window called "Robo" that runs it, so you can see what it's doing
# (Ctrl+C there stops everything; hold the real arm first). If the arm isn't switched on
# yet, it waits for it. A game keeps going player after player (after the results it's
# back at the title screen); Esc closes it. Turning it on only adds one file,
# ~/.config/autostart/robo.desktop; "off" deletes that file again.
#
# It starts after you log in. To have it start with no one logging in, also turn on
# automatic login: Settings > Users > Unlock > Automatic Login.

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENTRY="$HOME/.config/autostart/robo.desktop"
PORT="${ROBO_ARM_PORT:-/dev/ttyACM0}"   # the OpenCR's USB port

describe() {
  case "$1" in
    claw) echo "Chocolate Catcher" ;;
    balls) echo "Ball Carry" ;;
    puppet) echo "Puppet Master" ;;
    hand) echo "hand control" ;;
    *) echo "the control panel" ;;
  esac
}

case "$1" in
  on)
    WHAT="${2:-panel}"
    case "$WHAT" in
      panel|claw|balls|puppet|hand) ;;
      *) echo "Use: $0 on [claw | balls | puppet | hand]   (nothing = the control panel)"; exit 1 ;;
    esac
    mkdir -p "$(dirname "$ENTRY")"
    cat > "$ENTRY" <<EOF
[Desktop Entry]
Type=Application
Name=Robo
Comment=Start Robo: $(describe "$WHAT") (OpenMANIPULATOR-X)
Exec=gnome-terminal --title=Robo -- bash -ic "$HERE/autostart.sh run $WHAT"
Terminal=false
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=5
EOF
    echo "$(describe "$WHAT") will start by itself after you log in to the desktop."
    echo "(Added $ENTRY. To turn it off: $HERE/autostart.sh off)"
    ;;
  off)
    rm -f "$ENTRY"
    echo "Robo won't start by itself any more."
    ;;
  status)
    if [ -f "$ENTRY" ]; then
      WHAT="$(sed -n 's/.*autostart.sh run \([a-z]*\).*/\1/p' "$ENTRY")"
      echo "On: $(describe "$WHAT") starts after you log in."
    else
      echo "Off: start Robo with $HERE/robo.sh"
    fi
    ;;
  run)
    # What runs at login (in the "Robo" terminal window)
    WHAT="${2:-panel}"
    echo "Starting $(describe "$WHAT") ..."
    if [ ! -e "$PORT" ]; then
      echo "Waiting for the arm: turn on its 12 V power and check the OpenCR's USB cable."
      until [ -e "$PORT" ]; do sleep 2; done
      echo "Arm found."
      sleep 3   # let the board finish starting
    fi
    if [ "$WHAT" = panel ]; then
      "$HERE/robo.sh"
    else
      GAME=()
      [ "$WHAT" = claw ] && GAME=(--claw)
      [ "$WHAT" = balls ] && GAME=(--balls)
      [ "$WHAT" = hand ] && GAME=(--hand)
      # One game, full screen, for player after player (it returns to its title screen
      # after each round). Not restarted when it closes: that would restart the arm,
      # and the arm goes limp in between
      "$HERE/game.sh" "${GAME[@]}" --fullscreen
    fi
    echo
    read -r -p "Robo has stopped. Press Enter to close this window." _
    ;;
  *)
    echo "Use: $0 on [claw | balls | puppet | hand] | off | status"
    exit 1
    ;;
esac
