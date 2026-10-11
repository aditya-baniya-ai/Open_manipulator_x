"""
BALL CARRY: move Robo with your hand, grab the ball the screen asks for, and carry it
to the other side. As many balls as you can in 60 seconds.

Colored balls start on the left of the table (the PICKUP zone). The screen says which
one to carry next: "Carry the GREEN ball". Move your hand: Robo follows. Close your hand
(fist): Robo goes down and grabs. Move over the right side (the DROP zone) and open your
hand: Robo lets go. A camera looking at the table checks the ball really got there,
by its color.

    Right ball delivered    +1000 points (the ball counts)
    Wrong ball delivered    no points ("we needed the GREEN one")
    All balls in time       +10 points for every second left
    Max score               5,600 (all 5 balls, with time to spare)

Two cameras: one facing the player (the hand), one looking at the table (the balls).
No second camera yet? Use --keyboard: W A S D move Robo, Space grabs and lets go.

Set up the table camera first (once):  python3 balls.py setup --camera /dev/video2
Then (see README.md, "Ball Carry"):
    python3 ball_carry.py --no-arm                  no robot: a pretend arm and table
    python3 ball_carry.py --table-camera /dev/video2
    python3 ball_carry.py --keyboard --table-camera /dev/video0
"""

import argparse
import json
import math
import random
import time
from pathlib import Path

import cv2
import numpy as np

import arm_link
import balls as ballvision
from puppet_master import (CAMERA_BOX, CYAN, DIM, FOOTER_BOX, GOLD, GREEN, H, INK, MAP_BOX,
                           PINK, RED, Camera, Text, Tracking, W, background, glow_circle, panel)
from tracker import PLAY_AREA, make_tracker

LEADERBOARD = Path(__file__).with_name("ball_leaderboard.json")
ROUND_TIME = 60.0
BALL_POINTS = 1000
TIME_BONUS = 10            # points per second left, when every ball is delivered
SHOW_HAND_FOR = 1.0
KEY_STEP = 0.04            # how far one key press moves Robo (play-area units)


def load_board():
    try:
        return json.loads(LEADERBOARD.read_text())
    except (OSError, ValueError):
        return []


def rank_for(balls, total):
    return "S" if balls >= total else "A" if balls >= total - 1 else \
        "B" if balls >= total - 2 else "C"


# --- A pretend table (for --no-arm): balls you can really move with the pretend arm ---

class VirtualTable:
    """Draws a table seen from above with the balls on it, as the table camera would
    see it. The pretend arm can pick the balls up and put them down."""

    def __init__(self, robot, colors):
        self.robot, self.held = robot, None
        spots = [(120, -100), (160, -95), (200, -80), (125, -135), (150, -140)]   # all in reach
        self.balls = {name: spot for name, spot in zip(colors, spots)}
        self.was_closed = False
        self.frame = None

    @staticmethod
    def to_pixel(x, y):
        return int(320 + y * 1.4), int(480 - (x - 40) * 1.9)

    def update(self):
        x, y, z, _ = arm_link.arm.forward(self.robot.joints())
        if self.robot.closed and not self.was_closed and z < arm_link.GRAB_HEIGHT + 15:
            near = [(math.dist((x, y), spot), name) for name, spot in self.balls.items()]
            if near and min(near)[0] < 20:
                self.held = min(near)[1]
        if not self.robot.closed:
            self.held = None
        self.was_closed = self.robot.closed
        if self.held:
            self.balls[self.held] = (x, y)
        self.frame = self.draw((x, y))

    def draw(self, gripper):
        image = np.full((480, 640, 3), (150, 155, 160), np.uint8)
        for name, (x, y) in self.balls.items():
            color = ballvision.COLORS[name]["draw"]
            radius = 30 if name == self.held else 27      # lifted: a bit bigger
            cv2.circle(image, self.to_pixel(x, y), radius, color, -1, cv2.LINE_AA)
        cv2.circle(image, self.to_pixel(*gripper), 34, (60, 60, 60), 3, cv2.LINE_AA)
        return image


