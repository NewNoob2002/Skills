# sdk_stub

仅用于让模板脱离真实 SDK 独立编译：`vendor_i2c.h` 代表厂商 C SDK，`cmsis_compiler.h`、`cmsis_os2.h` 是 CMSIS-Core / CMSIS-RTOS2 中被模板用到的最小声明。

真实项目中删除本目录，改用厂商 SDK 与 CMSIS 的头文件，并以 `-isystem` 引入。
