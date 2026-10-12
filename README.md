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
| USB speaker | ✅ working |
| Text to speech (Piper) | ✅ working |
| Local LLM (Ollama, llama3.2:3b on the GPU) | ✅ working |
| Talk with Robo (Whisper + LLM + Piper + gestures) | 🚧 talking works (--test); with the arm not tested yet |
| Everything in one command + control panel with voice (`launch/robo.sh`) | 🚧 written, not tested yet |
| Robot says hello while it greets, picking | ⏳ planned |

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

### Step 5b. Calm the base servo (stops it jittering)

With ROBOTIS's default settings, the base jitters about ±0.3° when the arm holds a pose with the forearm sticking out (like Home). These commands give **only the base servo** gentler settings (P 400, I 0, D 0 instead of 800 / 100 / 100). They're sent to the servo at every launch and aren't stored in it permanently. First keep a backup:

```bash
cp ~/colcon_ws/src/open_manipulator/open_manipulator_x_description/ros2_control/open_manipulator_x_system.ros2_control.xacro ~/omx_ros2_control_backup.xacro
```

```bash
sed -i '/<gpio name="dxl1">/,/<\/gpio>/ { s|"Position P Gain">800<|"Position P Gain">400<|; s|"Position I Gain">100<|"Position I Gain">0<|; s|"Position D Gain">100<|"Position D Gain">0<|; }' ~/colcon_ws/src/open_manipulator/open_manipulator_x_description/ros2_control/open_manipulator_x_system.ros2_control.xacro
```

Check: this should show P 400, I 0 and D 0:

```bash
sed -n '/<gpio name="dxl1">/,/<\/gpio>/p' ~/colcon_ws/src/open_manipulator/open_manipulator_x_description/ros2_control/open_manipulator_x_system.ros2_control.xacro | grep "Gain"
```

Then rebuild that package (a WARNING about "underlay workspaces" is harmless):

```bash
cd ~/colcon_ws && colcon build --symlink-install --packages-select open_manipulator_x_description
```

To undo: copy the backup back (`cp ~/omx_ros2_control_backup.xacro ~/colcon_ws/src/open_manipulator/open_manipulator_x_description/ros2_control/open_manipulator_x_system.ros2_control.xacro`) and rebuild the same way. If you ever re-download the ROBOTIS code (`vcs import` again), repeat this step.

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

The robot listens with the Logitech BRIO's built-in microphone. Check it's found:

```bash
arecord -l
```

