#!/usr/bin/env python3
"""嵌入式 C/C++ 固件 ELF 开销门禁（只读）。

子命令：
  check <elf> --tier T0|T1|T2|T3 [--allow CLASS ...] [--budget budget.json]
      检查链接产物中是否出现按资源等级禁止的运行时符号（异常、RTTI、堆、静态析构、
      局部静态 guard、std::__throw_*、printf 族、iostream、非 lock-free 原子库调用），
      并按预算文件检查段大小。
  diff <base.elf> <new.elf> [--top N]
      对比两个 ELF 的 text/data/bss 与符号级大小增量（A/B 评估一项改动的真实开销）。

规则依据见 references/cpp/features.md。工具：默认依次尝试 arm-none-eabi-、llvm-、无前缀的
nm/size；其他架构用 --prefix（如 riscv32-unknown-elf-）或 --nm/--size 指定。
退出码：0 通过；1 有 fail 级发现或超出预算；2 参数、工具或文件错误。仅依赖 Python 标准库（3.8+）。
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

# 符号类别：匹配 `nm -C` 的反修饰名。
SYMBOL_CLASSES = {
    "exceptions": (r"^(?:__cxa_throw|__cxa_begin_catch|__cxa_end_catch|__cxa_allocate_exception"
                   r"|__gxx_personality_v0|_Unwind_RaiseException|_Unwind_Resume)$",
                   "C++ 异常运行时（unwinder、personality）"),
    "rtti": (r"^typeinfo (?:name )?for ", "RTTI 类型信息"),
    "heap": (r"^(?:malloc|_malloc_r|free|_free_r|calloc|_calloc_r|realloc|_realloc_r|_sbrk|_sbrk_r"
             r"|operator new(?:\[\])?\(.*\)|operator delete(?:\[\])?\(.*\))$",
             "堆分配（malloc/new）"),
    "static_dtor": (r"^(?:__cxa_atexit|__aeabi_atexit|atexit|__register_exitproc)$",
                    "静态对象析构/atexit 注册"),
    "local_static_guard": (r"^__cxa_guard_(?:acquire|release|abort)$", "函数局部静态的线程安全 guard"),
    "throw_helpers": (r"^std::__throw_", "libstdc++ 抛异常辅助函数（-fno-exceptions 下仍可能被链接）"),
    "stdio_format": (r"^(?:_v?fprintf_r|_svfprintf_r|_vfiprintf_r|_svfiprintf_r|_printf_i|_printf_float"
                     r"|vfprintf|vsnprintf|_vsnprintf_r|printf|sprintf|snprintf|_vfprintf_r)$",
                     "printf 族格式化"),
    "iostream": (r"^std::(?:basic_ostream|basic_istream|basic_ios|ios_base)\b", "iostream"),
    "atomic_libcall": (r"^__atomic_(?:fetch_\w+|load|store|exchange|compare_exchange|\w+_fetch)_\d+$",
                       "非 lock-free 原子的库调用"),
}

# 等级策略：fail = 门禁失败；warn = 报告但通过（需在评审中说明）；info = 仅列出。
TIER_POLICY = {
    "T0": {cls: "fail" for cls in SYMBOL_CLASSES},
    "T1": {"exceptions": "fail", "rtti": "fail", "iostream": "fail", "throw_helpers": "fail",
           "static_dtor": "fail", "atomic_libcall": "fail", "heap": "warn",
           "local_static_guard": "warn", "stdio_format": "warn"},
    "T2": {"exceptions": "fail", "rtti": "fail", "iostream": "fail", "throw_helpers": "warn",
           "static_dtor": "warn", "atomic_libcall": "warn", "heap": "warn",
           "local_static_guard": "warn", "stdio_format": "warn"},
    "T3": {cls: "info" for cls in SYMBOL_CLASSES},
}

BUDGET_KEYS = ("text_max", "data_max", "bss_max", "flash_max", "ram_max")
MAX_EXAMPLES = 5


class ToolError(Exception):
    pass


def find_tool(name, prefix, explicit):
    if explicit:
        if shutil.which(explicit) is None:
            raise ToolError(f"tool not found: {explicit}")
        return explicit
    candidates = [prefix + name] if prefix is not None else [f"arm-none-eabi-{name}", f"llvm-{name}", name]
    for cand in candidates:
        if shutil.which(cand):
            return cand
    raise ToolError(f"none of {candidates} found; pass --prefix or --{name}")


def run_tool(cmd):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise ToolError(f"cannot run {cmd[0]}: {exc}") from exc
    if proc.returncode != 0:
        raise ToolError(f"{' '.join(cmd)} failed: {proc.stderr.strip()[:300]}")
    return proc.stdout


def parse_berkeley_size(text):
    """解析 `size -B` 输出的最后一行：text data bss dec hex filename。"""
    rows = [line.split() for line in text.strip().splitlines() if line.strip()]
    if len(rows) < 2 or len(rows[-1]) < 3:
        raise ToolError(f"unexpected size output: {text[:200]!r}")
    text_sz, data_sz, bss_sz = (int(v) for v in rows[-1][:3])
    return {"text": text_sz, "data": data_sz, "bss": bss_sz,
            "flash": text_sz + data_sz, "ram": data_sz + bss_sz}


def parse_nm_defined(text):
    """解析 `nm -C --defined-only`：返回符号名集合（反修饰名可能含空格）。"""
    names = set()
    for line in text.splitlines():
        parts = line.split(maxsplit=2)
        if len(parts) == 3 and len(parts[1]) == 1:
            names.add(parts[2])
    return names


def parse_nm_sizes(text):
    """解析 `nm -C -S --defined-only`：返回 {名字: 大小}，同名符号（如多个局部静态）累加。"""
    sizes = {}
    for line in text.splitlines():
        parts = line.split(maxsplit=3)
        if len(parts) == 4 and len(parts[2]) == 1:
            try:
                size = int(parts[1], 16)
            except ValueError:
                continue
            sizes[parts[3]] = sizes.get(parts[3], 0) + size
    return sizes


def classify(symbols):
    compiled = {cls: re.compile(pattern) for cls, (pattern, _) in SYMBOL_CLASSES.items()}
    hits = {}
    for name in sorted(symbols):
        for cls, regex in compiled.items():
            if regex.search(name):
                hits.setdefault(cls, []).append(name)
    return hits


def evaluate(hits, tier, allowed):
    policy = TIER_POLICY[tier]
    findings = []
    for cls, names in sorted(hits.items()):
        level = "info" if cls in allowed else policy.get(cls, "info")
        findings.append({"class": cls, "level": level, "allowed": cls in allowed,
                         "description": SYMBOL_CLASSES[cls][1], "count": len(names),
                         "examples": names[:MAX_EXAMPLES]})
    return findings


def check_budget(sizes, budget):
    over = []
    for key in BUDGET_KEYS:
        if key in budget:
            metric = key[:-4]
            if sizes[metric] > int(budget[key]):
                over.append({"metric": metric, "actual": sizes[metric], "max": int(budget[key])})
    return over


def load_budget(path):
    try:
        with open(path, encoding="utf-8") as handle:
            budget = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolError(f"cannot load budget {path}: {exc}") from exc
    unknown = set(budget) - set(BUDGET_KEYS) - {"_comment"}
    if unknown:
        raise ToolError(f"unknown budget keys {sorted(unknown)}; allowed: {list(BUDGET_KEYS)}")
    return budget


def require_file(path):
    if not Path(path).is_file():
        raise ToolError(f"file not found: {path}")


def cmd_check(args):
    require_file(args.elf)
    nm = find_tool("nm", args.prefix, args.nm)
    size = find_tool("size", args.prefix, args.size)
    unknown = set(args.allow) - set(SYMBOL_CLASSES)
    if unknown:
        raise ToolError(f"unknown --allow classes {sorted(unknown)}; known: {sorted(SYMBOL_CLASSES)}")

    sizes = parse_berkeley_size(run_tool([size, "-B", args.elf]))
    symbols = parse_nm_defined(run_tool([nm, "-C", "--defined-only", args.elf]))
    findings = evaluate(classify(symbols), args.tier, set(args.allow))
    over = check_budget(sizes, load_budget(args.budget)) if args.budget else []
    failed = any(f["level"] == "fail" for f in findings) or bool(over)
    report = {"elf": args.elf, "tier": args.tier, "sizes": sizes, "findings": findings,
              "budget_exceeded": over, "result": "FAIL" if failed else "PASS"}

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"{args.elf}: tier {args.tier}  text={sizes['text']} data={sizes['data']} "
              f"bss={sizes['bss']}  (flash={sizes['flash']} ram={sizes['ram']})")
        for f in findings:
            tag = "ALLOWED" if f["allowed"] else f["level"].upper()
            print(f"  [{tag}] {f['class']}: {f['description']} ({f['count']} symbols) "
                  f"e.g. {', '.join(f['examples'])}")
        for o in over:
            print(f"  [FAIL] budget: {o['metric']} {o['actual']} > {o['max']}")
        if not findings and not over:
            print("  no restricted runtime symbols")
        print(f"cpp_cost check: {report['result']}")
    return 1 if failed else 0


def cmd_diff(args):
    for path in (args.base, args.new):
        require_file(path)
    nm = find_tool("nm", args.prefix, args.nm)
    size = find_tool("size", args.prefix, args.size)
    base_sz = parse_berkeley_size(run_tool([size, "-B", args.base]))
    new_sz = parse_berkeley_size(run_tool([size, "-B", args.new]))
    base_sym = parse_nm_sizes(run_tool([nm, "-C", "-S", "--defined-only", args.base]))
    new_sym = parse_nm_sizes(run_tool([nm, "-C", "-S", "--defined-only", args.new]))

    deltas = []
    for name in set(base_sym) | set(new_sym):
        delta = new_sym.get(name, 0) - base_sym.get(name, 0)
        if delta != 0:
            state = "added" if name not in base_sym else "removed" if name not in new_sym else "changed"
            deltas.append({"symbol": name, "delta": delta, "state": state})
    deltas.sort(key=lambda d: (-abs(d["delta"]), d["symbol"]))
    sections = {k: {"base": base_sz[k], "new": new_sz[k], "delta": new_sz[k] - base_sz[k]} for k in base_sz}
    report = {"base": args.base, "new": args.new, "sections": sections, "symbols": deltas[:args.top]}

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        for key, val in sections.items():
            print(f"{key:>6}: {val['base']:>8} -> {val['new']:>8}  ({val['delta']:+d})")
        print(f"top {min(args.top, len(deltas))} symbol deltas:")
        for d in deltas[:args.top]:
            print(f"  {d['delta']:+7d}  {d['state']:<8} {d['symbol']}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--prefix", help="工具前缀，例如 arm-none-eabi- 或 riscv32-unknown-elf-")
    parser.add_argument("--nm", help="nm 可执行文件")
    parser.add_argument("--size", help="size 可执行文件")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="禁用符号与段预算检查")
    p_check.add_argument("elf")
    p_check.add_argument("--tier", required=True, choices=sorted(TIER_POLICY))
    p_check.add_argument("--allow", action="append", default=[], metavar="CLASS",
                         help=f"已评审允许的类别，可重复：{', '.join(sorted(SYMBOL_CLASSES))}")
    p_check.add_argument("--budget", help=f"预算 JSON，键：{', '.join(BUDGET_KEYS)}")

    p_diff = sub.add_parser("diff", help="两个 ELF 的尺寸增量")
    p_diff.add_argument("base")
    p_diff.add_argument("new")
    p_diff.add_argument("--top", type=int, default=20)

    args = parser.parse_args(argv)
    try:
        return cmd_check(args) if args.command == "check" else cmd_diff(args)
    except ToolError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
