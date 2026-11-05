# 验证工程的构建入口：host 告警门禁、Cortex-M4 交叉编译、clang-tidy 编译数据库。
SRCS := module/ledctl/ledctl.c bsp/board_led.c bsp/board_tick.c app/main.c
PLAT := platform/board/vectors.c
INCS := -Iinterface -Imodule/ledctl -Ibsp -Iplatform/board
# BARR-C 告警门禁（assets/barr-c/COMPILER_FLAGS.md）；本工程另加 -Werror，使告警成为构建失败
WARN := -std=c99 -Werror=implicit-function-declaration -Wall -Wextra -Werror=parentheses \
        -Wfloat-equal -Wsign-compare -Wshadow -Wundef -Wswitch-default -Wimplicit-fallthrough -Wvla -Werror

.PHONY: warnings cross compdb
warnings:
	gcc $(WARN) $(INCS) -fsyntax-only $(SRCS) $(PLAT)

cross:
	mkdir -p build/cross
	for f in $(SRCS) $(PLAT); do arm-none-eabi-gcc -mcpu=cortex-m4 -mthumb -Os $(WARN) $(INCS) -c $$f -o build/cross/$$(basename $$f .c).o || exit 1; done

compdb:
	python3 gen_compdb.py $$(find app module interface bsp -name "*.c" | sort)
