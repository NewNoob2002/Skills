#!/usr/bin/env python3
"""Agent Skill 自检：frontmatter、引用完整性、资源可达性、脚本与数据文件、打包卫生。

用法：
  python3 tools/validate_skill.py [SKILL_DIR ...] [--doc FILE ...] [--config FILE | --no-config] [--json]

不带参数时检查 skills/ 下每个含 SKILL.md 的目录，以及仓库根的 README.md。
状态：PASS；FAIL（有 error 级发现）；NOT_RUN（前提不存在，如没有该文件或缺少外部工具）；
BLOCKED（依赖的检查失败而无法执行）。NOT_RUN 与 BLOCKED 都不是通过。
退出码：0 没有 FAIL；1 至少一项 FAIL；2 用法、配置或环境错误（如缺少 PyYAML）。依赖标准库与 PyYAML。

检查项（规则依据 https://agentskills.io/specification 与 Codex agents/openai.yaml 文档）：
  frontmatter  name/description/compatibility/metadata 约束，name 与目录同名，SKILL.md 行数预算
  links        Markdown 相对链接存在，且不逃出技能目录（安装时只复制技能目录）
  paths        反引号中的 scripts/ assets/ references/ agents/ 路径存在（相对技能根）
  sections     “§N” 引用指向目标文件中存在的 “## N.” 标题
  reachability references/ 下每个文件都由 SKILL.md 直接链接（规范建议引用只保持一层）
  orphans      scripts/、assets/ 下每个顶层条目都在技能文档中被提到
  scripts      带 shebang 的脚本可执行；Python 可编译；shell 通过 -n 语法检查
  data-json    *.json 可解析
  data-yaml    *.yml/*.yaml/.clang-format/.clang-tidy 可解析
  openai-yaml  agents/openai.yaml 字段、图标路径、颜色格式
  rules        standards/rules.yaml 结构、ID 唯一、profile/来源/工具已声明、ref 章节存在、冲突双向登记；
               文档中以反引号引用的 Rule ID 必须存在
  profiles     profiles/<id>.yaml 与 rules.yaml 声明的 profile 一一对应，引用与门禁工具存在
  hygiene      无 __pycache__/*.pyc/build 目录/编辑器残留、无超大文件、无指向技能外的符号链接
"""

from __future__ import annotations

import argparse
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml  # type: ignore[import-not-found]
except ImportError:
    yaml = None  # type: ignore[assignment]
REPO = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = Path(__file__).resolve().with_name("validate_skill.json")

PASS, FAIL, NOT_RUN, BLOCKED = "PASS", "FAIL", "NOT_RUN", "BLOCKED"

FRONTMATTER_KEYS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SPEC_MAX_SKILL_LINES = 500  # 规范建议值；项目可在配置里收紧
SKILL_ROOT_DIRS = ("scripts", "assets", "references", "agents", "standards", "profiles")
HYGIENE_DIRS = {"__pycache__", ".git", ".pytest_cache", ".mypy_cache", "node_modules"}
HYGIENE_DIR_RE = re.compile(r"^build(?:-.*)?$")
HYGIENE_FILE_RE = re.compile(r"(?:\.pyc|\.pyo|\.swp|\.swo|~|\.orig|\.rej)$|^\.DS_Store$")
DEFAULT_MAX_FILE_BYTES = 1 << 20
YAML_FILE_NAMES = {".clang-format", ".clang-tidy"}
OPENAI_SCHEMA = {
    "interface": {"display_name", "short_description", "icon_small", "icon_large", "brand_color",
                  "default_prompt"},
    "policy": {"allow_implicit_invocation"},
    "dependencies": {"tools"},
}
OPENAI_TOOL_KEYS = {"type", "value", "description", "transport", "url"}
OPENAI_TOOL_TYPES = {"mcp"}  # Codex 文档示例中唯一出现的类型；其他值只提示
CONFIG_KEYS = {"max_skill_md_lines", "max_file_bytes", "external_paths"}
TRIGGER_HINT_RE = re.compile(r"use (?:it )?when|时使用|适用于|用于", re.IGNORECASE)


# --------------------------------------------------------------------------- 结果模型

@dataclass
class Finding:
    level: str  # "error" 计入 FAIL；"warn" 只提示
    file: str
    line: int | None
    message: str


@dataclass
class Check:
    id: str
    findings: list[Finding] = field(default_factory=list)
    not_run: str | None = None   # 前提不存在（如没有该文件）而未执行
    blocked: str | None = None   # 依赖的其他检查失败而无法执行

    def error(self, file: str, line: int | None, message: str) -> None:
        self.findings.append(Finding("error", file, line, message))

    def warn(self, file: str, line: int | None, message: str) -> None:
        self.findings.append(Finding("warn", file, line, message))

    @property
    def status(self) -> str:
        if any(f.level == "error" for f in self.findings):
            return FAIL
        if self.blocked:
            return BLOCKED
        if self.not_run:
            return NOT_RUN
        return PASS

    def to_json(self) -> dict:
        return {"id": self.id, "status": self.status, "not_run_reason": self.not_run,
                "blocked_reason": self.blocked,
                "findings": [f.__dict__ for f in self.findings]}


# --------------------------------------------------------------------------- YAML 加载（基于 PyYAML）

class YamlSyntaxError(ValueError):
    """确定的 YAML 错误：语法错误、重复键、超长整数，或 YAML 1.1/1.2 读法不同的未加引号标量。"""

    def __init__(self, message: str, lineno: int | None = None):
        super().__init__(message)
        self.lineno = lineno


# YAML 1.1（PyYAML 等）与 1.2（多数 JS/Go/Rust 解析器）读法不同的 plain scalar：必须加引号
_AMBIGUOUS_RES = (
    # 1.1 布尔；单字母 y/n 不计入：PyYAML 与 1.2 解析器都读作字符串，计入会让单字母键全部报错
    re.compile(r"^(?:yes|Yes|YES|no|No|NO|on|On|ON|off|Off|OFF)$"),
    re.compile(r"^[-+]?0[0-9_]+$"),                                          # 1.1 八进制 012
    re.compile(r"^[-+]?0b[01_]+$"),                                           # 1.1 二进制
    re.compile(r"^0o[0-7]+$"),                                                # 1.2 八进制，1.1 为字符串
    re.compile(r"^[-+]?[0-9][0-9_]*_[0-9_]*(?:\.[0-9_]*)?$"),                 # 1.1 数字下划线
    re.compile(r"^[-+]?[1-9][0-9_]*(?::[0-5]?[0-9])+(?:\.[0-9_]*)?$"),        # 1.1 六十进制
    re.compile(r"^[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}(?:[Tt ].*)?$"),              # 1.1 时间戳
    re.compile(r"^[-+]?[0-9]+[eE][-+]?[0-9]+$"),                              # 1.2 浮点，1.1 为字符串
)


def _check_ambiguous_scalars(node, seen: set[int] | None = None) -> None:
    if node is None:
        return
    if seen is None:
        seen = set()
    if id(node) in seen:
        return
    seen.add(id(node))
    if isinstance(node, yaml.ScalarNode):
        if node.style is None or node.style == "":
            for pattern in _AMBIGUOUS_RES:
                if pattern.match(node.value):
                    lineno = node.start_mark.line + 1
                    raise YamlSyntaxError(
                        f"line {lineno}: {node.value!r} is read differently by YAML 1.1 and 1.2 parsers; quote it",
                        lineno=lineno,
                    )
    elif isinstance(node, yaml.SequenceNode):
        for child in node.value:
            _check_ambiguous_scalars(child, seen)
    elif isinstance(node, yaml.MappingNode):
        for key_node, val_node in node.value:
            _check_ambiguous_scalars(key_node, seen)
            _check_ambiguous_scalars(val_node, seen)


