# Hardware

## Parts

- OpenMANIPULATOR-X arm on its base plate
- OpenCR 1.0 board
- 12 V 5 A power adapter
- Micro USB data cable
- NVIDIA Jetson Orin Nano (Ubuntu 22.04.5)
- Camera: Logitech BRIO (USB). Color picture is `/dev/video0`; `/dev/video2` is its infrared camera.
- Microphone, speaker (TODO: models)

## Servos

DYNAMIXEL servos on one daisy-chained TTL cable, 1 Mbps, Protocol 2.0.

| ID | Joint | ROS name |
|---|---|---|
| 11 | Base (rotation) | joint1 |
| 12 | Shoulder | joint2 |
| 13 | Elbow | joint3 |
| 14 | Wrist | joint4 |
| 15 | Gripper | gripper |

180° on the servo (2048 steps) is the center and equals 0 rad in ROS.

## Wiring

- Keep the board's power switch OFF while connecting cables.
- Arm's white 3-pin cable → the first 3-pin TTL port on the bottom-left edge of the OpenCR (next to the red connector). Not the 4-pin ports.
- 12 V adapter → round power jack.
- OpenCR micro USB (right edge) → Mac (for Arduino) or Jetson (for ROS 2).

Photos: TODO (add the board photo here).
