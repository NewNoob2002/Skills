# 验证工程的构建入口：host 告警门禁、Cortex-M4 交叉编译、QEMU 目标测试、clang-tidy 编译数据库。
SRCS := module/ledctl/ledctl.c bsp/board_led.c bsp/board_tick.c app/main.c
PLAT := platform/board/vectors.c
INCS := -Iinterface -Imodule/ledctl -Ibsp -Iplatform/board
# BARR-C 告警门禁（assets/barr-c/COMPILER_FLAGS.md）；本工程另加 -Werror，使告警成为构建失败
WARN := -std=c99 -Werror=implicit-function-declaration -Wall -Wextra -Werror=parentheses \
        -Wfloat-equal -Wsign-compare -Wshadow -Wundef -Wswitch-default -Wimplicit-fallthrough -Wvla -Werror

.PHONY: warnings cross target qemu compdb
warnings:
	gcc $(WARN) $(INCS) -fsyntax-only $(SRCS) $(PLAT)

cross:
	mkdir -p build/cross
	for f in $(SRCS) $(PLAT); do arm-none-eabi-gcc -mcpu=cortex-m4 -mthumb -Os $(WARN) $(INCS) -c $$f -o build/cross/$$(basename $$f .c).o || exit 1; done

compdb:
	python3 gen_compdb.py $$(find app module interface bsp -name "*.c" | sort)

# 目标测试：被测源码 + tests/target/ 链接成 mps2-an386 镜像，在 QEMU 中经 semihosting 报告结果。
# app/main.c 一并链接（入口改名，不执行），以确保整个固件的符号都能解析。
LDSCRIPT ?= tests/target/link.ld
TGT_FLAGS := -mcpu=cortex-m4 -mthumb -Os -g -ffunction-sections -fdata-sections
target:
	mkdir -p build/target
	arm-none-eabi-gcc $(TGT_FLAGS) $(WARN) $(INCS) -Dmain=app_main_unused -c app/main.c -o build/target/main.o
	arm-none-eabi-gcc $(TGT_FLAGS) -std=c99 -Wall -Wextra -Werror $(INCS) -Itests/target -nostdlib \
		-T $(LDSCRIPT) -Wl,--gc-sections -o build/target/app.elf \
		$(filter-out app/main.c,$(SRCS)) $(PLAT) build/target/main.o tests/target/startup.c tests/target/target_main.c

# 超时视为失败（例如节拍不增长导致主循环永远等待）
qemu: target
	timeout 20 qemu-system-arm -M mps2-an386 -nographic -semihosting -no-reboot -kernel build/target/app.elf
