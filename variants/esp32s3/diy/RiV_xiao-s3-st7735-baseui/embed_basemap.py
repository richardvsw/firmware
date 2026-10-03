import hashlib
import os
from SCons.Script import Import

Import("env")


VARIANT = env.subst("$PROJECT_DIR/variants/esp32s3/diy/RiV_xiao-s3-st7735-baseui")
BIN = os.path.join(VARIANT, "basemap.bin")
OUT = os.path.join(VARIANT, "graphics", "draw", "basemap_blob.cpp")

data = open(BIN, "rb").read() if os.path.exists(BIN) else b""
tag = "// sha1 " + hashlib.sha1(data).hexdigest()

up_to_date = False
if os.path.exists(OUT):
    with open(OUT, "r", encoding="utf-8") as f:
        up_to_date = f.readline().strip() == tag

if not up_to_date:
    rows = []
    for i in range(0, len(data), 24):
        rows.append(",".join(str(b) for b in data[i : i + 24]))
    body = ",\n".join(rows) if rows else "0"
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(tag + "\n")
        f.write("#include <stdint.h>\n")
        f.write("#if defined(BASEUI_HAS_MAP)\n")
        f.write("extern const uint32_t kBasemapBlobLen;\n")
        f.write("extern const uint8_t kBasemapBlob[];\n")
        f.write("const uint32_t kBasemapBlobLen = %d;\n" % len(data))
        f.write("const uint8_t kBasemapBlob[] __attribute__((aligned(4))) = {\n")
        f.write(body + "\n};\n")
        f.write("#endif\n")
    print("embed_basemap: %d bytes embedded from basemap.bin" % len(data))
