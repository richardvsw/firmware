Import("env")
import os
import re

# HiBy R1: patches device-ui's FBDriver (library copy, idempotent) from this variant folder only.
#   1. touch:   bind the touchscreen evdev explicitly (auto-discovery bound nothing on the R1)
#   2. scale:   render at a smaller logical size and upscale in the flush -> bigger UI
#   3. power:   screen timeout (sysfs backlight, FBDriver has none), wake on touch / message, power key toggles the screen
# Options (platformio.ini):
#   custom_hiby_touch_device    = /dev/input/event1   (empty disables touch binding)
#   custom_hiby_touch_swap_axes = 0
#   custom_hiby_touch_calib     =                     ("min_x min_y max_x max_y", empty keeps the default)
#   custom_hiby_ui_scale        = 125                 (percent, 100 or empty disables)
#   custom_hiby_power_device    = /dev/input/event0   (KEY_POWER source, empty disables the power key)
#   custom_hiby_backlight       = /sys/class/backlight/backlight_pwm0

def opt(name, default):
    return str(env.GetProjectOption(name, default)).strip()

touch_dev = opt("custom_hiby_touch_device", "/dev/input/event1")
swap = opt("custom_hiby_touch_swap_axes", "0") in ("1", "true", "yes")
calib = opt("custom_hiby_touch_calib", "").replace(",", " ").split()
scale = opt("custom_hiby_ui_scale", "125")
power_dev = opt("custom_hiby_power_device", "/dev/input/event0")
backlight = opt("custom_hiby_backlight", "/sys/class/backlight/backlight_pwm0")
try:
    scale_pct = int(scale) if scale else 100
except ValueError:
    scale_pct = 100
if scale_pct < 100 or scale_pct > 300:
    scale_pct = 100

LIBDIR = env.subst("$PROJECT_DIR/.pio/libdeps/${PIOENV}/meshtastic-device-ui")
cpp = os.path.join(LIBDIR, "source/graphics/driver/FBDriver.cpp")
hdr = os.path.join(LIBDIR, "include/graphics/driver/FBDriver.h")

def rd(p):
    with open(p, "r", encoding="utf-8", newline="") as f:
        raw = f.read()
    return raw.replace("\r\n", "\n"), "\r\n" in raw

def wr(p, s, crlf):
    data = (s.replace("\n", "\r\n") if crlf else s).encode("utf-8")
    with open(p, "rb") as f:
        if f.read() == data:
            return False
    with open(p, "wb") as f:
        f.write(data)
    return True

def strip(s):
    # remove everything this script added earlier (BEGIN/END blocks and the first, unmarked touch block)
    s = re.sub(r"[ \t]*// HIBY-R1 BEGIN (\w+)\n.*?[ \t]*// HIBY-R1 END \1\n", "", s, flags=re.S)
    s = re.sub(r"    // HIBY-R1 touch: bind the touchscreen explicitly.*?\n    }\n(?=    // discover input devices)", "", s, flags=re.S)
    return s

def block(name, body, indent=""):
    return "%s// HIBY-R1 BEGIN %s\n%s%s// HIBY-R1 END %s\n" % (indent, name, body, indent, name)

INCLUDES = """#include "src/display/lv_display_private.h"
#include <fcntl.h>
#include <linux/input.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
"""

