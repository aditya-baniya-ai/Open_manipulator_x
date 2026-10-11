"""
Robo's arm for the Puppet Master game: follow the player's hand smoothly, and "whack"
(a quick tap down onto the table and back up).

The game works in "play area" positions (0 to 1, as the player sees the screen) and
this turns them into points in front of Robo, then into joint angles with brain/arm.py
(which also checks every point is safe).

    RealArm     the real arm, or the simulated one in RViz (through ROS)
    VirtualArm  no robot at all: a pretend arm that behaves like the real one
                (same speed limit and delay), to try the game on any computer
"""

import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "brain"))
import arm  # noqa: E402  (also makes ../gestures importable)

HOVER_HEIGHT = 60.0      # mm: fingertips this high while moving around
TOUCH_HEIGHT = 20.0      # mm: fingertips this high at the bottom of a whack
NEAR, FAR = 120.0, 220.0  # mm: closest and farthest the gripper goes from the base
SIDE = math.radians(55)  # the furthest the base turns left or right
MAX_SPEED = 1.5          # rad/s: fastest any joint moves while following the hand
MAX_GLIDE = 250.0        # mm/s: fastest the gripper slides across the table
WHACK_TIME = 0.30        # seconds down, and the same back up
GRAB_HEIGHT = 15.0       # mm: fingertips this high to grab a ball off the table
RELEASE_HEIGHT = 40.0    # mm: fingertips this high to let go of a ball
GRIPPER_WAIT = 0.6       # seconds for the gripper to close or open
LAG = 0.12               # seconds the pretend arm trails behind (like the real one)


def area_to_point(u, v):
    """Play-area position to a point on the table in front of Robo (x, y in mm).

    Robo faces the player, so the player's right (u = 1) is Robo's left (+y), and the
    top of the screen (v = 0) is near Robo, the bottom (v = 1) near the player."""
    angle = (u - 0.5) * 2 * SIDE
    reach = NEAR + v * (FAR - NEAR)
    return arm.BASE_X + reach * math.cos(angle), reach * math.sin(angle)


def point_to_area(x, y):
    """The opposite of area_to_point (for drawing where the gripper is)."""
    reach = math.hypot(x - arm.BASE_X, y)
    angle = math.atan2(y, x - arm.BASE_X)
    return 0.5 + angle / (2 * SIDE), (reach - NEAR) / (FAR - NEAR)


def limit_step(start, goal, seconds):
    """Move from start toward goal, no joint faster than MAX_SPEED."""
    most = MAX_SPEED * seconds
    return [s + max(-most, min(most, g - s)) for s, g in zip(start, goal)]


class ArmBase:
    """What both arms share: following, whacking, and where the gripper is."""

    def __init__(self, touch_height):
        self.touch_height = touch_height
        self.command = None          # joint angles last sent
        self.aim = None              # the point (x, y mm) the gripper is sliding to
        self.whack_started = None    # time the current whack began, or None
        self.whack_spot = None       # where the gripper was when it whacked (x, y)
        self.whack_checked = True    # the current whack has been checked for a hit
        self.last_follow = time.monotonic()
        self.steps = []              # (time, what to do) for grab and release
        self.busy_until = 0.0        # the arm is grabbing or releasing until then
        self.closed = False          # the gripper is closed (holding, or tried to)

    def whacking(self):
        return self.whack_started is not None and \
            time.monotonic() - self.whack_started < 2 * WHACK_TIME

    def busy(self):
        """Whacking, grabbing or releasing: the arm doesn't follow the hand meanwhile."""
        return self.whacking() or time.monotonic() < self.busy_until

    def follow(self, u, v):
        """Move toward this play-area position (does nothing while busy)."""
        now = time.monotonic()
        seconds, self.last_follow = min(0.1, now - self.last_follow), now
        if self.busy() or self.command is None:
            return
        # Slide the gripper level toward the hand's point (a straight, flat path, so a
        # carried ball can't sag into the others), no faster than MAX_GLIDE ...
        if self.aim is None:
            self.aim = arm.forward(self.command)[:2]
        gx, gy = area_to_point(u, v)
        distance = math.hypot(gx - self.aim[0], gy - self.aim[1])
        share = min(1.0, MAX_GLIDE * seconds / distance) if distance > 0 else 1.0
        # ... and no joint faster than MAX_SPEED: if a joint would have to (the base,
        # moving sideways close to it), take a shorter step instead, so all the joints
        # stay in step and the gripper stays level
        goal = None
        for _ in range(4):
            aim = (self.aim[0] + (gx - self.aim[0]) * share,
                   self.aim[1] + (gy - self.aim[1]) * share)
            goal, _ = arm.solve(*aim, HOVER_HEIGHT)
            if goal is None:
                return
            fastest = max(abs(g - c) for g, c in zip(goal, self.command)) / max(seconds, 1e-3)
            if fastest <= MAX_SPEED:
                break
            share *= 0.95 * MAX_SPEED / fastest
        self.aim = aim
        self.command = limit_step(self.command, goal, seconds)   # (a last safety net)
        self.send([self.command], [max(0.1, seconds * 2)])

    def whack(self):
        """Tap straight down where the gripper is now, and back up. Returns False if
        it's already whacking."""
        if self.whacking() or self.command is None:
            return False
        x, y, _, _ = arm.forward(self.command)
        down, why = arm.solve(x, y, self.touch_height)
        if down is None:
            return False
        self.whack_started = time.monotonic()
        self.whack_checked = False
        self.whack_spot = (x, y)
        self.send([down, self.command], [WHACK_TIME, 2 * WHACK_TIME])
        return True

    def grab(self, height=GRAB_HEIGHT):
        """Go down, close the gripper, come back up (without freezing the game: the
        steps happen in run_steps). Returns False if it can't right now."""
        return self.down_and_up(height, closed=True)

    def release(self, height=RELEASE_HEIGHT):
        """Go down a little, open the gripper, come back up."""
        return self.down_and_up(height, closed=False)

    def down_and_up(self, height, closed):
        if self.busy() or self.command is None:
            return False
        x, y, _, _ = arm.forward(self.command)
        down, _ = arm.solve(x, y, height)
        if down is None:
            return False
        now = time.monotonic()
        up = list(self.command)
        self.send([down], [0.45])
        self.steps = [(now + 0.5, lambda: self.set_gripper(closed)),
                      (now + 0.5 + GRIPPER_WAIT, lambda: self.send([up], [0.45]))]
        self.busy_until = now + 1.0 + GRIPPER_WAIT
        return True

    def run_steps(self):
        """Do the grab/release steps that are due (call every frame)."""
        now = time.monotonic()
        while self.steps and now >= self.steps[0][0]:
            self.steps.pop(0)[1]()

    def bottom_of_whack(self):
        """True once, when the current whack reaches the table: the moment to check
        for a hit."""
        if self.whack_checked or time.monotonic() - self.whack_started < WHACK_TIME + LAG:
            return False
        self.whack_checked = True
        return True

    def gripper_area(self):
        """Where the gripper really is now, as a play-area position."""
        x, y, z, _ = arm.forward(self.joints())
        u, v = point_to_area(x, y)
        return u, v, z


