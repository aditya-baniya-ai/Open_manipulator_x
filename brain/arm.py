"""
Robo's hands: move the gripper to a point (x, y, z in mm) instead of joint angles.

It works out the 4 joint angles itself (inverse kinematics), checks they're safe,
and moves there. This is what picking things up and the LLM brain build on.

Where the numbers are measured from (mm):
    x  forward from the base         y  to the left         z  up from the table
The point is the middle of the gripper fingertips. "Straight down" means the gripper
points at the table; that's how Robo picks things up (the arm has no wrist twist).

Check the math (no arm needed, works on any computer):
    python3 arm.py test

With the arm (or the simulation) launched (see README.md):
    python3 arm.py where                 where the gripper is now, and the joint angles
    python3 arm.py go 200 0 100          move the gripper to x=200 y=0 z=100, pointing down
    python3 arm.py go 200 0 100 --level  ... pointing forward instead of down
    python3 arm.py home                  back to the home pose

Try every new point in the simulation first (launch/gestures.sh --sim).
"""

import argparse
import math
import sys
from pathlib import Path

# The gesture code (connecting to the arm, sending moves) lives in ../gestures
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "gestures"))

# If the arm's base stands on a plate or board (not straight on the table), put its
# thickness here (mm), so heights are measured from the table
MOUNT_HEIGHT = 0.0

# The arm's sizes, from ROBOTIS's model (open_manipulator_x.urdf.xacro), in mm
BASE_X = 12.0                       # the base turns around a point 12 mm in front of x=0
SHOULDER_Z = MOUNT_HEIGHT + 17.0 + 59.5   # shoulder joint height above the table
UPPER_ARM = (24.0, 128.0)           # shoulder to elbow (forward, up) at the home pose
FOREARM = 124.0                     # elbow to wrist
HAND = 126.0                        # wrist to the middle of the fingertips

TABLE_CLEARANCE = 10.0  # the fingertips never go lower than this above the table (mm)
SPEED = 0.6             # fastest any joint turns (radians a second)
STEP = 10.0             # straight-line moves are split into points this far apart (mm)
STRAIGHT_SPEED = 50.0   # fastest straight-line move (mm a second)
DOWN = math.pi / 2      # gripper pitch: pointing straight down
LEVEL = 0.0             # gripper pitch: pointing forward

UPPER_LENGTH = math.hypot(*UPPER_ARM)
UPPER_LEAN = math.atan2(UPPER_ARM[0], UPPER_ARM[1])   # the upper arm leans forward a bit

# Safe range of each joint (the same as the gesture buttons use)
LIMITS = [(-2.8, 2.8), (-1.5, 1.5), (-1.5, 1.4), (-1.7, 1.9)]


def forward(joints):
    """Where the fingertips are for these joint angles: (x, y, z, pitch).

    pitch is the gripper's angle below level (0 forward, pi/2 straight down).
    """
    j1, j2, j3, j4 = joints
    # Work in the arm's own upright plane: r forward from the base axis, h up
    a = math.pi / 2 - UPPER_LEAN - j2            # upper arm angle above level
    b = -(j2 + j3)                               # forearm angle above level
    pitch = j2 + j3 + j4
    r = UPPER_LENGTH * math.cos(a) + FOREARM * math.cos(b) + HAND * math.cos(pitch)
    h = SHOULDER_Z + UPPER_LENGTH * math.sin(a) + FOREARM * math.sin(b) - HAND * math.sin(pitch)
    return BASE_X + r * math.cos(j1), r * math.sin(j1), h, pitch


def wrist_height(joints):
    a = math.pi / 2 - UPPER_LEAN - joints[1]
    b = -(joints[1] + joints[2])
    return SHOULDER_Z + UPPER_LENGTH * math.sin(a) + FOREARM * math.sin(b)


def problem(joints, z=None, floor=TABLE_CLEARANCE):
    """Why these joint angles aren't safe, or None if they are. Nothing may go lower
    than floor (mm above the table)."""
    for i, (angle, (low, high)) in enumerate(zip(joints, LIMITS)):
        if not low <= angle <= high:
            return f"joint{i + 1} would be at {math.degrees(angle):.0f}°, outside its safe range"
    if z is None:
        z = forward(joints)[2]
    if z < floor:
        return f"that's {z:.0f} mm above the table, lower than {floor:.0f} mm"
    # The wrist must stay above the table too, whichever way the gripper points
    if wrist_height(joints) < floor:
        return "the wrist would hit the table"
    return None


