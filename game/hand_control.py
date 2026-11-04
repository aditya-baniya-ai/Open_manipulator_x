"""
HAND CONTROL: move Robo's arm with your hand. No game, no score: just the camera with your
hand, and the robot following it.

    Hand left / right       the claw moves left / right
    Hand up / down          the claw moves toward you / away from you
    Make a fist             the claw goes down, grabs, and comes back up at the same spot
    Keep the fist           the claw stays closed and holds what it grabbed (moves slower)
    Open your hand          the claw opens and lets go

It's Chocolate Catcher (claw_machine.py) without the game, and uses the same pieces:
hand tracking (tracker.py), the arm that follows the hand (arm_link.py) and the screen
parts (puppet_master.py).

    ../launch/hand.sh                     with the arm (starts it too)
    python3 hand_control.py --no-arm      no robot: a pretend arm on the screen
    python3 hand_control.py --keyboard    W A S D move, Space = fist on / off

Esc closes it (the arm goes home first).
"""

import argparse

import cv2
import numpy as np

import arm_link
from puppet_master import (CYAN, DIM, GOLD, GREEN, INK, PINK, Camera, Text, Tracking, W,
                           background, glow_circle, panel)
from tracker import PLAY_AREA, make_tracker

HOVER = 110.0             # mm: the claw glides this high (a fist takes it down to grab)
KEY_STEP = 0.04
VIEW = (30, 95, 830, 695)            # the camera, big on the left (800 x 600)
SIDE_BOX = (860, 95, 1250, 695)      # what Robo is doing, on the right


