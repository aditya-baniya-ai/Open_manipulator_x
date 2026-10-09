# Hardware

## Parts

- OpenMANIPULATOR-X arm on its base plate
- OpenCR 1.0 board
- 12 V 5 A power adapter
- Micro USB data cable
- NVIDIA Jetson Orin NX 16GB (Engineering Reference Developer Kit), Ubuntu 22.04.5, 16 GB memory
- Camera: Logitech BRIO (USB). Color picture is `/dev/video0`; `/dev/video2` is its infrared camera.
- Microphone: the BRIO's built-in mic, `plughw:CARD=BRIO,DEV=0`. The Jetson has no mic of its own.
- Speaker: a USB speaker ("USB PnP Audio Device"), `plughw:CARD=Device,DEV=0`. The Jetson has no speaker or headphone jack of its own.

Sound card **numbers** change when USB audio devices are plugged in (the BRIO was card 2, then card 3 after adding the speaker), so always use the **names** above, not `plughw:2,0`. List them with `aplay -l` (speakers) and `arecord -l` (microphones).

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

Servo settings: ROBOTIS's defaults are Position P/I/D gain 800/100/100 for every servo. This setup uses **400/0/0 for the base (ID 11)** to stop it jittering (README, setup Step 5b).

## Mounting direction

Mount the arm so that with the **base servo at 0°** (the middle of its range) the arm faces your work area. The base can only turn about ±180° from there, so if "forward" sits near ±180° the arm is stuck at an end stop on one side.

To check: start the arm, run `ros2 topic echo /joint_states --once`, and look at `joint1` while the arm faces forward. It should be close to 0. If it's close to ±3.14 instead, the arm is mounted backwards: turn off the 12 V, unscrew the base bracket from the plate, turn the **whole** arm 180° (hold it by the bottom servo so the servo itself doesn't turn), and screw it back down.

## Power off = the arm slumps

With the 12 V off (or torque off), the arm can't hold itself up and folds under its own weight, often past the shoulder and elbow limits. Before starting the arm again, hold it so it stands roughly straight up, and keep holding it while you turn the 12 V on. All the programs in this repo check this at startup and refuse to move the arm if a joint is out of its safe range.

## Wiring

- Keep the board's power switch OFF while connecting cables.
- Arm's white 3-pin cable → the first 3-pin TTL port on the bottom-left edge of the OpenCR (next to the red connector). Not the 4-pin ports.
- 12 V adapter → round power jack.
- OpenCR micro USB (right edge) → Mac (for Arduino) or Jetson (for ROS 2).

Photos: TODO (add the board photo here).
