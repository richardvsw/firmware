#include <Arduino.h>
#include <LovyanGFX.hpp>

class LGFX : public lgfx::LGFX_Device
{
    lgfx::Panel_ILI9341  _panel_instance;
    lgfx::Bus_SPI        _bus_instance;
    lgfx::Light_PWM      _light_instance;

public:
    LGFX(void)
    {
        // SPI Bus Config
        {
            auto cfg = _bus_instance.config();
            cfg.spi_host   = SPI2_HOST;
            cfg.spi_mode   = 0;
            cfg.freq_write = 20000000; // Keep it at 20MHz for safety/reliability
            cfg.freq_read  = 20000000;
            cfg.spi_3wire  = false;
            cfg.use_lock   = true;
            cfg.dma_channel = SPI_DMA_CH_AUTO;
            cfg.pin_sclk   = 12; // SCK
            cfg.pin_mosi   = 11; // MOSI
            cfg.pin_miso   = 13; // MISO
            cfg.pin_dc     = 16; // DC
            _bus_instance.config(cfg);
            _panel_instance.setBus(&_bus_instance);
        }

        // Panel Config
        {
            auto cfg = _panel_instance.config();
            cfg.pin_cs           = 15; // CS
            cfg.pin_rst          = 3;  // RST
            cfg.pin_busy         = -1;
            cfg.panel_width      = 240;
            cfg.panel_height     = 320;
            cfg.offset_x         = 0;
            cfg.offset_y         = 0;
            cfg.offset_rotation  = 0;
            cfg.dummy_read_pixel = 8;
            cfg.dummy_read_bits  = 1;
            cfg.readable         = true;
            cfg.invert           = false;
            cfg.rgb_order        = false;
            cfg.dlen_16bit       = false;
            cfg.bus_shared       = true;
            _panel_instance.config(cfg);
        }

        // Backlight Config
        {
            auto cfg = _light_instance.config();
            cfg.pin_bl      = 4; // Backlight Pin
            cfg.invert      = false;
            cfg.freq        = 44100;
            cfg.pwm_channel = 7;
            _light_instance.config(cfg);
            _panel_instance.setLight(&_light_instance);
        }

        setPanel(&_panel_instance);
    }
};

LGFX tft;

void setup() {
    Serial.begin(115200);
    delay(1000);
    Serial.println("--- Starting Minimal TFT Test ---");

    // Initialize display
    tft.init();
    tft.setRotation(1); // Landscape
    tft.fillScreen(TFT_BLACK);

    Serial.println("TFT initialized successfully!");
}

void loop() {
    // Cycle screen colors to verify functionality
    Serial.println("Filling screen Red");
    tft.fillScreen(TFT_RED);
    tft.setTextColor(TFT_WHITE);
    tft.setTextSize(2);
    tft.setCursor(20, 100);
    tft.print("TFT TEST: RED");
    delay(2000);

    Serial.println("Filling screen Green");
    tft.fillScreen(TFT_GREEN);
    tft.setTextColor(TFT_BLACK);
    tft.setCursor(20, 100);
    tft.print("TFT TEST: GREEN");
    delay(2000);

    Serial.println("Filling screen Blue");
    tft.fillScreen(TFT_BLUE);
    tft.setTextColor(TFT_WHITE);
    tft.setCursor(20, 100);
    tft.print("TFT TEST: BLUE");
    delay(2000);
}
