// ─── cardkb_emulator/src/main.cpp ────────────────────────────────────────────
// RP2040 Zero — Rii i8 USB HID → CardKB I2C Emulator
#ifndef ARDUINO_ARCH_ESP32  // skip when compiled by ESP32-S3 toolchain
//
// Core0: I2C slave @ 0x5F (CardKB protocol)
// Core1: USB Host (pio_usb) reading Rii i8 dongle
//
// Wiring — USB Host:
//   Rii dongle D+  → GPIO0
//   Rii dongle D-  → GPIO1  (auto, adjacent to D+)
//   Rii dongle VCC → VBUS (5V)
//   Rii dongle GND → GND
//
// Wiring — I2C Slave (to ESP32-S3 Meshtastic):
//   GPIO4 → SDA
//   GPIO5 → SCL
//   GND   → GND  (common ground with ESP32-S3)
//   (pull-ups optional — ESP32-S3 internal pull-ups sufficient for short wires)
// ─────────────────────────────────────────────────────────────────────────────

#include <Arduino.h>
#include <Wire.h>
#include "Adafruit_TinyUSB.h"
#include "pio_usb.h"

// ─── I2C config ───────────────────────────────────────────────────────────────
#define I2C_SDA_PIN     4
#define I2C_SCL_PIN     5
#define CARDKB_I2C_ADDR 0x5F

// ─── USB Host ─────────────────────────────────────────────────────────────────
Adafruit_USBH_Host USBHost;

// ─── Shared state (core0 reads, core1 writes) ────────────────────────────────
volatile uint8_t pendingKey = 0x00;
volatile bool    capsLock   = false;

// ─── CardKB keymap (from official M5Stack firmware source) ───────────────────
// Columns: nor, shift, long_shift, sym, long_sym, fn, long_fn
// Index 0 = key scan 1 (esc), index 47 = key scan 48 (space)
// We don't use this table directly — we compute output in hidToCardKB()
// It's here for reference / future Fn-layer extension

