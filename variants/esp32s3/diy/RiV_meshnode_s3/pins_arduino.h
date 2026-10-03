#ifndef Pins_Arduino_h
#define Pins_Arduino_h

#include <stdint.h>

// ── USB descriptor ───────────────────────────────────────────────
#define USB_VID 0x303a
#define USB_PID 0x1001

// ── UART (USB Serial — reserve for debug) ────────────────────────
static const uint8_t TX = 43;
static const uint8_t RX = 44;

// ── I2C bus — BME280, PCF8563, OLED ─────────────────────────────
static const uint8_t SDA = 18;
static const uint8_t SCL = 17;

// ── SPI2 shared bus — LoRa (CS=10) + TFT (CS=15) ────────────────
static const uint8_t SS   = 10;    // LoRa CS as default SS
static const uint8_t MOSI = 11;
static const uint8_t MISO = 13;
static const uint8_t SCK  = 12;

// ── ADC ──────────────────────────────────────────────────────────
static const uint8_t A0 = 1;       // Battery ADC

#endif /* Pins_Arduino_h */
