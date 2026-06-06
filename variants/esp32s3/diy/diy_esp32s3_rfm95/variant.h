#define HAS_GPS 0
#undef GPS_RX_PIN
#undef GPS_TX_PIN

// OLED display via I2C
#define USE_SSD1306
#define I2C_SDA 18
#define I2C_SCL 17

// Boot button (GPIO0 on most ESP32-S3 dev boards)
#define BUTTON_PIN 0
#define BUTTON_NEED_PULLUP

// RFM95W (SX1276) via SPI
#define USE_RF95
#define LORA_CS   10
#define LORA_MOSI 11
#define LORA_SCK  12
#define LORA_MISO 13
#define LORA_DIO0 14 // primary interrupt (TxDone / RxDone)

// Optional: uncomment and connect if you wired RESET and DIO1/DIO2
// #define LORA_RESET  -1
// #define LORA_DIO1   -1
// #define LORA_DIO2   -1
