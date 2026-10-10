"""
Pick something up with the camera on the gripper (no LLM yet).

  1. Look:   point the gripper (and its camera) down at the table and find the object
             with YOLO-World (it understands any name: "block", "glue stick", ...).
  2. Center: move over the object a little at a time, looking again after each move,
             until it's right under the fingers.
  3. Grab:   open, go straight down, close, and check the gripper is holding something.
  4. Lift it, wait for Enter, then put it back down where it was.

Teach it once first (1 minute): it learns where an object right under the fingers
shows up in the camera picture, and which way the picture moves when the arm moves.
That's saved in camera.json next to this file. Teach again if the camera is moved.

Start the arm and the camera first (see README.md, "Pick things up"), then:
    python3 pick.py teach            follow the steps it prints
    python3 pick.py look block       only look, from high up: live camera (q to close)
    python3 pick.py pick block       pick the block up
    python3 pick.py pick "glue stick"

Options:
    --grab-height 15   how high the fingertips go to grab (mm above the table)
    --conf 0.1         how sure YOLO-World must be (0-1)
    --no-window        don't show the camera window
"""

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "perception"))
import arm  # noqa: E402  (also makes ../gestures importable)

CALIBRATION = HERE / "camera.json"
WORLD_MODEL = "yolov8s-worldv2.pt"

# Search pose: the camera as high as it gets, looking down at the whole pick-up area
# (about 50-300 mm in front of the base, 160 mm to each side). Joint angles in degrees:
# shoulder leaning back, elbow, wrist bent down; the base faces forward.
SEARCH_POSE = (0.0, -52.0, 24.0, 100.0)
LOOK_HEIGHT = 80.0     # fingertips this high (mm) while looking straight down
LOOK_SPOT = (180.0, 0.0)          # where the gripper looks first (x, y mm)
SEARCH_TURNS = [0.0, 0.5, -0.5, 1.0, -1.0]   # base turns (radians) to look around
TEACH_SPOT = (180.0, 0.0)         # where the object is put while teaching
TEACH_GRAB_HEIGHT = 40.0          # fingertips this high while you place the object
TEACH_SHIFT = 30.0                # mm the arm moves while teaching
CLOSE_ENOUGH = 4.0     # mm: centered when the object is this close to the grab spot
MAX_TRIES = 8          # centering moves before giving up
LONGEST_STEP = 60.0    # mm: the most one centering move goes
HOLDING = -0.006       # gripper position: closed further than this means it's empty
SETTLE = 0.4           # seconds to let the arm stop shaking before looking
WINDOW = "Robo's gripper camera (yellow cross: grab spot, q: close)"


# --- Seeing -----------------------------------------------------------------------

class Eyes:
    """Camera pictures (from /image_raw) and YOLO-World."""

    def __init__(self, node, conf, window):
        from rclpy.qos import qos_profile_sensor_data
        from sensor_msgs.msg import Image
        from ultralytics import YOLO
        self.node, self.conf, self.window = node, conf, window
        self.msg = None
        node.create_subscription(Image, "/image_raw", self.on_image, qos_profile_sensor_data)
        print(f"Loading {WORLD_MODEL} ...")
        # Kept in the home folder (like detect.py does), so it downloads only once
        os.chdir(Path.home())
        self.model = YOLO(WORLD_MODEL)
        self.name = None
        self.key = None    # the last key pressed in the window

    def on_image(self, msg):
        self.msg = msg

    def picture(self, settle=True):
        """A fresh camera picture, taken after the arm has stopped moving
        (settle=False: right away, for live video)."""
        import rclpy
        from detect import to_bgr
        end = time.monotonic() + (SETTLE if settle else 0.0)
        while time.monotonic() < end:
            rclpy.spin_once(self.node, timeout_sec=0.05)
        self.msg = None
        end = time.monotonic() + 5.0
        while self.msg is None:
            if time.monotonic() > end:
                raise RuntimeError("No camera pictures on /image_raw. Is the camera running?")
            rclpy.spin_once(self.node, timeout_sec=0.05)
        return to_bgr(self.msg)

    def find(self, name, grab_spot=None, settle=True):
        """Look for name in a fresh picture. Returns its centre (x, y) in pixels and how
        sure YOLO is, or None. Shows the picture in a window, if that's on."""
        import cv2
        if name != self.name:
            self.model.set_classes([name])
            self.name = name
        image = self.picture(settle)
        result = self.model(image, conf=self.conf, verbose=False)[0]
        found = None
        if len(result.boxes):
            best = int(result.boxes.conf.argmax())
            x1, y1, x2, y2 = result.boxes.xyxy[best].tolist()
            found = ((x1 + x2) / 2, (y1 + y2) / 2), float(result.boxes.conf[best])
        if self.window:
            shown = result.plot()
            if grab_spot:
                spot = tuple(int(v) for v in grab_spot)
                cv2.drawMarker(shown, spot, (0, 255, 255), cv2.MARKER_CROSS, 30, 2)
            cv2.imshow(WINDOW, shown)
            # The window only draws while OpenCV gets time to update it
            self.key = cv2.waitKey(100 if settle else 1) & 0xFF
        return found


