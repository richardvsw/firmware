#pragma once

#define USES_CDC_SERIAL

// SPI
#define HW_SPI_SCK      12
#define HW_SPI_MISO     13
#define HW_SPI_MOSI     11
#define SPI_SCK         HW_SPI_SCK
#define SPI_MISO        HW_SPI_MISO
#define SPI_MOSI        HW_SPI_MOSI

// LORA
#define LORA_SCK        12
#define LORA_MISO       13
#define LORA_MOSI       11
#define LORA_CS         10
#define LORA_RESET      9
#define LORA_DIO0       14
#define LORA_DIO1       -1
#define LORA_DIO2       -1

// LCD
#define TFT_SCK         15
#define TFT_MOSI        7
#define TFT_MISO        -1
#define TFT_DC          16
#define TFT_RST         3
#define TFT_BL          4

// JOYSTICK
#define STICK_UP          17
#define STICK_DOWN        18
#define STICK_CENTER      38
#define STICK_LEFT        5
#define STICK_RIGHT       6

// BUTTON
#define BUTTON_PIN      0
#define BUTTON_ACTIVE_LOW true

// POWER
#undef HAS_AXP192
#undef HAS_AXP2101

#undef HAS_RTC
#undef HAS_BUZZER
#undef HAS_WS2812
#undef INPUTBROKER_MATRIX_TYPE

// LED
#define LED_PIN         -1
