// ╔══════════════════════════════════════════════════════════════╗
// ║              MeshNode-S3 — variant.h                         ║
// ║  ESP32-S3 N16R8 + RFM95W + ILI9341 3.2" TFT                 ║
// ║  Path: variants/esp32s3/diy/meshnode_s3/variant.h            ║
// ╚══════════════════════════════════════════════════════════════╝

// ── No GPS ───────────────────────────────────────────────────────
#define HAS_GPS 0
#undef GPS_RX_PIN
#undef GPS_TX_PIN

// ╔══════════════════════════════════════════════════════════════╗
// ║                    RADIO — RFM95W (SX1276)                   ║
// ╚══════════════════════════════════════════════════════════════╝
#define USE_RF95

#define LORA_SCK            12
#define LORA_MISO           13
#define LORA_MOSI           11
#define LORA_CS             10
#define LORA_RESET          9
#define LORA_DIO0           14      // IRQ — TX/RX done
#define LORA_DIO1           -1      // not connected on RFM95W, required by RF95Configuration.h
#define LORA_DIO2           -1      // not connected

// ╔══════════════════════════════════════════════════════════════╗
// ║           DISPLAY — ILI9341 3.2" 240×320 (no touch)          ║
// ║           Defined here + mirrored as -D flags in             ║
// ║           platformio.ini for TFT_eSPI compatibility          ║
// ╚══════════════════════════════════════════════════════════════╝
#define HAS_SCREEN          1
#define TFT_CS              15
#define TFT_DC              16
#define TFT_RST             3
#define TFT_BL              4
#define TFT_WIDTH           240
#define TFT_HEIGHT          320
// Note: SD slot on TFT module is NOT wired. SD_CS left floating.

// ╔══════════════════════════════════════════════════════════════╗
// ║                   I2C BUS — SCL=17, SDA=18                   ║
// ║    Devices: BME280 (0x76), PCF8563 (0x51), OLED (0x3C)      ║
// ╚══════════════════════════════════════════════════════════════╝
#define I2C_SDA             18
#define I2C_SCL             17

// ── OLED (optional — uncomment if fitted alongside TFT) ──────────
// #define USE_SSD1306

// ── BME280 environmental telemetry ───────────────────────────────
// Enabled via -D HAS_BME280=1 in platformio.ini
// I2C address: 0x76 (SDO=GND) or 0x77 (SDO=VCC)

// ── PCF8563 RTC ───────────────────────────────────────────────────
// Enabled via -D HAS_PCF8563=1 in platformio.ini
#define PCF8563_RTC         0x51
#define RTC_INT             40  // SQW/INT → alarm wake interrupt

#define ADC_CHANNEL         ADC_CHANNEL_0
#define ADC_MULTIPLIER      2.0
