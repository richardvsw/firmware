import os
from SCons.Script import Import

Import("env")

LIB = env.subst("$PROJECT_DIR/.pio/libdeps/${PIOENV}/meshtastic-device-ui")


def patch(path, replacements):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8", newline="") as f:
        content = f.read()
    changed = False
    for old, new in replacements:
        if old in content:
            content = content.replace(old, new)
            changed = True
    if changed:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        print(f"Patched {path}")


# OK BUTTON PULLUP
patch(
    os.path.join(LIB, "source", "input", "EncoderInputDriver.cpp"),
    [("pinMode(INPUTDRIVER_ENCODER_BTN, INPUT);", "pinMode(INPUTDRIVER_ENCODER_BTN, INPUT_PULLUP);")],
)

# CHANNEL PANEL BUTTONS
patch(
    os.path.join(LIB, "generated", "ui_240x320", "screens.c"),
    [
        ("lv_obj_set_pos(obj, 224, 18);", "lv_obj_set_pos(obj, 205, 18);"),
        ("lv_obj_set_pos(obj, 224, 54);", "lv_obj_set_pos(obj, 205, 54);"),
        ("lv_obj_set_pos(obj, 224, 80);", "lv_obj_set_pos(obj, 205, 80);"),
    ],
)

# LCD REINIT
drv = os.path.join(LIB, "include", "graphics", "driver", "LGFXDriver.h")
if os.path.exists(drv):
    with open(drv, "r", encoding="utf-8", newline="") as f:
        d = f.read()
    crlf = "\r\n" in d
    d = d.replace("\r\n", "\n")
    if "RIV_LCD_REINIT_MS" not in d:
        a = "        ISpiLock::Guard bus;\n        lgfx->init();\n        lgfx->setBrightness(defaultBrightness);\n"
        b = "template <class LGFX> void LGFXDriver<LGFX>::task_handler(void)\n{\n"
        if a in d and b in d:
            d = d.replace(a, "        ISpiLock::Guard bus;\n        lgfx->init();\n#ifdef RIV_LCD_REINIT_MS\n        delay(120);\n        lgfx->init();\n#endif\n        lgfx->setBrightness(defaultBrightness);\n", 1)
            d = d.replace(b, b + "#ifdef RIV_LCD_REINIT_MS\n    static bool lcdReinit = false;\n    if (!lcdReinit && millis() > RIV_LCD_REINIT_MS) {\n        lcdReinit = true;\n        {\n            ISpiLock::Guard bus;\n            lgfx->init();\n            lgfx->setBrightness(lastBrightness);\n        }\n        lv_obj_invalidate(lv_screen_active());\n    }\n#endif\n", 1)
            with open(drv, "w", encoding="utf-8", newline="") as f:
                f.write(d.replace("\n", "\r\n") if crlf else d)
            print(f"Patched {drv}")
        else:
            print("RIV-LCD-REINIT WARNING: anchors not found in", drv)
