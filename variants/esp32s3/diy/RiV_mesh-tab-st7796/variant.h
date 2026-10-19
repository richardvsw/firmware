#ifndef _VARIANT_MESHTAB_DIY_
#define _VARIANT_MESHTAB_DIY_

#define CONFIG_SOC_IEEE802154_SUPPORTED 0

// ==================== POWER & SYSTEM ====================
#define USE_POWERSAVE
#define SLEEP_TIME 180

// Analog Battery Measurement
#define BATTERY_PIN 4       // Voltage divider pin
#define ADC_MULTIPLIER 1.6  // Ratio voltage divider (100k / 220k)
#define ADC_CHANNEL ADC_CHANNEL_3

// Onboard LED & User Button
#define LED_POWER -1 
#define BUTTON_PIN 0        // Boot Button

// Notification Buzzer
#define PIN_BUZZER 12       // PWM Piezo Buzzer

// ==================== I2C BUS (Touch FT6336 & Sensors) ====================
#define I2C_SDA 18
#define I2C_SCL 17

// ==================== LORA RADIO (RFM95 / SX1276 - Dedicated SPI2) ====================
#define USE_RFM95

// LORA SPI Pins
#define LORA_SCK 5
#define LORA_MOSI 6
#define LORA_MISO 3
#define LORA_CS 7

// LORA Control Pins
#define LORA_RESET 8
#define LORA_DIO0 9
#define LORA_DIO1 4
#define LORA_DIO2 RADIOLIB_NC

// ==================== DISPLAY TFT (ST7796 SPI - Dedicated SPI3) ====================
#define HAS_TFT 1
#define ST7796_CS 11
#define ST7796_RST 16
#define ST7796_DC 15        // Disambungkan ke pin LCD_RS / DC pada layar
#define TFT_BL 2           // Display Backlight PWM

// Dimensions & Rotation
#define TFT_WIDTH 320
#define TFT_HEIGHT 480
#define TFT_ROTATION 2

// ==================== TOUCHSCREEN (Capacitive FT6336) ====================
#define HAS_TOUCHSCREEN 1
#define TOUCH_SDA 18
#define TOUCH_SCL 17
#define TOUCH_INT -1
#define TOUCH_RST -1

// ==================== SD CARD (LoRa SPI bus) ====================

#endif // _VARIANT_MESHTAB_DIY_