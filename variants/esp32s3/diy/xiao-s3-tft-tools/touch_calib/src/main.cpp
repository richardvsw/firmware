// XPT2046 touch / rotation diagnostic for xiao-s3-tft (ILI9488 IPS + XPT2046 on a XIAO ESP32S3).
// Adapted from tools/xpt2046_calib (ILI9341 handheld). Same three phases:
//   1) LCD ROTATION: short tap = next rotation, hold ~1s = confirm (pick where TOP is really at the top)
//   2) TOUCH CORNERS: hold each highlighted corner ~2s
//   3) RESULTS: prints the -DLGFX_ROTATION / -DLGFX_TOUCH_ROTATION values to put in platformio.ini
#include <Arduino.h>
#define LGFX_USE_V1
#include <LovyanGFX.hpp>

// Must match the firmware's touch calibration flags (LGFX_TOUCH_X_MIN/MAX, Y_MIN/MAX in platformio.ini).
static const float FW_X_MIN = 300, FW_X_MAX = 3900, FW_Y_MIN = 300, FW_Y_MAX = 3900;

class LGFX : public lgfx::LGFX_Device {
    lgfx::Panel_ILI9488IPS _panel;
    lgfx::Bus_SPI          _bus;
    lgfx::Light_PWM        _light;
    lgfx::Touch_XPT2046    _touch;

  public:
    LGFX() {
        {
            auto cfg = _bus.config();
            cfg.spi_host = SPI2_HOST;
            cfg.spi_mode = 0;
            cfg.freq_write = 40000000;
            cfg.freq_read = 16000000;
            cfg.use_lock = true;
            cfg.dma_channel = SPI_DMA_CH_AUTO;
            cfg.pin_sclk = 7;
            cfg.pin_mosi = 9;
            cfg.pin_miso = 8;
            cfg.pin_dc = 2;
            _bus.config(cfg);
            _panel.setBus(&_bus);
        }
        {
            auto cfg = _panel.config();
            cfg.pin_cs = 1;
            cfg.pin_rst = 3;
            cfg.pin_busy = -1;
            cfg.panel_width = 320;  // native portrait, same as the firmware
            cfg.panel_height = 480;
            cfg.offset_rotation = 1; // same as firmware LGFX_ROTATION=1; rotation printed below is the effective total
            cfg.readable = false;    // LCD SDO is not wired
            cfg.invert = false;
            cfg.rgb_order = false;
            cfg.dlen_16bit = false;
            cfg.bus_shared = true;
            _panel.config(cfg);
        }
        {
            auto cfg = _light.config();
            cfg.pin_bl = 4;
            cfg.invert = false;
            cfg.freq = 44100;
            cfg.pwm_channel = 7;
            _light.config(cfg);
            _panel.setLight(&_light);
        }
        {
            auto cfg = _touch.config();
            cfg.spi_host = SPI2_HOST;
            cfg.freq = 2500000;
            cfg.pin_cs = 5;
            cfg.pin_sclk = 7;
            cfg.pin_mosi = 9;
            cfg.pin_miso = 8;
            // Wide raw range for reliable detection; the firmware's own range is applied in guessRotation()
            cfg.x_min = 0;
            cfg.x_max = 4095;
            cfg.y_min = 0;
            cfg.y_max = 4095;
            cfg.pin_int = -1;
            cfg.pin_rst = -1;
            cfg.offset_rotation = 0;
            cfg.bus_shared = true;
            _touch.config(cfg);
            _panel.setTouch(&_touch);
        }
        setPanel(&_panel);
    }
};

static LGFX lcd;

static bool lcdConfirmed = false;
static int lcdRot = 1;
static int step = 0; // 0-3 collecting, 4 done

static const uint16_t COLORS[4] = {TFT_RED, TFT_GREEN, TFT_BLUE, TFT_YELLOW};
static const char *NAMES[4] = {"TOP-LEFT", "TOP-RIGHT", "BOT-RIGHT", "BOT-LEFT"};
static const char *SHORT[4] = {"TL", "TR", "BR", "BL"};

static int dotX[4], dotY[4];
static float adcX[4], adcY[4];

#define BOX 60
static int boxX(int i) { return (i == 0 || i == 3) ? 0 : lcd.width() - BOX; }
static int boxY(int i) { return (i == 0 || i == 1) ? 0 : lcd.height() - BOX; }

