#ifndef CONFIG_STORE_H
#define CONFIG_STORE_H

#include <stddef.h>
#include <stdint.h>

/*
 * 原子保存（LNXU-002）：写 <path>.tmp → fsync → close → rename 到 <path> → fsync 所在目录。
 * dir 是 path 所在的目录。成功返回 0，失败返回 -errno，且不留下半写的 <path>。
 */
int config_save(const char *dir, const char *path, const uint8_t *data, size_t len);

#endif /* CONFIG_STORE_H */