def solve(x, y, z, pitch=DOWN):
    """The joint angles that put the fingertips at (x, y, z) with this pitch.

    Returns (joints, None), or (None, the reason it can't).
    """
    r = math.hypot(x - BASE_X, y)
    j1 = math.atan2(y, x - BASE_X) if r > 1e-6 else 0.0
    # Where the wrist must be so the hand reaches the point at this pitch
    wr = r - HAND * math.cos(pitch)
    wh = z + HAND * math.sin(pitch) - SHOULDER_Z
    reach = math.hypot(wr, wh)
    bend = (reach ** 2 - UPPER_LENGTH ** 2 - FOREARM ** 2) / (2 * UPPER_LENGTH * FOREARM)
    if not -1.0 <= bend <= 1.0:
        return None, "it's too far away" if bend > 1.0 else "it's too close to the base"
    elbow = math.acos(bend)                   # 0 = arm straight; elbow stays above
    a = math.atan2(wh, wr) + math.atan2(FOREARM * math.sin(elbow),
                                        UPPER_LENGTH + FOREARM * math.cos(elbow))
    b = a - elbow
    j2 = math.pi / 2 - UPPER_LEAN - a
    j3 = -b - j2
    j4 = pitch - j2 - j3
    joints = [j1, j2, j3, j4]
    why = problem(joints, z)
    return (None, why) if why else (joints, None)


def solve_any_pitch(x, y, z, pitch=DOWN):
    """Like solve, but if the point can't be reached at this pitch, tilt the gripper
    a bit at a time (up to 40 degrees) until it can. Returns (joints, pitch, reason)."""
    first_reason = None
    for tilt in range(0, 41, 5):
        for p in (pitch - math.radians(tilt), pitch + math.radians(tilt)):
            joints, why = solve(x, y, z, p)
            if joints:
                return joints, p, None
            first_reason = first_reason or why
    return None, None, first_reason


def seconds_for(start, end, at_least=0.5):
    """How long a move takes so no joint turns faster than SPEED."""
    return max(at_least, max(abs(e - s) for s, e in zip(start, end)) / SPEED)


def straight_line(start, end, pitch):
    """Joint angles along a straight line from start (x, y, z) to end, keeping the
    gripper at the same pitch. Returns (list of joint angles, None) or (None, reason)."""
    distance = math.dist(start, end)
    steps = max(1, math.ceil(distance / STEP))
    path = []
    for i in range(1, steps + 1):
        point = [s + (e - s) * i / steps for s, e in zip(start, end)]
        joints, why = solve(*point, pitch)
        if joints is None:
            return None, f"the point {format_point(point)} can't be reached: {why}"
        path.append(joints)
    return path, None


def format_point(point):
    return "(" + ", ".join(f"{v:.0f}" for v in point[:3]) + ") mm"


# --- Moving the real (or simulated) arm -------------------------------------------

def current_joints(node):
    from gestures import JOINTS, catch_up
    catch_up(node)
    return [node.joints[j] for j in JOINTS]


def where(node):
    """Where the fingertips are now: (x, y, z, pitch)."""
    return forward(current_joints(node))


def move_joints(node, path, at_least=0.5):
    """Move through these joint angles (one or more), no joint faster than SPEED.
    at_least: the shortest time for each piece of the move (seconds)."""
    from gestures import move_arm, point
    t, last, points = 0.0, current_joints(node), []
    for joints in path:
        t += seconds_for(last, joints, at_least)
        points.append(point(list(joints), t))
        last = joints
    node.target = None  # the joint buttons start again from wherever this ends
    return move_arm(node, points)


def path_problem(start, end, checks=50):
    """Why moving the joints straight from start to end isn't safe (the gripper would
    pass through the table on the way, for example), or None if it is.
    If the arm starts lower than allowed (after a bow, say), it may move as long as it
    never goes lower than where it started, so it can always get back up."""
    floor = min(TABLE_CLEARANCE, forward(start)[2], wrist_height(start))
    for i in range(1, checks + 1):
        why = problem([s + (e - s) * i / checks for s, e in zip(start, end)], floor=floor)
        if why:
            return why
    return None


def move_joints_safely(node, joints):
    """Move to these joint angles. If the direct way isn't safe, go through the home
    pose (base where it is) first. Returns None, or why it couldn't."""
    start = current_joints(node)
    if path_problem(start, joints) is None:
        return None if move_joints(node, [joints]) else "the arm controller refused"
    home = [start[0], 0.0, 0.0, 0.0]
    if path_problem(start, home) or path_problem(home, joints):
        return "there's no safe way to get there from here"
    return None if move_joints(node, [home, joints]) else "the arm controller refused"