// ─── Phase 1: LCD rotation ───────────────────────────────────────────────────
void drawLCDScreen() {
    lcd.fillScreen(TFT_BLACK);
    int w = lcd.width(), h = lcd.height();

    lcd.fillRect(0, 0, w, 6, TFT_RED);
    lcd.fillRect(0, h - 6, w, 6, TFT_BLUE);
    lcd.fillRect(0, 0, 6, h, TFT_GREEN);
    lcd.fillRect(w - 6, 0, 6, h, TFT_YELLOW);

    lcd.setTextSize(3);
    lcd.setTextColor(TFT_RED, TFT_BLACK);
    lcd.setCursor(w / 2 - 24, 14);
    lcd.print("TOP");
    lcd.setTextColor(TFT_BLUE, TFT_BLACK);
    lcd.setCursor(w / 2 - 24, h - 30);
    lcd.print("BOT");
    lcd.setTextSize(2);
    lcd.setTextColor(TFT_GREEN, TFT_BLACK);
    lcd.setCursor(10, h / 2 - 8);
    lcd.print("L");
    lcd.setTextColor(TFT_YELLOW, TFT_BLACK);
    lcd.setCursor(w - 22, h / 2 - 8);
    lcd.print("R");

    int bw = 200, bh = 60, bx = w / 2 - bw / 2, by = h / 2 - bh / 2;
    lcd.fillRect(bx, by, bw, bh, TFT_NAVY);
    lcd.setTextSize(2);
    lcd.setTextColor(TFT_WHITE, TFT_NAVY);
    lcd.setCursor(bx + 8, by + 6);
    lcd.printf("Rotation: %d", lcdRot);
    lcd.setTextSize(1);
    lcd.setTextColor(TFT_YELLOW, TFT_NAVY);
    lcd.setCursor(bx + 8, by + 28);
    lcd.printf("-DLGFX_ROTATION=%d", (lcdRot + 1) & 7);
    lcd.setCursor(bx + 8, by + 42);
    lcd.print("tap=next  hold=confirm");
}

// ─── Phase 2: corner test ────────────────────────────────────────────────────
void drawCornerScreen(int s) {
    lcd.fillScreen(TFT_BLACK);
    int w = lcd.width(), h = lcd.height();
    lcd.setTextSize(2);
    lcd.setTextColor(TFT_WHITE, TFT_BLACK);
    char buf[32];
    snprintf(buf, sizeof(buf), "Step %d/4", s + 1);
    lcd.setCursor(w / 2 - strlen(buf) * 12 / 2, h / 2 - 40);
    lcd.print(buf);
    lcd.setTextSize(1);
    lcd.setTextColor(COLORS[s], TFT_BLACK);
    lcd.setCursor(w / 2 - strlen(NAMES[s]) * 6 / 2, h / 2 - 16);
    lcd.print(NAMES[s]);
    lcd.setTextColor(TFT_DARKGREY, TFT_BLACK);
    lcd.setCursor(w / 2 - 54, h / 2 + 4);
    lcd.print("Hold corner ~2s");

    for (int i = 0; i < 4; i++) {
        uint16_t c = (i == s) ? COLORS[i] : TFT_DARKGREY;
        int x = boxX(i), y = boxY(i);
        lcd.drawRect(x, y, BOX, BOX, c);
        lcd.drawRect(x + 2, y + 2, BOX - 4, BOX - 4, c);
        lcd.setTextSize(2);
        lcd.setTextColor(c, TFT_BLACK);
        lcd.setCursor(x + 12, y + 20);
        lcd.print(SHORT[i]);
    }
    for (int i = 0; i < s; i++) {
        lcd.fillCircle(dotX[i], dotY[i], 8, COLORS[i]);
        lcd.drawCircle(dotX[i], dotY[i], 9, TFT_WHITE);
    }
    lcd.setTextSize(1);
    for (int i = 0; i < 4; i++) {
        lcd.setTextColor(COLORS[i], TFT_BLACK);
        lcd.setCursor(w / 2 - 60 + i * 30, h - 14);
        lcd.print(SHORT[i]);
    }
}

void drawCountdown(int remaining) {
    int w = lcd.width(), h = lcd.height();
    int bw = 80, bh = 40, bx = w / 2 - bw / 2, by = h / 2 + 24;
    lcd.fillRect(bx, by, bw, bh, TFT_BLACK);
    lcd.setTextSize(3);
    lcd.setTextColor(TFT_ORANGE, TFT_BLACK);
    lcd.setCursor(bx + bw / 2 - 12, by + 8);
    lcd.print(remaining);
}

