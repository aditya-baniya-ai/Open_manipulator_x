#!/usr/bin/env bash
# Control Robo's arm with your hand (no game): starts the arm, then a window with the
# camera, your hand, and the claw following it. Esc closes it (hold the real arm first).
#
#   ~/Documents/Open_manipulator_x/launch/hand.sh               real arm
#   ~/Documents/Open_manipulator_x/launch/hand.sh --fullscreen  full screen
#   ~/Documents/Open_manipulator_x/launch/hand.sh --sim         simulated arm in RViz
#   ~/Documents/Open_manipulator_x/launch/hand.sh --no-arm      no arm (pretend arm)
#   ~/Documents/Open_manipulator_x/launch/hand.sh --keyboard    W A S D and Space
#
# To start it by itself at login: ~/Documents/Open_manipulator_x/launch/autostart.sh on hand

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Before the real arm starts: if a joint reads a whole turn off (like the base saying
# 353° when it faces forward), fix_turns.py corrects it, so the safe-range check passes.
# Skipped with --sim / --no-arm, and while an arm program already has the USB port.
REAL_ARM=true
for arg in "$@"; do
  case "$arg" in --sim|--no-arm) REAL_ARM=false ;; esac
done
if [ "$REAL_ARM" = true ] && [ -e /dev/ttyACM0 ] &&
   ! pgrep -f "open_manipulator_x_bringup|ros2_control_node" > /dev/null; then
  /usr/bin/python3 "$HERE/fix_turns.py" --port /dev/ttyACM0
fi

exec "$HERE/game.sh" --hand "$@"
