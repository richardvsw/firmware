#pragma once

#include <stdint.h>

void hiby_r1_led_init();
void hiby_r1_led_tx();
void hiby_r1_led_rx();
void hiby_r1_led_set_charging(bool charging);
void hiby_r1_led_restore();
