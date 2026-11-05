/** @file gpio_if.h
 *
 * @brief 单个 GPIO 输出引脚的硬件服务契约。
 *
 * 由 bsp/ 实现并在 app/ 中绑定到具体引脚；module/ 只依赖本头文件。
 * 本文件只有声明，不含实现。
 */

#ifndef GPIO_IF_H
#define GPIO_IF_H

#include <stdbool.h>

#include "proj_err.h"

typedef struct
{
    /* 设置引脚电平；b_high 为 true 表示输出高电平。 */
    proj_err_t (*p_write)(void * p_ctx, bool b_high);

    /* 传给 p_write 的实现私有上下文，例如端口与引脚号。 */
    void * p_ctx;
} gpio_if_t;

#endif /* GPIO_IF_H */

/*** end of file ***/
