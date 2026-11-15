
#include <Arduino.h>
#include <SPI.h>
#include <LoRa.h>

// ======================================
// SMARTWASTE - ESP32 LORA TRANSMITTER
// ALWAYS TRANSMIT - EVEN IF SENSORS FAIL
// ======================================

// 1 = Dummy data
// 0 = Real sensors
#define TEST 0

// ---------- BIN CONFIGURATION ----------

#define BIN_ID "BIN_001"

#define BIN_LATITUDE  45.748
#define BIN_LONGITUDE 21.208

// ---------- ULTRASONIC PINS ----------

#define US_MID_TRIG   22
#define US_MID_ECHO   32

#define US_FULL_TRIG  25
#define US_FULL_ECHO  33

#define US_TOP_TRIG   27
#define US_TOP_ECHO   35

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
const unsigned long SENSOR_DELAY_MS = 60;

const float MIN_DISTANCE_CM = 2.0f;
const float MAX_DISTANCE_CM = 400.0f;

// Invalid sensor value
const float INVALID_DISTANCE = -1.0f;

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
// INITIALIZE ULTRASONIC SENSOR
// ======================================

void initUltrasonic(int trigPin, int echoPin)
{
    pinMode(trigPin, OUTPUT);
    pinMode(echoPin, INPUT);

    digitalWrite(trigPin, LOW);
}

// ======================================
// READ ULTRASONIC DISTANCE
// RETURNS -1 IF SENSOR FAILS
// ======================================

float readDistanceCm(int trigPin, int echoPin)
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
        return INVALID_DISTANCE;
    }

    float distance = (duration * 0.0343f) / 2.0f;

    if (distance < MIN_DISTANCE_CM ||
        distance > MAX_DISTANCE_CM) {
        return INVALID_DISTANCE;
    }

    return distance;
}

// ======================================
// READ ALL SENSORS
// NEVER BLOCK TRANSMISSION
// ======================================

void readAllSensors(
    float &distanceMid,
    float &distanceFull,
    float &distanceTop
)
{
    distanceMid = readDistanceCm(
        US_MID_TRIG,
        US_MID_ECHO
    );

    delay(SENSOR_DELAY_MS);

    distanceFull = readDistanceCm(
        US_FULL_TRIG,
        US_FULL_ECHO
    );

    delay(SENSOR_DELAY_MS);

    distanceTop = readDistanceCm(
        US_TOP_TRIG,
        US_TOP_ECHO
    );

    if (distanceMid < 0) {
        Serial.println("WARNING: MID sensor failed");
    }

    if (distanceFull < 0) {
        Serial.println("WARNING: FULL sensor failed");
    }

    if (distanceTop < 0) {
        Serial.println("WARNING: TOP sensor failed");
    }
}

// ======================================
// SEND JSON OVER LORA
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
        Serial.println("ERROR: Payload too large!");
        return false;
    }

    Serial.println("-----------------------------");
    Serial.println("SENDING LORA PACKET:");
    Serial.println(payload);

    if (LoRa.beginPacket() == 0) {
        Serial.println("ERROR: Cannot start packet!");
        return false;
    }

    size_t written = LoRa.write(
        (const uint8_t *)payload,
        (size_t)length
    );

    if (written != (size_t)length) {
        Serial.println("ERROR: Incomplete packet write!");
        LoRa.endPacket();
        return false;
    }

    if (LoRa.endPacket() != 1) {
        Serial.println("ERROR: LoRa TX failed!");
        return false;
    }

    Serial.println("LORA PACKET TRANSMITTED!");
    Serial.println("-----------------------------");

    return true;
}

// ======================================
// MEASURE AND TRANSMIT
// ======================================

void measureAndTransmit()
{
    float distanceMid = INVALID_DISTANCE;
    float distanceFull = INVALID_DISTANCE;
    float distanceTop = INVALID_DISTANCE;

    Serial.println();
    Serial.println("=============================");
    Serial.println("SMARTWASTE TRANSMISSION");
    Serial.println("=============================");

#if TEST

    Serial.println("MODE: TEST");

    distanceMid = dummyData[dummyIndex][0];
    distanceFull = dummyData[dummyIndex][1];
    distanceTop = dummyData[dummyIndex][2];

    dummyIndex++;

    if (dummyIndex >= DUMMY_COUNT) {
        dummyIndex = 0;
    }

#else

    Serial.println("MODE: REAL SENSORS");

    readAllSensors(
        distanceMid,
        distanceFull,
        distanceTop
    );

#endif

    Serial.printf(
        "MID:  %.2f cm\n",
        distanceMid
    );

    Serial.printf(
        "FULL: %.2f cm\n",
        distanceFull
    );

    Serial.printf(
        "TOP:  %.2f cm\n",
        distanceTop
    );

    // ALWAYS ATTEMPT TRANSMISSION
    // EVEN IF ALL SENSORS FAILED

    bool success = sendLoRaJSON(
        distanceMid,
        distanceFull,
        distanceTop
    );

    if (!success) {
        Serial.println("WARNING: LoRa TX attempt failed!");
    }
}

// ======================================
// SETUP
// ======================================

void setup()
{
    Serial.begin(115200);

    delay(1000);

    Serial.println("SMARTWASTE ESP32 TRANSMITTER");
    Serial.println("ALWAYS TRANSMIT MODE");

    // Initialize ultrasonic sensors

    initUltrasonic(
        US_MID_TRIG,
        US_MID_ECHO
    );

    initUltrasonic(
        US_FULL_TRIG,
        US_FULL_ECHO
    );

    initUltrasonic(
        US_TOP_TRIG,
        US_TOP_ECHO
    );

    // Initialize SPI

    SPI.begin(
        LORA_SCK,
        LORA_MISO,
        LORA_MOSI,
        LORA_SS
    );

    // Configure LoRa pins

    LoRa.setPins(
        LORA_SS,
        LORA_RST,
        LORA_DIO0
    );

    // Initialize LoRa

    if (!LoRa.begin(LORA_FREQ)) {
        Serial.println("ERROR: LoRa initialization failed!");

        while (true) {
            delay(1000);
        }
    }

    // Radio configuration

    LoRa.setSpreadingFactor(7);
    LoRa.setSignalBandwidth(125E3);
    LoRa.setCodingRate4(5);
    LoRa.setSyncWord(LORA_SYNC_WORD);
    LoRa.enableCrc();
    LoRa.setTxPower(14);

    Serial.println("LoRa initialized successfully!");
    Serial.println("Frequency: 433.92 MHz");
    Serial.println("SF7 | BW125 | CR4/5");
    Serial.println("Sync Word: 0x12");
    Serial.println("CRC: Enabled");

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
