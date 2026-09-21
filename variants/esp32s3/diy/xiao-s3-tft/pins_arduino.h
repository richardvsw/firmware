#ifndef Pins_Arduino_h
#define Pins_Arduino_h

#include <stdint.h>
#include "variant.h"

#ifdef NO_DISPLAY_TEST
// Identical to variants/esp32s3/seeed_xiao_s3/pins_arduino.h
#define USB_VID 0x2886
#define USB_PID 0x0059

static const uint8_t SDA = 47;
static const uint8_t SCL = 48;

static const uint8_t MISO = 8;
static const uint8_t SCK = 7;
static const uint8_t MOSI = 9;
static const uint8_t SS = 41;
#else
// I2C (unused on this build — XIAO D5/D4 header pins, kept defined for Wire.cpp defaults)
static const uint8_t SDA = 6;
static const uint8_t SCL = 43;

// SPI (shared by LoRa SX1262, ILI9488, XPT2046)
static const uint8_t SS   = LORA_CS;
static const uint8_t MOSI = HW_SPI_MOSI;
static const uint8_t MISO = HW_SPI_MISO;
static const uint8_t SCK  = HW_SPI_SCK;
#endif

#endif /* Pins_Arduino_h */