void markDot(int sx, int sy, int idx) {
    lcd.fillCircle(sx, sy, 8, COLORS[idx]);
    lcd.drawCircle(sx, sy, 9, TFT_WHITE);
    lcd.setTextSize(1);
    lcd.setTextColor(TFT_BLACK, COLORS[idx]);
    lcd.setCursor(sx - 5, sy - 4);
    lcd.print(SHORT[idx]);
    lcd.setTextColor(COLORS[idx], TFT_BLACK);
    int tx = (sx < lcd.width() / 2) ? sx + 14 : sx - 44;
    int ty = (sy < lcd.height() / 2) ? sy + 2 : sy - 12;
    lcd.setCursor(tx, ty);
    lcd.printf("%d,%d", sx, sy);
}

// ─── Phase 3: results ────────────────────────────────────────────────────────
// Apply LovyanGFX touch rotation transform to normalized (nx,ny) → screen (sx,sy)
void applyRot(int rot, float nx, float ny, int w, int h, int &sx, int &sy) {
    switch (rot & 7) {
    case 0: sx = nx * w; sy = ny * h; break;
    case 1: sx = ny * w; sy = nx * h; break;
    case 2: sx = (1 - nx) * w; sy = (1 - ny) * h; break;
    case 3: sx = (1 - ny) * w; sy = nx * h; break;
    case 4: sx = (1 - nx) * w; sy = ny * h; break;
    case 5: sx = nx * w; sy = (1 - ny) * h; break;
    case 6: sx = ny * w; sy = (1 - nx) * h; break;
    case 7: sx = (1 - ny) * w; sy = (1 - nx) * h; break;
    }
    sx = constrain(sx, 0, w - 1);
    sy = constrain(sy, 0, h - 1);
}

int guessRotation() {
    int w = lcd.width(), h = lcd.height();
    int expX[4] = {0, w - 1, w - 1, 0};
    int expY[4] = {0, 0, h - 1, h - 1};
    int bestRot = 0;
    float bestScore = 1e9f;
    for (int r = 0; r < 8; r++) {
        float score = 0;
        for (int i = 0; i < 4; i++) {
            float nx = (adcX[i] - FW_X_MIN) / (FW_X_MAX - FW_X_MIN);
            float ny = (adcY[i] - FW_Y_MIN) / (FW_Y_MAX - FW_Y_MIN);
            int sx, sy;
            applyRot(r, nx, ny, w, h, sx, sy);
            float dx = sx - expX[i], dy = sy - expY[i];
            score += dx * dx + dy * dy;
        }
        if (score < bestScore) {
            bestScore = score;
            bestRot = r;
        }
    }
    return bestRot;
}

void showResults() {
    lcd.fillScreen(TFT_BLACK);
    int w = lcd.width(), h = lcd.height();

    lcd.fillRect(0, 0, w, 24, TFT_DARKGREEN);
    lcd.setTextSize(2);
    lcd.setTextColor(TFT_WHITE, TFT_DARKGREEN);
    lcd.setCursor(w / 2 - 72, 4);
    lcd.print("Build Flags");

    int totalTouchRot = guessRotation();
    int y = 32;
    int fwRot = (lcdRot + 1) & 7;                     // panel offset_rotation=1 adds 1
    int touchRot = (totalTouchRot - fwRot + 8) & 7;   // touch offset alone = total - LGFX_ROTATION
    lcd.setTextSize(1);
    lcd.setTextColor(TFT_YELLOW, TFT_BLACK);
    lcd.setCursor(4, y);
    lcd.printf("-DLGFX_ROTATION=%d", fwRot);
    y += 14;
    lcd.setCursor(4, y);
    lcd.printf("-DLGFX_TOUCH_ROTATION=%d", touchRot);
    y += 16;

    lcd.setTextColor(TFT_CYAN, TFT_BLACK);
    lcd.setCursor(4, y);
    lcd.print("Corner positions:");
    y += 14;
    for (int i = 0; i < 4; i++) {
        lcd.setTextColor(COLORS[i], TFT_BLACK);
        lcd.setCursor(4, y);
        lcd.printf("%s: screen x=%d y=%d", SHORT[i], dotX[i], dotY[i]);
        y += 12;
    }
    y += 8;
    lcd.setTextColor(TFT_DARKGREY, TFT_BLACK);
    lcd.setCursor(4, y);
    lcd.print("Tap anywhere to restart");

    Serial.println("\n=== TOUCH CALIBRATION RESULT ===");
    Serial.printf("-DLGFX_ROTATION=%d\n", fwRot);
    Serial.printf("-DLGFX_TOUCH_ROTATION=%d\n", touchRot);
    for (int i = 0; i < 4; i++)
        Serial.printf("%s screen=(%d,%d)\n", SHORT[i], dotX[i], dotY[i]);
    Serial.println("================================");
}

