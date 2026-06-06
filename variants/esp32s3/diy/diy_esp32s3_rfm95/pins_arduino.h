#ifndef Pins_Arduino_h
#define Pins_Arduino_h

#include <stdint.h>

#define USB_VID 0x303a
#define USB_PID 0x1001

// I2C — OLED display
static const uint8_t SDA = 18;
static const uint8_t SCL = 17;

// SPI — RFM95W radio
static const uint8_t MISO = 13;
static const uint8_t SCK  = 12;
static const uint8_t MOSI = 11;
static const uint8_t SS   = 10;

#endif /* Pins_Arduino_h */
