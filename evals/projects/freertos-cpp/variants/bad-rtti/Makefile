# 验证工程构建入口。外部依赖通过变量传入：CPPUTEST（安装前缀）、FREERTOS（FreeRTOS-Kernel 源码）。
INCS   := -Iinterface -Imodule/filter -Imodule/telemetry -Ibsp
# assets/cpp/compile_flags.md 的严格告警组
STRICT := -Wall -Wextra -Wpedantic -Wshadow -Wconversion -Wsign-conversion -Wold-style-cast \
          -Wnon-virtual-dtor -Woverloaded-virtual -Wcast-align -Wdouble-promotion -Wnull-dereference \
          -Wimplicit-fallthrough -Wundef -Werror
# T0 目标：Cortex-M0+，无异常、无 RTTI、静态析构不注册（compile_flags.md）
TARGET := -mcpu=cortex-m0plus -mthumb -mfloat-abi=soft -std=c++17 -Os -fno-exceptions \
          -fno-use-cxa-atexit -ffunction-sections -fdata-sections
TSRC   := app/app_main.cpp module/telemetry/telemetry.cpp bsp/adc.cpp

.PHONY: cross unit rtos format
cross:
	mkdir -p build
	arm-none-eabi-g++ $(TARGET) $(STRICT) $(INCS) $(TSRC) -Wl,--gc-sections --specs=nano.specs --specs=nosys.specs -o build/app_m0.elf

unit:
	mkdir -p build
	g++ -std=c++17 -g $(STRICT) $(INCS) -isystem $(CPPUTEST)/include tests/test_telemetry.cpp tests/all_tests.cpp \
	    module/telemetry/telemetry.cpp -L$(CPPUTEST)/lib -lCppUTest -lCppUTestExt -o build/unit_tests
	./build/unit_tests -c

FRTOS_SRC = $(FREERTOS)/tasks.c $(FREERTOS)/queue.c $(FREERTOS)/list.c $(FREERTOS)/portable/MemMang/heap_3.c \
            $(FREERTOS)/portable/ThirdParty/GCC/Posix/port.c $(FREERTOS)/portable/ThirdParty/GCC/Posix/utils/wait_for_event.c
FRTOS_INC = -Ihost_rtos -isystem $(FREERTOS)/include -isystem $(FREERTOS)/portable/ThirdParty/GCC/Posix \
            -isystem $(FREERTOS)/portable/ThirdParty/GCC/Posix/utils
rtos:
	mkdir -p build/frtos
	for f in $(FRTOS_SRC); do gcc -c -O1 $(FRTOS_INC) $$f -o build/frtos/$$(basename $$f .c).o || exit 1; done
	g++ -std=c++17 $(STRICT) $(INCS) $(FRTOS_INC) host_rtos/main_posix.cpp module/telemetry/telemetry.cpp build/frtos/*.o -lpthread -o build/rtos_host
	./build/rtos_host

format:
	clang-format --style=file:$(STYLE) --dry-run --Werror $$(find app module interface bsp tests host_rtos -name "*.[ch]pp" | sort)
