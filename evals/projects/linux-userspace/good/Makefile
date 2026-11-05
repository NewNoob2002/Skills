# 验证工程构建入口：告警门禁（C11 + POSIX，-Werror）。
WARN := -std=c11 -D_POSIX_C_SOURCE=200809L -Wall -Wextra -Wpedantic -Wshadow -Wformat=2 -Wundef -Werror
.PHONY: warnings
warnings:
	gcc $(WARN) -fsyntax-only src/*.c
