// XIAO-S3-TFT Meshtastic Variant
// Hardware: Seeed XIAO ESP32S3 + Wio-SX1262 baseboard + 3.5" ILI9488 IPS SPI TFT (landscape 480x320 or portrait 320x480) + XPT2046 touch
// LoRa pinout copied from variants/esp32s3/seeed_xiao_s3 (official Wio-SX1262 support).
// Display/touch/UI logic adapted from variants/esp32s3/diy/RiV_handheld-s3 (RFM95W -> SX1262 swap).

#pragma once

// ─── Chip & Flash ────────────────────────────────────────────────────────────
// (Architecture macros defined by PlatformIO)

// ─── USB ─────────────────────────────────────────────────────────────────────
#define USES_CDC_SERIAL

// ─── SPI (Wio-SX1262 hardware SPI bus, shared with ILI9488 + XPT2046 + SD) ────────
#define HW_SPI_SCK      7
#define HW_SPI_MISO     8
#define HW_SPI_MOSI     9
#define SPI_SCK         HW_SPI_SCK
#define SPI_MISO        HW_SPI_MISO
#define SPI_MOSI        HW_SPI_MOSI

// ─── LoRa SX1262 (Wio-SX1262 baseboard) ──────────────────────────────────────
#define USE_SX1262

#define LORA_SCK        HW_SPI_SCK
#define LORA_MISO       HW_SPI_MISO
#define LORA_MOSI       HW_SPI_MOSI
#define LORA_CS         41
#define LORA_RESET      42
#define LORA_DIO1       39
#define LORA_DIO2       38

#define SX126X_CS               LORA_CS
#define SX126X_DIO1              LORA_DIO1
#define SX126X_BUSY             40
#define SX126X_RESET            LORA_RESET
// DIO2 controls an antenna switch; DIO3 controls TCXO voltage (Wio-SX1262 baseboard)
#define SX126X_DIO2_AS_RF_SWITCH
#define SX126X_RXEN              38
#define SX126X_TXEN              RADIOLIB_NC
#define SX126X_DIO3_TCXO_VOLTAGE 1.8

// ─── ILI9488 Display (3.5" 480x320, shares SPI bus with LoRa) ────────────────
// Do NOT wire the LCD's SDO/MISO pin: ILI9488 keeps driving it when deselected, the radio then
// fails init ("SX126x init result -2"). The display is write-only; touch T_DO still goes to MISO.
#define TFT_SCK         HW_SPI_SCK
#define TFT_MOSI        HW_SPI_MOSI
#define TFT_MISO        HW_SPI_MISO
#define TFT_CS          1    // XIAO D0
#define TFT_DC          2    // XIAO D1
#ifdef XIAO_TFT_EN_RST
#define TFT_RST         -1   // LCD RST wired to the EN pad
#else
#define TFT_RST         3    // XIAO D2
#endif
#define TFT_BL          4    // XIAO D3, backlight PWM

// ─── XPT2046 Touch Controller (shares SPI bus, polling mode — no IRQ pin) ────
#define TOUCH_CS        5    // XIAO D4
#define SCREEN_TOUCH_INT -1  // not wired, polled via SPI

// ─── SD card (SPI, shares the bus; only CS needed) ───────────────────────────
#define SDCARD_CS       44   // XIAO D7

// ─── GPS (UART) or I2C on D5/D6 ──────────────────────────────────────────────
#ifdef XIAO_TFT_I2C
#define I2C_SDA         43   // XIAO D6
#define I2C_SCL         6    // XIAO D5
// INA219 as the node battery (Power > INA I2C address 64): the battery path only starts when an ADC pin is defined,
// GPIO10 is an unconnected chip pad and is never read while the INA answers
#define BATTERY_PIN     10
#define ADC_CHANNEL     ADC_CHANNEL_9
#ifdef XIAO_TFT_EN_RST
#define GPS_RX_PIN      3    // XIAO D2  <- GPS module TX, receive only
#define GPS_TX_PIN      10   // unconnected chip pin
#define GPS_BAUDRATE    9600
#define GPS_THREAD_INTERVAL 50
#define HAS_GPS         1
#endif
#else
// defaults only; override in the app: Position > GPS RX/TX GPIO
#define GPS_RX_PIN      6    // XIAO D5  <- GPS module TX
#define GPS_TX_PIN      43   // XIAO D6  -> GPS module RX
#define GPS_BAUDRATE    9600
#define GPS_THREAD_INTERVAL 50
#define HAS_GPS         1
#endif

// ─── Button ──────────────────────────────────────────────────────────────────
#define BUTTON_PIN      21   // XIAO user LED / Wio user button (GPIO21); unused, input broker is excluded
#define BUTTON_NEED_PULLUP

// ─── Power ───────────────────────────────────────────────────────────────────
// No PMU — USB powered or raw LiPo with external regulator
#undef HAS_AXP192
#undef HAS_AXP2101

// ─── Not fitted: RTC / buzzer / WS2812 / matrix keyboard (all XIAO header pins D0-D10 are in use) ─────────
#undef HAS_RTC
#undef HAS_BUZZER
#undef HAS_WS2812
#undef INPUTBROKER_MATRIX_TYPE

// ─── MUI / LVGL ──────────────────────────────────────────────────────────────
// HAS_SCREEN is set by the platformio env (0: MUI drives the TFT, legacy Screen is excluded)

// ─── Misc ────────────────────────────────────────────────────────────────────
// Wio-SX1262 green power LED is driven from GPIO48 (same as the official seeed_xiao_s3 variant)
#define LED_POWER       48
#define LED_STATE_ON    1

