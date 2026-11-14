import time
import json
import os
import argparse
from pathlib import Path

import spidev
import RPi.GPIO as GPIO
import requests
from dotenv import load_dotenv


# ======================================
# SMARTWASTE - LORA RECEIVER
# Raspberry Pi 4 + Ra-02 SX1278
# ======================================

load_dotenv(
    Path(__file__).resolve().parents[1] / ".env"
)

# Raspberry Pi GPIO (BCM numbering)
LORA_RST = 25

# SPI configuration
SPI_BUS = 0
SPI_DEVICE = 0

# Must match ESP32
LORA_FREQUENCY = 433920000
LORA_SYNC_WORD = 0x12

# FastAPI
API_URL = os.getenv("SMARTWASTE_LORA_API_URL", "http://127.0.0.1:8000/iot/ultrasonic-readings")
API_KEY = os.getenv("SMARTWASTE_API_KEY", "")

# SX1278 registers
REG_FIFO = 0x00
REG_OP_MODE = 0x01
REG_FRF_MSB = 0x06
REG_FRF_MID = 0x07
REG_FRF_LSB = 0x08
REG_LNA = 0x0C
REG_FIFO_ADDR_PTR = 0x0D
REG_FIFO_RX_BASE_ADDR = 0x0F
REG_FIFO_RX_CURRENT_ADDR = 0x10
REG_IRQ_FLAGS = 0x12
REG_RX_NB_BYTES = 0x13
REG_PKT_SNR_VALUE = 0x19
REG_PKT_RSSI_VALUE = 0x1A
REG_MODEM_CONFIG_1 = 0x1D
REG_MODEM_CONFIG_2 = 0x1E
REG_PREAMBLE_MSB = 0x20
REG_PREAMBLE_LSB = 0x21
REG_MODEM_CONFIG_3 = 0x26
REG_SYNC_WORD = 0x39
REG_DIO_MAPPING_1 = 0x40
REG_VERSION = 0x42

IRQ_RX_DONE = 0x40
IRQ_CRC_ERROR = 0x20


class LoRaReceiver:

    def __init__(self):
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(
            LORA_RST,
            GPIO.OUT,
            initial=GPIO.HIGH
        )

        self.spi = spidev.SpiDev()
        self.spi.open(SPI_BUS, SPI_DEVICE)
        self.spi.max_speed_hz = 500000
        self.spi.mode = 0

        self.reset()
        self.initialize()

    def read_register(self, address):
        result = self.spi.xfer2([
            address & 0x7F,
            0x00
        ])
        return result[1]

    def write_register(self, address, value):
        self.spi.xfer2([
            address | 0x80,
            value & 0xFF
        ])

    def reset(self):
        GPIO.output(LORA_RST, GPIO.LOW)
        time.sleep(0.02)

        GPIO.output(LORA_RST, GPIO.HIGH)
        time.sleep(0.1)

    def initialize(self):
        print("Initializing LoRa...", flush=True)

        version = self.read_register(REG_VERSION)

        print(
            f"SX1278 version: 0x{version:02X}",
            flush=True
        )

        if version != 0x12:
            raise RuntimeError(
                "LoRa module not detected!"
            )

        # LoRa sleep mode
        self.write_register(REG_OP_MODE, 0x80)
        time.sleep(0.01)

        # LoRa standby mode
        self.write_register(REG_OP_MODE, 0x81)

        # Set frequency
        frf = (
            LORA_FREQUENCY * (1 << 19)
        ) // 32000000

        self.write_register(
            REG_FRF_MSB,
            (frf >> 16) & 0xFF
        )

        self.write_register(
            REG_FRF_MID,
            (frf >> 8) & 0xFF
        )

        self.write_register(
            REG_FRF_LSB,
            frf & 0xFF
        )

        # LNA gain
        value = self.read_register(REG_LNA)

        self.write_register(
            REG_LNA,
            value | 0x03
        )

        # FIFO RX starts at 0
        self.write_register(
            REG_FIFO_RX_BASE_ADDR, 0x00
        )

        self.write_register(
            REG_FIFO_ADDR_PTR, 0x00
        )

        # BW 125kHz
        # Coding Rate 4/5
        # Explicit Header
        self.write_register(
            REG_MODEM_CONFIG_1, 0x72
        )

        # SF7 and CRC enabled
        self.write_register(
            REG_MODEM_CONFIG_2, 0x74
        )

        # AGC enabled
        self.write_register(
            REG_MODEM_CONFIG_3, 0x04
        )

        # Preamble: 8 symbols
        self.write_register(
            REG_PREAMBLE_MSB, 0x00
        )
        self.write_register(
            REG_PREAMBLE_LSB, 0x08
        )

        # Sync word
        self.write_register(
            REG_SYNC_WORD,
            LORA_SYNC_WORD
        )

        # DIO0 = RX Done
        self.write_register(
            REG_DIO_MAPPING_1, 0x00
        )

        # Clear IRQ
        self.write_register(
            REG_IRQ_FLAGS, 0xFF
        )

        # Continuous receiver mode
        self.write_register(
            REG_OP_MODE, 0x85
        )

        print("LoRa initialized successfully!", flush=True)
        print("Frequency: 433.92 MHz", flush=True)
        print("SF7 | BW 125kHz | CR 4/5", flush=True)
        print("CRC enabled", flush=True)
        print("Waiting for packets...", flush=True)

    def receive_packet(self):
        irq = self.read_register(REG_IRQ_FLAGS)

        if not (irq & IRQ_RX_DONE):
            if irq & IRQ_CRC_ERROR:
                self.write_register(
                    REG_IRQ_FLAGS, irq
                )
            return None

        try:
            if irq & IRQ_CRC_ERROR:
                print("CRC error - packet ignored")
                return None

            packet_length = self.read_register(
                REG_RX_NB_BYTES
            )

            if packet_length == 0:
                return None

            address = self.read_register(
                REG_FIFO_RX_CURRENT_ADDR
            )

            self.write_register(
                REG_FIFO_ADDR_PTR,
                address
            )

            # Read FIFO
            result = self.spi.xfer2(
                [REG_FIFO] + [0] * packet_length
            )

            packet = bytes(result[1:])

            # Read signal information
            rssi = self.read_register(
                REG_PKT_RSSI_VALUE
            ) - 164

            snr = self.read_register(
                REG_PKT_SNR_VALUE
            )

            if snr > 127:
                snr -= 256

            snr = snr / 4.0

            return packet, rssi, snr

        finally:
            # Clear interrupt flags
            self.write_register(
                REG_IRQ_FLAGS, 0xFF
            )

    def close(self):
        try:
            self.write_register(
                REG_OP_MODE, 0x80
            )
        finally:
            self.spi.close()
            GPIO.cleanup()