def _make_strict_loader():
    """拒绝同一映射内的重复显式键，同时保留 SafeLoader 对 merge key（<<）展开和显式覆盖的语义。"""

    base_loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)

    class StrictLoader(base_loader):
        def construct_object(self, node, deep=False):
            try:
                return super().construct_object(node, deep=deep)
            except ValueError as exc:
                raise yaml.constructor.ConstructorError(
                    None, None, str(exc), getattr(node, "start_mark", None)
                ) from None

        def flatten_mapping(self, node):
            explicit = []
            seen_merge = False
            for key_node, _ in node.value:
                if key_node.tag == "tag:yaml.org,2002:merge":
                    if seen_merge:
                        raise yaml.constructor.ConstructorError(
                            None, None, "duplicate key '<<'", key_node.start_mark
                        )
                    seen_merge = True
                else:
                    explicit.append(key_node)
            super().flatten_mapping(node)
            keys = []
            for key_node in explicit:
                key = self.construct_object(key_node, deep=True)
                if key in keys:
                    raise yaml.constructor.ConstructorError(
                        None, None, f"duplicate key {key!r}", key_node.start_mark
                    )
                keys.append(key)

    return StrictLoader


def _yaml_syntax_error(exc: Exception, text: str) -> YamlSyntaxError:
    mark = getattr(exc, "problem_mark", None) or getattr(exc, "context_mark", None)
    if mark is not None:
        lineno = mark.line + 1
    elif (pos := getattr(exc, "position", None)) is not None:
        lineno = text.count("\n", 0, pos) + 1
    else:
        lineno = 1
    return YamlSyntaxError(f"line {lineno}: {exc}", lineno=lineno)


def _strict_pyyaml_load(text: str, all_documents: bool = False):
    if yaml is None:
        raise RuntimeError("PyYAML is required")
    loader_cls = _make_strict_loader()
    try:
        if all_documents:
            return list(yaml.load_all(text, Loader=loader_cls))  # noqa: S506 - 派生自 SafeLoader
        return yaml.load(text, Loader=loader_cls)  # noqa: S506 - 派生自 SafeLoader
    except (yaml.YAMLError, ValueError) as exc:
        raise _yaml_syntax_error(exc, text) from None


def load_yaml(text: str):
    """用 PyYAML 解析单文档 YAML，拒绝 YAML 1.1/1.2 歧义 plain 标量与重复键。"""
    if yaml is None:
        raise RuntimeError("PyYAML is required")
    loader_cls = _make_strict_loader()
    try:
        loader = loader_cls(text)
        try:
            root = loader.get_single_node()
            _check_ambiguous_scalars(root)
            return None if root is None else loader.construct_document(root)
        finally:
            loader.dispose()
    except YamlSyntaxError:
        raise
    except (yaml.YAMLError, ValueError) as exc:
        raise _yaml_syntax_error(exc, text) from None
def sorted_keys(keys) -> list:
    """YAML 键可能混有 int/str/None，排序时统一按 str 比较，避免 TypeError。"""
    return sorted(keys, key=lambda k: (type(k).__name__, str(k)))


# --------------------------------------------------------------------------- Markdown 扫描

FENCE_RE = re.compile(r"^\s*(```+|~~~+)")
CODE_SPAN_RE = re.compile(r"`[^`\n]+`")
LINK_RE = re.compile(r"!?\[(?:[^\]\\]|\\.)*\]\(\s*<?([^)\s>]+)>?(?:\s+[\"'][^)]*[\"'])?\s*\)")
# 引用式链接：定义 [label]: target；使用 [text][label]、[label][] 与已定义时的 [label] 简写
REF_DEF_RE = re.compile(r"^ {0,3}\[([^\]]+)\]:\s*<?([^\s>]+)>?(?:\s+.*)?$")
REF_FULL_RE = re.compile(r"!?\[((?:[^\]\\]|\\.)*)\]\[([^\]]*)\]")
REF_SHORT_RE = re.compile(r"!?\[((?:[^\]\\]|\\.)+)\](?!\(|\[)")
SECTION_HEADING_RE = re.compile(r"^#{1,6}\s+(\d+)(?=[.、:：)）\s]|$)")
_FILE_REF = (r"(?:\[[^\]]*\]\(([^)\s#]+\.md)(?:#[^)]*)?\)"
             r"|`([^`\s]+\.md)`"
             r"|(?<![\w/.-])((?:[\w.-]+/)*[\w-]+\.md)"
             r"|\[((?:[^\]\\]|\\.)*)\]\[([^\]]*)\]"
             r"|\[((?:[^\]\\]|\\.)+)\](?!\(|\[))")
# 文件引用与 § 之间允许少量连接词（“[x](a.md) 的 §2”）
SECTION_REF_RE = re.compile(_FILE_REF + r"?\s*(?:的|中的|中|里的|里)?\s*(§\d+(?:\s*(?:[、,，/–—~-]|和|与|及|至)\s*§?\d+)*)")
AMBIGUOUS_SECTION_PREFIX_RE = re.compile(r"[A-Za-z0-9_./`-]*[A-Za-z_./`-][A-Za-z0-9_./`-]*\s*(?:的|中的|中|里的|里)?\s*$")
URL_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


def prose_lines(text: str):
    """逐行产出 (行号, 内容)，跳过围栏代码块（代码块中的 # 注释不是标题，路径也不是引用）。"""
    fence = None
    for no, line in enumerate(text.splitlines(), 1):
        m = FENCE_RE.match(line)
        if m:
            marker = m.group(1)
            if fence is None:
                fence = marker[0] * 3
            elif line.strip().startswith(fence):
                fence = None
            continue
        if fence is None:
            yield no, line


def blank_code_spans(line: str) -> str:
    return CODE_SPAN_RE.sub(lambda m: " " * len(m.group(0)), line)