class VirtualArm(ArmBase):
    """A pretend arm: follows its commands with a delay and the same speed limit."""

    name = "virtual arm"

    def __init__(self, touch_height=TOUCH_HEIGHT):
        super().__init__(touch_height)
        self.state = None
        self.plan = []           # (time, joints) still to reach
        self.updated = time.monotonic()

    def start(self):
        goal, _ = arm.solve(*area_to_point(0.5, 0.5), HOVER_HEIGHT)
        self.state = list(goal)
        self.command = list(goal)
        self.updated = time.monotonic()
        return None

    def send(self, path, times):
        now = time.monotonic()
        self.plan = [(now + t, list(j)) for j, t in zip(path, times)]

    def joints(self):
        now = time.monotonic()
        seconds, self.updated = now - self.updated, now
        while len(self.plan) > 1 and now >= self.plan[0][0]:
            self.plan.pop(0)
        if self.plan:
            goal = self.plan[0][1]
            # Ease toward the goal like a real servo (a little behind, speed-limited)
            eased = [s + (g - s) * min(1.0, seconds / LAG) for s, g in zip(self.state, goal)]
            self.state = limit_step(self.state, eased, seconds * 2.5)
        return self.state

    def set_gripper(self, closed):
        self.closed = closed

    def update(self):
        self.run_steps()

    def stop(self):
        pass


class RealArm(ArmBase):
    """The real arm (or the simulated one), through ROS."""

    name = "Robo's arm"

    def __init__(self, touch_height=TOUCH_HEIGHT, ros_args=None):
        super().__init__(touch_height)
        import rclpy
        from gestures import Gesturer
        rclpy.init(args=ros_args)
        self.rclpy = rclpy
        self.node = Gesturer()

    def start(self):
        """Check the arm, then move to the middle of the play area.
        Returns None, or why it can't start."""
        from gestures import connect
        if not connect(self.node):
            return "the arm isn't ready (see the messages above)"
        goal, why = arm.solve(*area_to_point(0.5, 0.5), HOVER_HEIGHT)
        why = why or arm.move_joints_safely(self.node, goal)
        if why:
            return why
        self.command = list(goal)
        self.node.gripper.wait_for_server(timeout_sec=2.0)
        self.set_gripper(False)
        return None

    def set_gripper(self, closed):
        """Open or close the gripper without waiting for it."""
        from control_msgs.action import GripperCommand
        from gestures import GRIPPER_POSITION
        goal = GripperCommand.Goal()
        goal.command.position = GRIPPER_POSITION["close" if closed else "open"]
        goal.command.max_effort = 100.0
        self.node.gripper.send_goal_async(goal)
        self.closed = closed

    def send(self, path, times):
        from gestures import JOINTS, point
        from trajectory_msgs.msg import JointTrajectory
        msg = JointTrajectory()
        msg.joint_names = JOINTS
        msg.points = [point(list(j), t) for j, t in zip(path, times)]
        self.node.jog_pub.publish(msg)

    def update(self):
        """Read new joint angles (call every frame)."""
        for _ in range(5):
            self.rclpy.spin_once(self.node, timeout_sec=0.0)
        self.run_steps()

    def joints(self):
        from gestures import JOINTS
        return [self.node.joints[j] for j in JOINTS]

    def stop(self):
        """Back to the home pose, then disconnect."""
        try:
            if self.command is not None:
                arm.move_joints_safely(self.node, [self.joints()[0], 0.0, 0.0, 0.0])
        finally:
            self.node.destroy_node()
            if self.rclpy.ok():
                self.rclpy.shutdown()
