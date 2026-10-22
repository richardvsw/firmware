#include "configuration.h"

#ifdef _VARIANT_HIBY_R1

#include "HiByR1_LED.h"
#include <cstdio>

static void sysfs_write(const char *path, const char *val)
{
    FILE *f = fopen(path, "w");
    if (f) {
        fputs(val, f);
        fclose(f);
    }
}

void hiby_r1_led_init()
{
    sysfs_write("/sys/class/leds/red/trigger", "none");
    sysfs_write("/sys/class/leds/red/brightness", "0");
    sysfs_write("/sys/class/leds/blue/trigger", "breathing");
}

void hiby_r1_led_tx()
{
    sysfs_write("/sys/class/leds/red/brightness", "100");
}

void hiby_r1_led_rx()
{
    sysfs_write("/sys/class/leds/blue/brightness", "100");
}

void hiby_r1_led_set_charging(bool charging)
{
    if (charging) {
        sysfs_write("/sys/class/leds/red/trigger", "breathing");
    } else {
        sysfs_write("/sys/class/leds/red/trigger", "none");
        sysfs_write("/sys/class/leds/red/brightness", "0");
    }
}

void hiby_r1_led_restore()
{
    sysfs_write("/sys/class/leds/blue/trigger", "none");
    sysfs_write("/sys/class/leds/blue/brightness", "0");
    sysfs_write("/sys/class/leds/red/trigger", "breathing");
}

#endif
