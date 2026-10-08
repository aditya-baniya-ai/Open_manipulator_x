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
import math
import sys
import termios
import time
import tty
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from control_msgs.action import FollowJointTrajectory, GripperCommand
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from sensor_msgs.msg import JointState
from builtin_interfaces.msg import Duration

JOINTS = ["joint1", "joint2", "joint3", "joint4"]
BASE_LIMIT = 2.8   # radians, keep the base away from its end stops
HOME_TIME = 1.5    # seconds to reach the home pose before each gesture

# Each gesture is a list of moves: (base turn, joint2, joint3, joint4, seconds).
#   base turn: radians, relative to where the base faces now
#   joint2 shoulder, joint3 elbow, joint4 wrist: radians, 0 = home pose
#   seconds: time to get from the previous move to this one
# A move can have a 6th value, "open" or "close": the gripper does that once the arm
# reaches the pose (only when it changes from the pose before).
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
GRIPPER_POSITION = {name: position for name, position in GRIPPER.values()}
GRIPPER_TIME = 1.0  # seconds to wait for the gripper to open or close

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
        # Joint nudges go straight to the controller's topic: quicker than an action
        self.jog_pub = self.create_publisher(JointTrajectory, "/arm_controller/joint_trajectory", 10)

    def on_joint_states(self, msg):
        self.joints.update(zip(msg.name, msg.position))
        if "joint1" in msg.name:
            self.base = msg.position[msg.name.index("joint1")]


def point(positions, t):
    p = JointTrajectoryPoint()
    p.positions = positions
    p.time_from_start = Duration(sec=int(t), nanosec=int((t % 1) * 1e9))
    return p


def build_trajectory(base, moves, start_home=True, end_home=True):
    """Home pose, then the moves, then back to the home pose."""
    t, points = 0.0, []
    if start_home:
        t = HOME_TIME
        points.append(point([base, 0.0, 0.0, 0.0], t))
    for turn, j2, j3, j4, seconds, *_ in moves:
        t += seconds
        b = max(-BASE_LIMIT, min(BASE_LIMIT, base + turn))
        points.append(point([b, j2, j3, j4], t))
    if end_home and (moves or not start_home):
        t += 1.0
        points.append(point([base, 0.0, 0.0, 0.0], t))
    return points


def split_at_gripper(moves):
    """Split a gesture into arm segments, each followed by a gripper action (or None).

    The arm moves smoothly through each segment; the gripper acts in between.
    """
    segments, current, last = [], [], None
    for move in moves:
        current.append(move)
        grip = move[5] if len(move) > 5 else None
        if grip is not None and grip != last:
            segments.append((current, grip))
            current, last = [], grip
    # The last part returns home, even when the last pose ended with a gripper action
    segments.append((current, None))
    return segments


def catch_up(node):
    """Read any waiting messages (like /joint_states) so the angles are current."""
    for _ in range(50):
        rclpy.spin_once(node, timeout_sec=0.0)


def record_pose(node):
    """Add the current pose to the move being recorded."""
    catch_up(node)
    turn = node.base - node.home_base
    j2, j3, j4 = (node.joints[j] for j in JOINTS[1:])
    pose = [round(v, 2) for v in (turn, j2, j3, j4)] + [1.0]
    grip = node.joints.get("gripper_left_joint")
    if grip is not None:
        # Remember the gripper too: open if it's past halfway open
        pose.append("open" if grip > 0.0045 else "close")
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


def move_gripper(node, position, wait=False):
    """Open or close the gripper. With wait=True, give it time to finish first."""
    if not node.gripper.wait_for_server(timeout_sec=1.0):
        node.get_logger().error("The gripper controller isn't running.")
        return
    goal = GripperCommand.Goal()
    goal.command.position = position
    goal.command.max_effort = 100.0
    rclpy.spin_until_future_complete(node, node.gripper.send_goal_async(goal))
    if wait:
        # Holding an object, the gripper stops early, so wait a set time instead
        end = time.monotonic() + GRIPPER_TIME
        while time.monotonic() < end:
            rclpy.spin_once(node, timeout_sec=0.05)


