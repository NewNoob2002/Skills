#!/bin/sh
# 安装 evals/ 验证工程所需的用户级工具（无需 root）。每个工具独立目录，版本固定。
# 用法：sh tools/install_eval_tools.sh [prefix]   （默认 ~/.local/share/embedded-eval）
#
# 前置（需要 root，由用户执行；以 CachyOS/Arch 为例）：
#   sudo pacman -S --needed ruby cppcheck qemu-system-arm
# 另需：gcc、clang、clang-format、clang-tidy、cmake、ninja、dtc、gperf、arm-none-eabi-gcc、uv、git、curl。
# Ceedling：gem install --user-install --no-document ceedling -v 1.2.2
set -eu
P=${1:-$HOME/.local/share/embedded-eval}
mkdir -p "$P"
log() { printf '\n=== %s ===\n' "$*"; }

log "west（uv tool）"
uv tool install --quiet west==1.4.0 2>/dev/null || uv tool install --quiet west
west --version

log "FreeRTOS-Kernel V11.3.3"
[ -d "$P/freertos-kernel" ] || git clone --quiet --depth 1 --branch V11.3.3 https://github.com/FreeRTOS/FreeRTOS-Kernel.git "$P/freertos-kernel"
ls "$P/freertos-kernel/portable/ThirdParty/GCC/Posix"

log "ETL 20.49.0"
[ -d "$P/etl" ] || git clone --quiet --depth 1 --branch 20.49.0 https://github.com/ETLCPP/etl.git "$P/etl"
ls "$P/etl/include/etl/vector.h"

log "CppUTest v4.0（源码构建，安装到 $P/cpputest-install）"
[ -d "$P/cpputest-src" ] || git clone --quiet --depth 1 --branch v4.0 https://github.com/cpputest/cpputest.git "$P/cpputest-src"
if [ ! -f "$P/cpputest-install/lib/libCppUTest.a" ]; then
    # v4.0 声明的 CMake 最低版本低于 3.5，CMake ≥ 4 需要策略参数（见 references/verification/cpp-testing.md §2）
    cmake -S "$P/cpputest-src" -B "$P/cpputest-build" -G Ninja -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_POLICY_VERSION_MINIMUM=3.5 -DTESTS=OFF -DCMAKE_INSTALL_PREFIX="$P/cpputest-install" >/dev/null
    cmake --build "$P/cpputest-build" >/dev/null
    cmake --install "$P/cpputest-build" >/dev/null
fi
ls "$P/cpputest-install/lib"

log "Renode 1.17.0（portable，自带运行时）"
if [ ! -x "$P/renode/renode" ]; then
    mkdir -p "$P/renode-dl"
    curl -sSL -o "$P/renode-dl/renode.tar.gz" \
        https://github.com/renode/renode/releases/download/v1.17.0/renode-1.17.0.linux-portable.tar.gz
    mkdir -p "$P/renode" && tar -xzf "$P/renode-dl/renode.tar.gz" -C "$P/renode" --strip-components=1
fi
"$P/renode/renode" --version 2>/dev/null | head -2 || ls "$P/renode"

log "Zephyr v4.5.0 工作区（只取主仓，模块按需）"
if [ ! -d "$P/zephyrproject/.west" ]; then
    west init -m https://github.com/zephyrproject-rtos/zephyr --mr v4.5.0 "$P/zephyrproject"
fi
cd "$P/zephyrproject"
# native_sim 不需要任何 HAL 模块；只拉取 cmsis 系列以便后续 ARM 目标构建
west config manifest.project-filter -- '-.*,+cmsis,+cmsis_6'
west update --narrow -o=--depth=1
log "Zephyr Python 依赖（独立 venv）"
[ -d .venv ] || uv venv --quiet .venv
VIRTUAL_ENV="$P/zephyrproject/.venv" uv pip install --quiet -r zephyr/scripts/requirements-base.txt \
    -r zephyr/scripts/requirements-build-test.txt -r zephyr/scripts/requirements-run-test.txt
.venv/bin/python -c "import elftools, yaml; print('zephyr venv ok')"
log "done"
