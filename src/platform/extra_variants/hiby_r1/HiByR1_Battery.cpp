#include "configuration.h"

#ifdef _VARIANT_HIBY_R1

#include "HiByR1_Battery.h"
#include <fcntl.h>
#include <unistd.h>
#include <cstdlib>
#include <cctype>

HiByR1_Battery hibyR1Battery;

HiByR1_Battery::HiByR1_Battery()
{
}

static int read_int_sysfs(const char *path)
{
    int fd = open(path, O_RDONLY);
    if (fd < 0) return -1;
    char buf[32];
    ssize_t n = read(fd, buf, sizeof(buf) - 1);
    close(fd);
    if (n <= 0) return -1;
    buf[n] = '\0';
    return atoi(buf);
}

int HiByR1_Battery::getBatteryPercent()
{
    int cap = read_int_sysfs("/sys/class/power_supply/battery/capacity");
    if (cap < 0)
        cap = read_int_sysfs("/sys/class/power_supply/axp_battery/capacity");
    if (cap >= 0 && cap <= 100)
        return cap;
    return -1;
}

uint16_t HiByR1_Battery::getBattVoltage()
{
    int uv = read_int_sysfs("/sys/class/power_supply/battery/voltage_now");
    if (uv < 0)
        uv = read_int_sysfs("/sys/class/power_supply/axp_battery/voltage_now");
    if (uv > 100000)
        return static_cast<uint16_t>(uv / 1000);
    return 3800; // nominal 3.8V fallback
}

bool HiByR1_Battery::isBatteryConnect()
{
    return getBatteryPercent() >= 0;
}

bool HiByR1_Battery::isVbusIn()
{
    int online = read_int_sysfs("/sys/class/power_supply/usb/online");
    if (online < 0)
        online = read_int_sysfs("/sys/class/power_supply/ac/online");
    return online > 0;
}

bool HiByR1_Battery::isCharging()
{
    int fd = open("/sys/class/power_supply/battery/status", O_RDONLY);
    if (fd >= 0) {
        char buf[32];
        ssize_t n = read(fd, buf, sizeof(buf) - 1);
        close(fd);
        if (n > 0) {
            buf[n] = '\0';
            // Match 'Charging' or 'c' / 'C'
            if (buf[0] == 'C' || buf[0] == 'c')
                return true;
        }
    }
    return isVbusIn();
}

#endif
