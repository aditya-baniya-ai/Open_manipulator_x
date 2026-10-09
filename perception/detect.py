"""
Live object detection from the camera (ROS 2 + YOLO on the Jetson GPU).

Start the camera first (see README.md), then:
    python3 detect.py                      # regular YOLO: 80 everyday objects
    python3 detect.py --find pencil cup    # YOLO-World: only the words you give it

It checks every camera frame. To save power, --fps 5 checks only 5 frames a second
(still plenty to notice someone walking in).

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
from sensor_msgs.msg import Image
from std_msgs.msg import Bool, String
from ultralytics import YOLO

YOLO_MODEL = "yolo11n.pt"            # small and fast, knows 80 objects
WORLD_MODEL = "yolov8s-worldv2.pt"   # finds any object you name


class Detector(Node):
    def __init__(self):
        super().__init__("detector")
        self.frame = None
        self.create_subscription(Image, "/image_raw", self.on_image, qos_profile_sensor_data)
        self.person_pub = self.create_publisher(Bool, "/person_detected", 10)
        self.detections_pub = self.create_publisher(String, "/detections", 10)

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


def load_model(find):
    # Models are kept in the home folder, so they download only once
    os.chdir(Path.home())
    if find:
        model = YOLO(WORLD_MODEL)
        model.set_classes(find)
        return model
    return YOLO(YOLO_MODEL)


def main():
    parser = argparse.ArgumentParser(description="Live object detection from the camera.")
    parser.add_argument("--find", nargs="+", metavar="WORD",
                        help="use YOLO-World and look only for these objects")
    parser.add_argument("--conf", type=float, default=0.4,
                        help="how sure YOLO must be to report something (0-1, default 0.4)")
    parser.add_argument("--fps", type=float, default=0,
                        help="camera frames to check per second, to save power "
                             "(default 0: every frame)")
    parser.add_argument("--no-window", action="store_true",
                        help="don't open the video window (e.g. over SSH)")
    args, ros_args = parser.parse_known_args()

    print("Loading model ...")
    model = load_model(args.find)

    rclpy.init(args=ros_args)
    node = Detector()
    log = node.get_logger()
    log.info("Waiting for camera images on /image_raw ...")

    last_seen = None
    last_check = 0.0
    try:
        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.01)
            if node.frame is None:
                continue
            if args.fps and time.monotonic() - last_check < 1.0 / args.fps:
                continue  # skip frames between checks, to save power
            last_check = time.monotonic()
            frame, node.frame = to_bgr(node.frame), None

            result = model(frame, conf=args.conf, verbose=False)[0]
            names = [result.names[int(c)] for c in result.boxes.cls]

            node.person_pub.publish(Bool(data="person" in names))
            seen = ", ".join(sorted(set(names)))
            node.detections_pub.publish(String(data=seen))
            if seen != last_seen:
                log.info(f"Seeing: {seen or 'nothing'}")
                last_seen = seen

            if not args.no_window:
                cv2.imshow("detections (press q to quit)", result.plot())
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    except KeyboardInterrupt:
        pass

    cv2.destroyAllWindows()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
