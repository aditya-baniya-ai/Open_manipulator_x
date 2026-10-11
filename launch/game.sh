#!/usr/bin/env bash
# Start a game with one command: the arm, then the game.
#
#   ~/Documents/Open_manipulator_x/launch/game.sh              Puppet Master, real arm
#   ~/Documents/Open_manipulator_x/launch/game.sh --sim        simulated arm in RViz
#   ~/Documents/Open_manipulator_x/launch/game.sh --no-arm     no arm at all (pretend arm)
#   ~/Documents/Open_manipulator_x/launch/game.sh --setup      place the target stickers
#   ~/Documents/Open_manipulator_x/launch/game.sh --balls      Ball Carry instead
#
# Other options go to the game, e.g. --fullscreen, --tracker yolo, --camera /dev/video2,
# --keyboard (Ball Carry: W A S D and Space instead of your hand).
# The camera must face the player and not be used by another program (don't run
# robo.sh or usb_cam at the same time).
#
# The arm runs in the background (log: /tmp/robo_arm.log). Quitting the game (Esc,
# or Ctrl+C here) stops everything. On the real arm, hold it first: it goes limp.

set -m   # the arm runs in its own process group, so it can be stopped cleanly

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$HERE")"
SIM=false
NO_ARM=false
GAME=puppet_master.py
GAME_ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --sim) SIM=true ;;
    --no-arm) NO_ARM=true; GAME_ARGS+=(--no-arm) ;;
    --balls) GAME=ball_carry.py ;;
    *) GAME_ARGS+=("$1") ;;
  esac
  shift
done

# MediaPipe lives in its own environment (see README, "Puppet Master"), if it's set up
PYTHON=python3
[ -x "$HOME/game_venv/bin/python" ] && PYTHON="$HOME/game_venv/bin/python"

if [ "$NO_ARM" = true ]; then
  cd "$REPO/game" && exec "$PYTHON" "$GAME" "${GAME_ARGS[@]}"
fi

# Two arm programs at once fight each other and the arm shakes, so refuse to start a second
if ros2 node list 2>/dev/null | grep -q "^/controller_manager$"; then
  echo "An arm (real or simulated) is already running. Stop it first:"
  echo "  $HERE/stop.sh"
  echo "If it's the real arm, hold it first: it may go limp."
  exit 1
fi

ARM_GROUP=""
stop_arm() {
  [ -z "$ARM_GROUP" ] && return
  echo "Stopping the arm ..."
  kill -INT -- -"$ARM_GROUP" 2>/dev/null
  for _ in $(seq 100); do
    kill -0 -- -"$ARM_GROUP" 2>/dev/null || return
    sleep 0.1
  done
  kill -KILL -- -"$ARM_GROUP" 2>/dev/null
}
trap stop_arm EXIT

if [ "$SIM" = true ]; then
  echo "Starting the simulated arm (RViz will open) ...   log: /tmp/robo_arm.log"
  ros2 launch open_manipulator_x_bringup base.launch.py use_sim:=false \
    use_fake_hardware:=true fake_sensor_commands:=true start_rviz:=true > /tmp/robo_arm.log 2>&1 &
else
  echo "Starting the real arm ...   log: /tmp/robo_arm.log"
  ros2 launch open_manipulator_x_bringup hardware.launch.py port_name:=/dev/ttyACM0 \
    > /tmp/robo_arm.log 2>&1 &
fi
ARM_GROUP=$!

echo "If it stays on 'Waiting for the arm', look in /tmp/robo_arm.log for errors."
cd "$REPO/game" && "$PYTHON" "$GAME" "${GAME_ARGS[@]}"
