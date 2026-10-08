"""
Keyboard-triggered gestures for OpenMANIPULATOR-X (ROS 2).

Run it while the arm (or the simulation) is launched (see README.md):
    python3 gestures.py

Then press a key:
    w  wave        n  nod (yes)    s  shake (no)
    b  bow         l  look around  h  go home
    q  quit

Move each joint a little (hold the key to keep moving):
    1/2  base     3/4  shoulder     5/6  elbow     7/8  wrist
    o    open the gripper           c    close the gripper

Record your own move (move the joints between poses):
    p  add the current pose to the move
    k  keep the move: type a name and a key to play it with
    x  throw away the poses recorded so far

Saved moves go in my_gestures.json next to this file and load every time.

Every gesture starts and ends at the home pose (joints 2-4 at 0 rad, the same
pose as the Arduino greeting). The base (joint1) stays facing wherever it is now;
shake and look-around turn it relative to that direction and come back.
"""

import json
import sys
import termios
import tty
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from control_msgs.action import FollowJointTrajectory, GripperCommand
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
BUILT_IN = set(GESTURES)
RECORD_KEYS = {"p", "k", "x", "q", "o", "c"}

# Gripper finger positions, the same values ROBOTIS's teleop uses
GRIPPER = {"o": ("open", 0.019), "c": ("close", -0.01)}

# Keys that nudge one joint: key -> (joint index, direction)
JOG_KEYS = {
    "1": (0, -1), "2": (0, 1),   # base
    "3": (1, -1), "4": (1, 1),   # shoulder
    "5": (2, -1), "6": (2, 1),   # elbow
    "7": (3, -1), "8": (3, 1),   # wrist
}
JOG_STEP = 0.05   # radians per key press, about 3 degrees
JOG_TIME = 0.2    # seconds for each nudge
# Safe range for each joint, in radians
LIMITS = [(-BASE_LIMIT, BASE_LIMIT), (-1.5, 1.5), (-1.5, 1.4), (-1.7, 1.9)]
SAVED_FILE = Path(__file__).with_name("my_gestures.json")


class Gesturer(Node):
    def __init__(self):
        super().__init__("gesturer")
        self.base = None
        self.joints = {}       # latest angle of every joint, by name
        self.home_base = None  # where the base faced at the last home pose
        self.recording = []    # poses added with p, not saved yet
        self.target = None     # where the number keys are moving the joints to
        self.create_subscription(JointState, "/joint_states", self.on_joint_states, 10)
        self.client = ActionClient(
            self, FollowJointTrajectory, "/arm_controller/follow_joint_trajectory"
        )
        self.gripper = ActionClient(self, GripperCommand, "/gripper_controller/gripper_cmd")

    def on_joint_states(self, msg):
        self.joints.update(zip(msg.name, msg.position))
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


def catch_up(node):
    """Read any waiting /joint_states messages so the angles are current."""
    for _ in range(20):
        rclpy.spin_once(node, timeout_sec=0.0)


def record_pose(node):
    """Add the current pose to the move being recorded."""
    catch_up(node)
    turn = node.base - node.home_base
    j2, j3, j4 = (node.joints[j] for j in JOINTS[1:])
    pose = [round(v, 2) for v in (turn, j2, j3, j4)] + [1.0]
    node.recording.append(pose)
    print(f"Pose {len(node.recording)} added: {tuple(pose)}")
    print("Move the arm and press p again, or press k to save the move.")


def load_saved():
    """Add the moves saved in my_gestures.json to GESTURES."""
    if not SAVED_FILE.exists():
        return
    for key, g in json.loads(SAVED_FILE.read_text()).items():
        GESTURES[key] = (g["name"], [tuple(m) for m in g["moves"]])


def write_saved(saved):
    """Write my_gestures.json with one pose per line, so it's easy to edit."""
    parts = []
    for key, g in saved.items():
        moves = ",\n      ".join(json.dumps(m) for m in g["moves"])
        parts.append(
            f'  {json.dumps(key)}: {{\n'
            f'    "name": {json.dumps(g["name"])},\n'
            f'    "moves": [\n      {moves}\n    ]\n  }}'
        )
    SAVED_FILE.write_text("{\n" + ",\n".join(parts) + "\n}\n")


