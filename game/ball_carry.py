"""
BALL CARRY: move Robo with your hand and carry all the balls from the left side of the
table to the right side, as fast as you can. Fastest time wins.

Move your hand: Robo follows. Close your hand (fist): Robo goes down and grabs. Move
over to the right side and open your hand: Robo lets go.

Robo checks every carry itself, no extra camera needed:
    - holding a ball: the gripper closed on something (a ball stops the fingers
      partway; empty, they close all the way)
    - across: it let go on the right side a ball it didn't pick up from the right side
      (so a ball dropped in the middle can be picked up again and finished, but a ball
      that's already across can't count twice). Robo always knows where its gripper
      is from its joint angles.

The stopwatch stops when all the balls are across (or at the time limit). P pauses it.

One camera, facing the player (the hand). Or no camera: --keyboard (W A S D move Robo,
Space grabs and lets go).

    python3 ball_carry.py --no-arm      no robot: a pretend arm and pretend balls
    python3 ball_carry.py               with Robo's arm (real or simulated) running
"""

import argparse
import json
import math
import time
from pathlib import Path

import cv2
import numpy as np

import arm_link
from puppet_master import (CAMERA_BOX, CYAN, DIM, FOOTER_BOX, GOLD, GREEN, H, INK, MAP_BOX,
                           PINK, RED, Camera, Text, Tracking, W, background, glow_circle, panel)
from tracker import PLAY_AREA, make_tracker

LEADERBOARD = Path(__file__).with_name("ball_leaderboard.json")
BALLS = 5                 # balls to carry across
TIME_LIMIT = 120.0        # seconds: the round ends here even if balls are left
MIDDLE = 0.5              # the middle of the table (play-area position, left to right)
MARGIN = 0.05             # "the right side" starts at MIDDLE + MARGIN
SHOW_HAND_FOR = 1.0
KEY_STEP = 0.04           # how far one key press moves Robo (play-area units)


def load_board():
    try:
        return json.loads(LEADERBOARD.read_text())
    except (OSError, ValueError):
        return []


def board_order(entry):
    """More balls first; for the same balls, the faster time."""
    return (-entry["balls"], entry["time"])


def to_map(u, v):
    """Play-area position to a point on the table map (Robo at the top)."""
    left, top, right, bottom = MAP_BOX
    scale = min((right - left - 60) / (2 * arm_link.FAR * math.sin(arm_link.SIDE)),
                (bottom - top - 200) / arm_link.FAR)
    reach = arm_link.NEAR + v * (arm_link.FAR - arm_link.NEAR)
    angle = (u - 0.5) * 2 * arm_link.SIDE
    return (int((left + right) / 2 + reach * math.sin(angle) * scale),
            int(top + 70 + reach * math.cos(angle) * scale))


class VirtualBalls:
    """Pretend balls for --no-arm: the pretend arm really picks them up and puts them
    down (to try the game without a robot)."""

    def __init__(self, robot):
        self.robot, self.was_closed = robot, False
        self.balls = [(0.12, 0.3), (0.25, 0.25), (0.18, 0.55), (0.08, 0.75), (0.3, 0.7)][:BALLS]
        self.robot.held = None

    def update(self):
        u, v, z = self.robot.gripper_area()
        if self.robot.closed and not self.was_closed and z < arm_link.GRAB_HEIGHT + 15:
            near = [(math.hypot(u - bu, v - bv), i) for i, (bu, bv) in enumerate(self.balls)]
            if near and min(near)[0] < 0.08:
                self.robot.held = min(near)[1]
        if not self.robot.closed:
            self.robot.held = None
        self.was_closed = self.robot.closed
        if self.robot.held is not None:
            self.balls[self.robot.held] = (u, v)


