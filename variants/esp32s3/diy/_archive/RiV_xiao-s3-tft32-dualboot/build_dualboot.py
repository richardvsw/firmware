"""Builds the launcher, Pathfinder and the Meshtastic dualboot env one after another and merges them into one 8 MB image.

Run from anywhere:  python build_dualboot.py [--skip launcher|pathfinder|meshtastic]...
Output: <repo>/build-artifacts/RiV_xiao-s3-tft-dualboot/dualboot.factory.bin  (flash at 0x0, erase flash first)
        plus the three app images and the partition table next to it for single-slot updates.
"""
import glob
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APPS = os.path.join(os.path.dirname(HERE), "RiV_xiao-s3-tft32-dualboot-apps")
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
OUT = os.path.join(REPO, "build-artifacts", "RiV_xiao-s3-tft32-dualboot")
ENV = "RiV_xiao-s3-tft32-dualboot"
PIO = shutil.which("pio") or os.path.expanduser("~/.platformio/penv/Scripts/pio.exe")
ESPTOOL = os.path.expanduser("~/.platformio/packages/tool-esptoolpy/esptool.py")

# partition offsets, keep in sync with partitions.csv
OFF_BOOT, OFF_PART, OFF_FACTORY, OFF_APP0, OFF_PATH, OFF_FS = 0x0, 0x8000, 0x10000, 0x90000, 0x430000, 0x6D0000
SIZE_FACTORY, SIZE_APP0, SIZE_PATH = 0x80000, 0x3A0000, 0x2A0000

skip = set()
args = sys.argv[1:]
while args:
    a = args.pop(0)
    if a == "--skip" and args:
        skip.add(args.pop(0))


def run(cmd, cwd):
    print(">>", " ".join(cmd), "  [in %s]" % cwd, flush=True)
    r = subprocess.run(cmd, cwd=cwd)
    if r.returncode != 0:
        sys.exit("build step failed: " + " ".join(cmd))


def newest(pattern):
    files = sorted(glob.glob(pattern), key=os.path.getmtime)
    if not files:
        sys.exit("not found: " + pattern)
    return files[-1]


if "launcher" not in skip:
    run([PIO, "run"], os.path.join(APPS, "launcher"))
if "pathfinder" not in skip:
    run([PIO, "run"], os.path.join(APPS, "pathfinder"))
if "meshtastic" not in skip:
    run([PIO, "run", "-e", ENV], REPO)

mt = os.path.join(REPO, ".pio", "build", ENV)
launcher = os.path.join(REPO, ".pio-dualboot-tft32", "launcher", "build", "launcher", "firmware.bin")
pathfinder = os.path.join(REPO, ".pio-dualboot-tft32", "pathfinder", "build", "pathfinder", "firmware.bin")
bootloader = os.path.join(mt, "bootloader.bin")
partitions = os.path.join(mt, "partitions.bin")
cand = [f for f in glob.glob(os.path.join(mt, "firmware-%s-*.bin" % ENV)) if not f.endswith(".factory.bin")]
if not cand:
    sys.exit("Meshtastic app image not found in " + mt)
app0 = sorted(cand, key=os.path.getmtime)[-1]
littlefs = newest(os.path.join(mt, "littlefs-%s-*.bin" % ENV))

for name, path, limit in (("launcher", launcher, SIZE_FACTORY), ("meshtastic", app0, SIZE_APP0), ("pathfinder", pathfinder, SIZE_PATH)):
    size = os.path.getsize(path)
    print("%-11s %8d bytes of %8d (%.0f%%)" % (name, size, limit, 100.0 * size / limit))
    if size > limit:
        sys.exit("%s image does not fit its slot" % name)

os.makedirs(OUT, exist_ok=True)
for src, name in ((launcher, "launcher.bin"), (app0, "meshtastic.bin"), (pathfinder, "pathfinder.bin"),
                  (bootloader, "bootloader.bin"), (partitions, "partitions.bin"), (littlefs, "littlefs.bin")):
    shutil.copy(src, os.path.join(OUT, name))

merged = os.path.join(OUT, "dualboot.factory.bin")
run([sys.executable, ESPTOOL, "--chip", "esp32s3", "merge_bin", "-o", merged,
     "--flash_mode", "keep", "--flash_freq", "keep", "--flash_size", "8MB",
     hex(OFF_BOOT), os.path.join(OUT, "bootloader.bin"),
     hex(OFF_PART), os.path.join(OUT, "partitions.bin"),
     hex(OFF_FACTORY), os.path.join(OUT, "launcher.bin"),
     hex(OFF_APP0), os.path.join(OUT, "meshtastic.bin"),
     hex(OFF_PATH), os.path.join(OUT, "pathfinder.bin"),
     hex(OFF_FS), os.path.join(OUT, "littlefs.bin")], REPO)
print("merged image:", merged, os.path.getsize(merged), "bytes")
