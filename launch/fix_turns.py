"""
Fix a joint that reads a whole turn off, like the base saying 353° when it faces forward
(it's really -7°). Runs before the arm starts (hand.sh does it), so the "outside its safe
range" check sees the real angle.

For each arm servo (IDs 11-14, not the gripper) it reads the angle. Only when it is more
than half a turn from 0 does it change the servo's Homing Offset by whole turns (4096
steps = 360°), so 353° becomes -7°. Whole turns never change where the joint really
points, only the number it reports. The servo keeps the new offset (it is stored in
the servo), and the old one is written to ~/robo_servo_backup.txt first.

    python3 fix_turns.py                  check and fix (port /dev/ttyACM0)
    python3 fix_turns.py --check          only show the angles, change nothing
    python3 fix_turns.py --port /dev/ttyACM1

It talks to the servos itself (DYNAMIXEL protocol 2.0 through the OpenCR), so the arm
program must not be running yet. If anything goes wrong it just says so and changes
nothing; the arm then starts as before.
"""

import argparse
import struct
import sys
import time
from pathlib import Path

ARM_IDS = [11, 12, 13, 14]       # base, shoulder, elbow, wrist (15, the gripper, is left alone)
NAMES = {11: "Base", 12: "Shoulder", 13: "Elbow", 14: "Wrist"}
TURN = 4096                      # steps in one full turn
ZERO = 2048                      # the step that means 0°
HOMING_OFFSET, TORQUE_ENABLE, PRESENT_POSITION = 20, 64, 132   # XM430 control table
OFFSET_LIMIT = 1044479
BACKUP = Path.home() / "robo_servo_backup.txt"


def crc16(data):
    crc = 0
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x8005) if crc & 0x8000 else crc << 1
            crc &= 0xFFFF
    return crc


class Bus:
    """Just enough of DYNAMIXEL protocol 2.0: read and write a few bytes."""

    def __init__(self, port):
        import serial    # pyserial
        self.port = serial.Serial(port, 1000000, timeout=0.1)
        self.port.reset_input_buffer()

    def close(self):
        self.port.close()

    def send(self, servo, instruction, params):
        body = bytes([instruction]) + bytes(params)
        body = body.replace(b"\xff\xff\xfd", b"\xff\xff\xfd\xfd")      # byte stuffing
        packet = b"\xff\xff\xfd\x00" + bytes([servo]) + struct.pack("<H", len(body) + 2) + body
        packet += struct.pack("<H", crc16(packet))
        self.port.reset_input_buffer()
        self.port.write(packet)
        return self.reply(servo)

    def reply(self, servo):
        data, end = b"", time.time() + 0.3
        while time.time() < end:
            data += self.port.read(64)
            start = data.find(b"\xff\xff\xfd\x00")
            if start >= 0 and len(data) >= start + 7:
                length = struct.unpack("<H", data[start + 5:start + 7])[0]
                packet = data[start:start + 7 + length]
                if len(packet) == 7 + length:
                    if crc16(packet[:-2]) != struct.unpack("<H", packet[-2:])[0]:
                        raise IOError("bad reply (checksum)")
                    if packet[4] != servo:
                        raise IOError(f"reply from servo {packet[4]}, not {servo}")
                    if packet[8] & 0x7F:
                        raise IOError(f"servo {servo} error {packet[8]}")
                    return packet[9:-2].replace(b"\xff\xff\xfd\xfd", b"\xff\xff\xfd")
        raise IOError(f"no answer from servo {servo}")

    def read32(self, servo, address):
        data = self.send(servo, 0x02, struct.pack("<HH", address, 4))
        return struct.unpack("<i", data[:4])[0]

    def write(self, servo, address, value, size):
        fmt = {1: "<B", 4: "<i"}[size]
        self.send(servo, 0x03, struct.pack("<H", address) + struct.pack(fmt, value))


def turns_off(position):
    """How many whole turns the reading is away from the -180°..+180° window."""
    return round((position - ZERO) / TURN)


def degrees(position):
    return (position - ZERO) * 360 / TURN


def main():
    parser = argparse.ArgumentParser(description="Fix a joint that reads a whole turn off.")
    parser.add_argument("--port", default="/dev/ttyACM0")
    parser.add_argument("--check", action="store_true", help="only show, change nothing")
    args = parser.parse_args()

    try:
        bus = Bus(args.port)
    except ImportError:
        print("(Can't check the joints' turns: pyserial is missing. sudo apt install python3-serial)")
        return 0
    except Exception as error:
        print(f"(Can't check the joints' turns: {error})")
        return 0
    try:
        for servo in ARM_IDS:
            position = bus.read32(servo, PRESENT_POSITION)
            turns = turns_off(position)
            if not turns:
                if args.check:
                    print(f"{NAMES[servo]}: {degrees(position):+.0f}°  (fine)")
                continue
            offset = bus.read32(servo, HOMING_OFFSET)
            new_offset = offset - turns * TURN
            fixed = position - turns * TURN
            print(f"{NAMES[servo]} reads {degrees(position):+.0f}°, which is really "
                  f"{degrees(fixed):+.0f}° ({abs(turns)} whole turn{'s' * (abs(turns) > 1)} off).")
            if args.check:
                continue
            if abs(new_offset) > OFFSET_LIMIT:
                print("  The offset would be too big, so it's left alone.")
                continue
            with BACKUP.open("a") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  servo {servo} ({NAMES[servo]}) "
                        f"Homing Offset was {offset}, set to {new_offset}\n")
            bus.write(servo, TORQUE_ENABLE, 0, 1)       # the offset can only change with torque off
            bus.write(servo, HOMING_OFFSET, new_offset, 4)
            time.sleep(0.05)
            now = bus.read32(servo, PRESENT_POSITION)
            print(f"  Fixed: it now reads {degrees(now):+.0f}°.  (old offset saved in {BACKUP})")
    except Exception as error:
        print(f"(Couldn't finish checking the joints' turns: {error})")
    finally:
        bus.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
