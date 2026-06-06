#pragma once

// ╔══════════════════════════════════════════════════════════════╗
// ║         LGFX Driver — MeshNode-S3                            ║
// ║         ILI9341 3.2" 240×320 on SPI2                        ║
// ║  Place at: variants/esp32s3/diy/meshnode_s3/                 ║
// ║            graphics/LGFX/LGFX_MeshNode_S3.h                 ║
// ╚══════════════════════════════════════════════════════════════╝

#include <LovyanGFX.hpp>

class LGFX_MESHNODE_S3 : public lgfx::LGFX_Device
{
    lgfx::Panel_ILI9341  _panel_instance;
    lgfx::Bus_SPI        _bus_instance;
    lgfx::Light_PWM      _light_instance;

public:
    LGFX_MESHNODE_S3(void)
    {
        // ── SPI bus config ────────────────────────────────────────
        {
            auto cfg = _bus_instance.config();
            cfg.spi_host   = SPI2_HOST;
            cfg.spi_mode   = 0;
            cfg.freq_write = 40000000;
            cfg.freq_read  = 20000000;
            cfg.spi_3wire  = false;
            cfg.use_lock   = true;
            cfg.dma_channel = SPI_DMA_CH_AUTO;
            cfg.pin_sclk   = 12;
            cfg.pin_mosi   = 11;
            cfg.pin_miso   = 13;
            cfg.pin_dc     = 16;
            _bus_instance.config(cfg);
            _panel_instance.setBus(&_bus_instance);
        }

        // ── Panel config ──────────────────────────────────────────
        {
            auto cfg = _panel_instance.config();
            cfg.pin_cs           = 15;
            cfg.pin_rst          = 3;
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
            cfg.bus_shared       = true;  // shared SPI bus with LoRa
            _panel_instance.config(cfg);
        }

        // ── Backlight config ──────────────────────────────────────
        {
            auto cfg = _light_instance.config();
            cfg.pin_bl      = 4;
            cfg.invert      = false;
            cfg.freq        = 44100;
            cfg.pwm_channel = 7;
            _light_instance.config(cfg);
            _panel_instance.setLight(&_light_instance);
        }

        setPanel(&_panel_instance);
    }
};
