#!/bin/bash
# skill 自测：编译 C++ 模板（C++17/20 × M0+/M4/M7，严格告警 -Werror）、负向编译、格式与 clang-tidy。
# 用法：ETL_INCLUDE=<etl>/include tests/cpp/run_cpp_checks.sh
# 依赖：arm-none-eabi-g++；clang-format、clang-tidy 可选（缺失时报告 SKIP）。
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
SKILL=$(cd "$HERE/../../embedded-engineering" && pwd)
T=$SKILL/assets/cpp/templates
: "${ETL_INCLUDE:?set ETL_INCLUDE to the ETL include directory}"
CXX=${CXX_CROSS:-arm-none-eabi-g++}
INC="-I$T/interface -I$T/driver/device -I$T/bsp -I$T/lib -I$T/osal -I$T/platform -I$T -isystem $T/sdk_stub -isystem $ETL_INCLUDE"
WARN="-Wall -Wextra -Wpedantic -Wshadow -Wconversion -Wsign-conversion -Wold-style-cast -Wnon-virtual-dtor -Woverloaded-virtual -Wcast-align -Wdouble-promotion -Wnull-dereference -Wimplicit-fallthrough -Wundef -Werror"
RT="-fno-exceptions -fno-rtti -fno-use-cxa-atexit"
fail=0
pass() { echo "PASS $*"; }
bad() { echo "FAIL $*"; fail=1; }

for std in c++17 c++20; do
  CI=""; [ "$std" = c++17 ] && CI="-Dconstinit="
  for cpu in cortex-m0plus cortex-m4 cortex-m7; do
    EXTRA=""; [ "$cpu" = cortex-m0plus ] && EXTRA="-DPROJ_SKIP_SPSC"
    for src in "$HERE/compile_all.cpp" "$T/bsp/heap_guard.cpp" "$T/app/app_main.cpp"; do
      if out=$($CXX -mcpu=$cpu -mthumb -Os -std=$std $RT $WARN $CI $EXTRA $INC -c "$src" -o /dev/null 2>&1); then
        pass "compile $std $cpu $(basename "$src")"
      else
        bad "compile $std $cpu $(basename "$src")"; echo "$out" | head -8
      fi
    done
  done
done

neg() { # file cpu expected_message
  out=$($CXX -mcpu=$2 -mthumb -std=c++20 $RT $INC -fsyntax-only "$HERE/$1" 2>&1)
  if [ $? -ne 0 ] && echo "$out" | grep -qE "$3"; then pass "negative $1 ($3)"; else bad "negative $1 did not fail with '$3'"; fi
}
neg neg_baud_tolerance.cpp cortex-m4 "baud rate error exceeds tolerance"
neg neg_bad_bus.cpp cortex-m4 "Bus must provide|template constraint failure|constraints not satisfied"
neg neg_spsc_armv6m.cpp cortex-m0plus "needs lock-free 32-bit atomics"
neg neg_dma_alignment.cpp cortex-m7 "whole cache lines"

CPP_FILES=$(find "$T" \( -name '*.hpp' -o -name '*.cpp' \) | sort)
if command -v clang-format >/dev/null; then
  if clang-format --style=file:"$SKILL/assets/cpp/.clang-format" --dry-run --Werror $CPP_FILES; then pass "clang-format C++ templates"; else bad "clang-format C++ templates"; fi
else echo "SKIP clang-format not installed"; fi

if command -v clang-tidy >/dev/null; then
  # 主机目标只做语义检查；platform/ 使用豁免配置。CppUTest 测试模板不在此检查（依赖 CppUTest 头）。
  TIDY_SRC="$HERE/compile_all.cpp $T/app/app_main.cpp"
  if out=$(clang-tidy --quiet --config-file="$SKILL/assets/cpp/.clang-tidy" $TIDY_SRC -- -x c++ -std=c++20 $INC 2>&1); then
    pass "clang-tidy C++ config (compile_all.cpp, app_main.cpp)"
  else bad "clang-tidy C++ config"; echo "$out" | grep -E "warning|error" | head -20; fi
  if out=$(clang-tidy --quiet --config-file="$SKILL/assets/cpp/.clang-tidy" "$T/bsp/heap_guard.cpp" -- -x c++ -std=c++20 $INC 2>&1); then
    pass "clang-tidy heap_guard.cpp"
  else bad "clang-tidy heap_guard.cpp"; echo "$out" | grep -E "warning|error" | head -20; fi
else echo "SKIP clang-tidy not installed"; fi
exit $fail
