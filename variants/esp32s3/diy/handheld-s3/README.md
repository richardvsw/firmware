# Handheld-S3 — Meshtastic Handheld Node

A portable, self-contained Meshtastic node built around the ESP32-S3 N16R8 with a 320×240 touchscreen,
LoRa radio, GPS, SD card for offline maps, and a Rii i8 mini wireless keyboard (via RP2040 CardKB emulator).

---

## Hardware BOM

| Component | Part | Notes |
|---|---|---|
| MCU | ESP32-S3 N16R8 | 16 MB flash, 8 MB OPI PSRAM |
| Radio | RFM95W | SPI, 915 / 868 / 433 MHz |
| Display | ILI9341 2.4" 320×240 | SPI, shared bus |
| Touch | XPT2046 | SPI, shared bus, polling mode |
| SD Card | SPI microSD module | SPI, shared bus |
| Keyboard | Rii i8 mini + RP2040 Zero | USB HID → I2C CardKB emulator |
| GPS | GK9501S | UART, 9600 baud |
| Env sensor | BMP280 | I2C @ 0x76 |

---

## Pin Assignments — ESP32-S3

### SPI bus (shared — RFM95W, ILI9341, XPT2046, SD)

| Signal | GPIO |
|---|---|
| SCK | 12 |
| MOSI | 11 |
| MISO | 13 |

### RFM95W (LoRa)

| Signal | GPIO |
|---|---|
| CS | 10 |
| RESET | 9 |
| DIO0 (IRQ) | 14 |

### ILI9341 (Display)

| Signal | GPIO |
|---|---|
| CS | 15 |
| DC | 16 |
| RST | 3 |
| Backlight | 4 |

### XPT2046 (Touch)

| Signal | GPIO |
|---|---|
| CS | 5 |
| INT (polling) | 6 |

### SD Card

| Signal | GPIO |
|---|---|
| CS | 7 |

### I2C (CardKB + BMP280)

| Signal | GPIO |
|---|---|
| SDA | 2 |
| SCL | 1 |

### GPS (UART1)

| Signal | GPIO |
|---|---|
| RX | 42 |
| TX | 41 |

### Button

| Signal | GPIO |
|---|---|
| Boot / User | 0 |

---

## Pin Assignments — RP2040 Zero

### USB Host (Rii i8 dongle)

| Signal | GPIO |
|---|---|
| D+ | 0 |
| D− | 1 (auto) |
| VCC | VBUS (5 V) |

### I2C Slave (to ESP32-S3)

| Signal | GPIO |
|---|---|
| SDA | 4 |
| SCL | 5 |
| GND | GND |

No external pull-ups needed for wires shorter than 15 cm — ESP32-S3 internal pull-ups are sufficient.

---

## Variant Folder Structure

```
variants/esp32s3/diy/handheld-s3/
├── variant.h                  ← GPIO definitions, feature flags
├── variant.cpp                ← WDT unsubscribe fix (IDLE0 released after UI init)
├── pins_arduino.h             ← Arduino SDA/SCL/SPI aliases
├── lgfx_user_config.h         ← LovyanGFX ILI9341 + XPT2046 config
├── platformio.ini             ← PlatformIO [env:handheld-s3] block
├── PacketAPI.cpp              ← Patched copy: skips BT programming-mode when
│                                  DISABLE_MUI_PROGRAMMING_MODE is defined
├── rp2040_firmware/
│   ├── hid_dump/              ← Flash first to verify Rii i8 HID keycodes
│   │   ├── platformio.ini
│   │   └── src/main.cpp
│   └── cardkb_emulator/       ← Production RP2040 firmware
│       ├── platformio.ini
│       └── src/main.cpp
└── README.md
```

> **No core Meshtastic files are patched.**
> `PacketAPI.cpp` is included from this folder via `build_src_filter`; the original is excluded.

---

## Build & Flash (ESP32-S3)

### Prerequisites