class Game:
    def __init__(self, args):
        self.args = args
        self.text = Text()
        self.background = background()
        for box in (CAMERA_BOX, MAP_BOX, FOOTER_BOX):
            panel(self.background, box)
        self.robot = arm_link.VirtualArm() if args.no_arm \
            else arm_link.RealArm(ros_args=args.ros_args)

        # The table: the real table camera, or the pretend table
        self.setup = ballvision.load_setup()
        if args.no_arm and not args.table_camera:
            self.setup = ballvision.default_setup()
            self.table = VirtualTable(self.robot, list(self.setup["colors"]))
            self.table_camera = None
        else:
            if self.setup is None:
                raise RuntimeError("Set up the table camera first:  "
                                   "python3 balls.py setup --camera " + str(args.table_camera))
            self.table, self.table_camera = None, Camera(args.table_camera, mirror=False)
        self.finder = ballvision.BallFinder(self.setup)
        self.colors = list(self.setup["colors"])

        # The player: hand tracking, or the keyboard
        self.keyboard = args.keyboard
        if not self.keyboard:
            self.camera = Camera(args.camera)
            self.tracking = Tracking(make_tracker(args.tracker), self.camera)
        self.cursor = [0.5, 0.5]
        self.hand, self.hand_since, self.hand_seen, self.was_fist = None, None, 0.0, False

        self.state, self.name = "title", ""
        self.board = load_board()
        self.round = None
        self.balls, self.zones, self.vision_ms = {}, {}, 0.0
        self.message, self.message_at = "", 0.0
        self.countdown_at = self.result_at = 0.0

    # -- the round ------------------------------------------------------------------
    def new_round(self):
        self.round = {"started": time.monotonic(), "delivered": [], "wrong": [],
                      "judge": ballvision.Judge(), "want": None, "times": [],
                      "asked_at": time.monotonic(), "finished": None}
        self.pick_next()

    def left(self):
        r = self.round
        end = r["finished"] or time.monotonic()
        return max(0.0, ROUND_TIME - (end - r["started"]))

    def score(self):
        r = self.round
        if not r:
            return 0
        points = BALL_POINTS * len(r["delivered"])
        if len(r["delivered"]) == len(self.colors):
            points += int(TIME_BONUS * self.left())
        return points

    def pick_next(self):
        """Ask for a ball that's still waiting (preferably one the camera sees on the left)."""
        r = self.round
        waiting = [c for c in self.colors if c not in r["judge"].delivered]
        on_left = [c for c in waiting if self.zones.get(c) == "pickup"]
        r["want"] = random.choice(on_left or waiting) if waiting else None
        r["asked_at"] = time.monotonic()

    def say(self, message):
        self.message, self.message_at = message, time.monotonic()

    # -- each frame -------------------------------------------------------------------
    def step(self):
        now = time.monotonic()
        self.robot.update()
        if self.table:
            self.table.update()
            table_frame = self.table.frame
        else:
            table_frame = self.table_camera.frame
        if table_frame is not None:
            started = time.perf_counter()
            self.balls = self.finder.find(table_frame)
            self.zones = {c: self.finder.zone_of(b, table_frame.shape) for c, b in self.balls.items()}
            self.vision_ms = 0.9 * self.vision_ms + 0.1 * (time.perf_counter() - started) * 1000

        hand_frame = None
        if not self.keyboard:
            hand_frame, self.hand = self.tracking.frame, self.tracking.hand
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
                self.new_round()
        elif self.state == "play":
            self.play()
        elif self.state == "results" and now - self.result_at > 15.0:
            self.state = "title"
        return self.draw(hand_frame, table_frame)

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
            if fist and not self.robot.closed:
                self.robot.grab()
            elif not fist and self.robot.closed:
                self.robot.release()
        self.was_fist = fist

    def toggle_grip(self):
        if self.state == "play":
            self.robot.release() if self.robot.closed else self.robot.grab()

    def play(self):
        r = self.round
        self.control()
        newly = r["judge"].update(self.balls, self.zones, gripper_open=not self.robot.closed)
        for color in newly:
            if color == r["want"]:
                r["delivered"].append(color)
                r["times"].append(time.monotonic() - r["asked_at"])
                self.say(f"+{BALL_POINTS}  {color.upper()} delivered!")
            else:
                r["wrong"].append(color)
                self.say(f"Wrong ball! We needed {r['want'].upper()}")
            if color == r["want"] or r["want"] in r["judge"].delivered:
                self.pick_next()
        if r["want"] is None and not r["finished"]:
            r["finished"] = time.monotonic()        # every ball delivered: stop the clock
        if (self.left() <= 0 or r["finished"]) and not self.robot.busy():
            self.finish()

    def finish(self):
        r = self.round
        r["finished"] = r["finished"] or time.monotonic()
        entry = {"name": self.name or "PLAYER", "score": self.score(),
                 "balls": len(r["delivered"]), "time": round(ROUND_TIME - self.left(), 1),
                 "date": time.strftime("%Y-%m-%d")}
        self.board.append(entry)
        self.board.sort(key=lambda e: -e["score"])
        LEADERBOARD.write_text(json.dumps(self.board[:10], indent=1) + "\n")
        self.state, self.result_at = "results", time.monotonic()
        if self.robot.closed:
            self.robot.release()

    def key(self, key):
        if key == 27:
            return False
        if self.state == "title":
            if key in (13, 10):
                self.state = "ready"
            elif key in (8, 127):
                self.name = self.name[:-1]
            elif 32 <= key < 127 and len(self.name) < 12:
                self.name += chr(key).upper()
            return True
        if self.state == "results" and key in (13, 10):
            self.state, self.name = "title", ""
        elif self.keyboard:
            moves = {ord("a"): (-KEY_STEP, 0), ord("d"): (KEY_STEP, 0),
                     ord("w"): (0, -KEY_STEP), ord("s"): (0, KEY_STEP)}
            if key in moves:
                dx, dy = moves[key]
                self.cursor = [min(1, max(0, self.cursor[0] + dx)),
                               min(1, max(0, self.cursor[1] + dy))]
            elif key == 32:
                self.toggle_grip()
        return True

    # -- drawing ----------------------------------------------------------------------
    def draw(self, hand_frame, table_frame):
        canvas = self.background.copy()
        self.draw_header(canvas)
        self.draw_player(canvas, hand_frame)
        self.draw_table(canvas, table_frame)
        self.draw_footer(canvas)
        if self.state != "play":
            canvas = self.text.draw(canvas)
            self.draw_overlay(canvas)
        return self.text.draw(canvas)

    def draw_header(self, canvas):
        t = self.text
        t.add("BALL", 30, 22, 38, GOLD)
        t.add("CARRY", 140, 22, 38, CYAN)
        t.add("move Robo with your hand, carry the balls", 32, 66, 15, DIM)
        r = self.round if self.state in ("play", "results") else None
        delivered = len(r["delivered"]) if r else 0
        t.add(f"{delivered} / {len(self.colors)}", W // 2, 42, 54, INK, "mm")
        t.add("BALLS", W // 2, 82, 14, DIM, "mm")
        best = self.board[0]["score"] if self.board else 0
        t.add("HIGH SCORE", W - 30, 20, 14, DIM, "ra")
        t.add(f"{best:,}", W - 30, 38, 28, GOLD, "ra")
        if r:
            left = self.left()
            cv2.rectangle(canvas, (870, 76), (1250, 86), (70, 50, 60), -1)
            cv2.rectangle(canvas, (870, 76), (870 + int(380 * left / ROUND_TIME), 86),
                          RED if left < 10 else CYAN, -1)
            t.add(f"{left:4.1f}s", 860, 81, 18, RED if left < 10 else INK, "rm")

    def draw_player(self, canvas, frame):
        left, top, right, bottom = CAMERA_BOX
        t = self.text
        if self.keyboard:
            t.add("KEYBOARD CONTROL", left + 20, top + 20, 18, GOLD)
            for i, (keys, what) in enumerate([("W  A  S  D", "move Robo"),
                                              ("SPACE", "grab / let go"),
                                              ("ESC", "quit")]):
                t.add(keys, left + 40, top + 80 + i * 50, 26, INK)
                t.add(what, left + 260, top + 84 + i * 50, 20, DIM)
            return
        if frame is None:
            t.add("Waiting for the player camera ...", (left + right) // 2,
                  (top + bottom) // 2, 22, DIM, "mm")
            return
        width, height = right - left - 10, bottom - top - 10
        view = (cv2.resize(frame, (width, height)) * 0.75).astype(np.uint8)
        a = PLAY_AREA
        cv2.rectangle(view, (int(a[0] * width), int(a[1] * height)),
                      (int(a[2] * width), int(a[3] * height)), (120, 90, 100), 1, cv2.LINE_AA)
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
        t.add("FIST = GRAB   ·   OPEN HAND = LET GO", left + 15, bottom - 32, 16, DIM)

    def draw_table(self, canvas, frame):
        left, top, right, bottom = MAP_BOX
        t = self.text
        t.add("THE TABLE (checked by the camera)", left + 15, top + 12, 16, DIM)
        width = right - left - 20
        height = width * 3 // 4
        x0, y0 = left + 10, top + 40
        if frame is None:
            t.add("Waiting for the table camera ...", (left + right) // 2, y0 + height // 2,
                  20, DIM, "mm")
        else:
            view = cv2.resize(frame, (width, height))
            sx, sy = width / frame.shape[1], height / frame.shape[0]
            for zone, color in (("pickup", (200, 200, 200)), ("drop", GREEN)):
                l, tp, r, b = self.setup[zone]
                cv2.rectangle(view, (int(l * width), int(tp * height)),
                              (int(r * width), int(b * height)), color, 2, cv2.LINE_AA)
            want = self.round["want"] if self.round and self.state == "play" else None
            for name, (x, y, radius) in self.balls.items():
                spot = (int(x * sx), int(y * sy))
                color = ballvision.COLORS.get(name, {}).get("draw", INK)
                if name == want:
                    glow_circle(view, spot, radius * sx + 10, color, 3)
                else:
                    cv2.circle(view, spot, int(radius * sx) + 5, INK, 2, cv2.LINE_AA)
            canvas[y0:y0 + height, x0:x0 + width] = view
            for zone, label in (("pickup", "PICK UP"), ("drop", "DROP HERE")):
                l, tp, r, b = self.setup[zone]
                cx, cy = x0 + int((l + r) / 2 * width), y0 + int(tp * height) - 12
                cy = max(cy, y0 + 12)
                # A dark tag behind the label, so it shows on any table color
                cv2.rectangle(canvas, (cx - 55, cy - 11), (cx + 55, cy + 11), (35, 25, 30), -1)
                t.add(label, cx, cy, 14, GREEN if zone == "drop" else INK, "mm")
        # What to do now
        banner_y = y0 + height + 40
        r = self.round if self.state == "play" else None
        if r and r["want"]:
            color = ballvision.COLORS.get(r["want"], {}).get("draw", INK)
            cv2.circle(canvas, (left + 50, banner_y + 25), 22, color, -1, cv2.LINE_AA)
            t.add("CARRY THE", left + 90, banner_y + 8, 18, DIM)
            t.add(f"{r['want'].upper()} BALL  →", left + 90, banner_y + 28, 34, color)
        holding = "HOLDING" if self.robot.closed else "GRIPPER OPEN"
        t.add(holding, right - 20, banner_y + 25, 18, PINK if self.robot.closed else DIM, "rm")
        if self.message and time.monotonic() - self.message_at < 2.0:
            good = self.message.startswith("+")
            t.add(self.message, (left + right) // 2, bottom - 30, 24, GREEN if good else RED, "mm")

    def draw_footer(self, canvas):
        left, top, right, bottom = FOOTER_BOX
        t = self.text
        r = self.round if self.state in ("play", "results") else None
        stats = [("SCORE", f"{self.score():,}" if r else "0"),
                 ("WRONG BALLS", len(r["wrong"]) if r else 0),
                 ("AVG PER BALL", f"{sum(r['times']) / len(r['times']):.1f}s"
                  if r and r["times"] else "-")]
        for i, (label, value) in enumerate(stats):
            x = left + 20 + i * 205
            t.add(label, x, top + 15, 13, DIM)
            t.add(value, x, top + 35, 26, INK)
        control = "keyboard" if self.keyboard else f"{self.tracking.tracker.name} " \
            f"{self.tracking.ms:.0f} ms"
        t.add(f"{control}  ·  colors {self.vision_ms:.1f} ms  ·  {self.robot.name}",
              left + 20, bottom - 18, 12, DIM)

    def draw_overlay(self, canvas):
        overlay = canvas.copy()
        cv2.rectangle(overlay, (0, 0), (W, H), (15, 8, 10), -1)
        dark = 0.5 if self.state == "countdown" else 0.88
        cv2.addWeighted(overlay, dark, canvas, 1 - dark, 0, canvas)
        t, mid = self.text, W // 2
        grab = "Space" if self.keyboard else "Close your hand"
        if self.state == "title":
            t.add("BALL CARRY", mid, 130, 72, GOLD, "mm")
            t.add("Carry the ball the screen asks for to the right side. "
                  "As many as you can in 60 s!", mid, 195, 20, INK, "mm")
            t.add(f"{grab} to grab, let go over the DROP zone. "
                  "The camera checks every ball.", mid, 225, 17, DIM, "mm")
            t.add("TYPE YOUR NAME", mid, 300, 16, DIM, "mm")
            cursor = "_" if int(time.monotonic() * 2) % 2 else " "
            t.add(self.name + cursor, mid, 345, 46, CYAN, "mm")
            t.add("press ENTER to play", mid, 400, 18, INK, "mm")
            t.add("TOP 10", mid, 460, 18, GOLD, "mm")
            for i, e in enumerate(self.board[:10]):
                x, y = mid - 300 + (i // 5) * 320, 495 + (i % 5) * 32
                t.add(f"{i + 1:>2}. {e['name'][:12]}", x, y, 20, INK)
                t.add(f"{e['balls']} balls  {e['score']:,}", x + 280, y, 20, GOLD, "ra")
            if not self.board:
                t.add("Be the first on the board!", mid, 500, 20, DIM, "mm")
        elif self.state == "ready":
            t.add(f"Get ready, {self.name or 'player'}!", mid, 250, 44, INK, "mm")
            t.add("Put all the balls in the PICK UP zone on the left", mid, 310, 22, CYAN, "mm")
            if not self.keyboard:
                t.add("Hold your hand up in front of the camera", mid, 350, 22, INK, "mm")
        elif self.state == "countdown":
            t.add(str(max(1, 3 - int(time.monotonic() - self.countdown_at))), mid, H // 2,
                  160, GOLD, "mm")
            t.add(f"Move: Robo follows. {grab}: grab.", mid, H // 2 + 120, 22, INK, "mm")
        elif self.state == "results":
            r = self.round
            done = len(r["delivered"])
            rank = rank_for(done, len(self.colors))
            heading = "ALL DONE!" if done == len(self.colors) else \
                "TIME!" if self.left() <= 0 else "ALL BALLS MOVED"
            t.add(heading, mid, 110, 40, DIM, "mm")
            t.add(f"{done} / {len(self.colors)} balls", mid, 200, 80, GOLD, "mm")
            t.add(f"{self.score():,} points   ·   RANK {rank}", mid, 280, 34,
                  {"S": PINK, "A": GOLD, "B": CYAN}.get(rank, INK), "mm")
            if self.board and self.board[0]["score"] == self.score() and \
                    self.board[0]["name"] == (self.name or "PLAYER"):
                t.add("NEW HIGH SCORE!", mid, 340, 30, PINK, "mm")
            t.add(f"Wrong balls {len(r['wrong'])}", mid, 400, 20, INK, "mm")
            t.add("Put the balls back on the left, then press ENTER", mid, 460, 18, DIM, "mm")


def main():
    parser = argparse.ArgumentParser(description="Ball Carry: carry the balls with Robo.")
    parser.add_argument("--no-arm", action="store_true",
                        help="no robot: a pretend arm (and a pretend table, unless "
                             "--table-camera is given)")
    parser.add_argument("--keyboard", action="store_true",
                        help="control Robo with W A S D and Space instead of your hand")
    parser.add_argument("--camera", default="/dev/video0",
                        help="the camera facing the player (default /dev/video0)")
    parser.add_argument("--table-camera", help="the camera looking at the table")
    parser.add_argument("--tracker", default="auto", choices=["auto", "mediapipe", "yolo"])
    parser.add_argument("--fullscreen", action="store_true")
    args, args.ros_args = parser.parse_known_args()
    if not args.no_arm and not args.table_camera:
        parser.error("give the table camera, e.g. --table-camera /dev/video2 "
                     "(or --no-arm to try it without the robot)")

    try:
        game = Game(args)
    except RuntimeError as error:
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
        if game.table_camera:
            game.table_camera.close()
        game.robot.stop()


if __name__ == "__main__":
    main()
