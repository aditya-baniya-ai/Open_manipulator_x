"""
CHOCOLATE CATCHER: a claw machine with Robo as the claw. You only win the chocolates
you get into the basket.

    Hand left / right       the claw moves left / right
    Hand up / down          the claw moves toward you / away from you
    Make a fist             the claw goes down, grabs, and comes back up at the same spot
    Keep the fist           the claw stays closed and holds the chocolate while you move
    Open your hand          the claw opens and the chocolate drops

The moment you grab a chocolate, a timer starts: get it to the BASKET and open your
hand before the time runs out. While it's carrying, the claw moves a bit slower. If the
time runs out, the claw opens by itself and the chocolate drops where it is.
A chocolate counts only if it's dropped over the basket.

Robo checks everything itself: "holding" means a chocolate stopped the gripper fingers
partway (empty, they close all the way), and the basket is a spot it knows.

    python3 claw_machine.py --no-arm       no robot: a pretend claw and pretend prizes
    python3 claw_machine.py                with Robo's arm (real or simulated) running
    python3 claw_machine.py --keyboard     W A S D move the claw, Space = fist on / off
"""

import argparse
import json
import math
import time
from pathlib import Path

import cv2
import numpy as np

import arm_link
from ball_carry import VirtualBalls
from puppet_master import (CYAN, DIM, GOLD, GREEN, H, INK, PINK, RED, Camera, Text, Tracking,
                           W, background, glow_circle, panel)
from tracker import PLAY_AREA, make_tracker

LEADERBOARD = Path(__file__).with_name("claw_leaderboard.json")
TRIES = 5                 # grabs per player
CARRY_TIME = 10.0         # seconds from grabbing to dropping it in the basket
BASKET = (0.9, 0.35)      # where the basket is (play-area position: right side, near you)
BASKET_RADIUS = 0.12      # how close (play-area units) counts as over the basket
SHOW_HAND_FOR = 1.0
KEY_STEP = 0.04
CHOCOLATE = (30, 80, 140)            # BGR colour of the prizes

# Screen layout: the camera big on the left, the score and timer on the right
VIEW = (30, 95, 830, 695)            # left, top, right, bottom (800 x 600: 4:3 camera)
SIDE_BOX = (860, 95, 1250, 695)


def load_board():
    """The saved top 10. Scores saved by an older version of the game (a different
    format) are left out."""
    try:
        board = json.loads(LEADERBOARD.read_text())
    except (OSError, ValueError):
        return []
    return [e for e in board if isinstance(e, dict) and all(k in e for k in ("name", "prizes", "carry"))]


def plural(count, word):
    return f"{count} {word}" + ("" if count == 1 else "s")


def how_to_play(keyboard):
    if keyboard:
        return [("W A S D move the claw", "A / D: left and right.  W / S: toward you and away."),
                ("Space: grab", "The claw goes down, grabs, and comes back up."),
                ("Carry it to the BASKET", f"You have {CARRY_TIME:.0f} seconds once you grab."),
                ("Space again: drop it", "Over the basket? It's yours!"),
                (f"{TRIES} grabs", "Only chocolates in the basket count.")]
    return [("Move your hand: the claw follows", "Left / right, and up = toward you, "
             "down = away from you."),
            ("Make a fist: GRAB", "The claw goes down, grabs, and comes back up."),
            ("Keep the fist and carry it", f"You have {CARRY_TIME:.0f} seconds to reach "
             "the BASKET. The claw moves a bit slower."),
            ("Open your hand: DROP", "Over the basket? It's yours! Time up? It drops."),
            (f"{TRIES} grabs", "Only chocolates in the basket count.")]


