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
