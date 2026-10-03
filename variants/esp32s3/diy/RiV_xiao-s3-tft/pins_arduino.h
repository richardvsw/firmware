#ifndef Pins_Arduino_h
#define Pins_Arduino_h

#include <stdint.h>
#include "variant.h"

// I2C is compiled out; these are only the Wire defaults, kept so Wire.cpp compiles (XIAO D5/D6, used by GPS)
static const uint8_t SDA = 6;
static const uint8_t SCL = 43;

// SPI (shared by LoRa SX1262, ILI9488, XPT2046)
static const uint8_t SS   = LORA_CS;
static const uint8_t MOSI = HW_SPI_MOSI;
static const uint8_t MISO = HW_SPI_MISO;
static const uint8_t SCK  = HW_SPI_SCK;

#endif /* Pins_Arduino_h */
