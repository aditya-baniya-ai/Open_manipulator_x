#!/usr/bin/env bash
# Start the whole robot with one command: the arm, the camera, person/object detection,
# and Robo's control panel (gestures, joints, gripper, recording, talking with Robo,
# and greeting people the camera sees).
#
#   ~/Documents/Open_manipulator_x/launch/robo.sh                real arm
#   ~/Documents/Open_manipulator_x/launch/robo.sh --sim          simulated arm in RViz
#   ~/Documents/Open_manipulator_x/launch/robo.sh --rviz         real arm, also shown in RViz
#   ~/Documents/Open_manipulator_x/launch/robo.sh --no-camera    no camera or detection
#   ~/Documents/Open_manipulator_x/launch/robo.sh --no-video     detection without its video window
#
# Detection speed options (see README, "Faster detection"):
#   --busy-fps 20          keep detecting 20 frames a second while Robo talks (default: pause)
#   --yolo yolo11n.engine  use the TensorRT model (about 3x faster)
#   --imgsz 320            smaller picture for YOLO: faster, less accurate (default 640)
#
# The arm, camera and detection run in the background (their messages go to log files
# in /tmp). Closing the control panel (Quit, or Ctrl+C here) stops everything.
# On the real arm, hold it first: it goes limp.

# Each background part runs in its own process group, so Ctrl+C here only reaches the
# control panel, and each part can be stopped cleanly afterwards
set -m

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$HERE")"
SIM=false
RVIZ=false
CAMERA=true
VIDEO=true
DETECT_ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --sim) SIM=true ;;
    --rviz) RVIZ=true ;;
    --no-camera) CAMERA=false ;;
    --no-video) VIDEO=false ;;
    --busy-fps|--imgsz) DETECT_ARGS+=("$1" "$2"); shift ;;
    --yolo) DETECT_ARGS+=(--model "$2"); shift ;;
    *) echo "Unknown option: $1"
       echo "Use: --sim --rviz --no-camera --no-video --busy-fps N --yolo FILE --imgsz N"
       exit 1 ;;
  esac
  shift
done

# Two arm programs at once fight each other and the arm shakes, so refuse to start a second
if ros2 node list 2>/dev/null | grep -q "^/controller_manager$"; then
  echo "An arm (real or simulated) is already running. Stop it first:"
  echo "  $HERE/stop.sh"
  echo "If it's the real arm, hold it first: it may go limp."
  exit 1
fi

GROUPS_TO_STOP=()

# Stop every background part: Ctrl+C to each group (like pressing Ctrl+C in its own
# terminal), forced after 10 seconds
stop_all() {
  echo "Stopping everything ..."
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

# 2. The camera and detection
if [ "$CAMERA" = true ]; then
  echo "Starting the camera ...   log: /tmp/robo_camera.log"
  ros2 run usb_cam usb_cam_node_exe --ros-args -p video_device:=/dev/video0 \
    -p image_width:=640 -p image_height:=480 -p pixel_format:=mjpeg2rgb \
    -p framerate:=30.0 > /tmp/robo_camera.log 2>&1 &
  GROUPS_TO_STOP+=($!)

  echo "Starting detection (YOLO) ...   log: /tmp/robo_detect.log"
  [ "$VIDEO" = false ] && DETECT_ARGS+=(--no-window)
  PYTHONUNBUFFERED=1 python3 "$REPO/perception/detect.py" "${DETECT_ARGS[@]}" \
    > /tmp/robo_detect.log 2>&1 &
  GROUPS_TO_STOP+=($!)
fi

# 3. The control panel (waits for the arm, then opens)
echo "If it stays on 'Waiting for the arm', look in /tmp/robo_arm.log for errors."
python3 "$REPO/gestures/gui.py"
