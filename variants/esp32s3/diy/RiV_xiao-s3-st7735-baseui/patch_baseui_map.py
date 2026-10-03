import atexit
import os
import shutil
from SCons.Script import Import

Import("env")

PROJECT = env.subst("$PROJECT_DIR")
SCREEN = os.path.join(PROJECT, "src", "graphics", "Screen.cpp")
TFT = os.path.join(PROJECT, "src", "graphics", "TFTDisplay.cpp")
VARIANT_DRAW = os.path.join(PROJECT, "variants", "esp32s3", "diy", "RiV_xiao-s3-st7735-baseui", "graphics", "draw")
SRC_DRAW = os.path.join(PROJECT, "src", "graphics", "draw")
BACKUP = os.path.join(PROJECT, ".pio", "baseui_map_backup")
MAP_FILES = ("BaseMap.cpp", "BaseMap.h", "MapRenderer.cpp", "MapRenderer.h", "basemap_blob.cpp")

def heal():
    if os.path.isdir(BACKUP):
        for target in (SCREEN, TFT):
            saved = os.path.join(BACKUP, os.path.basename(target))
            if os.path.exists(saved):
                shutil.copyfile(saved, target)
        shutil.rmtree(BACKUP, ignore_errors=True)
    for name in MAP_FILES:
        stale = os.path.join(SRC_DRAW, name)
        if os.path.exists(stale):
            os.remove(stale)

def finish():
    for target in (SCREEN, TFT):
        saved = os.path.join(BACKUP, os.path.basename(target))
        if os.path.exists(saved):
            shutil.copyfile(saved, target)
    shutil.rmtree(BACKUP, ignore_errors=True)
    for name in MAP_FILES:
        staged = os.path.join(SRC_DRAW, name)
        if os.path.exists(staged):
            os.remove(staged)

def apply(path, edits):
    with open(path, "rb") as f:
        text = f.read().decode("utf-8")
    nl = "\r\n" if "\r\n" in text else "\n"
    patched = text
    for old, new in edits:
        old, new = old.replace("\n", nl), new.replace("\n", nl)
        if patched.count(old) != 1:
            raise SystemExit(
                "patch_baseui_map: anchor not found exactly once in %s: %s" % (os.path.basename(path), old.strip()[:60])
            )
        patched = patched.replace(old, new)
    with open(path, "wb") as f:
        f.write(patched.encode("utf-8"))
    print("patch_baseui_map: %s hooked for this build, restored on exit" % os.path.basename(path))

INCLUDE_OLD = '#include "draw/DebugRenderer.h"'
INCLUDE_NEW = """#include "draw/DebugRenderer.h"
#if defined(BASEUI_HAS_MAP)
#include "draw/MapRenderer.h"
#endif"""

FRAME_OLD = "    fsi.positions.textMessage = numframes;"
FRAME_NEW = """#if defined(BASEUI_HAS_MAP)
    graphics::MapRenderer::frameIndex = numframes;
    normalFrames[numframes++] = graphics::MapRenderer::drawMapFrame;
    indicatorIcons.push_back(icon_compass);
    PUSH_FRAME_TITLE("Map");
#endif

    fsi.positions.textMessage = numframes;"""

INPUT_OLD = "    // UP/DOWN in message screen scrolls through message threads"
INPUT_NEW = """#if defined(BASEUI_HAS_MAP)
    // MAP
    if (ui->getUiState()->currentFrame == graphics::MapRenderer::frameIndex) {
        if (graphics::MapRenderer::handleInput(event)) {
            setFastFramerate();
            return 0;
        }
    }
#endif

    // UP/DOWN in message screen scrolls through message threads"""

TFT_ROTATION_OLD = "    tft->setRotation(3); // Orient horizontal and wide underneath the silkscreen name label"
TFT_ROTATION_NEW = """#if defined(BASEUI_TFT_ROTATION)
    tft->setRotation(BASEUI_TFT_ROTATION);
#else
    tft->setRotation(3); // Orient horizontal and wide underneath the silkscreen name label
#endif"""

TFT_RGB_OLD = """            cfg.invert = TFT_INVERT;       // Set to true if the light/darkness of the panel is reversed
            cfg.rgb_order = false;         // Set to true if the panel's red and blue are swapped"""
TFT_RGB_NEW = """            cfg.invert = TFT_INVERT;       // Set to true if the light/darkness of the panel is reversed
#ifdef BASEUI_TFT_RGB_ORDER
            cfg.rgb_order = BASEUI_TFT_RGB_ORDER;
#else
            cfg.rgb_order = false;         // Set to true if the panel's red and blue are swapped
#endif"""

heal()

os.makedirs(BACKUP, exist_ok=True)
for target in (SCREEN, TFT):
    shutil.copyfile(target, os.path.join(BACKUP, os.path.basename(target)))
atexit.register(finish)

staged = 0
for name in MAP_FILES:
    source = os.path.join(VARIANT_DRAW, name)
    if os.path.exists(source):
        shutil.copyfile(source, os.path.join(SRC_DRAW, name))
        staged += 1
print("patch_baseui_map: staged %d map source files into src/graphics/draw, removed on exit" % staged)

apply(SCREEN, ((INCLUDE_OLD, INCLUDE_NEW), (FRAME_OLD, FRAME_NEW), (INPUT_OLD, INPUT_NEW)))
apply(TFT, ((TFT_ROTATION_OLD, TFT_ROTATION_NEW), (TFT_RGB_OLD, TFT_RGB_NEW)))
