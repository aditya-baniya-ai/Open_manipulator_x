"""
Wave gesture for OpenMANIPULATOR-X (ROS 2).

Run it while the arm is launched (see docs/setup_jetson.md):
    python3 wave.py

It sends one trajectory to the arm controller:
  1. go to the init pose (all joints at 0 rad, the same pose as the Arduino greeting)
  2. tilt the wrist back and forth a few times
  3. return to the init pose
The base (joint1) stays wherever it is now.
"""

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from control_msgs.action import FollowJointTrajectory
from trajectory_msgs.msg import JointTrajectoryPoint
from sensor_msgs.msg import JointState
from builtin_interfaces.msg import Duration

JOINTS = ["joint1", "joint2", "joint3", "joint4"]
SWING = 0.6      # radians, about 35 degrees
WAVES = 3
STEP = 0.6       # seconds per wrist swing


class Waver(Node):
    def __init__(self):
        super().__init__("waver")
        self.base = None
        self.create_subscription(JointState, "/joint_states", self.on_joint_states, 10)
        self.client = ActionClient(
            self, FollowJointTrajectory, "/arm_controller/follow_joint_trajectory"
        )

    def on_joint_states(self, msg):
        if "joint1" in msg.name:
            self.base = msg.position[msg.name.index("joint1")]


def point(positions, t):
    p = JointTrajectoryPoint()
    p.positions = positions
    p.time_from_start = Duration(sec=int(t), nanosec=int((t % 1) * 1e9))
    return p


def main():
    rclpy.init()
    node = Waver()
    log = node.get_logger()

    log.info("Waiting for /joint_states ...")
    while rclpy.ok() and node.base is None:
        rclpy.spin_once(node, timeout_sec=0.1)

    log.info("Waiting for the arm controller ...")
    node.client.wait_for_server()

    b = node.base
    t = 2.0
    points = [point([b, 0.0, 0.0, 0.0], t)]          # init pose
    for _ in range(WAVES):
        t += STEP
        points.append(point([b, 0.0, 0.0, -SWING], t))
        t += STEP
        points.append(point([b, 0.0, 0.0, SWING], t))
    t += 0.5
    points.append(point([b, 0.0, 0.0, 0.0], t))       # back to init pose

    goal = FollowJointTrajectory.Goal()
    goal.trajectory.joint_names = JOINTS
    goal.trajectory.points = points

    log.info("Sending wave ...")
    send_future = node.client.send_goal_async(goal)
    rclpy.spin_until_future_complete(node, send_future)
    handle = send_future.result()
    if not handle.accepted:
        log.error("The arm controller rejected the wave.")
    else:
        result_future = handle.get_result_async()
        rclpy.spin_until_future_complete(node, result_future)
        log.info("Wave finished.")

    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
