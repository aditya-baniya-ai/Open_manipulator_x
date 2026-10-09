# Troubleshooting

Problems hit while building this robot, and the fixes.

## Permission denied on /dev/ttyACM0

**Symptom:** the ROS 2 hardware launch can't open the OpenCR port.

**Cause:** your user isn't in the `dialout` group, which owns serial ports.

**Fix:**

```bash
sudo usermod -aG dialout $USER
```

Then log out and back in (or reboot). Check with `groups`; it should list `dialout`. Opening a new terminal isn't enough, because group changes only apply after a fresh login.

If the command says the group already exists, you probably ran `groupadd` or mistyped it. Run the exact `usermod` line above.

## Every servo shows MISSING ID (Arduino servo check)

- 12 V power is off or the switch is off.
- The servo cable isn't fully seated, or it's in a 4-pin port instead of a 3-pin one.
- Baud rate mismatch: `dxl.begin(1000000)` must match the servos (1 Mbps).

## Arduino upload to OpenCR fails or freezes

Put the board in recovery mode: hold **PUSH SW2**, press **RESET**, release SW2, then upload again. This also fixed the freeze while trying the ROBOTIS teaching example.

Upload from the Mac. The Arduino IDE can't upload to the OpenCR from the Jetson.

## Arm doesn't move after uploading usb_to_dxl

