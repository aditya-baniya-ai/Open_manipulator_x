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
  wave.py              ROS 2 wave gesture
dependencies.repos     list of ROBOTIS code to download (used in setup)
```

## Getting started

1. Wire the arm: [docs/hardware.md](docs/hardware.md)
2. Test it from a Mac with Arduino: [firmware/README.md](firmware/README.md)
3. Set up the Jetson and run the arm with ROS 2: [docs/setup_jetson.md](docs/setup_jetson.md)

Stuck? See [docs/troubleshooting.md](docs/troubleshooting.md).
