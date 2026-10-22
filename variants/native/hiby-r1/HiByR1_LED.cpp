#include "HiByR1_LED.h"
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <mutex>
#include <thread>
#include <unistd.h>

static void sysfs_write(const char *path, const char *val)
{
    FILE *f = fopen(path, "w");
    if (f) {
        fputs(val, f);
        fclose(f);
    }
}

static std::atomic<bool> pulse_red_req{false};
static std::atomic<bool> pulse_blue_req{false};
static std::atomic<bool> led_running{false};
static std::atomic<bool> is_charging{false};
static std::thread led_thread;
static std::mutex led_mtx;
static std::condition_variable led_cv;

static void led_worker()
{
    while (led_running) {
        std::unique_lock<std::mutex> lock(led_mtx);
        led_cv.wait_for(lock, std::chrono::milliseconds(50), [] {
            return pulse_red_req.load() || pulse_blue_req.load() || !led_running.load();
        });

        if (!led_running)
            break;

        if (pulse_red_req.exchange(false)) {
            sysfs_write("/sys/class/leds/red/trigger", "none");
            sysfs_write("/sys/class/leds/red/brightness", "100");
            std::this_thread::sleep_for(std::chrono::milliseconds(80));
            if (is_charging.load()) {
                sysfs_write("/sys/class/leds/red/trigger", "breathing");
            } else {
                sysfs_write("/sys/class/leds/red/brightness", "0");
            }
        }

        if (pulse_blue_req.exchange(false)) {
            sysfs_write("/sys/class/leds/blue/trigger", "none");
            sysfs_write("/sys/class/leds/blue/brightness", "100");
            std::this_thread::sleep_for(std::chrono::milliseconds(80));
            // Return to gentle breathing blue state
            sysfs_write("/sys/class/leds/blue/trigger", "breathing");
        }
    }
}

void hiby_r1_led_init()
{
    // Meshtastic active state:
    // Red: off (unless charging)
    // Blue: breathing indicator
    sysfs_write("/sys/class/leds/red/trigger", "none");
    sysfs_write("/sys/class/leds/red/brightness", "0");

    sysfs_write("/sys/class/leds/blue/trigger", "breathing");

    if (!led_running.exchange(true)) {
        led_thread = std::thread(led_worker);
    }
}

void hiby_r1_led_tx()
{
    pulse_red_req = true;
    led_cv.notify_one();
}

void hiby_r1_led_rx()
{
    pulse_blue_req = true;
    led_cv.notify_one();
}

void hiby_r1_led_set_charging(bool charging)
{
    is_charging = charging;
    if (charging) {
        sysfs_write("/sys/class/leds/red/trigger", "breathing");
    } else {
        sysfs_write("/sys/class/leds/red/trigger", "none");
        sysfs_write("/sys/class/leds/red/brightness", "0");
    }
}

void hiby_r1_led_restore()
{
    led_running = false;
    led_cv.notify_all();
    if (led_thread.joinable()) {
        led_thread.join();
    }

    // SonixOS default: Red breathing, Blue off
    sysfs_write("/sys/class/leds/blue/trigger", "none");
    sysfs_write("/sys/class/leds/blue/brightness", "0");
    sysfs_write("/sys/class/leds/red/trigger", "breathing");
}
