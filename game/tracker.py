"""
Hand tracking for the Puppet Master game: where the player's hand is, and whether
they're making a fist (the "whack" button).

Two ways to do it, with the same result:
    MediaPipeHands   MediaPipe's hand model: 21 points per hand, so it can see a fist.
                     Runs on the CPU.
    YoloPose         YOLO pose (the same YOLO as detection, can run on the GPU with
                     TensorRT): 17 body points but no fingers, so "whack" is raising
                     your other hand above your shoulder instead of a fist.

Both return a Hand (or None if no hand is seen):
    x, y     where the hand is, 0 to 1 (0, 0 = top left of the play area), as the
             player sees it in the mirrored picture
    whack    True while making a fist (MediaPipe) or the other hand is up (YOLO)
    points   the tracked points in picture pixels, to draw on screen

Speed tips used here: the picture is made smaller before tracking (hands and bodies
are big in the picture, so 320 pixels wide is plenty); MediaPipe uses its lightest
model and follows the hand from frame to frame instead of searching every time;
YOLO uses the TensorRT model when there is one (see README, "Puppet Master").
"""

import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2

# The part of the picture the hand moves around in (fractions of the width/height).
# Smaller = less arm movement needed to reach the edges.
PLAY_AREA = (0.15, 0.10, 0.85, 0.80)   # left, top, right, bottom
TRACK_WIDTH = 320                      # pixels: picture size used for tracking


@dataclass
class Hand:
    x: float
    y: float
    whack: bool
    points: list = field(default_factory=list)   # (x, y) pixels in the mirrored picture
    lines: list = field(default_factory=list)    # pairs of point indexes to draw


def to_play_area(x, y):
    """Picture position (0-1, mirrored) to play-area position (0-1, clamped)."""
    left, top, right, bottom = PLAY_AREA
    return (min(1.0, max(0.0, (x - left) / (right - left))),
            min(1.0, max(0.0, (y - top) / (bottom - top))))


def shrink(frame):
    height, width = frame.shape[:2]
    if width <= TRACK_WIDTH:
        return frame
    return cv2.resize(frame, (TRACK_WIDTH, height * TRACK_WIDTH // width),
                      interpolation=cv2.INTER_AREA)


class MediaPipeHands:
    name = "mediapipe"
    # Fingertip and the joint below it, for index, middle, ring and little finger
    FINGERS = [(8, 6), (12, 10), (16, 14), (20, 18)]
    PALM = [0, 5, 9, 17]

    def __init__(self):
        import mediapipe as mp
        self.mp = mp
        self.hands = mp.solutions.hands.Hands(
            static_image_mode=False,      # follow the hand between frames (much faster)
            max_num_hands=1,
            model_complexity=0,           # the lightest, fastest model
            min_detection_confidence=0.6,
            min_tracking_confidence=0.5)
        self.lines = list(mp.solutions.hands.HAND_CONNECTIONS)

    def track(self, frame):
        """frame: the mirrored camera picture (BGR)."""
        small = shrink(frame)
        result = self.hands.process(cv2.cvtColor(small, cv2.COLOR_BGR2RGB))
        if not result.multi_hand_landmarks:
            return None
        marks = result.multi_hand_landmarks[0].landmark
        height, width = frame.shape[:2]
        points = [(m.x * width, m.y * height) for m in marks]

        def dist(a, b):
            return ((marks[a].x - marks[b].x) ** 2 + (marks[a].y - marks[b].y) ** 2) ** 0.5
        # A finger is folded when its tip is closer to the wrist than its middle joint.
        # A fist folds all four (pointing folds only three, so it doesn't count)
        folded = sum(dist(tip, 0) < dist(joint, 0) for tip, joint in self.FINGERS)
        cx = sum(marks[i].x for i in self.PALM) / len(self.PALM)
        cy = sum(marks[i].y for i in self.PALM) / len(self.PALM)
        x, y = to_play_area(cx, cy)
        return Hand(x, y, folded == 4, points, self.lines)


class YoloPose:
    name = "yolo"
    # COCO body points: 5/6 shoulders, 7/8 elbows, 9/10 wrists (the person's own left/right)
    LINES = [(5, 6), (5, 7), (7, 9), (6, 8), (8, 10), (5, 11), (6, 12), (11, 12)]

    def __init__(self, model=None, imgsz=320):
        from ultralytics import YOLO
        os.chdir(Path.home())   # models live in the home folder (download once)
        if model is None:
            model = "yolo11n-pose.engine" if Path("yolo11n-pose.engine").exists() \
                else "yolo11n-pose.pt"
        self.model_name, self.imgsz = model, imgsz
        self.model = YOLO(model, task="pose")

    def track(self, frame):
        result = self.model(frame, imgsz=self.imgsz, conf=0.4, verbose=False)[0]
        if result.keypoints is None or len(result.keypoints) == 0:
            return None
        # The biggest person is the player
        boxes = result.boxes.xywh.tolist()
        best = max(range(len(boxes)), key=lambda i: boxes[i][2] * boxes[i][3])
        points = result.keypoints.xy[best].tolist()
        seen = result.keypoints.conf[best].tolist() if result.keypoints.conf is not None \
            else [1.0] * len(points)
        # In the mirrored picture the player's right hand is on the right, as in a mirror.
        # Play with the hand on the right side of the picture; raise the other to whack.
        left_wrist, right_wrist = points[9], points[10]
        hand, other, other_shoulder = (left_wrist, right_wrist, points[6]) \
            if left_wrist[0] > right_wrist[0] else (right_wrist, left_wrist, points[5])
        i_hand = points.index(hand)
        if seen[i_hand] < 0.3:
            return None
        height, width = frame.shape[:2]
        x, y = to_play_area(hand[0] / width, hand[1] / height)
        whack = seen[points.index(other)] > 0.3 and other[1] < other_shoulder[1]
        return Hand(x, y, whack, points, self.LINES)


def make_tracker(name="auto", **options):
    """mediapipe, yolo, or auto (MediaPipe if it's installed, otherwise YOLO)."""
    if name in ("auto", "mediapipe"):
        try:
            return MediaPipeHands()
        except ImportError:
            if name == "mediapipe":
                raise
    return YoloPose(**options)


def open_camera(device):
    """Open the camera: a number (0), or a device path (/dev/video0, opened with V4L2,
    Linux's own camera system: the quickest way on the Jetson)."""
    if str(device).isdigit():
        capture = cv2.VideoCapture(int(device))
    elif str(device).startswith("/dev/"):
        capture = cv2.VideoCapture(device, cv2.CAP_V4L2)
    else:
        capture = cv2.VideoCapture(device)
    capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    capture.set(cv2.CAP_PROP_FPS, 60)
    capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return capture


def timed(tracker, frame):
    started = time.perf_counter()
    hand = tracker.track(frame)
    return hand, (time.perf_counter() - started) * 1000
