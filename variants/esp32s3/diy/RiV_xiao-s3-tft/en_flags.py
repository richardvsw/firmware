Import("env")

# I2C AND SENSORS WERE EXCLUDED IN THE BASE ENV, LCD RST MOVES TO EN, TOUCH ROTATION COMES FROM touch_rotation.h
DROP = {
    "-DMESHTASTIC_EXCLUDE_I2C=1",
    "-DMESHTASTIC_EXCLUDE_ENVIRONMENTAL_SENSOR=1",
    "-DLGFX_PIN_RST=3",
    "-DTFT_RST=3",
}

flags = env.get("BUILD_FLAGS", [])
env.Replace(
    BUILD_FLAGS=[
        f for f in flags if f.replace(" ", "") not in DROP and not f.replace(" ", "").startswith("-DLGFX_TOUCH_ROTATION=")
    ]
)
