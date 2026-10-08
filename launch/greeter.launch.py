"""
Start the whole greeter robot with one command: arm, camera, detection and greeter.

    ros2 launch ~/Documents/Open_manipulator_x/launch/greeter.launch.py

Options (add after the command, e.g. ... greeter.launch.py sim:=true gesture:=b):
    sim:=true          use the simulated arm in RViz instead of the real one
    gesture:=b         greet with another gesture key (default w = wave)
    cooldown:=60       seconds between greetings (default 30)
    window:=false      don't open the detection video window
    camera:=/dev/video0   which camera to use

Press Ctrl+C once to stop everything. On the real arm, hold it first: it goes limp.
"""

import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

REPO = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
DETECT = os.path.join(REPO, "perception", "detect.py")
GREET = os.path.join(REPO, "gestures", "greet.py")


def generate_launch_description():
    sim = LaunchConfiguration("sim")
    window = LaunchConfiguration("window")
    bringup_launch = PathJoinSubstitution(
        [FindPackageShare("open_manipulator_x_bringup"), "launch"]
    )
    # Show Python print() output right away instead of in chunks
    unbuffered = {"PYTHONUNBUFFERED": "1"}

    return LaunchDescription([
        DeclareLaunchArgument("sim", default_value="false"),
        DeclareLaunchArgument("gesture", default_value="w"),
        DeclareLaunchArgument("cooldown", default_value="30"),
        DeclareLaunchArgument("window", default_value="true"),
        DeclareLaunchArgument("camera", default_value="/dev/video0"),

        # The real arm
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([bringup_launch, "/hardware.launch.py"]),
            launch_arguments={"port_name": "/dev/ttyACM0"}.items(),
            condition=UnlessCondition(sim),
        ),
        # Or the simulated arm in RViz
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([bringup_launch, "/base.launch.py"]),
            launch_arguments={
                "use_sim": "false",
                "use_fake_hardware": "true",
                "fake_sensor_commands": "true",
                "start_rviz": "true",
            }.items(),
            condition=IfCondition(sim),
        ),

        # The camera
        Node(
            package="usb_cam",
            executable="usb_cam_node_exe",
            parameters=[{
                "video_device": LaunchConfiguration("camera"),
                "image_width": 640,
                "image_height": 480,
                "pixel_format": "mjpeg2rgb",
                "framerate": 30.0,
            }],
            output="screen",
        ),

        # Detection, with or without the video window
        ExecuteProcess(
            cmd=["python3", DETECT],
            additional_env=unbuffered,
            output="screen",
            condition=IfCondition(window),
        ),
        ExecuteProcess(
            cmd=["python3", DETECT, "--no-window"],
            additional_env=unbuffered,
            output="screen",
            condition=UnlessCondition(window),
        ),

        # The greeter
        ExecuteProcess(
            cmd=[
                "python3", GREET,
                "--gesture", LaunchConfiguration("gesture"),
                "--cooldown", LaunchConfiguration("cooldown"),
            ],
            additional_env=unbuffered,
            output="screen",
        ),
    ])
