
#include <Arduino.h>
#include <SPI.h>
#include <LoRa.h>

// ======================================
// SMARTWASTE - ESP32 LORA TRANSMITTER
// 3x HC-SR04 + SX1278 Ra-02
// ======================================

// 1 = Dummy data
// 0 = Real sensors
#define TEST 1

// ---------- BIN CONFIGURATION ----------

#define BIN_ID "BIN_001"

#define BIN_LATITUDE  45.748
#define BIN_LONGITUDE 21.208

// ---------- ULTRASONIC PINS ----------

#define US_MID_TRIG   25
#define US_MID_ECHO   33

#define US_FULL_TRIG  27
#define US_FULL_ECHO  32

#define US_TOP_TRIG   21
#define US_TOP_ECHO   22

// ---------- LORA PINS ----------

#define LORA_SCK   18
#define LORA_MISO  19
#define LORA_MOSI  23
#define LORA_SS     5
#define LORA_RST   14
#define LORA_DIO0  26

// ---------- LORA CONFIGURATION ----------

#define LORA_FREQ       433.92E6
#define LORA_SYNC_WORD  0x12

// ---------- TIMING ----------

const unsigned long SEND_INTERVAL_MS = 5000;
const unsigned long ECHO_TIMEOUT_US = 30000;

const float MIN_DISTANCE_CM = 2.0f;
const float MAX_DISTANCE_CM = 400.0f;

const unsigned long SENSOR_DELAY_MS = 60;

unsigned long lastSend = 0;

// ---------- TEST DATA ----------

#if TEST

const float dummyData[][3] = {
    {60.0f, 55.0f, 50.0f},
    {45.0f, 40.0f, 35.0f},
    {30.0f, 25.0f, 20.0f},
    {15.0f, 12.0f, 10.0f},
    { 6.0f,  5.0f,  4.0f}
};

const int DUMMY_COUNT =
    sizeof(dummyData) / sizeof(dummyData[0]);

int dummyIndex = 0;

#endif

// ======================================
// ULTRASONIC INITIALIZATION
// ======================================

void initUltrasonic(int trigPin, int echoPin)
{
    pinMode(trigPin, OUTPUT);
    pinMode(echoPin, INPUT);

    digitalWrite(trigPin, LOW);
}

// ======================================
// READ DISTANCE (CENTIMETERS)
// ======================================

bool readDistanceCm(
    int trigPin,
    int echoPin,
    float &distanceCm
)
{
    digitalWrite(trigPin, LOW);
    delayMicroseconds(2);

    digitalWrite(trigPin, HIGH);
    delayMicroseconds(10);
    digitalWrite(trigPin, LOW);

    unsigned long duration = pulseIn(
        echoPin,
        HIGH,
        ECHO_TIMEOUT_US
    );

    if (duration == 0) {
        return false;
    }

    float measuredDistance =
        (duration * 0.0343f) / 2.0f;

    if (measuredDistance < MIN_DISTANCE_CM ||
        measuredDistance > MAX_DISTANCE_CM) {
        return false;
    }

    distanceCm = measuredDistance;

    return true;
}

// ======================================
// READ ALL THREE SENSORS
// ======================================

bool readAllSensors(
    float &distanceMid,
    float &distanceFull,
    float &distanceTop
)
{
    bool midValid = readDistanceCm(
        US_MID_TRIG,
        US_MID_ECHO,
        distanceMid
    );

    delay(SENSOR_DELAY_MS);

    bool fullValid = readDistanceCm(
        US_FULL_TRIG,
        US_FULL_ECHO,
        distanceFull
    );

    delay(SENSOR_DELAY_MS);

    bool topValid = readDistanceCm(
        US_TOP_TRIG,
        US_TOP_ECHO,
        distanceTop
    );

    if (!midValid || !fullValid || !topValid) {
        Serial.println(
            "ERROR: Invalid ultrasonic measurement"
        );

        Serial.printf(
            "MID: %s | FULL: %s | TOP: %s\n",
            midValid ? "OK" : "FAIL",
            fullValid ? "OK" : "FAIL",
            topValid ? "OK" : "FAIL"
        );

        return false;
    }

    return true;
}

// ======================================
// CREATE AND SEND JSON OVER LORA
// ======================================

