# Robo: project summary and handoff

A summary of what this repo built, how the Jetson and the robot are set up, and everything a
**new project on the same Jetson and the same arm** (for example a chess-playing robot, in its
own repo) needs to know. Copy this file into a new repo as its starting notes.

Repo: https://github.com/aditya-baniya-ai/Open_manipulator_x (branch `main`).
Built at the Ingram Hall Makerspace, Texas State University, funded by an Ingram Digital Twin Award.

---

## 1. What Robo is

Robo is an OpenMANIPULATOR-X robot arm driven by an NVIDIA Jetson Orin NX with ROS 2 Humble.
It greets people it sees, talks about robotics and the Makerspace with a local AI, plays
gestures and moves people build, picks objects up with a gripper camera, and runs three
arcade games controlled by hand tracking. One command (`launch/robo.sh`) starts all of it,
and `launch/autostart.sh on` makes it start after logging in.

## 2. What was built

| Area | What it does | Main files |
|---|---|---|
| Arm control | Gestures (wave, nod, shake, bow, look around), joint nudges, gripper, record and save your own moves by name, safety checks at start | `gestures/gestures.py` |
| Control panel | One Tkinter window (maroon and gold), three tabs: **Robo** (gestures, gripper, live camera with YOLO boxes, camera greeting, talking), **Build your own move** (step-by-step builder), **Games** | `gestures/gui.py` |
| Vision | YOLO11n (TensorRT) person and object detection on every frame, YOLO-World for any named object, a JPEG preview for the panel, slows to 25 fps while Robo talks | `perception/detect.py` |
| Greeting | Waves and says hello when a new person appears (cooldown, flicker filtering) | `gestures/greet.py` |
| Voice | Whisper (small, GPU) listens, Ollama `llama3.2:3b` answers (streamed sentence by sentence, answers remembered), Piper speaks; Robo only talks about robotics, simulation, Texas State and the Makerspace | `voice/robo_voice.py`, `voice/robo_knowledge.md` |
| Robot math | Inverse and forward kinematics in mm, straight-line moves, safety checks (joint limits, never below the table, safe paths through home) | `brain/arm.py` |
| Picking | Find an object with the gripper camera (YOLO-World), centre over it, grab, check, lift | `brain/pick.py` |
| Games | **Puppet Master** (whack lit targets), **Ball Carry** (carry 5 balls across, fastest time), **Chocolate Catcher** (a claw machine: 5 lives as popping hearts, 10 s carry timer, 2-minute game, basket set with Tab) | `game/*.py` |
| Hand tracking | MediaPipe hands (default) or YOLO pose; steady fist detection (fingertips vs palm, two thresholds, 2 frames) | `game/tracker.py` |
| Arm for games | Follows the hand gliding level, speed-limited (slower while carrying), grab / release / whack without freezing the screen, a pretend arm for testing anywhere | `game/arm_link.py` |
| Sound | Chiptune music and effects made in code, one mixer, a ticking timer that speeds up; silent if no speaker | `game/sound.py` |
| Launch | `robo.sh` (everything), `vision.sh` (camera + detection on/off), `game.sh` (one game), `autostart.sh` (on/off), `stop.sh` (stop everything) | `launch/` |

Accomplishments along the way: fixed base-servo jitter (gains), arm mounting, over-current
throttling (25 W mode), Piper crashes (onnxruntime 1.20.1), the camera feed freezing during
gestures, YOLO about 2x faster with TensorRT, Robo's first spoken words from 15.8 s to 6.6 s by
slowing YOLO while it talks, hand-tracking speed (MediaPipe 21.5 ms on the Jetson), and a USB-port conflict
between the autostart window and a second launch (now refused).

## 3. Hardware

| Part | Details |
|---|---|
| Arm | OpenMANIPULATOR-X, 5 DYNAMIXEL **XM430-W350-T** servos, 12 V, payload 500 g, reach 380 mm, repeatability < 0.2 mm |
| Servo IDs | 11 base (`joint1`), 12 shoulder (`joint2`), 13 elbow (`joint3`), 14 wrist (`joint4`), 15 gripper; TTL bus, 1 Mbps, Protocol 2.0 |
| Controller board | OpenCR 1.0 running ROBOTIS's **`usb_to_dxl`** firmware (uploaded from a Mac with the Arduino IDE), on **`/dev/ttyACM0`** |
| Computer | NVIDIA Jetson Orin NX 16GB, Ubuntu 22.04.5, JetPack 6 (L4T R36), Python 3.10 |
| Camera | Logitech BRIO: colour picture **`/dev/video0`** (`/dev/video2` is its infrared camera) |
| Microphone | the BRIO's: **`plughw:CARD=BRIO,DEV=0`** |
| Speaker | USB "USB PnP Audio Device": **`plughw:CARD=Device,DEV=0`**, volume control `Speaker` |

Use sound card **names**, never numbers (the numbers change when USB audio is plugged in).
Wiring, mounting direction and slumping: [docs/hardware.md](hardware.md).

