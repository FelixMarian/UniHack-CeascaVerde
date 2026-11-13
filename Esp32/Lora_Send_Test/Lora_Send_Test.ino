
#include <SPI.h>
#include <LoRa.h>

// LoRa Ra-02 pin configuration
#define LORA_SCK   18
#define LORA_MISO  19
#define LORA_MOSI  23
#define LORA_SS     5
#define LORA_RST   14
#define LORA_DIO0  26

// SX1278 Ra-02 frequency
#define LORA_FREQ 433E6

// Automatically send every 5 seconds
const unsigned long SEND_INTERVAL = 5000;
unsigned long lastSend = 0;

void sendCommand(const String &command) {
  Serial.print("Sending LoRa command: ");
  Serial.println(command);

  if (LoRa.beginPacket() == 0) {
    Serial.println("ERROR: Could not start packet");
    return;
  }

  LoRa.print(command);

  if (LoRa.endPacket() == 1) {
    Serial.println("LoRa transmission completed!");
  } else {
    Serial.println("LoRa transmission failed!");
  }

  Serial.println("----------------------");
}

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(100);

  delay(1000);

  Serial.println("ESP32 LoRa Transmitter");
  Serial.println("Initializing LoRa...");

  // Initialize SPI with your exact pins
  SPI.begin(
    LORA_SCK,
    LORA_MISO,
    LORA_MOSI,
    LORA_SS
  );

  // Configure LoRa control pins
  LoRa.setPins(
    LORA_SS,
    LORA_RST,
    LORA_DIO0
  );

  // Initialize module
  if (!LoRa.begin(LORA_FREQ)) {
    Serial.println("ERROR: LoRa initialization failed!");

    while (true) {
      delay(1000);
    }
  }

  // LoRa settings
  LoRa.setSpreadingFactor(7);
  LoRa.setSignalBandwidth(125E3);
  LoRa.setCodingRate4(5);
  LoRa.setTxPower(14);

  Serial.println("LoRa initialized successfully!");
  Serial.println("Frequency: 433 MHz");
  Serial.println("Ready to send commands.");

  sendCommand("PING");
  lastSend = millis();
}

void loop() {

  // Automatic PING every 5 seconds
  if (millis() - lastSend >= SEND_INTERVAL) {
    lastSend = millis();

    sendCommand("PING");
  }

  // Send custom commands from Serial Monitor
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();

    if (command.length() > 0) {
      sendCommand(command);
    }
  }
}
