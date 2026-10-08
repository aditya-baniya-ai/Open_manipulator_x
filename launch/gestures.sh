#!/usr/bin/env bash
# Start the arm and the gesture menu together, in one terminal.
#
#   ~/Documents/Open_manipulator_x/launch/gestures.sh          real arm
#   ~/Documents/Open_manipulator_x/launch/gestures.sh --sim    simulated arm in RViz
#
# The arm runs in the background (its messages go to a log file), and the gesture
# menu runs here: play gestures, move joints with 1-8, and record your own moves.
# Press q (or Ctrl+C) to stop both. On the real arm, hold it first: it goes limp.

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="/tmp/omx_arm.log"

if [ "$1" = "--sim" ]; then
  echo "Starting the simulated arm (RViz will open) ..."
  ros2 launch open_manipulator_x_bringup base.launch.py use_sim:=false \
    use_fake_hardware:=true fake_sensor_commands:=true start_rviz:=true > "$LOG" 2>&1 &
else
  echo "Starting the real arm ..."
  ros2 launch open_manipulator_x_bringup hardware.launch.py port_name:=/dev/ttyACM0 > "$LOG" 2>&1 &
fi
ARM=$!
# Stop the arm when the gesture menu exits, however it exits
trap 'kill -TERM "$ARM" 2>/dev/null; wait "$ARM" 2>/dev/null' EXIT

echo "Arm messages go to $LOG. If it stays on 'Waiting', look there for errors."
python3 "$HERE/../gestures/gestures.py"
