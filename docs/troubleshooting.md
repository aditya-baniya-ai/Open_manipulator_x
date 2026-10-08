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

## A servo ignores a target near 0° or 360°

**Symptom:** in the base swing test, the base started at 348°, so `start + 90` went past 360 and the servo rejected it.

**Fix:** keep targets inside 0–360, for example go the other way if the target would pass 360:

```cpp
float target = (now + 90 <= 360) ? now + 90 : now - 90;
```

`servo_check.ino` already does this. In ROS 2 this matters less, because joints use radians with 0 at the servo's 180°.
