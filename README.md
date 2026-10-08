# OpenMANIPULATOR-X Greeter Robot

A table robot built from a ROBOTIS OpenMANIPULATOR-X arm and an NVIDIA Jetson Orin NX 16GB running ROS 2 Humble. The goal: it sees people with a camera, greets them with gestures and voice, listens to commands, and picks up small objects like a pencil.

> Demo video / GIF goes here.

## Status

| Part | State |
|---|---|
| Arm test and greeting on the OpenCR (Arduino) | ✅ working |
| ROS 2 Humble on the Jetson | ✅ installed |
| Arm controlled through ROS 2 | ✅ working |
| Keyboard control of each joint | ✅ working |
| Wave gesture in ROS 2 | ✅ working |
| More gestures (nod, shake, bow, look around) on key press | ✅ working |
| Record your own moves in simulation, play them on the real arm | ✅ working |
| Button window (gestures, joints, gripper, recording) | ✅ working |
| Gripper open / close | ✅ working |
| Real arm shown live in RViz (`--rviz`) | ✅ working |
| Start and stop the arm and controls with one command | ✅ working |
| Camera picture in ROS 2 (Logitech BRIO) | ✅ working |
| YOLO + YOLO-World on the Jetson GPU | ✅ installed, tested on a photo |
| Live object detection from the camera (YOLO / YOLO-World) | ✅ working |
| Wave automatically when a person appears (one command) | ✅ working |
| Microphone (BRIO) + speech to text (Whisper on the GPU) | ✅ working |
| Voice commands ("wave", "bow", ...) | 🚧 written, not tested yet |
| Local LLM (Ollama) | 🚧 installing |
| Voice replies (needs a speaker), picking | ⏳ planned |

## What you need

- OpenMANIPULATOR-X arm with an OpenCR 1.0 board and its 12 V 5 A power adapter
- Micro USB data cable
- NVIDIA Jetson Orin NX 16GB with Ubuntu 22.04 (JetPack 6). An Orin Nano should also work, with smaller AI models.
- A Mac or PC with the Arduino IDE (only for uploading firmware to the OpenCR)

Wiring and servo IDs: [docs/hardware.md](docs/hardware.md).

---

## Part 1: One-time setup

You only do this once. Everything stays set up after a reboot.

### Step 1. Upload the firmware to the OpenCR (on a Mac or PC)

The Arduino IDE can't upload to the OpenCR from the Jetson, so use a Mac or PC.

1. Install the Arduino IDE from arduino.cc.
2. Arduino IDE > Settings > Additional boards manager URLs, paste:
   `https://raw.githubusercontent.com/ROBOTIS-GIT/OpenCR/master/arduino/opencr_release/package_opencr_index.json`
3. Tools > Board > Boards Manager: install **OpenCR**.
4. Plug in the OpenCR and turn on its 12 V power. Select Tools > Board > OpenCR > OpenCR Board, and Tools > Port > the `usbmodem` port.
5. Open File > Examples > OpenCR > 10.Etc > **usb_to_dxl**, and click Upload.

A good upload ends with `[OK] Download`. The arm won't move after this, which is expected: it now waits for commands from the Jetson. If the upload freezes, hold **SW2**, press **RESET**, release SW2, and upload again.

Optional: to test the arm without ROS first, see [firmware/README.md](firmware/README.md).

### Step 2. Install ROS 2 Humble (on the Jetson)

```bash
sudo apt install -y software-properties-common curl
sudo add-apt-repository -y universe
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list
sudo apt update
sudo apt install -y ros-humble-desktop ros-dev-tools
```

### Step 3. Download this repo

```bash
mkdir -p ~/Documents
cd ~/Documents
git clone https://github.com/aditya-baniya-ai/Open_manipulator_x.git
```

### Step 4. Allow your user to use the USB port

```bash
sudo usermod -aG dialout $USER
```

**Log out and log back in** (or reboot). Then check:

```bash
groups
```

The list should include `dialout`.

### Step 5. Install and build the ROBOTIS arm software

```bash
sudo apt install -y ros-humble-ros2-control ros-humble-ros2-controllers ros-humble-moveit ros-humble-gripper-controllers
```

