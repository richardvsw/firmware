#include "variant.h"
#include "Arduino.h"

#ifdef ARCH_ESP32
#include "esp_task_wdt.h"

// The "tft" task (core 0) builds every LVGL screen synchronously on first
// DeviceUIConfig receipt (ui_init() -> create_screen_main_screen() -> ...).
// That single call can run long enough to starve IDLE0 past the task
// watchdog timeout, causing a panic/reboot mid-UI-build.
//
// Calling esp_task_wdt_delete() directly from initVariant() doesn't stick:
// Meshtastic's own setup() calls esp_task_wdt_init() again later (to set
// its own timeout/config), and that re-subscribes both idle tasks
// (CONFIG_ESP_TASK_WDT_CHECK_IDLE_TASK_CPU0/1 default), silently undoing
// our removal before the tft task ever starts.
//
// Instead, run the unsubscribe from a one-shot task that waits long enough
// for Meshtastic's own watchdog setup to finish, but well before the UI
// build (which happens only after the radio sends a DeviceUIConfig, many
// seconds into runtime) can ever starve IDLE0.
static void delayedWdtUnsubscribeTask(void *param)
{
    // Run on core 1 so TFT task (core 0) + spiLock priority-inheritance can't starve us.
    // Poll every 500 ms until Meshtastic's esp32Setup() subscribes IDLE0, then remove it.
    // Fallback: reconfigure WDT to stop monitoring all IDLE tasks if delete fails.
    TaskHandle_t idle0 = xTaskGetIdleTaskHandleForCPU(0);
    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(500));
        if (idle0 && esp_task_wdt_status(idle0) == ESP_OK) {
            if (esp_task_wdt_delete(idle0) == ESP_OK) {
                break;
            }
            // esp_task_wdt_delete failed — reconfigure WDT to not watch any IDLE task
            esp_task_wdt_config_t cfg = {
                .timeout_ms = 30000,
                .idle_core_mask = 0,
                .trigger_panic = false,
            };
            if (esp_task_wdt_reconfigure(&cfg) == ESP_OK) {
                break;
            }
        }
    }
    vTaskDelete(NULL);
}
#endif

// Pull all SPI CS pins HIGH before the bus starts.
// Without this, whichever CS floats LOW during boot will corrupt
// the first SPI transaction — identical to the T-Deck requirement.
void initVariant()
{
#ifdef ARCH_ESP32
    xTaskCreatePinnedToCore(delayedWdtUnsubscribeTask, "wdtUnsub", 2048, NULL, 1, NULL, 1);
#endif
#ifdef LORA_CS
    pinMode(LORA_CS,    OUTPUT);  digitalWrite(LORA_CS,    HIGH);
#endif
#ifdef TFT_CS
    pinMode(TFT_CS,     OUTPUT);  digitalWrite(TFT_CS,     HIGH);
#endif
#ifdef TOUCH_CS
    pinMode(TOUCH_CS,   OUTPUT);  digitalWrite(TOUCH_CS,   HIGH);
#endif
#ifdef SDCARD_CS
    pinMode(SDCARD_CS,  OUTPUT);  digitalWrite(SDCARD_CS,  HIGH);
#endif
#ifdef HW_BL_PIN
    pinMode(HW_BL_PIN,  OUTPUT);  digitalWrite(HW_BL_PIN,  HIGH);
#endif
    delay(10);
}