class HandControl:
    def __init__(self, args):
        self.text = Text()
        self.background = background()
        for box in (VIEW, SIDE_BOX):
            panel(self.background, box)
        self.robot = arm_link.VirtualArm() if args.no_arm \
            else arm_link.RealArm(ros_args=args.ros_args)
        self.robot.hover = HOVER
        self.keyboard = args.keyboard
        if not self.keyboard:
            self.camera = Camera(args.camera)
            self.tracking = Tracking(make_tracker(args.tracker), self.camera)
        self.cursor, self.key_fist = [0.5, 0.5], False
        self.hand, self.point = None, None
        self.was_fist = True       # a fist already made at the start doesn't grab
        self.phase = "open"        # open -> grab -> holding -> (open again)

    def control(self):
        """(u, v, fist) from the hand or the keyboard, or None when no hand is seen."""
        if self.keyboard:
            return self.cursor[0], self.cursor[1], self.key_fist
        if not self.hand:
            return None
        return self.hand.x, self.hand.y, self.hand.whack

    def step(self):
        self.robot.update()
        frame = None
        if not self.keyboard:
            frame, self.hand = self.tracking.frame, self.tracking.hand
        seen = self.control()
        if seen:
            u, v, fist = seen
            self.point = (u, v)
            self.robot.follow(u, v)            # ignored while grabbing
        else:
            fist = self.was_fist               # hand lost: keep the last state
        started_fist = fist and not self.was_fist
        self.was_fist = fist

        if self.phase == "open":
            if started_fist and self.robot.grab():
                self.phase = "grab"            # down, close, back up
        elif self.phase == "grab":
            if not self.robot.busy():
                if fist:
                    self.phase = "holding"
                    self.robot.carrying(True)  # slower while holding something
                else:
                    self.let_go()              # opened during the grab
        elif self.phase == "holding" and not fist:
            self.let_go()
        return self.draw(frame)

    def let_go(self):
        self.robot.open_here()
        self.robot.carrying(False)
        self.phase = "open"

    def key(self, key):
        if key == 27:                          # Esc
            return False
        if self.keyboard:
            moves = {ord("a"): (-KEY_STEP, 0), ord("d"): (KEY_STEP, 0),
                     ord("w"): (0, -KEY_STEP), ord("s"): (0, KEY_STEP)}
            if key in moves:
                dx, dy = moves[key]
                self.cursor = [min(1, max(0, self.cursor[0] + dx)),
                               min(1, max(0, self.cursor[1] + dy))]
            elif key == 32:
                self.key_fist = not self.key_fist
        return True

    # -- drawing ----------------------------------------------------------------------
    def area_to_view(self, u, v):
        left, top, right, bottom = VIEW
        a = PLAY_AREA
        width, height = right - left - 10, bottom - top - 10
        return (left + 5 + int((a[0] + u * (a[2] - a[0])) * width),
                top + 5 + int((a[1] + v * (a[3] - a[1])) * height))

    def draw(self, frame):
        canvas = self.background.copy()
        t = self.text
        t.add("HAND", 30, 20, 34, GOLD)
        t.add("CONTROL", 30 + t.width("HAND ", 34), 20, 34, CYAN)
        t.add("move your hand: Robo follows", 32, 62, 15, DIM)
        self.draw_view(canvas, frame)
        self.draw_side(canvas)
        return t.draw(canvas)

    def draw_view(self, canvas, frame):
        left, top, right, bottom = VIEW
        width, height = right - left - 10, bottom - top - 10
        if frame is not None:
            canvas[top + 5:bottom - 5, left + 5:right - 5] = \
                (cv2.resize(frame, (width, height)) * 0.7).astype(np.uint8)
        elif not self.keyboard:
            self.text.add("Waiting for the camera ...", (left + right) // 2,
                          (top + bottom) // 2, 22, DIM, "mm")
        # The play frame: the hand moves the claw inside this box
        a = PLAY_AREA
        corner1 = (left + 5 + int(a[0] * width), top + 5 + int(a[1] * height))
        corner2 = (left + 5 + int(a[2] * width), top + 5 + int(a[3] * height))
        cv2.rectangle(canvas, corner1, corner2, (170, 130, 150), 2, cv2.LINE_AA)
        self.text.add("PLAY FRAME", corner1[0] + 6, corner1[1] + 6, 13, DIM)
        self.text.add("toward you", (corner1[0] + corner2[0]) // 2, corner1[1] - 14, 13, DIM, "mm")
        self.text.add("toward Robo", (corner1[0] + corner2[0]) // 2, corner2[1] + 14, 13, DIM,
                      "mm")
        # Where the claw is (cross-hair, pink while closed)
        if self.robot.command is not None:
            u, v, _ = self.robot.gripper_area()
            claw = self.area_to_view(min(1, max(0, u)), min(1, max(0, v)))
            color = PINK if self.robot.closed else CYAN
            cv2.circle(canvas, claw, 20, color, 2, cv2.LINE_AA)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                cv2.line(canvas, (claw[0] + 12 * dx, claw[1] + 12 * dy),
                         (claw[0] + 30 * dx, claw[1] + 30 * dy), color, 2, cv2.LINE_AA)
        # The hand and its middle point
        hand = self.hand
        if hand and frame is not None:
            sx, sy = width / frame.shape[1], height / frame.shape[0]
            points = [(left + 5 + int(x * sx), top + 5 + int(y * sy)) for x, y in hand.points]
            for i, j in hand.lines:
                if i < len(points) and j < len(points):
                    cv2.line(canvas, points[i], points[j], (230, 200, 120), 2, cv2.LINE_AA)
            for p in points:
                cv2.circle(canvas, p, 3, INK, -1, cv2.LINE_AA)
        seen = self.control()
        if seen:
            middle = self.area_to_view(seen[0], seen[1])
            glow_circle(canvas, middle, 11, PINK if seen[2] else GOLD)
            self.text.add("FIST" if seen[2] else "OPEN", middle[0], middle[1] - 26, 14,
                          PINK if seen[2] else GOLD, "mm")

    def draw_side(self, canvas):
        left, top, right, bottom = SIDE_BOX
        t, mid = self.text, (left + right) // 2
        seen = self.control() is not None
        t.add("HAND", mid, top + 30, 15, DIM, "mm")
        t.add("SEEN" if seen else "NOT SEEN", mid, top + 70, 40, GREEN if seen else DIM, "mm")
        t.add("CLAW", mid, top + 140, 15, DIM, "mm")
        status, color = {"open": ("OPEN", CYAN), "grab": ("GRABBING ...", GOLD),
                         "holding": ("HOLDING", PINK)}[self.phase]
        t.add(status, mid, top + 180, 40, color, "mm")
        if self.phase == "holding":
            t.add("moving slower while holding", mid, top + 220, 14, DIM, "mm")
        cv2.line(canvas, (left + 25, top + 260), (right - 25, top + 260), (90, 60, 70), 1)
        controls = [("W A S D", "move"), ("Space", "grab / let go"), ("Esc", "close")] \
            if self.keyboard else \
            [("move your hand", "move the claw"), ("up / down", "toward you / away"),
             ("make a fist", "grab"), ("keep the fist", "hold and carry"),
             ("open your hand", "let go"), ("Esc", "close")]
        for i, (gesture, what) in enumerate(controls):
            y = top + 290 + i * 34
            t.add(gesture, left + 30, y, 17, CYAN)
            t.add(what, right - 30, y, 17, DIM, "ra")
        control = "keyboard" if self.keyboard else \
            f"{self.tracking.tracker.name} {self.tracking.ms:.0f} ms"
        t.add(f"{control}  ·  {self.robot.name}", mid, bottom - 16, 12, DIM, "mm")


def main():
    parser = argparse.ArgumentParser(description="Control Robo's arm with your hand.")
    parser.add_argument("--no-arm", action="store_true", help="no robot: a pretend arm")
    parser.add_argument("--keyboard", action="store_true",
                        help="W A S D move the claw, Space = fist on / off")
    parser.add_argument("--camera", default="/dev/video0",
                        help="the camera facing you (default /dev/video0)")
    parser.add_argument("--tracker", default="auto", choices=["auto", "mediapipe", "yolo"])
    parser.add_argument("--fullscreen", action="store_true")
    args, args.ros_args = parser.parse_known_args()

    try:
        app = HandControl(args)
    except RuntimeError as error:      # no camera
        print(error)
        return
    why = app.robot.start()
    if why:
        print(f"Can't start the arm: {why}")
        app.robot.stop()
        return
    cv2.namedWindow("Hand Control", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Hand Control", W, 720)
    if args.fullscreen:
        cv2.setWindowProperty("Hand Control", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    try:
        while True:
            cv2.imshow("Hand Control", app.step())
            key = cv2.waitKey(1)
            if key != -1 and not app.key(key & 0xFF):
                break
            if cv2.getWindowProperty("Hand Control", cv2.WND_PROP_VISIBLE) < 1:
                break
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        if not app.keyboard:
            app.tracking.close()
            app.camera.close()
        if app.robot.closed:
            app.robot.open_here()
        app.robot.stop()


if __name__ == "__main__":
    main()
