#pragma once

#define USES_CDC_SERIAL

// SPI
#define HW_SPI_SCK      7
#define HW_SPI_MISO     8
#define HW_SPI_MOSI     9
#define SPI_SCK         HW_SPI_SCK
#define SPI_MISO        HW_SPI_MISO
#define SPI_MOSI        HW_SPI_MOSI

// LORA
#define USE_SX1262

#define LORA_SCK        HW_SPI_SCK
#define LORA_MISO       HW_SPI_MISO
#define LORA_MOSI       HW_SPI_MOSI
#define LORA_CS         41
#define LORA_RESET      42
#define LORA_DIO1       39
#define LORA_DIO2       38

#define SX126X_CS               LORA_CS
#define SX126X_DIO1             LORA_DIO1
#define SX126X_BUSY             40
#define SX126X_RESET            LORA_RESET
#define SX126X_DIO2_AS_RF_SWITCH
#define SX126X_RXEN             38
#define SX126X_TXEN             RADIOLIB_NC
#define SX126X_DIO3_TCXO_VOLTAGE 1.8

// LCD
#define TFT_SCK         HW_SPI_SCK
#define TFT_MOSI        HW_SPI_MOSI
#define TFT_MISO        HW_SPI_MISO

#ifdef ST7735_GPS_WIRING
// GPS
#define GPS_RX_PIN          44
#define GPS_TX_PIN          43
#define HAS_GPS             1
#define GPS_THREAD_INTERVAL 50
#define PIN_GPS_STANDBY     1
#else
// BUTTON
#define BUTTON_PIN      21
#define BUTTON_NEED_PULLUP
#endif

// POWER
#undef HAS_AXP192
#undef HAS_AXP2101

#undef HAS_RTC
#undef HAS_BUZZER
#undef HAS_WS2812
#undef INPUTBROKER_MATRIX_TYPE

// LED
#define LED_POWER       48
#define LED_STATE_ON    1
