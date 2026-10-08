# OpenMANIPULATOR-X Greeter Robot

A table robot built from a ROBOTIS OpenMANIPULATOR-X arm and an NVIDIA Jetson Orin Nano running ROS 2 Humble. The goal: it sees people with a camera, greets them with gestures and voice, listens to commands, and picks up small objects like a pencil.

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
| Camera, voice, picking | ⏳ planned |

## What you need

- OpenMANIPULATOR-X arm with an OpenCR 1.0 board and its 12 V 5 A power adapter
- Micro USB data cable
- NVIDIA Jetson Orin Nano with Ubuntu 22.04
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

It should print `/dev/ttyACM0`. Setup is done.

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

### Option A: Gestures (Terminal 2)

```bash
python3 ~/Documents/Open_manipulator_x/gestures/gestures.py
```

Press a key (no Enter needed):

| Key | Gesture |
|---|---|
| `w` | wave |
| `n` | nod (yes) |
| `s` | shake (no) |
| `b` | bow |
| `l` | look around |
| `h` | go to the home pose |
| `q` | quit |

Moves you've saved yourself also show up in the menu, with the key you gave them. To record one, see [Make your own gesture](#make-your-own-gesture).

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

### Check the joint angles (any terminal)

```bash
ros2 topic echo /joint_states --once
```

### Stop the robot

1. Quit the gestures (`q`) or teleop (`ESC`), and press Ctrl+C in any other terminals except Terminal 1.
2. **Hold the arm**, then press Ctrl+C in Terminal 1. The arm goes limp.
3. Turn off the 12 V power.

### Simulation (no arm needed)

A virtual arm in RViz (the 3D viewer) that uses the same controller as the real one, so `gestures.py` works on it unchanged. Use it to try new moves safely. Don't run it at the same time as the real-arm launch.

Terminal 1:

```bash
ros2 launch open_manipulator_x_bringup base.launch.py use_sim:=false use_fake_hardware:=true fake_sensor_commands:=true start_rviz:=true
```

Terminal 2:

```bash
python3 ~/Documents/Open_manipulator_x/gestures/gestures.py
```

(ROBOTIS's own `fake.launch.py` refuses to run on the Jetson; see [troubleshooting](docs/troubleshooting.md#fakelaunchpy-says-can-not-launch-fake-robot-in-raspberry-pi).)

### Make your own gesture

Pose the arm, save each pose, then replay them. Do this in the simulation first.

1. Start the simulation (Terminal 1, above).
2. Terminal 2, keyboard control:
   ```bash
   ros2 launch open_manipulator_x_moveit_config servo.launch.py
   ```
3. Terminal 3:
   ```bash
   ros2 run open_manipulator_x_teleop open_manipulator_x_teleop
   ```
4. Terminal 4:
   ```bash
   python3 ~/Documents/Open_manipulator_x/gestures/gestures.py
   ```
5. Press `h` in Terminal 4 to go home.
6. Move the arm with the keys in Terminal 3, then press `p` in Terminal 4 to add that pose. Repeat for each pose in your move.
7. Press `k` in Terminal 4 to keep (save) the move. It asks two things; type each and press Enter:
   ```
   Name for this move: hello dance
   Key to play it (one letter): m
   Saved 'hello dance'. Press m to play it.
   ```
8. Press your key, and watch it in RViz. When it looks right, try it on the real arm.

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
dependencies.repos     list of ROBOTIS code to download (used in Step 5)
```

## Problems?

See [docs/troubleshooting.md](docs/troubleshooting.md).