void resetAll() {
    lcdConfirmed = false;
    lcdRot = 1;
    step = 0;
    lcd.setRotation(lcdRot);
    drawLCDScreen();
}

void setup() {
    Serial.begin(115200);
    // Keep the other devices on the shared SPI bus deselected (the firmware does this in initVariant()).
    // A floating radio CS lets the SX1262 drive MISO and drown out the touch chip's replies.
    pinMode(41, OUTPUT); digitalWrite(41, HIGH); // SX1262 CS
    pinMode(44, OUTPUT); digitalWrite(44, HIGH); // SD card CS
    delay(10);
    lcd.init();
    resetAll();
}

void loop() {
    uint16_t px, py;
    bool touched = lcd.getTouch(&px, &py);

    // Phase 1: LCD rotation
    if (!lcdConfirmed) {
        static uint32_t pressStart = 0;
        static bool pressing = false;
        static int lastCount = -1;

        if (touched && !pressing) {
            pressing = true;
            pressStart = millis();
            lastCount = -1;
        }
        if (pressing) {
            uint32_t elapsed = millis() - pressStart;
            int remaining = 1 - (int)(elapsed / 500);
            if (remaining != lastCount && remaining >= 0) {
                int w = lcd.width(), h = lcd.height();
                lcd.fillRect(w / 2 - 20, h / 2 + 36, 40, 30, TFT_BLACK);
                lcd.setTextSize(3);
                lcd.setTextColor(TFT_ORANGE, TFT_BLACK);
                lcd.setCursor(w / 2 - 12, h / 2 + 38);
                lcd.print(remaining);
                lastCount = remaining;
            }
            if (!touched) {
                pressing = false;
                lastCount = -1;
                if (elapsed >= 1000) {
                    lcdConfirmed = true;
                    drawCornerScreen(0);
                } else {
                    lcdRot = (lcdRot + 1) & 7;
                    lcd.setRotation(lcdRot);
                    drawLCDScreen();
                }
            }
        }
        return;
    }

    // Phase 3: results
    if (step == 4) {
        if (touched) {
            delay(400);
            resetAll();
        }
        return;
    }

    // Phase 2: corner touch (non-blocking)
    static uint32_t cPressStart = 0;
    static bool cPressing = false;
    static int cLastCount = -1;
    static long cSx = 0, cSy = 0;
    static int cN = 0;

    if (touched && !cPressing) {
        cPressing = true;
        cPressStart = millis();
        cLastCount = -1;
        cSx = px;
        cSy = py;
        cN = 1;
    }
    if (cPressing) {
        if (touched) {
            cSx += px;
            cSy += py;
            cN++;
        }
        uint32_t elapsed = millis() - cPressStart;
        int remaining = 2 - (int)(elapsed / 1000);
        if (remaining != cLastCount && remaining >= 0) {
            drawCountdown(remaining);
            cLastCount = remaining;
        }
        if (!touched) {
            cPressing = false;
            cLastCount = -1;
            if (elapsed < 1500) {
                drawCornerScreen(step);
                return;
            }
            int rawPx = cSx / cN, rawPy = cSy / cN;
            int w = lcd.width(), h = lcd.height();
            adcX[step] = (float)rawPx * 4095.f / (w - 1);
            adcY[step] = (float)rawPy * 4095.f / (h - 1);
            dotX[step] = rawPx;
            dotY[step] = rawPy;
            markDot(dotX[step], dotY[step], step);
            Serial.printf("%s: screen=(%d,%d)\n", SHORT[step], dotX[step], dotY[step]);
            step++;
            delay(300);
            if (step < 4)
                drawCornerScreen(step);
            else
                showResults();
        }
    }
}
