#!/usr/bin/env python3
"""Agent Skill 自检：frontmatter、引用完整性、资源可达性、脚本与数据文件、打包卫生。

用法：
  python3 tools/validate_skill.py [SKILL_DIR ...] [--doc FILE ...] [--config FILE | --no-config] [--json]

不带参数时检查 skills/ 下每个含 SKILL.md 的目录，以及仓库根的 README.md。
退出码：0 没有 FAIL；1 至少一项 FAIL；2 用法或配置错误。只用标准库；PyYAML 存在时额外解析 YAML 资产。

检查项（规则依据 https://agentskills.io/specification 与 Codex agents/openai.yaml 文档）：
  frontmatter  name/description/compatibility/metadata 约束，name 与目录同名，SKILL.md 行数预算
  links        Markdown 相对链接存在，且不逃出技能目录（安装时只复制技能目录）
  paths        反引号中的 scripts/ assets/ references/ agents/ 路径存在（相对技能根）
  sections     “§N” 引用指向目标文件中存在的 “## N.” 标题
  reachability references/ 下每个文件都由 SKILL.md 直接链接（规范建议引用只保持一层）
  orphans      scripts/、assets/ 下每个顶层条目都在技能文档中被提到
  scripts      带 shebang 的脚本可执行；Python 可编译；shell 通过 -n 语法检查
  data-json    *.json 可解析
  data-yaml    *.yml/*.yaml/.clang-format/.clang-tidy 可解析（需要 PyYAML，否则 NOT_RUN）
  openai-yaml  agents/openai.yaml 字段、图标路径、颜色格式
  hygiene      无 __pycache__/*.pyc/build 目录/编辑器残留、无超大文件、无指向技能外的符号链接
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = Path(__file__).resolve().with_name("validate_skill.json")

PASS, FAIL, NOT_RUN = "PASS", "FAIL", "NOT_RUN"

FRONTMATTER_KEYS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SPEC_MAX_SKILL_LINES = 500  # 规范建议值；项目可在配置里收紧
SKILL_ROOT_DIRS = ("scripts", "assets", "references", "agents")
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
    not_run: str | None = None

    def error(self, file: str, line: int | None, message: str) -> None:
        self.findings.append(Finding("error", file, line, message))

    def warn(self, file: str, line: int | None, message: str) -> None:
        self.findings.append(Finding("warn", file, line, message))

    @property
    def status(self) -> str:
        if any(f.level == "error" for f in self.findings):
            return FAIL
        if self.not_run:
            return NOT_RUN
        return PASS

    def to_json(self) -> dict:
        return {"id": self.id, "status": self.status, "not_run_reason": self.not_run,
                "findings": [f.__dict__ for f in self.findings]}


# --------------------------------------------------------------------------- YAML 子集

class YamlSubsetError(ValueError):
    pass


_KEY_RE = re.compile(r"""^("(?:[^"\\]|\\.)*"|'(?:[^']|'')*'|[^\s:#'"\-][^:#]*?|-[^\s:#][^:#]*?)\s*:(?:\s+(.*))?$""")


def _yaml_scalar(raw: str, lineno: int):
    s = raw.strip()
    if not s or s.startswith("#"):
        return None
    if s[0] in "[{&*!%@`":
        raise YamlSubsetError(f"line {lineno}: unsupported construct {s[:12]!r}")
    if s[0] == '"':
        try:
            value, end = json.JSONDecoder().raw_decode(s)
        except json.JSONDecodeError as exc:
            raise YamlSubsetError(f"line {lineno}: bad double-quoted scalar ({exc.msg})") from None
        tail = s[end:].strip()
        if tail and not tail.startswith("#"):
            raise YamlSubsetError(f"line {lineno}: trailing text after quoted scalar")
        return value
    if s[0] == "'":
        m = re.match(r"'((?:[^']|'')*)'\s*(?:#.*)?$", s)
        if not m:
            raise YamlSubsetError(f"line {lineno}: bad single-quoted scalar")
        return m.group(1).replace("''", "'")
    s = re.split(r"\s+#", s, maxsplit=1)[0].rstrip()
    low = s.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low in ("null", "~"):
        return None
    if re.fullmatch(r"[-+]?\d+", s):
        return int(s)
    if re.fullmatch(r"[-+]?(?:\d+\.\d*|\.\d+)(?:[eE][-+]?\d+)?", s):
        return float(s)
    return s


def parse_yaml_subset(text: str):
    """解析 frontmatter 与 openai.yaml 用到的 YAML 子集。

    支持：嵌套映射、标量、块标量（| > 及 - + 修饰）、列表（含 “- key: value” 映射项）。
    不支持锚点、标签、流式集合、多文档；遇到即抛 YamlSubsetError，由调用方决定是否改用 PyYAML。
    """
    lines = text.splitlines()

    def indent_of(line: str) -> int:
        if "\t" in line[: len(line) - len(line.lstrip())]:
            raise YamlSubsetError("tab indentation is not allowed in YAML")
        return len(line) - len(line.lstrip(" "))

    def skip_blank(i: int) -> int:
        while i < len(lines) and (not lines[i].strip() or lines[i].lstrip().startswith("#")):
            i += 1
        return i

    def block_scalar(i: int, parent_indent: int, style: str):
        body: list[str] = []
        block_indent = None
        while i < len(lines):
            line = lines[i]
            if not line.strip():
                body.append("")
                i += 1
                continue
            ind = indent_of(line)
            if ind <= parent_indent or (block_indent is not None and ind < block_indent):
                break
            if block_indent is None:
                block_indent = ind
            body.append(line[block_indent:])
            i += 1
        while body and body[-1] == "":
            body.pop()
        if style[0] == "|":
            value = "\n".join(body)
        else:
            paragraphs, current = [], []
            for part in body:
                if part == "":
                    paragraphs.append(" ".join(current))
                    current = []
                else:
                    current.append(part.strip())
            paragraphs.append(" ".join(current))
            value = "\n".join(paragraphs)
        if style.endswith("-") or not value:
            return value, i
        return value + "\n", i

    def parse_node(i: int):
        line = lines[i]
        stripped = line.strip()
        if stripped == "-" or stripped.startswith("- "):
            return parse_list(i, indent_of(line))
        return parse_map(i, indent_of(line))

    def parse_value(rest: str, i: int, indent: int):
        """rest 是 “key:” 之后的文本；i 是该键所在行。"""
        bare = re.split(r"\s+#", rest, maxsplit=1)[0].strip()
        if bare and re.fullmatch(r"[|>][-+]?", bare):
            return block_scalar(i + 1, indent, bare)
        if bare:
            return _yaml_scalar(rest, i + 1), i + 1
        j = skip_blank(i + 1)
        if j < len(lines):
            nxt = lines[j]
            ind = indent_of(nxt)
            if ind > indent:
                return parse_node(j)
            if ind == indent and (nxt.strip() == "-" or nxt.strip().startswith("- ")):
                return parse_list(j, indent)
        return None, i + 1

    def parse_map(i: int, indent: int):
        out: dict = {}
        while True:
            i = skip_blank(i)
            if i >= len(lines):
                return out, i
            line = lines[i]
            ind = indent_of(line)
            content = line.strip()
            if ind < indent or (ind == indent and (content == "-" or content.startswith("- "))):
                return out, i
            if ind > indent:
                raise YamlSubsetError(f"line {i + 1}: unexpected indentation")
            m = _KEY_RE.match(content)
            if not m:
                raise YamlSubsetError(f"line {i + 1}: expected 'key: value'")
            raw_key = m.group(1)
            key = _yaml_scalar(raw_key, i + 1) if raw_key[0] in "\"'" else raw_key.strip()
            if key in out:
                raise YamlSubsetError(f"line {i + 1}: duplicate key {key!r}")
            out[key], i = parse_value(m.group(2) or "", i, indent)

    def parse_list(i: int, indent: int):
        out: list = []
        while True:
            i = skip_blank(i)
            if i >= len(lines):
                return out, i
            line = lines[i]
            ind = indent_of(line)
            content = line.strip()
            if ind != indent or not (content == "-" or content.startswith("- ")):
                if ind > indent:
                    raise YamlSubsetError(f"line {i + 1}: unexpected indentation")
                return out, i
            item = content[1:].strip()
            if not item:
                j = skip_blank(i + 1)
                if j < len(lines) and indent_of(lines[j]) > indent:
                    value, i = parse_node(j)
                else:
                    value, i = None, i + 1
            elif _KEY_RE.match(item):
                # “- key: value”：把该行改写成缩进 +2 的映射行，后续同级键自然接上
                lines[i] = " " * (indent + 2) + item
                value, i = parse_map(i, indent + 2)
            else:
                value, i = _yaml_scalar(item, i + 1), i + 1
            out.append(value)

    start = skip_blank(0)
    if start >= len(lines):
        return None
    value, end = parse_node(start)
    end = skip_blank(end)
    if end < len(lines):
        raise YamlSubsetError(f"line {end + 1}: unexpected content")
    return value


def load_yaml(text: str):
    """先用子集解析器；不支持的写法再交给 PyYAML（若已安装）。"""
    try:
        return parse_yaml_subset(text)
    except YamlSubsetError as exc:
        try:
            import yaml  # type: ignore[import-not-found]
        except ImportError:
            raise exc from None
        try:
            return yaml.safe_load(text)
        except yaml.YAMLError as yexc:
            raise YamlSubsetError(str(yexc)) from None


# --------------------------------------------------------------------------- Markdown 扫描

FENCE_RE = re.compile(r"^\s*(```+|~~~+)")
CODE_SPAN_RE = re.compile(r"`[^`\n]+`")
LINK_RE = re.compile(r"!?\[(?:[^\]\\]|\\.)*\]\(\s*<?([^)\s>]+)>?(?:\s+[\"'][^)]*[\"'])?\s*\)")
SECTION_HEADING_RE = re.compile(r"^#{1,6}\s+(\d+)(?=[.、:：)）\s]|$)")
_FILE_REF = (r"(?:\[[^\]]*\]\(([^)\s#]+\.md)(?:#[^)]*)?\)"
             r"|`([^`\s]+\.md)`"
             r"|(?<![\w/.-])((?:[\w.-]+/)*[\w-]+\.md))")
SECTION_REF_RE = re.compile(_FILE_REF + r"?\s*(§\d+(?:\s*(?:[、,，/–—~-]|和|与|及|至)\s*§?\d+)*)")
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


def check_links(md: Path, text: str, ctx: RefContext, check: Check, linked: set[Path] | None = None) -> None:
    rel = str(md.relative_to(ctx.rel_base))
    for no, line in prose_lines(text):
        for m in LINK_RE.finditer(blank_code_spans(line)):
            target = m.group(1)
            if is_external(target):
                continue
            path_part = target.split("#", 1)[0]
            if not path_part:
                continue
            dest = (md.parent / path_part)
            if not dest.exists():
                check.error(rel, no, f"broken link: {target}")
                continue
            if ctx.confine is not None and not inside(dest, ctx.confine):
                check.error(rel, no, f"link escapes skill directory: {target}")
                continue
            if linked is not None:
                linked.add(dest.resolve())


def check_paths(md: Path, text: str, ctx: RefContext, check: Check) -> None:
    rel = str(md.relative_to(ctx.rel_base))
    for no, line in prose_lines(text):
        for span in CODE_SPAN_RE.finditer(line):
            for token in span.group(0)[1:-1].split():
                if "/" not in token or any(c in token for c in "<>*?[]{}$|=:"):
                    continue
                head = token.split("/", 1)[0]
                if not head or head in (".", ".."):
                    # 绝对路径、斜杠命令、./ 前缀（约定为外部源码树路径，如 ./scripts/checkpatch.pl）不检查
                    continue
                candidates: list[Path] = []
                if ctx.local_dirs and (md.parent / head).is_dir():
                    candidates = [md.parent]
                elif head in SKILL_ROOT_DIRS:
                    if token.rstrip("/") in ctx.external_paths:
                        continue
                    candidates = ctx.skill_roots
                else:
                    continue
                if not any((base / token).exists() for base in candidates):
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

    def numbers(path: Path) -> set[int]:
        key = path.resolve()
        if key not in cache:
            cache[key] = section_numbers(path.read_text(encoding="utf-8"))
        return cache[key]

    for no, line in prose_lines(text):
        for m in SECTION_REF_RE.finditer(line):
            name = m.group(1) or m.group(2) or m.group(3)
            if name:
                target = resolve_md(md, name, ctx)
                if target is None:
                    check.error(rel, no, f"§ reference to unknown file: {name}")
                    continue
            else:
                target = md
            have = numbers(target)
            for num in map(int, re.findall(r"\d+", m.group(4))):
                if num not in have:
                    if name:
                        check.error(rel, no, f"§{num} not found in {name} (headings: {sorted(have)})")
                    else:
                        check.error(rel, no, f"§{num} not found in this file (headings: {sorted(have)}); "
                                             "a reference to another file must name it as a .md link or path")


# --------------------------------------------------------------------------- 技能检查

def split_frontmatter(text: str):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, None, 0
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            return "\n".join(lines[1:idx]), "\n".join(lines[idx + 1:]), idx + 1
    return None, None, 0


def check_frontmatter(skill: Path, cfg: dict, check: Check) -> dict | None:
    entry = skill / "SKILL.md"
    if not entry.is_file():
        check.error(skill.name, None, "SKILL.md not found")
        return None
    text = entry.read_text(encoding="utf-8")
    raw, _body, _end = split_frontmatter(text)
    if raw is None:
        check.error("SKILL.md", 1, "missing YAML frontmatter delimited by '---'")
        return None
    try:
        meta = load_yaml(raw)
    except YamlSubsetError as exc:
        check.error("SKILL.md", None, f"frontmatter is not valid YAML: {exc}")
        return None
    if not isinstance(meta, dict):
        check.error("SKILL.md", None, "frontmatter must be a mapping")
        return None
    for key in sorted(set(meta) - FRONTMATTER_KEYS):
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
    comp = meta.get("compatibility")
    if comp is not None and (not isinstance(comp, str) or not 1 <= len(comp) <= 500):
        check.error("SKILL.md", None, "compatibility must be a 1-500 character string")
    md = meta.get("metadata")
    if md is not None:
        if not isinstance(md, dict):
            check.error("SKILL.md", None, "metadata must be a mapping")
        else:
            for k, v in md.items():
                if not isinstance(k, str) or not isinstance(v, str):
                    check.error("SKILL.md", None, f"metadata.{k}: keys and values must be strings (quote numbers)")
    tools = meta.get("allowed-tools")
    if tools is not None and not isinstance(tools, str):
        check.error("SKILL.md", None, "allowed-tools must be a space-separated string")
    lic = meta.get("license")
    if lic is not None and not isinstance(lic, str):
        check.error("SKILL.md", None, "license must be a string")

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


def check_orphans(skill: Path, check: Check) -> None:
    corpus = "\n".join(p.read_text(encoding="utf-8") for p in skill_markdown(skill))
    for root in ("scripts", "assets"):
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
    for path in sorted(p for p in base.rglob("*") if p.is_file()):
        rel = str(path.relative_to(skill))
        head = path.read_bytes()[:256]
        shebang = head.split(b"\n", 1)[0].decode("utf-8", "replace") if head.startswith(b"#!") else ""
        if shebang and not os.access(path, os.X_OK):
            check.error(rel, 1, "has a shebang but is not executable")
        is_py = path.suffix == ".py" or "python" in shebang
        is_sh = path.suffix == ".sh" or re.search(r"\b(?:ba)?sh\b", shebang) is not None
        if is_py:
            try:
                compile(path.read_text(encoding="utf-8"), rel, "exec")
            except SyntaxError as exc:
                check.error(rel, exc.lineno, f"Python syntax error: {exc.msg}")
        elif is_sh:
            shell = "bash" if "bash" in shebang else "sh"
            exe = shutil.which(shell)
            if exe is None:
                check.warn(rel, None, f"{shell} not found; syntax not checked")
                continue
            proc = subprocess.run([exe, "-n", str(path)], capture_output=True, text=True, check=False)
            if proc.returncode != 0:
                check.error(rel, None, f"{shell} -n failed: {proc.stderr.strip().splitlines()[-1:] or ''}")


def check_json(skill: Path, check: Check) -> None:
    for path in sorted(skill.rglob("*.json")):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            check.error(str(path.relative_to(skill)), getattr(exc, "lineno", None), f"invalid JSON: {exc}")


def check_yaml_assets(skill: Path, check: Check) -> None:
    files = sorted(p for p in skill.rglob("*")
                   if p.is_file() and (p.suffix in (".yml", ".yaml") or p.name in YAML_FILE_NAMES))
    if not files:
        return
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError:
        check.not_run = f"PyYAML not installed; {len(files)} YAML files not parsed"
        return
    for path in files:
        try:
            list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
        except yaml.YAMLError as exc:
            mark = getattr(exc, "problem_mark", None)
            check.error(str(path.relative_to(skill)), mark.line + 1 if mark else None, f"invalid YAML: {exc}")


def check_openai_yaml(skill: Path, check: Check) -> None:
    path = skill / "agents" / "openai.yaml"
    if not path.is_file():
        return
    rel = "agents/openai.yaml"
    try:
        data = load_yaml(path.read_text(encoding="utf-8"))
    except YamlSubsetError as exc:
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
            if k in iface and not (isinstance(iface[k], str) and (skill / iface[k]).is_file()):
                check.error(rel, None, f"interface.{k}: file not found: {iface.get(k)}")
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


def validate_skill(skill: Path, cfg: dict) -> dict:
    checks = {cid: Check(cid) for cid in ("frontmatter", "links", "paths", "sections", "reachability", "orphans",
                                          "scripts", "data-json", "data-yaml", "openai-yaml", "hygiene")}
    check_hygiene(skill, cfg, checks["hygiene"])
    meta = check_frontmatter(skill, cfg, checks["frontmatter"])
    ctx = RefContext(rel_base=skill, skill_roots=[skill], confine=skill, local_dirs=False,
                     external_paths={p.rstrip("/") for p in cfg.get("external_paths", [])})
    entry_links: set[Path] = set()
    cache: dict[Path, set[int]] = {}
    for md in skill_markdown(skill):
        try:
            text = md.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue  # hygiene 已报告
        check_links(md, text, ctx, checks["links"], entry_links if md == skill / "SKILL.md" else None)
        check_paths(md, text, ctx, checks["paths"])
        check_sections(md, text, ctx, checks["sections"], cache)
    if (skill / "SKILL.md").is_file():
        check_reachability(skill, entry_links, checks["reachability"])
    else:
        checks["reachability"].not_run = "SKILL.md missing"
    check_orphans(skill, checks["orphans"])
    check_scripts(skill, checks["scripts"])
    check_json(skill, checks["data-json"])
    check_yaml_assets(skill, checks["data-yaml"])
    check_openai_yaml(skill, checks["openai-yaml"])
    name = meta.get("name") if isinstance(meta, dict) else None
    return {"kind": "skill", "name": name or skill.name, "path": str(skill),
            "checks": [c.to_json() for c in checks.values()]}


def validate_doc(doc: Path, skills: list[Path], external_paths: set[str]) -> dict:
    checks = {cid: Check(cid) for cid in ("links", "paths", "sections")}
    ctx = RefContext(rel_base=doc.parent, skill_roots=skills, confine=None, local_dirs=True,
                     external_paths=external_paths)
    text = doc.read_text(encoding="utf-8")
    check_links(doc, text, ctx, checks["links"])
    check_paths(doc, text, ctx, checks["paths"])
    check_sections(doc, text, ctx, checks["sections"], {})
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
            note = chk["not_run_reason"] or ""
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
    totals = {PASS: 0, FAIL: 0, NOT_RUN: 0}
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

    try:
        config = load_config(None if args.no_config else args.config)
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"error: config: {exc}", file=sys.stderr)
        return 2

    skills = [p.resolve() for p in args.skills]
    docs = [p.resolve() for p in (args.doc or [])]
    if not skills:
        skills = sorted(p.parent.resolve() for p in (REPO / "skills").glob("*/SKILL.md"))
        if args.doc is None and (REPO / "README.md").is_file():
            docs = [REPO / "README.md"]
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
        external |= {p.rstrip("/") for p in config.get(s.name, {}).get("external_paths", [])}
    results += [validate_doc(d, skills, external) for d in docs]

    if args.json:
        print(json.dumps({"results": results, "summary": summarize(results)}, ensure_ascii=False, indent=2))
    else:
        print(render_text(results))
    return 1 if summarize(results)[FAIL] else 0


if __name__ == "__main__":
    sys.exit(main())