class Game:
    def __init__(self, args):
        self.args = args
        self.text = Text()
        self.background = background()
        for box in (CAMERA_BOX, MAP_BOX, FOOTER_BOX):
            panel(self.background, box)
        self.robot = arm_link.VirtualArm() if args.no_arm \
            else arm_link.RealArm(ros_args=args.ros_args)
        self.pretend = VirtualBalls(self.robot) if args.no_arm else None
        self.keyboard = args.keyboard
        if not self.keyboard:
            self.camera = Camera(args.camera)
            self.tracking = Tracking(make_tracker(args.tracker), self.camera)
        self.cursor = [0.5, 0.5]
        self.hand, self.hand_since, self.hand_seen, self.was_fist = None, None, 0.0, False
        self.state, self.name = "title", ""
        self.board = load_board()
        self.round = None
        self.message, self.message_at = "", 0.0
        self.countdown_at = self.result_at = 0.0

    # -- the stopwatch --------------------------------------------------------------
    def elapsed(self):
        r = self.round
        if not r:
            return 0.0
        now = r["paused_at"] or r["finished"] or time.monotonic()
        return min(TIME_LIMIT, now - r["started"] - r["paused_for"])

    def toggle_pause(self):
        r = self.round
        if self.state != "play" or r["finished"]:
            return
        if r["paused_at"]:
            r["paused_for"] += time.monotonic() - r["paused_at"]
            r["paused_at"] = None
            self.say("Go!")
        else:
            r["paused_at"] = time.monotonic()

    def say(self, message):
        self.message, self.message_at = message, time.monotonic()

    # -- each frame -------------------------------------------------------------------
    def step(self):
        now = time.monotonic()
        self.robot.update()
        if self.pretend:
            self.pretend.update()
        frame = None
        if not self.keyboard:
            frame, self.hand = self.tracking.frame, self.tracking.hand
            if self.hand:
                self.hand_seen, self.hand_since = now, self.hand_since or now
            elif now - self.hand_seen > 0.3:
                self.hand_since = None

        if self.state == "ready" and (self.keyboard or
                                      (self.hand_since and now - self.hand_since > SHOW_HAND_FOR)):
            self.state, self.countdown_at = "countdown", now
        elif self.state == "countdown":
            self.control(allow_grab=False)
            if now - self.countdown_at > 3.0:
                self.state = "play"
                self.round = {"started": now, "paused_at": None, "paused_for": 0.0,
                              "carried": 0, "drops": 0, "finished": None,
                              "grabbed_on": None, "splits": []}
        elif self.state == "play":
            if not self.round["paused_at"]:
                self.control()
            if self.round["carried"] >= BALLS or self.elapsed() >= TIME_LIMIT:
                if not self.robot.busy():
                    self.finish()
        elif self.state == "results" and now - self.result_at > 15.0:
            self.state = "title"
        return self.draw(frame)

    def control(self, allow_grab=True):
        """Move Robo (hand or keyboard) and grab or let go."""
        if self.keyboard:
            self.robot.follow(*self.cursor)
            return
        if not self.hand:
            return
        self.robot.follow(self.hand.x, self.hand.y)
        fist = self.hand.whack
        if allow_grab and fist != self.was_fist:
            self.grab() if fist else self.let_go()
        self.was_fist = fist

    def grab(self):
        if self.robot.closed or not self.robot.grab():
            return
        u, _, _ = self.robot.gripper_area()
        if self.round:
            self.round["grabbed_on"] = "right" if u > MIDDLE + MARGIN else "left"

    def let_go(self):
        """Opening the gripper: a carry counts if it was holding a ball, it's now over
        the right side, and it didn't pick the ball up from the right side."""
        if not self.robot.closed:
            return
        r = self.round
        holding = self.robot.holding()
        u, _, _ = self.robot.gripper_area()
        if not self.robot.release():
            return
        if self.state != "play" or r["finished"]:
            return
        if holding and r["grabbed_on"] == "left" and u > MIDDLE + MARGIN:
            r["carried"] += 1
            r["splits"].append(self.elapsed())
            self.say(f"+1   {r['carried']} / {BALLS}")
            if r["carried"] >= BALLS:
                r["finished"] = time.monotonic()        # stop the stopwatch
        elif holding and r["grabbed_on"] == "right":
            self.say("That one was already across: it doesn't count twice")
        elif holding:
            r["drops"] += 1
            self.say("Not across yet: let go on the RIGHT side")
        else:
            self.say("Empty: no ball in the gripper")
        r["grabbed_on"] = None

    def finish(self):
        r = self.round
        r["finished"] = r["finished"] or time.monotonic()
        entry = {"name": self.name or "PLAYER", "balls": r["carried"],
                 "time": round(self.elapsed(), 1), "date": time.strftime("%Y-%m-%d")}
        self.board.append(entry)
        self.board.sort(key=board_order)
        LEADERBOARD.write_text(json.dumps(self.board[:10], indent=1) + "\n")
        self.state, self.result_at = "results", time.monotonic()
        if self.robot.closed:
            self.robot.release()

    def key(self, key):
        if key == 27:
            return False
        if self.state == "howto":
            if key in (13, 10):
                self.state = "ready"
            elif key in (8, 127):                       # Backspace: back to the name
                self.state = "title"
            return True
        if self.state == "title":
            if key in (13, 10):
                self.state = "howto"
            elif key in (8, 127):
                self.name = self.name[:-1]
            elif 32 <= key < 127 and len(self.name) < 12:
                self.name += chr(key).upper()
            return True
        if self.state == "results" and key in (13, 10):
            self.state, self.name = "title", ""
        elif key in (ord("p"), ord("P")):
            self.toggle_pause()
        elif self.keyboard and not (self.round and self.round["paused_at"]):
            moves = {ord("a"): (-KEY_STEP, 0), ord("d"): (KEY_STEP, 0),
                     ord("w"): (0, -KEY_STEP), ord("s"): (0, KEY_STEP)}
            if key in moves:
                dx, dy = moves[key]
                self.cursor = [min(1, max(0, self.cursor[0] + dx)),
                               min(1, max(0, self.cursor[1] + dy))]
            elif key == 32 and self.state == "play":
                self.let_go() if self.robot.closed else self.grab()
        return True

    # -- drawing ----------------------------------------------------------------------
    def draw(self, frame):
        canvas = self.background.copy()
        self.draw_header(canvas)
        self.draw_player(canvas, frame)
        self.draw_table(canvas)
        self.draw_footer(canvas)
        if self.state != "play" or self.round["paused_at"]:
            canvas = self.text.draw(canvas)
            self.draw_overlay(canvas)
        return self.text.draw(canvas)

    def draw_header(self, canvas):
        t = self.text
        t.add("BALL", 30, 22, 38, GOLD)
        t.add("CARRY", 140, 22, 38, CYAN)
        t.add("carry every ball across, fastest time wins", 32, 66, 15, DIM)
        r = self.round if self.state in ("play", "results") else None
        t.add(f"{self.elapsed():5.1f}s", W // 2, 42, 54, INK, "mm")
        t.add("STOPWATCH", W // 2, 82, 14, DIM, "mm")
        best = next((e for e in self.board if e["balls"] >= BALLS), None)
        t.add("BEST TIME", W - 30, 20, 14, DIM, "ra")
        t.add(f"{best['time']:.1f}s" if best else "-", W - 30, 38, 28, GOLD, "ra")
        if r:
            t.add(f"{r['carried']} / {BALLS} BALLS", W // 2 + 150, 42, 26, PINK, "lm")

    def draw_player(self, canvas, frame):
        left, top, right, bottom = CAMERA_BOX
        t = self.text
        if self.keyboard:
            t.add("KEYBOARD CONTROL", left + 20, top + 20, 18, GOLD)
            for i, (keys, what) in enumerate([("W  A  S  D", "move Robo"),
                                              ("SPACE", "grab / let go"),
                                              ("P", "pause the stopwatch"), ("ESC", "quit")]):
                t.add(keys, left + 40, top + 80 + i * 50, 26, INK)
                t.add(what, left + 260, top + 84 + i * 50, 20, DIM)
            return
        if frame is None:
            t.add("Waiting for the camera ...", (left + right) // 2, (top + bottom) // 2,
                  22, DIM, "mm")
            return
        width, height = right - left - 10, bottom - top - 10
        view = (cv2.resize(frame, (width, height)) * 0.75).astype(np.uint8)
        a = PLAY_AREA
        cv2.rectangle(view, (int(a[0] * width), int(a[1] * height)),
                      (int(a[2] * width), int(a[3] * height)), (120, 90, 100), 1, cv2.LINE_AA)
        # The middle line: the hand crosses it as Robo crosses the table
        mid_x = int((a[0] + MIDDLE * (a[2] - a[0])) * width)
        cv2.line(view, (mid_x, int(a[1] * height)), (mid_x, int(a[3] * height)), GOLD, 1,
                 cv2.LINE_AA)
        hand = self.hand
        if hand:
            sx, sy = width / frame.shape[1], height / frame.shape[0]
            points = [(int(x * sx), int(y * sy)) for x, y in hand.points]
            for i, j in hand.lines:
                if i < len(points) and j < len(points):
                    cv2.line(view, points[i], points[j], CYAN, 2, cv2.LINE_AA)
            cx = int((a[0] + hand.x * (a[2] - a[0])) * width)
            cy = int((a[1] + hand.y * (a[3] - a[1])) * height)
            glow_circle(view, (cx, cy), 14, PINK if hand.whack else GOLD, 3)
        canvas[top + 5:bottom - 5, left + 5:right - 5] = view
        t.add("FIST = GRAB   ·   OPEN HAND = LET GO   ·   P = PAUSE", left + 15, bottom - 32,
              15, DIM)

    def draw_table(self, canvas):
        left, top, right, bottom = MAP_BOX
        t = self.text
        t.add("THE TABLE", left + 15, top + 12, 16, DIM)
        # The two halves of the reach area, and the middle line
        for (u0, u1), color, label in (((0.0, MIDDLE), (75, 55, 60), "PICK UP"),
                                       ((MIDDLE, 1.0), (55, 80, 55), "DROP")):
            points = [to_map(u0 + (u1 - u0) * i / 10, 0) for i in range(11)] + \
                     [to_map(u1 - (u1 - u0) * i / 10, 1) for i in range(11)]
            cv2.fillPoly(canvas, [np.array(points)], color, cv2.LINE_AA)
            spot = to_map((u0 + u1) / 2, 1.12)
            t.add(label, spot[0], spot[1], 16, GREEN if label == "DROP" else INK, "mm")
        cv2.line(canvas, to_map(MIDDLE, -0.05), to_map(MIDDLE, 1.05), GOLD, 2, cv2.LINE_AA)
        base = ((left + right) // 2, top + 70)
        cv2.circle(canvas, base, 22, (90, 70, 80), -1, cv2.LINE_AA)
        t.add("ROBO", base[0], base[1], 13, INK, "mm")
        if self.pretend:                                    # pretend balls (--no-arm)
            for i, (u, v) in enumerate(self.pretend.balls):
                if i != self.robot.held:
                    cv2.circle(canvas, to_map(u, v), 13, (0, 140, 255), -1, cv2.LINE_AA)
        holding = self.robot.holding() if self.robot.command is not None else False
        if self.robot.command is not None:
            u, v, z = self.robot.gripper_area()
            spot = to_map(u, v)
            if holding:
                cv2.circle(canvas, spot, 13, (0, 140, 255), -1, cv2.LINE_AA)
            cv2.circle(canvas, spot, 18, PINK if self.robot.closed else INK, 3, cv2.LINE_AA)
        # What Robo is doing, and the last message
        status = "HOLDING A BALL" if holding else \
            "GRIPPER CLOSED (EMPTY)" if self.robot.closed else "GRIPPER OPEN"
        t.add(status, (left + right) // 2, bottom - 80, 20, PINK if holding else DIM, "mm")
        if self.message and time.monotonic() - self.message_at < 2.0:
            good = self.message.startswith("+") or self.message == "Go!"
            t.add(self.message, (left + right) // 2, bottom - 40, 26, GREEN if good else RED,
                  "mm")

    def draw_howto(self, canvas):
        t, mid = self.text, W // 2
        t.add("HOW TO PLAY", mid, 70, 52, GOLD, "mm")
        t.add("Robo checks every carry itself: the ball must really be in the gripper "
              "and let go on the right side.", mid, 120, 17, DIM, "mm")
        for i, (big, small) in enumerate(how_to_play(self.keyboard)):
            y = 185 + i * 72
            cv2.circle(canvas, (mid - 330, y + 8), 22, CYAN, 2, cv2.LINE_AA)
            t.add(str(i + 1), mid - 330, y + 8, 22, CYAN, "mm")
            t.add(big, mid - 290, y - 6, 26, INK)
            t.add(small, mid - 290, y + 26, 18, DIM)
        t.add("press ENTER to start", mid, 640, 24, GREEN, "mm")
        t.add("Backspace: change your name", mid, 675, 14, DIM, "mm")

    def draw_footer(self, canvas):
        left, top, right, bottom = FOOTER_BOX
        t = self.text
        r = self.round if self.state in ("play", "results") else None
        splits = r["splits"] if r else []
        gaps = [b - a for a, b in zip([0.0] + splits, splits)]
        stats = [("BALLS ACROSS", f"{r['carried']} / {BALLS}" if r else f"0 / {BALLS}"),
                 ("FASTEST BALL", f"{min(gaps):.1f}s" if gaps else "-"),
                 ("DROPPED EARLY", r["drops"] if r else 0)]
        for i, (label, value) in enumerate(stats):
            x = left + 20 + i * 205
            t.add(label, x, top + 15, 13, DIM)
            t.add(value, x, top + 35, 26, INK)
        control = "keyboard" if self.keyboard else \
            f"{self.tracking.tracker.name} {self.tracking.ms:.0f} ms"
        t.add(f"{control}  ·  {self.robot.name}", left + 20, bottom - 18, 12, DIM)

    def draw_overlay(self, canvas):
        overlay = canvas.copy()
        cv2.rectangle(overlay, (0, 0), (W, H), (15, 8, 10), -1)
        dark = 0.5 if self.state in ("countdown", "play") else 0.88
        cv2.addWeighted(overlay, dark, canvas, 1 - dark, 0, canvas)
        t, mid = self.text, W // 2
        grab = "Space" if self.keyboard else "Close your hand"
        if self.state == "play":                       # paused
            t.add("PAUSED", mid, H // 2 - 20, 80, GOLD, "mm")
            t.add("press P to go on", mid, H // 2 + 50, 22, INK, "mm")
        elif self.state == "title":
            t.add("BALL CARRY", mid, 130, 72, GOLD, "mm")
            t.add(f"Carry all {BALLS} balls from the left side to the right side. "
                  "Fastest time wins!", mid, 195, 20, INK, "mm")
            t.add(f"{grab} to grab, let go on the right. Robo checks every carry itself.",
                  mid, 225, 17, DIM, "mm")
            t.add("TYPE YOUR NAME", mid, 300, 16, DIM, "mm")
            cursor = "_" if int(time.monotonic() * 2) % 2 else " "
            t.add(self.name + cursor, mid, 345, 46, CYAN, "mm")
            t.add("press ENTER to play", mid, 400, 18, INK, "mm")
            t.add("TOP 10", mid, 460, 18, GOLD, "mm")
            for i, e in enumerate(self.board[:10]):
                x, y = mid - 300 + (i // 5) * 320, 495 + (i % 5) * 32
                t.add(f"{i + 1:>2}. {e['name'][:12]}", x, y, 20, INK)
                t.add(f"{e['balls']}/{BALLS}  {e['time']:.1f}s", x + 280, y, 20, GOLD, "ra")
            if not self.board:
                t.add("Be the first on the board!", mid, 500, 20, DIM, "mm")
        elif self.state == "howto":
            self.draw_howto(canvas)
        elif self.state == "ready":
            t.add(f"Get ready, {self.name or 'player'}!", mid, 250, 44, INK, "mm")
            t.add(f"Put all {BALLS} balls on the LEFT side of the table", mid, 310, 22, CYAN,
                  "mm")
            if not self.keyboard:
                t.add("Hold your hand up in front of the camera", mid, 350, 22, INK, "mm")
        elif self.state == "countdown":
            t.add(str(max(1, 3 - int(time.monotonic() - self.countdown_at))), mid, H // 2,
                  160, GOLD, "mm")
            t.add(f"Move: Robo follows. {grab}: grab.", mid, H // 2 + 120, 22, INK, "mm")
        elif self.state == "results":
            r = self.round
            done = r["carried"] >= BALLS
            t.add("ALL ACROSS!" if done else "TIME'S UP!", mid, 110, 40, DIM, "mm")
            t.add(f"{self.elapsed():.1f}s" if done else f"{r['carried']} / {BALLS} balls",
                  mid, 200, 96, GOLD, "mm")
            place = next((i for i, e in enumerate(self.board)
                          if e["name"] == (self.name or "PLAYER") and e["balls"] == r["carried"]
                          and abs(e["time"] - round(self.elapsed(), 1)) < 0.05), 99)
            if place == 0:
                t.add("NEW RECORD!", mid, 290, 36, PINK, "mm")
            elif place < 10:
                t.add(f"#{place + 1} on the leaderboard", mid, 290, 28, CYAN, "mm")
            gaps = [b - a for a, b in zip([0.0] + r["splits"], r["splits"])]
            if gaps:
                t.add(f"Fastest ball {min(gaps):.1f}s   ·   Dropped early {r['drops']}", mid,
                      350, 20, INK, "mm")
            t.add("Put the balls back on the left, then press ENTER", mid, 430, 18, DIM, "mm")


def how_to_play(keyboard):
    """The steps shown before every game."""
    move = "W A S D move Robo" if keyboard else "Robo's gripper follows your hand"
    grab = "press Space" if keyboard else "make a fist"
    drop = "press Space again" if keyboard else "open your hand"
    return [
        (f"{move}", "Move it over a ball on the LEFT side of the table."),
        (f"To grab, {grab}", "Robo reaches down and picks the ball up."),
        ("Carry it across", "Move over the gold middle line to the RIGHT side."),
        (f"To let go, {drop}", "On the right side the ball counts: +1."),
        ("Dropped it too early?", "Just pick it up again and finish the carry."),
        (f"Carry all {BALLS} balls", "The stopwatch stops at the last one. P pauses it. "
                                     "Fastest time wins!"),
    ]


def main():
    parser = argparse.ArgumentParser(description="Ball Carry: carry the balls across with Robo.")
    parser.add_argument("--no-arm", action="store_true",
                        help="no robot: a pretend arm and pretend balls")
    parser.add_argument("--keyboard", action="store_true",
                        help="control Robo with W A S D and Space instead of your hand")
    parser.add_argument("--camera", default="/dev/video0",
                        help="the camera facing the player (default /dev/video0)")
    parser.add_argument("--tracker", default="auto", choices=["auto", "mediapipe", "yolo"])
    parser.add_argument("--fullscreen", action="store_true")
    args, args.ros_args = parser.parse_known_args()

    try:
        game = Game(args)
    except RuntimeError as error:      # no camera
        print(error)
        return
    why = game.robot.start()
    if why:
        print(f"Can't start the arm: {why}")
        game.robot.stop()
        return
    cv2.namedWindow("Ball Carry", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Ball Carry", W, H)
    if args.fullscreen:
        cv2.setWindowProperty("Ball Carry", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    try:
        while True:
            cv2.imshow("Ball Carry", game.step())
            key = cv2.waitKey(1)
            if key != -1 and not game.key(key & 0xFF):
                break
            if cv2.getWindowProperty("Ball Carry", cv2.WND_PROP_VISIBLE) < 1:
                break
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        if not game.keyboard:
            game.tracking.close()
            game.camera.close()
        game.robot.stop()


if __name__ == "__main__":
    main()
