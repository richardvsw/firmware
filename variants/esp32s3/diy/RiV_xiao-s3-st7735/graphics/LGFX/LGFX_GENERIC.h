#pragma once

// Variant copy for RiV_xiao-s3-st7735 (128x160 ST7735S, no touch). Differences from the stock template:
//  - LGFX_MEMORY_WIDTH/HEIGHT set the driver RAM size (default = panel size, so no offset arithmetic)
//  - LGFX_DOWNSCALE=K: the UI canvas (LGFX_SCREEN_*) is K times larger than the picture on the panel.
//    pushImage() below keeps the whole canvas in PSRAM and averages KxK blocks down onto the panel.

/**
 * @file LGFX_GENERIC.h
 * @author mverch67
 * @brief Generic LGFX class that works with compiler defines
 * @version 0.1
 * @date 2024-06-24
 *
 * Usage example for https://www.aliexpress.com/item/1005006323532762.html (2.4inch ST7789 touch)
 * Add to platformio.ini (pins for T3S3 v1.1 or v1.2):
 * build_flags =
 *  -D LGFX_DRIVER_TEMPLATE
 *  -D LGFX_DRIVER=LGFX_GENERIC
 *  -D LGFX_PANEL=ST7789
 *  -D LGFX_TOUCH=XPT2046
 *  -D LGFX_INVERT_COLOR=true
 *  -D LGFX_PIN_SCK=12
 *  -D LGFX_PIN_MOSI=15
 *  -D LGFX_PIN_MISO=16
 *  -D LGFX_PIN_DC=47
 *  -D LGFX_PIN_CS=48
 *  -D LGFX_PIN_RST=34
 *  -D LGFX_PIN_BL=35
 *  -D LGFX_TOUCH_INT=38
 *  -D LGFX_TOUCH_CS=39
 *  -D LGFX_TOUCH_CLK=12
 *  -D LGFX_TOUCH_DO=15
 *  -D LGFX_TOUCH_DIN=16
 */

#define LGFX_USE_V1
#include <LovyanGFX.hpp>
#include <esp_heap_caps.h>
#include <string.h>

#ifndef SPI_FREQUENCY
#define SPI_FREQUENCY 20000000
#endif

#ifndef LGFX_CFG_HOST
#define LGFX_CFG_HOST SPI3_HOST
#endif

#ifndef LGFX_SPI_3WIRE
#define LGFX_SPI_3WIRE false
#endif

#ifndef LGFX_SPI_MODE
#define LGFX_SPI_MODE 0
#endif

#ifndef LGFX_PIN_SCK
#define LGFX_PIN_SCK -1
#endif

#ifndef LGFX_PIN_MOSI
#define LGFX_PIN_MOSI -1
#endif

#ifndef LGFX_PIN_MISO
#define LGFX_PIN_MISO -1
#endif

#ifndef LGFX_PIN_DC
#define LGFX_PIN_DC -1
#endif

#ifndef LGFX_PIN_IO0
#define LGFX_PIN_IO0 -1
#endif

#ifndef LGFX_PIN_IO1
#define LGFX_PIN_IO1 -1
#endif

#ifndef LGFX_PIN_IO2
#define LGFX_PIN_IO2 -1
#endif

#ifndef LGFX_PIN_IO3
#define LGFX_PIN_IO3 -1
#endif

#ifndef LGFX_PIN_CS
#define LGFX_PIN_CS -1
#endif

#ifndef LGFX_PIN_RST
#define LGFX_PIN_RST -1
#endif

#ifndef LGFX_PIN_BUSY
#define LGFX_PIN_BUSY -1
#endif

#ifndef LGFX_SCREEN_WIDTH
#define LGFX_SCREEN_WIDTH 320
#endif

#ifndef LGFX_SCREEN_HEIGHT
#define LGFX_SCREEN_HEIGHT 240
#endif

// Variant override: native panel size, when the UI canvas (LGFX_SCREEN_*) is the rotated size,
// e.g. ILI9488 is 320x480 native but drawn as a 480x320 landscape canvas with LGFX_ROTATION=1.
#ifndef LGFX_PANEL_WIDTH
#define LGFX_PANEL_WIDTH LGFX_SCREEN_WIDTH
#endif

#ifndef LGFX_PANEL_HEIGHT
#define LGFX_PANEL_HEIGHT LGFX_SCREEN_HEIGHT
#endif

#ifndef LGFX_MEMORY_WIDTH
#define LGFX_MEMORY_WIDTH LGFX_PANEL_WIDTH
#endif

#ifndef LGFX_MEMORY_HEIGHT
#define LGFX_MEMORY_HEIGHT LGFX_PANEL_HEIGHT
#endif

#ifndef LGFX_DOWNSCALE
#define LGFX_DOWNSCALE 1
#endif

