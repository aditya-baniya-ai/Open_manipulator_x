"""
Keyboard-triggered gestures for OpenMANIPULATOR-X (ROS 2).

Run it while the arm is launched (see docs/setup_jetson.md):
    python3 gestures.py

Then press a key:
    w  wave        n  nod (yes)    s  shake (no)
    b  bow         l  look around  h  go home
    q  quit

Every gesture starts and ends at the home pose (joints 2-4 at 0 rad, the same
pose as the Arduino greeting). The base (joint1) stays facing wherever it is now;
shake and look-around turn it relative to that direction and come back.
"""

import sys
import termios
import tty

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from control_msgs.action import FollowJointTrajectory
from trajectory_msgs.msg import JointTrajectoryPoint
from sensor_msgs.msg import JointState
from builtin_interfaces.msg import Duration

JOINTS = ["joint1", "joint2", "joint3", "joint4"]
BASE_LIMIT = 2.8   # radians, keep the base away from its end stops
HOME_TIME = 1.5    # seconds to reach the home pose before each gesture

# Each gesture is a list of moves: (base turn, joint2, joint3, joint4, seconds).
#   base turn: radians, relative to where the base faces now
#   joint2 shoulder, joint3 elbow, joint4 wrist: radians, 0 = home pose
#   seconds: time to get from the previous move to this one
# If a gesture moves the wrong way on your arm, flip the sign of that number.
GESTURES = {
    "w": ("wave", [
        (0.0, 0.0, 0.0, -0.6, 0.6),
        (0.0, 0.0, 0.0, 0.6, 0.6),
    ] * 3),
    "n": ("nod", [
        (0.0, 0.0, 0.0, 0.5, 0.4),
        (0.0, 0.0, 0.0, -0.1, 0.4),
    ] * 2),
    "s": ("shake", [
        (-0.4, 0.0, 0.0, 0.0, 0.5),
        (0.4, 0.0, 0.0, 0.0, 0.8),
    ] * 2),
    "b": ("bow", [
        (0.0, 0.6, 0.3, 0.4, 1.5),   # lean forward
        (0.0, 0.6, 0.3, 0.4, 1.0),   # hold
    ]),
    "l": ("look around", [
        (0.8, 0.0, 0.0, 0.3, 1.5),   # turn left, look down a little
        (0.8, 0.0, 0.0, 0.3, 0.8),   # hold
        (-0.8, 0.0, 0.0, 0.3, 2.5),  # turn right
        (-0.8, 0.0, 0.0, 0.3, 0.8),  # hold
    ]),
    "h": ("home", []),
}


class Gesturer(Node):
    def __init__(self):
        super().__init__("gesturer")
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


def build_trajectory(base, moves):
    """Home pose, then the gesture's moves, then back to the home pose."""
    t = HOME_TIME
    points = [point([base, 0.0, 0.0, 0.0], t)]
    for turn, j2, j3, j4, seconds in moves:
        t += seconds
        b = max(-BASE_LIMIT, min(BASE_LIMIT, base + turn))
        points.append(point([b, j2, j3, j4], t))
    if moves:
        t += 1.0
        points.append(point([base, 0.0, 0.0, 0.0], t))
    return points


def run_gesture(node, moves):
    # Catch up on /joint_states so we use where the base faces right now
    for _ in range(20):
        rclpy.spin_once(node, timeout_sec=0.0)

    goal = FollowJointTrajectory.Goal()
    goal.trajectory.joint_names = JOINTS
    goal.trajectory.points = build_trajectory(node.base, moves)

    send_future = node.client.send_goal_async(goal)
    rclpy.spin_until_future_complete(node, send_future)
    handle = send_future.result()
    if not handle.accepted:
        node.get_logger().error("The arm controller rejected the gesture.")
        return
    result_future = handle.get_result_async()
    rclpy.spin_until_future_complete(node, result_future)


def read_key():
    """Wait for one key press, without needing Enter."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        return sys.stdin.read(1).lower()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def print_menu():
    print("\nPress a key:")
    for key, (name, _) in GESTURES.items():
        print(f"  {key}  {name}")
    print("  q  quit")


def main():
    rclpy.init()
    node = Gesturer()
    log = node.get_logger()

    log.info("Waiting for /joint_states ...")
    while rclpy.ok() and node.base is None:
        rclpy.spin_once(node, timeout_sec=0.1)

    log.info("Waiting for the arm controller ...")
    node.client.wait_for_server()

    try:
        while rclpy.ok():
            print_menu()
            key = read_key()
            if key == "q":
                break
            if key not in GESTURES:
                continue
            name, moves = GESTURES[key]
            log.info(f"{name} ...")
            run_gesture(node, moves)
            # Ignore keys pressed while the arm was moving
            termios.tcflush(sys.stdin, termios.TCIFLUSH)
    except KeyboardInterrupt:
        pass

    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
