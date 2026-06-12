// LovyanGFX driver config for ILI9341 2.4" 320x240
// Place this file in the variant folder

#pragma once
#include <LovyanGFX.hpp>

class LGFX : public lgfx::LGFX_Device {
    lgfx::Panel_ILI9341  _panel_instance;
    lgfx::Bus_SPI        _bus_instance;
    lgfx::Light_PWM      _light_instance;

public:
    LGFX(void) {
        // ── SPI bus config ────────────────────────────────────────────────────
        {
            auto cfg = _bus_instance.config();
            cfg.spi_host   = SPI2_HOST;
            cfg.spi_mode   = 0;
            cfg.freq_write = 40000000;
            cfg.freq_read  = 16000000;
            cfg.spi_3wire  = false;
            cfg.use_lock   = true;
            cfg.dma_channel = SPI_DMA_CH_AUTO;
            cfg.pin_sclk   = 12;
            cfg.pin_mosi   = 11;
            cfg.pin_miso   = 13;
            cfg.pin_dc     = 6;
            _bus_instance.config(cfg);
            _panel_instance.setBus(&_bus_instance);
        }

        // ── Panel config ──────────────────────────────────────────────────────
        {
            auto cfg = _panel_instance.config();
            cfg.pin_cs        = 5;
            cfg.pin_rst       = 7;
            cfg.pin_busy      = -1;
            cfg.panel_width   = 240;
            cfg.panel_height  = 320;
            cfg.offset_x      = 0;
            cfg.offset_y      = 0;
            cfg.offset_rotation = 1;  // landscape, USB on right
            cfg.dummy_read_pixel = 8;
            cfg.dummy_read_bits  = 1;
            cfg.readable      = true;
            cfg.invert        = false;
            cfg.rgb_order     = false;
            cfg.dlen_16bit    = false;
            cfg.bus_shared    = true;  // shares SPI with RFM95W
            _panel_instance.config(cfg);
        }

        // ── Backlight config ──────────────────────────────────────────────────
        {
            auto cfg = _light_instance.config();
            cfg.pin_bl        = 8;
            cfg.invert        = false;
            cfg.freq          = 44100;
            cfg.pwm_channel   = 7;
            _light_instance.config(cfg);
            _panel_instance.setLight(&_light_instance);
        }

        setPanel(&_panel_instance);
    }
};