HELPERS = r'''namespace
{
// ---- UI scale: render at a smaller logical size, upscale (nearest neighbour) in the flush ----
constexpr int hibyScale = %(scale)d; // percent
int32_t hibyPhysW = 0, hibyPhysH = 0;
lv_display_flush_cb_t hibyOrigFlush = nullptr;
uint8_t *hibyScaled = nullptr;
size_t hibyScaledSize = 0;
int32_t *hibySx = nullptr;
size_t hibySxCap = 0;

void hibyScaleFlush(lv_display_t *disp, const lv_area_t *a, uint8_t *src)
{
    const int32_t w = a->x2 - a->x1 + 1, h = a->y2 - a->y1 + 1;
    const uint32_t px = lv_color_format_get_size(lv_display_get_color_format(disp));
    lv_area_t d;
    d.x1 = a->x1 * hibyScale / 100;
    d.y1 = a->y1 * hibyScale / 100;
    d.x2 = ((a->x2 + 1) * hibyScale + 99) / 100 - 1;
    d.y2 = ((a->y2 + 1) * hibyScale + 99) / 100 - 1;
    if (d.x2 > hibyPhysW - 1)
        d.x2 = hibyPhysW - 1;
    if (d.y2 > hibyPhysH - 1)
        d.y2 = hibyPhysH - 1;
    const int32_t dw = d.x2 - d.x1 + 1, dh = d.y2 - d.y1 + 1;
    if (dw <= 0 || dh <= 0 || w <= 0 || h <= 0) {
        lv_display_flush_ready(disp);
        return;
    }
    size_t need = (size_t)dw * dh * px;
    if (need > hibyScaledSize) {
        free(hibyScaled);
        hibyScaled = (uint8_t *)malloc(need);
        hibyScaledSize = hibyScaled ? need : 0;
    }
    if ((size_t)dw > hibySxCap) {
        free(hibySx);
        hibySx = (int32_t *)malloc((size_t)dw * sizeof(int32_t));
        hibySxCap = hibySx ? (size_t)dw : 0;
    }
    if (!hibyScaled || !hibySx) {
        lv_display_flush_ready(disp);
        return;
    }
    for (int32_t x = 0; x < dw; x++) {
        int32_t s = (d.x1 + x) * 100 / hibyScale - a->x1;
        hibySx[x] = s < 0 ? 0 : (s >= w ? w - 1 : s);
    }
    uint8_t *out = hibyScaled;
    for (int32_t y = 0; y < dh; y++) {
        int32_t sy = (d.y1 + y) * 100 / hibyScale - a->y1;
        sy = sy < 0 ? 0 : (sy >= h ? h - 1 : sy);
        const uint8_t *row = src + (size_t)sy * w * px;
        if (px == 2) {
            const uint16_t *r = (const uint16_t *)row;
            uint16_t *o = (uint16_t *)out;
            for (int32_t x = 0; x < dw; x++)
                o[x] = r[hibySx[x]];
        } else if (px == 4) {
            const uint32_t *r = (const uint32_t *)row;
            uint32_t *o = (uint32_t *)out;
            for (int32_t x = 0; x < dw; x++)
                o[x] = r[hibySx[x]];
        } else {
            for (int32_t x = 0; x < dw; x++)
                memcpy(out + (size_t)x * px, row + (size_t)hibySx[x] * px, px);
        }
        out += (size_t)dw * px;
    }
    hibyOrigFlush(disp, &d, hibyScaled);
}

// returns true when the logical size was changed
bool hibyApplyScale(lv_display_t *disp)
{
    if (hibyScale <= 100 || lv_display_get_rotation(disp) != LV_DISPLAY_ROTATION_0)
        return false;
    hibyPhysW = lv_display_get_horizontal_resolution(disp);
    hibyPhysH = lv_display_get_vertical_resolution(disp);
    const int32_t lw = hibyPhysW * 100 / hibyScale, lh = hibyPhysH * 100 / hibyScale;
    const uint32_t px = lv_color_format_get_size(lv_display_get_color_format(disp));
    const uint32_t bufSize = (uint32_t)lw * px * 80;
    uint8_t *buf = (uint8_t *)malloc(bufSize);
    if (!buf)
        return false;
    hibyOrigFlush = disp->flush_cb;
    lv_display_set_resolution(disp, lw, lh);
    lv_display_set_buffers(disp, buf, NULL, bufSize, LV_DISPLAY_RENDER_MODE_PARTIAL);
    lv_display_set_flush_cb(disp, hibyScaleFlush);
    ILOG_INFO("HIBY-R1 scale: %%dx%%d -> logical %%dx%%d (%%d%%%%)", (int)hibyPhysW, (int)hibyPhysH, (int)lw, (int)lh, hibyScale);
    return true;
}

// ---- screen timeout + power key (the framebuffer driver has neither) ----
const char *const hibyBl = "%(bl)s/brightness";
const char *const hibyBlMax = "%(bl)s/max_brightness";
const char *const hibyPowerDev = "%(power)s";
int hibyBlMaxVal = 100;
uint8_t hibyUserBright = 255;
bool hibyScreenOff = false;
uint32_t hibyTimeoutMs = 30 * 1000;
int hibyPowerFd = -1;
uint32_t hibyOffAt = 0;

void hibyBlWrite(int v)
{
    FILE *f = fopen(hibyBl, "w");
    if (f) {
        fprintf(f, "%%d\n", v);
        fclose(f);
    }
}

int hibyBlFor(uint8_t b)
{
    // the PWM output switches off at the full maximum value (101 of 101 = dark), so stay one below it
    const int top = hibyBlMaxVal > 1 ? hibyBlMaxVal - 1 : 1;
    int v = top * b / 255;
    return v < 1 ? 1 : v;
}

void hibyScreen(bool on)
{
    if (on == !hibyScreenOff)
        return;
    hibyScreenOff = !on;
    if (!on)
        hibyOffAt = lv_tick_get();
    hibyBlWrite(on ? hibyBlFor(hibyUserBright) : 0);
}

void hibyPowerInit()
{
    FILE *f = fopen(hibyBlMax, "r");
    if (f) {
        int m = 0;
        if (fscanf(f, "%%d", &m) == 1 && m > 0)
            hibyBlMaxVal = m;
        fclose(f);
    }
    if (hibyPowerDev[0])
        hibyPowerFd = open(hibyPowerDev, O_RDONLY | O_NONBLOCK);
    ILOG_INFO("HIBY-R1 power key %%s: %%s, backlight max %%d", hibyPowerDev, hibyPowerFd >= 0 ? "open" : "cannot open", hibyBlMaxVal);
}
} // namespace
'''

