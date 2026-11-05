/** @file proj_err.h
 *
 * @brief 项目统一错误码。
 *
 * NOTE: 不命名为 error_t，避免与 glibc <errno.h> 中的 GNU 扩展类型冲突
 *       （Ceedling 在 host 上编译时会遇到）。
 */

#ifndef PROJ_ERR_H
#define PROJ_ERR_H

typedef enum
{
    PROJ_ERR_OK = 0,
    PROJ_ERR_INVALID_PARAM,
    PROJ_ERR_NOT_INITIALIZED,
    PROJ_ERR_TIMEOUT,
    PROJ_ERR_BUSY,
    PROJ_ERR_IO,
} proj_err_t;

#endif /* PROJ_ERR_H */

/*** end of file ***/
