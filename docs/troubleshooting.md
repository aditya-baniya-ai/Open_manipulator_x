# Troubleshooting

Problems hit while building this robot, and the fixes.

## Permission denied on /dev/ttyACM0

**Symptom:** the ROS 2 hardware launch can't open the OpenCR port.

**Cause:** your user isn't in the `dialout` group, which owns serial ports.

**Fix:**

```bash
sudo usermod -aG dialout $USER
```

Then log out and back in (or reboot). Check with `groups`; it should list `dialout`. Opening a new terminal isn't enough, because group changes only apply after a fresh login.

If the command says the group already exists, you probably ran `groupadd` or mistyped it. Run the exact `usermod` line above.

## Every servo shows MISSING ID (Arduino servo check)

- 12 V power is off or the switch is off.
- The servo cable isn't fully seated, or it's in a 4-pin port instead of a 3-pin one.
- Baud rate mismatch: `dxl.begin(1000000)` must match the servos (1 Mbps).

## Arduino upload to OpenCR fails or freezes

Put the board in recovery mode: hold **PUSH SW2**, press **RESET**, release SW2, then upload again. This also fixed the freeze while trying the ROBOTIS teaching example.

Upload from the Mac. The Arduino IDE can't upload to the OpenCR from the Jetson.

## A servo ignores a target near 0° or 360°

**Symptom:** in the base swing test, the base started at 348°, so `start + 90` went past 360 and the servo rejected it.

**Fix:** keep targets inside 0–360, for example go the other way if the target would pass 360:

```cpp
float target = (now + 90 <= 360) ? now + 90 : now - 90;
```

`servo_check.ino` already does this. In ROS 2 this matters less, because joints use radians with 0 at the servo's 180°.
