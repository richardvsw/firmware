// ─── hid_dump/src/main.cpp ────────────────────────────────────────────────────
// Dumps all USB HID reports from Rii i8 dongle to USB Serial (CDC)
#ifndef ARDUINO_ARCH_ESP32  // skip when compiled by ESP32-S3 toolchain
// Use this FIRST to verify exact keycodes from your specific unit.
//
// Wiring:
//   Rii dongle D+  → GPIO0
//   Rii dongle D-  → GPIO1
//   Rii dongle VCC → VBUS (5V)
//   Rii dongle GND → GND
//
// Open serial monitor at 115200. Press every key and note the output.
// ─────────────────────────────────────────────────────────────────────────────

#include <Arduino.h>
#include "Adafruit_TinyUSB.h"
#include "pio_usb.h"

// USB Host instance — runs on core1
Adafruit_USBH_Host USBHost;

// ─── Core0: setup & loop ─────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    while (!Serial && millis() < 3000) delay(10);

    Serial.println("========================================");
    Serial.println("  Rii i8 HID Dump  |  RP2040 Zero");
    Serial.println("  D+ → GPIO0   D- → GPIO1");
    Serial.println("========================================");
}

void loop() {
    // Nothing — callbacks handle everything
    delay(1);
}

// ─── Core1: USB host task ─────────────────────────────────────────────────────
void setup1() {
    // pio_usb on GPIO0 (D+), GPIO1 (D-) auto
    pio_usb_configuration_t pio_cfg = PIO_USB_DEFAULT_CONFIG;
    pio_cfg.pin_dp = 0;
    tuh_configure(1, TUH_CFGID_RPI_PIO_USB_CONFIGURATION, &pio_cfg);
    USBHost.begin(1);
}

void loop1() {
    USBHost.task();
}

// ─── HID mount callback ───────────────────────────────────────────────────────
void tuh_hid_mount_cb(uint8_t dev_addr, uint8_t instance,
                       uint8_t const* desc_report, uint16_t desc_len) {
    (void)desc_report; (void)desc_len;
    uint8_t proto = tuh_hid_interface_protocol(dev_addr, instance);
    Serial.printf("[MOUNT] dev=%u inst=%u proto=%u", dev_addr, instance, proto);
    switch (proto) {
        case HID_ITF_PROTOCOL_KEYBOARD: Serial.println(" (KEYBOARD)"); break;
        case HID_ITF_PROTOCOL_MOUSE:    Serial.println(" (MOUSE)");    break;
        default:                         Serial.println(" (OTHER)");    break;
    }
    tuh_hid_receive_report(dev_addr, instance);
}

// ─── HID unmount callback ────────────────────────────────────────────────────
void tuh_hid_umount_cb(uint8_t dev_addr, uint8_t instance) {
    Serial.printf("[UMOUNT] dev=%u inst=%u\n", dev_addr, instance);
}

// ─── HID report callback ─────────────────────────────────────────────────────
void tuh_hid_report_received_cb(uint8_t dev_addr, uint8_t instance,
                                  uint8_t const* report, uint16_t len) {
    uint8_t proto = tuh_hid_interface_protocol(dev_addr, instance);

    if (proto == HID_ITF_PROTOCOL_KEYBOARD) {
        if (len < 3) { tuh_hid_receive_report(dev_addr, instance); return; }

        uint8_t mod = report[0];
        // Skip pure key-up events
        bool any_key = false;
        for (int i = 2; i < (int)len; i++) { if (report[i]) { any_key = true; break; } }
        if (!any_key && mod == 0) { tuh_hid_receive_report(dev_addr, instance); return; }

        Serial.printf("KBD mod=0x%02X  keys=[", mod);
        for (int i = 2; i < (int)len; i++) {
            if (report[i] == 0) break;
            Serial.printf("0x%02X ", report[i]);
        }
        Serial.print("]  flags=(");
        if (mod & 0x01) Serial.print("LCtrl ");
        if (mod & 0x02) Serial.print("LShift ");
        if (mod & 0x04) Serial.print("LAlt ");
        if (mod & 0x08) Serial.print("LWin ");
        if (mod & 0x10) Serial.print("RCtrl ");
        if (mod & 0x20) Serial.print("RShift ");
        if (mod & 0x40) Serial.print("RAltGr ");
        if (mod & 0x80) Serial.print("RWin ");
        Serial.println(")");

    } else if (proto == HID_ITF_PROTOCOL_MOUSE) {
        if (len < 3) { tuh_hid_receive_report(dev_addr, instance); return; }
        uint8_t btn = report[0];
        int8_t  dx  = (int8_t)report[1];
        int8_t  dy  = (int8_t)report[2];
        if (btn || dx || dy) {
            Serial.printf("MOUSE btn=0x%02X dx=%d dy=%d\n", btn, dx, dy);
        }

    } else {
        // Consumer control (media keys land here)
        bool any = false;
        for (int i = 0; i < (int)len; i++) { if (report[i]) { any = true; break; } }
        if (any) {
            Serial.printf("HID[proto=%u] [", proto);
            for (int i = 0; i < (int)len; i++) Serial.printf("0x%02X ", report[i]);
            Serial.println("]");
        }
    }

    tuh_hid_receive_report(dev_addr, instance);
}
#endif // ARDUINO_ARCH_ESP32
