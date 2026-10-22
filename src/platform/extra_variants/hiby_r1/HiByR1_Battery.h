#pragma once

#include "Power.h"
#include <stdint.h>

class HiByR1_Battery : public HasBatteryLevel
{
  public:
    HiByR1_Battery();
    virtual int getBatteryPercent() override;
    virtual uint16_t getBattVoltage() override;
    virtual bool isBatteryConnect() override;
    virtual bool isVbusIn() override;
    virtual bool isCharging() override;
};

extern HiByR1_Battery hibyR1Battery;
