"""
CHOCOLATE CATCHER: a claw machine (crane game) with Robo as the claw.

Steer the claw with your hand over a chocolate (or a small toy). Make a fist, or press
Enter, and the claw drops, grabs and comes back up. Then Robo carries the prize to the
PRIZE CHUTE by itself and lets go. Still holding it when it gets there? You win it!
Like a real claw machine, a prize can slip out on the way.

    3 tries per player, 20 seconds to aim each (then the claw drops by itself)
    Most prizes wins (then the fastest aiming)

Robo checks every win itself: the gripper must still be holding the prize (a prize
stops the fingers partway; empty, they close all the way) when it reaches the chute.
Prizes: wrapped chocolate balls or small soft toys, about 25 to 45 mm, work best (flat
chocolate bars are too thin to grab).

    python3 claw_machine.py --no-arm       no robot: a pretend claw and pretend prizes
    python3 claw_machine.py                with Robo's arm (real or simulated) running
    python3 claw_machine.py --keyboard     W A S D move the claw, Enter or Space drops it
"""

import argparse
import json
import math
import time
from pathlib import Path

import cv2
import numpy as np

import arm_link
from ball_carry import VirtualBalls, to_map
from puppet_master import (CAMERA_BOX, CYAN, DIM, FOOTER_BOX, GOLD, GREEN, H, INK, MAP_BOX,
                           PINK, RED, Camera, Text, Tracking, W, background, glow_circle, panel)
from tracker import PLAY_AREA, make_tracker

LEADERBOARD = Path(__file__).with_name("claw_leaderboard.json")
TRIES = 3
AIM_TIME = 20.0           # seconds to aim each try; then the claw drops by itself
CHUTE = (0.95, 0.45)      # where the prize chute is (play-area position: right side)
SHOW_HAND_FOR = 1.0
KEY_STEP = 0.04
CHOCOLATE = (30, 80, 140)    # BGR colour of the prizes on the map


def load_board():
    try:
        return json.loads(LEADERBOARD.read_text())
    except (OSError, ValueError):
        return []


def plural(count, word):
    return f"{count} {word}" + ("" if count == 1 else "s")


def how_to_play(keyboard):
    move = "W A S D move the claw" if keyboard else "The claw follows your hand"
    drop = "press Enter (or Space)" if keyboard else "make a fist"
    return [
        (move, "Line it up over a chocolate. You have 20 seconds each try."),
        (f"To drop the claw, {drop}", "It goes down, grabs, and comes back up."),
        ("Robo carries it to the chute", "All by itself, like a real claw machine."),
        ("Still holding it? You win it!", "Prizes can slip out on the way: aim for the middle."),
        (f"{TRIES} tries", "The most prizes wins. The timer runs out? The claw drops anyway."),
    ]


