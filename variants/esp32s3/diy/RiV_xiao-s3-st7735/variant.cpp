#include "variant.h"
#include "Arduino.h"

#ifdef ARCH_ESP32
#include "esp_task_wdt.h"

// WATCHDOG: drop IDLE0 so the long first UI build does not trigger it
static void delayedWdtUnsubscribeTask(void *param)
{
    TaskHandle_t idle0 = xTaskGetIdleTaskHandleForCPU(0);
    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(500));
        if (idle0 && esp_task_wdt_status(idle0) == ESP_OK) {
            if (esp_task_wdt_delete(idle0) == ESP_OK) {
                break;
            }
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

// CS PINS
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
    delay(10);
}
