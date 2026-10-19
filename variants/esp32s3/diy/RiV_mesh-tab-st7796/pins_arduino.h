#ifndef Pins_Arduino_h
#define Pins_Arduino_h

#include "soc/soc_caps.h"
#include <stdint.h>

#define USB_VID 0x303A
#define USB_PID 0x80D6

// ==================== UART (Serial Debug) ====================
static const uint8_t TX = 43;
static const uint8_t RX = 44;

// ==================== I2C BUS (Touch FT6336 + Sensors) ====================
static const uint8_t SDA = 18;
static const uint8_t SCL = 17;

// ==================== DEFAULT SPI BUS (Dedicated SPI2 - LoRa RFM95) ====================
static const uint8_t SS = 7;     // LORA_CS
static const uint8_t MOSI = 6;   // LORA_MOSI
static const uint8_t MISO = 3;   // LORA_MISO
static const uint8_t SCK = 5;    // LORA_SCK

// ==================== SECONDARY SPI BUS (Dedicated SPI3 - ST7796 TFT) ====================
static const uint8_t SDO = 13;   // TFT_MOSI
static const uint8_t SDI = 10;   // TFT_MISO
// Note: SCLK TFT di GPIO 14 & CS TFT di GPIO 11 dikelola oleh LovyanGFX/variant.h

// ==================== ANALOG PINS (ADC) ====================
static const uint8_t A0 = 1;
static const uint8_t A1 = 2;
static const uint8_t A2 = 3;
static const uint8_t A3 = 4;     // Battery Sense
static const uint8_t A4 = 5;
static const uint8_t A5 = 6;
static const uint8_t A6 = 7;
static const uint8_t A7 = 8;
static const uint8_t A8 = 9;
static const uint8_t A9 = 10;
static const uint8_t A10 = 11;
static const uint8_t A11 = 12;
static const uint8_t A12 = 13;

// ==================== TOUCH PINS ====================
static const uint8_t T1 = 1;
static const uint8_t T3 = 3;
static const uint8_t T5 = 5;
static const uint8_t T6 = 6;
static const uint8_t T7 = 7;
static const uint8_t T8 = 8;
static const uint8_t T9 = 9;
static const uint8_t T10 = 10;
static const uint8_t T11 = 11;
static const uint8_t T12 = 12;
static const uint8_t T14 = 14;

// ==================== POWER & BATTERY SENSE ====================
static const uint8_t VBAT_SENSE = 4; // Disesuaikan ke GPIO 4 (Sesuai BATTERY_PIN di variant.h)
static const uint8_t VBUS_SENSE = 34;

// ==================== ONBOARD LED & RGB ====================
static const uint8_t RGB_DATA = 40;
#define RGB_BUILTIN (RGB_DATA + SOC_GPIO_PIN_COUNT)
#define RGB_BRIGHTNESS 64

static const uint8_t RGB_PWR = 39;
static const uint8_t LDO2 = 39;
static const uint8_t LED = -1;

#endif /* Pins_Arduino_h */