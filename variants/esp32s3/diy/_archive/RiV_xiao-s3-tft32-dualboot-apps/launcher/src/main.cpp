// Dual boot launcher for the XIAO ESP32S3 + Wio-SX1262 + 3.2" ILI9341 (240x320) TFT, landscape 320 x 240, connector on the left.
// Shows two buttons, sets the boot partition of the chosen app and restarts. The apps point the boot partition back at
// this launcher as soon as they start, so every restart returns to this menu.
#include <Arduino.h>
#include <Preferences.h>
#include <LovyanGFX.hpp>
#include "esp_ota_ops.h"
#include "esp_partition.h"
#include "logo_meshtastic.h"

// LovyanGFX reads a plain int as RGB565 and only a uint32_t as RGB888, so every colour goes through this cast
#define RGB(v) ((uint32_t)(v))
#include "logo_pathfinder.h"

// ---- wiring ----
#define PIN_SCK 7
#define PIN_MISO 8
#define PIN_MOSI 9
#define PIN_TFT_CS 1
#define PIN_TFT_DC 2
#define PIN_TFT_BL 3
#define PIN_TOUCH_CS 4
#define PIN_SD_CS 6
#define PIN_LORA_CS 41

static const uint32_t AUTOBOOT_MS = 5000; // boots the last app after this time, any touch cancels the countdown

class LGFX : public lgfx::LGFX_Device
{
    lgfx::Panel_ILI9341 _panel;
    lgfx::Bus_SPI _bus;
    lgfx::Light_PWM _light;
    lgfx::Touch_XPT2046 _touch;

  public:
    LGFX()
    {
        {
            auto cfg = _bus.config();
            cfg.spi_host = SPI2_HOST;
            cfg.spi_mode = 0;
            cfg.freq_write = 40000000;
            cfg.freq_read = 16000000;
            cfg.pin_sclk = PIN_SCK;
            cfg.pin_mosi = PIN_MOSI;
            cfg.pin_miso = -1; // the LCD SDO is not wired
            cfg.pin_dc = PIN_TFT_DC;
            _bus.config(cfg);
            _panel.setBus(&_bus);
        }
        {
            auto cfg = _panel.config();
            cfg.pin_cs = PIN_TFT_CS;
            cfg.pin_rst = -1; // LCD reset is on the EN pad
            cfg.pin_busy = -1;
            cfg.memory_width = 240;
            cfg.memory_height = 320;
            cfg.panel_width = 240;
            cfg.panel_height = 320;
            cfg.offset_x = 0;
            cfg.offset_y = 0;
            cfg.offset_rotation = 0;
            cfg.readable = false;
            cfg.invert = false;
            cfg.rgb_order = false;
            cfg.dlen_16bit = false;
            cfg.bus_shared = true;
            _panel.config(cfg);
        }
        {
            auto cfg = _light.config();
            cfg.pin_bl = PIN_TFT_BL;
            cfg.invert = false;
            cfg.freq = 44000;
            cfg.pwm_channel = 7;
            _light.config(cfg);
            _panel.setLight(&_light);
        }
        {
            auto cfg = _touch.config();
            cfg.x_min = 300;
            cfg.x_max = 3900;
            cfg.y_min = 300;
            cfg.y_max = 3900;
            cfg.pin_int = -1;
            cfg.bus_shared = true;
            cfg.offset_rotation = 7; // verified together with panel rotation 3
            cfg.spi_host = SPI2_HOST;
            cfg.freq = 2500000;
            cfg.pin_sclk = PIN_SCK;
            cfg.pin_mosi = PIN_MOSI;
            cfg.pin_miso = PIN_MISO;
            cfg.pin_cs = PIN_TOUCH_CS;
            _touch.config(cfg);
            _panel.setTouch(&_touch);
        }
        setPanel(&_panel);
    }
};

static LGFX tft;
static Preferences prefs;

struct Choice {
    const char *name;
    esp_partition_subtype_t subtype;
    uint32_t color;
    int x0, x1;
};

static const int BTN_Y0 = 36, BTN_Y1 = 212;

static Choice choices[2] = {
    {"Meshtastic", ESP_PARTITION_SUBTYPE_APP_OTA_0, 0x1E88E5, 8, 156},
    {"Pathfinder", ESP_PARTITION_SUBTYPE_APP_OTA_1, 0xEF6C00, 164, 312},
};

