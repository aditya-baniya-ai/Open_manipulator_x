# Jetson setup log

Every step to set up the Jetson and run the arm with ROS 2, in order.

## System

- Board: NVIDIA Jetson Orin Nano
- OS: Ubuntu 22.04.5 (so ROS 2 **Humble**)
- JetPack version: TODO (`cat /etc/nv_tegra_release`)
- Install type: native (no Docker), to avoid USB, GPU, audio and display passthrough problems

## Progress

| Step | Status |
|---|---|
| 1. ROS 2 Humble installed | ✅ talker/listener test works |
| 2. USB permission (dialout) | ✅ `groups` lists dialout |
| 3. `usb_to_dxl` uploaded to OpenCR (from Mac) | ✅ `[OK] Download` |
| 4. ROBOTIS arm packages built | ✅ 12 packages, about 2.5 min |
| 5. `.bashrc` + udev rules | ⏳ |
| 6. Arm launched through ROS 2 | ⏳ |
| 7. `/joint_states` + keyboard teleop test | ⏳ |
| 8. Wave gesture | ⏳ |

## 1. Install ROS 2 Humble

```bash
sudo apt install -y software-properties-common curl
sudo add-apt-repository -y universe
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list
sudo apt update
sudo apt install -y ros-humble-desktop ros-dev-tools
```

Check it works, in two terminals:

```bash
ros2 run demo_nodes_cpp talker
ros2 run demo_nodes_py listener
```

## 2. Serial port permission

The OpenCR shows up as `/dev/ttyACM0`. Your user needs to be in the `dialout` group to open it:

```bash
sudo usermod -aG dialout $USER
```

Log out and back in, then check that `groups` lists `dialout`. See [troubleshooting](troubleshooting.md#permission-denied-on-devttyacm0).

## 3. Upload usb_to_dxl to the OpenCR (on the Mac)

The Arduino IDE can't upload to the OpenCR from the Jetson, so do this on the Mac. See [firmware/README.md](../firmware/README.md#usb_to_dxl-for-ros-2). Then plug the OpenCR's USB into the Jetson and check that it shows up:

```bash
ls /dev/ttyACM*
```

It should print `/dev/ttyACM0`.

## 4. Workspace and ROBOTIS packages

This repo lives in `~/Documents/Open_manipulator_x` (clone it there first if you haven't). Only the ROBOTIS code goes in the `~/colcon_ws` workspace.

```bash
sudo apt install -y ros-humble-ros2-control ros-humble-ros2-controllers \
  ros-humble-moveit ros-humble-gripper-controllers
mkdir -p ~/colcon_ws/src
vcs import ~/colcon_ws/src < ~/Documents/Open_manipulator_x/dependencies.repos
cd ~/colcon_ws
rosdep update
rosdep install --from-paths src --ignore-src -y -r
colcon build --symlink-install
```

A good build ends with `Summary: 12 packages finished`. Lines saying packages "had stderr output", and CMake deprecation warnings, are just warnings and can be ignored. On the Jetson, rosdep fails on Gazebo; see [troubleshooting](troubleshooting.md#rosdep-unable-to-locate-package-ros-humble-gazebo-ros).

If rosdep says it isn't initialized, run `sudo rosdep init` once. If the build freezes or runs out of memory, use `colcon build --symlink-install --parallel-workers 1`.

The ROBOTIS packages come from the official `ROBOTIS-GIT/open_manipulator` repo, `humble` branch (not older forks).

## 5. Terminal setup and udev rules

```bash
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
echo "source ~/colcon_ws/install/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

Then install the ROBOTIS udev rules (`create_udev_rules`, from the open_manipulator packages) so the OpenCR port gets the correct permissions and low-latency setting. TODO: record the exact command once it's run.

## 6. Launch the arm

Put the arm in its start pose by hand first, then:

```bash
ros2 launch open_manipulator_x_bringup hardware.launch.py port_name:=/dev/ttyACM0
```

## 7. Test

```bash
ros2 topic echo /joint_states
```

Then try keyboard teleop. TODO: record the exact teleop command.

## 8. First gesture

```bash
python3 ~/Documents/Open_manipulator_x/gestures/wave.py
```

## Notes

- ROS 2 uses radians, and 0 rad equals 180° on the servos.
- Add anything else you run here as you go, including commands that didn't work.