class Game:
    def __init__(self, args):
        self.text = Text()
        self.background = background()
        for box in (VIEW, SIDE_BOX):
            panel(self.background, box)
        self.robot = arm_link.VirtualArm() if args.no_arm \
            else arm_link.RealArm(ros_args=args.ros_args)
        self.pretend = VirtualBalls(self.robot) if args.no_arm else None
        self.keyboard = args.keyboard
        if not self.keyboard:
            self.camera = Camera(args.camera)
            self.tracking = Tracking(make_tracker(args.tracker), self.camera)
        self.cursor, self.key_fist = [0.5, 0.5], False
        self.hand, self.hand_since, self.hand_seen = None, None, 0.0
        self.state, self.name = "title", ""
        self.board = load_board()
        self.round = None
        self.message, self.message_good, self.message_at = "", True, 0.0
        self.countdown_at = self.result_at = 0.0

    def say(self, message, good=True):
        self.message, self.message_good, self.message_at = message, good, time.monotonic()

    # -- the player's input: where, and fist or not -------------------------------------
    def control(self):
        """Returns (u, v, fist), or None when the hand isn't seen."""
        if self.keyboard:
            return self.cursor[0], self.cursor[1], self.key_fist
        if not self.hand:
            return None
        return self.hand.x, self.hand.y, self.hand.whack

    # -- a round: aim -> grab -> carry -> drop, TRIES times ----------------------------
    def new_round(self):
        self.round = {"won": 0, "grabs": 0, "phase": "aim", "carry_started": None,
                      "results": [], "carry_times": [], "was_fist": True}

    def carry_left(self):
        r = self.round
        if not r or r["phase"] != "carry":
            return CARRY_TIME
        return max(0.0, CARRY_TIME - (time.monotonic() - r["carry_started"]))

    def over_basket(self):
        u, v, _ = self.robot.gripper_area()
        return math.hypot(u - BASKET[0], v - BASKET[1]) <= BASKET_RADIUS

    def drop(self, why):
        """Open the claw where it is: the try is over. A win if it's over the basket."""
        r = self.round
        holding = self.robot.holding()
        won = holding and self.over_basket()
        held = getattr(self.robot, "held", None)
        self.robot.open_here()
        self.robot.glide = arm_link.MAX_GLIDE
        r["results"].append(won)
        if won:
            r["won"] += 1
            r["carry_times"].append(CARRY_TIME - self.carry_left())
            self.say("IN THE BASKET! It's yours!")
            if self.pretend and held is not None:
                self.pretend.balls.pop(held)         # it's in the basket now
                self.robot.held = None
        elif why == "time":
            self.say("Time's up! The claw opened", good=False)
        elif holding:
            self.say("Dropped outside the basket", good=False)
        else:
            self.say("Nothing in the claw", good=False)
        r["phase"], r["phase_at"] = "dropping", time.monotonic()

    def play(self):
        r = self.round
        seen = self.control()
        if seen:
            u, v, fist = seen
            self.robot.follow(u, v)              # ignored while grabbing (busy)
        else:
            fist = r["was_fist"]                 # hand lost: keep the last state
        started_fist = fist and not r["was_fist"]
        r["was_fist"] = fist

        if r["phase"] == "aim":
            if started_fist and r["grabs"] < TRIES and self.robot.grab():
                r["grabs"] += 1
                r["phase"] = "grab"
        elif r["phase"] == "grab":
            if not self.robot.busy():            # back up at the same spot
                if not fist:
                    self.drop("opened")          # let go during the grab
                elif self.robot.holding():
                    r["phase"], r["carry_started"] = "carry", time.monotonic()
                    self.robot.glide = arm_link.CARRY_GLIDE     # a bit slower now
                    self.say("Got it! To the basket!")
                else:
                    self.drop("empty")
        elif r["phase"] == "carry":
            if not fist:
                self.drop("opened")
            elif self.carry_left() <= 0:
                self.drop("time")
            elif not self.robot.holding():
                self.drop("slipped")
        elif r["phase"] == "dropping":
            if time.monotonic() - r["phase_at"] > arm_link.GRIPPER_WAIT:
                if r["grabs"] >= TRIES:
                    self.finish()
                else:
                    r["phase"] = "aim"

    def finish(self):
        r = self.round
        entry = {"name": self.name or "PLAYER", "prizes": r["won"],
                 "carry": round(sum(r["carry_times"]), 1), "date": time.strftime("%Y-%m-%d")}
        self.board.append(entry)
        self.board.sort(key=lambda e: (-e["prizes"], e["carry"]))
        LEADERBOARD.write_text(json.dumps(self.board[:10], indent=1) + "\n")
        self.state, self.result_at = "results", time.monotonic()

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
            seen = self.control()
            if seen:
                self.robot.follow(seen[0], seen[1])     # practice moving, no grabbing yet
            if now - self.countdown_at > 3.0:
                self.state = "play"
                self.new_round()
                self.round["was_fist"] = bool(seen and seen[2])
        elif self.state == "play":
            self.play()
        elif self.state == "results" and now - self.result_at > 15.0:
            self.state = "title"
        return self.draw(frame)

    def key(self, key):
        if key == 27:
            return False
        if self.state == "title":
            if key in (13, 10):
                self.state = "howto"
            elif key in (8, 127):
                self.name = self.name[:-1]
            elif 32 <= key < 127 and len(self.name) < 12:
                self.name += chr(key).upper()
        elif self.state == "howto":
            if key in (13, 10):
                self.state = "ready"
            elif key in (8, 127):
                self.state = "title"
        elif self.state == "results":
            if key in (13, 10):
                self.state, self.name = "title", ""
        elif self.keyboard:
            moves = {ord("a"): (-KEY_STEP, 0), ord("d"): (KEY_STEP, 0),
                     ord("w"): (0, -KEY_STEP), ord("s"): (0, KEY_STEP)}
            if key in moves:
                dx, dy = moves[key]
                self.cursor = [min(1, max(0, self.cursor[0] + dx)),
                               min(1, max(0, self.cursor[1] + dy))]
            elif key == 32:
                self.key_fist = not self.key_fist        # Space: fist on / off
        return True

    # -- drawing ----------------------------------------------------------------------
    def draw(self, frame):
        canvas = self.background.copy()
        self.draw_header(canvas)
        self.draw_view(canvas, frame)
        self.draw_side(canvas)
        if self.state != "play":
            canvas = self.text.draw(canvas)
            self.draw_overlay(canvas)
        return self.text.draw(canvas)

    def draw_header(self, canvas):
        t = self.text
        t.add("CHOCOLATE", 30, 20, 34, GOLD)
        t.add("CATCHER", 30 + t.width("CHOCOLATE ", 34), 20, 34, CYAN)
        t.add("grab it, carry it, drop it in the basket", 32, 62, 15, DIM)
        best = self.board[0] if self.board else None
        t.add("BEST", W - 30, 18, 14, DIM, "ra")
        t.add(f"{best['name'][:10]}  {plural(best['prizes'], 'chocolate')}" if best else "-",
              W - 30, 36, 24, GOLD, "ra")

    def area_to_view(self, u, v):
        """A play-area position to a point on the camera view (inside the play frame)."""
        left, top, right, bottom = VIEW
        a = PLAY_AREA
        width, height = right - left - 10, bottom - top - 10
        return (left + 5 + int((a[0] + u * (a[2] - a[0])) * width),
                top + 5 + int((a[1] + v * (a[3] - a[1])) * height))

    def draw_view(self, canvas, frame):
        """The camera: the hand, its middle point, the play frame, the basket and
        where the claw is."""
        left, top, right, bottom = VIEW
        width, height = right - left - 10, bottom - top - 10
        if frame is not None:
            view = (cv2.resize(frame, (width, height)) * 0.7).astype(np.uint8)
            canvas[top + 5:bottom - 5, left + 5:right - 5] = view
        elif not self.keyboard:
            self.text.add("Waiting for the camera ...", (left + right) // 2, (top + bottom) // 2,
                          22, DIM, "mm")
        # The play frame: the hand moves the claw inside this box
        a = PLAY_AREA
        frame_tl = (left + 5 + int(a[0] * width), top + 5 + int(a[1] * height))
        frame_br = (left + 5 + int(a[2] * width), top + 5 + int(a[3] * height))
        cv2.rectangle(canvas, frame_tl, frame_br, (170, 130, 150), 2, cv2.LINE_AA)
        self.text.add("PLAY FRAME", frame_tl[0] + 6, frame_tl[1] + 6, 13, DIM)
        self.text.add("toward Robo", (frame_tl[0] + frame_br[0]) // 2, frame_br[1] + 14, 13,
                      DIM, "mm")
        self.text.add("toward you", (frame_tl[0] + frame_br[0]) // 2, frame_tl[1] - 14, 13,
                      DIM, "mm")
        # The basket
        basket = self.area_to_view(*BASKET)
        radius = int(BASKET_RADIUS * (frame_br[0] - frame_tl[0]))
        holding_now = self.robot.holding() if self.robot.command is not None else False
        glow_circle(canvas, basket, radius, GREEN if holding_now else (60, 140, 60), 3)
        self.text.add("BASKET", basket[0], basket[1], 16, GREEN, "mm")
        # Where the claw is now (cross-hair; filled when holding a chocolate)
        if self.robot.command is not None:
            u, v, _ = self.robot.gripper_area()
            claw = self.area_to_view(min(1, max(0, u)), min(1, max(0, v)))
            color = PINK if self.robot.closed else CYAN
            if holding_now:
                cv2.circle(canvas, claw, 12, CHOCOLATE, -1, cv2.LINE_AA)
            cv2.circle(canvas, claw, 20, color, 2, cv2.LINE_AA)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                cv2.line(canvas, (claw[0] + 12 * dx, claw[1] + 12 * dy),
                         (claw[0] + 30 * dx, claw[1] + 30 * dy), color, 2, cv2.LINE_AA)
        # Pretend chocolates (--no-arm only: the real ones are on the real table)
        if self.pretend:
            for i, (u, v) in enumerate(self.pretend.balls):
                if i != getattr(self.robot, "held", None):
                    cv2.circle(canvas, self.area_to_view(u, v), 11, CHOCOLATE, -1, cv2.LINE_AA)
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
        seen = self.control() if self.state in ("play", "countdown") or self.keyboard else \
            (self.hand and (self.hand.x, self.hand.y, self.hand.whack))
        if seen:
            middle = self.area_to_view(seen[0], seen[1])
            glow_circle(canvas, middle, 11, PINK if seen[2] else GOLD)
            self.text.add("FIST" if seen[2] else "OPEN", middle[0], middle[1] - 26, 14,
                          PINK if seen[2] else GOLD, "mm")

    def draw_side(self, canvas):
        left, top, right, bottom = SIDE_BOX
        t, mid = self.text, (left + right) // 2
        r = self.round if self.state in ("play", "results") else None
        # Score
        t.add("CHOCOLATES WON", mid, top + 22, 15, DIM, "mm")
        t.add(str(r["won"] if r else 0), mid, top + 70, 64, GOLD, "mm")
        # Tries
        t.add("GRABS", mid, top + 125, 15, DIM, "mm")
        for i in range(TRIES):
            x = mid - (TRIES - 1) * 22 + i * 44
            done = r is not None and i < len(r["results"])
            current = r is not None and i == len(r["results"]) and self.state == "play"
            color = (GREEN if r["results"][i] else RED) if done else CYAN if current else DIM
            cv2.circle(canvas, (x, top + 158), 15, color, -1 if done else 2, cv2.LINE_AA)
        left_grabs = TRIES - (r["grabs"] if r else 0)
        t.add(f"{left_grabs} left", mid, top + 192, 15, INK, "mm")
        # The carry timer
        cv2.line(canvas, (left + 25, top + 215), (right - 25, top + 215), (90, 60, 70), 1)
        ring = (mid, top + 320)
        if r and self.state == "play" and r["phase"] == "carry":
            remaining = self.carry_left()
            color = RED if remaining < 3 else GOLD
            cv2.ellipse(canvas, ring, (78, 78), -90, 0, 360, (70, 50, 60), 10, cv2.LINE_AA)
            cv2.ellipse(canvas, ring, (78, 78), -90, 0, 360 * remaining / CARRY_TIME, color, 10,
                        cv2.LINE_AA)
            t.add(f"{remaining:.1f}", ring[0], ring[1] - 4, 46, color, "mm")
            t.add("seconds", ring[0], ring[1] + 32, 14, DIM, "mm")
            t.add("TO THE BASKET!", mid, top + 425, 22, color, "mm")
        else:
            phase = r["phase"] if r and self.state == "play" else "aim"
            words = {"aim": ("TIMER", "starts when you grab"),
                     "grab": ("GRABBING ...", "keep your fist closed"),
                     "dropping": ("CLAW OPEN", "next grab coming")}[phase]
            cv2.ellipse(canvas, ring, (78, 78), -90, 0, 360, (70, 50, 60), 10, cv2.LINE_AA)
            t.add(f"{CARRY_TIME:.0f}", ring[0], ring[1] - 4, 46, DIM, "mm")
            t.add(words[0], mid, top + 425, 20, INK, "mm")
            t.add(words[1], mid, top + 450, 14, DIM, "mm")
        # Controls
        cv2.line(canvas, (left + 25, top + 475), (right - 25, top + 475), (90, 60, 70), 1)
        controls = [("Space / W A S D", "grab and drop / move")] if self.keyboard else \
            [("move hand", "move the claw"), ("fist", "grab and hold"), ("open hand", "drop")]
        for i, (gesture, what) in enumerate(controls):
            y = top + 498 + i * 24
            t.add(gesture, left + 30, y, 15, CYAN)
            t.add(what, right - 30, y, 15, DIM, "ra")
        # The latest message
        if self.message and time.monotonic() - self.message_at < 2.5:
            t.add(self.message, (VIEW[0] + VIEW[2]) // 2, VIEW[3] - 30, 30,
                  GREEN if self.message_good else RED, "mm")
        control = "keyboard" if self.keyboard else \
            f"{self.tracking.tracker.name} {self.tracking.ms:.0f} ms"
        t.add(f"{control}  ·  {self.robot.name}", mid, bottom - 16, 12, DIM, "mm")

    def draw_overlay(self, canvas):
        overlay = canvas.copy()
        cv2.rectangle(overlay, (0, 0), (W, H), (15, 8, 10), -1)
        dark = 0.45 if self.state == "countdown" else 0.88
        cv2.addWeighted(overlay, dark, canvas, 1 - dark, 0, canvas)
        t, mid = self.text, W // 2
        if self.state == "title":
            t.add("CHOCOLATE CATCHER", mid, 130, 64, GOLD, "mm")
            t.add("Grab a chocolate with Robo's claw and drop it in the basket. "
                  "Keep what you catch!", mid, 195, 20, INK, "mm")
            t.add(f"{TRIES} grabs. {CARRY_TIME:.0f} seconds to reach the basket each time.",
                  mid, 225, 17, DIM, "mm")
            t.add("TYPE YOUR NAME", mid, 300, 16, DIM, "mm")
            cursor = "_" if int(time.monotonic() * 2) % 2 else " "
            t.add(self.name + cursor, mid, 345, 46, CYAN, "mm")
            t.add("press ENTER", mid, 400, 18, INK, "mm")
            t.add("TOP 10", mid, 460, 18, GOLD, "mm")
            for i, e in enumerate(self.board[:10]):
                x, y = mid - 300 + (i // 5) * 320, 495 + (i % 5) * 32
                t.add(f"{i + 1:>2}. {e['name'][:12]}", x, y, 20, INK)
                t.add(plural(e["prizes"], "chocolate"), x + 280, y, 20, GOLD, "ra")
            if not self.board:
                t.add("Be the first on the board!", mid, 500, 20, DIM, "mm")
        elif self.state == "howto":
            t.add("HOW TO PLAY", mid, 70, 52, GOLD, "mm")
            t.add("Only chocolates dropped in the basket count. Robo checks every one.",
                  mid, 120, 17, DIM, "mm")
            for i, (big, small) in enumerate(how_to_play(self.keyboard)):
                y = 190 + i * 82
                cv2.circle(canvas, (mid - 360, y + 8), 22, CYAN, 2, cv2.LINE_AA)
                t.add(str(i + 1), mid - 360, y + 8, 22, CYAN, "mm")
                t.add(big, mid - 320, y - 6, 26, INK)
                t.add(small, mid - 320, y + 26, 18, DIM)
            t.add("press ENTER to start", mid, 640, 24, GREEN, "mm")
            t.add("Backspace: change your name", mid, 675, 14, DIM, "mm")
        elif self.state == "ready":
            t.add(f"Get ready, {self.name or 'player'}!", mid, 250, 44, INK, "mm")
            t.add("Chocolates on the table, the basket where the screen shows it", mid, 310, 22,
                  CYAN, "mm")
            if not self.keyboard:
                t.add("Hold your open hand up in front of the camera", mid, 350, 22, INK, "mm")
        elif self.state == "countdown":
            t.add(str(max(1, 3 - int(time.monotonic() - self.countdown_at))), mid, H // 2,
                  160, GOLD, "mm")
            t.add("Move your hand: the claw follows. Fist = grab!", mid, H // 2 + 120, 22, INK,
                  "mm")
        elif self.state == "results":
            r = self.round
            t.add("GAME OVER", mid, 110, 40, DIM, "mm")
            t.add(plural(r["won"], "chocolate"), mid, 200, 80, GOLD, "mm")
            t.add("are yours!" if r["won"] else "better luck next time!", mid, 265, 26, INK, "mm")
            if r["won"] and self.board and self.board[0]["name"] == (self.name or "PLAYER") \
                    and self.board[0]["prizes"] == r["won"]:
                t.add("NEW RECORD!", mid, 320, 34, PINK, "mm")
            t.add("   ".join("IN" if w else "miss" for w in r["results"]), mid, 380, 22, INK,
                  "mm")
            t.add("Put the chocolates back on the table, then press ENTER", mid, 440, 18, DIM,
                  "mm")


def main():
    parser = argparse.ArgumentParser(description="Chocolate Catcher: a claw machine with Robo.")
    parser.add_argument("--no-arm", action="store_true",
                        help="no robot: a pretend claw and pretend prizes")
    parser.add_argument("--keyboard", action="store_true",
                        help="W A S D move the claw, Space = fist on / off")
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
    cv2.namedWindow("Chocolate Catcher", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Chocolate Catcher", W, H)
    if args.fullscreen:
        cv2.setWindowProperty("Chocolate Catcher", cv2.WND_PROP_FULLSCREEN,
                              cv2.WINDOW_FULLSCREEN)
    try:
        while True:
            cv2.imshow("Chocolate Catcher", game.step())
            key = cv2.waitKey(1)
            if key != -1 and not game.key(key & 0xFF):
                break
            if cv2.getWindowProperty("Chocolate Catcher", cv2.WND_PROP_VISIBLE) < 1:
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
