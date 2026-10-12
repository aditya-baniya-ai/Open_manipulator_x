#!/usr/bin/env bash
# Robo's eyes: the camera and person/object detection (YOLO, on the GPU), started and
# stopped together. robo.sh uses it, and so does the control panel, to free the camera
# and the GPU while a game is running.
#
#   vision.sh start [detect.py options]   start the camera and detection
#   vision.sh stop                         stop them (frees the camera and the GPU)
#   vision.sh resume                       start them again, with the same options
#   vision.sh running                      exit code 0 if they're running
#
# Logs: /tmp/robo_camera.log and /tmp/robo_detect.log

# Job control: each part runs in its own process group (so it can be stopped on its own),
# and Ctrl+C reaches it (a script's background programs ignore Ctrl+C otherwise)
set -m

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$HERE")"
PIDS=/tmp/robo_vision.pids     # the process groups of the camera and detection
ARGS=/tmp/robo_vision.args     # detection's options, for resume

running() {
  [ -f "$PIDS" ] || return 1
  for group in $(cat "$PIDS"); do
    kill -0 -- -"$group" 2>/dev/null && return 0
  done
  return 1
}

start() {
  if running; then
    echo "The camera and detection are already running."
    return 0
  fi
  printf '%s\n' "$@" > "$ARGS"   # detection's options, for resume
  : > "$PIDS"
  echo "Starting the camera ...   log: /tmp/robo_camera.log"
  ros2 run usb_cam usb_cam_node_exe --ros-args -p video_device:=/dev/video0 \
    -p image_width:=640 -p image_height:=480 -p pixel_format:=mjpeg2rgb \
    -p framerate:=30.0 > /tmp/robo_camera.log 2>&1 &
  echo $! >> "$PIDS"

  echo "Starting detection (YOLO) ...   log: /tmp/robo_detect.log"
  PYTHONUNBUFFERED=1 python3 "$REPO/perception/detect.py" --no-window "$@" \
    > /tmp/robo_detect.log 2>&1 &
  echo $! >> "$PIDS"
}

stop() {
  [ -f "$PIDS" ] || return 0
  # Ctrl+C to each part (like pressing Ctrl+C in its own terminal), forced after 10 s
  for group in $(cat "$PIDS"); do
    kill -INT -- -"$group" 2>/dev/null
  done
  for _ in $(seq 100); do
    running || break
    sleep 0.1
  done
  if running; then
    echo "The camera or detection didn't stop by itself, forcing it."
    for group in $(cat "$PIDS"); do
      kill -KILL -- -"$group" 2>/dev/null
    done
  fi
  rm -f "$PIDS"
}

case "$1" in
  start) shift; start "$@" ;;
  stop) stop ;;
  resume)
    # Only if they were started before (robo.sh --no-camera: nothing to bring back)
    [ -f "$ARGS" ] || exit 0
    OPTIONS=()
    while IFS= read -r line; do
      [ -n "$line" ] && OPTIONS+=("$line")
    done < "$ARGS"
    start "${OPTIONS[@]}" ;;
  running) running ;;
  *) echo "Use: $0 start [detect.py options] | stop | resume | running"; exit 1 ;;
esac
