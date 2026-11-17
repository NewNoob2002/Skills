#!/usr/bin/env python3
"""显式范围的布局/命名与默认 Doxygen 存在性检查。退出码 0/1/2/3 = PASS/违规/配置/缺工具。"""

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
EXCLUDED = {"third_party", "vendor", "generated", "sdk", "platform", "middleware", ".git"}
FUNCTIONS = {"FunctionDecl", "CXXMethodDecl", "CXXConstructorDecl", "CXXDestructorDecl",
             "CXXConversionDecl"}


class ConfigError(Exception):
    pass


class MissingTool(Exception):
    pass


def parse_json(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise ConfigError(f"invalid JSON: {error}") from error


def run(args, **kwargs):
    return subprocess.run([str(a) for a in args], text=True, capture_output=True, check=False, **kwargs)


def tool(name, major):
    binary = shutil.which(name)
    if not binary:
        raise MissingTool(name)
    version = run([binary, "--version"])
    if version.returncode or not re.search(rf"version\s+{major}\.", version.stdout):
        raise ConfigError(f"{name}: expected LLVM major {major}: {version.stdout.strip()}")
    return binary


def files(root, patterns, suffixes):
    if not isinstance(patterns, list) or any(not isinstance(p, str) for p in patterns):
        raise ConfigError("file ranges must be arrays of relative globs")
    selected = set()
    for pattern in patterns:
        if Path(pattern).is_absolute() or ".." in Path(pattern).parts:
            raise ConfigError(f"range outside root: {pattern}")
        for path in root.glob(pattern):
            if not path.is_file():
                continue
            if not path.resolve().is_relative_to(root):
                raise ConfigError(f"symlink outside root: {path}")
            resolved = path.resolve().relative_to(root)
            if (set(path.relative_to(root).parts) | set(resolved.parts)) & EXCLUDED:
                raise ConfigError(f"excluded code selected: {path}")
            if path.suffix not in suffixes:
                raise ConfigError(f"wrong language range: {path}")
            selected.add(path.resolve())
    return sorted(selected)


def compile_entries(root, database, sources):
    if database.name != "compile_commands.json":
        raise ConfigError("compile database must be named compile_commands.json")
    entries = parse_json(database.read_text())
    found = {}
    for entry in entries:
        directory = Path(entry["directory"])
        if not directory.is_absolute():
            raise ConfigError("compile database directory must be absolute")
        path = (directory / entry["file"]).resolve()
        if path in sources:
            if path in found:
                raise ConfigError(f"ambiguous compile commands: {path}")
            args = entry.get("arguments") or shlex.split(entry["command"])
            if not args or not directory.is_dir():
                raise ConfigError(f"invalid compile command: {path}")
            found[path] = (directory, args)
    missing = set(sources) - found.keys()
    if missing:
        raise ConfigError("no compile command: " + ", ".join(str(p) for p in sorted(missing)))
    return found


def ast_args(args):
    # 沿用真实命令的语言、宏和 include；只剔除输出/依赖文件参数，不执行 shell。
    result = []
    skip = False
    for arg in args[1:]:
        if skip:
            skip = False
        elif arg in {"-o", "-MF", "-MT", "-MQ", "--serialize-diagnostics"}:
            skip = True
        elif arg not in {"-c", "-MD", "-MMD", "-MP"}:
            result.append(arg)
    return result + ["-fsyntax-only", "-Xclang", "-ast-dump=json"]


def documented_functions(ast, directory, owned, translation_unit):
    records = []
    current_file = None

    def walk(node):
        nonlocal current_file
        loc = node.get("loc", {})
        # 宏展开的声明不在此检查的证明范围内；人工审查。
        if loc.get("file"):
            current_file = (directory / loc["file"]).resolve()
        path = current_file
        children = node.get("inner", [])
        if (node.get("kind") in FUNCTIONS and not node.get("isImplicit")
                and "expansionLoc" not in loc and path in owned and "offset" in loc):
            key = node.get("mangledName") or (path, node.get("name"), node.get("type", {}).get("qualType"))
            # 不同翻译单元的内部链接函数不是同一个接口，不能共享文档证明。
            if ((node.get("kind") == "FunctionDecl" and node.get("storageClass") == "static")
                    or "_GLOBAL__N_" in str(key)):
                key = (translation_unit, key)
            has_doc = any(n.get("kind") == "FullComment" for n in children)
            records.append((key, has_doc, path, node.get("name"), loc.get("line", "?")))
        for child in children:
            walk(child)
    walk(ast)
    return records


def check_docs(root, entries, owned, major):
    records = []
    for path, (directory, args) in entries.items():
        compiler = tool("clang" if path.suffix == ".c" else "clang++", major)
        proc = run([compiler, *ast_args(args)], cwd=directory)
        if proc.returncode:
            raise ConfigError(f"DOC-AST failed for {path}:\n{proc.stderr}")
        records.extend(documented_functions(parse_json(proc.stdout), directory, owned, path))
    documented = {key for key, doc, *_ in records if doc}
    missing = {(str(path.relative_to(root)), name, line) for key, doc, path, name, line in records
               if key not in documented}
    for path, name, line in sorted(missing, key=str):
        print(f"DOC-001 {path}:{line}: missing Doxygen block for {name}")
    return bool(missing)


def verify_tidy(tidy, path, config):
    # 旧方案同时列新旧检查名以支持 LLVM 17..23；23 移除了 hicpp 别名。
    proc = run([tidy, "--verify-config", *config, path, "--", "-x", "c++"])
    output = proc.stdout + proc.stderr
    if not proc.returncode:
        return
    remainder = re.sub(r"[^\n]*warning: unknown check 'hicpp-signed-bitwise' \[-verify-config\]\n?",
                       "", output).strip()
    checks = run([tidy, "--list-checks", *config, path, "--", "-x", "c++"])
    if remainder or checks.returncode or "    bugprone-signed-bitwise\n" not in checks.stdout:
        raise ConfigError(output)
    print("CONFIG_COMPAT: removed hicpp-signed-bitwise alias; bugprone-signed-bitwise is enabled")


def check(root, manifest):
    if not isinstance(manifest, dict):
        raise ConfigError("manifest must be an object")
    allowed = {"version", "llvm_major", "style", "cpp", "cpp_headers", "c", "compile_commands",
               "doxygen", "doc_headers"}
    if set(manifest) - allowed or manifest.get("version") != 1:
        raise ConfigError("unknown manifest keys or version (expected 1)")
    doxygen = manifest.get("doxygen", True)
    if not isinstance(doxygen, bool):
        raise ConfigError("doxygen must be a boolean")
    major = manifest.get("llvm_major", 23)
    if not isinstance(major, int) or major < 17:
        raise ConfigError("llvm_major must be an integer >= 17")
    cpp = files(root, manifest.get("cpp", []), {".cpp", ".cc", ".cxx"})
    headers = files(root, manifest.get("cpp_headers", []), {".h", ".hpp", ".hh", ".hxx", ".ipp"})
    c_files = files(root, manifest.get("c", []), {".c", ".h"})
    doc_headers = files(root, manifest.get("doc_headers", []), {".h", ".hpp", ".hh", ".hxx", ".ipp"})
    if set(headers) & set(c_files):
        raise ConfigError("header selected for both C and C++ layout")
    if not cpp and not headers and not c_files:
        print("PASS EMPTY: explicit ranges select no files; no tools invoked")
        return 0
    style = manifest.get("style", "project")
    if style == "project":
        format_style = "file"  # 从每个文件查找最近的项目配置。
        tidy_config = []
        for path in cpp + headers:
            for name in (".clang-format", ".clang-tidy"):
                if not any((p / name).is_file() for p in [path.parent, *path.parents]
                           if p == root or p.is_relative_to(root)):
                    raise ConfigError(f"missing project {name} for {path}")
    elif style in {"default-cpp", "readable-cpp"}:
        config = SKILL / "assets/cpp"
        if style == "readable-cpp":
            config /= style
        # 既有项目配置优先；显式风格仅作为无配置目录的 fallback。
        for path in cpp + headers:
            if any((p / name).exists() for p in [path.parent, *path.parents]
                   if p == root or p.is_relative_to(root)
                   for name in (".clang-format", ".clang-tidy")):
                raise ConfigError("project config exists: use style=project (no override)")
        format_style = f"file:{config / '.clang-format'}"
        tidy_config = [f"--config-file={config / '.clang-tidy'}"]
    else:
        raise ConfigError(f"unknown style: {style}")
    failed = False
    if cpp or headers:
        formatter = tool("clang-format", major)
        tidy = tool("clang-tidy", major) if cpp else None
        # 解析配置失败与代码排版不一致分开报告。
        for path in cpp + headers:
            validate = run([formatter, f"--style={format_style}", "--fallback-style=none",
                            f"--assume-filename={path}", "--dump-config"], cwd=root)
            if validate.returncode:
                raise ConfigError(validate.stderr)
        entries = compile_entries(root, root / manifest["compile_commands"], cpp) if cpp else {}
        if tidy:
            for path in cpp:
                verify_tidy(tidy, path, tidy_config)
        proc = run([formatter, f"--style={format_style}", "--fallback-style=none",
                    "--dry-run", "--Werror", *cpp, *headers], cwd=root)
        if proc.returncode:
            print("CPPF-001 layout:\n" + proc.stdout + proc.stderr)
            failed = True
        for path in cpp:
            proc = run([tidy, "--quiet", "--warnings-as-errors=*", *tidy_config,
                        "-p", (root / manifest["compile_commands"]).parent, path], cwd=root)
            output = proc.stdout + proc.stderr
            if "[clang-diagnostic-error]" in output or "Error while processing" in output:
                raise ConfigError(output)
            if proc.returncode:
                if not re.search(r"\[(?:readability|bugprone|cppcoreguidelines|modernize|performance|misc|hicpp)-", output):
                    raise ConfigError(output)
                print("CPPF-002 clang-tidy:\n" + output)
                failed = True
    if c_files:
        # C 门禁不接受空参数（其原行为是全仓扫描）。.h 的语言由清单显式决定。
        formatter = tool("clang-format", major)
        tidy = tool("clang-tidy", major)
        for path in c_files:
            validate = run([formatter, "--style=file", f"--assume-filename={path}",
                            "--dump-config"], cwd=root)
            if validate.returncode:
                raise ConfigError(validate.stderr)
            verify_tidy(tidy, path, [])
        database = root / manifest["compile_commands"]
        compile_entries(root, database, [p for p in c_files if p.suffix == ".c"])
        proc = run(["sh", SKILL / "scripts/barrc/check.sh", *c_files], cwd=root,
                   env=dict(os.environ, BARRC_COMPILE_DB=str(database.parent)))
        output = proc.stdout + proc.stderr
        print(output, end="")
        if proc.returncode:
            if (proc.returncode != 1 or "[clang-diagnostic-error]" in output
                    or "Error while processing" in output):
                raise ConfigError("C gate configuration/tool failure")
            failed = True
    if doxygen:
        sources = cpp + [p for p in c_files if p.suffix == ".c"]
        entries = compile_entries(root, root / manifest["compile_commands"], sources)
        failed |= check_docs(root, entries, set(cpp + headers + c_files + doc_headers), major)
        print("DOC-001: only associated block presence checked; English/semantics require review")
    if not failed:
        print("PASS style gate")
    return int(failed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        return check(args.root.resolve(), parse_json(args.manifest.read_text()))
    except MissingTool as error:
        print(f"TOOL_MISSING: {error}", file=sys.stderr)
        return 3
    except (ConfigError, OSError, ValueError, KeyError, TypeError) as error:
        print(f"CONFIG_ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
