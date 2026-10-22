#pragma once

// HiBy R1 Hardware Target Definitions for Meshtastic MUI
#define ARCH_PORTDUINO 1
#define PORTDUINO_LINUX_HARDWARE 1
#define PORTDUINO_BUILDROOT 1

// Display & Touchscreen (LG35583 LCD + CST8xx Capacitive Touch)
#define HAS_SCREEN 1
#define USE_TFTDISPLAY 1
#define HAS_TFT 1
#define TFT_WIDTH 480
#define TFT_HEIGHT 800

// Ingenic X1600 SoC specifics
#define MAX_RX_TOPHONE portduino_config.maxtophone
#define MAX_NUM_NODES portduino_config.MaxNodes

#define _VARIANT_HIBY_R1 1

// Battery & Power (CW2015 + AXP2101 PMIC via sysfs)
#define HAS_BATTERY 1

// Side PWM LEDs (PC01 Red, PC02 Blue via sysfs)
#define HAS_STATUS_LED 1
#define LED_RED_SYSFS "/sys/class/leds/red"
#define LED_BLUE_SYSFS "/sys/class/leds/blue"