#ifndef LGFX_OFFSET_X
#define LGFX_OFFSET_X 0
#endif

#ifndef LGFX_OFFSET_Y
#define LGFX_OFFSET_Y 0
#endif

#ifndef LGFX_ROTATION
#define LGFX_ROTATION 0
#endif

#ifndef LGFX_READ_PIXEL
#define LGFX_READ_PIXEL 9
#endif

#ifndef LGFX_READ_BITS
#define LGFX_READ_BITS 1
#endif

#ifndef LGFX_READABLE
#define LGFX_READABLE true
#endif

#ifndef LGFX_INVERT_COLOR
#define LGFX_INVERT_COLOR true
#endif

#ifndef LGFX_RGB_ORDER
#define LGFX_RGB_ORDER false
#endif

#ifndef LGFX_DLEN_16BITS
#define LGFX_DLEN_16BITS false
#endif

#ifndef LGFX_INVERT_LIGHT
#define LGFX_INVERT_LIGHT false
#endif

#ifndef LGFX_PWM_FREQ
#define LGFX_PWM_FREQ 44000
#endif

#ifndef LGFX_PWM_CHANNEL
#define LGFX_PWM_CHANNEL 7
#endif

#ifndef LGFX_TOUCH_SPI_HOST
#define LGFX_TOUCH_SPI_HOST 3
#endif

#ifndef LGFX_TOUCH_SPI_FREQ
#define LGFX_TOUCH_SPI_FREQ 1000000
#endif

#ifndef LGFX_TOUCH_CS
#define LGFX_TOUCH_CS -1
#endif

#ifndef LGFX_TOUCH_X_MIN
#define LGFX_TOUCH_X_MIN 0
#endif

#ifndef LGFX_TOUCH_X_MAX
#define LGFX_TOUCH_X_MAX LGFX_SCREEN_WIDTH - 1
#endif

#ifndef LGFX_TOUCH_Y_MIN
#define LGFX_TOUCH_Y_MIN 0
#endif

#ifndef LGFX_TOUCH_Y_MAX
#define LGFX_TOUCH_Y_MAX LGFX_SCREEN_HEIGHT - 1
#endif

#ifndef LGFX_TOUCH_INT
#define LGFX_TOUCH_INT -1
#endif

#ifndef LGFX_TOUCH_RST
#define LGFX_TOUCH_RST -1
#endif

#ifndef LGFX_TOUCH_ROTATION
#define LGFX_TOUCH_ROTATION 0
#endif

#ifndef LGFX_TOUCH_I2C_PORT
#define LGFX_TOUCH_I2C_PORT 0
#endif

#ifndef LGFX_TOUCH_I2C_FREQ
#define LGFX_TOUCH_I2C_FREQ 400000
#endif

#define LCONCAT(A, B) A##B
#define LCONCAT_EXPAND(A, B) LCONCAT(A, B)

#ifndef LGFX_PANEL
#error "LGFX_PANEL must be defined!"
#else
#define LGFX_PANEL_INSTANCE LCONCAT_EXPAND(lgfx::Panel_, LGFX_PANEL)
#endif

#ifdef LGFX_TOUCH
#define LGFX_TOUCH_INSTANCE LCONCAT_EXPAND(lgfx::Touch_, LGFX_TOUCH)
#endif

class LGFX_GENERIC : public lgfx::LGFX_Device
{
    LGFX_PANEL_INSTANCE _panel_instance;
    lgfx::Bus_SPI _bus_instance;
#ifdef LGFX_PIN_BL
    lgfx::Light_PWM _light_instance;
#endif
#ifdef LGFX_TOUCH
    LGFX_TOUCH_INSTANCE _touch_instance;
#endif

