// XIAO-S3-JOYSTICK Meshtastic Variant
// Same board as the official variants/esp32s3/seeed_xiao_s3 (XIAO ESP32S3 + Wio-SX1262), no display.
// GPS is dropped to free 2 header pins for a 5-way discrete joystick (R/L/U/D/OK + common GND),
// wired via the HAS_TRACKBALL driver (src/input/TrackballInterruptImpl1.cpp) - each direction is its
// own GPIO pulled to GND on press (INPUT_PULLUP, same as any other button here).
// I2C (for the stock OLED expansion board) is kept.

#pragma once

#define LED_POWER 48
#define LED_STATE_ON 1 // State when LED is lit

#define BUTTON_PIN 21 // This is the Program Button
#define BUTTON_NEED_PULLUP

#define BATTERY_PIN -1
#define ADC_CHANNEL ADC_CHANNEL_0
#define BATTERY_SENSE_RESOLUTION_BITS 12

// XIAO S3 Expansion board has 1.3 inch OLED Screen
#define USCREEN_SSD1306

#define I2C_SDA 5
#define I2C_SCL 6

// XIAO S3 LORA module (Wio-SX1262 baseboard)
#define USE_SX1262

#define LORA_MISO 8
#define LORA_SCK 7
#define LORA_MOSI 9
#define LORA_CS 41

#define LORA_RESET 42
#define LORA_DIO1 39

#define LORA_DIO2 38

#ifdef USE_SX1262
#define SX126X_CS LORA_CS
#define SX126X_DIO1 LORA_DIO1
#define SX126X_BUSY 40
#define SX126X_RESET LORA_RESET

//  DIO2 controlls an antenna switch and the TCXO voltage is controlled by DIO3
#define SX126X_DIO2_AS_RF_SWITCH
#define SX126X_RXEN 38
#define SX126X_TXEN RADIOLIB_NC
#define SX126X_DIO3_TCXO_VOLTAGE 1.8
#endif

// ─── 5-way discrete joystick (no GPS on this build; GPS's GPIO43/44 freed for R/OK) ─────────
// XIAO header: D0=GPIO1, D1=GPIO2, D2=GPIO3, D3=GPIO4, D6=GPIO43
#define HAS_TRACKBALL 1
#define TB_UP    3    // XIAO D2
#define TB_DOWN  4    // XIAO D3
#define TB_LEFT  2    // XIAO D1
#define TB_RIGHT 1    // XIAO D0
#define TB_PRESS 43   // XIAO D6, this is the "OK" button
