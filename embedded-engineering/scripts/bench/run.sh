#!/bin/bash
# C++ 特性开销微基准：在“你自己的”工具链与选项下复现 references/cpp-features.md 中的数据。
#
# 用法：
#   scripts/bench/run.sh [--cpu cortex-m4] [--float-abi hard|soft] [--fpu fpv4-sp-d16]
#                        [--std c++20] [--etl <etl>/include] [--out <dir>] [--cxx arm-none-eabi-g++]
# 输出：每个变体的 text/data/bss、相对空 C++ 程序的增量，以及拉入的受限运行时符号类别。
# 只编译链接（newlib-nano + nosys），不运行、不 flash。依赖 bash、arm-none-eabi 工具链、python3。
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$HERE/src
COST=$HERE/../cpp_cost.py
CPU=cortex-m4; FLOAT_ABI=hard; FPU=fpv4-sp-d16; STD=c++20; ETL=""; OUT=""; CXX=arm-none-eabi-g++
while [ "$#" -gt 0 ]; do
  case "$1" in
    --cpu) CPU=$2; shift 2 ;;
    --float-abi) FLOAT_ABI=$2; shift 2 ;;
    --fpu) FPU=$2; shift 2 ;;
    --std) STD=$2; shift 2 ;;
    --etl) ETL=$2; shift 2 ;;
    --out) OUT=$2; shift 2 ;;
    --cxx) CXX=$2; shift 2 ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "unknown option $1" >&2; exit 2 ;;
  esac
done
command -v "$CXX" >/dev/null || { echo "error: $CXX not found" >&2; exit 2; }
CC=${CXX%g++}gcc; PREFIX=${CXX%g++}
[ -n "$OUT" ] || OUT=$(mktemp -d "${TMPDIR:-/tmp}/cpp-bench.XXXXXX")
mkdir -p "$OUT"

ARCH="-mcpu=$CPU -mthumb -mfloat-abi=$FLOAT_ABI"
[ "$FLOAT_ABI" = soft ] || ARCH="$ARCH -mfpu=$FPU"
COMMON="$ARCH -Os -ffunction-sections -fdata-sections -I$SRC"
[ -n "$ETL" ] && COMMON="$COMMON -isystem $ETL"
CFLAGS="$COMMON -std=c11"
CXXBASE="$COMMON -std=$STD -fno-exceptions -fno-rtti"
LD="$ARCH -Wl,--gc-sections --specs=nano.specs --specs=nosys.specs"

$CC $CFLAGS -c "$SRC/common.c" -o "$OUT/common.o" || exit 1
BASE_TEXT=""

classes() { # elf -> 逗号分隔的符号类别
  python3 -I "$COST" --prefix "$PREFIX" --json check "$1" --tier T3 2>/dev/null |
    python3 -I -c 'import json,sys; print(",".join(f["class"] for f in json.load(sys.stdin)["findings"]) or "-")'
}

build() { # name source [extra flags]
  local name=$1 src=$2 extra=${3:-} log="$OUT/$1.log"
  case "$src" in
    *etl*|*f07_*) [ -n "$ETL" ] || { printf '%-26s SKIP (needs --etl)\n' "$name"; return; } ;;
  esac
  if [[ "$src" == *.c ]]; then
    $CC $CFLAGS $extra -c "$SRC/$src" -o "$OUT/$name.o" >"$log" 2>&1 &&
      $CC $LD "$OUT/$name.o" "$OUT/common.o" -o "$OUT/$name.elf" >>"$log" 2>&1
  else
    $CXX $CXXBASE $extra -c "$SRC/$src" -o "$OUT/$name.o" >"$log" 2>&1 &&
      $CXX $LD $extra "$OUT/$name.o" "$OUT/common.o" -o "$OUT/$name.elf" >>"$log" 2>&1
  fi || { printf '%-26s BUILD/LINK FAIL (see %s)\n' "$name" "$log"; return; }
  read -r t d b _ <<<"$(${PREFIX}size -B "$OUT/$name.elf" | tail -1)"
  [ -z "$BASE_TEXT" ] && BASE_TEXT=$t
  printf '%-26s %7s %6s %6s %+8d  %s\n' "$name" "$t" "$d" "$b" $((t - BASE_TEXT)) "$(classes "$OUT/$name.elf")"
}

echo "toolchain: $($CXX --version | head -1)"
echo "flags: $CXXBASE"
printf '%-26s %7s %6s %6s %8s  %s\n' variant text data bss dtext runtime_classes
build a1_baseline_cpp        a1_baseline.cpp
build a0_baseline_c          a0_baseline.c
build d1_c_functable         d1_c_functable.c
build d2_virtual_prot_dtor   d2_cpp_virtual.cpp
build d2b_virtual_pub_dtor   d2b_cpp_virtual_public_dtor.cpp
build d3_template_concept    d3_cpp_template.cpp
build d4_crtp                d4_cpp_crtp.cpp
build f01_exceptions         f01_exceptions.cpp "-fexceptions"
build f02a_rtti_dynamic_cast f02_rtti_dynamic_cast.cpp "-frtti"
build f02b_virtual_no_rtti   f02b_virtual_no_rtti.cpp
build f03a_std_function      f03a_std_function.cpp
build f03b_etl_delegate      f03b_etl_delegate.cpp
build f03c_etl_inplace_fn    f03c_etl_inplace_function.cpp
build f04_iostream           f04_iostream.cpp
build f05a_printf            f05a_printf_int.cpp
build f05b_snprintf          f05b_snprintf_int.cpp
build f06_std_vector         f06_std_vector.cpp
build f07_etl_vector         f07_etl_vector.cpp
build f08a_local_static      f08_local_static.cpp
build f08b_local_static_nts  f08_local_static.cpp "-fno-threadsafe-statics"
build f09a_global_dtor       f09_global_dtor.cpp
build f09b_global_dtor_ncxa  f09_global_dtor.cpp "-fno-use-cxa-atexit"
build f10a_span              f10a_span.cpp
build f10b_ptr_len_c         f10b_ptr_len.c
build f11_optional           f11_optional.cpp
build f12_variant_visit      f12_variant_visit.cpp
build f13a_crc_consteval     f13a_crc_constexpr.cpp
build f13b_crc_runtime_c     f13b_crc_runtime.c
build f14_atomic32_rmw       f14_atomic_rmw.cpp
build f15_atomic64_rmw       f15_atomic64.cpp
echo "elf/logs: $OUT"
