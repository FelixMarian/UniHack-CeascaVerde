#include <SPI.h>
#include <MFRC522.h>
#include <Servo.h>

constexpr byte RFID_SS_PIN = 10;
constexpr byte RFID_RST_PIN = 9;
constexpr byte SERVO_PIN = 6;

constexpr int CLOSED_ANGLE = 0;
constexpr int OPEN_ANGLE = 90;

MFRC522 rfid(RFID_SS_PIN, RFID_RST_PIN);
Servo lidServo;
bool lidOpen = false;

void setup() {
  Serial.begin(9600);
  SPI.begin();
  rfid.PCD_Init();

  lidServo.attach(SERVO_PIN);
  lidServo.write(CLOSED_ANGLE);
}

void loop() {
  if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) {
    return;
  }

  // Cartela rămâne în starea HALT cât timp stă lângă cititor.
  rfid.PICC_HaltA();

  lidOpen = !lidOpen;
  lidServo.write(lidOpen ? OPEN_ANGLE : CLOSED_ANGLE);

  Serial.print(F("UID:"));
  for (byte i = 0; i < rfid.uid.size; i++) {
    Serial.print(' ');
    if (rfid.uid.uidByte[i] < 0x10) {
      Serial.print('0');
    }
    Serial.print(rfid.uid.uidByte[i], HEX);
  }
  Serial.println(lidOpen ? F(" -> 90 grade") : F(" -> 0 grade"));
}