# --- Teaching: where things look in the picture -------------------------------------

def to_gripper_frame(dx, dy, base):
    """A move in x, y (mm) as (along the arm, sideways) for a base facing base radians."""
    return (dx * math.cos(base) + dy * math.sin(base),
            -dx * math.sin(base) + dy * math.cos(base))


def from_gripper_frame(along, side, base):
    return (along * math.cos(base) - side * math.sin(base),
            along * math.sin(base) + side * math.cos(base))


def solve2(m, v):
    """Solve the 2x2 system m @ x = v."""
    (a, b), (c, d) = m
    det = a * d - b * c
    return ((d * v[0] - b * v[1]) / det, (-c * v[0] + a * v[1]) / det)


def object_offset(calibration, pixel):
    """How far (mm, along the arm and sideways) the object is from right under the
    fingers, from where it shows up in the picture."""
    gx, gy = calibration["grab_spot"]
    return solve2(calibration["pixels_per_mm"], (pixel[0] - gx, pixel[1] - gy))


def teach(node, eyes, name, grab_height):
    from gestures import GRIPPER_POSITION, move_gripper
    x, y = TEACH_SPOT
    print(f"Teaching with a {name}. Keep hands clear while the arm moves.")
    if arm.move_to(node, x, y, LOOK_HEIGHT) or \
            arm.move_to(node, x, y, TEACH_GRAB_HEIGHT, straight=True):
        print("Couldn't reach the teaching spot.")
        return
    move_gripper(node, GRIPPER_POSITION["open"], wait=True)
    input(f"\nPut the {name} on the table between the open fingers, right under them,"
          "\nthen take your hand away and press Enter ...")
    # Go down to grabbing height; closing and opening the gripper there pushes the
    # object to the exact middle
    arm.move_to(node, x, y, grab_height, straight=True)
    move_gripper(node, GRIPPER_POSITION["close"], wait=True)
    move_gripper(node, GRIPPER_POSITION["open"], wait=True)
    arm.move_to(node, x, y, LOOK_HEIGHT, straight=True)

    seen = eyes.find(name)
    if not seen:
        print(f"The camera can't see the {name}. Try a lower --conf or another name.")
        return
    spot = seen[0]
    print(f"Grab spot: pixel {spot[0]:.0f}, {spot[1]:.0f}")

    # Move the arm a little along and sideways, and see which way the object moves
    offsets, shifts = [], []
    for dx, dy in ((TEACH_SHIFT, 0.0), (0.0, TEACH_SHIFT)):
        arm.move_to(node, x + dx, y + dy, LOOK_HEIGHT)
        moved = eyes.find(name)
        if not moved:
            print(f"Lost sight of the {name} while teaching. Put it back and try again.")
            return
        # Where the object now is from the fingers' point of view. Moving sideways turns
        # the base (and the camera) a little, so this isn't simply (-dx, -dy)
        hx, hy, _, _ = arm.where(node)
        offsets.append(to_gripper_frame(x - hx, y - hy, math.atan2(hy, hx - arm.BASE_X)))
        shifts.append([moved[0][i] - spot[i] for i in (0, 1)])
    # pixels_per_mm turns the object's offset (mm) into how far it shows up from the
    # grab spot (pixels): shifts = pixels_per_mm @ offsets, for both moves
    # (offsets as the columns of a 2x2 matrix, then its inverse)
    (a, b), (c, d) = offsets
    det = a * d - b * c
    inverse = [[d / det, -c / det], [-b / det, a / det]]
    pixels_per_mm = [[shifts[0][i] * inverse[0][j] + shifts[1][i] * inverse[1][j]
                      for j in (0, 1)] for i in (0, 1)]
    arm.move_to(node, x, y, LOOK_HEIGHT)
    calibration = {"grab_spot": list(spot), "pixels_per_mm": pixels_per_mm,
                   "look_height": LOOK_HEIGHT}

    # Check: from where it's seen now, does it work out the object is where it is?
    along, side = object_offset(calibration, eyes.find(name)[0])
    print(f"Check: it thinks the {name} is {math.hypot(along, side):.0f} mm from the grab "
          "spot (should be close to 0)")
    CALIBRATION.write_text(json.dumps(calibration, indent=2) + "\n")
    print(f"Saved to {CALIBRATION}. Now try:  python3 pick.py pick {name!r}")


# --- Picking up ---------------------------------------------------------------------

def search(node, eyes, name, calibration):
    """Look around until the object is in sight. Returns True if it's seen."""
    x0, y0 = LOOK_SPOT
    for turn in SEARCH_TURNS:
        r = math.hypot(x0 - arm.BASE_X, y0)
        x, y = arm.BASE_X + r * math.cos(turn), r * math.sin(turn)
        if arm.move_to(node, x, y, LOOK_HEIGHT):
            continue
        seen = eyes.find(name, calibration["grab_spot"])
        if seen:
            print(f"I see a {name} ({seen[1]:.0%} sure)")
            return True
    print(f"I can't find a {name}.")
    return False