## 4. How the Jetson is configured (shared by every project on it)

Everything below is already done on this Jetson. A new project reuses it as is.
On a new Jetson, follow README Part 1 (Steps 1 to 14).

| What | Setting / location |
|---|---|
| ROS 2 | Humble (`ros-humble-desktop`, `ros-dev-tools`, ros2-control, ros2-controllers, gripper-controllers, MoveIt, usb-cam, rqt-image-view, v4l-utils) |
| ROBOTIS software | `~/colcon_ws` (from `dependencies.repos`), built with `colcon build --symlink-install` |
| Base servo gains | P 400 / I 0 / D 0 for ID 11 only, in `~/colcon_ws/src/open_manipulator/open_manipulator_x_description/ros2_control/open_manipulator_x_system.ros2_control.xacro` (backup: `~/omx_ros2_control_backup.xacro`). Redo after any `vcs import`. |
| Terminal | `~/.bashrc` sources `/opt/ros/humble/setup.bash` and `~/colcon_ws/install/setup.bash`, and adds `~/.local/bin` to `PATH` |
| USB | user in the `dialout` group; ROBOTIS udev rules (`ros2 run open_manipulator_x_bringup create_udev_rules`) |
| Power | `sudo nvpmodel -m 3` (25 W, all 8 cores; MAXN throttles from over-current, 10/15 W crashes Piper). `sudo jetson_clocks` for full speed until the next reboot. |
| PyTorch | Jetson wheels: torch 2.10.0, torchvision 0.25.0 (ultralytics assets), plus cuDSS 0.7.1 |
| Pins that matter | **NumPy < 2** (ROS 2 Humble), **opencv-python < 4.12**, **onnxruntime 1.20.1** (Piper), scipy < 1.15, coverage >= 7.2 |
| YOLO | `ultralytics` + CLIP; models in `~`: `yolo11n.pt`, **`~/yolo11n.engine`** (TensorRT, 640), **`~/yolo11n-pose.engine`** (TensorRT, 320), `yolov8s-worldv2.pt` |
| Whisper | `openai-whisper`, model `small` on the GPU, ffmpeg |
| Piper | `piper-tts`, voice `~/piper_voices/en_US-lessac-medium.onnx` |
| LLM | Ollama (service starts at boot), model `llama3.2:3b`, kept loaded (`keep_alive: -1`) |
| Games | MediaPipe 0.10.18 in its own environment **`~/game_venv`** (system site packages + a `.pth` to the user site; protobuf 4.25.9 only inside it) |
| Claude Code | install with `curl -fsSL https://claude.ai/install.sh \| bash`; log in over SSH from the Mac (the login link opens there) |
| Remote access | `ssh jetson@<address>` (`hostname -I` on the Jetson) |

Measured on this Jetson: YOLO11n 12.8 ms (TensorRT) vs 26.9 ms (`.pt`); YOLO pose 11 ms
(TensorRT, 320); MediaPipe hands 21.5 ms (after `jetson_clocks`); LLM 11.5 tokens/s alone,
3.3 with YOLO at full speed; voice answer: heard 1.9 s, first words 6.6 s.

## 5. The robot, for any program that moves it

### Coordinates (as `brain/arm.py` uses them)
- **x forward** from the base, **y to the left**, **z up from the table**, in **mm**.
- The base turns around **x = 12 mm**; the shoulder joint is **76.5 mm** above the table.
- Links: shoulder to elbow (24, 128) mm, elbow to wrist 124 mm, wrist to fingertips 126 mm.
- `MOUNT_HEIGHT` in `brain/arm.py`: the thickness of a plate under the base, if any (0 now).
- Joint angles: 0 = upright home pose; for shoulder, elbow and wrist **positive = forward / down**; for the base positive = toward Robo's left.

### Joint limits
| Joint | ROBOTIS (URDF) | Used in this repo |
|---|---|---|
| Base (joint1) | −π to +π (±180°) | ±2.8 rad (±160°) |
| Shoulder (joint2) | −1.5 to +1.5 rad | same |
| Elbow (joint3) | −1.5 to +1.4 rad | same |
| Wrist (joint4) | −1.7 to +1.97 rad | −1.7 to +1.9 |
| Gripper (each finger) | −0.010 (closed) to +0.019 m (open); stroke 20–75 mm | open 0.019, close −0.01 |

These only protect each motor's own end. **They don't know about the table**: `brain/arm.py`
also keeps the fingertips and wrist at least 10 mm above it and checks whole paths.

### Reach (fingertips pointing straight down)
| Height | Reach from the base axis |
|---|---|
| 15–60 mm | about 60–227 mm, at every angle up to ±85° |
| 100 mm | up to about 187 mm |
| 110 mm | up to about 169 mm straight down; up to 246 mm if the gripper may tilt 20° |
| 120 mm and up | straight down barely works; needs a tilt |

