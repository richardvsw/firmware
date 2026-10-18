// XIAO-S3-TFT32 dual boot Meshtastic Variant (temporary, 3.2" ILI9341 wiring)
// Hardware: Seeed XIAO ESP32S3 + Wio-SX1262 baseboard + 2.8/3.2" ILI9431 IPS SPI TFT + XPT2046 touch
// LoRa pinout dari Wio-SX1262 baseboard

#pragma once

// ─── Chip & Flash ────────────────────────────────────────────────────────────
#define USES_CDC_SERIAL

// ─── SPI (Shared Bus - SPI2_HOST) ────────────────────────────────────────────
#define HW_SPI_SCK      7    // XIAO D8
#define HW_SPI_MISO     8    // XIAO D9
#define HW_SPI_MOSI     9    // XIAO D10
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
#define SX126X_DIO2_AS_RF_SWITCH
#define SX126X_RXEN              38
#define SX126X_TXEN              RADIOLIB_NC
#define SX126X_DIO3_TCXO_VOLTAGE 1.8

// ─── ILI9431 Display (TFT Reset dihubungkan ke EN pin) ───────────────────────
#define TFT_SCK         HW_SPI_SCK
#define TFT_MOSI        HW_SPI_MOSI
#define TFT_MISO        HW_SPI_MISO
#define TFT_CS          1    // XIAO D0
#define TFT_DC          2    // XIAO D1
#define TFT_RST         -1   // DIHUBUNGKAN KE PIN EN (Reset Hardware)
#define TFT_BL          3    // XIAO D2, backlight PWM

// ─── XPT2046 Touch Controller ────────────────────────────────────────────────
#define TOUCH_CS        4    // XIAO D3
#define SCREEN_TOUCH_INT -1  // Polled via SPI

// ─── SD card (Pindah ke D5 / GPIO 6) ─────────────────────────────────────────
#define SDCARD_CS       6    // XIAO D5

// ─── GPS (UART Native: GPIO 43 & GPIO 44) ────────────────────────────────────
#define GPS_RX_PIN      44   // XIAO D7 (Hubungkan ke TX GPS)
#define GPS_TX_PIN      43   // XIAO D6 (Hubungkan ke RX GPS)
#define GPS_BAUDRATE    115200   // Baudrate standar GEPRC M10 kalau pakai neo m6 default 9600
#define GPS_THREAD_INTERVAL 50
#define HAS_GPS         1

// ─── ADC Battery / Buzzer Selection (GPIO 5 / XIAO D4) ───────────────────────
#if defined(ACTIVE_BUZZER_MODE) && (ACTIVE_BUZZER_MODE == 1)
    // 🔊 JIKA COMPILE VERSI BUZZER AKTIF:
    // 1. Matikan semua fungsi pembacaan Baterai di Pin 5
    #undef BATTERY_PIN
    #undef ADC_CHANNEL
    #undef ADC_MULTIPLIER
    #undef BATTERY_SENSE_RESOLUTION_BITS
    
    // 2. Sembunyikan pin dari Core Meshtastic agar TIDAK kena error PWM (LEDC)
    #undef HAS_BUZZER
    #define HAS_BUZZER 0
    #undef PIN_BUZZER
    
#else
    // 🔋 JIKA COMPILE VERSI BATERAI (DEFAULT):
    // Jadikan Pin 5 sebagai pembaca voltase baterai
    #define BATTERY_PIN         5    // XIAO D4, ADC1_CH4 (Voltage Divider)
    #define ADC_CHANNEL         ADC_CHANNEL_4
    #define ADC_MULTIPLIER      2.0  // Divider 100k/100k
    
    #ifndef BATTERY_SENSE_RESOLUTION_BITS
    #define BATTERY_SENSE_RESOLUTION_BITS 12 
    #endif

    // Pastikan fungsi buzzer mati
    #undef HAS_BUZZER
    #define HAS_BUZZER          0
#endif

// ─── Button ──────────────────────────────────────────────────────────────────
#define BUTTON_PIN      21   // Unused, input broker is excluded
#define BUTTON_NEED_PULLUP

// ─── Power ───────────────────────────────────────────────────────────────────
#undef HAS_AXP192
#undef HAS_AXP2101

// ─── Not fitted ──────────────────────────────────────────────────────────────
#undef HAS_RTC
#undef HAS_BUZZER
#undef HAS_WS2812
#undef INPUTBROKER_MATRIX_TYPE

// ─── Misc ────────────────────────────────────────────────────────────────────
#define LED_POWER       48
#define LED_STATE_ON    1