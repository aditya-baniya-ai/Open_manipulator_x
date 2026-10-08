# Jetson setup notes

The commands are in the [README](../README.md). This file explains why each step is needed and tracks progress.

## System

- Board: NVIDIA Jetson Orin Nano
- OS: Ubuntu 22.04.5 (so ROS 2 **Humble**)
- JetPack version: TODO (`cat /etc/nv_tegra_release`)
- Install type: native (no Docker), to avoid USB, GPU, audio and display passthrough problems

## Progress

| Step | Status |
|---|---|
| ROS 2 Humble installed | ✅ talker/listener test works |
| USB permission (dialout) | ✅ `groups` lists dialout |
| `usb_to_dxl` uploaded to OpenCR (from Mac) | ✅ `[OK] Download` |
| ROBOTIS arm packages built | ✅ 12 packages, about 2.5 min |
| `.bashrc` + udev rules | ✅ |
| Arm launched through ROS 2 | ✅ arm_controller active, gripper moves |
| Keyboard teleop | ✅ joints move with MoveIt Servo |
| Wave gesture | ✅ arm waves through ROS 2 |
| Other gestures (nod, shake, bow, look around) | ✅ all move correctly |

## Why each step

**Step 1, firmware.** `usb_to_dxl` turns the OpenCR into a USB-to-servo bridge. It has no motions of its own; the Jetson does all the control. It stays on the board after power off. Uploading any other sketch (like `servo_check`) replaces it.

**Step 2, ROS 2 Humble.** Humble is the ROS 2 version for Ubuntu 22.04. To check the install, run `ros2 run demo_nodes_cpp talker` in one terminal and `ros2 run demo_nodes_py listener` in another; the listener should print what the talker sends.

**Step 3, this repo.** It lives in `~/Documents/Open_manipulator_x`, outside the ROS workspace. Only the ROBOTIS code goes in `~/colcon_ws`. The gestures script is plain Python, so it doesn't need building.

**Step 4, dialout.** Serial ports like `/dev/ttyACM0` belong to the `dialout` group. Group changes only apply after logging in again; a new terminal isn't enough.

**Step 5, ROBOTIS software.**
- The apt packages are ros2_control (talks to motor hardware), ros2_controllers (the `arm_controller`), gripper controllers, and MoveIt (motion planning, needed later for picking).
- `vcs import` downloads the 4 ROBOTIS repos listed in `dependencies.repos`: DynamixelSDK, dynamixel_hardware_interface, dynamixel_interfaces, and open_manipulator (`humble` branch of the official ROBOTIS-GIT repo, not older forks).
- `rosdep` installs everything those repos need. The Gazebo keys are skipped because Gazebo (the simulator) isn't built for ARM computers like the Jetson.
- `colcon build` compiles the code into `~/colcon_ws/install`. `--symlink-install` means edits to Python and config files apply without rebuilding.

**Step 6, terminal and udev.** The `.bashrc` lines make every new terminal find ROS 2 and the ROBOTIS packages. The udev rules set the OpenCR port's permissions and low-latency mode.

**Step 7, check.** `/dev/ttyACM0` is the OpenCR's USB port as seen by Linux.

## Other launch files

In `open_manipulator_x_bringup`:
- `fake.launch.py`: a pretend arm with no hardware, good for testing code safely.
- `gazebo.launch.py`: simulation (not available on the Jetson).

## Changing gestures

Edit the `GESTURES` list at the top of `gestures/gestures.py`. Each move is (base turn, shoulder, elbow, wrist, seconds), in radians, with 0 = home pose. ROS 2 uses radians, and 0 rad equals 180° on the servos. If a gesture moves the wrong way, flip the sign of that number.