It should list a card called `BRIO` (its number can change when other USB audio devices are plugged in, so the scripts find it by name). Install Whisper and ffmpeg. The newer `coverage` and `scipy` replace old Ubuntu copies that clash with Whisper (see [troubleshooting](docs/troubleshooting.md#whisper-module-coverage-has-no-attribute-types)):

```bash
sudo apt install -y ffmpeg
pip3 install openai-whisper "numpy<2"
pip3 install -U "coverage>=7.2" "scipy<1.15" "numpy<2"
```

Test it: record 5 seconds while you speak, then turn it into text (the first run downloads the model, about 140 MB):

```bash
arecord -D plughw:CARD=BRIO,DEV=0 -f S16_LE -r 16000 -c 1 -d 5 ~/mic_test.wav
```

```bash
python3 -c "
import whisper
m = whisper.load_model('base', device='cuda')
print('Heard:', m.transcribe('$HOME/mic_test.wav', fp16=True)['text'])
"
```


### Step 11. Set up the speaker

Plug a USB speaker into the Jetson. Check it's found (ours is listed as `USB PnP Audio Device`, card name `Device`):

```bash
aplay -l
```

Turn its volume up to 100% and save the setting so it survives a reboot:

```bash
amixer -c Device set Speaker 100% unmute
sudo alsactl store
```

(If your speaker has a different name, use it instead of `Device`; `amixer -c Device scontrols` lists the volume controls.) Test it, you should hear "Front Left", "Front Right":

```bash
speaker-test -D plughw:CARD=Device,DEV=0 -c 2 -t wav -l 1
```


### Step 12. Install Piper (text to speech)

Piper turns text into a spoken voice, running entirely on the Jetson. First, put the Jetson in its **25W** power mode: in the lower modes (10W, 15W) some CPU cores are switched off, and Piper's voice engine (onnxruntime) crashes trying to use them. 25W keeps all 8 cores on with a power budget (MAXN has no budget, so running everything at once triggers "System throttled due to over-current"). Check which cores are on:

```bash
cat /sys/devices/system/cpu/online
```

If it shows `0-3` instead of `0-7`, switch to mode 3 (25W) and say `yes` to the reboot (note the old mode from `sudo nvpmodel -q` if you want to switch back later). On other Jetsons the 25W mode may have a different number: `grep POWER_MODEL /etc/nvpmodel.conf` lists them.

```bash
sudo nvpmodel -m 3
```

Install Piper, with an onnxruntime version that doesn't have the Jetson Orin "Unknown CPU vendor" bug:

```bash
pip3 install piper-tts "onnxruntime==1.20.1" "numpy<2"
```

Download an English voice (about 60 MB):

```bash
mkdir -p ~/piper_voices && cd ~/piper_voices && python3 -m piper.download_voices en_US-lessac-medium
```

Test it:

```bash
python3 -m piper -m ~/piper_voices/en_US-lessac-medium.onnx -f ~/hello.wav -- 'Hello! I am your robot arm. Nice to meet you.'
aplay -D plughw:CARD=Device,DEV=0 ~/hello.wav
```

Setup is done.

---

## Part 2: Running the robot

### Everything at once (recommended)

One command starts the whole robot: the arm, the camera, person/object detection, and **Robo's control panel**, with everything built so far: gestures, building your own moves, talking with Robo, the camera greeting, and the three games. Turn on the arm's 12 V power, make sure it stands upright, clear the space around it, then:

```bash
~/Documents/Open_manipulator_x/launch/robo.sh
```

To use the simulated arm instead (RViz opens):

```bash
~/Documents/Open_manipulator_x/launch/robo.sh --sim
```

Other options: `--rviz` (real arm, also shown in RViz), `--no-camera` (no camera or detection), and the detection speed options in [Faster detection](#faster-detection-running-everything-together).

The control panel is one window in Texas State maroon and gold, with three tabs:

**Robo tab** (everyday use), in three columns:

| Left: the arm | Middle: the camera | Right: talking with Robo |
|---|---|---|
| **Gestures**: built-in ones and the moves you've built, by name. **Gripper** open / close. | **Live video** with YOLO's boxes. If no video arrives (camera unplugged or not working), it says **"Camera not connected"**, and the video comes back by itself once the camera works again. | **Talk once** listens for one question and answers it, then stops. **Live** keeps listening and answering until you turn it off (or say "goodbye"). **Stop talking** cuts Robo off. |
| | **Camera greeting**: when someone new appears, Robo waves and says hello, on its own, without clicking anything (untick to turn it off). It's paused while you're talking with Robo or building a move. | **Speaker volume** `-` / `+` in 5% steps, and a **transcript** with a timing line under each answer. |

**Build your own move tab**, a step-by-step builder (see [Make your own gesture](#make-your-own-gesture)). Camera greetings are paused while this tab is open, so a greeting wave never moves the arm away from the pose you're building.

**Games tab**: **Puppet Master**, **Ball Carry** and **Chocolate Catcher** (the rules are in their sections below), each with a Play button, plus options: control with the keyboard instead of your hand, full screen, and music and sound effects (Chocolate Catcher). A game can start straight away, even while the voice is still getting ready. The game opens in its own window; close it (or press Esc) to come back, or click **Stop the game**.

While a game is running, the panel switches off everything else that uses the camera or the GPU, so the game feels fast: the **camera and detection** stop (the game needs the camera to itself), and the **voice** is unloaded (Whisper and the LLM leave the GPU; the microphone stops). The arm buttons, gestures, greetings and talking are paused, so nothing else moves the arm. When the game ends, it all comes back on by itself: the video returns after detection loads again (about 20 seconds), and the voice gets ready again in the background. The games need MediaPipe; set it up once (step 2 of [Puppet Master](#puppet-master-game)).

Robo **streams** its answers: it starts speaking as soon as the first sentence is written, while the LLM is still writing the rest, and the gesture starts with the first sentence. Under each answer, a grey line shows how long it took, from when you stopped talking: `(heard in 0.7 s · first words after 1.6 s · full answer written after 6.2 s)`.

Robo also **remembers answers** to recent and repeated questions, together with their finished audio, so asking again needs neither the LLM nor the voice: it answers almost instantly, and the timing line says `from memory`. It recognises the same question with small differences ("Hey Robo, what is the Makerspace?" matches "what is the makerspace"), but always thinks through follow-ups like "tell me more" or "why?". Saved answers are kept in `~/.cache/robo_answers/` (the 200 most recently used), are cleared automatically when you edit `robo_knowledge.md`, Robo's personality, the LLM or the voice. To clear them by hand, delete that folder: `rm -rf ~/.cache/robo_answers`.

Everything gets ready by itself when the panel opens: the speaking voice first (a few seconds, so greetings talk right away), then listening and the LLM, which are also warmed up so the first answer is quick (about 20 to 30 seconds in total; please stay quiet near the end while it measures the room's noise). After that, Talk once and Live start listening immediately. If you click while it's still getting ready, it starts listening as soon as it's ready. The LLM stays loaded on the GPU while the panel is open. The volume buttons change the speaker until the next reboot; to keep a level after rebooting, run `sudo alsactl store`.

**To stop:** hold the real arm, then click **Quit** (or press Ctrl+C in the terminal). Everything stops. If something is left running, run `~/Documents/Open_manipulator_x/launch/stop.sh`.

The sections below start each part on its own, which is useful for testing one thing at a time.

### Running parts separately

You'll use 2 or 3 terminal windows. Open a new one with **Ctrl+Shift+T**.

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

Everything above (gestures, joints, gripper, building your own moves) as buttons in Robo's control panel, so you don't need the keyboard. The first time, install Tkinter (Python's window toolkit):

```bash
sudo apt install -y python3-tk
```

Then start the arm and the window together:

```bash
~/Documents/Open_manipulator_x/launch/gestures.sh --gui
```

Add `--sim` to use the simulated arm (`gestures.sh --sim --gui`), or `--rviz` to also see the real arm move live in RViz (`gestures.sh --rviz --gui`). Hold a joint's `-` / `+` button to keep it moving; its live angle is shown next to the buttons. The window (and the camera view) keeps running while a gesture plays; gestures can't overlap: clicking another one while a gesture plays shows "Wait for the current move to finish". The Quit button also stops the arm.

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

**If something is left running** (the arm shakes, RViz won't close, or a program says another arm is running), hold the arm and run `~/Documents/Open_manipulator_x/launch/stop.sh`.

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

### Talk with Robo

Robo is the robot's voice personality: say anything and it answers out loud with a matching gesture. Whisper listens, a local LLM (Ollama, `llama3.2:3b`) decides what to say and which gesture to do, and Piper speaks through the USB speaker. Everything runs on the Jetson.

Robo only talks about **robotics, simulation, itself, Texas State University and the Ingram Hall Makerspace**, and politely declines anything else. Its facts about itself, TXST and the Makerspace come from [`voice/robo_knowledge.md`](voice/robo_knowledge.md), and it's told never to make up details that aren't there. To correct or add facts (new equipment, events, staff contacts), edit that file and restart.

First test the talking alone, without the arm. Stay quiet for the first second while it measures the room's noise. (The first run downloads the Whisper `small` model, about 460 MB.)

```bash
python3 ~/Documents/Open_manipulator_x/voice/chat.py --test
```

Then start the arm on its own in another terminal: the real arm with `ros2 launch open_manipulator_x_bringup hardware.launch.py port_name:=/dev/ttyACM0`, or the simulation with the `base.launch.py` command from [Simulation](#simulation-no-arm-needed). Then run it without `--test`:

```bash
python3 ~/Documents/Open_manipulator_x/voice/chat.py
```

It prints `You: ...` and `Robo: ... [gesture]` for each exchange, with a timing line under each answer, and remembers the last few. Robo starts speaking as soon as the first sentence of its answer is written. Pause briefly after each sentence (Robo decides you've finished after 0.8 s of quiet). **Press Enter** to cut Robo off while it's talking (it goes straight back to listening). Say "goodbye" or press Ctrl+C to stop.

Robo gives short answers to greetings and longer, descriptive ones (3 to 5 sentences) to questions. The gesture is picked by simple rules: a gesture or saved move you name, a wave for hello or goodbye, a bow for thank you, a head shake when it declines an off-topic question, looking around when you talk about the Makerspace, and a nod otherwise. To change how Robo talks, edit `PERSONALITY` at the top of `voice/chat.py`.

| Option | What it does |
|---|---|
| `--wake robo` | only answer sentences that contain "Robo" (so it doesn't reply to everyone talking nearby) |
| `--whisper base` | faster but less accurate hearing (default `small`) |
| `--model llama3.1:8b` | a bigger, smarter LLM (download it first with `ollama pull llama3.1:8b`); slower answers |

### How fast is Robo?

Measured on the Jetson Orin NX 16GB in 25W mode, with `llama3.2:3b` and Whisper `small`. Times are from when Robo notices you've stopped talking (after a pause: 1.2 s in the measurements below, 0.8 s now).

**LLM writing speed** (`ollama run llama3.2:3b --verbose "What is a robot arm? Answer in 3 sentences."`, the `eval rate` line):

| | Tokens per second |
|---|---|
| Nothing else running | 11.5 |
| With `robo.sh` running (YOLO on every camera frame, Whisper, RViz) | 3.3 |

The GPU is shared, so YOLO checking 30 frames a second slowed the LLM (and Whisper) down about 3.5 times. That's why detection now **pauses while Robo is talking** with someone.

**A full conversation turn** (the timing line under each answer):

| | Heard in | First words after | Full answer written after |
|---|---|---|---|
| Before pausing YOLO | 3.3 s | 15.8 s | 26 s |
| After pausing YOLO | 1.9 s | 6.6 s | 24.7 s |
| Repeated question (from memory) | 1.8 s | 1.8 s | 1.8 s |

**Faster listening and answering** (added after these measurements, to measure again):
- Whisper starts transcribing **the moment you pause**, in the background, while Robo is still waiting to be sure you've finished. If you keep talking, that early text is thrown away and it tries again at your next pause, so nothing you say is lost. (Whisper always works on 30 seconds of audio at a time, so transcribing small pieces while you talk wouldn't make it faster; starting at the pause does.)
- Robo decides you've finished after **0.8 s** of quiet instead of 1.2 s.
- Robo **starts every answer with a very short sentence** ("Sure!", "Great question!"), so it can start speaking almost as soon as the LLM begins writing.

| | Heard in | First words after | Full answer written after |
|---|---|---|---|
| With these changes | to measure | to measure | to measure |

"First words after" is what you notice: Robo speaks while the LLM is still writing, so the full answer time mostly shows how long the answer is. From memory, Robo starts talking as soon as Whisper has understood the question.

### Faster detection (running everything together)

YOLO, Whisper and the LLM all share the Jetson's one GPU, so the way to run everything together *and* fast is to make YOLO cheaper. The camera view always shows live video. **By default**, detection uses the **TensorRT model** (`~/yolo11n.engine`, made once with the steps below; without it, the normal `yolo11n.pt`), checks **every frame** while Robo is idle, and **25 frames a second** while Robo is talking. No options are needed for this.

| Option (for `launch/robo.sh`) | What it does |
|---|---|
| `--busy-fps 0` | pause detection completely while Robo is talking (default 25) |
| `--yolo yolo11n.pt` | use a different YOLO model file (default: the TensorRT model if it exists) |
| `--imgsz 320` | YOLO looks at a smaller picture: about 4x less work, but misses small or far-away people more often (default 640; a TensorRT model must be exported at the same size) |

`detect.py` logs how long YOLO takes every 5 seconds (in `/tmp/robo_detect.log`, or in the terminal when run on its own), like `YOLO (yolo11n.pt, imgsz 640): 13.9 ms per frame, 30.0 frames checked per second`.

**Make the TensorRT model (once, takes about 5 to 10 minutes).** The export needs `onnx`; installing it with the version limits first keeps NumPy and onnxruntime at the versions ROS 2 and Piper need:

```bash
python3 -c "import tensorrt; print(tensorrt.__version__)"
pip3 install "onnx>=1.12,<1.18" onnxslim "numpy<2" "onnxruntime==1.20.1"
cd ~ && yolo export model=yolo11n.pt format=engine half=True imgsz=640 device=0
```

The first command just checks TensorRT is there (it comes with JetPack). The export creates `~/yolo11n.engine`. Afterwards, check nothing else changed: `python3 -c "import numpy, onnxruntime; print(numpy.__version__, onnxruntime.__version__)"` should print `1.x` and `1.20.1`.

**Measured on our Jetson** (25W mode, 640 pixel picture, average of 50 runs; `r.speed` from Ultralytics):

| Model | Prepare (CPU) | Network (GPU) | Boxes (CPU) |
|---|---|---|---|
| `yolo11n.pt` | 7.6 ms | 26.9 ms | 3.7 ms |
| `yolo11n.engine` (TensorRT) | 14.2 ms | 12.8 ms | 6.5 ms |

The GPU part is what slows the LLM down. At 30 frames a second, the normal model keeps the GPU busy about 81% of the time; TensorRT about 38%, leaving more than twice as much for the LLM and Whisper. Building the engine took about 8 minutes, and it didn't change any other package versions.

**Conversation speed with each setting** (ask Robo a **new** question, one it hasn't answered before; YOLO's ms per frame is in `/tmp/robo_detect.log`):

| Setting | YOLO ms per frame | First words after |
|---|---|---|
| `yolo11n.pt`, paused while talking (`--yolo yolo11n.pt --busy-fps 0`) | n/a (paused) | 6.6 s |
| **Default:** TensorRT, 25 frames a second while talking | to measure | to measure |
| TensorRT at 320 (`--yolo yolo11n_320.engine --imgsz 320`) | to measure | to measure |

(For `--imgsz 320` with the TensorRT model, export it at that size too: add `imgsz=320` to the export command, and rename the result, e.g. `mv ~/yolo11n.engine ~/yolo11n_320.engine`.)

### Check the joint angles (any terminal)

```bash
ros2 topic echo /joint_states --once
```

### Stop the robot

1. Quit the gestures (`q`) or teleop (`ESC`), and press Ctrl+C in any other terminals except Terminal 1. If you started with `gestures.sh`, hold the arm before pressing `q`: that stops the arm too.
2. **Hold the arm**, then press Ctrl+C in Terminal 1. The arm goes limp.
3. Turn off the 12 V power.

When the power is off, the arm slumps. Before starting it again, hold it standing roughly straight up and keep holding it while you turn the 12 V on. If you forget, the programs refuse to move the arm and tell you what to do.

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

Pose the arm, save each pose, then save the whole move with a **name**. Try it in the simulation first.

1. Start everything (or just the arm and the panel with `launch/gestures.sh --sim --gui`):
   ```bash
   ~/Documents/Open_manipulator_x/launch/robo.sh --sim
   ```
2. Open the **Build your own move** tab. Camera greetings pause while it's open.
3. **Step 1 · Move the arm:** hold the `-` / `+` buttons for each joint (live angles shown). **Go home** brings it back to the start.
4. **Step 2 · Gripper:** open or close it if you want.
5. **Step 3 · Add poses:** set the seconds to reach this pose (default 1.0), then click **Add pose**. Repeat for every pose. The list shows each pose's angles, gripper and time; select one and click **Delete selected pose** to remove it.
6. **Step 4 · Test and save:** **Test the move** plays it without saving. Then type a **name** (like `hello dance`) and click **Save move**. Using the name of a move you already saved asks before replacing it; built-in names like `wave` aren't allowed.
7. Your move is now a button in **Gestures** on the Robo tab, and you can say its name to Robo. **Your saved moves** (on the right of the builder) lets you **Play**, **Edit** (loads its poses into the builder; save with the same name to replace it) or **Delete** each one.

**Recording on the real arm, watching it in RViz too:** start with `~/Documents/Open_manipulator_x/launch/robo.sh --rviz` (12 V on, space around the arm clear). Keep poses away from the table and the arm's own base, and give poses that are far apart more seconds, so the arm doesn't swing fast.

**With the keyboard instead** (`launch/gestures.sh --sim`): press `h` to go home, move with the number keys (`1`–`8`), `p` to add a pose, `x` to start over, and `k` to save: it asks for a name and picks a free key to play it with.

**The gripper:** each pose also remembers whether the gripper was open or closed. Click **Open** / **Close** (or press `o` / `c`) *before* **Add pose**. When the move plays, the arm reaches that pose, then the gripper opens or closes (only when it changes), then the arm carries on.

**Changing a saved move:** use **Edit** in the builder, or record it again and save it with the **same name**. For small changes you can also edit `gestures/my_gestures.json` (each move is stored under a letter, the keyboard menu's key for it):

```bash
gedit ~/Documents/Open_manipulator_x/gestures/my_gestures.json
```

Each pose is one line: base turn, shoulder, elbow, wrist (radians), seconds to get there, and optionally `"open"` or `"close"` for the gripper:

```json
[-0.55, 0.15, 0.6, 0.0, 1.0, "close"],
```

- Slower or faster: change the seconds (`2.0` takes twice as long as `1.0`).
- Add a gripper action: add `, "open"` or `, "close"` after the seconds.
- Remove a pose: delete its line (the new last line in a list mustn't end with a comma).
- Delete a move: remove its whole block. Rename it: change `"name"`.

Restart the controls to load your changes.

### Move the gripper to a point (Robo's hands)

The first part of Robo's "brain" (picking things up when you ask): instead of joint angles, give a point in **mm** and Robo works out the joint angles itself. The point is the middle of the gripper fingertips:

- **x** forward from the base, **y** to the left, **z** up from the table
- Pointing **straight down** (how Robo picks things up), it reaches up to about 100 mm high and 80 to 240 mm in front of the base. Further away or higher, the gripper has to tilt.
- It refuses any point it can't reach safely, and never goes lower than 10 mm above the table.

Check the math first (no arm needed):

```bash
python3 ~/Documents/Open_manipulator_x/brain/arm.py test
```

Then start the arm, **in the simulation first** (`~/Documents/Open_manipulator_x/launch/gestures.sh --sim`), and in another terminal:

```bash
python3 ~/Documents/Open_manipulator_x/brain/arm.py where
```

```bash
python3 ~/Documents/Open_manipulator_x/brain/arm.py go 200 0 100
```

```bash
python3 ~/Documents/Open_manipulator_x/brain/arm.py go 200 0 40
```

```bash
python3 ~/Documents/Open_manipulator_x/brain/arm.py home
```

`where` says where the gripper is now (and the joint angles), `go X Y Z` moves it there pointing down (add `--level` to point it forward), and `home` goes back to the home pose.

On the real arm, try `go 200 0 100` first (well above the table) and measure with a ruler: the fingertips should be about 200 mm in front of the base and 100 mm above the table. If the arm stands on a plate or board, put its thickness in `MOUNT_HEIGHT` at the top of `brain/arm.py`.

### Pick things up (camera on the gripper)

Robo finds an object with the camera on its gripper, moves right over it, grabs it, lifts it, and puts it back down when you press Enter. Start with something easy to grab: a block or a glue stick, about 20 to 40 mm wide.

1. Start the arm (Terminal 1; hold the arm while it starts):
   ```bash
   ~/Documents/Open_manipulator_x/launch/gestures.sh
   ```
2. Start the camera (Terminal 2):
   ```bash
   ros2 run usb_cam usb_cam_node_exe --ros-args -p video_device:=/dev/video0 -p image_width:=640 -p image_height:=480 -p pixel_format:=mjpeg2rgb -p framerate:=30.0
   ```
3. **Teach it once** (Terminal 3). The arm points down with the gripper open; put the block between the fingers and press Enter. It centres the block, lifts up and moves a little, to learn where the block shows up in the picture. That's saved in `brain/camera.json`; teach again if the camera is moved.
   ```bash
   python3 ~/Documents/Open_manipulator_x/brain/pick.py teach block
   ```
4. Put the block anywhere on the table about 80 to 220 mm in front of the arm, and pick it up:
   ```bash
   python3 ~/Documents/Open_manipulator_x/brain/pick.py pick block
   ```

Other things to try:

```bash
python3 ~/Documents/Open_manipulator_x/brain/pick.py look block
```

```bash
python3 ~/Documents/Open_manipulator_x/brain/pick.py pick "glue stick"
```

`look` only looks, from the **search pose** (shoulder leaning back, wrist bent down, so the camera is as high as it gets and sees the whole pick-up area): it shows the gripper camera live with a box around the object, and says where it sees it. Press `q` in the window to finish. After teaching, a yellow cross shows where an object right under the fingers shows up.

- If it can't find the object, try a lower `--conf 0.05`, or another name ("cube", "toy block", "red block").
- If the fingers hit the table or close above the object, change `--grab-height` (fingertip height when grabbing, default 15 mm).
- If it says "Missed", it closed on nothing: the gripper closed all the way. The line before it shows the gripper position; tell us if it misses while really holding something.

### Puppet Master (game)

An arcade game: **your hand controls Robo's arm**. A camera on a stand watches the player; Robo's gripper follows the hand, and **making a fist whacks** (Robo taps straight down). Target stickers lie on the table in front of Robo, and the screen lights one up at a time: whack it before its timer runs out.

| Target | Points |
|---|---|
| Normal (blue) | 50, plus up to 50 for being quick |
| Gold | double points, but it doesn't stay long |
| Red | **don't whack it**: −300 and the combo is gone (+50 for leaving it alone) |
| Missed whack | −50 and the combo is gone |
| Combo | ×2 after 5 hits in a row, ×3 after 10 |

A round is 60 seconds and the max score is 9,999. Ranks: S 7,500+, A 5,500+, B 3,500+, C below. The top 10 are kept in `game/leaderboard.json` and shown on the title screen.

**1. Get the latest code** (the games are part of it). If you tried the games on the `game` branch before, go back to `main` first:

```bash
cd ~/Documents/Open_manipulator_x && git checkout main && git pull
```

**2. Install MediaPipe** (the hand tracker), once. It goes in its own environment, `~/game_venv`, so nothing else on the Jetson changes. Everything already installed (ROS, OpenCV, YOLO) still works inside it.

```bash
python3 -m venv --system-site-packages ~/game_venv
```

```bash
python3 -c "import site; print(site.getusersitepackages())" > ~/game_venv/lib/python3.10/site-packages/user_site.pth
```

```bash
~/game_venv/bin/pip install --no-deps mediapipe==0.10.18
```

```bash
~/game_venv/bin/pip install absl-py attrs flatbuffers "protobuf>=4.25.3,<5" sentencepiece
```

Check it (NumPy must still be 1.x):

```bash
~/game_venv/bin/python -c "import mediapipe, cv2, numpy; print('mediapipe', mediapipe.__version__, 'numpy', numpy.__version__)"
```

To undo all of it: `rm -rf ~/game_venv`.

**3. Put the camera on a stand** facing where the player stands (about 1.5 to 2 m away, at chest height), not on the gripper. The game uses the camera directly, so don't run `robo.sh` or the `usb_cam` camera at the same time.

**4. Check the hand tracking speed** (only the camera; the arm doesn't move). Hold a hand up in front of the camera:

```bash
cd ~/Documents/Open_manipulator_x/game && ~/game_venv/bin/python bench_tracking.py
```

It compares MediaPipe and YOLO pose and says which is faster. The game uses MediaPipe (it sees a fist; YOLO pose has no fingers, so with `--tracker yolo` you whack by raising your other hand). To make YOLO pose faster on the Jetson GPU, build its TensorRT model once (then the benchmark and the game use it automatically):

```bash
cd ~ && yolo export model=yolo11n-pose.pt format=engine half=True imgsz=320 device=0
```

**5. Try it without the robot** (a pretend arm on the screen):

```bash
~/Documents/Open_manipulator_x/launch/game.sh --no-arm
```

**6. Place the target stickers** (once, on the real arm): the gripper stops over each target spot in turn; put a sticker (or a coin, or a coaster) right under it and press Enter.

```bash
~/Documents/Open_manipulator_x/launch/game.sh --setup
```

**7. Play.** In the simulation first, then on the real arm:

```bash
~/Documents/Open_manipulator_x/launch/game.sh --sim
```

```bash
~/Documents/Open_manipulator_x/launch/game.sh --fullscreen
```

Type your name and press Enter, hold your hand up, and play. Keys: `F` full screen, `Esc` quit (it stops the arm too, so hold the real arm).

Safety: the player stands back behind a line, not within the arm's reach. The arm only moves inside the play area, never faster than 1.5 rad/s, never lower than the touch height, and it holds still when it loses sight of the hand. If the fingers press too hard on the table, raise `--touch-height 25` (default 20 mm). The rules (round time, points, ranks, target spots) are at the top of `game/puppet_master.py`.

### Ball Carry (game)

Move Robo with your hand and carry all **5 balls** from the left side of the table to the right side, as fast as you can. **Fastest time wins.** It uses the same camera on a stand as Puppet Master (facing the player); nothing else.

- Put 5 balls (ping-pong size, about 40 mm) on the **left** side of the table, within Robo's reach: closer than about 220 mm to the base and not more than about 55 degrees to the side.
- Move your hand: Robo follows, gliding level at 60 mm so a carried ball doesn't knock the others.
- **Close your hand** (fist): Robo goes down and grabs. Move over to the **right** side and **open your hand**: Robo lets go.
- The stopwatch stops when the 5th ball is across. `P` pauses and restarts it. The round ends anyway after 2 minutes.

Robo checks every carry itself:
- **Holding a ball?** A ball stops the gripper fingers partway; empty, they close all the way.
- **Across?** Robo knows where its gripper is from its joint angles: the ball has to be let go on the right side, and not picked up from the right side (so a ball that's already across can't count twice).

| What happens | On screen |
|---|---|
| Ball let go on the right side | +1 (and the time it took) |
| Ball let go before the right side | "Not across yet": pick it up again and finish |
| Gripper closed on nothing | "Empty" |
| Ball picked up from the right side and let go there again | doesn't count twice |

Before every game a **How to play** screen shows these steps (type your name, Enter, read, Enter). The top 10 (most balls, then fastest time) are on the title screen.

Try it without the robot (a pretend arm and pretend balls):

```bash
~/Documents/Open_manipulator_x/launch/game.sh --balls --no-arm
```

Play (in the simulation first with `--sim`, then on the real arm):

```bash
~/Documents/Open_manipulator_x/launch/game.sh --balls --fullscreen
```

No camera, or to test: `--keyboard` moves Robo with `W` `A` `S` `D`, and `Space` grabs and lets go.

If the gripper misses the balls or touches the table, change `GRAB_HEIGHT` (default 15 mm) at the top of `game/arm_link.py`. If it says "Empty" while it's really holding a ball, the ball is too small or soft for the holding check: change `HOLDING` in the same file (a ball must stop the fingers above that position).

### Chocolate Catcher (game)

A **claw machine** with Robo as the claw. **You only win the chocolates you get into the basket.** It uses the same camera on a stand as the other games (facing the player).

| You do | Robo does |
|---|---|
| Move your hand left / right | the claw moves left / right |
| Move your hand up / down | the claw moves toward you / away from you |
| Make a fist | the claw goes down, grabs, and comes back up at the same spot |
| Keep the fist (and move) | the claw stays closed, holding the chocolate, and follows your hand |
| Open your hand | the claw opens and the chocolate drops |

- **The timer starts when you grab a chocolate:** you have **10 seconds** to get it over the **basket** and open your hand. While carrying, the claw moves a bit slower (150 mm/s instead of 250).
- If the time runs out, the claw **opens by itself** and the chocolate drops where it is.
- A chocolate counts only if it's dropped **over the basket**. **5 grabs** per player; the most chocolates wins.
- Robo checks it all itself: holding (a chocolate stops the gripper fingers partway; empty, they close all the way) and where the claw is when it opens.
- The fist has to be steady for 2 camera pictures before it counts (open again the same way), so one odd picture can't grab or drop by mistake.

**Sounds** (on the USB speaker): bouncy background music; beeps for 3-2-1-GO; a "bloop" when the claw drops; while you carry a chocolate, a **ticking timer that speeds up** (with a heartbeat near the end) while the music gets quieter; a happy jingle in the basket; a cartoon "womp" when it drops outside; the sad trombone for an empty claw or time's up (with a buzzer); and a fanfare (or a sad trombone) at the end. They're all made in code (`game/sound.py`), so there's nothing to download. To hear them all once: `cd ~/Documents/Open_manipulator_x/game && python3 sound.py`. If the speaker isn't there, the game just plays silently. `--no-sound` (or unticking "Music and sound effects" in the Games tab) turns them off.

The screen shows the camera with your hand, its middle point, the play frame, the basket and the claw; and on the side the chocolates won, the grabs left, the carry timer and the controls. A How to play screen comes before every game.

Set up: put a box or bowl on the table where the screen shows the BASKET (on the right, toward you), and the chocolates anywhere else in reach (within about 220 mm of the base). **Wrapped chocolate balls or small soft toys, about 25 to 45 mm**, work best; flat chocolate bars are too thin to grab.

Try it without the robot, then play:

```bash
~/Documents/Open_manipulator_x/launch/game.sh --claw --no-arm
```

```bash
~/Documents/Open_manipulator_x/launch/game.sh --claw --fullscreen
```

`--keyboard`: `W` `A` `S` `D` move the claw (`W` toward you), `Space` is the fist (press once to grab and hold, again to drop). `--sim` uses the simulated arm. The grabs, the carry time and the basket position (`BASKET`) are at the top of `game/claw_machine.py`.

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
  gui.py               Robo's control panel: gestures, joints, gripper, recording,
                       talking with Robo (once or live) and the camera greeting
brain/
  arm.py               Robo's hands: move the gripper to a point in mm (inverse kinematics)
  pick.py              find an object with the gripper camera and pick it up
game/
  puppet_master.py     the Puppet Master game: your hand controls Robo, whack the targets
  tracker.py           hand tracking (MediaPipe hands or YOLO pose)
  arm_link.py          the arm follows the hand and whacks (or a pretend arm)
  bench_tracking.py    compares the hand trackers' speed
  ball_carry.py        the Ball Carry game: carry the balls across, fastest time wins
  claw_machine.py      the Chocolate Catcher game: a claw machine with Robo as the claw
  sound.py             the games' music and sound effects (made in code)
perception/
  detect.py            live object detection from the camera (YOLO / YOLO-World)
voice/
  listen.py            voice commands: say "wave", "bow", ... and the arm does it
  robo_voice.py        Robo's voice: listening, personality, LLM, speaking, gesture rules
  chat.py              talk with Robo in the terminal (the control panel has it as buttons)
  robo_knowledge.md    Robo's facts about itself, Texas State and the Ingram Hall Makerspace
launch/
  greeter.launch.py    starts the whole greeter robot with one command
  gestures.sh          starts the arm (real or --sim) and the controls (keys, or --gui) together
  robo.sh              starts EVERYTHING: arm, camera, detection and the control panel
  vision.sh            starts / stops the camera and detection (the panel stops them during games)
  game.sh              starts the arm and a game (Puppet Master, --balls, --claw)
  stop.sh              stops every robot program (use when something is left running)
dependencies.repos     list of ROBOTIS code to download (used in Step 5)
```

## Problems?

See [docs/troubleshooting.md](docs/troubleshooting.md).
