/** @file etl_profile.h
 *
 * @brief ETL 配置。放在项目包含路径中即可：ETL 的 platform.h 用
 * __has_include("etl_profile.h") 自动包含它；找不到时 ETL
 * 使用自动探测的默认值。
 *
 * MCU 默认：不抛异常；容器越界等错误走 etl::error_handler
 * 回调，由项目记录并进入故障处理。
 */

#ifndef ETL_PROFILE_H
#define ETL_PROFILE_H

/* 不使用异常：与 -fno-exceptions 一致。 */
#undef ETL_THROW_EXCEPTIONS

/* 错误交给 etl::error_handler::set_callback() 注册的回调；ETL_CHECK_PUSH_POP
 * 让满/空容器的 push/pop 也经过检查。发布构建若需要更小体积，可改为
 * ETL_NO_CHECKS 并记录理由。 */
#define ETL_LOG_ERRORS
#define ETL_CHECK_PUSH_POP

/* 工具链没有完整 STL 时（例如 Zephyr CONFIG_MINIMAL_LIBCPP）取消注释。 */
/* #define ETL_NO_STL */

#endif /* ETL_PROFILE_H */
