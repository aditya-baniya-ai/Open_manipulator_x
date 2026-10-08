# OpenMANIPULATOR-X Greeter Robot

A table robot built from a ROBOTIS OpenMANIPULATOR-X arm and an NVIDIA Jetson Orin Nano running ROS 2 Humble. The goal: it sees people with a camera, greets them with gestures and voice, listens to commands, and picks up small objects like a pencil.

> Demo video / GIF goes here.

## Status

| Part | State |
|---|---|
| Arm test and greeting on the OpenCR (Arduino) | ✅ working |
| ROS 2 Humble on the Jetson | ✅ installed |
| Arm controlled through ROS 2 | ✅ working |
| Wave gesture in ROS 2 | ✅ working |
| More gestures (nod, shake, bow, look around) on key press | 🚧 written, not tested yet |
| Camera, voice, picking | ⏳ planned |

## What's in this repo

```
docs/
  hardware.md          parts list, servo IDs, wiring
  setup_jetson.md      every step to set up the Jetson, in order
  troubleshooting.md   problems we hit and how we fixed them
  OpenMANIPULATOR-X_Quick_Setup.docx   one-page guide for the Arduino test
firmware/
  README.md            how to upload code to the OpenCR board
  servo_check/         Arduino test: stands the arm up and waves
gestures/
  gestures.py          press a key to wave, nod, shake, bow or look around
dependencies.repos     list of ROBOTIS code to download (used in setup)
```

## Getting started

1. Wire the arm: [docs/hardware.md](docs/hardware.md)
2. Test it from a Mac with Arduino: [firmware/README.md](firmware/README.md)
3. Set up the Jetson and run the arm with ROS 2: [docs/setup_jetson.md](docs/setup_jetson.md)

Stuck? See [docs/troubleshooting.md](docs/troubleshooting.md).

## Running the robot (after setup)

Setup only happens once. After a reboot, just:

1. Turn on the arm's 12 V power and plug the OpenCR's USB into the Jetson.
2. Terminal 1, start the arm and leave it running:
   ```bash
   ros2 launch open_manipulator_x_bringup hardware.launch.py port_name:=/dev/ttyACM0
   ```
3. Terminal 2, gestures (press a key to wave, nod, shake, bow, look around):
   ```bash
   python3 ~/Documents/Open_manipulator_x/gestures/gestures.py
   ```

For keyboard control of each joint instead, run these in Terminals 2 and 3:

```bash
ros2 launch open_manipulator_x_moveit_config servo.launch.py
```

```bash
ros2 run open_manipulator_x_teleop open_manipulator_x_teleop
```

**To stop:** quit the gestures (`q`), hold the arm, press Ctrl+C in Terminal 1 (the arm goes limp), then turn off the 12 V power.

## How it works

```
gestures.py            sends joint angles over time
   ↓  ROS 2 action
arm_controller         turns them into a smooth path   ┐ started by
   ↓                                                    │ hardware.launch.py
dynamixel_hardware_interface   sends servo commands    ┘
   ↓  USB /dev/ttyACM0
OpenCR (usb_to_dxl)    passes commands to the servos
   ↓
servos                 move, and report their angles back as /joint_states
```