// ─── HID keycode → CardKB byte ───────────────────────────────────────────────
// mod bits: 0x01=LCtrl 0x02=LShift 0x04=LAlt 0x08=LWin
//           0x10=RCtrl 0x20=RShift 0x40=RAltGr 0x80=RWin
//
// Mapping:
//   Shift / CapsLock → uppercase / symbols on numbers
//   Alt / AltGr      → CardKB sym layer
//   Win              → CardKB fn layer
uint8_t hidToCardKB(uint8_t hid, uint8_t mod) {
    bool shift = ((mod & 0x22) != 0) ^ capsLock;  // XOR with capslock for letters
    bool sym   = (mod & 0x44) != 0;   // LAlt or RAltGr = sym layer
    bool fn    = (mod & 0x88) != 0;   // LWin or RWin   = fn layer

    // For number keys, CapsLock doesn't affect shift symbols
    bool shiftNum = (mod & 0x22) != 0;

    switch (hid) {
        // ── Letters (a-z, HID 0x04-0x1D) ─────────────────────────────────────
        // sym layer matches CardKB source exactly
        case 0x04: return fn ? 154 : sym ? ';'  : shift ? 'A' : 'a';
        case 0x05: return fn ? 170 : sym ? 0    : shift ? 'B' : 'b';
        case 0x06: return fn ? 168 : sym ? 0    : shift ? 'C' : 'c';
        case 0x07: return fn ? 156 : sym ? '`'  : shift ? 'D' : 'd';
        case 0x08: return fn ? 143 : sym ? '['  : shift ? 'E' : 'e';
        case 0x09: return fn ? 157 : sym ? '+'  : shift ? 'F' : 'f';
        case 0x0A: return fn ? 158 : sym ? '-'  : shift ? 'G' : 'g';
        case 0x0B: return fn ? 159 : sym ? '_'  : shift ? 'H' : 'h';
        case 0x0C: return fn ? 148 : sym ? '~'  : shift ? 'I' : 'i';
        case 0x0D: return fn ? 160 : sym ? '='  : shift ? 'J' : 'j';
        case 0x0E: return fn ? 161 : sym ? '?'  : shift ? 'K' : 'k';
        case 0x0F: return fn ? 162 : sym ? 0    : shift ? 'L' : 'l';
        case 0x10: return fn ? 172 : sym ? 0    : shift ? 'M' : 'm';
        case 0x11: return fn ? 171 : sym ? 0    : shift ? 'N' : 'n';
        case 0x12: return fn ? 149 : sym ? '\'' : shift ? 'O' : 'o';
        case 0x13: return fn ? 150 : sym ? '"'  : shift ? 'P' : 'p';
        case 0x14: return fn ? 141 : sym ? '{'  : shift ? 'Q' : 'q';
        case 0x15: return fn ? 144 : sym ? ']'  : shift ? 'R' : 'r';
        case 0x16: return fn ? 155 : sym ? ':'  : shift ? 'S' : 's';
        case 0x17: return fn ? 145 : sym ? '/'  : shift ? 'T' : 't';
        case 0x18: return fn ? 147 : sym ? '|'  : shift ? 'U' : 'u';
        case 0x19: return fn ? 169 : sym ? 0    : shift ? 'V' : 'v';
        case 0x1A: return fn ? 142 : sym ? '}'  : shift ? 'W' : 'w';
        case 0x1B: return fn ? 167 : sym ? 0    : shift ? 'X' : 'x';
        case 0x1C: return fn ? 146 : sym ? '\\' : shift ? 'Y' : 'y';
        case 0x1D: return fn ? 166 : sym ? 0    : shift ? 'Z' : 'z';

        // ── Numbers ───────────────────────────────────────────────────────────
        case 0x1E: return shiftNum ? '!' : '1';
        case 0x1F: return shiftNum ? '@' : '2';
        case 0x20: return shiftNum ? '#' : '3';
        case 0x21: return shiftNum ? '$' : '4';
        case 0x22: return shiftNum ? '%' : '5';
        case 0x23: return shiftNum ? '^' : '6';
        case 0x24: return shiftNum ? '&' : '7';
        case 0x25: return shiftNum ? '*' : '8';
        case 0x26: return shiftNum ? '(' : '9';
        case 0x27: return shiftNum ? ')' : '0';

        // ── Special keys ──────────────────────────────────────────────────────
        case 0x28: return 13;    // Enter
        case 0x29: return 27;    // Esc
        case 0x2A: return shiftNum ? 127 : 8;  // Backspace / Shift+BS=DEL
        case 0x4C: return 127;   // Delete key
        case 0x2B: return 9;     // Tab
        case 0x2C: return ' ';   // Space

        // ── Punctuation ───────────────────────────────────────────────────────
        case 0x2D: return shiftNum ? '_' : '-';
        case 0x2E: return shiftNum ? '+' : '=';
        case 0x2F: return shiftNum ? '{' : '[';
        case 0x30: return shiftNum ? '}' : ']';
        case 0x31: return shiftNum ? '|' : '\\';
        case 0x33: return shiftNum ? ':' : ';';
        case 0x34: return shiftNum ? '"' : '\'';
        case 0x35: return shiftNum ? '~' : '`';
        case 0x36: return shiftNum ? '<' : ',';
        case 0x37: return shiftNum ? '>' : '.';
        case 0x38: return shiftNum ? '?' : '/';

        // ── Arrow keys ────────────────────────────────────────────────────────
        case 0x4F: return fn ? 165 : 183;  // Right / Fn+Right
        case 0x50: return fn ? 152 : 180;  // Left  / Fn+Left
        case 0x51: return fn ? 164 : 182;  // Down  / Fn+Down
        case 0x52: return fn ? 153 : 181;  // Up    / Fn+Up

        // ── F keys → CardKB Fn layer values (129-140) ─────────────────────────
        case 0x3A: return 129;   // F1
        case 0x3B: return 130;   // F2
        case 0x3C: return 131;   // F3
        case 0x3D: return 132;   // F4
        case 0x3E: return 133;   // F5
        case 0x3F: return 134;   // F6
        case 0x40: return 135;   // F7
        case 0x41: return 136;   // F8
        case 0x42: return 137;   // F9
        case 0x43: return 138;   // F10
        case 0x44: return 139;   // F11
        case 0x45: return 140;   // F12

        // ── Nav keys → CardKB Fn+arrow equivalents ───────────────────────────
        case 0x4A: return 152;   // Home  → Fn+Left
        case 0x4B: return 153;   // PgUp  → Fn+Up
        case 0x4E: return 164;   // PgDn  → Fn+Down
        case 0x4D: return 165;   // End   → Fn+Right

        // ── Caps Lock (sentinel — handled in caller) ──────────────────────────
        case 0x39: return 0xFF;  // special: toggle capsLock flag

        // ── Ignored keys ──────────────────────────────────────────────────────
        // Ctrl, Win, Alt (used as modifiers above, not standalone keys)
        // Media keys (handled separately if needed)
        default: return 0x00;
    }
}

