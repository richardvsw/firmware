#pragma once

#define USES_CDC_SERIAL

// LCD
#define HAS_SPI_TFT                 1
#define ST7735S                     1
#define USE_TFTDISPLAY              1

#define ST7735_CS                   2
#define ST7735_RS                   3
#define ST7735_DC                   3
#define ST7735_RESET                4
#define ST7735_RST                  4
#define TFT_RST                     4
#define ST7735_SDA                  9
#define ST7735_MOSI                 9
#define ST7735_SCK                  7
#define ST7735_MISO                 8
#define ST7735_BUSY                -1
#define ST7735_SPI_HOST     SPI2_HOST

#undef TFT_BL

#define SPI_FREQUENCY        10000000
#define SPI_READ_FREQUENCY    8000000

#define TFT_WIDTH                 128
#define TFT_HEIGHT                160
#define ST7735_WIDTH              128
#define ST7735_HEIGHT             160
#define TFT_OFFSET_X                0
#define TFT_OFFSET_Y                0
#define ST7735_OFFSET_X             0
#define ST7735_OFFSET_Y             0

#define LGFX_ROTATION               0
#define TFT_ROTATION                0
#define TFT_OFFSET_ROTATION         0

#define DISPLAY_FORCE_SMALL_FONTS

// LORA
#define USE_SX1262
#define LORA_SCK                    7
#define LORA_MISO                   8
#define LORA_MOSI                   9
#define LORA_CS                    41
#define LORA_RESET                 42
#define LORA_DIO1                  39
#define LORA_DIO2                  38

#define SX126X_CS               LORA_CS
#define SX126X_DIO1             LORA_DIO1
#define SX126X_BUSY             40
#define SX126X_RESET            LORA_RESET
#define SX126X_DIO2_AS_RF_SWITCH
#define SX126X_RXEN             38
#define SX126X_TXEN             RADIOLIB_NC
#define SX126X_DIO3_TCXO_VOLTAGE 1.8

// GPS / I2C / BUTTON
#define GPS_L76K
#ifdef GPS_L76K
#define GPS_RX_PIN                 44
#define GPS_TX_PIN                 43
#define HAS_GPS                     1
#define GPS_THREAD_INTERVAL        50
#define PIN_SERIAL1_RX      PIN_GPS_TX
#define PIN_SERIAL1_TX      PIN_GPS_RX
#define PIN_GPS_STANDBY             1
#endif

#define I2C_SDA                     5
#define I2C_SCL                     6

#define BUTTON_PIN                 21
#define BUTTON_NEED_PULLUP
#define BATTERY_PIN                -1
#define ADC_CHANNEL                 ADC_CHANNEL_0
#define BATTERY_SENSE_RESOLUTION_BITS 12
#define LED_POWER                  48
#define LED_STATE_ON                1