  public:
    const uint32_t screenWidth = LGFX_SCREEN_WIDTH;
    const uint32_t screenHeight = LGFX_SCREEN_HEIGHT;

#ifdef LGFX_HAS_BUTTON
    bool hasButton(void) { return true; }
#else
    bool hasButton(void) { return false; }
#endif

#if LGFX_DOWNSCALE > 1
    // LVGL hands over partial areas of the (byte-swapped RGB565) UI canvas. Each area is copied into a full
    // canvas kept in PSRAM, then every KxK block it touches is averaged and pushed to the panel, so blocks
    // that straddle an area edge are still computed from complete data.
    void pushImage(int32_t x, int32_t y, int32_t w, int32_t h, const uint16_t *data)
    {
        constexpr int32_t K = LGFX_DOWNSCALE;
        constexpr int32_t W = LGFX_SCREEN_WIDTH;
        constexpr int32_t H = LGFX_SCREEN_HEIGHT;
        constexpr int32_t OW = W / K;
        constexpr int32_t OH = H / K;
        constexpr int32_t OX = (LGFX_PANEL_WIDTH - OW) / 2;
        constexpr int32_t OY = (LGFX_PANEL_HEIGHT - OH) / 2;
        constexpr int32_t N = K * K;
        static_assert(OW <= LGFX_PANEL_WIDTH && OH <= LGFX_PANEL_HEIGHT, "scaled UI does not fit the panel");

        if (!_canvas) {
            _canvas = (uint16_t *)heap_caps_calloc(W * H, sizeof(uint16_t), MALLOC_CAP_SPIRAM);
            if (!_canvas)
                return;
            fillScreen(0); // blank the margin the scaled picture does not cover
        }

        const int32_t stride = w;
        int32_t sx = 0, sy = 0;
        if (x < 0) {
            sx = -x;
            w += x;
            x = 0;
        }
        if (y < 0) {
            sy = -y;
            h += y;
            y = 0;
        }
        if (x + w > W)
            w = W - x;
        if (y + h > H)
            h = H - y;
        if (w <= 0 || h <= 0)
            return;

        for (int32_t r = 0; r < h; r++)
            memcpy(&_canvas[(y + r) * W + x], &data[(sy + r) * stride + sx], w * sizeof(uint16_t));

        const int32_t bx0 = x / K, bx1 = (x + w - 1) / K;
        const int32_t by0 = y / K, by1 = (y + h - 1) / K;
        const int32_t ow = bx1 - bx0 + 1;

        for (int32_t by = by0; by <= by1; by += STRIP_ROWS) {
            const int32_t rows = (by1 - by + 1) < STRIP_ROWS ? (by1 - by + 1) : STRIP_ROWS;
            for (int32_t r = 0; r < rows; r++) {
                for (int32_t c = 0; c < ow; c++) {
                    const uint16_t *p = &_canvas[((by + r) * K) * W + (bx0 + c) * K];
                    uint32_t sr = 0, sg = 0, sb = 0;
                    for (int32_t j = 0; j < K; j++) {
                        for (int32_t i = 0; i < K; i++) {
                            const uint16_t v = __builtin_bswap16(p[j * W + i]);
                            sr += v >> 11;
                            sg += (v >> 5) & 0x3F;
                            sb += v & 0x1F;
                        }
                    }
                    _strip[r * ow + c] = ((sr / N) << 11) | ((sg / N) << 5) | (sb / N);
                }
            }
            LGFX_Device::pushImage(OX + bx0, OY + by, ow, rows, (const lgfx::rgb565_t *)_strip);
        }
    }

  private:
    static constexpr int32_t STRIP_ROWS = 8;
    uint16_t *_canvas = nullptr;
    uint16_t _strip[(LGFX_SCREEN_WIDTH / LGFX_DOWNSCALE) * STRIP_ROWS];

  public:
#endif

