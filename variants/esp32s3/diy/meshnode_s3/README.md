# MeshNode-S3 — Custom Meshtastic Device Variant

ESP32-S3 N16R8 + RFM95W + ILI9341 3.2" TFT + BME280 + PCF8563 + WS2812×8
+ Buzzer + Rotary Encoder + PIR wake.

Minimal diff against upstream `meshtastic/firmware`. Your files live in
one folder — upstream merges have zero conflicts.

---

## File Placement

```
firmware/
├── boards/
│   └── meshnode-s3.json                        ← COPY HERE (custom board def)
└── variants/
    └── esp32s3/
        └── diy/
            └── meshnode_s3/                    ← COPY THIS FOLDER HERE
                ├── variant.h
                ├── pins_arduino.h
                ├── platformio.ini
                └── README.md
```

**Only 2 locations touched — nothing else modified.**

---

## Setup Steps (Windows)

### 1. Install tools
- [VS Code](https://code.visualstudio.com)
- PlatformIO IDE extension (VS Code Extensions sidebar)

### 2. Fork & clone
```powershell
git clone https://github.com/YOUR_USERNAME/firmware.git
cd firmware
git submodule update --init --recursive
git remote add upstream https://github.com/meshtastic/firmware.git
```

### 3. Place files

```powershell
# Board JSON — tells PlatformIO what chip/flash/PSRAM this board has
copy meshnode-s3.json  boards\

# Variant folder
mkdir variants\esp32s3\diy\meshnode_s3
copy variant.h        variants\esp32s3\diy\meshnode_s3\
copy pins_arduino.h   variants\esp32s3\diy\meshnode_s3\
copy platformio.ini   variants\esp32s3\diy\meshnode_s3\
copy README.md        variants\esp32s3\diy\meshnode_s3\
```

> ✅ The root `platformio.ini` already contains:
> ```
> extra_configs = variants/*/*.ini
>                 variants/*/*/platformio.ini
>                 variants/*/diy/*/platformio.ini
> ```
> Your variant is auto-discovered. No edits to root ini needed.

### 4. Build

**VS Code:**
1. Open firmware folder in VS Code
2. Wait for PlatformIO to initialise (first run downloads toolchain — ~5 min)
3. Bottom toolbar → environment picker → select `meshnode-s3`
4. Click **✓ Build**

**PowerShell:**
```powershell
pio run --environment meshnode-s3
```

### 5. Flash

**VS Code:** Click **→ Upload** in bottom toolbar

**PowerShell:**
```powershell
pio run --environment meshnode-s3 --target upload
```

If port not auto-detected (check Device Manager → Ports):
```powershell
pio run --environment meshnode-s3 --target upload --upload-port COM3
```

### 6. Serial monitor
```powershell
pio device monitor --environment meshnode-s3 --baud 115200
```

### 7. Your compiled .bin location
```
firmware\.pio\build\meshnode-s3\firmware.bin
```

---

## Pin Map

### SPI2 Shared Bus
| Signal | GPIO | Connected to |
|---|---|---|
| MOSI | 11 | LoRa + TFT |
| SCK | 12 | LoRa + TFT |
| MISO | 13 | LoRa + TFT |
| LoRa CS | 10 | RFM95W NSS |
| TFT CS | 15 | ILI9341 |

### LoRa RFM95W
| Signal | GPIO |
|---|---|
| RST | 9 |
| DIO0 | 14 |

### ILI9341 TFT
| Signal | GPIO |
|---|---|
| DC | 16 |
| RST | 3 |
| Backlight | 4 |

### I2C Bus (SCL=17, SDA=18)
| Device | Address |
|---|---|
| BME280 | 0x76 |
| PCF8563 | 0x51 |
| OLED (optional) | 0x3C |

### Peripherals
| Function | GPIO |
|---|---|
| WS2812 Data | 5 |
| Buzzer | 6 |
| Rotary A | 7 |
| Rotary B | 8 |
| Rotary SW | 38 |
| PIR | 39 |
| PCF8563 INT | 40 |
| Battery ADC | 1 |
| Boot button | 0 |

### Reserved — Do Not Use
| GPIO | Reason |
|---|---|
| 26–32, 35–37 | OPI PSRAM internal (N16R8) |
| 19, 20 | USB D−/D+ |
| 0, 45, 46 | Strapping pins |
| 43, 44 | UART0 debug |

---

## Updating from Upstream

```powershell
git fetch upstream
git merge upstream/master
# your variants\esp32s3\diy\meshnode_s3\ is untouched — zero conflicts
git push origin master
```

---

## Troubleshooting

**`UnknownBoard: Unknown board ID 'meshnode-s3'`**
The board JSON is missing. Make sure `meshnode-s3.json` is copied to the
`boards/` folder in the root of the firmware repo.

**`No section: 'esp32s3_base'`**
Your fork's root `platformio.ini` doesn't have the `extra_configs` line
that auto-discovers variant ini files. Check it contains:
```ini
extra_configs =
    variants/*/*.ini
    variants/*/*/platformio.ini
    variants/*/diy/*/platformio.ini
```
If missing, paste the `[env:meshnode-s3]` block directly at the bottom of
the root `platformio.ini` as a fallback.

**TFT white screen**
- Verify DC=16 wiring — most common mistake
- If colours wrong, add `-D TFT_RGB_ORDER=1` to build_flags

**LoRa not found**
- Check CS=10, RST=9, DIO0=14
- RFM95W must have DIO0 wired — not DIO1/DIO2

**PSRAM not detected**
- Board JSON must have `"memory_type": "qio_opi"`
- N16R8 will not work with `dio_opi` (that's for 2MB PSRAM variants)

**WS2812 not lighting**
- Power from 5V not 3.3V
- 300–500Ω resistor on data line near first LED


## Standalone Screen Test

A minimal, standalone TFT screen test project is located in `tft_test/`. It bypasses the entire Meshtastic firmware and initializes only the ILI9341 display under the exact same **N16R8 (Octal PSRAM / `qio_opi`)** constraints.

To compile and upload from PowerShell:
```powershell
cd variants\esp32s3\diy\meshnode_s3\tft_test
$env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8=1; pio run --target upload --upload-port COM19
```
It cycles screen colors (Red, Green, Blue) and prints debug messages to the Serial Monitor at `115200` baud.
