// pins_arduino.h — handheld-s3 variant
// Required by Arduino-ESP32 framework alongside variant.h

#pragma once
#include "variant.h"

// I2C
static const uint8_t SDA = I2C_SDA;
static const uint8_t SCL = I2C_SCL;

// SPI
static const uint8_t SS   = LORA_CS;
static const uint8_t MOSI = HW_SPI_MOSI;
static const uint8_t MISO = HW_SPI_MISO;
static const uint8_t SCK  = HW_SPI_SCK;

// UART (GPS)
static const uint8_t TX = GPS_TX_PIN;
static const uint8_t RX = GPS_RX_PIN;
