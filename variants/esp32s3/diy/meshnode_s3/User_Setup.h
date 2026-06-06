// ╔══════════════════════════════════════════════════════════════╗
// ║       TFT_eSPI User Setup — MeshNode-S3                      ║
// ║       ILI9341 3.2" 240×320 on SPI2 shared bus               ║
// ║                                                              ║
// ║  Selected automatically via -I variants/esp32s3/meshnode_s3  ║
// ║  in platformio.ini. Do NOT edit TFT_eSPI's own User_Setup.h  ║
// ╚══════════════════════════════════════════════════════════════╝

#pragma once

#define ILI9341_DRIVER

#define TFT_WIDTH       240
#define TFT_HEIGHT      320

// SPI2 pins (shared with LoRa)
#define TFT_MOSI        11
#define TFT_SCLK        12
#define TFT_MISO        13
#define TFT_CS          15
#define TFT_DC          16
#define TFT_RST         3

// Backlight
#define TFT_BL          4
#define TFT_BACKLIGHT_ON HIGH

// SPI speed
#define SPI_FREQUENCY       40000000
#define SPI_READ_FREQUENCY  20000000

// Force SPI2 (HSPI) on ESP32-S3
#define USE_HSPI_PORT

// Uncomment if red and blue colours appear swapped
// #define TFT_RGB_ORDER TFT_BGR

// Fonts
#define LOAD_GLCD
#define LOAD_FONT2
#define LOAD_FONT4
#define LOAD_FONT6
#define LOAD_FONT7
#define LOAD_FONT8
#define LOAD_GFXFF
#define SMOOTH_FONT
