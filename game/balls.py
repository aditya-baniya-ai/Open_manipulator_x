"""
Seeing the colored balls for the Ball Carry game, with a camera looking at the table.

Each ball is found by its color (HSV color filtering: about 1 ms a picture, and it
tells red from green, which YOLO can't). Two boxes in the picture are the zones:
    PICKUP  where the balls start (left)
    DROP    where they have to be carried to (right)
A ball counts as delivered when it sits inside the drop zone for a moment while the
gripper is open (so a ball that's only being carried over the zone doesn't count yet).

Set it up once with the table camera (drag the two zones, click each ball):
    python3 balls.py setup --camera /dev/video0
Check it afterwards (live picture with what it sees):
    python3 balls.py test --camera /dev/video0
The settings are saved in ball_setup.json next to this file.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

SETUP_FILE = Path(__file__).with_name("ball_setup.json")
STAY = 0.5           # seconds a ball must stay in the drop zone to count
MIN_AREA = 120       # pixels: smaller color blobs are ignored (noise)

# The balls: name, the color to draw it with (BGR), and a starting guess of its color
# range in HSV (OpenCV hue is 0-180). "setup" replaces the ranges with your balls' colors.
COLORS = {
    "red":    {"draw": (40, 40, 230), "ranges": [[0, 120, 70, 8, 255, 255],
                                                  [170, 120, 70, 180, 255, 255]]},
    "orange": {"draw": (0, 140, 255), "ranges": [[9, 130, 90, 20, 255, 255]]},
    "yellow": {"draw": (0, 220, 255), "ranges": [[21, 100, 90, 35, 255, 255]]},
    "green":  {"draw": (70, 200, 60), "ranges": [[40, 80, 50, 85, 255, 255]]},
    "blue":   {"draw": (220, 120, 30), "ranges": [[95, 120, 50, 130, 255, 255]]},
}


def default_setup(width=640, height=480):
    """Zones as fractions of the picture (left third and right third)."""
    return {"pickup": [0.03, 0.15, 0.33, 0.85], "drop": [0.67, 0.15, 0.97, 0.85],
            "colors": {name: c["ranges"] for name, c in COLORS.items()}}


def load_setup():
    if SETUP_FILE.exists():
        return json.loads(SETUP_FILE.read_text())
    return None


def in_box(box, x, y, width, height):
    left, top, right, bottom = box
    return left * width <= x <= right * width and top * height <= y <= bottom * height


class BallFinder:
    """Finds each colored ball in a picture."""

    def __init__(self, setup):
        self.setup = setup
        self.kernel = np.ones((5, 5), np.uint8)

    def find(self, frame):
        """Returns {color: (x, y, radius)} in pixels, the biggest blob of each color."""
        blurred = cv2.GaussianBlur(frame, (5, 5), 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
        found = {}
        for name, ranges in self.setup["colors"].items():
            mask = None
            for r in ranges:
                part = cv2.inRange(hsv, np.array(r[:3]), np.array(r[3:]))
                mask = part if mask is None else mask | part
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self.kernel)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                continue
            biggest = max(contours, key=cv2.contourArea)
            if cv2.contourArea(biggest) < MIN_AREA:
                continue
            (x, y), radius = cv2.minEnclosingCircle(biggest)
            found[name] = (x, y, radius)
        return found

    def zone_of(self, ball, frame_shape):
        height, width = frame_shape[:2]
        x, y, _ = ball
        for zone in ("drop", "pickup"):
            if in_box(self.setup[zone], x, y, width, height):
                return zone
        return None


class Judge:
    """Decides when a ball has really been delivered to the drop zone."""

    def __init__(self):
        self.since = {}          # color -> time it was first seen staying in the drop zone
        self.delivered = set()

    def update(self, balls, zones, gripper_open):
        """balls: {color: ...}, zones: {color: "drop"/"pickup"/None}.
        Returns the colors that were just delivered."""
        now = time.monotonic()
        newly = []
        for color in list(self.since):
            if zones.get(color) != "drop":
                del self.since[color]            # left the zone (or not seen): start over
        for color, zone in zones.items():
            if zone != "drop" or color in self.delivered:
                continue
            self.since.setdefault(color, now)
            if gripper_open and now - self.since[color] >= STAY:
                self.delivered.add(color)
                newly.append(color)
        return newly


# --- Setup and test tools (run this file directly) -----------------------------------

def open_camera(device):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from tracker import open_camera as opener
    camera = opener(device)
    if not camera.isOpened():
        sys.exit(f"Can't open the camera {device}. Is another program using it?")
    return camera


def draw_view(frame, setup, balls, finder):
    view = frame.copy()
    height, width = view.shape[:2]
    for zone, color in (("pickup", (200, 200, 200)), ("drop", (60, 220, 60))):
        l, t, r, b = setup[zone]
        cv2.rectangle(view, (int(l * width), int(t * height)), (int(r * width), int(b * height)),
                      color, 2)
        cv2.putText(view, zone.upper(), (int(l * width) + 5, int(t * height) + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    for name, ball in balls.items():
        x, y, radius = ball
        draw = COLORS.get(name, {}).get("draw", (255, 255, 255))
        cv2.circle(view, (int(x), int(y)), int(radius) + 4, draw, 2)
        cv2.putText(view, f"{name} ({finder.zone_of(ball, view.shape) or '-'})",
                    (int(x) - 30, int(y - radius) - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, draw, 2)
    return view


def sample_color(hsv, x, y):
    """The ball's color (hue, saturation, brightness) at a clicked spot: the middle
    value of a small square, so one odd pixel doesn't matter."""
    patch = hsv[max(0, y - 4):y + 5, max(0, x - 4):x + 5].reshape(-1, 3)
    return [int(v) for v in np.median(patch, axis=0)]


