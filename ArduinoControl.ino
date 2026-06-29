#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

// ── BTS7960 Left ─────────────────────────────
#define L_RPWM  2
#define L_LPWM  3
#define L_R_EN  22
#define L_L_EN  23

// ── BTS7960 Right ────────────────────────────
#define R_RPWM  4
#define R_LPWM  5
#define R_R_EN  24
#define R_L_EN  25

const int DRIVE_SPEED = 50;
const int TURN_SPEED  = 80;

// ── PCA9685 ───────────────────────────────────
Adafruit_PWMServoDriver pca(0x40);
#define SERVOMIN   120
#define SERVOMAX   520
#define NUM_SERVOS 4

// ── Non-blocking servo state ──────────────────
int  currentAngle[NUM_SERVOS] = {95, 0, 0, 0};
int  targetAngle[NUM_SERVOS]  = {95, 0, 0, 0};
unsigned long lastServoStep   = 0;
const int SERVO_STEP_MS       = 8;   // ms between each 1° step

// ── Command buffer ────────────────────────────
String        cmdBuffer    = "";
unsigned long lastCharTime = 0;
const unsigned long FLUSH_MS = 150;  // flush if no \n after 150ms

// =============================================
//   SETUP
// =============================================
void setup() {
  pinMode(L_R_EN, OUTPUT); pinMode(L_L_EN, OUTPUT);
  pinMode(R_R_EN, OUTPUT); pinMode(R_L_EN, OUTPUT);
  pinMode(L_RPWM, OUTPUT); pinMode(L_LPWM, OUTPUT);
  pinMode(R_RPWM, OUTPUT); pinMode(R_LPWM, OUTPUT);

  digitalWrite(L_R_EN, HIGH); digitalWrite(L_L_EN, HIGH);
  digitalWrite(R_R_EN, HIGH); digitalWrite(R_L_EN, HIGH);
  stopMotors();

  Wire.begin();
  pca.begin();
  pca.setPWMFreq(50);
  delay(100);

  // Move all servos to starting position
  for (int i = 0; i < NUM_SERVOS; i++) {
    pca.setPWM(i, 0, angleToPulse(currentAngle[i]));
    delay(20);
  }

  Serial.begin(9600);
  Serial1.begin(9600);

  Serial.println("==============================");
  Serial.println("  ROVER + ARM READY");
  Serial.println("  Motor : F B L R S");
  Serial.println("  Arm   : S1-90S2-45");
  Serial.println("==============================");
}


void loop() {

  // ── 1A. Read USB bytes (Flask app via COM port) ─────────
  while (Serial.available()) {
    char c = (char)Serial.read();
    lastCharTime = millis();

    // Debug: print every raw byte
    Serial.print("[RX_USB] '");
    if      (c == '\n') Serial.print("\\n");
    else if (c == '\r') Serial.print("\\r");
    else                Serial.print(c);
    Serial.print("' ("); Serial.print((int)c); Serial.println(")");

    // Motor commands — fire instantly, no newline needed
    if (c == 'F') { cmdBuffer = ""; moveForward();  Serial.println(">> FORWARD");  continue; }
    if (c == 'B') { cmdBuffer = ""; moveBackward(); Serial.println(">> BACKWARD"); continue; }
    if (c == 'L') { cmdBuffer = ""; turnLeft();     Serial.println(">> LEFT");     continue; }
    if (c == 'R') { cmdBuffer = ""; turnRight();    Serial.println(">> RIGHT");    continue; }

    // Newline = end of arm/stop command
    if (c == '\n' || c == '\r') {
      processBuffer();
      continue;
    }

    // Accumulate arm command chars
    cmdBuffer += c;
  }

  // ── 1B. Read Bluetooth bytes (Local app) ───────────────
  while (Serial1.available()) {
    char c = (char)Serial1.read();
    lastCharTime = millis();

    // Debug: print every raw byte
    Serial.print("[RX] '");
    if      (c == '\n') Serial.print("\\n");
    else if (c == '\r') Serial.print("\\r");
    else                Serial.print(c);
    Serial.print("' ("); Serial.print((int)c); Serial.println(")");

    // Motor commands — fire instantly, no newline needed
    if (c == 'F') { cmdBuffer = ""; moveForward();  Serial.println(">> FORWARD");  continue; }
    if (c == 'B') { cmdBuffer = ""; moveBackward(); Serial.println(">> BACKWARD"); continue; }
    if (c == 'L') { cmdBuffer = ""; turnLeft();     Serial.println(">> LEFT");     continue; }
    if (c == 'R') { cmdBuffer = ""; turnRight();    Serial.println(">> RIGHT");    continue; }

    // Newline = end of arm/stop command
    if (c == '\n' || c == '\r') {
      processBuffer();
      continue;
    }

    // Accumulate arm command chars
    cmdBuffer += c;
  }

  // ── 2. Timeout flush (no \n from app) ────
  if (cmdBuffer.length() > 0 && (millis() - lastCharTime > FLUSH_MS)) {
    Serial.println("[TIMEOUT FLUSH]");
    processBuffer();
  }

  // ── 3. Non-blocking servo stepping ───────
  // Each loop() call advances servos by 1° if needed
  // Motors keep running because we never block here
  if (millis() - lastServoStep >= SERVO_STEP_MS) {
    lastServoStep = millis();
    for (int i = 0; i < NUM_SERVOS; i++) {
      if (currentAngle[i] < targetAngle[i]) {
        currentAngle[i]++;
        pca.setPWM(i, 0, angleToPulse(currentAngle[i]));
      } else if (currentAngle[i] > targetAngle[i]) {
        currentAngle[i]--;
        pca.setPWM(i, 0, angleToPulse(currentAngle[i]));
      }
    }
  }
}

