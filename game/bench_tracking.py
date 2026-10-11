"""
Which hand tracker is faster on this computer? Runs MediaPipe and YOLO pose on the
same camera pictures (or a photo) and prints the time per picture.

    python3 bench_tracking.py                  live camera (/dev/video0), hold up a hand
    python3 bench_tracking.py --image hand.jpg a photo instead of the camera
    python3 bench_tracking.py --yolo yolo11n-pose.engine   test the TensorRT model

Only the camera is used: the arm doesn't move. Stop the camera program first if it's
running (only one program can use the camera at a time).
"""

import argparse
import statistics
import sys
import time

import cv2

from tracker import MediaPipeHands, YoloPose, timed


def frames_from(args):
    if args.image:
        frame = cv2.imread(args.image)
        if frame is None:
            sys.exit(f"Can't read {args.image}")
        frame = cv2.flip(frame, 1)
        while True:
            yield frame
    camera = cv2.VideoCapture(args.camera)
    camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    if not camera.isOpened():
        sys.exit(f"Can't open camera {args.camera}. Is another program using it?")
    while True:
        ok, frame = camera.read()
        if ok:
            yield cv2.flip(frame, 1)


def bench(tracker, frames, count):
    times, found, whacks = [], 0, 0
    for _ in range(5):            # warm up (first runs are slow)
        tracker.track(next(frames))
    for _ in range(count):
        hand, ms = timed(tracker, next(frames))
        times.append(ms)
        found += hand is not None
        whacks += bool(hand and hand.whack)
    times.sort()
    return {
        "mean": statistics.mean(times),
        "p95": times[int(len(times) * 0.95) - 1],
        "found": found / count,
        "whack": whacks / count,
    }


def main():
    parser = argparse.ArgumentParser(description="Compare hand tracker speed.")
    parser.add_argument("--image", help="use this photo instead of the camera")
    parser.add_argument("--camera", default="/dev/video0", help="camera device")
    parser.add_argument("--count", type=int, default=100, help="pictures per tracker")
    parser.add_argument("--yolo", help="YOLO pose model (default: the .engine if it exists)")
    parser.add_argument("--imgsz", type=int, default=320, help="YOLO picture size")
    args = parser.parse_args()
    frames = frames_from(args)

    results = {}
    for name, make in (("mediapipe", MediaPipeHands),
                       ("yolo", lambda: YoloPose(args.yolo, args.imgsz))):
        try:
            tracker = make()
        except Exception as error:  # not installed, model missing, ...
            print(f"{name}: can't start ({type(error).__name__}: {error})")
            continue
        label = name if name == "mediapipe" else f"yolo ({tracker.model_name}, {args.imgsz})"
        print(f"Testing {label} ...")
        results[label] = bench(tracker, frames, args.count)
        time.sleep(0.5)

    print("\ntracker                          ms/picture   95% under   pictures/s   hand found   whack")
    for label, r in results.items():
        print(f"{label:32} {r['mean']:8.1f}   {r['p95']:8.1f}   {1000 / r['mean']:9.0f}"
              f"   {r['found']:10.0%}   {r['whack']:5.0%}")
    if results:
        fastest = min(results, key=lambda k: results[k]["mean"])
        print(f"\nFastest here: {fastest}")


if __name__ == "__main__":
    main()
