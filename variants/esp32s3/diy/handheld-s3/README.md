# Handheld-S3 — Meshtastic Handheld Node

A portable Meshtastic node using ESP32-S3 + Rii i8 mini keyboard (via RP2040 CardKB emulator).

---

## Hardware

| Component | Part | Notes |
|---|---|---|
| MCU | ESP32-S3 N16R8 | 16MB flash, 8MB PSRAM |
| Radio | RFM95W | SPI, 915/868/433 MHz |
| Display | ILI9341 2.4" 320×240 | SPI, shared bus with RFM95W |
| Keyboard | Rii i8 mini + RP2040 Zero | USB HID → I2C CardKB emulator |
| GPS | GK9501S | UART, 9600 baud |
| Pressure/Temp | BMP280 | I2C @ 0x76 |

---

## Pin Assignments — ESP32-S3

### SPI (shared — RFM95W + ILI9341)
| Signal | GPIO |
|---|---|
| SCK | 12 |
| MOSI | 11 |
| MISO | 13 |

### RFM95W
| Signal | GPIO |
|---|---|
| CS | 10 |
| RESET | 9 |
| DIO0 (IRQ) | 14 |

### ILI9341
| Signal | GPIO |
|---|---|
| CS | 5 |
| DC | 6 |
| RST | 7 |
| Backlight | 8 |

### I2C (CardKB emulator + BMP280)
| Signal | GPIO |
|---|---|
| SDA | 2 |
| SCL | 1 |

### GPS (UART1)
| Signal | GPIO |
|---|---|
| RX | 17 |
| TX | 18 |

### Button
| Signal | GPIO |
|---|---|
| Boot/User button | 0 |

---

## Pin Assignments — RP2040 Zero

### USB Host (Rii i8 dongle)
| Signal | GPIO |
|---|---|
| D+ | 0 |
| D- | 1 (auto) |
| VCC | VBUS (5V) |

### I2C Slave (to ESP32-S3)
| Signal | GPIO |
|---|---|
| SDA | 4 |
| SCL | 5 |

Connect GND of RP2040 to GND of ESP32-S3.  
No external pull-ups needed for short wires (<15cm) — ESP32-S3 internal pull-ups sufficient.

---

## Firmware Structure

```
handheld-s3/
├── meshtastic_variant/
│   └── handheld-s3/
│       ├── variant.h            ← GPIO definitions, feature flags
│       ├── pins_arduino.h       ← Arduino SDA/SCL/SPI aliases
│       ├── lgfx_user_config.h   ← LovyanGFX ILI9341 config
│       └── platformio_env.ini   ← PlatformIO env block (merge into firmware's platformio.ini)
│
├── rp2040_firmware/
│   ├── hid_dump/                ← FLASH THIS FIRST for testing
│   │   ├── platformio.ini
│   │   └── src/main.cpp
│   │
│   └── cardkb_emulator/         ← Production firmware
│       ├── platformio.ini
│       └── src/main.cpp
│
└── README.md
```

---

## Setup Steps

### Step 1 — Test Rii i8 keycodes (hid_dump)

1. Open `rp2040_firmware/hid_dump/` in VSCode
2. Connect RP2040 Zero via USB to your PC
3. Flash: `pio run -e hid_dump -t upload`
4. Open serial monitor: `pio device monitor`
5. Connect Rii i8 dongle to GPIO0/1
6. Press every key — note all HID codes in output
7. Verify keycodes match the mapping in `cardkb_emulator/src/main.cpp`
8. Update `hidToCardKB()` if any codes differ

### Step 2 — Flash CardKB emulator

1. Open `rp2040_firmware/cardkb_emulator/` in VSCode
2. Flash: `pio run -e cardkb_emulator -t upload`
3. Wire RP2040 I2C (GPIO4=SDA, GPIO5=SCL, GND) to ESP32-S3

### Step 3 — Meshtastic variant

1. Copy `meshtastic_variant/handheld-s3/` folder to:
   ```
   <meshtastic_firmware>/variants/esp32s3/diy/handheld-s3/
   ```
2. Open `platformio_env.ini` and **merge** the `[env:handheld-s3]` block into the main Meshtastic `platformio.ini`
3. Build: `pio run -e handheld-s3`
4. Flash: `pio run -e handheld-s3 -t upload`

### Step 4 — Meshtastic config

In Meshtastic app or web UI:
- **Display → Flip Screen** — adjust for your mounting orientation
- **Canned Messages → Allow Input Source** → set to `CARDKB`
- **Position → GPS Mode** → `ENABLED`
- **Telemetry → Environment** → enable BMP280

---

## Key Mapping

### Normal keys
Standard QWERTY, numbers, Enter, Backspace, Tab, Esc, Space — all direct ASCII.

### Modifier layers
| Rii i8 key | Function |
|---|---|
| Shift | Uppercase / number symbols (!@#$...) |
| Caps Lock | Toggle caps (tracked in RP2040 firmware) |
| Alt / AltGr | CardKB sym layer (;:`+−_=?{}[]\/\|~'") |
| Win | CardKB fn layer (custom codes 128–175) |

### Arrow & navigation
| Rii i8 key | Output |
|---|---|
| ← → ↑ ↓ | CardKB 180/183/181/182 |
| Home | 152 (Fn+Left) |
| PgUp | 153 (Fn+Up) |
| PgDn | 164 (Fn+Down) |
| End | 165 (Fn+Right) |

### F keys → CardKB Fn layer
| Key | Value |
|---|---|
| F1–F12 | 129–140 |

---

## Known Limitations

- Rii i8 media keys (volume, play/pause) are ignored — only keyboard HID reports are processed
- Touchpad mouse events are ignored
- Key repeat: Rii i8 dongle handles repeat internally; firmware forwards each unique report once
- `pendingKey` is a single byte — rapid typing may drop keys if ESP32-S3 polls slowly. Meshtastic polls CardKB every ~100ms which is fine for human typing speed

---

## Dependencies

### RP2040 firmware
- [arduino-pico](https://github.com/earlephilhower/arduino-pico) (Earle Philhower)
- [Adafruit TinyUSB](https://github.com/adafruit/Adafruit_TinyUSB_Arduino)
- [Pico-PIO-USB](https://github.com/sekigon-gonnoc/Pico-PIO-USB)

### Meshtastic variant
- [Meshtastic firmware](https://github.com/meshtastic/firmware) develop branch
- [LovyanGFX](https://github.com/lovyan03/LovyanGFX)
