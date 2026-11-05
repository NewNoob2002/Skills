/* 仅用于模板编译检查：CMSIS-RTOS2 cmsis_os2.h 中用到的声明（签名同官方）。真实项目使用 RTOS 提供的头。 */
#ifndef CMSIS_OS2_STUB_H
#define CMSIS_OS2_STUB_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
typedef void *osMutexId_t;
typedef int32_t osStatus_t;
#define osWaitForever 0xFFFFFFFFU
osStatus_t osMutexAcquire(osMutexId_t mutex_id, uint32_t timeout);
osStatus_t osMutexRelease(osMutexId_t mutex_id);
#ifdef __cplusplus
}
#endif
#endif
