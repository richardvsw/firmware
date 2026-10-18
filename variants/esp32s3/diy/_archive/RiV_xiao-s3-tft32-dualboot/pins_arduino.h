#ifndef Pins_Arduino_h
#define Pins_Arduino_h

#include <stdint.h>
#include "variant.h"

// I2C dinonaktifkan karena pin D5 & D6 digunakan untuk SD Card & GPS
static const uint8_t SDA = -1;
static const uint8_t SCL = -1;

// SPI (Shared by LoRa SX1262, ILI9431, XPT2046, SD Card)
static const uint8_t SS   = LORA_CS;      // GPIO 41
static const uint8_t MOSI = HW_SPI_MOSI;   // GPIO 9 (D10)
static const uint8_t MISO = HW_SPI_MISO;   // GPIO 8 (D9)
static const uint8_t SCK  = HW_SPI_SCK;    // GPIO 7 (D8)

#endif /* Pins_Arduino_h */