from packet import validate_ultrasonic as validate_reading


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--no-api",
        action="store_true",
        help="Receive packets without sending to FastAPI"
    )

    args = parser.parse_args()

    if not args.no_api and not API_KEY:
        print("ERROR: SMARTWASTE_API_KEY missing!")
        raise SystemExit(1)

    radio = LoRaReceiver()

    try:
        while True:
            result = radio.receive_packet()

            if result is None:
                time.sleep(0.02)
                continue

            packet, rssi, snr = result

            print("\n==============================")
            print("LORA PACKET RECEIVED")
            print("==============================")

            print("RSSI:", rssi, "dBm")
            print("SNR:", snr, "dB")

            try:
                message = packet.decode("utf-8")

                print("RAW:", message)

                data = json.loads(message)

                reading = validate_reading(data)

                bin_id = reading["bin_id"]
                print("BIN ID:", bin_id)
                print("DISTANCES cm: mid=", reading["distance_mid_cm"],
                      "full=", reading["distance_full_cm"], "top=", reading["distance_top_cm"])

                if args.no_api:
                    print("TEST MODE: No database upload")
                    continue

                response = requests.post(
                    API_URL,
                    json=reading,
                    headers={
                        "x-api-key": API_KEY
                    },
                    timeout=5
                )

                if not response.ok:
                    try:
                        print("API rejected reading:", response.status_code, response.json().get("detail"), flush=True)
                    except ValueError:
                        print("API error:", response.status_code, flush=True)
                response.raise_for_status()

                result = response.json()
                if not isinstance(result, dict):
                    raise ValueError("Unexpected IoT API response")
                print("CATEGORY:", result.get("fill_category"), result.get("category_label"), flush=True)
                if result.get("changed") is True:
                    print("Database updated:",
                          "measurement=", result.get("measurement_saved"),
                          "coordinates=", result.get("coordinates_updated"), flush=True)
                elif result.get("changed") is False:
                    print("Unchanged: no database write", flush=True)
                else:
                    raise ValueError("Unexpected IoT API response")

            except (
                UnicodeError,
                ValueError,
                requests.RequestException
            ) as error:
                print("Packet error:", error)

    except KeyboardInterrupt:
        print("\nStopping LoRa receiver...")

    finally:
        radio.close()


if __name__ == "__main__":
    main()
