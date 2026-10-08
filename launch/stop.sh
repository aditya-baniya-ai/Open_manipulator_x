#!/usr/bin/env bash
# Stop every robot program on this computer: arm launches (real or simulated), RViz,
# MoveIt Servo, controllers, and this repo's scripts. Hold the real arm first: it may
# go limp. Use it when something is left running (e.g. the arm shakes, or RViz won't close).
#
#   ~/Documents/Open_manipulator_x/launch/stop.sh

# Every ROS program runs from /opt/ros/humble or the ROBOTIS workspace
pkill -f /opt/ros/humble
pkill -f colcon_ws/install
pkill -f -e "gestures/(gestures|gui|greet)\.py|perception/detect\.py|voice/listen\.py" > /dev/null
sleep 2

# Restart the ROS helper (ros2 node list etc. need it after a forced stop)
ros2 daemon stop > /dev/null 2>&1
ros2 daemon start > /dev/null 2>&1

LEFT="$(ros2 node list 2>/dev/null)"
if [ -z "$LEFT" ]; then
  echo "Everything is stopped."
else
  echo "Still running (if not on this computer, it's another computer on the network):"
  echo "$LEFT"
fi