METHODS = r'''void FBDriver::task_handler(void)
{
    DisplayDriver::task_handler();

    // power key toggles the screen
    if (hibyPowerFd >= 0) {
        struct input_event ev;
        while (read(hibyPowerFd, &ev, sizeof(ev)) == (ssize_t)sizeof(ev)) {
            if (ev.type == EV_KEY && ev.code == KEY_POWER && ev.value == 1) {
                if (hibyScreenOff) {
                    hibyScreen(true);
                    lv_display_trigger_activity(NULL);
                } else {
                    hibyScreen(false);
                }
            }
        }
    }

    const uint32_t idle = lv_display_get_inactive_time(NULL);
    if (hibyScreenOff) {
        // touch (or any input) wakes it, except right after it was switched off (the power key press itself counts as input)
        if (idle < 500 && lv_tick_elaps(hibyOffAt) > 800)
            hibyScreen(true);
    } else if (hibyTimeoutMs > 0 && idle > hibyTimeoutMs) {
        hibyScreen(false);
    }
}

void FBDriver::forceWakeup(void)
{
    hibyScreen(true);
    lv_display_trigger_activity(NULL);
}

void FBDriver::wakeForMessage(void)
{
    forceWakeup();
}

bool FBDriver::isPowersaving(void)
{
    return hibyScreenOff;
}

uint16_t FBDriver::getScreenTimeout()
{
    return hibyTimeoutMs / 1000;
}

void FBDriver::setScreenTimeout(uint16_t timeout)
{
    hibyTimeoutMs = (uint32_t)timeout * 1000;
}

uint8_t FBDriver::getBrightness()
{
    return hibyUserBright;
}

void FBDriver::setBrightness(uint8_t brightness)
{
    hibyUserBright = brightness;
    if (!hibyScreenOff)
        hibyBlWrite(hibyBlFor(brightness));
}

'''