// ─── I2C slave: respond to ESP32-S3 master reads ──────────────────────────────
// Called from core0 Wire ISR
void onI2CRequest() {
    // Always write 1 byte — 0x00 means no key pending
    // (real CardKB writes nothing when idle, but that causes master hangs)
    Wire.write((uint8_t)pendingKey);
    pendingKey = 0x00;
}

// ─── Core0: I2C slave init ───────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);

    Wire.setSDA(I2C_SDA_PIN);
    Wire.setSCL(I2C_SCL_PIN);
    Wire.begin(CARDKB_I2C_ADDR);   // slave mode
    Wire.onRequest(onI2CRequest);

    Serial.println("CardKB emulator ready @ 0x5F");
    Serial.println("SDA=GPIO4  SCL=GPIO5");
}

void loop() {
    // Core0 is idle — I2C handled via interrupt/callback
    delay(1);
}

// ─── Core1: USB Host init ────────────────────────────────────────────────────
void setup1() {
    pio_usb_configuration_t pio_cfg = PIO_USB_DEFAULT_CONFIG;
    pio_cfg.pin_dp = 0;   // D+ on GPIO0, D- on GPIO1
    tuh_configure(1, TUH_CFGID_RPI_PIO_USB_CONFIGURATION, &pio_cfg);
    USBHost.begin(1);
}

void loop1() {
    USBHost.task();
}

// ─── USB HID mount ────────────────────────────────────────────────────────────
void tuh_hid_mount_cb(uint8_t dev_addr, uint8_t instance,
                       uint8_t const* desc_report, uint16_t desc_len) {
    (void)desc_report; (void)desc_len;
    tuh_hid_receive_report(dev_addr, instance);
}

void tuh_hid_umount_cb(uint8_t dev_addr, uint8_t instance) {
    (void)dev_addr; (void)instance;
}

// ─── USB HID report received ─────────────────────────────────────────────────
void tuh_hid_report_received_cb(uint8_t dev_addr, uint8_t instance,
                                  uint8_t const* report, uint16_t len) {
    uint8_t proto = tuh_hid_interface_protocol(dev_addr, instance);

    if (proto == HID_ITF_PROTOCOL_KEYBOARD && len >= 3) {
        uint8_t mod     = report[0];
        uint8_t keycode = report[2];

        // Handle Caps Lock toggle
        if (keycode == 0x39) {
            capsLock = !capsLock;
        }
        // Ignore modifier-only events and key-up
        else if (keycode != 0x00) {
            uint8_t ckbyte = hidToCardKB(keycode, mod);
            if (ckbyte != 0x00 && ckbyte != 0xFF) {
                // Atomic write — pendingKey is volatile, single byte
                pendingKey = ckbyte;
            }
        }
    }
    // Mouse and consumer control reports: ignored for CardKB emulation

    tuh_hid_receive_report(dev_addr, instance);
}
#endif // ARDUINO_ARCH_ESP32