This is normal. `usb_to_dxl` only passes commands from USB to the servos, and has no motions of its own. Plug the OpenCR into the Jetson and launch the arm with ROS 2 (see [Start the arm](../README.md#start-the-arm-terminal-1) in the README).

## rosdep: Unable to locate package ros-humble-gazebo-ros

**Cause:** Gazebo (the simulator) isn't built for ARM computers like the Jetson. It's only needed for simulation, not for the real arm.

**Fix:** skip the Gazebo keys:

```bash
cd ~/colcon_ws
rosdep install --from-paths src --ignore-src -y -r --skip-keys "gazebo_ros gazebo_ros_pkgs gazebo_ros2_control gazebo_plugins"
```

## Teleop: gripper moves but joints don't

**Symptom:** `open_manipulator_x_teleop` prints `fail to connect moveit_servo`. The o/p keys open and close the gripper, but the joint keys (1/q, 2/w, ...) only print `Joint PUB` and nothing moves.

**Cause:** the gripper keys send commands straight to the gripper controller, but the joint keys go through MoveIt Servo, which isn't running. The hardware is fine.

**Fix:** start MoveIt Servo in another terminal before teleop: `ros2 launch open_manipulator_x_moveit_config servo.launch.py` (see [Option B](../README.md#option-b-move-each-joint-with-the-keyboard-terminals-2-and-3) in the README). To test the arm without MoveIt, run `gestures/gestures.py`, which talks to the arm controller directly.

## fake.launch.py says "Can not launch fake robot in Raspberry Pi"

**Cause:** ROBOTIS's `fake.launch.py` decides it's on a Raspberry Pi if the file `/sys/firmware/devicetree/base/model` exists. The Jetson has that file too, so the launch quits even though simulation works fine.

**Fix:** call `base.launch.py` directly. Include `use_sim:=false`: it defaults to `true` (Gazebo), and then the control program never starts and the spawners wait forever with `waiting for service /controller_manager/list_controllers`.

```bash
ros2 launch open_manipulator_x_bringup base.launch.py use_sim:=false use_fake_hardware:=true fake_sensor_commands:=true start_rviz:=true
```

## Whisper: module 'coverage' has no attribute 'types'

**Symptom:** `import whisper` fails inside `numba` with `AttributeError: module 'coverage' has no attribute 'types'`. There may also be a warning that SciPy needs `NumPy <1.25.0`.

**Cause:** Ubuntu 22.04 ships old `coverage` and `scipy` packages. Whisper's `numba` needs a newer `coverage`, and the old SciPy predates the NumPy that YOLO installed.

**Fix:** install newer copies for your user (Ubuntu's own copies are left alone), keeping NumPy on 1.x for ROS 2:

```bash
pip3 install -U "coverage>=7.2" "scipy<1.15" "numpy<2"
```

## Checking the microphone without a speaker

Record, then measure how loud the recording is:

```bash
arecord -D plughw:CARD=BRIO,DEV=0 -f S16_LE -r 16000 -c 1 -d 5 ~/mic_test.wav
python3 -c "
import wave, numpy as np
w = wave.open('$HOME/mic_test.wav')
a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
print('seconds:', round(len(a) / w.getframerate(), 1), ' loudest:', int(np.abs(a).max()), 'out of 32767')
"
```

A loudest value above about 1000 means it picked up your voice. Near 0 means silence (muted or wrong device).

## The simulation or arm keeps running after closing the controls

**Symptom:** after Ctrl+C (or closing the controls) started with `launch/gestures.sh`, RViz or the arm launch is still running.

**Cause:** older versions of `gestures.sh` didn't stop the whole arm launch, and the button window ignored Ctrl+C. Both are fixed; run `git pull`.

**Fix for anything still running now:**

```bash
~/Documents/Open_manipulator_x/launch/stop.sh
```

It stops every robot program and says whether anything is still running.

## Arm stays stiff after every program is stopped

**Symptom:** nothing is running (`ps aux | grep -E "ros2|rviz|control_node" | grep -v grep` prints nothing), but the joints still hold their position and can't be moved by hand.

**Cause:** the servos keep holding their last position until they're told to let go or lose power. If the arm program was force-stopped (for example with `pkill`), it never released them.

**Fix:** hold the arm, then turn off the 12 V power switch on the OpenCR. The joints go free. Turn it back on before the next launch.

## "The arm is outside its safe range, so it won't be moved"

**Symptom:** `gestures.py`, `gui.py`, `greet.py` or `listen.py` stops at startup with this message, naming a joint. (Before this check existed: the angles in the button window looked strange, like shoulder +107° and elbow -107°, and the buttons didn't move the arm.)

**Cause:** with the power off, the arm slumped under its own weight, past the joint limits. Or the base is at its end stop (about ±180°) because the arm is mounted backwards; see [hardware.md](hardware.md#mounting-direction).

**Fix:** hold the arm and turn the 12 V off. Move the arm by hand so it stands straight up with the base facing forward. Keep holding it while you turn the 12 V back on, then start again. Check with `ros2 topic echo /joint_states --once`: joint1, joint2 and joint3 should all be close to 0.

## The arm (and RViz) keeps shaking

**Cause:** two programs are controlling the arm at once: for example a leftover simulation plus the real arm (their joint angles mix, so RViz flickers and the real arm gets jumpy commands), or a leftover MoveIt Servo from `servo.launch.py` that keeps sending its own "hold here" commands.

**Fix:** hold the real arm, stop everything, check nothing is left, then start just one thing:

```bash
~/Documents/Open_manipulator_x/launch/stop.sh
```

It should say `Everything is stopped.` (A plain `pkill -f ros2` isn't enough: it misses programs like `robot_state_publisher`, which keep running in the background.) If it lists nodes that aren't running on your Jetson, they're from another computer on the network: see the next section. `launch/gestures.sh` and the controls now refuse to start when this happens, and say why.

## Nodes from other computers (shared network)

ROS 2 automatically shares topics with every computer on the same network. In a lab or makerspace, another robot's `/joint_states` or commands can mix with yours. If `launch/stop.sh` (or `ros2 node list` with nothing running) still lists nodes, give your robot its own private channel. Pick a number from 1 to 101 that nobody else on the network uses:

```bash
echo "export ROS_DOMAIN_ID=42" >> ~/.bashrc && source ~/.bashrc
```

Every terminal then only sees ROS programs with the same number.

## The base jitters quickly (about ±1°) while holding a pose

**Symptom:** after a gesture or Home, with the forearm sticking out, the base buzzes back and forth by a fraction of a degree. In the button window its angle flickers by ±1°.

**How we found the cause:** the controller's target for the base stays exactly the same, but the measured position moves around it:

```bash
for i in 1 2 3; do ros2 topic echo /arm_controller/state --once --field desired.positions; ros2 topic echo /arm_controller/state --once --field actual.positions; sleep 1; done
```

So nothing in the software moves it: the base servo itself overshoots. ROBOTIS gives every servo P 800, I 100, D 100. That's too stiff for the base turning the long, sticking-out arm, with a little play in its gears.

**Fix:** give the base servo P 400, I 0, D 0 (README, setup Step 5b). It's sent at every launch and not stored in the servo permanently, and there's a backup and undo. Lowering only I and D wasn't enough; lowering P to 400 stopped it.

## A servo ignores a target near 0° or 360°

**Symptom:** in the base swing test, the base started at 348°, so `start + 90` went past 360 and the servo rejected it.

**Fix:** keep targets inside 0–360, for example go the other way if the target would pass 360:

```cpp
float target = (now + 90 <= 360) ? now + 90 : now - 90;
```

`servo_check.ino` already does this. In ROS 2 this matters less, because joints use radians with 0 at the servo's 180°.
