#pragma once
#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef void *TaskHandle_t;
typedef void (*TaskFunction_t)(void *);
typedef uint32_t BaseType_t;

#define pdPASS (1)
#define pdFAIL (0)

static inline BaseType_t xTaskCreate(TaskFunction_t pxTaskCode,
                                     const char * const pcName,
                                     const uint16_t usStackDepth,
                                     void * const pvParameters,
                                     uint32_t uxPriority,
                                     TaskHandle_t * const pxCreatedTask) {
    (void)pcName; (void)usStackDepth; (void)uxPriority; (void)pxCreatedTask;
    // On Linux without FreeRTOS, run task synchronously or no-op
    if (pxTaskCode) {
        pxTaskCode(pvParameters);
    }
    return pdPASS;
}

static inline void vTaskDelete(TaskHandle_t xTaskToDelete) {
    (void)xTaskToDelete;
}

static inline void vTaskDelay(const uint32_t xTicksToDelay) {
    (void)xTicksToDelay;
}

#ifdef __cplusplus
}
#endif
