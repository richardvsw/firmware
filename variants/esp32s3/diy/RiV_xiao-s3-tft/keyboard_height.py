import os

Import("env")

# PORTRAIT 320x480: THE ON-SCREEN KEYBOARD IS 45% OF THE HEIGHT, KEYS COME OUT TALL AND THIN, A SHORTER KEYBOARD GIVES SQUARER KEYS
OLD = "lv_obj_set_size(objects.keyboard, LV_PCT(100), LV_PCT(45));"
NEW = "lv_obj_set_size(objects.keyboard, LV_PCT(100), LV_PCT(34));"

path = env.subst("$PROJECT_DIR/.pio/libdeps/${PIOENV}/meshtastic-device-ui/source/graphics/TFT/TFTView_320x240.cpp")
if os.path.exists(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        content = f.read()
    if OLD in content:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(content.replace(OLD, NEW, 1))
        print(f"Patched {path}: keyboard height 45% -> 34%")