- [PlatformIO](https://platformio.org/) (CLI or VSCode extension)
- This repo cloned: `git clone --recurse-submodules https://github.com/meshtastic/firmware`

### Add the environment

Merge `[env:handheld-s3]` from `platformio.ini` into the root `platformio.ini` of the Meshtastic
firmware repo (or use this file standalone if PlatformIO supports multi-file configs in your setup).

### Build & upload

```bash
pio run -e handheld-s3 -t upload
```

---

## SD Card — Offline Maps

Format SD card as FAT32. Extract OSM tiles so the path matches:

```
/maps/openstreetmaps/{zoom}/{x}/{y}.png
```

In the Meshtastic UI, go to **Map → Settings** and set the tile style to `openstreetmaps`.

Recommended zoom levels to pre-cache: 10–15.

---

## Bluetooth

Bluetooth PIN is fixed at **123456** (set via `USERPREFS_FIXED_BLUETOOTH=123456`).  
The device does not display a random PIN — pair with 123456 from the Meshtastic app.

---

## WiFi

Configure via the Meshtastic app, web UI, or CLI after connecting over serial or BT:

```bash
python -m meshtastic --port COM21 \
  --set network.wifi_enabled true \
  --set network.wifi_ssid "YourSSID" \
  --set network.wifi_psk "YourPassword"
```

---

## RP2040 Keyboard Emulator

### Step 1 — Verify keycodes (hid_dump)

1. Open `rp2040_firmware/hid_dump/` in VSCode with PlatformIO
2. Flash to RP2040 Zero: `pio run -e hid_dump -t upload`
3. Connect Rii i8 USB dongle to GPIO 0/1
4. Open serial monitor and press every key — note all HID codes
5. Compare with the mapping in `cardkb_emulator/src/main.cpp`; update `hidToCardKB()` if any differ

### Step 2 — Flash CardKB emulator

```bash
cd rp2040_firmware/cardkb_emulator
pio run -e cardkb_emulator -t upload
```

Wire RP2040 → ESP32-S3: GPIO4 (SDA), GPIO5 (SCL), GND.

### Key mapping

| Layer | Trigger | Notes |
|---|---|---|
| Normal | — | A–Z, 0–9, Enter, Backspace, Tab, Esc, Space |
| Shift | Shift held | Uppercase, symbols !@#$%^&*()_+ etc. |
| Sym | Alt held | CardKB sym layer: ; : \` + − _ = ? { } [ ] \ / \| ~ ' " |
| Fn | Win held | CardKB fn layer codes 128–175 |
| Caps | Caps Lock toggle | Tracked in RP2040 firmware |
| Arrows | ←→↑↓ | CardKB 180/183/181/182 |
| F1–F12 | F1–F12 keys | CardKB 129–140 |
| Home / End / PgUp / PgDn | Navigation keys | Fn layer codes 152/165/153/164 |

---

## Meshtastic App Config (after first boot)

| Setting | Value |
|---|---|
| Bluetooth → Pairing Mode | Fixed PIN → **123456** |
| Canned Messages → Input Source | `CARDKB` |
| Position → GPS Mode | `ENABLED` |
| Telemetry → Environment | Enable (BMP280) |
| Map → Tile Style | `openstreetmaps` (if using SD map tiles) |

---

## Known Limitations

- Rii i8 media keys (volume, play/pause) and touchpad mouse events are ignored
- `pendingKey` is a single byte — very rapid key presses may drop characters if polling is slow (Meshtastic polls every ~100 ms, fine for normal typing)
- Touch is in polling mode (no INT line used); slight latency compared to interrupt-driven touch

---

## Dependencies

### RP2040 firmware
- [arduino-pico](https://github.com/earlephilhower/arduino-pico) — Earle Philhower
- [Adafruit TinyUSB](https://github.com/adafruit/Adafruit_TinyUSB_Arduino)
- [Pico-PIO-USB](https://github.com/sekigon-gonnoc/Pico-PIO-USB)

### ESP32-S3 variant
- [Meshtastic firmware](https://github.com/meshtastic/firmware) — develop branch
- [LovyanGFX](https://github.com/lovyan03/LovyanGFX) 1.2.21