### Speeds
Servo maximum about 4.8 rad/s (46 RPM). This repo: games 1.5 rad/s and 250 mm/s
(0.8 rad/s and 90 mm/s while carrying); `arm.py` moves 0.6 rad/s; straight lines 50 mm/s.
Safe to raise gradually up to about 3.0 rad/s; above that the arm overshoots, shakes and
draws a lot of current.

### ROS 2 interfaces (from `hardware.launch.py port_name:=/dev/ttyACM0`)
| Interface | Type | Use |
|---|---|---|
| `/joint_states` | `sensor_msgs/JointState` | angles of joint1-4 and `gripper_left_joint` |
| `/arm_controller/follow_joint_trajectory` | action `FollowJointTrajectory` | whole moves (wait for the result) |
| `/arm_controller/joint_trajectory` | topic `JointTrajectory` | quick streamed updates (following a hand) |
| `/gripper_controller/gripper_cmd` | action `GripperCommand` | open 0.019 / close −0.01, max effort 100 |
| `/image_raw` | `sensor_msgs/Image` | camera (from `usb_cam`) |
| `/person_detected`, `/detections`, `/detections/image/compressed` | `Bool`, `String`, JPEG | from `detect.py` |
| `/robo_busy` | `Bool` | the panel tells `detect.py` to slow down |

Simulation without the arm (RViz):
`ros2 launch open_manipulator_x_bringup base.launch.py use_sim:=false use_fake_hardware:=true fake_sensor_commands:=true start_rviz:=true`

### Safety rules that every program here follows
- **Only one arm program at a time.** Two fight over the USB port (the second hangs at "Init Dxl Comm Port" / "Waiting for the arm") or make the arm shake. Check with `pgrep -f "open_manipulator_x_bringup|ros2_control_node"` and stop with `launch/stop.sh`.
- **Check the joint angles before moving** (`connect()` in `gestures/gestures.py`): when the 12 V is off the arm slumps past its limits. Hold it upright while turning the power on.
- **Hold the real arm** when stopping: it goes limp.
- **Only one program can use the camera** (`usb_cam`, `detect.py` or a game).
- Test new moves in the simulation first.

## 6. Running a second project on the same Jetson and arm

1. **Turn autostart off** while working on the other project: `~/Documents/Open_manipulator_x/launch/autostart.sh off` (otherwise Robo takes the arm and the camera at login).
2. **Stop Robo** before starting the other project: `~/Documents/Open_manipulator_x/launch/stop.sh`. Its pattern doesn't know the new project's programs, so give the new repo its own stop script.
3. **Share, don't change**: ROS 2, `~/colcon_ws` (with the base gains), the Python packages and their pins, Ollama, the models in `~`, `~/game_venv`. Install new Python packages with the same pins (`"numpy<2"`), or in a separate environment like `~/game_venv`, so Robo keeps working.
4. **Don't re-run `vcs import`** into `~/colcon_ws`, or the base gains need redoing (README Step 5b).
5. Per-robot files that stay in this repo and aren't shared: `gestures/my_gestures.json`, `brain/camera.json`, `game/claw_setup.json`, the game leaderboards.
6. Reuse by copying, not by importing across repos: `brain/arm.py` (kinematics and safe moves), `game/arm_link.py` (following, grab and release without freezing, pretend arm), `game/tracker.py`, `game/sound.py`, `launch/vision.sh` and the `robo.sh` patterns (process groups, refusing a second arm), `connect()` from `gestures/gestures.py`.

## 7. Notes for a chess-playing robot

- **The board must be small.** With every square reachable straight down (grabbing at 20 mm, travelling at 90 mm) and the near edge at least 70 mm from the base axis, the largest board has **23 mm squares (184 mm board)**, placed from x = 70 mm in front of the base, centred left to right. 21 mm squares if the near edge is 80 mm away.
- **The gripper can't close below about 20 mm** (stroke 20–75 mm), and pieces on 23 mm squares are about 15–18 mm wide. Options: stick foam or rubber pads on the fingers (also helps small objects stop the fingers, so "holding" can be detected), use custom pieces with a wider grip part (a 20–22 mm cylinder or knob on top), or both. Try this first, before anything else.
- **Captured pieces** need a drop zone that is also reachable (beside the board, within about 200 mm of the base).
- **Seeing the board**: an overhead camera (the BRIO on a stand looking down at the board) and a 4-corner calibration (pixels to board squares, like the basket and Tab idea). Detect moves by comparing the board before and after the human's move (which squares changed), which is more reliable than recognising every piece.
- **The chess brain**: Stockfish (`sudo apt install stockfish`) with the `python-chess` package (moves, rules, and talking to Stockfish).
- **Moves**: for each robot move, hover above the "from" square, go straight down, grab, go up, hover above the "to" square, go down, release, up (the `arm.py` straight-line moves). Capture = remove the captured piece first.
- **Height**: travel high enough to clear the tallest piece (king) while carrying a piece, about 90–110 mm, with a little tilt where needed.
- **Nice extras that reuse this repo**: Robo's voice to announce moves, sounds for check and checkmate, hand gestures to resign or offer a draw.