def key_problem(key):
    """Return why a key can't be used for a saved move, or None if it's fine."""
    if len(key) != 1 or not key.isalpha():
        return "Please use one letter."
    if key in BUILT_IN or key in RECORD_KEYS:
        return f"'{key}' is already used. Try another."
    return None


def save_recording(node, name, key):
    """Save the recorded poses as a move called name, played with key."""
    GESTURES[key] = (name, [tuple(m) for m in node.recording])
    saved = json.loads(SAVED_FILE.read_text()) if SAVED_FILE.exists() else {}
    saved[key] = {"name": name, "moves": node.recording}
    write_saved(saved)
    node.recording = []


def save_move(node):
    """Ask for a name and a key, then save the recorded poses as a move."""
    if not node.recording:
        print("Nothing recorded yet. Press p to add poses first.")
        return
    name = input("Name for this move: ").strip() or "my move"
    while True:
        key = input("Key to play it (one letter): ").strip().lower()
        problem = key_problem(key)
        if problem is None:
            break
        print(problem)

    save_recording(node, name, key)
    print(f"Saved '{name}'. Press {key} to play it.")


def move_gripper(node, position):
    """Open or close the gripper, without waiting for it to finish."""
    if not node.gripper.wait_for_server(timeout_sec=1.0):
        node.get_logger().error("The gripper controller isn't running.")
        return
    goal = GripperCommand.Goal()
    goal.command.position = position
    goal.command.max_effort = 100.0
    rclpy.spin_until_future_complete(node, node.gripper.send_goal_async(goal))


def jog(node, joint, direction):
    """Nudge one joint a little, without waiting for it to finish."""
    catch_up(node)
    if node.target is None:
        node.target = [node.joints[j] for j in JOINTS]
    low, high = LIMITS[joint]
    node.target[joint] = min(high, max(low, node.target[joint] + direction * JOG_STEP))

    goal = FollowJointTrajectory.Goal()
    goal.trajectory.joint_names = JOINTS
    goal.trajectory.points = [point(list(node.target), JOG_TIME)]
    rclpy.spin_until_future_complete(node, node.client.send_goal_async(goal))


def run_gesture(node, moves):
    catch_up(node)
    node.home_base = node.base
    node.target = None  # number keys start again from wherever the gesture ends

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
    print("Move joints:   1/2 base, 3/4 shoulder, 5/6 elbow, 7/8 wrist")
    print("Gripper:       o open, c close")
    print("Record a move: p add pose, k keep (save), x start over")


def main():
    load_saved()
    rclpy.init()
    node = Gesturer()
    log = node.get_logger()

    log.info("Waiting for /joint_states ...")
    while rclpy.ok() and node.base is None:
        rclpy.spin_once(node, timeout_sec=0.1)

    log.info("Waiting for the arm controller ...")
    node.client.wait_for_server()
    node.home_base = node.base

    try:
        print_menu()
        while rclpy.ok():
            key = read_key()
            if key == "q":
                break
            if key in JOG_KEYS:
                jog(node, *JOG_KEYS[key])
                continue
            if key in GRIPPER:
                name, position = GRIPPER[key]
                print(f"Gripper {name}")
                move_gripper(node, position)
                continue
            if key == "p":
                record_pose(node)
                continue
            if key == "k":
                save_move(node)
                print_menu()
                continue
            if key == "x":
                node.recording = []
                print("Recording cleared.")
                continue
            if key not in GESTURES:
                continue
            name, moves = GESTURES[key]
            log.info(f"{name} ...")
            run_gesture(node, moves)
            # Ignore keys pressed while the arm was moving
            termios.tcflush(sys.stdin, termios.TCIFLUSH)
            print_menu()
    except KeyboardInterrupt:
        pass

    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
