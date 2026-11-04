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
exec "$HERE/game.sh" --hand "$@"
