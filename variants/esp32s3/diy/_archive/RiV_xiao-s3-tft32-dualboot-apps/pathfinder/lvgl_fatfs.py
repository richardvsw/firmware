Import("env")
import os
import re

def fix_fatfs(source, target, env):
    path = os.path.join(
        env["PROJECT_LIBDEPS_DIR"],
        env["PIOENV"],
        "lvgl",
        "src",
        "extra",
        "libs",
        "fsdrv",
        "lv_fs_fatfs.c",
    )
    if not os.path.isfile(path):
        print("[fix] lv_fs_fatfs.c not found")
        return

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        src = f.read()

    original = src

    # 1) Perbaiki kalau sudah rusak dobel
    src = src.replace("FF_FF_DIR", "FF_DIR")

    # 2) Ganti DIR murni → FF_DIR (jangan sentuh yang sudah FF_DIR)
    # sizeof(DIR) → sizeof(FF_DIR)
    src = re.sub(r"\bsizeof\s*\(\s*DIR\s*\)", "sizeof(FF_DIR)", src)
    # DIR * → FF_DIR *
    src = re.sub(r"(?<!FF_)\bDIR\s*\*", "FF_DIR *", src)
    # DIR* → FF_DIR*
    src = re.sub(r"(?<!FF_)\bDIR\*", "FF_DIR*", src)

    if src != original:
        with open(path, "w", encoding="utf-8") as f:
            f.write(src)
        print("[fix] Patched lv_fs_fatfs.c (DIR -> FF_DIR, fixed doubles)")
    else:
        print("[fix] lv_fs_fatfs.c already OK")

fix_fatfs(None, None, env)