```bash
mkdir -p ~/colcon_ws/src
vcs import ~/colcon_ws/src < ~/Documents/Open_manipulator_x/dependencies.repos
```

```bash
cd ~/colcon_ws
sudo rosdep init
rosdep update
rosdep install --from-paths src --ignore-src -y -r --skip-keys "gazebo_ros gazebo_ros_pkgs gazebo_ros2_control gazebo_plugins"
```

(If `sudo rosdep init` says it's already initialized, that's fine.)

```bash
cd ~/colcon_ws
colcon build --symlink-install
```

This takes a few minutes. It should end with `Summary: 12 packages finished`. Warnings are fine. If it freezes, press Ctrl+C and run `colcon build --symlink-install --parallel-workers 1`.

### Step 6. Set up the terminal and USB rules

Make every new terminal load ROS 2 and the arm software:

```bash
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
echo "source ~/colcon_ws/install/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

Install the USB rules for the OpenCR (asks for your password):

```bash
ros2 run open_manipulator_x_bringup create_udev_rules
```

### Step 7. Check the OpenCR is connected

Plug the OpenCR's USB into the Jetson (unplug and replug it if it was already in), turn on the 12 V power, then:

```bash
ls /dev/ttyACM*
```

It should print `/dev/ttyACM0`.

### Step 8. Install the camera software

Plug the Logitech BRIO camera into the Jetson, then:

```bash
sudo apt install -y v4l-utils ros-humble-usb-cam ros-humble-rqt-image-view
```

Check the camera is found:

```bash
v4l2-ctl --list-devices
```

It should list `Logitech BRIO` with `/dev/video0` first. That's the color picture (`/dev/video2` is its infrared camera).

### Step 9. Install YOLO and YOLO-World (object detection)

YOLO needs PyTorch built for the Jetson's GPU. A normal `pip install torch` won't use the GPU. These packages are for **JetPack 6** with Python 3.10; check yours with `cat /etc/nv_tegra_release` (R36 = JetPack 6).

```bash
sudo apt update && sudo apt install -y python3-pip && pip3 install -U pip
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc
```

PyTorch and torchvision for the Jetson:

```bash
pip3 install https://github.com/ultralytics/assets/releases/download/v0.0.0/torch-2.10.0-cp310-cp310-linux_aarch64.whl
pip3 install https://github.com/ultralytics/assets/releases/download/v0.0.0/torchvision-0.25.0-cp310-cp310-linux_aarch64.whl
```

cuDSS, a library this PyTorch needs (without it, `import torch` fails with `libcudss.so.0`):

```bash
cd ~ && wget https://developer.download.nvidia.com/compute/cudss/0.7.1/local_installers/cudss-local-tegra-repo-ubuntu2204-0.7.1_0.7.1-1_arm64.deb
sudo dpkg -i cudss-local-tegra-repo-ubuntu2204-0.7.1_0.7.1-1_arm64.deb
sudo cp /var/cudss-local-tegra-repo-ubuntu2204-0.7.1/cudss-*-keyring.gpg /usr/share/keyrings/
sudo apt-get update && sudo apt-get -y install cudss
```

YOLO, plus CLIP for YOLO-World. Keep the version limits: ROS 2 Humble needs NumPy 1.x, and newer OpenCV would pull in NumPy 2.

```bash
pip3 install ultralytics "numpy<2" "opencv-python<4.12"
pip3 install git+https://github.com/ultralytics/CLIP.git
```

Check it all works. It should print `2.10.0 True` and a NumPy version starting with `1.`:

```bash
python3 -c "import ultralytics, torch, numpy; print(ultralytics.__version__, torch.__version__, torch.cuda.is_available(), numpy.__version__)"
```

### Step 10. Install Whisper (speech to text)

The robot listens with the Logitech BRIO's built-in microphone (ALSA card 2). Check it's found:

```bash
arecord -l
```

It should list `card 2: BRIO`. Install Whisper and ffmpeg. The newer `coverage` and `scipy` replace old Ubuntu copies that clash with Whisper (see [troubleshooting](docs/troubleshooting.md#whisper-module-coverage-has-no-attribute-types)):

```bash
sudo apt install -y ffmpeg
pip3 install openai-whisper "numpy<2"
pip3 install -U "coverage>=7.2" "scipy<1.15" "numpy<2"
```

Test it: record 5 seconds while you speak, then turn it into text (the first run downloads the model, about 140 MB):

```bash
arecord -D plughw:2,0 -f S16_LE -r 16000 -c 1 -d 5 ~/mic_test.wav
```

```bash
python3 -c "
import whisper
m = whisper.load_model('base', device='cuda')
print('Heard:', m.transcribe('$HOME/mic_test.wav', fp16=True)['text'])
"
```

Setup is done.

---

## Part 2: Running the robot

Do this every time you want to use the robot. You'll use 2 or 3 terminal windows. Open a new one with **Ctrl+Shift+T**.

### Start the arm (Terminal 1)

1. Turn on the arm's 12 V power and make sure the OpenCR's USB is plugged into the Jetson.
2. Keep your hands clear and the power switch within reach, then run:

```bash
ros2 launch open_manipulator_x_bringup hardware.launch.py port_name:=/dev/ttyACM0
```

Leave this running. The arm won't move yet, but its joints will hold position. When you see `Configured and activated arm_controller`, it's ready.

### Option A: Gestures (one command, starts the arm too)

Instead of Terminal 1 above, this starts the arm in the background and the gesture menu in the same terminal:

```bash
~/Documents/Open_manipulator_x/launch/gestures.sh
```

(If the arm is already running in Terminal 1, just run `python3 ~/Documents/Open_manipulator_x/gestures/gestures.py` instead.)

Press a key (no Enter needed):

| Key | Does |
|---|---|
| `w` | wave |
| `n` | nod (yes) |
| `s` | shake (no) |
| `b` | bow |
| `l` | look around |
| `h` | go to the home pose |
| `1` / `2` | turn the base |
| `3` / `4` | move the shoulder |
| `5` / `6` | move the elbow |
| `7` / `8` | tilt the wrist |
| `o` / `c` | open / close the gripper |
| `p` `k` `x` | record your own move (see [Make your own gesture](#make-your-own-gesture)) |
| `q` | quit (also stops the arm if `gestures.sh` started it) |

Hold a number key to keep a joint moving. Moves you've saved yourself also show up in the menu, with the key you gave them.

### Option A2: The same controls as buttons in a window

Everything above (gestures, joints, gripper, recording) as buttons, so you don't need the keyboard. The first time, install Tkinter (Python's window toolkit):

```bash
sudo apt install -y python3-tk
```

Then start the arm and the window together:

```bash
~/Documents/Open_manipulator_x/launch/gestures.sh --gui
```

Add `--sim` to use the simulated arm (`gestures.sh --sim --gui`), or `--rviz` to also see the real arm move live in RViz (`gestures.sh --rviz --gui`). Hold a joint's `-` / `+` button to keep it moving; its live angle is shown next to the buttons. The window stops responding while a gesture plays, so gestures can't overlap. The Quit button also stops the arm.

### Option B: Move each joint with the keyboard (Terminals 2 and 3)

Terminal 2:

```bash
ros2 launch open_manipulator_x_moveit_config servo.launch.py
```

Terminal 3:

```bash
ros2 run open_manipulator_x_teleop open_manipulator_x_teleop
```

| Keys | Moves |
|---|---|
| `1` / `q` | joint 1 (base) |
| `2` / `w` | joint 2 (shoulder) |
| `3` / `e` | joint 3 (elbow) |
| `4` / `r` | joint 4 (wrist) |
| `o` / `p` | open / close the gripper |
| `ESC` | quit |

### Camera

Start the camera (its own terminal, leave it running):

```bash
ros2 run usb_cam usb_cam_node_exe --ros-args -p video_device:=/dev/video0 -p image_width:=640 -p image_height:=480 -p pixel_format:=mjpeg2rgb -p framerate:=30.0
```

See the picture (another terminal), then pick `/image_raw` from the dropdown at the top left:

```bash
ros2 run rqt_image_view rqt_image_view
```

### Detect objects (camera must be running)

Regular YOLO, which knows 80 everyday objects (person, cup, bottle, phone, ...):

```bash
python3 ~/Documents/Open_manipulator_x/perception/detect.py
```

YOLO-World, which looks only for the words you give it, including objects regular YOLO doesn't know:

```bash
python3 ~/Documents/Open_manipulator_x/perception/detect.py --find pencil cup
```

A window shows boxes around what it finds; press `q` in the window to quit. Other options: `--conf 0.6` reports only things it's more sure about (default 0.4), and `--no-window` runs without the video window.

It also publishes what it sees, for other programs (like the robot's greeting) to use. To watch it:

```bash
ros2 topic echo /person_detected
```

```bash
ros2 topic echo /detections
```

### Greet people automatically (one command)

The robot waves when someone appears in front of the camera. One command starts everything: the arm, the camera, detection and the greeter.

Turn on the arm's 12 V power, clear the space around it, then:

```bash
ros2 launch ~/Documents/Open_manipulator_x/launch/greeter.launch.py
```

To try it in the simulation instead of the real arm:

```bash
ros2 launch ~/Documents/Open_manipulator_x/launch/greeter.launch.py sim:=true
```

**To stop:** hold the arm, then press Ctrl+C once. Everything stops and the arm goes limp.

A person has to be in view for 1 second before it greets. It greets each person once: it won't greet again until 30 seconds have passed and nobody has been in view for 3 seconds.

Options (add them to the end of the command, like `sim:=true` above):

| Option | What it does |
|---|---|
| `sim:=true` | use the simulated arm in RViz |
| `gesture:=b` | greet with another gesture key, including moves you saved yourself (default `w`, wave) |
| `cooldown:=60` | seconds between greetings (default 30) |
| `window:=false` | don't open the detection video window |
| `camera:=/dev/video0` | which camera to use |

To run the parts separately instead (for example to see each one's messages on its own), start the arm and camera as above, then `python3 ~/Documents/Open_manipulator_x/perception/detect.py` and `python3 ~/Documents/Open_manipulator_x/gestures/greet.py`, each in its own terminal. `greet.py` also takes `--see-time 2` (how long someone must be in view first).

### Voice commands

Say a gesture's name and the arm does it. It listens with the BRIO's microphone and uses Whisper to turn speech into text.

First test the listening alone, without the arm. Stay quiet for the first second while it measures the room's noise, then speak:

```bash
python3 ~/Documents/Open_manipulator_x/voice/listen.py --test
```

It prints `Heard: ...` for each sentence, and `-> wave` (etc.) when it recognises a command. Then start the arm (or the simulation) and run it without `--test`:

```bash
python3 ~/Documents/Open_manipulator_x/voice/listen.py
```

| Say | Gesture |
|---|---|
| "wave", "hello", "hi" | wave |
| "nod" | nod |
| "shake" | shake |
| "bow" | bow |
| "look around" | look around |
| "go home", "rest" | home |
| the name of a move you saved | that move |

Options:

| Option | What it does |
|---|---|
| `--wake robot` | only act on sentences that contain "robot" (fewer accidental moves) |
| `--threshold 800` | how loud speech must be to count; raise it in a noisy room |
| `--model small` | more accurate Whisper model, but slower (`tiny`, `base`, `small`) |

What it heard is published on `/voice_text`.

### Check the joint angles (any terminal)

```bash
ros2 topic echo /joint_states --once
```

### Stop the robot

1. Quit the gestures (`q`) or teleop (`ESC`), and press Ctrl+C in any other terminals except Terminal 1. If you started with `gestures.sh`, hold the arm before pressing `q`: that stops the arm too.
2. **Hold the arm**, then press Ctrl+C in Terminal 1. The arm goes limp.
3. Turn off the 12 V power.

### Simulation (no arm needed)

A virtual arm in RViz (the 3D viewer) that uses the same controller as the real one, so everything works on it unchanged. Use it to try new moves safely. Don't run it at the same time as the real arm.

Simulated arm + gesture menu, in one command:

```bash
~/Documents/Open_manipulator_x/launch/gestures.sh --sim
```

You can't run the simulated and the real arm at the same time (they'd fight over the same controller names). But you can watch the **real** arm in RViz: the 3D model follows the real servo angles live.

```bash
~/Documents/Open_manipulator_x/launch/gestures.sh --rviz
```

(Or without the controls: `ros2 launch open_manipulator_x_bringup hardware.launch.py port_name:=/dev/ttyACM0 start_rviz:=true`.)

Or just the simulated arm, to use with the other programs:

```bash
ros2 launch open_manipulator_x_bringup base.launch.py use_sim:=false use_fake_hardware:=true fake_sensor_commands:=true start_rviz:=true
```

(ROBOTIS's own `fake.launch.py` refuses to run on the Jetson; see [troubleshooting](docs/troubleshooting.md#fakelaunchpy-says-can-not-launch-fake-robot-in-raspberry-pi).)

### Make your own gesture

Pose the arm, save each pose, then replay them. Do this in the simulation first. Everything happens in one terminal:

1. Start the simulated arm and the gesture menu:
   ```bash
   ~/Documents/Open_manipulator_x/launch/gestures.sh --sim
   ```
2. Press `h` to go home.
3. Move the arm with the number keys (`1`–`8`), then press `p` to add that pose. Repeat for each pose in your move.
4. Press `k` to keep (save) the move. It asks two things; type each and press Enter:
   ```
   Name for this move: hello dance
   Key to play it (one letter): m
   Saved 'hello dance'. Press m to play it.
   ```
5. Press your key, and watch it in RViz. When it looks right, press `q`, start the real arm with `~/Documents/Open_manipulator_x/launch/gestures.sh`, and press your key.

**Recording on the real arm, watching it in RViz too:** start with `~/Documents/Open_manipulator_x/launch/gestures.sh --rviz --gui` (12 V on, space around the arm clear). The real arm moves and RViz shows it live; record the same way. Keep poses away from the table and the arm's own base, and remember each pose takes 1 second to reach, so poses far apart make fast swings.

Prefer buttons? Start with `gestures.sh --sim --gui` instead: move the joints with `-` / `+`, click **Add pose** for each pose, then type a name and a letter and click **Save move**. Your move appears as a new button.

| Key | While recording |
|---|---|
| `p` | add the current pose |
| `k` | keep (save) the move, with a name and a key |
| `x` | throw away the poses so far and start over |

Saved moves go in `gestures/my_gestures.json` and load every time `gestures.py` starts. Each pose there is one line: (base turn, shoulder, elbow, wrist, seconds to get there), in radians. To make a step faster or slower, change its last number. To delete a move, remove it from that file.

### Get the latest code

```bash
cd ~/Documents/Open_manipulator_x
git pull
```

---

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

Keyboard teleop adds one more layer: MoveIt Servo (`servo.launch.py`) turns key presses into small, continuous joint moves.

## What's in this repo

```
README.md              this guide
docs/
  hardware.md          parts list, servo IDs, wiring
  setup_jetson.md      setup notes: why each step is needed, and progress
  troubleshooting.md   problems we hit and how we fixed them
  OpenMANIPULATOR-X_Quick_Setup.docx   one-page guide for the Arduino test
firmware/
  README.md            how to upload code to the OpenCR board
  servo_check/         Arduino test: stands the arm up and waves
gestures/
  gestures.py          press a key to wave, nod, shake, bow or look around,
                       or record and save your own moves (my_gestures.json)
  greet.py             waves automatically when the camera sees a person
  gui.py               the same controls as gestures.py, as buttons in a window
perception/
  detect.py            live object detection from the camera (YOLO / YOLO-World)
voice/
  listen.py            voice commands: say "wave", "bow", ... and the arm does it
launch/
  greeter.launch.py    starts the whole greeter robot with one command
  gestures.sh          starts the arm (real or --sim) and the controls (keys, or --gui) together
dependencies.repos     list of ROBOTIS code to download (used in Step 5)
```

## Problems?

See [docs/troubleshooting.md](docs/troubleshooting.md).
