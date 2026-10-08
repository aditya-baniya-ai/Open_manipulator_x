# OpenCR firmware

The OpenCR runs one of two things:

| Sketch | When | Where |
|---|---|---|
| `servo_check` | Testing the arm on its own from a Mac, no ROS | [servo_check/servo_check.ino](servo_check/servo_check.ino) |
| `usb_to_dxl` | Running the arm from ROS 2 on the Jetson | Arduino IDE example (below) |

Uploading one replaces the other, so put `usb_to_dxl` back before using ROS 2.

## Arduino IDE setup (Mac or PC)

1. Install Arduino IDE.
2. Settings > Additional boards manager URLs:
   `https://raw.githubusercontent.com/ROBOTIS-GIT/OpenCR/master/arduino/opencr_release/package_opencr_index.json`
3. Boards Manager: install **OpenCR**. Library Manager: install **Dynamixel2Arduino**.
4. Tools > Board > OpenCR > OpenCR Board, and Tools > Port > the `usbmodem` port.

Full illustrated guide: [docs/OpenMANIPULATOR-X_Quick_Setup.docx](../docs/OpenMANIPULATOR-X_Quick_Setup.docx).

## servo_check

Locks all joints, turns the base 90°, stands the arm straight up, and waves the wrist on a loop. Open the Serial Monitor at 115200 baud to start it. Switch board power off to stop.

## usb_to_dxl (for ROS 2)

File > Examples > OpenCR > 10.Etc > usb_to_dxl, then Upload. The OpenCR then just passes USB data through to the servos, and the Jetson does the control.

A good upload ends with `CRC OK`, `[OK] Download` and `jump_to_fw`. **The arm will not move after this upload.** That's expected: `usb_to_dxl` has no motions of its own, so the arm waits for ROS 2 commands from the Jetson.