def jog(node, joint, direction):
    """Nudge one joint a little, without waiting for it to finish."""
    catch_up(node)
    if node.target is None:
        node.target = [node.joints[j] for j in JOINTS]
    now = node.target[joint]
    low, high = LIMITS[joint]
    # Stop at the limit, but never push a joint the other way (it may start past it)
    if direction < 0:
        node.target[joint] = max(now - JOG_STEP, min(now, low))
    else:
        node.target[joint] = min(now + JOG_STEP, max(now, high))

    msg = JointTrajectory()
    msg.joint_names = JOINTS
    msg.points = [point(list(node.target), JOG_TIME)]
    node.jog_pub.publish(msg)


JOINT_LABELS = ["Base", "Shoulder", "Elbow", "Wrist"]


def connect(node):
    """Wait for the arm, then check every joint is in its safe range.

    Returns True when it's safe to move. If the arm slumped while the power was off
    (or was turned too far by hand), says which joint is out and how to fix it.
    """
    print("Waiting for the arm ...")
    while rclpy.ok() and not all(j in node.joints for j in JOINTS):
        rclpy.spin_once(node, timeout_sec=0.1)
    node.client.wait_for_server()
    catch_up(node)
    node.home_base = node.base

    # Two arms (e.g. a leftover simulation plus the real arm) mix their joint angles
    # and the arm shakes, so don't move anything while more than one is running
    arms = node.count_publishers("/joint_states")
    if arms > 1:
        print(f"\n{arms} arm programs are running at once (real and/or simulated), so the")
        print("arm won't be moved: their angles would mix and the arm would shake.")
        print("Stop them all (hold the real arm first), then start just one:")
        print("  ~/Documents/Open_manipulator_x/launch/stop.sh\n")
        return False
    # Our own joint buttons are one sender; any other (like a leftover MoveIt Servo)
    # keeps sending its own "hold here" commands and the arm shakes
    senders = node.count_publishers("/arm_controller/joint_trajectory")
    if senders > 1:
        print("\nSomething else (probably MoveIt Servo from servo.launch.py) is also sending")
        print("commands to the arm, so it won't be moved: the arm would shake.")
        print("Stop it first:  ~/Documents/Open_manipulator_x/launch/stop.sh\n")
        return False

    problems = []
    for label, joint, (low, high) in zip(JOINT_LABELS, JOINTS, LIMITS):
        angle = node.joints[joint]
        if not low <= angle <= high:
            problems.append(f"  {label} is at {math.degrees(angle):+.0f}°, "
                            f"safe range is {math.degrees(low):+.0f}° to {math.degrees(high):+.0f}°")
    if problems:
        print("\nThe arm is outside its safe range, so it won't be moved:")
        print("\n".join(problems))
        print("\nTo fix it: hold the arm and turn the 12 V off. Move the arm by hand so it")
        print("stands straight up with the base facing forward. Keep holding it while you")
        print("turn the 12 V back on, then start again.\n")
        return False
    print("Arm ready.")
    return True


def move_arm(node, points):
    """Send the arm along these points and wait until it gets there."""
    goal = FollowJointTrajectory.Goal()
    goal.trajectory.joint_names = JOINTS
    goal.trajectory.points = points

    send_future = node.client.send_goal_async(goal)
    rclpy.spin_until_future_complete(node, send_future)
    handle = send_future.result()
    if not handle.accepted:
        node.get_logger().error("The arm controller rejected the gesture.")
        return False
    rclpy.spin_until_future_complete(node, handle.get_result_async())
    return True


def run_gesture(node, moves):
    catch_up(node)
    node.home_base = base = node.base
    node.target = None  # number keys start again from wherever the gesture ends

    segments = split_at_gripper(moves)
    for i, (part, grip) in enumerate(segments):
        points = build_trajectory(base, part, start_home=(i == 0),
                                  end_home=(i == len(segments) - 1))
        if points and not move_arm(node, points):
            return
        if grip is not None:
            move_gripper(node, GRIPPER_POSITION[grip], wait=True)


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

    if not connect(node):
        node.destroy_node()
        rclpy.shutdown()
        return

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