bool sendLoRaJSON(
    float distanceMid,
    float distanceFull,
    float distanceTop
)
{
    char payload[200];

    int length = snprintf(
        payload,
        sizeof(payload),
        "{\"bin_id\":\"%s\","
        "\"lat\":%.6f,"
        "\"long\":%.6f,"
        "\"distance_mid_cm\":%.2f,"
        "\"distance_full_cm\":%.2f,"
        "\"distance_top_cm\":%.2f}",
        BIN_ID,
        BIN_LATITUDE,
        BIN_LONGITUDE,
        distanceMid,
        distanceFull,
        distanceTop
    );

    if (length <= 0 ||
        length >= (int)sizeof(payload) ||
        length > 255) {
        Serial.println(
            "ERROR: JSON payload too large"
        );
        return false;
    }

    Serial.println("----------------------");
    Serial.println("Sending JSON:");
    Serial.println(payload);

    if (LoRa.beginPacket() == 0) {
        Serial.println(
            "ERROR: Cannot start LoRa packet"
        );
        return false;
    }

    LoRa.write(
        (const uint8_t *)payload,
        (size_t)length
    );

    if (LoRa.endPacket() != 1) {
        Serial.println(
            "ERROR: LoRa transmission failed"
        );
        return false;
    }

    Serial.println(
        "LoRa transmission completed!"
    );

    return true;
}

// ======================================
// MEASUREMENT AND TRANSMISSION
// ======================================

void measureAndTransmit()
{
    float distanceMid = 0.0f;
    float distanceFull = 0.0f;
    float distanceTop = 0.0f;

    Serial.println();
    Serial.println("======================");
    Serial.println("SMARTWASTE MEASUREMENT");
    Serial.println("======================");

#if TEST

    // Use simulated measurements
    Serial.println("MODE: TEST");

    distanceMid = dummyData[dummyIndex][0];
    distanceFull = dummyData[dummyIndex][1];
    distanceTop = dummyData[dummyIndex][2];

    dummyIndex++;

    if (dummyIndex >= DUMMY_COUNT) {
        dummyIndex = 0;
    }

#else

    // Use real HC-SR04 measurements
    Serial.println("MODE: REAL SENSORS");

    bool valid = readAllSensors(
        distanceMid,
        distanceFull,
        distanceTop
    );

    if (!valid) {
        Serial.println(
            "Packet skipped. Retrying next cycle."
        );
        return;
    }

#endif

    Serial.printf("MID:  %.2f cm\n", distanceMid);
    Serial.printf("FULL: %.2f cm\n", distanceFull);
    Serial.printf("TOP:  %.2f cm\n", distanceTop);

    sendLoRaJSON(
        distanceMid,
        distanceFull,
        distanceTop
    );
}

// ======================================
// SETUP
// ======================================

void setup()
{
    Serial.begin(115200);

    delay(1000);

    Serial.println(
        "SMARTWASTE ESP32 TRANSMITTER"
    );

#if TEST
    Serial.println("TEST MODE ENABLED");
#else
    Serial.println("REAL SENSOR MODE ENABLED");
#endif

    // Keep original sensor initialization
    initUltrasonic(
        US_MID_TRIG, US_MID_ECHO
    );

    initUltrasonic(
        US_FULL_TRIG, US_FULL_ECHO
    );

    initUltrasonic(
        US_TOP_TRIG, US_TOP_ECHO
    );

    // Original SPI initialization
    SPI.begin(
        LORA_SCK,
        LORA_MISO,
        LORA_MOSI,
        LORA_SS
    );

    // Original LoRa control pins
    LoRa.setPins(
        LORA_SS,
        LORA_RST,
        LORA_DIO0
    );

    // Original LoRa initialization
    if (!LoRa.begin(LORA_FREQ)) {
        Serial.println(
            "ERROR: LoRa initialization failed!"
        );

        while (true) {
            delay(1000);
        }
    }

    // Original radio settings
    LoRa.setSpreadingFactor(7);
    LoRa.setSignalBandwidth(125E3);
    LoRa.setCodingRate4(5);
    LoRa.setSyncWord(LORA_SYNC_WORD);
    LoRa.enableCrc();
    LoRa.setTxPower(14);

    Serial.println(
        "LoRa initialized successfully!"
    );

    Serial.println(
        "433.92 MHz | SF7 | BW125 | CR4/5"
    );

    Serial.println(
        "Sync: 0x12 | CRC: Enabled"
    );

    // First transmission
    measureAndTransmit();

    lastSend = millis();
}

// ======================================
// MAIN LOOP
// ======================================

void loop()
{
    if (millis() - lastSend >= SEND_INTERVAL_MS) {
        lastSend = millis();
        measureAndTransmit();
    }
}