def read_text_or_none(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def normalize_label(label: str) -> str:
    return " ".join(label.split()).casefold()


def section_numbers(text: str) -> set[int]:
    return {int(m.group(1)) for _, line in prose_lines(text) if (m := SECTION_HEADING_RE.match(line))}


def is_external(target: str) -> bool:
    return bool(URL_SCHEME_RE.match(target)) or target.startswith(("//", "#"))


def inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


# --------------------------------------------------------------------------- 引用检查（技能与仓库文档共用）

@dataclass
class RefContext:
    """一份 Markdown 的引用解析上下文。"""
    rel_base: Path            # 报告用的相对路径基准
    skill_roots: list[Path]   # 反引号路径按这些技能根解析
    confine: Path | None      # 链接不得逃出的目录（技能文件为技能根；仓库文档为 None）
    local_dirs: bool          # True：首段为文档同级目录的反引号路径按文档目录解析（仓库文档）
    external_paths: set[str]


def _collect_ref_defs(lines: list[tuple[int, str]]) -> tuple[dict[str, str], set[int]]:
    definitions: dict[str, str] = {}
    def_lines: set[int] = set()
    for no, line in lines:
        m = REF_DEF_RE.match(line)
        if m:
            definitions.setdefault(normalize_label(m.group(1)), m.group(2))
            def_lines.add(no)
    return definitions, def_lines


def check_links(md: Path, text: str, ctx: RefContext, check: Check, linked: set[Path] | None = None) -> None:
    rel = str(md.relative_to(ctx.rel_base))

    def verify(target: str, no: int, record_reachability: bool) -> Path | None:
        if is_external(target):
            return None
        path_part = target.split("#", 1)[0]
        if not path_part:
            return None
        dest = md.parent / path_part
        if not dest.exists():
            check.error(rel, no, f"broken link: {target}")
            return None
        if ctx.confine is not None and not inside(dest, ctx.confine):
            check.error(rel, no, f"link escapes skill directory: {target}")
            return None
        resolved = dest.resolve()
        if record_reachability and linked is not None:
            linked.add(resolved)
        return resolved

    lines = list(prose_lines(text))
    definitions, def_lines = _collect_ref_defs(lines)
    valid_defs: dict[str, Path] = {}
    for no, line in lines:
        m = REF_DEF_RE.match(line)
        if m:
            label = normalize_label(m.group(1))
            resolved = verify(m.group(2), no, record_reachability=False)
            if resolved is not None and label not in valid_defs:
                valid_defs[label] = resolved
    for no, line in lines:
        if no in def_lines:
            continue
        scan = blank_code_spans(line)
        for m in LINK_RE.finditer(scan):
            verify(m.group(1), no, record_reachability=True)
        scan = LINK_RE.sub(lambda m: " " * len(m.group(0)), scan)
        for m in REF_FULL_RE.finditer(scan):
            label = normalize_label(m.group(2) or m.group(1))
            if label not in definitions:
                check.error(rel, no, f"undefined link reference: [{m.group(2) or m.group(1)}]")
            elif linked is not None and label in valid_defs:
                linked.add(valid_defs[label])
        scan = REF_FULL_RE.sub(lambda m: " " * len(m.group(0)), scan)
        # 简写形式 [label] 只有在已定义时才是链接；实际被使用时才计入可达集合
        for m in REF_SHORT_RE.finditer(scan):
            label = normalize_label(m.group(1))
            if linked is not None and label in valid_defs:
                linked.add(valid_defs[label])


def check_paths(md: Path, text: str, ctx: RefContext, check: Check) -> None:
    rel = str(md.relative_to(ctx.rel_base))
    for no, line in prose_lines(text):
        for span in CODE_SPAN_RE.finditer(line):
            for token in span.group(0)[1:-1].split():
                if "/" not in token or token.startswith("/") or any(c in token for c in "<>*?[]{}$|=:"):
                    continue
                norm = posixpath.normpath(token)
                if norm == ".":
                    continue
                # 外部源码树中的路径（如 Linux 的 ./scripts/checkpatch.pl）必须登记在 external_paths
                if norm in ctx.external_paths:
                    continue
                if norm == ".." or norm.startswith("../"):
                    if ctx.confine is not None:
                        check.error(rel, no, f"path escapes skill directory: {token}")
                    continue
                head = norm.split("/", 1)[0]
                if not head:
                    continue
                candidates: list[Path] = []
                if ctx.local_dirs and (md.parent / head).is_dir():
                    candidates = [md.parent]
                elif head in SKILL_ROOT_DIRS:
                    candidates = ctx.skill_roots
                else:
                    continue
                if ctx.confine is not None and any(not inside(base / norm, ctx.confine) for base in candidates):
                    check.error(rel, no, f"path escapes skill directory: {token}")
                elif not any((base / norm).exists() for base in candidates):
                    check.error(rel, no, f"path not found: {token}")


def resolve_md(md: Path, name: str, ctx: RefContext) -> Path | None:
    bases = [md.parent]
    for root in ctx.skill_roots:
        bases += [root / "references", root]
    for base in bases:
        cand = base / name
        if cand.is_file():
            return cand
    return None


def check_sections(md: Path, text: str, ctx: RefContext, check: Check, cache: dict[Path, set[int]]) -> None:
    rel = str(md.relative_to(ctx.rel_base))

    def numbers(path: Path) -> set[int] | None:
        key = path.resolve()
        if key not in cache:
            body = read_text_or_none(path)
            cache[key] = None if body is None else section_numbers(body)
        return cache[key]

    lines = list(prose_lines(text))
    definitions, def_lines = _collect_ref_defs(lines)
    for no, line in lines:
        if no in def_lines:
            continue
        for m in SECTION_REF_RE.finditer(line):
            name = m.group(1) or m.group(2) or m.group(3)
            if name is None and m.group(4) is not None:
                raw_label = m.group(5) or m.group(4)
                target_str = definitions.get(normalize_label(raw_label), "")
                name = target_str.split("#", 1)[0] or f"[{raw_label}]"
            elif name is None and m.group(6) is not None:
                raw_label = m.group(6)
                label = normalize_label(raw_label)
                if label in definitions:
                    name = definitions[label].split("#", 1)[0] or f"[{raw_label}]"
                elif raw_label.endswith(".md"):
                    name = raw_label
                else:
                    check.error(rel, no, f"ambiguous § reference after '[{raw_label}]': name the file as a .md link "
                                         "or path, or drop the word")
                    continue
            if name:
                target = resolve_md(md, name, ctx)
                if target is None:
                    check.error(rel, no, f"§ reference to unknown file: {name}")
                    continue
            else:
                if AMBIGUOUS_SECTION_PREFIX_RE.search(line[:m.start()]):
                    word = line[:m.start()].rstrip().split()[-1]
                    check.error(rel, no, f"ambiguous § reference after {word!r}: name the file as a .md link "
                                         "or path, or drop the word")
                    continue
                target = md
            have = numbers(target)
            if have is None:
                check.error(rel, no, f"cannot read {target.name} to resolve §")
                continue
            for num in map(int, re.findall(r"\d+", m.group(7))):
                if num not in have:
                    if name:
                        check.error(rel, no, f"§{num} not found in {name} (headings: {sorted(have)})")
                    else:
                        check.error(rel, no, f"§{num} not found in this file (headings: {sorted(have)}); "
                                             "a reference to another file must name it as a .md link or path")
# --------------------------------------------------------------------------- 技能检查

def split_frontmatter(text: str):
    """分隔符必须是第 0 列的 '---'；块标量里缩进的 '---' 不是结束符。保留原始行结束符。"""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n").rstrip() != "---":
        return None, None, 0
    for idx in range(1, len(lines)):
        if lines[idx].rstrip("\r\n").rstrip() == "---":
            return "".join(lines[1:idx]), "".join(lines[idx + 1:]), idx + 1
    return None, None, 0

def check_frontmatter(skill: Path, cfg: dict, check: Check) -> dict | None:
    entry = skill / "SKILL.md"
    if not entry.is_file():
        check.error(skill.name, None, "SKILL.md not found")
        return None
    text = read_text_or_none(entry)
    if text is None:
        check.error("SKILL.md", None, "SKILL.md is not readable UTF-8")
        return None
    raw, _body, _end = split_frontmatter(text)
    if raw is None:
        check.error("SKILL.md", 1, "missing YAML frontmatter delimited by '---'")
        return None
    try:
        meta = load_yaml(raw)
    except YamlSyntaxError as exc:
        check.error("SKILL.md", None, f"frontmatter is not valid YAML: {exc}")
        return None
    if not isinstance(meta, dict):
        check.error("SKILL.md", None, "frontmatter must be a mapping")
        return None
    for key in sorted_keys(k for k in meta if not isinstance(k, str)):
        check.error("SKILL.md", None, f"frontmatter key {key!r} must be a string")
    for key in sorted_keys(k for k in meta if isinstance(k, str) and k not in FRONTMATTER_KEYS):
        check.error("SKILL.md", None, f"unknown frontmatter field: {key}")
    name = meta.get("name")
    if not isinstance(name, str) or not name:
        check.error("SKILL.md", None, "name is required")
    else:
        if len(name) > 64:
            check.error("SKILL.md", None, f"name longer than 64 characters ({len(name)})")
        if not NAME_RE.match(name):
            check.error("SKILL.md", None, f"name {name!r}: only a-z, 0-9 and single hyphens, no leading/trailing hyphen")
        if name != skill.name:
            check.error("SKILL.md", None, f"name {name!r} does not match directory {skill.name!r}")
    desc = meta.get("description")
    if not isinstance(desc, str) or not desc.strip():
        check.error("SKILL.md", None, "description is required and must be non-empty")
    else:
        if len(desc) > 1024:
            check.error("SKILL.md", None, f"description longer than 1024 characters ({len(desc)})")
        if not TRIGGER_HINT_RE.search(desc):
            check.warn("SKILL.md", None, "description does not say when to use the skill")
    # 可选字段按“是否出现”校验：显式 null 也必须满足类型约束
    if "compatibility" in meta:
        comp = meta["compatibility"]
        if not isinstance(comp, str) or not 1 <= len(comp) <= 500:
            check.error("SKILL.md", None, "compatibility must be a 1-500 character string")
    if "metadata" in meta:
        md = meta["metadata"]
        if not isinstance(md, dict):
            check.error("SKILL.md", None, "metadata must be a mapping")
        else:
            for k, v in md.items():
                if not isinstance(k, str) or not isinstance(v, str):
                    check.error("SKILL.md", None, f"metadata.{k}: keys and values must be strings (quote numbers)")
    if "allowed-tools" in meta and not isinstance(meta["allowed-tools"], str):
        check.error("SKILL.md", None, "allowed-tools must be a space-separated string")
    if "license" in meta and not (isinstance(meta["license"], str) and meta["license"].strip()):
        check.error("SKILL.md", None, "license must be a non-empty string")

    limit = cfg.get("max_skill_md_lines", SPEC_MAX_SKILL_LINES)
    count = len(text.splitlines())
    if count > limit:
        check.error("SKILL.md", None, f"SKILL.md has {count} lines, budget is {limit}")
    elif count > SPEC_MAX_SKILL_LINES:
        check.warn("SKILL.md", None, f"SKILL.md has {count} lines; spec recommends under {SPEC_MAX_SKILL_LINES}")
    return meta


def skill_markdown(skill: Path) -> list[Path]:
    return sorted(p for p in skill.rglob("*.md") if p.is_file())


def check_reachability(skill: Path, linked_from_entry: set[Path], check: Check) -> None:
    refs = skill / "references"
    if not refs.is_dir():
        return
    for md in sorted(refs.rglob("*.md")):
        if md.resolve() not in linked_from_entry:
            check.error(str(md.relative_to(skill)), None, "not linked from SKILL.md")


def check_orphans(skill: Path, check: Check, texts: list[str]) -> None:
    corpus = "\n".join(texts)
    for root in ("scripts", "assets", "standards", "profiles"):
        base = skill / root
        if not base.is_dir():
            continue
        for entry in sorted(base.iterdir()):
            if is_hygiene_violation(entry):
                continue  # 由 hygiene 报告，避免同一问题重复计数
            needle = f"{root}/{entry.name}"
            if not re.search(re.escape(needle) + r"(?![\w.-])", corpus):
                check.error(needle, None, "not mentioned in any skill document")


def check_scripts(skill: Path, check: Check) -> None:
    base = skill / "scripts"
    if not base.is_dir():
        return
    unchecked: dict[str, int] = {}
    for path in sorted(p for p in base.rglob("*") if p.is_file()):
        rel = str(path.relative_to(skill))
        head = path.read_bytes()[:256]
        shebang = head.split(b"\n", 1)[0].decode("utf-8", "replace") if head.startswith(b"#!") else ""
        if shebang and not os.access(path, os.X_OK):
            check.error(rel, 1, "has a shebang but is not executable")
        is_py = path.suffix == ".py" or "python" in shebang
        is_sh = path.suffix == ".sh" or re.search(r"\b(?:ba)?sh\b", shebang) is not None
        if is_py:
            source = read_text_or_none(path)
            if source is None:
                check.error(rel, None, "Python source is not readable UTF-8")
                continue
            try:
                compile(source, rel, "exec")
            except SyntaxError as exc:
                check.error(rel, exc.lineno, f"Python syntax error: {exc.msg}")
        elif is_sh:
            shell = "bash" if "bash" in shebang else "sh"
            exe = shutil.which(shell)
            if exe is None:
                check.warn(rel, None, f"{shell} not found; syntax not checked")
                unchecked[shell] = unchecked.get(shell, 0) + 1
                continue
            proc = subprocess.run([exe, "-n", str(path)], capture_output=True, text=True, check=False)
            if proc.returncode != 0:
                check.error(rel, None, f"{shell} -n failed: {proc.stderr.strip().splitlines()[-1:] or ''}")
    if unchecked:
        # 有脚本没检查就不能报 PASS；有错误时 FAIL 优先
        check.not_run = "; ".join(f"{shell} not found: {n} script(s) not syntax-checked"
                                  for shell, n in sorted(unchecked.items()))


def check_json(skill: Path, check: Check) -> None:
    for path in sorted(skill.rglob("*.json")):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            check.error(str(path.relative_to(skill)), getattr(exc, "lineno", None), f"invalid JSON: {exc}")


def check_yaml_assets(skill: Path, check: Check) -> None:
    # rules.yaml、profiles/*.yaml、agents/openai.yaml 由各自的专门检查解析，这里不重复计数
    owned = {(skill / RULES_FILE).resolve(), (skill / "agents" / "openai.yaml").resolve()}
    owned |= {p.resolve() for p in (skill / "profiles").glob("*.yaml")}
    files = sorted(p for p in skill.rglob("*")
                   if p.is_file() and (p.suffix in (".yml", ".yaml") or p.name in YAML_FILE_NAMES)
                   and p.resolve() not in owned)
    if not files:
        return
    for path in files:
        body = read_text_or_none(path)
        if body is None:
            check.error(str(path.relative_to(skill)), None, "not readable UTF-8")
            continue
        try:
            _strict_pyyaml_load(body, all_documents=True)
        except YamlSyntaxError as exc:
            check.error(str(path.relative_to(skill)), exc.lineno, f"invalid YAML: {exc}")

def check_openai_yaml(skill: Path, check: Check) -> None:
    path = skill / "agents" / "openai.yaml"
    if not path.is_file():
        return
    rel = "agents/openai.yaml"
    body = read_text_or_none(path)
    if body is None:
        check.error(rel, None, "not readable UTF-8")
        return
    try:
        data = load_yaml(body)
    except YamlSyntaxError as exc:
        check.error(rel, None, f"cannot parse: {exc}")
        return
    if not isinstance(data, dict):
        check.error(rel, None, "top level must be a mapping")
        return
    for key, value in data.items():
        if key not in OPENAI_SCHEMA:
            check.warn(rel, None, f"undocumented top-level key: {key}")
            continue
        if not isinstance(value, dict):
            check.error(rel, None, f"{key} must be a mapping")
            continue
        for sub in value:
            if sub not in OPENAI_SCHEMA[key]:
                check.warn(rel, None, f"undocumented key: {key}.{sub}")
    iface = data.get("interface") or {}
    if isinstance(iface, dict):
        for k in ("display_name", "short_description", "default_prompt"):
            if k in iface and not isinstance(iface[k], str):
                check.error(rel, None, f"interface.{k} must be a string")
        for k in ("icon_small", "icon_large"):
            if k not in iface:
                continue
            icon = iface[k]
            if not (isinstance(icon, str) and (skill / icon).is_file()):
                check.error(rel, None, f"interface.{k}: file not found: {icon!r}")
            elif not inside(skill / icon, skill):
                # 安装时只复制技能目录，技能外的图标不会随技能交付
                check.error(rel, None, f"interface.{k}: icon is outside the skill directory: {icon}")
        color = iface.get("brand_color")
        if color is not None and not (isinstance(color, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", color)):
            check.error(rel, None, f"interface.brand_color must look like #RRGGBB: {color!r}")
    policy = data.get("policy") or {}
    if isinstance(policy, dict) and "allow_implicit_invocation" in policy \
            and not isinstance(policy["allow_implicit_invocation"], bool):
        check.error(rel, None, "policy.allow_implicit_invocation must be true or false")
    deps = data.get("dependencies") or {}
    if isinstance(deps, dict) and "tools" in deps:
        tools = deps["tools"]
        if not isinstance(tools, list):
            check.error(rel, None, "dependencies.tools must be a list")
        else:
            for idx, tool in enumerate(tools):
                if not isinstance(tool, dict):
                    check.error(rel, None, f"dependencies.tools[{idx}] must be a mapping")
                    continue
                for k in tool:
                    if k not in OPENAI_TOOL_KEYS:
                        check.warn(rel, None, f"undocumented key: dependencies.tools[{idx}].{k}")
                    elif not (isinstance(tool[k], str) and tool[k].strip()):
                        check.error(rel, None, f"dependencies.tools[{idx}].{k} must be a non-empty string")
                if isinstance(tool.get("type"), str) and tool["type"] not in OPENAI_TOOL_TYPES:
                    check.warn(rel, None, f"dependencies.tools[{idx}].type {tool['type']!r} is not documented")


RULES_FILE = Path("standards") / "rules.yaml"
RULE_ID_RE = re.compile(r"^[A-Z]{1,5}-\d{3}$")
RULE_REQUIRED = ("id", "title", "level", "profiles", "lang", "source", "ref", "verify")
RULE_OPTIONAL = ("when", "except", "cost", "conflicts")
RULE_LEVELS = {"mandatory", "advisory"}
RULE_LANGS = {"c", "cpp"}
VERIFY_METHODS = {"auto", "review", "test", "measure"}
VERIFY_KEYS = {"method", "tool", "check", "coverage", "gap"}
VERIFY_COVERAGES = {"full", "partial"}
RULES_TOP_KEYS = {"version", "profiles", "sources", "verify_tools", "rules"}
TOOL_KEYS = {"path", "external", "checks"}
PROFILE_REQUIRED = ("id", "summary", "evidence", "coding", "architecture", "references", "tests", "gates")
REF_RE = re.compile(r"^(\S+?)(?:\s+(§\d+(?:\s*(?:[、,，/–—~-]|和|与|及|至)\s*§?\d+)*))?$")


def _str_list(value) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(v, str) and bool(v.strip()) for v in value)


def _check_ref(skill: Path, rel: str, where: str, ref: str, check: Check, cache: dict[Path, set[int]]) -> None:
    """ref 形如 'references/c/barr-c.md §2、§4'：文件必须在技能内，§N 必须是该文件的章节。"""
    m = REF_RE.match(ref.strip())
    if not m:
        check.error(rel, None, f"{where}: malformed ref {ref!r} (expected '<path> §N')")
        return
    target = skill / m.group(1)
    if not target.is_file() or not inside(target, skill):
        check.error(rel, None, f"{where}: ref file not found in skill: {m.group(1)}")
        return
    if m.group(2):
        key = target.resolve()
        if key not in cache:
            body = read_text_or_none(target)
            cache[key] = None if body is None else section_numbers(body)
        if cache[key] is None:
            check.error(rel, None, f"{where}: cannot read {m.group(1)}")
            return
        for num in map(int, re.findall(r"\d+", m.group(2))):
            if num not in cache[key]:
                check.error(rel, None, f"{where}: §{num} not found in {m.group(1)}")


def load_rules(skill: Path) -> tuple[bool, object, str | None]:
    """返回 (文件是否存在, 解析数据, 解析错误)。"""
    path = skill / RULES_FILE
    if not path.is_file():
        return False, None, None
    body = read_text_or_none(path)
    if body is None:
        return True, None, "not readable UTF-8"
    try:
        return True, load_yaml(body), None
    except YamlSyntaxError as exc:
        return True, None, f"cannot parse: {exc}"

CITED_RULE_RE = re.compile(r"`([A-Z]{1,5}-\d{3})`")


def check_cited_rules(docs: dict[Path, str], skill: Path, known: set[str], check: Check) -> None:
    """文档中以反引号引用的 Rule ID（如 `ISR-002`）必须存在于 rules.yaml。"""
    for md, text in docs.items():
        rel = str(md.relative_to(skill))
        for no, line in prose_lines(text):
            for m in CITED_RULE_RE.finditer(line):
                if m.group(1) not in known:
                    check.error(rel, no, f"cites unknown rule {m.group(1)}")


def check_rules(skill: Path, exists: bool, data: object, parse_error: str | None,
                check: Check, docs: dict[Path, str] | None = None) -> None:
    rel = str(RULES_FILE)
    if not exists:
        check.not_run = f"no {rel}"
        return
    if parse_error:
        check.error(rel, None, parse_error)
        return
    if not isinstance(data, dict):
        check.error(rel, None, "top level must be a mapping")
        return
    for key in sorted_keys(set(data) - RULES_TOP_KEYS):
        check.error(rel, None, f"unknown top-level key: {key}")
    profiles = data.get("profiles")
    if not _str_list(profiles) or len(set(profiles)) != len(profiles):
        check.error(rel, None, "profiles must be a non-empty list of unique names")
        profiles = []
    sources = data.get("sources")
    if not isinstance(sources, dict) or not sources:
        check.error(rel, None, "sources must be a non-empty mapping")
        sources = {}
    tools = data.get("verify_tools")
    if not isinstance(tools, dict):
        check.error(rel, None, "verify_tools must be a mapping")
        tools = {}
    tool_checks: dict[str, set[str] | None] = {}
    tool_text: dict[str, str] = {}
    for name, spec in tools.items():
        where = f"verify_tools.{name}"
        if not isinstance(name, str) or not name.strip():
            check.error(rel, None, f"verify_tools key {name!r} must be a non-empty string")
            continue
        if not isinstance(spec, dict) or set(spec) - TOOL_KEYS:
            check.error(rel, None, f"{where}: must be a mapping of {sorted(TOOL_KEYS)}")
            continue
        if ("path" in spec) == ("external" in spec):
            check.error(rel, None, f"{where}: give exactly one of path / external")
            continue
        if "external" in spec and not (isinstance(spec["external"], str) and spec["external"].strip()):
            check.error(rel, None, f"{where}.external must be a non-empty string")
        if "path" in spec:
            if not (isinstance(spec["path"], str) and spec["path"].strip()):
                check.error(rel, None, f"{where}.path must be a non-empty string")
            else:
                target = skill / spec["path"]
                if not target.is_file() or not inside(target, skill):
                    check.error(rel, None, f"{where}: path not found in skill: {spec['path']}")
                elif target.suffix in (".md", "") or target.name.startswith("."):
                    body = read_text_or_none(target)
                    if body is not None:
                        tool_text[name] = body
        if "checks" in spec:
            if not _str_list(spec["checks"]):
                check.error(rel, None, f"{where}.checks must be a non-empty list of strings")
            else:
                tool_checks[name] = set(spec["checks"])
        else:
            tool_checks[name] = None
    rules = data.get("rules")
    if not isinstance(rules, list) or not rules:
        check.error(rel, None, "rules must be a non-empty list")
        return
    seen: dict[str, dict] = {}
    cache: dict[Path, set[int]] = {}
    for idx, rule in enumerate(rules):
        if not isinstance(rule, dict):
            check.error(rel, None, f"rules[{idx}] must be a mapping")
            continue
        rid = rule.get("id")
        where = rid if isinstance(rid, str) else f"rules[{idx}]"
        if not isinstance(rid, str) or not RULE_ID_RE.match(rid):
            check.error(rel, None, f"{where}: id must match {RULE_ID_RE.pattern}")
        elif rid in seen:
            check.error(rel, None, f"{rid}: duplicate id")
        else:
            seen[rid] = rule
        for key in RULE_REQUIRED:
            if key not in rule:
                check.error(rel, None, f"{where}: missing {key}")
        for key in sorted_keys(set(rule) - set(RULE_REQUIRED) - set(RULE_OPTIONAL)):
            check.error(rel, None, f"{where}: unknown key {key}")
        for key in ("title", "when", "except", "cost"):
            if key in rule and not (isinstance(rule[key], str) and rule[key].strip()):
                check.error(rel, None, f"{where}: {key} must be a non-empty string")
        if "level" in rule and (not isinstance(rule["level"], str) or rule["level"] not in RULE_LEVELS):
            check.error(rel, None, f"{where}: level must be one of {sorted(RULE_LEVELS)}")
        rp = rule.get("profiles")
        if "profiles" in rule:
            if not _str_list(rp):
                check.error(rel, None, f"{where}: profiles must be a non-empty list")
            elif rp != ["all"]:
                for p in rp:
                    if p not in profiles:
                        check.error(rel, None, f"{where}: unknown profile {p!r}")
        rl = rule.get("lang")
        if "lang" in rule and not (_str_list(rl) and set(rl) <= RULE_LANGS):
            check.error(rel, None, f"{where}: lang must be a list from {sorted(RULE_LANGS)}")
        rs = rule.get("source")
        if "source" in rule:
            if not _str_list(rs):
                check.error(rel, None, f"{where}: source must be a non-empty list")
            else:
                for s in rs:
                    if s not in sources:
                        check.error(rel, None, f"{where}: undeclared source {s!r}")
        refs = rule.get("ref")
        if "ref" in rule:
            ref_list = [refs] if isinstance(refs, str) else refs
            if not _str_list(ref_list):
                check.error(rel, None, f"{where}: ref must be a string or list of strings")
            else:
                for ref in ref_list:
                    _check_ref(skill, rel, where, ref, check, cache)
        verify = rule.get("verify")
        if "verify" in rule:
            if not isinstance(verify, dict) or set(verify) - VERIFY_KEYS:
                check.error(rel, None, f"{where}: verify must be a mapping of {sorted(VERIFY_KEYS)}")
            else:
                method = verify.get("method")
                tool = verify.get("tool")
                coverage = verify.get("coverage")
                gap = verify.get("gap")
                valid_tool = isinstance(tool, str) and bool(tool.strip())
                if not isinstance(method, str) or method not in VERIFY_METHODS:
                    check.error(rel, None, f"{where}: verify.method must be one of {sorted(VERIFY_METHODS)}")
                if method == "auto":
                    if not valid_tool:
                        check.error(rel, None, f"{where}: verify.method auto requires verify.tool")
                    if "coverage" not in verify:
                        check.error(rel, None, f"{where}: verify.method auto requires verify.coverage")
                    elif not isinstance(coverage, str) or coverage not in VERIFY_COVERAGES:
                        check.error(rel, None,
                                    f"{where}: verify.coverage must be one of {sorted(VERIFY_COVERAGES)}")
                    elif coverage == "partial":
                        if not (isinstance(gap, str) and gap.strip()):
                            check.error(rel, None, f"{where}: verify.coverage partial requires non-empty verify.gap")
                    elif "gap" in verify:
                        check.error(rel, None, f"{where}: verify.gap is only allowed when verify.coverage is partial")
                else:
                    if "coverage" in verify:
                        check.error(rel, None, f"{where}: verify.coverage is only allowed when verify.method is auto")
                    if "gap" in verify:
                        check.error(rel, None, f"{where}: verify.gap is only allowed when verify.coverage is partial")
                if "tool" in verify:
                    if not valid_tool:
                        check.error(rel, None, f"{where}: verify.tool must be a non-empty string")
                    elif tool not in tools:
                        check.error(rel, None, f"{where}: undeclared verify.tool {tool!r}")
                if "check" in verify:
                    item = verify["check"]
                    if not (isinstance(item, str) and item.strip()):
                        check.error(rel, None, f"{where}: verify.check must be a non-empty string")
                    elif not valid_tool:
                        check.error(rel, None, f"{where}: verify.check requires verify.tool")
                    elif tool in tools:
                        allowed = tool_checks.get(tool)
                        if allowed is not None:
                            if item not in allowed:
                                check.error(rel, None,
                                            f"{where}: {tool} has no check {item!r} (declared: {sorted(allowed)})")
                        elif tool in tool_text:
                            if item not in tool_text[tool]:
                                check.error(rel, None,
                                            f"{where}: {item!r} does not appear in {tools[tool].get('path')}")
                        else:
                            check.error(rel, None,
                                        f"{where}: {tool} does not declare checks and is not a text file; "
                                        "omit verify.check")
        if "conflicts" in rule and not _str_list(rule["conflicts"]):
            check.error(rel, None, f"{where}: conflicts must be a non-empty list of rule ids")

    if docs is not None:
        check_cited_rules(docs, skill, set(seen), check)
    for rid, rule in seen.items():
        conflicts = rule.get("conflicts")
        if not _str_list(conflicts):
            continue
        for other in conflicts:
            if other == rid:
                check.error(rel, None, f"{rid}: conflicts with itself")
            elif other not in seen:
                check.error(rel, None, f"{rid}: conflicts with unknown rule {other}")
            else:
                other_conflicts = seen[other].get("conflicts")
                if not _str_list(other_conflicts) or rid not in other_conflicts:
                    check.error(rel, None, f"{rid}: conflict with {other} is not listed on {other}")


def check_profiles(skill: Path, exists: bool, data: object, rules_error: str | None,
                   check: Check) -> None:
    pdir = skill / "profiles"
    if not exists:
        if pdir.is_dir():
            check.error("profiles/", None, "profiles/ exists but standards/rules.yaml is missing")
        else:
            check.not_run = "no standards/rules.yaml"
        return
    if rules_error is not None or not isinstance(data, dict):
        check.blocked = "standards/rules.yaml is invalid (see rules)"
        return
    declared = data.get("profiles") if _str_list(data.get("profiles")) else []
    tools = data.get("verify_tools") if isinstance(data.get("verify_tools"), dict) else {}
    if not pdir.is_dir():
        check.error("profiles/", None, "standards/rules.yaml declares profiles but profiles/ is missing")
        return
    files = {p.stem: p for p in pdir.glob("*.yaml")}
    for name in declared:
        if name not in files:
            check.error(f"profiles/{name}.yaml", None, "declared in rules.yaml but file is missing")
    for stem, path in sorted(files.items()):
        rel = f"profiles/{path.name}"
        if stem not in declared:
            check.error(rel, None, "not declared in standards/rules.yaml profiles")
        body = read_text_or_none(path)
        if body is None:
            check.error(rel, None, "not readable UTF-8")
            continue
        try:
            prof = load_yaml(body)
        except YamlSyntaxError as exc:
            check.error(rel, None, f"cannot parse: {exc}")
            continue
        if not isinstance(prof, dict):
            check.error(rel, None, "top level must be a mapping")
            continue
        for key in PROFILE_REQUIRED:
            if key not in prof:
                check.error(rel, None, f"missing {key}")
        for key in sorted_keys(set(prof) - set(PROFILE_REQUIRED)):
            check.error(rel, None, f"unknown key {key}")
        if prof.get("id") != stem:
            check.error(rel, None, f"id {prof.get('id')!r} does not match file name")
        for key in ("summary", "evidence", "architecture"):
            if key in prof and not (isinstance(prof[key], str) and prof[key].strip()):
                check.error(rel, None, f"{key} must be a non-empty string")
        refs = prof.get("references")
        if "references" in prof:
            if not _str_list(refs):
                check.error(rel, None, "references must be a non-empty list")
            else:
                for ref in refs:
                    target = skill / ref
                    if not target.is_file():
                        check.error(rel, None, f"reference not found: {ref}")
                    elif not inside(target, skill):
                        check.error(rel, None, f"reference is outside the skill directory: {ref}")
        for key in ("coding", "tests"):
            val = prof.get(key)
            if key in prof and not (isinstance(val, dict) and val
                                    and all(isinstance(k, str) and k.strip() and isinstance(v, str) and v.strip()
                                            for k, v in val.items())):
                check.error(rel, None, f"{key} must be a non-empty mapping of strings")
        gates = prof.get("gates")
        if "gates" in prof:
            if not isinstance(gates, list) or not gates:
                check.error(rel, None, "gates must be a non-empty list")
            else:
                for idx, gate in enumerate(gates):
                    if not isinstance(gate, dict) or set(gate) != {"tool", "run"}:
                        check.error(rel, None, f"gates[{idx}] must have exactly tool and run")
                        continue
                    gtool, grun = gate["tool"], gate["run"]
                    if not (isinstance(gtool, str) and gtool.strip()):
                        check.error(rel, None, f"gates[{idx}].tool must be a non-empty string")
                    elif gtool not in tools:
                        check.error(rel, None, f"gates[{idx}]: tool {gtool!r} not in verify_tools")
                    if not (isinstance(grun, str) and grun.strip()):
                        check.error(rel, None, f"gates[{idx}].run must be a non-empty string")

# --------------------------------------------------------------------------- 计数声明

CN_NUM = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
_NUM = r"(\d+|[一二两三四五六七八九十])"
# 文档里的规模数字（profile、规则、验证工程、变体）容易在内容增加后过期；只核对这几种固定句式
COUNT_PATTERNS = (
    ("profiles", re.compile(_NUM + r"\s*个\s*profile")),
    ("rules", re.compile(_NUM + r"\s*条带 ID 的规则")),
    ("projects", re.compile(_NUM + r"\s*个验证工程")),
    ("variants", re.compile(r"个验证工程、\s*" + _NUM + r"\s*个变体")),
)
# 与技能同仓库、描述其规模的文档；历史报告（如 validation-report.md）记录的是当时的数字，不核对
COUNT_REPO_DOCS = ("README.md", "docs/design.md")


def _to_int(token: str) -> int:
    return int(token) if token.isdigit() else CN_NUM[token]


def count_repo(skill: Path) -> Path | None:
    """技能位于 <repo>/skills/<name> 时返回仓库根；否则（如复制到临时目录）不核对仓库级文档。"""
    return skill.parent.parent if skill.parent.name == "skills" else None


def actual_counts(skill: Path, rules_data: object) -> dict[str, int]:
    counts: dict[str, int] = {}
    if (skill / "profiles").is_dir():
        counts["profiles"] = len(list((skill / "profiles").glob("*.yaml")))
    if isinstance(rules_data, dict) and isinstance(rules_data.get("rules"), list):
        counts["rules"] = len(rules_data["rules"])
    repo = count_repo(skill)
    projects = sorted((repo / "evals" / "projects").glob("*/eval.yaml")) if repo else []
    if projects:
        counts["projects"] = len(projects)
        total = 0
        for f in projects:
            data = load_yaml(f.read_text(encoding="utf-8"))
            variants = data.get("variants") if isinstance(data, dict) else None
            if not isinstance(variants, dict):
                return {k: v for k, v in counts.items() if k != "projects"}  # 结构不明时不核对工程/变体数
            total += len(variants)
        counts["variants"] = total
    return counts


def check_counts(skill: Path, rules_data: object, check: Check) -> None:
    counts = actual_counts(skill, rules_data)
    repo = count_repo(skill)
    files = [skill / "SKILL.md"] + ([repo / d for d in COUNT_REPO_DOCS] if repo else [])
    for path in files:
        text = read_text_or_none(path)
        if text is None:
            continue
        rel = path.name if path.parent == skill else str(path.relative_to(repo))
        # 目录树等围栏代码块里也有规模数字，因此逐行扫描全文
        for no, line in enumerate(text.splitlines(), 1):
            for kind, pattern in COUNT_PATTERNS:
                if kind not in counts:
                    continue
                for m in pattern.finditer(line):
                    claimed = _to_int(m.group(1))
                    if claimed != counts[kind]:
                        check.error(rel, no, f"{kind} count says {claimed}, actual {counts[kind]}")


def is_hygiene_violation(path: Path) -> bool:
    if path.is_dir() and not path.is_symlink():
        return path.name in HYGIENE_DIRS or HYGIENE_DIR_RE.match(path.name) is not None
    return HYGIENE_FILE_RE.search(path.name) is not None


def check_hygiene(skill: Path, cfg: dict, check: Check) -> None:
    limit = cfg.get("max_file_bytes", DEFAULT_MAX_FILE_BYTES)
    for path in sorted(skill.rglob("*")):
        rel = str(path.relative_to(skill))
        if path.is_symlink():
            if not inside(path, skill):
                check.error(rel, None, "symlink points outside the skill directory")
            continue
        if path.is_dir():
            if is_hygiene_violation(path):
                check.error(rel, None, "build/cache directory inside skill (install.sh copies it verbatim)")
            continue
        if is_hygiene_violation(path):
            check.error(rel, None, "generated or editor backup file inside skill")
        size = path.stat().st_size
        if size > limit:
            check.error(rel, None, f"file is {size} bytes, limit {limit}")
        if path.suffix == ".md":
            try:
                path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                check.error(rel, None, "Markdown file is not UTF-8")


def _run_check(check: Check, default_file: str, fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 - 单个检查未预期异常不得中断整体报告
        check.error(default_file, None, f"internal error: {type(exc).__name__}: {exc}")
        return None


def validate_skill(skill: Path, cfg: dict) -> dict:
    checks = {cid: Check(cid) for cid in ("frontmatter", "links", "paths", "sections", "reachability", "orphans",
                                          "scripts", "data-json", "data-yaml", "openai-yaml", "rules",
                                          "profiles", "counts", "hygiene")}
    _run_check(checks["hygiene"], skill.name, check_hygiene, skill, cfg, checks["hygiene"])
    meta = _run_check(checks["frontmatter"], "SKILL.md", check_frontmatter, skill, cfg, checks["frontmatter"])
    ctx = RefContext(rel_base=skill, skill_roots=[skill], confine=skill, local_dirs=False,
                     external_paths={posixpath.normpath(p) for p in cfg.get("external_paths", [])})
    entry_links: set[Path] = set()
    cache: dict[Path, set[int]] = {}
    texts: list[str] = []
    docs: dict[Path, str] = {}
    for md in skill_markdown(skill):
        text = read_text_or_none(md)
        if text is None:
            continue  # hygiene 已报告
        texts.append(text)
        docs[md] = text
    _run_check(checks["links"], skill.name,
               lambda: [check_links(md, t, ctx, checks["links"], entry_links if md == skill / "SKILL.md" else None)
                        for md, t in docs.items()])
    _run_check(checks["paths"], skill.name,
               lambda: [check_paths(md, t, ctx, checks["paths"]) for md, t in docs.items()])
    _run_check(checks["sections"], skill.name,
               lambda: [check_sections(md, t, ctx, checks["sections"], cache) for md, t in docs.items()])
    if (skill / "SKILL.md").is_file():
        _run_check(checks["reachability"], "SKILL.md", check_reachability, skill, entry_links, checks["reachability"])
    else:
        checks["reachability"].not_run = "SKILL.md missing"
    _run_check(checks["orphans"], skill.name, check_orphans, skill, checks["orphans"], texts)
    _run_check(checks["scripts"], "scripts/", check_scripts, skill, checks["scripts"])
    _run_check(checks["data-json"], skill.name, check_json, skill, checks["data-json"])
    _run_check(checks["data-yaml"], skill.name, check_yaml_assets, skill, checks["data-yaml"])
    _run_check(checks["openai-yaml"], "agents/openai.yaml", check_openai_yaml, skill, checks["openai-yaml"])
    rules_exists, rules_data, rules_error = load_rules(skill)
    _run_check(checks["rules"], str(RULES_FILE), check_rules, skill, rules_exists, rules_data, rules_error,
               checks["rules"], docs)
    _run_check(checks["profiles"], "profiles/", check_profiles, skill, rules_exists, rules_data, rules_error,
               checks["profiles"])
    _run_check(checks["counts"], skill.name, check_counts, skill, rules_data, checks["counts"])
    name = meta.get("name") if isinstance(meta, dict) else None
    return {"kind": "skill", "name": name or skill.name, "path": str(skill),
            "checks": [c.to_json() for c in checks.values()]}


def validate_doc(doc: Path, skills: list[Path], external_paths: set[str]) -> dict:
    checks = {cid: Check(cid) for cid in ("links", "paths", "sections")}
    ctx = RefContext(rel_base=doc.parent, skill_roots=skills, confine=None, local_dirs=True,
                     external_paths=external_paths)
    text = read_text_or_none(doc)
    if text is None:
        checks["links"].error(doc.name, None, "not readable UTF-8")
        checks["paths"].blocked = f"{doc.name} is not readable UTF-8 (see links)"
        checks["sections"].blocked = f"{doc.name} is not readable UTF-8 (see links)"
        return {"kind": "doc", "name": doc.name, "path": str(doc), "checks": [c.to_json() for c in checks.values()]}
    _run_check(checks["links"], doc.name, check_links, doc, text, ctx, checks["links"])
    _run_check(checks["paths"], doc.name, check_paths, doc, text, ctx, checks["paths"])
    _run_check(checks["sections"], doc.name, check_sections, doc, text, ctx, checks["sections"], {})
    return {"kind": "doc", "name": doc.name, "path": str(doc), "checks": [c.to_json() for c in checks.values()]}


# --------------------------------------------------------------------------- CLI

def load_config(path: Path | None) -> dict:
    if path is None or not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    skills = data.get("skills", {})
    if set(data) - {"skills"} or not isinstance(skills, dict):
        raise ValueError(f"{path}: only a top-level 'skills' mapping is supported")
    for name, cfg in skills.items():
        unknown = set(cfg) - CONFIG_KEYS
        if unknown:
            raise ValueError(f"{path}: skills.{name}: unknown keys {sorted(unknown)}")
    return skills


def render_text(results: list[dict]) -> str:
    out = []
    for res in results:
        out.append(f"{res['kind']} {res['name']} ({res['path']})")
        for chk in res["checks"]:
            errors = sum(f["level"] == "error" for f in chk["findings"])
            warns = len(chk["findings"]) - errors
            note = chk["blocked_reason"] or chk["not_run_reason"] or ""
            if errors or warns:
                note = f"{errors} error(s), {warns} warning(s)" + (f"; {note}" if note else "")
            out.append(f"  {chk['status']:<8} {chk['id']:<13} {note}".rstrip())
            for f in chk["findings"]:
                loc = f["file"] + (f":{f['line']}" if f["line"] else "")
                out.append(f"      {f['level']:<5} {loc}: {f['message']}")
    totals = summarize(results)
    out.append("summary: " + ", ".join(f"{v} {k}" for k, v in totals.items()))
    return "\n".join(out)


def summarize(results: list[dict]) -> dict:
    totals = {PASS: 0, FAIL: 0, NOT_RUN: 0, BLOCKED: 0}
    for res in results:
        for chk in res["checks"]:
            totals[chk["status"]] += 1
    return totals


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("skills", nargs="*", type=Path, help="skill directories (default: skills/*/ with SKILL.md)")
    ap.add_argument("--doc", action="append", type=Path, default=None,
                    help="extra Markdown file to check against the skills (default: README.md when no skills given)")
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ap.add_argument("--no-config", action="store_true")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)
    if yaml is None:
        print("error: PyYAML is required; run: uv run --with pyyaml python3 tools/validate_skill.py",
              file=sys.stderr)
        return 2

    try:
        config = load_config(None if args.no_config else args.config)
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"error: config: {exc}", file=sys.stderr)
        return 2

    skills = [p.resolve() for p in args.skills]
    docs = [p.resolve() for p in (args.doc or [])]
    if not skills:
        skills = sorted(p.parent.resolve() for p in (REPO / "skills").glob("*/SKILL.md"))
        if args.doc is None:
            # 仓库文档：README 与 docs/、research/ 下的 Markdown（生成的结果文件不在其中）
            docs = [p for p in [REPO / "README.md"] if p.is_file()]
            docs += sorted((REPO / "docs").glob("*.md")) + sorted((REPO / "research").glob("*.md"))
    if not skills:
        print("error: no skill directories found", file=sys.stderr)
        return 2
    for path in skills + docs:
        if not path.exists():
            print(f"error: {path} not found", file=sys.stderr)
            return 2

    results = [validate_skill(s, config.get(s.name, {})) for s in skills]
    external = set()
    for s in skills:
        external |= {posixpath.normpath(p) for p in config.get(s.name, {}).get("external_paths", [])}
    results += [validate_doc(d, skills, external) for d in docs]
    if args.json:
        print(json.dumps({"results": results, "summary": summarize(results)}, ensure_ascii=False, indent=2))
    else:
        print(render_text(results))
    return 1 if summarize(results)[FAIL] else 0


if __name__ == "__main__":
    sys.exit(main())
