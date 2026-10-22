import os
from SCons.Script import Import

Import("env")

SRC = env.subst("$PROJECT_DIR/.pio/libdeps/${PIOENV}/LovyanGFX/src/lgfx/v1/touch/Touch_FT5x06.cpp")

OLD = """    _inited = _write_reg(0x00, 0x00)
          && _read_reg(FT5x06_CIPHER_REG, tmp, 6)
          && _write_reg(FT5x06_INTMODE_REG, 0x00) // INT Polling mode
          && tmp[5]
          ;
"""

NEW = """    bool w0 = _write_reg(0x00, 0x00);
    bool rd = _read_reg(FT5x06_CIPHER_REG, tmp, 6);
    bool wi = _write_reg(FT5x06_INTMODE_REG, 0x00);
    Serial.printf("FT5x06 touch init: write0=%d read=%d intmode=%d id=%02x %02x %02x %02x %02x %02x addr=%02x\\n", w0, rd, wi, tmp[0], tmp[1],
                  tmp[2], tmp[3], tmp[4], tmp[5], (unsigned)_cfg.i2c_addr);
    _inited = w0 && rd && wi; // some FT6336 chips return 0 as vendor id
"""

if os.path.exists(SRC):
    with open(SRC, "r", encoding="utf-8", newline="") as f:
        s = f.read()
    crlf = "\r\n" in s
    s = s.replace("\r\n", "\n")
    if "FT5x06 touch init" not in s and OLD in s:
        s = s.replace(OLD, NEW, 1)
        s = s.replace('#include "Touch_FT5x06.hpp"\n', '#include "Touch_FT5x06.hpp"\n#include <Arduino.h>\n#include <Wire.h>\n', 1)
        with open(SRC, "w", encoding="utf-8", newline="") as f:
            f.write(s.replace("\n", "\r\n") if crlf else s)
        print("Patched", SRC)
    elif "FT5x06 touch init" not in s:
        print("TOUCH-PATCH WARNING: anchor not found in", SRC)
