/* FreeRTOS POSIX 移植的 host 集成测试配置（只用于 host，不用于目标板）。 */
#ifndef FREERTOS_CONFIG_H
#define FREERTOS_CONFIG_H

#define configUSE_PREEMPTION                    1
#define configUSE_IDLE_HOOK                     0
#define configUSE_TICK_HOOK                     0
#define configTICK_RATE_HZ                      ( 1000 )
#define configMINIMAL_STACK_SIZE                ( ( unsigned short ) PTHREAD_STACK_MIN )
#define configTOTAL_HEAP_SIZE                   ( ( size_t ) ( 64 * 1024 ) )
#define configMAX_TASK_NAME_LEN                 ( 16 )
#define configTICK_TYPE_WIDTH_IN_BITS           TICK_TYPE_WIDTH_64_BITS
#define configMAX_PRIORITIES                    ( 5 )
#define configUSE_MUTEXES                       1
#define configQUEUE_REGISTRY_SIZE               0
#define configUSE_TIMERS                        0
#define configSUPPORT_DYNAMIC_ALLOCATION        1
#define configSUPPORT_STATIC_ALLOCATION         0
#define configCHECK_FOR_STACK_OVERFLOW          0
#define configUSE_MALLOC_FAILED_HOOK            0
#define configUSE_TRACE_FACILITY                0

#define INCLUDE_vTaskDelay                      1
#define INCLUDE_vTaskDelete                     1
#define INCLUDE_xTaskGetTickCount               1

/* 断言失败直接结束进程并返回非零，host 测试据此判定失败。 */
#include <stdlib.h>
#define configASSERT( x )    do { if( ( x ) == 0 ) { exit( 3 ); } } while( 0 )

#endif /* FREERTOS_CONFIG_H */