    LGFX_GENERIC(void)
    {
        {
            auto cfg = _bus_instance.config();

            // SPI
            cfg.spi_host = LGFX_CFG_HOST;
            cfg.spi_mode = LGFX_SPI_MODE;
            cfg.freq_write = SPI_FREQUENCY; // SPI clock for transmission (up to 80MHz, rounded to
                                            // the value obtained by dividing 80MHz by an integer)
            cfg.freq_read = 16000000;       // SPI clock when receiving
            cfg.spi_3wire = LGFX_SPI_3WIRE;
            cfg.use_lock = true;               // Set to true to use transaction locking
            cfg.dma_channel = SPI_DMA_CH_AUTO; // SPI_DMA_CH_AUTO; // Set DMA channel
                                               // to use (0=not use DMA / 1=1ch / 2=ch
                                               // / SPI_DMA_CH_AUTO=auto setting)
            cfg.pin_sclk = LGFX_PIN_SCK;       // Set SPI SCLK pin number
            cfg.pin_mosi = LGFX_PIN_MOSI;      // Set SPI MOSI pin number
            cfg.pin_miso = LGFX_PIN_MISO;      // Set SPI MISO pin number (-1 = disable)
            cfg.pin_dc = LGFX_PIN_DC;          // Set SPI DC pin number (-1 = disable)

            // quad spi pins (only used if all 4 are defined)
            cfg.pin_io0 = LGFX_PIN_IO0; // Set Quad SPI IO0 pin number
            cfg.pin_io1 = LGFX_PIN_IO1; // Set Quad SPI IO1 pin number
            cfg.pin_io2 = LGFX_PIN_IO2; // Set Quad SPI IO2 pin number
            cfg.pin_io3 = LGFX_PIN_IO3; // Set Quad SPI IO3 pin number

            _bus_instance.config(cfg);              // applies the set value to the bus.
            _panel_instance.setBus(&_bus_instance); // set the bus on the panel.
        }

        {                                        // Set the display panel control.
            auto cfg = _panel_instance.config(); // Gets a structure for display panel settings.

            cfg.pin_cs = LGFX_PIN_CS;     // Pin number where CS is connected (-1 = disable)
            cfg.pin_rst = LGFX_PIN_RST;   // Pin number where RST is connected  (-1 = disable)
            cfg.pin_busy = LGFX_PIN_BUSY; // Pin number where BUSY is connected (-1 = disable)

            // The following setting values ​​are general initial values ​​for
            // each panel, so please comment out any unknown items and try them.

            cfg.panel_width = LGFX_PANEL_WIDTH;    // actual displayable width
            cfg.panel_height = LGFX_PANEL_HEIGHT;  // actual displayable height
            cfg.offset_x = LGFX_OFFSET_X;           // Panel offset amount in X direction
            cfg.offset_y = LGFX_OFFSET_Y;           // Panel offset amount in Y direction
            cfg.offset_rotation = LGFX_ROTATION;    // Rotation direction value offset 0~7 (4~7 is upside down)
            cfg.dummy_read_pixel = LGFX_READ_PIXEL; // Number of bits for dummy read before pixel readout
            cfg.dummy_read_bits = LGFX_READ_BITS;   // Number of bits for dummy read before non-pixel data read
            cfg.readable = LGFX_READABLE;           // Set to true if data can be read
            cfg.invert = LGFX_INVERT_COLOR;         // Set to true if the light/darkness of the panel is reversed
            cfg.rgb_order = LGFX_RGB_ORDER;         // Set to true if the panel's red and blue are swapped
            cfg.dlen_16bit = LGFX_DLEN_16BITS;      // Set to true for panels that transmit data length in 16-bit
                                                    // units with 16-bit parallel or SPI
            cfg.bus_shared = true;                  // If the bus is shared with the SD card, set to
                                                    // true (bus control with drawJpgFile etc.)
            cfg.memory_width = LGFX_MEMORY_WIDTH;   // driver RAM size (ST7735 variants differ from the visible panel)
            cfg.memory_height = LGFX_MEMORY_HEIGHT;

            // Set the following only when the display is shifted with a driver with a
            // variable number of pixels, such as the ST7735 or ILI9163.
            // cfg.memory_width = TFT_WIDTH;   // Maximum width supported by the
            // driver IC cfg.memory_height = TFT_HEIGHT;  // Maximum height supported
            // by the driver IC
            _panel_instance.config(cfg);
        }

#ifdef LGFX_PIN_BL
        // Set the backlight control. (delete if not necessary)
        {
            auto cfg = _light_instance.config(); // Gets a structure for backlight settings.

            cfg.pin_bl = LGFX_PIN_BL;       // Pin number to which the backlight is connected
            cfg.invert = LGFX_INVERT_LIGHT; // true to invert the brightness of the backlight
            cfg.freq = LGFX_PWM_FREQ;
            cfg.pwm_channel = LGFX_PWM_CHANNEL;

            _light_instance.config(cfg);
            _panel_instance.setLight(&_light_instance); // Set the backlight on the panel.
        }
#endif

#ifdef LGFX_TOUCH
        // Configure settings for touch screen control.
        {
            auto cfg = _touch_instance.config();

#if LGFX_TOUCH_CS > 0
            cfg.spi_host = LGFX_TOUCH_SPI_HOST;
            cfg.freq = LGFX_TOUCH_SPI_FREQ;
            cfg.pin_cs = LGFX_TOUCH_CS;
            cfg.pin_sclk = LGFX_TOUCH_CLK;
            cfg.pin_mosi = LGFX_TOUCH_DIN;
            cfg.pin_miso = LGFX_TOUCH_DO;
#else
            cfg.pin_cs = LGFX_TOUCH_CS;
#endif
            cfg.x_min = LGFX_TOUCH_X_MIN;
            cfg.x_max = LGFX_TOUCH_X_MAX;
            cfg.y_min = LGFX_TOUCH_Y_MIN;
            cfg.y_max = LGFX_TOUCH_Y_MAX;
            cfg.pin_int = LGFX_TOUCH_INT;
            cfg.pin_rst = LGFX_TOUCH_RST;
            cfg.offset_rotation = LGFX_TOUCH_ROTATION;

#ifdef LGFX_TOUCH_I2C_ADDR
            // I2C
            cfg.i2c_port = LGFX_TOUCH_I2C_PORT;
            cfg.i2c_addr = LGFX_TOUCH_I2C_ADDR;
            cfg.pin_sda = LGFX_TOUCH_I2C_SDA;
            cfg.pin_scl = LGFX_TOUCH_I2C_SCL;
            cfg.bus_shared = true;
            cfg.freq = LGFX_TOUCH_I2C_FREQ;
#endif
            _touch_instance.config(cfg);
            _panel_instance.setTouch(&_touch_instance);
        }
#endif
        setPanel(&_panel_instance); // Sets the panel to use.
    }
};