def center(node, eyes, name, calibration):
    """Move over the object until it's right under the fingers. Returns (x, y) or None."""
    for _ in range(MAX_TRIES):
        seen = eyes.find(name, calibration["grab_spot"])
        if not seen:
            print(f"Lost sight of the {name}.")
            return None
        x, y, _, _ = arm.where(node)
        base = math.atan2(y, x - arm.BASE_X)
        along, side = object_offset(calibration, seen[0])
        distance = math.hypot(along, side)
        if distance <= CLOSE_ENOUGH:
            return x, y
        # Go most of the way at once, but never too far in one move
        scale = min(1.0, LONGEST_STEP / distance)
        dx, dy = from_gripper_frame(along * scale, side * scale, base)
        print(f"  {distance:.0f} mm away, moving closer")
        why = arm.move_to(node, x + dx, y + dy, LOOK_HEIGHT)
        if why:
            print(f"The {name} is out of reach ({why}). Please move it closer.")
            return None
    print(f"Couldn't get right over the {name}.")
    return None


def look(node, eyes, name, window):
    """Point the camera down and say where it sees the object. With the window on,
    keeps showing live video until q is pressed in it (or Ctrl+C)."""
    calibration = json.loads(CALIBRATION.read_text()) if CALIBRATION.exists() else None
    grab_spot = calibration and calibration["grab_spot"]
    why = arm.move_joints_safely(node, [math.radians(v) for v in SEARCH_POSE])
    if why:
        print(f"Couldn't reach the search pose: {why}")
        return
    if window:
        print("Showing the gripper camera. Press q in the window to finish.")
    last = None
    while True:
        seen = eyes.find(name, grab_spot, settle=last is None)
        if not seen:
            said = f"I don't see a {name}."
        elif calibration:
            along, side = object_offset(calibration, seen[0])
            said = (f"I see a {name}, {round(along, -1):+.0f} mm along the arm and "
                    f"{round(side, -1):+.0f} mm sideways from the grab spot")
        else:
            said = f"I see a {name} at pixel {seen[0][0]:.0f}, {seen[0][1]:.0f}"
        if said != last:
            print(said + (f" ({seen[1]:.0%} sure)" if seen else ""))
            last = said
        if not window or eyes.key == ord("q"):
            break


def gripper_position(node):
    from gestures import catch_up
    catch_up(node)
    return node.joints.get("gripper_left_joint")


def pick(node, eyes, name, grab_height):
    from gestures import GRIPPER_POSITION, move_gripper
    if not CALIBRATION.exists():
        print("Teach it first:  python3 pick.py teach")
        return
    calibration = json.loads(CALIBRATION.read_text())
    move_gripper(node, GRIPPER_POSITION["open"], wait=True)
    if not search(node, eyes, name, calibration):
        return
    spot = center(node, eyes, name, calibration)
    if spot is None:
        return
    x, y = spot

    print(f"Going down to grab the {name} ...")
    why = arm.move_to(node, x, y, grab_height, straight=True)
    if why:
        print(f"Can't go down: {why}")
        return
    move_gripper(node, GRIPPER_POSITION["close"], wait=True)
    closed = gripper_position(node)
    arm.move_to(node, x, y, LOOK_HEIGHT, straight=True)
    print(f"(gripper position {closed:+.4f}; empty is about {GRIPPER_POSITION['close']:+.3f})"
          if closed is not None else "")
    if closed is not None and closed < HOLDING:
        print("Missed: the gripper closed all the way. Try again?")
        move_gripper(node, GRIPPER_POSITION["open"], wait=True)
        return
    print(f"Got the {name}!")

    input(f"Press Enter to put the {name} back down ...")
    arm.move_to(node, x, y, grab_height + 5, straight=True)
    move_gripper(node, GRIPPER_POSITION["open"], wait=True)
    arm.move_to(node, x, y, LOOK_HEIGHT, straight=True)


def main():
    parser = argparse.ArgumentParser(description="Pick something up with the gripper camera.")
    parser.add_argument("command", choices=["teach", "look", "pick"])
    parser.add_argument("name", nargs="?", default="block",
                        help='what to look for, e.g. block or "glue stick" (default block)')
    parser.add_argument("--grab-height", type=float, default=15.0,
                        help="fingertip height when grabbing, mm above the table (default 15)")
    parser.add_argument("--conf", type=float, default=0.1,
                        help="how sure YOLO-World must be, 0-1 (default 0.1)")
    parser.add_argument("--no-window", action="store_true", help="don't show the camera")
    args, ros_args = parser.parse_known_args()

    import rclpy
    from gestures import Gesturer, connect
    rclpy.init(args=ros_args)
    node = Gesturer()
    try:
        if not connect(node):
            return
        eyes = Eyes(node, args.conf, not args.no_window)
        if args.command == "teach":
            teach(node, eyes, args.name, args.grab_height)
        elif args.command == "pick":
            pick(node, eyes, args.name, args.grab_height)
        else:
            look(node, eyes, args.name, not args.no_window)
        arm.move_joints_safely(node, [arm.current_joints(node)[0], 0.0, 0.0, 0.0])
    except KeyboardInterrupt:
        pass
    finally:
        if not args.no_window:
            import cv2
            cv2.destroyAllWindows()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
