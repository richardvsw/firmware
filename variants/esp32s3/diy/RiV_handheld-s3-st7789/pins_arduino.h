#ifndef Pins_Arduino_h
#define Pins_Arduino_h

#include <stdint.h>

// I2C
static const uint8_t SDA = 2;
static const uint8_t SCL = 1;

// SPI
static const uint8_t SS   = 10;
static const uint8_t MOSI = 11;
static const uint8_t MISO = 13;
static const uint8_t SCK  = 12;

// UART
static const uint8_t TX = 43;
static const uint8_t RX = 44;

#endif /* Pins_Arduino_h */
