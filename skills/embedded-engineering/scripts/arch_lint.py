#!/usr/bin/env python3
"""MCU 分层架构依赖检查（只读）。

检查项：
  1. #include 方向是否符合层规则（assets/arch_layers.json）。
  2. 受限层中是否包含厂商/RTOS 头文件。
  3. 受限层中是否出现 HAL 调用或 PERIPH->REG 形式的寄存器访问。
  4. 指定层内部（默认 module/）的子模块之间是否有循环依赖。

这是基于正则的启发式检查，不做完整预处理：条件编译分支中的 #include 都会被计入，
宏拼接的 include 无法识别。结果用于定位问题，最终判断仍需人工审查。

退出码：0 无违规；1 有违规；2 参数或配置错误。仅依赖 Python 标准库（3.8+）。
"""

import argparse
import fnmatch
import json
import os
import re
import sys
from pathlib import Path, PurePosixPath

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "assets" / "arch_layers.json"
# C 与 C++ 源文件、头文件、模板实现文件都参与分层检查。
SOURCE_SUFFIXES = {".c", ".h", ".cpp", ".hpp", ".cc", ".hh", ".cxx", ".hxx", ".ipp", ".inl"}
INCLUDE_RE = re.compile(r'^\s*#\s*include\s*([<"])([^>"]+)[>"]', re.MULTILINE)
# 注释与字符串替换为等长空白，保留换行以便行号仍然准确。
COMMENT_OR_STRING_RE = re.compile(
    r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'',
    re.DOTALL,
)
# 只去注释（保留字符串），用于扫描 #include "x.h"。
COMMENT_RE = re.compile(r'//[^\n]*|/\*.*?\*/', re.DOTALL)


def blank_out(match):
    text = match.group(0)
    return re.sub(r"[^\n]", " ", text)


def strip_comments_and_strings(text):
    return COMMENT_OR_STRING_RE.sub(blank_out, text)


def strip_comments(text):
    return COMMENT_RE.sub(blank_out, text)


def glob_match(rel_path, patterns):
    """rel_path 为 POSIX 相对路径；'dir/**' 匹配该目录下任意深度。"""
    for pattern in patterns:
        if pattern.endswith("/**"):
            prefix = pattern[:-3]
            if prefix.startswith("**/"):
                needle = "/" + prefix[3:] + "/"
                if needle in "/" + rel_path + "/":
                    return True
            elif rel_path == prefix or rel_path.startswith(prefix + "/"):
                return True
        elif fnmatch.fnmatch(rel_path, pattern):
            return True
    return False


def load_config(path):
    try:
        with open(path, encoding="utf-8") as handle:
            config = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"error: cannot load config {path}: {exc}") from exc

    names = set()
    for layer in config.get("layers", []):
        for key in ("name", "globs", "allow"):
            if key not in layer:
                raise SystemExit(f"error: layer entry missing '{key}': {layer}")
        names.add(layer["name"])
    for layer in config["layers"]:
        unknown = set(layer["allow"]) - names
        if unknown:
            raise SystemExit(f"error: layer {layer['name']} allows unknown layers {sorted(unknown)}")
        for ref in layer.get("forbid_includes", []):
            if ref.startswith("@") and ref[1:] not in config.get("include_sets", {}):
                raise SystemExit(f"error: unknown include set {ref} in layer {layer['name']}")
        for ref in layer.get("forbid_code", []):
            if ref not in config.get("code_patterns", {}):
                raise SystemExit(f"error: unknown code pattern {ref} in layer {layer['name']}")
    return config


def collect_files(root, excludes):
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = PurePosixPath(Path(dirpath).relative_to(root).as_posix())
        # 提前剪枝被排除的目录，避免遍历 build/ 等大目录。
        dirnames[:] = [
            d for d in dirnames
            if not glob_match(str(rel_dir / d) if str(rel_dir) != "." else d, excludes)
        ]
        for name in filenames:
            if Path(name).suffix not in SOURCE_SUFFIXES:
                continue
            rel = str(rel_dir / name) if str(rel_dir) != "." else name
            if not glob_match(rel, excludes):
                files.append(rel)
    return sorted(files)


def layer_of(rel_path, config):
    for layer in config["layers"]:
        if glob_match(rel_path, layer["globs"]):
            return layer
    return None


def submodule_of(rel_path, layer):
    """module/motor/motor.c -> module/motor；用于循环依赖检查。"""
    for pattern in layer["globs"]:
        if pattern.endswith("/**"):
            prefix = pattern[:-3]
            if rel_path.startswith(prefix + "/"):
                rest = rel_path[len(prefix) + 1:]
                head = rest.split("/", 1)[0]
                if "/" in rest:
                    return f"{prefix}/{head}"
                return f"{prefix}/{Path(head).stem}"
    return rel_path


def resolve_include(include, including_file, all_files, by_basename):
    """返回项目内可能被包含的文件列表；为空表示外部头文件（SDK、标准库）。"""
    including_dir = PurePosixPath(including_file).parent
    direct = str(PurePosixPath(os.path.normpath(str(including_dir / include))).as_posix())
    if direct in all_files:
        return [direct]
    if include in all_files:
        return [include]
    candidates = by_basename.get(PurePosixPath(include).name, [])
    suffix = "/" + include
    exact = [c for c in candidates if c.endswith(suffix) or c == include]
    return exact or candidates


