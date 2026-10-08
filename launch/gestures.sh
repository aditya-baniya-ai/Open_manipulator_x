#!/usr/bin/env bash
# Start the arm and the gesture controls together, in one terminal.
#
#   ~/Documents/Open_manipulator_x/launch/gestures.sh               real arm, keyboard menu
#   ~/Documents/Open_manipulator_x/launch/gestures.sh --sim         simulated arm in RViz
#   ~/Documents/Open_manipulator_x/launch/gestures.sh --gui         buttons in a window
#   ~/Documents/Open_manipulator_x/launch/gestures.sh --sim --gui   both
#
# The arm runs in the background (its messages go to a log file). The controls let
# you play gestures, move each joint, open/close the gripper and record your own moves.
# Quitting them (q, the Quit button, or Ctrl+C) stops the arm too.
# On the real arm, hold it first: it goes limp.

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="/tmp/omx_arm.log"
SIM=false
CONTROLS="gestures.py"
for arg in "$@"; do
  case "$arg" in
    --sim) SIM=true ;;
    --gui) CONTROLS="gui.py" ;;
    *) echo "Unknown option: $arg (use --sim and/or --gui)"; exit 1 ;;
  esac
done

if [ "$SIM" = true ]; then
  echo "Starting the simulated arm (RViz will open) ..."
  ros2 launch open_manipulator_x_bringup base.launch.py use_sim:=false \
    use_fake_hardware:=true fake_sensor_commands:=true start_rviz:=true > "$LOG" 2>&1 &
else
  echo "Starting the real arm ..."
  ros2 launch open_manipulator_x_bringup hardware.launch.py port_name:=/dev/ttyACM0 > "$LOG" 2>&1 &
fi
ARM=$!
# Stop the arm when the controls exit, however they exit
trap 'kill -TERM "$ARM" 2>/dev/null; wait "$ARM" 2>/dev/null' EXIT

echo "Arm messages go to $LOG. If it stays on 'Waiting', look there for errors."
python3 "$HERE/../gestures/$CONTROLS"
