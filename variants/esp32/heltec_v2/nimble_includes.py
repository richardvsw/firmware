#!/usr/bin/env python3
# trunk-ignore-all(ruff/F821)
# trunk-ignore-all(flake8/F821): For SConstruct imports
#
# Fix for heltec_v2 (original ESP32) NimBLE include paths.
#
# Background: framework-arduinoespressif32-libs/esp32/pioarduino-build.py only
# adds Bluedroid headers to CPPPATH, not NimBLE headers — unlike esp32s3/c3/etc.
# which have NimBLE bundled in their SDK libs.  The NimBLE headers for the
# original ESP32 live only in framework-espidf.
#
# The build_flags -I${platformio.packages_dir}/... approach fails on Windows
# because ${platformio.packages_dir} expands with backslashes, producing mixed-
# slash paths that Xtensa GCC cannot resolve.
#
# This script uses platformio.fs.to_unix_path() to normalise all separators to
# forward slashes before appending to CPPPATH, and targets DefaultEnvironment()
# so the paths are present for ALL build units including framework libraries.

import os
from platformio import fs

Import("env")  # noqa: F821 – injected by SCons

platform = env.PioPlatform()

espidf_dir = platform.get_package_dir("framework-espidf")
if not espidf_dir:
    # Fallback: derive from PACKAGES_DIR
    espidf_dir = os.path.join(env.subst("$PACKAGES_DIR"), "framework-espidf")

nimble_base = os.path.join(
    espidf_dir,
    "components",
    "bt",
    "host",
    "nimble",
)

nimble_includes = [
    os.path.join(nimble_base, "nimble", "nimble", "host", "include"),
    os.path.join(nimble_base, "nimble", "nimble", "include"),
    os.path.join(nimble_base, "nimble", "porting", "nimble", "include"),
    os.path.join(nimble_base, "port", "include"),
    os.path.join(nimble_base, "nimble", "porting", "npl", "freertos", "include"),
    os.path.join(nimble_base, "nimble", "nimble", "transport", "include"),
    os.path.join(nimble_base, "nimble", "nimble", "host", "services", "gap", "include"),
    os.path.join(nimble_base, "esp-hci", "include"),
    os.path.join(nimble_base, "nimble", "nimble", "host", "services", "gatt", "include"),
    os.path.join(nimble_base, "nimble", "nimble", "host", "util", "include"),
]

# Normalise to forward slashes so Xtensa GCC on Windows can resolve the paths.
# os.path.join() on Windows produces backslashes; platformio.fs.to_unix_path()
# converts them consistently.
nimble_includes = [fs.to_unix_path(p) for p in nimble_includes]

# Prepend to ensure they are searched before any Bluedroid paths that the
# framework builder may have added.
env.PrependUnique(CPPPATH=nimble_includes)
