"""
Greet people automatically: wave when someone appears in front of the camera.

Needs the arm launch, the camera and perception/detect.py running (see README.md):
    python3 greet.py                  # wave (w) at each new person
    python3 greet.py --gesture b      # bow instead; any key from gestures.py works,
                                      # including moves you saved yourself

How it decides to greet:
  - a person has to be in view for --see-time seconds (so a false detection for one
    frame doesn't count)
  - then it greets once, and won't greet again until --cooldown seconds have passed
    AND nobody has been in view for a few seconds (so it doesn't keep waving at
    someone who stays in front of it)
"""

import argparse
import time

import rclpy
from std_msgs.msg import Bool

from gestures import GESTURES, Gesturer, connect, load_saved, run_gesture

GONE_TIME = 3.0     # seconds with nobody in view before the next person counts as new
FLICKER_TIME = 0.5  # a person missed for less than this still counts as in view


class Greeter(Gesturer):
    def __init__(self):
        super().__init__()
        self.last_person = None  # when a person was last detected
        self.create_subscription(Bool, "/person_detected", self.on_person, 10)

    def on_person(self, msg):
        if msg.data:
            self.last_person = time.monotonic()


def main():
    parser = argparse.ArgumentParser(description="Wave when a person appears.")
    parser.add_argument("--gesture", default="w",
                        help="key of the gesture to do (default w = wave)")
    parser.add_argument("--cooldown", type=float, default=30.0,
                        help="minimum seconds between greetings (default 30)")
    parser.add_argument("--see-time", type=float, default=1.0,
                        help="seconds a person must be in view before greeting (default 1)")
    args, ros_args = parser.parse_known_args()

    load_saved()
    if args.gesture not in GESTURES:
        parser.error(f"no gesture on key '{args.gesture}'. Choose from: {' '.join(GESTURES)}")
    name, moves = GESTURES[args.gesture]

    rclpy.init(args=ros_args)
    node = Greeter()
    log = node.get_logger()

    if not connect(node):
        node.destroy_node()
        rclpy.shutdown()
        return
    log.info(f"Ready. Will greet with '{name}'. Press Ctrl+C to stop.")

    in_view_since = None  # when the current person came into view
    last_greet = None     # when we last greeted
    ready = True          # False after a greeting, until nobody is in view for a while

    try:
        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.05)
            now = time.monotonic()
            seen = node.last_person is not None and now - node.last_person < FLICKER_TIME

            if not seen:
                in_view_since = None
                if node.last_person is None or now - node.last_person >= GONE_TIME:
                    ready = True
                continue

            if in_view_since is None:
                in_view_since = now
            cooled_down = last_greet is None or now - last_greet >= args.cooldown
            if ready and cooled_down and now - in_view_since >= args.see_time:
                log.info(f"Person in view: {name}!")
                run_gesture(node, moves)
                last_greet = time.monotonic()
                ready = False
    except KeyboardInterrupt:
        pass

    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
