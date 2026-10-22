#include "variant.h"
#include "HiByR1_Battery.h"
#include "HiByR1_LED.h"
#include "NodeDB.h"
#include "Observer.h"
#include "Power.h"
#include "PowerStatus.h"
#include "graphics/view/TFT/TFTView_320x240.h"
#include "mesh/RadioInterface.h"
#include <cstdlib>

class HiByR1PowerObserver : public Observer<const meshtastic::PowerStatus *>
{
  protected:
    virtual int onNotify(const meshtastic::PowerStatus *st) override
    {
        if (!st)
            return 0;
        uint32_t pct = st->getBatteryChargePercent();
        float volt = st->getBatteryVoltageMv() / 1000.0f;
        bool isCharging = st->getIsCharging();
        hiby_r1_led_set_charging(isCharging);

        auto view = TFTView_320x240::instance();
        if (view && nodeDB) {
            view->updateMetrics(nodeDB->getNodeNum(), isCharging ? 101 : pct, volt, 0.0f, 0.0f);
        }
        return 0;
    }
};

class HiByR1RxObserver : public Observer<uint32_t>
{
  protected:
    virtual int onNotify(uint32_t) override
    {
        hiby_r1_led_rx();
        return 0;
    }
};

static HiByR1PowerObserver powerObs;
static HiByR1RxObserver rxObs;

void earlyInitVariant()
{
    // earlyInitVariant runs before consoleInit, no LOG_* here
}

void lateInitVariant()
{
    // Register battery sensor with Meshtastic Power subsystem
    if (power) {
        power->setBatterySensor(&hibyR1Battery);
        powerObs.observe(&powerStatus->onNewStatus);
    }

    // Initialize side LEDs (blue breathing, red off/traffic)
    hiby_r1_led_init();
    std::atexit(hiby_r1_led_restore);

    // Observe LoRa packet reception for LED RX flash
    rxObs.observe(&RadioInterface::loraRxPacketObservable);

    // Initial battery update for MUI top bar
    if (powerStatus) {
        int pct = hibyR1Battery.getBatteryPercent();
        float volt = hibyR1Battery.getBattVoltage() / 1000.0f;
        bool chg = hibyR1Battery.isCharging();
        auto view = TFTView_320x240::instance();
        if (view && nodeDB && pct >= 0) {
            view->updateMetrics(nodeDB->getNodeNum(), chg ? 101 : pct, volt, 0.0f, 0.0f);
        }
    }
}
