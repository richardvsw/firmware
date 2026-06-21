// Handheld-S3 Meshtastic Variant
// Hardware: ESP32-S3 N16R8 + RFM95W + ILI9341 2.4" + XPT2046 touch + GK9501S GPS
// Based on meshnode_s3, stripped of encoder/RTC/buzzer/WS2812

#pragma once

// ─── Chip & Flash ────────────────────────────────────────────────────────────
// (Architecture macros defined by PlatformIO)

// ─── USB ─────────────────────────────────────────────────────────────────────
#define USES_CDC_SERIAL

// ─── SPI (RFM95W + ILI9341 share SPI bus) ────────────────────────────────────
#define HW_SPI_SCK      12
#define HW_SPI_MISO     13
#define HW_SPI_MOSI     11
#define SPI_SCK         HW_SPI_SCK
#define SPI_MISO        HW_SPI_MISO
#define SPI_MOSI        HW_SPI_MOSI

// ─── LoRa RFM95W ─────────────────────────────────────────────────────────────
#define LORA_SCK        12
#define LORA_MISO       13
#define LORA_MOSI       11
#define LORA_CS         10
#define LORA_RESET      9
#define LORA_DIO0       14   // IRQ
#define LORA_DIO1       -1   // not connected on RFM95W
#define LORA_DIO2       -1   // not connected

// ─── ILI9341 Display ─────────────────────────────────────────────────────────
#define TFT_SCK         12
#define TFT_MOSI        11
#define TFT_MISO        13
#define TFT_CS          15
#define TFT_DC          16
#define TFT_RST         3
#define TFT_BL          4    // backlight PWM

// ─── XPT2046 Touch Controller ────────────────────────────────────────────────
#define TOUCH_CS        5
#define SCREEN_TOUCH_INT 6

// ─── SD Card ─────────────────────────────────────────────────────────────────
#define SDCARD_CS       7

// ─── I2C (CardKB + BMP280) ───────────────────────────────────────────────────
#define I2C_SDA         2
#define I2C_SCL         1

// ─── CardKB (RP2040 emulating CardKB at 0x5F) ────────────────────────────────
#define CARDKB_ADDR     0x5F
#define HAS_CARDKB      1

// ─── BMP280 Environmental Sensor ─────────────────────────────────────────────
// Uses same I2C bus (SDA=2, SCL=1), address 0x76 or 0x77
#define HAS_BME280      1   // BMP280 compatible define

// ─── GPS GK9501S ─────────────────────────────────────────────────────────────
#define GPS_SERIAL_NUM  1
#define GPS_RX_PIN      42
#define GPS_TX_PIN      41
#define GPS_BAUDRATE    9600
#define HAS_GPS         1
#define GPS_THREAD_INTERVAL 200

// ─── Buttons ─────────────────────────────────────────────────────────────────
#define BUTTON_PIN      0    // Boot button, used as user button
#define BUTTON_ACTIVE_LOW true

// ─── Power ───────────────────────────────────────────────────────────────────
// No PMU on this build — USB powered or raw LiPo with external regulator
#undef HAS_AXP192
#undef HAS_AXP2101

// ─── No encoder / RTC / buzzer / WS2812 ──────────────────────────────────────
#undef HAS_RTC
#undef HAS_BUZZER
#undef HAS_WS2812
#undef INPUTBROKER_MATRIX_TYPE

// ─── MUI / LVGL ──────────────────────────────────────────────────────────────
#define USE_EINK_DYNAMICDISPLAY 0
#define HAS_SCREEN      1

// ─── Misc ────────────────────────────────────────────────────────────────────
#define LED_PIN         -1   // no onboard LED
#define HAS_TELEMETRY   1
#define HAS_ENVIRONMENTAL_SENSOR 1