def hue_gap(a, b):
    """Distance between two hues on the hue circle (0-180 in OpenCV)."""
    d = abs(a - b) % 180
    return min(d, 180 - d)


def ranges_for(samples):
    """Color ranges from the clicked colors. Each hue range reaches at most halfway to
    the nearest other ball's hue (and at most 10), so similar colors (orange and
    yellow) never overlap."""
    ranges = {}
    for name, (h, s, v) in samples.items():
        others = [hue_gap(h, other[0]) for n, other in samples.items() if n != name]
        half = max(2, min([10] + [gap // 2 - 1 for gap in others]))
        low_s, low_v = max(40, s - 70), max(40, v - 80)
        if h - half < 0 or h + half > 180:    # red wraps around the end of the hue circle
            ranges[name] = [[0, low_s, low_v, (h + half) % 180, 255, 255],
                            [(h - half) % 180, low_s, low_v, 180, 255, 255]]
        else:
            ranges[name] = [[h - half, low_s, low_v, h + half, 255, 255]]
    return ranges


def setup_tool(camera):
    setup = load_setup() or default_setup()
    window = "Ball setup"
    cv2.namedWindow(window)
    state = {"drag": None, "box": None, "click": None}

    def on_mouse(event, x, y, flags, _):
        if event == cv2.EVENT_LBUTTONDOWN:
            state["drag"], state["click"] = (x, y), (x, y)
        elif event == cv2.EVENT_MOUSEMOVE and state["drag"]:
            state["box"] = (*state["drag"], x, y)
        elif event == cv2.EVENT_LBUTTONUP:
            state["drag"] = None
    cv2.setMouseCallback(window, on_mouse)

    def frame_now():
        ok, frame = camera.read()
        return frame if ok else None

    for zone in ("pickup", "drop"):
        print(f"Drag a box around the {zone.upper()} zone, then press Enter "
              "(Enter without dragging keeps the old one).")
        state["box"] = None
        while True:
            frame = frame_now()
            if frame is None:
                continue
            view = draw_view(frame, setup, {}, BallFinder(setup))
            if state["box"]:
                x0, y0, x1, y1 = state["box"]
                cv2.rectangle(view, (x0, y0), (x1, y1), (0, 255, 255), 2)
            cv2.putText(view, f"Drag the {zone.upper()} zone, then Enter", (10, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            cv2.imshow(window, view)
            if cv2.waitKey(1) & 0xFF in (13, 10):
                break
        if state["box"]:
            height, width = frame.shape[:2]
            x0, y0, x1, y1 = state["box"]
            setup[zone] = [min(x0, x1) / width, min(y0, y1) / height,
                           max(x0, x1) / width, max(y0, y1) / height]

    samples = {}
    for name in COLORS:
        print(f"Click the {name.upper()} ball (or press s to skip it, if you have none).")
        state["click"] = None
        skipped = False
        while state["click"] is None:
            frame = frame_now()
            if frame is None:
                continue
            view = frame.copy()
            cv2.putText(view, f"Click the {name.upper()} ball (s: skip)", (10, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, COLORS[name]["draw"], 2)
            cv2.imshow(window, view)
            if cv2.waitKey(1) & 0xFF == ord("s"):
                skipped = True
                break
        if skipped:
            continue
        hsv = cv2.cvtColor(cv2.GaussianBlur(frame, (5, 5), 0), cv2.COLOR_BGR2HSV)
        samples[name] = sample_color(hsv, *state["click"])
    setup["colors"] = ranges_for(samples)
    SETUP_FILE.write_text(json.dumps(setup, indent=1) + "\n")
    print(f"Saved to {SETUP_FILE}. Now check it: every ball should get a circle.")
    test_tool(camera, window)


def test_tool(camera, window="Ball test"):
    setup = load_setup()
    if setup is None:
        sys.exit("Run the setup first:  python3 balls.py setup")
    finder = BallFinder(setup)
    print("Showing what the table camera sees. Press q in the window to finish.")
    while True:
        ok, frame = camera.read()
        if not ok:
            continue
        started = time.perf_counter()
        balls = finder.find(frame)
        ms = (time.perf_counter() - started) * 1000
        view = draw_view(frame, setup, balls, finder)
        cv2.putText(view, f"{len(balls)} balls, {ms:.1f} ms", (10, view.shape[0] - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.imshow(window, view)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break


def main():
    parser = argparse.ArgumentParser(description="Set up and test the ball colors and zones.")
    parser.add_argument("command", choices=["setup", "test"])
    parser.add_argument("--camera", default="/dev/video0", help="the camera looking at the table")
    args = parser.parse_args()
    camera = open_camera(args.camera)
    try:
        setup_tool(camera) if args.command == "setup" else test_tool(camera)
    finally:
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