static void drawButton(int i, bool highlight, int secondsLeft)
{
    Choice &c = choices[i];
    const int bw = c.x1 - c.x0, bh = BTN_Y1 - BTN_Y0, cx = (c.x0 + c.x1) / 2;
    if (i == 0) {
        // Meshtastic UI logo on its own green background
        tft.fillRoundRect(c.x0, BTN_Y0, bw, bh, 12, RGB(0x6CEB95));
        tft.pushImage(c.x0 + (bw - LOGO_MESHTASTIC_W) / 2, BTN_Y0 + 44, LOGO_MESHTASTIC_W, LOGO_MESHTASTIC_H,
                      logo_meshtastic, lgfx::palette_8bit, (const lgfx::rgb565_t *)logo_meshtastic_pal);
        for (int k = 0; k < (highlight ? 3 : 1); k++)
            tft.drawRoundRect(c.x0 + k, BTN_Y0 + k, bw - 2 * k, bh - 2 * k, 12, highlight ? RGB(0xFFFFFF) : RGB(0x303030));
        if (highlight && secondsLeft > 0) {
            char buf[24];
            snprintf(buf, sizeof(buf), "starting in %d s", secondsLeft);
            tft.setTextColor(RGB(0x1F2937), RGB(0x6CEB95));
            tft.setTextDatum(textdatum_t::middle_center);
            tft.setFont(&fonts::FreeSans9pt7b);
            tft.drawString(buf, cx, BTN_Y1 - 24);
        }
        return;
    }
    {
        // Pathfinder logo on a white button
        tft.fillRoundRect(c.x0, BTN_Y0, bw, bh, 12, RGB(0xFFFFFF));
        tft.pushImage(c.x0 + (bw - LOGO_PATHFINDER_W) / 2, BTN_Y0 + 14, LOGO_PATHFINDER_W, LOGO_PATHFINDER_H,
                      logo_pathfinder, lgfx::palette_8bit, (const lgfx::rgb565_t *)logo_pathfinder_pal);
        for (int k = 0; k < (highlight ? 4 : 1); k++)
            tft.drawRoundRect(c.x0 + k, BTN_Y0 + k, bw - 2 * k, bh - 2 * k, 12, highlight ? RGB(0xEF6C00) : RGB(0x303030));
        if (highlight && secondsLeft > 0) {
            char buf[24];
            snprintf(buf, sizeof(buf), "starting in %d s", secondsLeft);
            tft.setTextColor(RGB(0x1F2937), RGB(0xFFFFFF));
            tft.setTextDatum(textdatum_t::middle_center);
            tft.setFont(&fonts::FreeSans9pt7b);
            tft.drawString(buf, cx, BTN_Y1 - 22);
        }
        return;
    }
    uint32_t col = RGB(highlight ? c.color : 0x303030);
    tft.fillRoundRect(c.x0, BTN_Y0, bw, bh, 12, col);
    tft.drawRoundRect(c.x0, BTN_Y0, bw, bh, 12, RGB(c.color));
    tft.setTextColor(RGB(0xFFFFFF), col);
    tft.setTextDatum(textdatum_t::middle_center);
    tft.setFont(&fonts::FreeSansBold12pt7b);
    tft.drawString(c.name, cx, (BTN_Y0 + BTN_Y1) / 2 - 14);
    tft.setFont(&fonts::FreeSans9pt7b);
    tft.drawString("LoRa tools", cx, (BTN_Y0 + BTN_Y1) / 2 + 18);
    if (highlight && secondsLeft > 0) {
        char buf[24];
        snprintf(buf, sizeof(buf), "starting in %d s", secondsLeft);
        tft.drawString(buf, cx, BTN_Y1 - 24);
    }
}

static void bootInto(int i)
{
    prefs.putUChar("last", (uint8_t)i);
    const esp_partition_t *p = esp_partition_find_first(ESP_PARTITION_TYPE_APP, choices[i].subtype, NULL);
    if (!p || esp_ota_set_boot_partition(p) != ESP_OK) {
        tft.fillRect(8, 6, 304, 26, RGB(0xB00020));
        tft.setTextColor(RGB(0xFFFFFF), RGB(0xB00020));
        tft.setTextDatum(textdatum_t::middle_center);
        tft.setFont(&fonts::FreeSans9pt7b);
        tft.drawString("No valid app in that slot", 160, 19);
        delay(2500);
        return;
    }
    tft.fillScreen(RGB(0x000000));
    tft.setTextColor(RGB(0xFFFFFF), RGB(0x000000));
    tft.setTextDatum(textdatum_t::middle_center);
    tft.setFont(&fonts::FreeSansBold18pt7b);
    tft.drawString(choices[i].name, 160, 120);
    delay(150);
    esp_restart();
}

static void drawSignature()
{
    tft.setTextDatum(textdatum_t::bottom_right);
    tft.setTextColor(RGB(0x9AA0A6), RGB(0x000000));
    tft.setFont(&fonts::FreeSans9pt7b);
    tft.drawString("RiV", 314, 238);
    tft.setTextDatum(textdatum_t::middle_center);
}

void setup()
{
    // park every chip select high before the shared SPI bus starts
    const int cs[] = {PIN_TFT_CS, PIN_TOUCH_CS, PIN_LORA_CS, PIN_SD_CS};
    for (int pin : cs) {
        pinMode(pin, OUTPUT);
        digitalWrite(pin, HIGH);
    }
    Serial.begin(115200);
    prefs.begin("dualboot", false);
    tft.init();
    tft.setRotation(3);
    tft.setBrightness(180);
    tft.fillScreen(RGB(0x000000));
    tft.setTextDatum(textdatum_t::middle_center);
    tft.setTextColor(RGB(0xFFFFFF), RGB(0x000000));
    tft.setFont(&fonts::FreeSansBold12pt7b);
    tft.drawString("Select the firmware", 160, 17);
    drawSignature();
    uint8_t last = prefs.getUChar("last", 0) & 1;
    drawButton(0, last == 0, 0);
    drawButton(1, last == 1, 0);

    uint32_t t0 = millis();
    bool counting = true;
    int shown = -1;
    for (;;) {
        uint16_t x, y;
        if (tft.getTouch(&x, &y)) {
            for (int i = 0; i < 2; i++) {
                if (x >= choices[i].x0 && x <= choices[i].x1 && y >= BTN_Y0 && y <= BTN_Y1) {
                    drawButton(i, true, 0);
                    bootInto(i);
                    // bootInto only returns on an error, redraw and keep waiting
                    drawButton(0, last == 0, 0);
                    drawButton(1, last == 1, 0);
                    t0 = millis();
                }
            }
            counting = false;
            drawButton(last, true, 0);
            delay(120);
        }
        if (counting) {
            int left = (AUTOBOOT_MS - (millis() - t0) + 999) / 1000;
            if (millis() - t0 >= AUTOBOOT_MS) {
                bootInto(last);
                t0 = millis();
            } else if (left != shown) {
                shown = left;
                drawButton(last, true, left);
            }
        }
        delay(15);
    }
}

void loop() {}