def move_to(node, x, y, z, pitch=DOWN, straight=False):
    """Move the fingertips to (x, y, z) mm. straight=True moves along a straight line
    (for going down to an object and back up). Returns None, or why it couldn't."""
    if straight:
        x0, y0, z0, _ = where(node)
        path, why = straight_line((x0, y0, z0), (x, y, z), pitch)
        if path is None:
            return why
        # At most STRAIGHT_SPEED mm a second, so going down to an object is gentle
        ok = move_joints(node, path, at_least=STEP / STRAIGHT_SPEED)
        return None if ok else "the arm controller refused"
    joints, why = solve(x, y, z, pitch)
    if joints is None:
        return f"{format_point((x, y, z))} can't be reached: {why}"
    return move_joints_safely(node, joints)


# --- Checking the math, without an arm ----------------------------------------------

def self_test():
    """Solve many points, then check forward() lands exactly on each one."""
    import random
    random.seed(1)
    # The home pose (all joints 0) should match the arm's model
    x, y, z, pitch = forward([0, 0, 0, 0])
    print(f"Home pose: fingertips at {format_point((x, y, z))}, pointing forward")
    assert abs(x - (BASE_X + 24 + 124 + 126)) < 1e-6 and abs(z - (SHOULDER_Z + 128)) < 1e-6

    reached = tried = 0
    worst = 0.0
    for _ in range(5000):
        target = (random.uniform(-50, 400), random.uniform(-300, 300), random.uniform(0, 350))
        p = random.choice([DOWN, LEVEL, math.radians(45)])
        joints, _ = solve(*target, p)
        tried += 1
        if joints is None:
            continue
        reached += 1
        fx, fy, fz, fp = forward(joints)
        worst = max(worst, math.dist(target, (fx, fy, fz)), abs(fp - p) * 1000)
    print(f"{reached} of {tried} random points reachable; worst error {worst:.6f} mm")
    assert worst < 1e-6

    # Typical picking points: straight down onto the table in front of the arm
    for r in (120, 160, 200, 240):
        joints, why = solve(r, 0, 20)
        print(f"  down to ({r}, 0, 20): " + (
            ", ".join(f"{math.degrees(j):+.0f}°" for j in joints) if joints else f"no, {why}"))

    path, why = straight_line((200, 0, 90), (200, 0, 20), DOWN)
    assert path, why
    print(f"Straight line down 70 mm: {len(path)} points, all safe")
    home, low = [0.0] * 4, solve(240, 0, 20)[0]
    search = [0.0, math.radians(-52), math.radians(24), math.radians(100)]
    assert path_problem(home, search) is None and path_problem(home, low) is None
    assert path_problem(low, [0.0, 1.0, 0.6, 0.3])   # swings the gripper into the table
    bow = [0.0, 0.6, 0.3, 0.4]   # starts low: may climb out, but not go lower
    assert path_problem(bow, home) is None and path_problem(bow, [0.0, 1.0, 0.6, 0.3])
    print("Path check: catches a move that would swing through the table")
    print("All good.")


def main():
    parser = argparse.ArgumentParser(description="Move the gripper to a point in mm.")
    parser.add_argument("command", choices=["test", "where", "go", "home"])
    parser.add_argument("xyz", nargs="*", type=float, help="x y z in mm (for go)")
    parser.add_argument("--level", action="store_true",
                        help="point the gripper forward instead of down")
    args, ros_args = parser.parse_known_args()

    if args.command == "test":
        self_test()
        return
    if args.command == "go" and len(args.xyz) != 3:
        parser.error("go needs x y z, e.g.  go 200 0 100")

    import rclpy
    from gestures import Gesturer, connect
    rclpy.init(args=ros_args)
    node = Gesturer()
    try:
        if not connect(node):
            return
        if args.command == "where":
            x, y, z, pitch = where(node)
            print(f"Gripper at {format_point((x, y, z))}, "
                  f"pointing {math.degrees(pitch):.0f}° below level")
            print("Joints (base, shoulder, elbow, wrist): " + ", ".join(
                f"{math.degrees(j):.0f}" for j in current_joints(node)) + " degrees")
        elif args.command == "home":
            move_joints_safely(node, [current_joints(node)[0], 0.0, 0.0, 0.0])
        else:
            pitch = LEVEL if args.level else DOWN
            joints, why = solve(*args.xyz, pitch)
            if joints is None:
                print(f"Can't go to {format_point(args.xyz)}: {why}")
                return
            print("Joints: " + ", ".join(f"{math.degrees(j):+.0f}°" for j in joints))
            why = move_joints_safely(node, joints)
            if why:
                print(f"Can't go there: {why}")
                return
            x, y, z, _ = where(node)
            print(f"Arrived at {format_point((x, y, z))}")
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
