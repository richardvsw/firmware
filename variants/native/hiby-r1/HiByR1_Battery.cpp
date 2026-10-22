#include "HiByR1_Battery.h"
#include <cstdio>
#include <cstring>
#include <dirent.h>
#include <unistd.h>

HiByR1_Battery hibyR1Battery;

HiByR1_Battery::HiByR1_Battery()
{
}

int HiByR1_Battery::getBatteryPercent()
{
    const char *paths[] = {
        "/sys/class/power_supply/battery/capacity",
        "/sys/class/power_supply/cw2015/capacity",
        "/sys/class/power_supply/axp2101-battery/capacity",
        nullptr
    };

    for (int i = 0; paths[i]; i++) {
        FILE *f = fopen(paths[i], "r");
        if (f) {
            int cap = -1;
            if (fscanf(f, "%d", &cap) == 1 && cap >= 0 && cap <= 100) {
                fclose(f);
                return cap;
            }
            fclose(f);
        }
    }

    // Generic fallback: iterate /sys/class/power_supply/
    DIR *dir = opendir("/sys/class/power_supply");
    if (dir) {
        struct dirent *ent;
        while ((ent = readdir(dir)) != nullptr) {
            if (ent->d_name[0] == '.')
                continue;
            char path[256];
            snprintf(path, sizeof(path), "/sys/class/power_supply/%s/capacity", ent->d_name);
            FILE *f = fopen(path, "r");
            if (f) {
                int cap = -1;
                if (fscanf(f, "%d", &cap) == 1 && cap >= 0 && cap <= 100) {
                    fclose(f);
                    closedir(dir);
                    return cap;
                }
                fclose(f);
            }
        }
        closedir(dir);
    }

    return -1;
}

uint16_t HiByR1_Battery::getBattVoltage()
{
    const char *paths[] = {
        "/sys/class/power_supply/battery/voltage_now",
        "/sys/class/power_supply/cw2015/voltage_now",
        "/sys/class/power_supply/axp2101-battery/voltage_now",
        nullptr
    };

    for (int i = 0; paths[i]; i++) {
        FILE *f = fopen(paths[i], "r");
        if (f) {
            int uv = 0;
            if (fscanf(f, "%d", &uv) == 1 && uv > 100000) {
                fclose(f);
                return static_cast<uint16_t>(uv / 1000);
            }
            fclose(f);
        }
    }

    // Generic fallback: iterate /sys/class/power_supply/
    DIR *dir = opendir("/sys/class/power_supply");
    if (dir) {
        struct dirent *ent;
        while ((ent = readdir(dir)) != nullptr) {
            if (ent->d_name[0] == '.')
                continue;
            char path[256];
            snprintf(path, sizeof(path), "/sys/class/power_supply/%s/voltage_now", ent->d_name);
            FILE *f = fopen(path, "r");
            if (f) {
                int uv = 0;
                if (fscanf(f, "%d", &uv) == 1 && uv > 100000) {
                    fclose(f);
                    closedir(dir);
                    return static_cast<uint16_t>(uv / 1000);
                }
                fclose(f);
            }
        }
        closedir(dir);
    }

    return 3800; // nominal 3.8V fallback
}

bool HiByR1_Battery::isBatteryConnect()
{
    return getBatteryPercent() >= 0;
}

bool HiByR1_Battery::isVbusIn()
{
    const char *paths[] = {
        "/sys/class/power_supply/usb/online",
        "/sys/class/power_supply/mp2731-charger/online",
        "/sys/class/power_supply/axp2101-usb/online",
        nullptr
    };

    for (int i = 0; paths[i]; i++) {
        FILE *f = fopen(paths[i], "r");
        if (f) {
            int online = 0;
            if (fscanf(f, "%d", &online) == 1 && online > 0) {
                fclose(f);
                return true;
            }
            fclose(f);
        }
    }

    return false;
}

bool HiByR1_Battery::isCharging()
{
    const char *paths[] = {
        "/sys/class/power_supply/battery/status",
        "/sys/class/power_supply/cw2015/status",
        "/sys/class/power_supply/axp2101-battery/status",
        nullptr
    };

    for (int i = 0; paths[i]; i++) {
        FILE *f = fopen(paths[i], "r");
        if (f) {
            char st[32] = {0};
            if (fscanf(f, "%31s", st) == 1) {
                fclose(f);
                if (strcasecmp(st, "Charging") == 0)
                    return true;
            }
            fclose(f);
        }
    }

    return isVbusIn();
}
