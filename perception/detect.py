"""
Live object detection from the camera (ROS 2 + YOLO on the Jetson GPU).

Start the camera first (see README.md), then:
    python3 detect.py                      # regular YOLO: 80 everyday objects
    python3 detect.py --find pencil cup    # YOLO-World: only the words you give it

It checks every camera frame. To save power, --fps 5 checks only 5 frames a second
(still plenty to notice someone walking in).

While Robo is talking with someone (the control panel publishes /robo_busy), detection
pauses by default, so Whisper and the LLM get the whole GPU and answer much faster.
--busy-fps 20 keeps checking 20 frames a second during conversations instead.
The video window keeps showing live video either way; only the boxes update less often.

Faster options (see README, "Faster detection"):
    --model yolo11n.engine   the TensorRT version of the model (about 3x faster on the
                             Jetson; make it once with: yolo export model=yolo11n.pt
                             format=engine half=True)
    --imgsz 320              look at a smaller picture: faster, but misses small or
                             far-away people more often (default 640)

Every 5 seconds it logs how long YOLO takes per frame, to compare settings.

It also sends a small copy of the video (with the boxes) to Robo's control panel on
/detections/image/compressed (JPEG, about 15 frames a second).

It shows a window with boxes around what it finds (press q in the window to quit),
and publishes:
    /person_detected   std_msgs/Bool     true while a person is in view
    /detections        std_msgs/String   what it sees, e.g. "person, cup"
"""

import argparse
import os
import time
from pathlib import Path

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage, Image
from std_msgs.msg import Bool, String
from ultralytics import YOLO

YOLO_MODEL = "yolo11n.pt"            # small and fast, knows 80 objects
PREVIEW_WIDTH = 480                  # size of the video sent to the control panel
PREVIEW_FPS = 15                     # how often it's sent
WORLD_MODEL = "yolov8s-worldv2.pt"   # finds any object you name


class Detector(Node):
    def __init__(self):
        super().__init__("detector")
        self.frame = None
        self.create_subscription(Image, "/image_raw", self.on_image, qos_profile_sensor_data)
        self.person_pub = self.create_publisher(Bool, "/person_detected", 10)
        self.detections_pub = self.create_publisher(String, "/detections", 10)
        self.preview_pub = self.create_publisher(CompressedImage,
                                                 "/detections/image/compressed", 1)
        # The control panel says when Robo is busy talking; then we pause to free the GPU
        self.busy_until = 0.0
        self.create_subscription(Bool, "/robo_busy", self.on_busy, 10)

    def on_busy(self, msg):
        # The panel repeats this every second while busy; if it stops (e.g. it closed),
        # detection resumes on its own after a few seconds
        self.busy_until = time.monotonic() + 3.0 if msg.data else 0.0

    def busy(self):
        return time.monotonic() < self.busy_until

    def on_image(self, msg):
        # Keep only the newest frame, so detection never falls behind the camera
        self.frame = msg


def to_bgr(msg):
    """Turn a ROS image message into an OpenCV (BGR) picture."""
    img = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, -1)
    if msg.encoding == "rgb8":
        return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    if msg.encoding == "bgr8":
        return img
    raise ValueError(f"Unsupported image encoding: {msg.encoding}")


def load_model(find, name):
    # Models are kept in the home folder, so they download only once
    os.chdir(Path.home())
    if find:
        model = YOLO(WORLD_MODEL)
        model.set_classes(find)
        return model
    return YOLO(name)


def label(image, text, row):
    """Write a line of text on the video, with a dark outline so it's readable."""
    position = (10, 25 + 25 * row)
    cv2.putText(image, text, position, cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 3)
    cv2.putText(image, text, position, cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)


