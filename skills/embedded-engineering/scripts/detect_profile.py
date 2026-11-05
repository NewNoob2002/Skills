#!/usr/bin/env python3
"""识别仓库（或子目录）适用的 embedded-engineering profile（只读）。

输出每个候选 profile 的得分与证据文件，以及项目自带的规范/工具配置。
这是启发式判定：Agent 应核对证据，再按 references/profiles.md 决定。
仅依赖 Python 标准库（3.8+）。退出码：0 正常；2 参数错误。
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

SKIP_DIRS = {".git", "build", "out", "node_modules", ".venv", "venv", "__pycache__",
             ".pio", "cmake-build-debug", "cmake-build-release", "twister-out"}
MAX_FILES = 20000
MAX_READ = 64 * 1024

# (profile, 权重, 说明, 判定函数(rel_path, name) -> bool, 可选内容正则)
NAME_RULES = [
    ("zephyr", 5, "west manifest", lambda r, n: n == "west.yml", None),
    ("zephyr", 4, "Zephyr module", lambda r, n: r.endswith("zephyr/module.yml"), None),
    ("zephyr", 3, "prj.conf", lambda r, n: n == "prj.conf", None),
    ("zephyr", 2, "devicetree overlay", lambda r, n: n.endswith(".overlay"), None),
    ("zephyr", 4, "find_package(Zephyr)", lambda r, n: n == "CMakeLists.txt",
     re.compile(r"find_package\s*\(\s*Zephyr", re.I)),
    ("zephyr", 2, "Twister testcase", lambda r, n: n in ("testcase.yaml", "sample.yaml"), None),
    ("linux-kernel", 5, "Kbuild file", lambda r, n: n == "Kbuild", None),
    ("linux-kernel", 4, "kbuild obj-y/obj-m", lambda r, n: n == "Makefile",
     re.compile(r"^\s*obj-(?:y|m|\$\()", re.M)),
    ("linux-kernel", 3, "MODULE_LICENSE / module_init", lambda r, n: n.endswith(".c"),
     re.compile(r"\bMODULE_LICENSE\s*\(|\bmodule_(?:platform_|i2c_|spi_)?(?:init|driver)\s*\(")),
    ("linux-kernel", 3, "DT schema binding", lambda r, n: "bindings/" in r and n.endswith(".yaml"),
     re.compile(r"devicetree\.org/meta-schemas")),
    ("linux-kernel", 2, "MAINTAINERS file", lambda r, n: n == "MAINTAINERS", None),
    ("mcu-rtos", 5, "FreeRTOSConfig.h", lambda r, n: n == "FreeRTOSConfig.h", None),
    ("mcu-rtos", 4, "CMSIS-RTOS2 header", lambda r, n: n in ("cmsis_os2.h", "cmsis_os.h"), None),
    ("mcu-rtos", 4, "RT-Thread / ThreadX config", lambda r, n: n in ("rtconfig.h", "tx_user.h", "tx_api.h"), None),
    ("mcu-baremetal", 4, "startup assembly", lambda r, n: re.match(r"startup_.*\.(s|S|asm)$", n) is not None, None),
    ("mcu-baremetal", 3, "linker script", lambda r, n: n.endswith((".ld", ".sct", ".icf")), None),
    ("mcu-baremetal", 3, "CMSIS core header", lambda r, n: re.match(r"core_cm\w*\.h$", n) is not None, None),
    ("mcu-baremetal", 3, "vendor HAL header", lambda r, n: re.match(r"(stm32|gd32|at32|ch32|py32)\w*_hal\.h$|fsl_device_registers\.h$|nrfx\.h$", n) is not None, None),
    ("mcu-baremetal", 3, "CubeMX project", lambda r, n: n.endswith(".ioc"), None),
    ("mcu-baremetal", 2, "arm-none-eabi toolchain", lambda r, n: n.endswith((".cmake", "Makefile", "CMakeLists.txt")),
     re.compile(r"arm-none-eabi|riscv(?:32|64)?-unknown-elf|xtensa-")),
    ("linux-userspace", 3, "Yocto recipe", lambda r, n: n.endswith((".bb", ".bbappend")), None),
    ("linux-userspace", 3, "systemd unit", lambda r, n: n.endswith((".service", ".socket")), None),
    ("linux-userspace", 2, "Meson project", lambda r, n: n == "meson.build", None),
    ("linux-userspace", 2, "Linux userspace API", lambda r, n: n.endswith(".c"),
     re.compile(r"#\s*include\s*<(?:gpiod\.h|linux/spi/spidev\.h|linux/i2c-dev\.h|sys/epoll\.h|systemd/sd-daemon\.h)>")),
]

TOOLING = {
    "AGENTS.md": "agent rules", "CLAUDE.md": "agent rules", ".clang-format": "formatter",
    ".clang-tidy": "static analysis", ".editorconfig": "editor", ".checkpatch.conf": "checkpatch",
    "project.yml": "Ceedling (if :project: section)", "compile_commands.json": "compilation database",
    ".gitlint": "commit lint", "MISRA.md": "MISRA records", "CONTRIBUTING.md": "contribution rules",
    "CONTRIBUTING.rst": "contribution rules",
}

CONTENT_RULE_LIMIT = 300  # 每个内容规则最多读取的文件数，控制大仓库耗时

C_SUFFIXES = {".c"}
CPP_SUFFIXES = {".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx", ".ipp"}
HEADER_SUFFIXES = {".h"}  # C 与 C++ 共用，单独计数

CXX_STD_RES = [
    re.compile(r"CMAKE_CXX_STANDARD\s+(\d+)"),
    re.compile(r"cxx_std_(\d+)"),
    re.compile(r"-std=(?:c|gnu)\+\+(\d+)"),
]
ZEPHYR_CPP_RE = re.compile(r"^CONFIG_CPP=y", re.M)
ZEPHYR_STD_RE = re.compile(r"^CONFIG_STD_CPP(\d+)=y", re.M)
CPP_LIBRARY_RULES = [
    ("etl", lambda rel, name: name == "etl_profile.h" or rel.endswith("etl/platform.h")),
    ("pigweed", lambda rel, name: rel.endswith("pw_status/status.h") or name == "pigweed.json"),
    ("modm", lambda rel, name: rel.endswith("modm/platform.hpp") or name == "project.xml"),
]
CPPUTEST_RE = re.compile(r'#\s*include\s*[<"]CppUTest/|find_package\s*\(\s*CppUTest')

# 链接脚本 MEMORY 区域：NAME (attr) : ORIGIN = x, LENGTH = 512K
MEMORY_RE = re.compile(
    r"^\s*(\w+)\s*(?:\([^)]*\))?\s*:\s*ORIGIN\s*=\s*[^,]+,\s*LENGTH\s*=\s*(0x[0-9a-fA-F]+|\d+)\s*([KkMm])?",
    re.M)
FLASH_NAME_RE = re.compile(r"FLASH|ROM|TEXT", re.I)
RAM_NAME_RE = re.compile(r"RAM|DTCM|CCM", re.I)
TIER_T0_FLASH, TIER_T0_RAM = 64 * 1024, 16 * 1024
TIER_T2_FLASH, TIER_T2_RAM = 1024 * 1024, 512 * 1024


def parse_memory_regions(text):
    """返回链接脚本中 Flash 类与 RAM 类区域的总字节数。"""
    flash = ram = 0
    for name, length, unit in MEMORY_RE.findall(text):
        size = int(length, 0) * {"": 1, "k": 1024, "m": 1024 * 1024}[unit.lower()]
        if FLASH_NAME_RE.search(name):
            flash += size
        elif RAM_NAME_RE.search(name):
            ram += size
    return flash, ram


def tier_for(flash, ram):
    """按 references/cpp/features.md §2：任一条件满足即归入较低等级。"""
    if (flash and flash <= TIER_T0_FLASH) or (ram and ram <= TIER_T0_RAM):
        return "T0"
    if flash >= TIER_T2_FLASH or ram >= TIER_T2_RAM:
        return "T2"
    return "T1"


def read_head(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read(MAX_READ)
    except OSError:
        return ""


def scan(root):
    scores = {}
    evidence = {}
    tooling = []
    ceedling = []
    content_reads = {}
    count = 0
    truncated = False
    lang = {"c": 0, "cpp": 0, "h": 0}
    cxx_std = set()
    zephyr_cpp = False
    libraries = set()
    cpputest = []
    memory = []
    extra_reads = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        rel_dir = Path(dirpath).relative_to(root)
        for name in sorted(filenames):
            count += 1
            if count > MAX_FILES:
                truncated = True
                break
            rel = (rel_dir / name).as_posix()
            if name in TOOLING and len(rel_dir.parts) <= 2:
                tooling.append({"file": rel, "kind": TOOLING[name]})
            for idx, (profile, weight, label, pred, content_re) in enumerate(NAME_RULES):
                if not pred(rel, name):
                    continue
                if content_re is not None:
                    if content_reads.get(idx, 0) >= CONTENT_RULE_LIMIT:
                        continue
                    content_reads[idx] = content_reads.get(idx, 0) + 1
                    try:
                        with open(Path(dirpath) / name, encoding="utf-8", errors="replace") as fh:
                            if not content_re.search(fh.read(MAX_READ)):
                                continue
                    except OSError:
                        continue
                key = (profile, label)
                ev = evidence.setdefault(profile, {})
                if key not in ev:
                    scores[profile] = scores.get(profile, 0) + weight
                    ev[key] = []
                if len(ev[key]) < 5:
                    ev[key].append(rel)
            suffix = Path(name).suffix
            if suffix in C_SUFFIXES:
                lang["c"] += 1
            elif suffix in CPP_SUFFIXES:
                lang["cpp"] += 1
            elif suffix in HEADER_SUFFIXES:
                lang["h"] += 1
            for lib, pred in CPP_LIBRARY_RULES:
                if pred(rel, name):
                    libraries.add(lib)
            if extra_reads < CONTENT_RULE_LIMIT * 4:
                path = Path(dirpath) / name
                if name == "CMakeLists.txt" or name.endswith(".cmake") or name in ("Makefile", "meson.build"):
                    extra_reads += 1
                    head = read_head(path)
                    for regex in CXX_STD_RES:
                        cxx_std.update(regex.findall(head))
                    if CPPUTEST_RE.search(head):
                        cpputest.append(rel)
                elif name == "prj.conf" or (name.endswith(".conf") and "boards" not in rel):
                    extra_reads += 1
                    head = read_head(path)
                    zephyr_cpp = zephyr_cpp or bool(ZEPHYR_CPP_RE.search(head))
                    cxx_std.update(ZEPHYR_STD_RE.findall(head))
                elif suffix == ".ld":
                    extra_reads += 1
                    flash, ram = parse_memory_regions(read_head(path))
                    if flash or ram:
                        memory.append({"file": rel, "flash_bytes": flash, "ram_bytes": ram,
                                       "tier": tier_for(flash, ram)})
                elif suffix in CPP_SUFFIXES and "test" in rel.lower() and len(cpputest) < 5:
                    extra_reads += 1
                    if CPPUTEST_RE.search(read_head(path)):
                        cpputest.append(rel)
            if name == "project.yml":
                try:
                    with open(Path(dirpath) / name, encoding="utf-8", errors="replace") as fh:
                        if re.search(r"^:project:", fh.read(MAX_READ), re.M):
                            ceedling.append(rel)
                except OSError:
                    pass
        if truncated:
            break

    # RTOS 项目通常也带启动文件和链接脚本；两者同时出现时以 mcu-rtos 为主。
    if scores.get("mcu-rtos") and scores.get("mcu-baremetal"):
        scores["mcu-rtos"] += scores["mcu-baremetal"]
        scores["mcu-baremetal"] = 0
    # Zephyr 自带 linker/startup，不应再判为裸机。
    if scores.get("zephyr", 0) >= 5:
        scores.pop("mcu-baremetal", None)

    ranked = sorted(((p, s) for p, s in scores.items() if s > 0), key=lambda x: -x[1])
    suggested = ranked[0][0] if ranked else None
    if suggested == "linux-userspace":
        tier = {"suggested": "T3", "basis": "linux-userspace profile"}
    elif suggested == "linux-kernel":
        tier = {"suggested": None, "basis": "C++ is not used in the Linux kernel"}
    elif memory:
        # 多个链接脚本（bootloader + app 等）时取 Flash 最大者，并保留全部明细供核对。
        main_script = max(memory, key=lambda m: m["flash_bytes"])
        tier = {"suggested": main_script["tier"], "basis": f"linker script {main_script['file']}",
                "linker_scripts": memory[:10]}
    else:
        tier = {"suggested": None, "basis": "no linker script MEMORY regions found; decide from the datasheet"}
    return {
        "root": str(root),
        "candidates": [
            {"profile": p, "score": s,
             "evidence": [{"signal": label, "files": files}
                          for (_, label), files in evidence.get(p, {}).items()]}
            for p, s in ranked
        ],
        "suggested": suggested,
        "languages": {"c_sources": lang["c"], "cpp_sources_and_headers": lang["cpp"],
                      "h_headers": lang["h"],
                      "cpp_standard": sorted(cxx_std, key=int),
                      "zephyr_config_cpp": zephyr_cpp,
                      "cpp_libraries": sorted(libraries)},
        "resource_tier": tier,
        "test_baseline_present": {"ceedling": ceedling, "cpputest": sorted(set(cpputest))[:5]},
        "project_rules_and_tooling": tooling,
        "files_scanned": min(count, MAX_FILES),
        "truncated": truncated,
        "note": "Heuristic only. Verify evidence; mixed repos need per-directory profiles "
                "(run again on subdirectories). Project rules override profile defaults.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("root", nargs="?", default=".", help="仓库或子目录")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 2
    print(json.dumps(scan(root), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
