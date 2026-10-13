#!/usr/bin/env bash
# Start the whole robot with one command: the arm, the camera, person/object detection,
# and Robo's control panel (gestures, joints, gripper, recording, talking with Robo,
# and greeting people the camera sees).
#
#   ~/Documents/Open_manipulator_x/launch/robo.sh                real arm
#   ~/Documents/Open_manipulator_x/launch/robo.sh --sim          simulated arm in RViz
#   ~/Documents/Open_manipulator_x/launch/robo.sh --rviz         real arm, also shown in RViz
#   ~/Documents/Open_manipulator_x/launch/robo.sh --no-camera    no camera or detection
#
# Detection uses the TensorRT model (~/yolo11n.engine) when it exists, and checks 25
# frames a second while Robo talks. Options to change that (see README, "Faster detection"):
#   --busy-fps 0           pause detection completely while Robo talks (default 25)
#   --yolo yolo11n.pt      use a different YOLO model file
#   --imgsz 320            smaller picture for YOLO: faster, less accurate (default 640)
#
# The arm, camera and detection run in the background (their messages go to log files
# in /tmp). Closing the control panel (Quit, or Ctrl+C here) stops everything.
# On the real arm, hold it first: it goes limp.
#
# The panel's Games tab starts the games. While a game runs, the panel stops the
# camera and detection and unloads the voice models, so the game has the camera and
# the whole GPU; they all come back when the game ends.

# Each background part runs in its own process group, so Ctrl+C here only reaches the
# control panel, and each part can be stopped cleanly afterwards
set -m

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$HERE")"
SIM=false
RVIZ=false
CAMERA=true
DETECT_ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --sim) SIM=true ;;
    --rviz) RVIZ=true ;;
    --no-camera) CAMERA=false ;;
    --busy-fps|--imgsz) DETECT_ARGS+=("$1" "$2"); shift ;;
    --yolo) DETECT_ARGS+=(--model "$2"); shift ;;
    *) echo "Unknown option: $1"
       echo "Use: --sim --rviz --no-camera --busy-fps N --yolo FILE --imgsz N"
       exit 1 ;;
  esac
  shift
done

# Two arm programs at once fight each other (and only one can open the OpenCR's USB
# port), so refuse to start a second. Look for the arm's programs themselves, which
# also finds one that's still starting up (ROS's node list doesn't show those yet),
# like the "Robo" window that autostart.sh opens at login.
if pgrep -f "open_manipulator_x_bringup|ros2_control_node" > /dev/null ||
   ros2 node list 2>/dev/null | grep -q "^/controller_manager$"; then
  echo "An arm (real or simulated) is already running, maybe in the \"Robo\" window"
  echo "that autostart opens at login. Use that one, or stop it first:"
  echo "  $HERE/stop.sh"
  echo "If it's the real arm, hold it first: it may go limp."
  exit 1
fi

GROUPS_TO_STOP=()

# Stop every background part: Ctrl+C to each group (like pressing Ctrl+C in its own
# terminal), forced after 10 seconds
stop_all() {
  echo "Stopping everything ..."
  "$HERE/vision.sh" stop
  for group in "${GROUPS_TO_STOP[@]}"; do
    kill -INT -- -"$group" 2>/dev/null
  done
  for _ in $(seq 100); do
    alive=false
    for group in "${GROUPS_TO_STOP[@]}"; do
      kill -0 -- -"$group" 2>/dev/null && alive=true
    done
    [ "$alive" = false ] && return
    sleep 0.1
  done
  echo "Something didn't stop by itself, forcing it."
  for group in "${GROUPS_TO_STOP[@]}"; do
    kill -KILL -- -"$group" 2>/dev/null
  done
}
trap stop_all EXIT

# 1. The arm
if [ "$SIM" = true ]; then
  echo "Starting the simulated arm (RViz will open) ...   log: /tmp/robo_arm.log"
  ros2 launch open_manipulator_x_bringup base.launch.py use_sim:=false \
    use_fake_hardware:=true fake_sensor_commands:=true start_rviz:=true > /tmp/robo_arm.log 2>&1 &
else
  echo "Starting the real arm ...   log: /tmp/robo_arm.log"
  ros2 launch open_manipulator_x_bringup hardware.launch.py port_name:=/dev/ttyACM0 \
    start_rviz:="$RVIZ" > /tmp/robo_arm.log 2>&1 &
fi
GROUPS_TO_STOP+=($!)

# 2. The camera and detection (vision.sh: the panel stops them during games)
if [ "$CAMERA" = true ]; then
  "$HERE/vision.sh" start "${DETECT_ARGS[@]}"   # the video shows in the control panel
else
  "$HERE/vision.sh" stop
  rm -f /tmp/robo_vision.args                   # nothing to bring back after a game
fi

# 3. The control panel (waits for the arm, then opens)
echo "If it stays on 'Waiting for the arm', look in /tmp/robo_arm.log for errors."
python3 "$REPO/gestures/gui.py"