def expand_patterns(refs, config):
    patterns = []
    for ref in refs:
        if ref.startswith("@"):
            patterns.extend(config["include_sets"][ref[1:]])
        else:
            patterns.append(ref)
    return patterns


def find_cycles(graph):
    """Tarjan 强连通分量；仅返回多个子模块间的环，同子模块内部依赖不算环。"""
    index = {}
    lowlink = {}
    stack = []
    on_stack = set()
    result = []
    counter = [0]

    def visit(node):
        index[node] = lowlink[node] = counter[0]
        counter[0] += 1
        stack.append(node)
        on_stack.add(node)
        for succ in graph.get(node, ()):
            if succ not in index:
                visit(succ)
                lowlink[node] = min(lowlink[node], lowlink[succ])
            elif succ in on_stack:
                lowlink[node] = min(lowlink[node], index[succ])
        if lowlink[node] == index[node]:
            component = []
            while True:
                item = stack.pop()
                on_stack.discard(item)
                component.append(item)
                if item == node:
                    break
            if len(component) > 1:
                result.append(sorted(component))

    sys.setrecursionlimit(max(1000, len(graph) * 4))
    for node in sorted(graph):
        if node not in index:
            visit(node)
    return result


def lint(root, config):
    excludes = config.get("exclude", [])
    shared = config.get("shared", [])
    files = collect_files(root, excludes)
    all_files = set(files)
    by_basename = {}
    for rel in files:
        by_basename.setdefault(PurePosixPath(rel).name, []).append(rel)

    code_res = {k: re.compile(v) for k, v in config.get("code_patterns", {}).items()}
    cycle_layers = set(config.get("cycle_check_layers", []))
    violations = []
    graph = {}
    layered = 0

    for rel in files:
        layer = layer_of(rel, config)
        if layer is None:
            continue
        layered += 1
        try:
            text = (root / rel).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            violations.append({"file": rel, "line": 0, "kind": "io_error", "detail": str(exc)})
            continue

        forbidden = expand_patterns(layer.get("forbid_includes", []), config)
        no_comments = strip_comments(text)
        for match in INCLUDE_RE.finditer(no_comments):
            include = match.group(2).strip()
            line = no_comments.count("\n", 0, match.start()) + 1
            targets = resolve_include(include, rel, all_files, by_basename)
            target_layers = []
            if targets:
                for target in targets:
                    if glob_match(target, shared):
                        target_layers.append(None)
                        continue
                    tl = layer_of(target, config)
                    target_layers.append(tl["name"] if tl else None)
                allowed = [t is None or t in layer["allow"] for t in target_layers]
                if not any(allowed):
                    violations.append({
                        "file": rel, "line": line, "kind": "layer_dependency",
                        "detail": f'{layer["name"]} -> {"/".join(sorted(set(filter(None, target_layers))))} via "{include}"',
                    })
                if layer["name"] in cycle_layers:
                    src = submodule_of(rel, layer)
                    for target, tl in zip(targets, target_layers):
                        if tl == layer["name"]:
                            dst = submodule_of(target, layer)
                            if dst != src:
                                graph.setdefault(src, set()).add(dst)
                    graph.setdefault(src, set())
            # 除非每个解析结果都位于当前层显式允许的层（shared 不算），否则都要检查禁止头模式
            if not (targets and all(t in layer["allow"] for t in target_layers)):
                base = PurePosixPath(include).name
                hit = next((p for p in forbidden
                            if fnmatch.fnmatch(include, p) or fnmatch.fnmatch(base, p)), None)
                if hit:
                    violations.append({
                        "file": rel, "line": line, "kind": "forbidden_include",
                        "detail": f'{layer["name"]} must not include "{include}" (matches {hit})',
                    })
        if layer.get("forbid_code"):
            code = strip_comments_and_strings(text)
            for ref in layer["forbid_code"]:
                for match in code_res[ref].finditer(code):
                    line = code.count("\n", 0, match.start()) + 1
                    violations.append({
                        "file": rel, "line": line, "kind": ref,
                        "detail": f'{layer["name"]}: "{match.group(0).strip()}"',
                    })

    for cycle in find_cycles(graph):
        violations.append({
            "file": cycle[0], "line": 0, "kind": "cycle",
            "detail": " <-> ".join(cycle),
        })

    return {"root": str(root), "files_scanned": len(files), "files_layered": layered,
            "violations": violations}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("root", nargs="?", default=".", help="固件仓库根目录")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="层规则 JSON")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 2
    try:
        config = load_config(args.config)
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        return 2

    report = lint(root, config)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        for v in report["violations"]:
            print(f'{v["file"]}:{v["line"]}: [{v["kind"]}] {v["detail"]}')
        print(f'arch_lint: {len(report["violations"])} violation(s); '
              f'{report["files_layered"]}/{report["files_scanned"]} files mapped to layers')
    if report["files_layered"] == 0:
        # 没有任何文件落入层，多半是目录结构与配置不符；不能当作“通过”。
        print("arch_lint: no file matched any layer; check --config globs against the repo layout",
              file=sys.stderr)
        return 2
    return 1 if report["violations"] else 0


if __name__ == "__main__":
    sys.exit(main())