class Game:
    def __init__(self, args):
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

    def say(self, message):
        self.message, self.message_at = message, time.monotonic()

    # -- a try: aim -> drop (grab) -> carry to the chute -> let go -----------------
    def new_round(self):
        self.round = {"try": 1, "won": 0, "phase": "aim", "aim_started": time.monotonic(),
                      "aim_times": [], "results": [], "phase_at": time.monotonic()}

    def aim_left(self):
        r = self.round
        if not r or r["phase"] != "aim":
            return AIM_TIME
        return max(0.0, AIM_TIME - (time.monotonic() - r["aim_started"]))

    def drop(self):
        """Drop the claw where it is now (fist, Enter, or the timer ran out)."""
        r = self.round
        if r["phase"] != "aim" or not self.robot.grab():
            return
        r["aim_times"].append(AIM_TIME - self.aim_left())
        r["phase"], r["phase_at"] = "grab", time.monotonic()

    def play(self):
        r = self.round
        if r["phase"] == "aim":
            self.control()
            if self.aim_left() <= 0:
                self.say("Time's up: dropping!")
                self.drop()
        elif r["phase"] == "grab" and not self.robot.busy():
            r["phase"] = "carry"                       # up again: off to the chute
        elif r["phase"] == "carry":
            self.robot.follow(*CHUTE)
            u, v, _ = self.robot.gripper_area()
            if math.hypot(u - CHUTE[0], v - CHUTE[1]) < 0.03 and not self.robot.busy():
                won = self.robot.holding()           # still holding it at the chute?
                held = getattr(self.robot, "held", None)
                self.robot.release()
                r["results"].append(won)
                if won:
                    r["won"] += 1
                    self.say("YOU WON A PRIZE!")
                    if self.pretend and held is not None:
                        self.pretend.balls.pop(held)  # it went down the chute
                        self.robot.held = None
                else:
                    self.say("Empty claw... so close!")
                r["phase"], r["phase_at"] = "drop_prize", time.monotonic()
        elif r["phase"] == "drop_prize" and not self.robot.busy():
            if r["try"] >= TRIES:
                self.finish()
            else:
                r["try"] += 1
                r["phase"], r["aim_started"] = "aim", time.monotonic()
                self.was_fist = bool(self.hand and self.hand.whack)

    def control(self):
        if self.keyboard:
            self.robot.follow(*self.cursor)
            return
        if not self.hand:
            return
        self.robot.follow(self.hand.x, self.hand.y)
        fist = self.hand.whack
        if fist and not self.was_fist and self.state == "play":
            self.drop()
        self.was_fist = fist

    def finish(self):
        r = self.round
        entry = {"name": self.name or "PLAYER", "prizes": r["won"],
                 "aim": round(sum(r["aim_times"]), 1), "date": time.strftime("%Y-%m-%d")}
        self.board.append(entry)
        self.board.sort(key=lambda e: (-e["prizes"], e["aim"]))
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
            if self.keyboard:
                self.robot.follow(*self.cursor)
            elif self.hand:
                self.robot.follow(self.hand.x, self.hand.y)
                self.was_fist = self.hand.whack
            if now - self.countdown_at > 3.0:
                self.state = "play"
                self.new_round()
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
        elif self.state == "play":
            if key in (13, 10, 32):
                self.drop()
            elif self.keyboard:
                moves = {ord("a"): (-KEY_STEP, 0), ord("d"): (KEY_STEP, 0),
                         ord("w"): (0, -KEY_STEP), ord("s"): (0, KEY_STEP)}
                if key in moves and self.round["phase"] == "aim":
                    dx, dy = moves[key]
                    self.cursor = [min(1, max(0, self.cursor[0] + dx)),
                                   min(1, max(0, self.cursor[1] + dy))]
        return True

    # -- drawing ----------------------------------------------------------------------
    def draw(self, frame):
        canvas = self.background.copy()
        self.draw_header(canvas)
        self.draw_player(canvas, frame)
        self.draw_table(canvas)
        self.draw_footer(canvas)
        if self.state != "play":
            canvas = self.text.draw(canvas)
            self.draw_overlay(canvas)
        return self.text.draw(canvas)

    def draw_header(self, canvas):
        t = self.text
        t.add("CHOCOLATE", 30, 22, 34, GOLD)
        t.add("CATCHER", 30 + self.text.width("CHOCOLATE ", 34), 22, 34, CYAN)
        t.add("a claw machine with Robo as the claw", 32, 66, 15, DIM)
        r = self.round if self.state in ("play", "results") else None
        t.add(f"{r['won'] if r else 0}", W // 2, 42, 54, INK, "mm")
        t.add("PRIZES", W // 2, 82, 14, DIM, "mm")
        best = self.board[0] if self.board else None
        t.add("BEST", W - 30, 20, 14, DIM, "ra")
        t.add(plural(best["prizes"], "prize") if best else "-", W - 30, 38, 28, GOLD, "ra")
        if r and self.state == "play":
            # The tries: filled = used, and how each one went
            for i in range(TRIES):
                x = W // 2 + 120 + i * 40
                done = i < len(r["results"])
                color = (GREEN if r["results"][i] else RED) if done else \
                    CYAN if i == r["try"] - 1 else DIM
                cv2.circle(canvas, (x, 42), 13, color, -1 if done else 2, cv2.LINE_AA)
            t.add(f"TRY {r['try']} / {TRIES}", W // 2 + 120, 74, 14, DIM, "lm")

    def draw_player(self, canvas, frame):
        left, top, right, bottom = CAMERA_BOX
        t = self.text
        if self.keyboard:
            t.add("KEYBOARD CONTROL", left + 20, top + 20, 18, GOLD)
            for i, (keys, what) in enumerate([("W  A  S  D", "move the claw"),
                                              ("ENTER", "drop the claw"), ("ESC", "quit")]):
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
        t.add("MOVE = AIM   ·   FIST = DROP THE CLAW", left + 15, bottom - 32, 16, DIM)

    def draw_table(self, canvas):
        left, top, right, bottom = MAP_BOX
        t = self.text
        t.add("THE CLAW MACHINE", left + 15, top + 12, 16, DIM)
        points = [to_map(i / 20, 0) for i in range(21)] + [to_map(1 - i / 20, 1) for i in range(21)]
        cv2.fillPoly(canvas, [np.array(points)], (60, 40, 45), cv2.LINE_AA)
        # The prize chute
        chute = to_map(*CHUTE)
        cv2.circle(canvas, chute, 34, (30, 90, 130), -1, cv2.LINE_AA)
        cv2.circle(canvas, chute, 34, GOLD, 2, cv2.LINE_AA)
        t.add("PRIZE", chute[0], chute[1] + 50, 14, GOLD, "mm")
        t.add("CHUTE", chute[0], chute[1] + 66, 14, GOLD, "mm")
        base = ((left + right) // 2, top + 70)
        cv2.circle(canvas, base, 22, (90, 70, 80), -1, cv2.LINE_AA)
        t.add("ROBO", base[0], base[1], 13, INK, "mm")
        if self.pretend:
            for i, (u, v) in enumerate(self.pretend.balls):
                if i != self.robot.held:
                    cv2.circle(canvas, to_map(u, v), 13, CHOCOLATE, -1, cv2.LINE_AA)
                    cv2.circle(canvas, to_map(u, v), 13, (60, 140, 200), 1, cv2.LINE_AA)
        holding = self.robot.holding() if self.robot.command is not None else False
        if self.robot.command is not None:
            u, v, _ = self.robot.gripper_area()
            spot = to_map(u, v)
            if holding:
                cv2.circle(canvas, spot, 13, CHOCOLATE, -1, cv2.LINE_AA)
            # The claw: a cross-hair while aiming
            aiming = self.round and self.state == "play" and self.round["phase"] == "aim"
            color = GOLD if aiming else PINK
            cv2.circle(canvas, spot, 20, color, 3, cv2.LINE_AA)
            if aiming:
                cv2.line(canvas, (spot[0] - 28, spot[1]), (spot[0] + 28, spot[1]), color, 1)
                cv2.line(canvas, (spot[0], spot[1] - 28), (spot[0], spot[1] + 28), color, 1)
        r = self.round if self.state == "play" else None
        if r:
            phase = {"aim": f"AIM AND DROP   {self.aim_left():4.1f}s",
                     "grab": "GRABBING ...", "carry": "TO THE CHUTE ...",
                     "drop_prize": "LETTING GO ..."}[r["phase"]]
            t.add(phase, (left + right) // 2, bottom - 80, 22,
                  RED if r["phase"] == "aim" and self.aim_left() < 5 else INK, "mm")
        if self.message and time.monotonic() - self.message_at < 2.5:
            good = "WON" in self.message
            t.add(self.message, (left + right) // 2, bottom - 40, 28, GREEN if good else RED,
                  "mm")

    def draw_footer(self, canvas):
        left, top, right, bottom = FOOTER_BOX
        t = self.text
        r = self.round if self.state in ("play", "results") else None
        stats = [("PRIZES", f"{r['won']} / {TRIES}" if r else f"0 / {TRIES}"),
                 ("TRIES LEFT", TRIES - len(r["results"]) if r else TRIES),
                 ("AIM TIME", f"{sum(r['aim_times']):.1f}s" if r and r["aim_times"] else "-")]
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
        dark = 0.5 if self.state == "countdown" else 0.88
        cv2.addWeighted(overlay, dark, canvas, 1 - dark, 0, canvas)
        t, mid = self.text, W // 2
        if self.state == "title":
            t.add("CHOCOLATE CATCHER", mid, 130, 64, GOLD, "mm")
            t.add("A claw machine with a real robot. Grab a prize and get it to the chute!",
                  mid, 195, 20, INK, "mm")
            t.add(f"{TRIES} tries. Most prizes wins.", mid, 225, 17, DIM, "mm")
            t.add("TYPE YOUR NAME", mid, 300, 16, DIM, "mm")
            cursor = "_" if int(time.monotonic() * 2) % 2 else " "
            t.add(self.name + cursor, mid, 345, 46, CYAN, "mm")
            t.add("press ENTER", mid, 400, 18, INK, "mm")
            t.add("TOP 10", mid, 460, 18, GOLD, "mm")
            for i, e in enumerate(self.board[:10]):
                x, y = mid - 300 + (i // 5) * 320, 495 + (i % 5) * 32
                t.add(f"{i + 1:>2}. {e['name'][:12]}", x, y, 20, INK)
                t.add(plural(e["prizes"], "prize"), x + 280, y, 20, GOLD, "ra")
            if not self.board:
                t.add("Be the first on the board!", mid, 500, 20, DIM, "mm")
        elif self.state == "howto":
            t.add("HOW TO PLAY", mid, 70, 52, GOLD, "mm")
            t.add("Robo checks every win itself: the prize must still be in the claw at "
                  "the chute.", mid, 120, 17, DIM, "mm")
            for i, (big, small) in enumerate(how_to_play(self.keyboard)):
                y = 190 + i * 82
                cv2.circle(canvas, (mid - 330, y + 8), 22, CYAN, 2, cv2.LINE_AA)
                t.add(str(i + 1), mid - 330, y + 8, 22, CYAN, "mm")
                t.add(big, mid - 290, y - 6, 26, INK)
                t.add(small, mid - 290, y + 26, 18, DIM)
            t.add("press ENTER to start", mid, 640, 24, GREEN, "mm")
            t.add("Backspace: change your name", mid, 675, 14, DIM, "mm")
        elif self.state == "ready":
            t.add(f"Get ready, {self.name or 'player'}!", mid, 250, 44, INK, "mm")
            t.add("Put the prizes on the table, away from the chute", mid, 310, 22, CYAN, "mm")
            if not self.keyboard:
                t.add("Hold your hand up in front of the camera", mid, 350, 22, INK, "mm")
        elif self.state == "countdown":
            t.add(str(max(1, 3 - int(time.monotonic() - self.countdown_at))), mid, H // 2,
                  160, GOLD, "mm")
            t.add("Aim with your hand. Fist = drop the claw!" if not self.keyboard else
                  "W A S D to aim. Enter = drop the claw!", mid, H // 2 + 120, 22, INK, "mm")
        elif self.state == "results":
            r = self.round
            t.add("GAME OVER", mid, 110, 40, DIM, "mm")
            t.add(f"{r['won']} / {TRIES} " + ("prize" if TRIES == 1 else "prizes"), mid, 200, 80,
                  GOLD, "mm")
            if r["won"] and self.board and self.board[0]["name"] == (self.name or "PLAYER") \
                    and self.board[0]["prizes"] == r["won"]:
                t.add("NEW RECORD!", mid, 285, 34, PINK, "mm")
            t.add("   ".join("WON" if w else "missed" for w in r["results"]), mid, 345, 22,
                  INK, "mm")
            t.add("Put the prizes back, then press ENTER", mid, 430, 18, DIM, "mm")


def main():
    parser = argparse.ArgumentParser(description="Chocolate Catcher: a claw machine with Robo.")
    parser.add_argument("--no-arm", action="store_true",
                        help="no robot: a pretend claw and pretend prizes")
    parser.add_argument("--keyboard", action="store_true",
                        help="W A S D move the claw, Enter or Space drops it")
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