HEADER_DECL = """    void task_handler(void) override;
    void forceWakeup(void) override;
    void wakeForMessage(void) override;
    bool isPowersaving(void) override;
    uint16_t getScreenTimeout() override;
    void setScreenTimeout(uint16_t timeout) override;
    uint8_t getBrightness() override;
    void setBrightness(uint8_t brightness) override;
"""

def touch_body():
    if not touch_dev:
        return None
    b = ("    {\n"
         '        lv_indev_t *hibyTouch = lv_evdev_create(LV_INDEV_TYPE_POINTER, "%s");\n'
         "        if (hibyTouch) {\n"
         "            lv_indev_set_display(hibyTouch, display);\n"
         "            lv_evdev_set_swap_axes(hibyTouch, %s);\n" % (touch_dev, "true" if swap else "false"))
    if len(calib) >= 4:
        b += "            lv_evdev_set_calibration(hibyTouch, %s, %s, %s, %s);\n" % tuple(calib[:4])
    b += ('            ILOG_INFO("HIBY-R1 touch: bound %s");\n'
          "        } else {\n"
          '            ILOG_ERROR("HIBY-R1 touch: cannot open %s");\n'
          "        }\n"
          "    }\n" % (touch_dev, touch_dev))
    return b

def patch_cpp():
    s, crlf = rd(cpp)
    s = strip(s)
    anchors = {
        "inc": "#include <cstring>\n",
        "init": "void FBDriver::init(DeviceGUI *gui)\n{\n",
        "setfile": "    lv_linux_fbdev_set_file(display, device);\n",
        "evdev": "#if LV_USE_EVDEV\n    // discover input devices\n",
        "methods": "#if LV_USE_EVDEV\nvoid FBDriver::discovery_cb(",
    }
    for k, a in anchors.items():
        if a not in s:
            print("HIBY-FBDRIVER WARNING: anchor '%s' not found in FBDriver.cpp, device-ui changed?" % k)
            return
    s = s.replace(anchors["inc"], anchors["inc"] + block("includes", INCLUDES), 1)
    helpers = HELPERS % {"scale": scale_pct, "bl": backlight, "power": power_dev}
    s = s.replace(anchors["init"], block("helpers", helpers) + "\n" + anchors["init"], 1)
    setup = ("    if (hibyApplyScale(display)) {\n"
             "        screenWidth = lv_display_get_horizontal_resolution(display);\n"
             "        screenHeight = lv_display_get_vertical_resolution(display);\n"
             "    }\n"
             "    hibyPowerInit();\n")
    s = s.replace(anchors["setfile"], anchors["setfile"] + block("setup", setup, "    "), 1)
    tb = touch_body()
    if tb:
        s = s.replace(anchors["evdev"], "#if LV_USE_EVDEV\n" + block("touch", tb, "    ") + "    // discover input devices\n", 1)
    s = s.replace(anchors["methods"], block("methods", METHODS) + anchors["methods"], 1)
    if wr(cpp, s, crlf):
        print("HIBY-FBDRIVER: patched FBDriver.cpp (touch=%s, scale=%d%%, power=%s)" % (touch_dev or "off", scale_pct, power_dev or "off"))
    else:
        print("HIBY-FBDRIVER: FBDriver.cpp already up to date")

def patch_hdr():
    s, crlf = rd(hdr)
    s = strip(s)
    a = "    void init(DeviceGUI *gui) override;\n"
    if a not in s:
        print("HIBY-FBDRIVER WARNING: anchor not found in FBDriver.h")
        return
    s = s.replace(a, a + block("decl", HEADER_DECL, "    "), 1)
    wr(hdr, s, crlf)

if not os.path.exists(cpp) or not os.path.exists(hdr):
    print("HIBY-FBDRIVER: FBDriver sources not found (run the build once to fetch libraries): " + cpp)
else:
    patch_cpp()
    patch_hdr()