def main():
    parser = argparse.ArgumentParser(description="Live object detection from the camera.")
    parser.add_argument("--find", nargs="+", metavar="WORD",
                        help="use YOLO-World and look only for these objects")
    parser.add_argument("--conf", type=float, default=0.4,
                        help="how sure YOLO must be to report something (0-1, default 0.4)")
    parser.add_argument("--fps", type=float, default=0,
                        help="camera frames to check per second, to save power "
                             "(default 0: every frame)")
    parser.add_argument("--busy-fps", type=float, default=0,
                        help="frames to check per second while Robo is talking "
                             "(default 0: pause)")
    parser.add_argument("--model", default=YOLO_MODEL,
                        help="YOLO model file, e.g. yolo11n.engine (default yolo11n.pt)")
    parser.add_argument("--imgsz", type=int, default=640,
                        help="picture size YOLO looks at (default 640; 320 is faster)")
    parser.add_argument("--no-window", action="store_true",
                        help="don't open the video window (e.g. over SSH)")
    args, ros_args = parser.parse_known_args()

    print(f"Loading model {args.model} ...")
    model = load_model(args.find, args.model)

    rclpy.init(args=ros_args)
    node = Detector()
    log = node.get_logger()
    log.info("Waiting for camera images on /image_raw ...")

    last_seen = None
    last_check = 0.0
    busy = False
    last_result = None              # the latest detection, drawn on frames in between
    last_preview = 0.0
    times, stats_since = [], time.monotonic()
    try:
        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.01)
            if node.frame is None:
                continue
            frame, node.frame = to_bgr(node.frame), None
            now = time.monotonic()

            if node.busy() != busy:
                busy = node.busy()
                if busy:
                    log.info("Robo is talking: detection " + (
                        f"slowed to {args.busy_fps:g} checks a second" if args.busy_fps
                        else "paused") + ", so the LLM gets more of the GPU")
                else:
                    log.info("Detection back to normal")

            # Check this frame? (every frame by default; fewer while Robo is talking)
            rate = args.busy_fps if busy else args.fps
            check = not (busy and args.busy_fps == 0) and \
                (rate == 0 or now - last_check >= 1.0 / rate)

            if check:
                # Keep the average rate (e.g. 20 of the camera's 30 frames a second)
                last_check = max(last_check + 1.0 / rate, now - 1.0 / rate) if rate else now
                started = time.perf_counter()
                result = model(frame, conf=args.conf, imgsz=args.imgsz, quantize=16,
                               verbose=False)[0]
                times.append(time.perf_counter() - started)
                last_result = result
                names = [result.names[int(c)] for c in result.boxes.cls]

                node.person_pub.publish(Bool(data="person" in names))
                seen = ", ".join(sorted(set(names)))
                node.detections_pub.publish(String(data=seen))
                if seen != last_seen:
                    log.info(f"Seeing: {seen or 'nothing'}")
                    last_seen = seen

            # Every 5 seconds: how long YOLO takes, to compare settings
            if now - stats_since >= 5.0:
                if times:
                    log.info(f"YOLO ({args.model}, imgsz {args.imgsz}): "
                             f"{1000 * sum(times) / len(times):.1f} ms per frame, "
                             f"{len(times) / (now - stats_since):.1f} frames checked per second")
                times, stats_since = [], now

            # Always show the live video, with the latest boxes drawn on it
            shown = last_result.plot(img=frame) if last_result is not None else frame
            if busy:
                label(shown, "Robo is talking: detection " + (
                    f"at {args.busy_fps:g}/s" if args.busy_fps else "paused"), 0)

            # A small JPEG copy for the control panel
            if now - last_preview >= 1.0 / PREVIEW_FPS:
                last_preview = now
                height, width = shown.shape[:2]
                small = cv2.resize(shown, (PREVIEW_WIDTH, height * PREVIEW_WIDTH // width))
                ok, jpeg = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if ok:
                    preview = CompressedImage()
                    preview.format = "jpeg"
                    preview.data = jpeg.tobytes()
                    node.preview_pub.publish(preview)

            if not args.no_window:
                cv2.imshow("detections (press q to quit)", shown)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    except KeyboardInterrupt:
        pass

    cv2.destroyAllWindows()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
