#include "variant.h"
#include "Arduino.h"

#ifdef XIAO_TFT_DUALBOOT
#include "esp_ota_ops.h"
#include "esp_partition.h"

// Dual boot: the launcher in the factory slot picked this app. Point the boot partition back at the launcher right away,
// so any restart (power cycle, reboot after a config change) returns to the selection menu.
static void dualbootReturnToLauncher()
{
    const esp_partition_t *launcher =
        esp_partition_find_first(ESP_PARTITION_TYPE_APP, ESP_PARTITION_SUBTYPE_APP_FACTORY, NULL);
    if (launcher)
        esp_ota_set_boot_partition(launcher);
}
#endif

#ifdef ARCH_ESP32
#include "esp_task_wdt.h"

// The tft task builds every LVGL screen synchronously on first DeviceUIConfig receipt, that can starve IDLE0 past the task
// watchdog timeout. Unsubscribe IDLE0 once Meshtastic has set up its own watchdog.
static void delayedWdtUnsubscribeTask(void *param)
{
    vTaskDelay(pdMS_TO_TICKS(3000));
    TaskHandle_t idle0 = xTaskGetIdleTaskHandleForCPU(0);
    if (!idle0) {
        vTaskDelete(NULL);
        return;
    }
    if (esp_task_wdt_status(idle0) != ESP_OK) {
        vTaskDelete(NULL);
        return;
    }
    if (esp_task_wdt_delete(idle0) != ESP_OK) {
        esp_task_wdt_config_t cfg = {
            .timeout_ms = 30000,
            .idle_core_mask = 0,
            .trigger_panic = false,
        };
        esp_task_wdt_reconfigure(&cfg);
    }
    vTaskDelete(NULL);
}
#endif

// Pull all SPI CS pins HIGH before the bus starts, a floating CS corrupts the first SPI transaction.
void initVariant()
{
#ifdef XIAO_TFT_DUALBOOT
    dualbootReturnToLauncher();
#endif
#ifdef ARCH_ESP32
    xTaskCreatePinnedToCore(delayedWdtUnsubscribeTask, "wdt", 2048, NULL, 1, NULL, 1);
#endif
#ifdef LORA_CS
    pinMode(LORA_CS, OUTPUT);
    digitalWrite(LORA_CS, HIGH);
#endif
#ifdef TFT_CS
    pinMode(TFT_CS, OUTPUT);
    digitalWrite(TFT_CS, HIGH);
#endif
#ifdef TOUCH_CS
    pinMode(TOUCH_CS, OUTPUT);
    digitalWrite(TOUCH_CS, HIGH);
#endif
#ifdef SDCARD_CS
    pinMode(SDCARD_CS, OUTPUT);
    digitalWrite(SDCARD_CS, HIGH);
#endif
    delay(20);
}