// =============================================
//   PROCESS BUFFER — decide what command is
// =============================================
void processBuffer() {
  cmdBuffer.trim();

  if (cmdBuffer.length() == 0) {
    cmdBuffer = "";
    return;
  }

  Serial.print("[PROCESS] \""); Serial.print(cmdBuffer); Serial.println("\"");

  // Bare "S" = stop motors
  if (cmdBuffer == "S") {
    stopMotors();
    Serial.println(">> STOP");
    cmdBuffer = "";
    return;
  }

  // Arm command: contains 'S' and '-'
  if (cmdBuffer.indexOf('S') != -1 && cmdBuffer.indexOf('-') != -1) {
    Serial.println("[ARM] Parsing...");
    parseArmCommand(cmdBuffer);
    cmdBuffer = "";
    return;
  }

  Serial.print("[UNKNOWN] \""); Serial.print(cmdBuffer); Serial.println("\"");
  cmdBuffer = "";
}

// =============================================
//   ARM PARSER
//   Parses "S1-90S2-45S3-120" and sets targets
// =============================================
uint16_t angleToPulse(int angle) {
  angle = constrain(angle, 0, 180);
  return map(angle, 0, 180, SERVOMIN, SERVOMAX);
}

void parseArmCommand(const String& data) {
  int len    = data.length();
  int i      = 0;
  int parsed = 0;

  while (i < len) {
    if (data[i] != 'S') { i++; continue; }

    // Parse servo number (supports 1 or 2 digits)
    int numStart = i + 1;
    int numEnd   = numStart;
    while (numEnd < len && isDigit(data[numEnd])) numEnd++;
    if (numEnd == numStart) { i++; continue; }

    int servoNum = data.substring(numStart, numEnd).toInt();

    // Must have '-' after servo number
    if (numEnd >= len || data[numEnd] != '-') { i = numEnd; continue; }

    // Parse angle digits
    int angStart = numEnd + 1;
    int angEnd   = angStart;
    while (angEnd < len && isDigit(data[angEnd])) angEnd++;
    if (angEnd == angStart) { i = angStart; continue; }

    int angle = data.substring(angStart, angEnd).toInt();
    angle = constrain(angle, 0, 180);

    if (servoNum >= 1 && servoNum <= NUM_SERVOS) {
      int ch = servoNum - 1;
      if (servoNum == 4) angle = constrain(angle, 0, 45); // gripper limit
      targetAngle[ch] = angle; // set target — movement in loop()
      Serial.print("  Servo "); Serial.print(servoNum);
      Serial.print(" target -> ");   Serial.println(angle);
      parsed++;
    } else {
      Serial.print("  [SKIP] Invalid servo number: "); Serial.println(servoNum);
    }

    i = angEnd;
  }

  if (parsed == 0) {
    Serial.println("  [WARN] Nothing parsed! Check format:");
    Serial.println("  Expected: S1-90  or  S1-90S2-45");
  } else {
    Serial.print("  [OK] Set "); Serial.print(parsed); Serial.println(" servo target(s)");
  }
}

// =============================================
//   MOTOR FUNCTIONS
// =============================================
void moveForward() {
  analogWrite(L_RPWM, DRIVE_SPEED); analogWrite(L_LPWM, 0);
  analogWrite(R_RPWM, DRIVE_SPEED); analogWrite(R_LPWM, 0);
}
void moveBackward() {
  analogWrite(L_RPWM, 0); analogWrite(L_LPWM, DRIVE_SPEED);
  analogWrite(R_RPWM, 0); analogWrite(R_LPWM, DRIVE_SPEED);
}
void turnLeft() {
  analogWrite(L_RPWM, 0);          analogWrite(L_LPWM, TURN_SPEED);
  analogWrite(R_RPWM, TURN_SPEED); analogWrite(R_LPWM, 0);
}
void turnRight() {
  analogWrite(L_RPWM, TURN_SPEED); analogWrite(L_LPWM, 0);
  analogWrite(R_RPWM, 0);          analogWrite(R_LPWM, TURN_SPEED);
}
void stopMotors() {
  analogWrite(L_RPWM, 0); analogWrite(L_LPWM, 0);
  analogWrite(R_RPWM, 0); analogWrite(R_LPWM, 0);
}
