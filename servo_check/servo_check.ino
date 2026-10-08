#include <Dynamixel2Arduino.h>

Dynamixel2Arduino dxl(Serial3, 84);
using namespace ControlTableItem;

const uint8_t ARM_IDS[] = {11, 12, 13, 14};   // joints to lock
const uint8_t STAND_IDS[] = {12, 13, 14};     // joints to straighten
const uint8_t WRIST = 14;
const float STRAIGHT = 180.0;   // straight position for each joint
const float SWING = 35.0;       // degrees the wrist tilts each way
const int WAVES = 3;            // waves per greeting

// Wait until a joint is within 3 degrees of its target (gives up after 8 seconds)
void waitFor(uint8_t id, float target) {
  unsigned long start = millis();
  while (fabs(dxl.getPresentPosition(id, UNIT_DEGREE) - target) > 3.0 &&
         millis() - start < 8000) {
    delay(20);
  }
}

void setup() {
#ifdef BDPIN_DXL_PWR_EN
  pinMode(BDPIN_DXL_PWR_EN, OUTPUT);
  digitalWrite(BDPIN_DXL_PWR_EN, HIGH);
#endif
  Serial.begin(115200);
  while (!Serial);   // nothing moves until you open the Serial Monitor

  dxl.begin(1000000);
  dxl.setPortProtocolVersion(2.0);

  for (uint8_t id : ARM_IDS) {
    if (!dxl.ping(id)) {
      Serial.print("MISSING ID "); Serial.println(id);
      while (true);
    }
    dxl.torqueOff(id);
    dxl.setOperatingMode(id, OP_POSITION);
    dxl.writeControlTableItem(PROFILE_VELOCITY, id, 20);
    dxl.writeControlTableItem(PROFILE_ACCELERATION, id, 10);
    float now = dxl.getPresentPosition(id, UNIT_DEGREE);
    dxl.setGoalPosition(id, now, UNIT_DEGREE);
    dxl.torqueOn(id);
  }

  // Stand straight up (slow and steady)
    // Turn the base 90 degrees so the wrist waves sideways to you
  const uint8_t BASE = 11;
  float baseNow = dxl.getPresentPosition(BASE, UNIT_DEGREE);
  float baseTarget = (baseNow + 90 <= 360) ? baseNow + 90 : baseNow - 90;
  Serial.println("Turning to face sideways...");
  dxl.setGoalPosition(BASE, baseTarget, UNIT_DEGREE);
  waitFor(BASE, baseTarget);
  Serial.println("Standing straight up...");
  for (uint8_t id : STAND_IDS) {
    dxl.setGoalPosition(id, STRAIGHT, UNIT_DEGREE);
  }
  for (uint8_t id : STAND_IDS) {
    waitFor(id, STRAIGHT);
    Serial.print("ID "); Serial.print(id);
    Serial.print(" at "); Serial.println(dxl.getPresentPosition(id, UNIT_DEGREE), 1);
  }

  // Make only the wrist quicker, like a hand
  dxl.writeControlTableItem(PROFILE_VELOCITY, WRIST, 70);
  dxl.writeControlTableItem(PROFILE_ACCELERATION, WRIST, 20);

  delay(1000);
  Serial.println("Ready. Switch the board power OFF to stop.");
}

// Greeting: arm stays straight up, wrist waves a few times, then rests
void greet() {
  Serial.println("Hello!");
  for (int i = 0; i < WAVES; i++) {
    dxl.setGoalPosition(WRIST, STRAIGHT - SWING, UNIT_DEGREE);
    waitFor(WRIST, STRAIGHT - SWING);
    delay(100);

    dxl.setGoalPosition(WRIST, STRAIGHT + SWING, UNIT_DEGREE);
    waitFor(WRIST, STRAIGHT + SWING);
    delay(100);
  }

  // Back to center
  dxl.setGoalPosition(WRIST, STRAIGHT, UNIT_DEGREE);
  waitFor(WRIST, STRAIGHT);
}

void loop() {
  greet();
  delay(2000);   // rest between greetings
}