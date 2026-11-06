#!/usr/bin/env python3
"""运行 evals/projects/*/eval.yaml 中的验证工程，对照预期结果给出结论。

用法：
  python3 tools/run_evals.py [PROJECT ...] [--json FILE] [--report FILE] [--prefix DIR] [--keep] [--strict]

每个工程目录：
  eval.yaml            检查定义与每个变体的预期
  good/                已知良好样例（完整工程）
  variants/<name>/     故意引入问题的变体：只放与 good/ 不同的文件，运行时叠加到 good/ 的副本上

检查状态：PASS / FAIL / NOT_RUN（缺少工具或外部依赖）/ BLOCKED（依赖的检查未通过，或工具自身报告配置错误）。
变体结论：MATCH（所有已执行的检查都符合预期，且没有未执行的检查）/ MISMATCH（至少一项与预期不符）/
NOT_RUN（没有不符，但有检查未执行，因而不能确认）。NOT_RUN 不是通过。

退出码：0 没有 MISMATCH（--strict 时还要求没有 NOT_RUN）；1 有 MISMATCH；2 定义错误或用法错误。
外部依赖目录默认 ~/.local/share/embedded-eval（可用 --prefix 或 EMBEDDED_EVAL_PREFIX 覆盖）。
依赖 PyYAML。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:
    import yaml  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - 由 main() 报告
    yaml = None

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "skills" / "embedded-engineering"
EVALS = REPO / "evals" / "projects"
RULES = SKILL / "standards" / "rules.yaml"

PASS, FAIL, NOT_RUN, BLOCKED = "PASS", "FAIL", "NOT_RUN", "BLOCKED"
MATCH, MISMATCH = "MATCH", "MISMATCH"
CHECK_KEYS = {"run", "requires", "needs", "pass_codes", "blocked_codes", "timeout", "rules", "env"}
VARIANT_KEYS = {"violates", "defect", "expect", "known_gap", "remove", "note"}
TOP_KEYS = {"project", "profile", "summary", "setup", "checks", "variants"}
OUTPUT_TAIL = 40


class DefinitionError(Exception):
    pass


def placeholders(prefix: Path) -> dict[str, str]:
    return {
        "skill": str(SKILL),
        "repo": str(REPO),
        "prefix": str(prefix),
        "freertos": str(prefix / "freertos-kernel"),
        "etl": str(prefix / "etl" / "include"),
        "cpputest": str(prefix / "cpputest-install"),
        "zephyr_workspace": str(prefix / "zephyrproject"),
        "zephyr_base": str(prefix / "zephyrproject" / "zephyr"),
        "zephyr_venv": str(prefix / "zephyrproject" / ".venv"),
        "renode": str(prefix / "renode" / "renode"),
        # ESP-IDF 按官方安装方式位于 ~/esp/esp-idf，可用 IDF_PATH 覆盖；检查命令中 source 其 export.sh
        "idf_path": os.environ.get("IDF_PATH") or str(Path.home() / "esp" / "esp-idf"),
    }


def expand(text: str, values: dict[str, str]) -> str:
    # 只替换已知的 {name}，shell 命令中的其他花括号保持原样；以 _ 开头的是内部值
    for key, value in values.items():
        if key.startswith("_"):
            continue
        text = text.replace("{" + key + "}", value)
    return text


def load_rules() -> dict[str, dict]:
    data = yaml.safe_load(RULES.read_text(encoding="utf-8"))
    return {r["id"]: r for r in data["rules"]}


def load_project(path: Path, rules: dict[str, dict]) -> dict:
    data = yaml.safe_load((path / "eval.yaml").read_text(encoding="utf-8"))
    where = path.name
    if not isinstance(data, dict) or set(data) - TOP_KEYS:
        raise DefinitionError(f"{where}: eval.yaml must be a mapping of {sorted(TOP_KEYS)}")
    if data.get("project") != path.name:
        raise DefinitionError(f"{where}: project must equal the directory name")
    if not (path / "good").is_dir():
        raise DefinitionError(f"{where}: good/ is missing")
    checks = data.get("checks")
    if not isinstance(checks, dict) or not checks:
        raise DefinitionError(f"{where}: checks must be a non-empty mapping")
    for cid, spec in checks.items():
        if not isinstance(spec, dict) or set(spec) - CHECK_KEYS or not isinstance(spec.get("run"), str):
            raise DefinitionError(f"{where}: check {cid} must have a string run and only {sorted(CHECK_KEYS)}")
        for need in spec.get("needs", []):
            if need not in checks or list(checks).index(need) >= list(checks).index(cid):
                raise DefinitionError(f"{where}: check {cid} needs {need}, which must be defined before it")
        for rid in spec.get("rules", []):
            if rid not in rules:
                raise DefinitionError(f"{where}: check {cid} cites unknown rule {rid}")
    variants = data.get("variants")
    if not isinstance(variants, dict) or "good" not in variants:
        raise DefinitionError(f"{where}: variants must include good")
    for name, var in variants.items():
        var = var or {}
        variants[name] = var
        if set(var) - VARIANT_KEYS:
            raise DefinitionError(f"{where}: variant {name}: unknown keys {sorted(set(var) - VARIANT_KEYS)}")
        expect = var.get("expect") or {}
        for cid, status in expect.items():
            if cid not in checks or status not in (PASS, FAIL, BLOCKED):
                raise DefinitionError(f"{where}: variant {name}: expect.{cid} must name a check and be PASS/FAIL/BLOCKED")
            if status == BLOCKED and not checks[cid].get("needs"):
                # 只有依赖其他检查的检查才可能被预期阻塞（依赖项按预期失败时）
                raise DefinitionError(f"{where}: variant {name}: expect.{cid} BLOCKED requires the check to have needs")
        violates = var.get("violates") or []
        for rid in violates:
            if rid not in rules:
                raise DefinitionError(f"{where}: variant {name} violates unknown rule {rid}")
        if name == "good":
            if violates or expect or (path / "variants" / "good").exists():
                raise DefinitionError(f"{where}: good must not violate rules, expect failures or have an overlay")
            continue
        if not violates and not var.get("defect"):
            # 业务逻辑缺陷不对应规则编号，但必须写明缺陷是什么
            raise DefinitionError(f"{where}: variant {name} must list violated rules or describe the defect")
        if var.get("defect") and not expected_failures(expect) and not var.get("known_gap"):
            raise DefinitionError(f"{where}: variant {name}: a defect must be expected to FAIL some check "
                                  "or document known_gap")
        if not (path / "variants" / name).is_dir() and not var.get("remove"):
            raise DefinitionError(f"{where}: variant {name} has neither variants/{name}/ nor remove")
        expected_fail = expected_failures(expect)
        detecting = {rid for cid in expected_fail for rid in checks[cid].get("rules", [])}
        undetected = [rid for rid in violates if rid not in detecting]
        # 违反的规则如果没有被任何预期 FAIL 的检查覆盖，必须写明已知漏报
        if undetected and not var.get("known_gap"):
            raise DefinitionError(f"{where}: variant {name}: {undetected} not covered by an expected FAIL; "
                                  "add the detecting check to expect or document known_gap")
    data["_path"] = path
    return data


def expected_failures(expect: dict) -> set[str]:
    return {cid for cid, status in expect.items() if status == FAIL}


def tool_path(prefix: Path) -> str:
    """检查运行时的 PATH：在系统 PATH 之后追加用户级安装目录（gem --user-install、uv tool）。"""
    extra = [str(Path.home() / ".local" / "bin"), str(prefix / "bin")]
    ruby = shutil.which("ruby")
    if ruby:
        out = subprocess.run([ruby, "-e", "print Gem.user_dir"], capture_output=True, text=True, check=False)
        if out.returncode == 0 and out.stdout:
            extra.append(str(Path(out.stdout) / "bin"))
    parts = os.environ.get("PATH", "").split(os.pathsep)
    return os.pathsep.join(parts + [p for p in extra if p not in parts])


def missing_requirements(spec: dict, values: dict[str, str]) -> list[str]:
    missing = []
    for req in spec.get("requires", []):
        item = expand(req, values)
        if "/" in item:
            if not Path(item).exists():
                missing.append(item)
        elif shutil.which(item, path=values["_path"]) is None:
            missing.append(item)
    return missing


def materialize(project: dict, name: str, dest: Path, values: dict[str, str]) -> None:
    path: Path = project["_path"]
    shutil.copytree(path / "good", dest, symlinks=True)
    overlay = path / "variants" / name
    if name != "good" and overlay.is_dir():
        shutil.copytree(overlay, dest, symlinks=True, dirs_exist_ok=True)
    for rel in project["variants"][name].get("remove") or []:
        target = dest / rel
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
    for step in project.get("setup") or []:
        src, dst = (expand(x, values) for x in step["copy"])
        (dest / dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest / dst)


def run_check(spec: dict, cwd: Path, values: dict[str, str], results: dict[str, dict]) -> dict:
    missing = missing_requirements(spec, values)
    if missing:
        return {"status": NOT_RUN, "reason": "missing: " + ", ".join(missing)}
    for need in spec.get("needs", []):
        if results[need]["status"] != PASS:
            return {"status": BLOCKED, "reason": f"needs {need} ({results[need]['status']})"}
    env = dict(os.environ)
    env["PATH"] = values["_path"]
    env.update({k: expand(v, values) for k, v in (spec.get("env") or {}).items()})
    command = expand(spec["run"], values)
    start = time.monotonic()
    try:
        proc = subprocess.run(["/bin/sh", "-c", command], cwd=cwd, env=env, capture_output=True, text=True,
                              timeout=spec.get("timeout", 600), check=False)
    except subprocess.TimeoutExpired:
        # 超时视为失败：被测程序挂起（例如 RTOS 测试死锁）本身就是缺陷
        return {"status": FAIL, "reason": f"timeout after {spec.get('timeout', 600)} s", "command": command}
    output = (proc.stdout + proc.stderr).strip().splitlines()
    code = proc.returncode
    if code in spec.get("pass_codes", [0]):
        status = PASS
    elif code in spec.get("blocked_codes", []):
        status = BLOCKED
    else:
        status = FAIL
    return {"status": status, "exit_code": code, "seconds": round(time.monotonic() - start, 1),
            "command": command, "output_tail": output[-OUTPUT_TAIL:]}


def run_variant(project: dict, name: str, values: dict[str, str], keep: bool) -> dict:
    var = project["variants"][name]
    tmp = Path(tempfile.mkdtemp(prefix=f"eval-{project['project']}-{name}-"))
    try:
        materialize(project, name, tmp / "work", values)
        results: dict[str, dict] = {}
        for cid, spec in project["checks"].items():
            results[cid] = run_check(spec, tmp / "work", values, results)
    finally:
        if not keep:
            shutil.rmtree(tmp, ignore_errors=True)
    expect = var.get("expect") or {}
    mismatches, unverified = [], []
    for cid, res in results.items():
        want = expect.get(cid, PASS)
        res["expected"] = want
        if res["status"] == want:
            continue
        if res["status"] in (NOT_RUN, BLOCKED):
            unverified.append(cid)
        else:
            mismatches.append(cid)
    verdict = MISMATCH if mismatches else (NOT_RUN if unverified else MATCH)
    detected = [cid for cid, res in results.items() if res["status"] == FAIL]
    return {"variant": name, "violates": var.get("violates") or [], "defect": var.get("defect"),
            "known_gap": var.get("known_gap"),
            "verdict": verdict, "mismatches": mismatches, "unverified": unverified, "detected_by": detected,
            "workdir": str(tmp / "work") if keep else None, "checks": results}


def rule_coverage(projects: list[dict], rules: dict[str, dict]) -> dict:
    exercised: dict[str, list[str]] = {}
    for proj in projects:
        for name, var in proj["variants"].items():
            for rid in var.get("violates") or []:
                exercised.setdefault(rid, []).append(f"{proj['project']}/{name}")
    auto = {rid for rid, r in rules.items() if r["verify"]["method"] == "auto"}
    full = {rid for rid in auto if rules[rid]["verify"].get("coverage") == "full"}
    return {"exercised": exercised,
            "auto_rules": len(auto), "auto_exercised": sorted(auto & set(exercised)),
            "full_rules_not_exercised": sorted(full - set(exercised))}


def render_markdown(report: dict) -> str:
    lines = ["# 验证工程运行结果", "",
             f"生成时间：{report['generated']}；技能提交：`{report['commit']}`。本文件由 `tools/run_evals.py` 生成，不要手改。", ""]
    s = report["summary"]
    lines += [f"变体结论：MATCH {s[MATCH]}，MISMATCH {s[MISMATCH]}，NOT_RUN {s[NOT_RUN]}。", ""]
    for proj in report["projects"]:
        lines += [f"## {proj['project']}（profile `{proj['profile']}`）", "", proj.get("summary", ""), ""]
        cids = list(proj["checks"])
        lines.append("| 变体 | 违反的规则 | 结论 | " + " | ".join(cids) + " |")
        lines.append("| --- | --- | --- | " + " | ".join("---" for _ in cids) + " |")
        for var in proj["results"]:
            cells = []
            for cid in cids:
                res = var["checks"][cid]
                if res["status"] == res["expected"] or res["status"] in (NOT_RUN, BLOCKED):
                    mark = res["status"]
                else:
                    mark = f"**{res['status']}≠{res['expected']}**"
                cells.append(mark)
            rules_txt = ", ".join(f"`{r}`" for r in var["violates"]) or (f"缺陷：{var['defect']}" if var["defect"] else "—")
            lines.append(f"| `{var['variant']}` | {rules_txt} | {var['verdict']} | " + " | ".join(cells) + " |")
        gaps = [v for v in proj["results"] if v["known_gap"]]
        if gaps:
            lines += ["", "已知漏报（自动检查不能发现，需 review 或 test 补足）：", ""]
            lines += [f"- `{v['variant']}`：{v['known_gap']}" for v in gaps]
        reasons = {(cid, var["checks"][cid].get("reason")) for var in proj["results"] for cid in cids
                   if var["checks"][cid]["status"] in (NOT_RUN, BLOCKED)}
        if reasons:
            lines += ["", "未执行的检查：", ""]
            lines += [f"- `{cid}`：{reason}" for cid, reason in sorted(reasons, key=str)]
        lines.append("")
    cov = report["rule_coverage"]
    lines += ["## 规则覆盖", "",
              f"`verify.method: auto` 的规则共 {cov['auto_rules']} 条，被至少一个变体违反并检验的有 "
              f"{len(cov['auto_exercised'])} 条：" + (", ".join(f"`{r}`" for r in cov["auto_exercised"]) or "无") + "。", ""]
    if cov["full_rules_not_exercised"]:
        lines.append("`coverage: full` 但没有任何变体检验的规则：" +
                     ", ".join(f"`{r}`" for r in cov["full_rules_not_exercised"]) + "。")
    else:
        lines.append("所有 `coverage: full` 的规则都至少被一个变体检验。")
    lines.append("")
    return "\n".join(lines)


def git_commit() -> str:
    try:
        out = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"], capture_output=True,
                             text=True, check=False).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain"], capture_output=True,
                               text=True, check=False).stdout.strip()
        return out + ("-dirty" if dirty else "") if out else "unknown"
    except OSError:
        return "unknown"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("projects", nargs="*", help="project names (default: all)")
    ap.add_argument("--json", type=Path, help="write the full result as JSON")
    ap.add_argument("--report", type=Path, help="write a Markdown summary")
    ap.add_argument("--prefix", type=Path,
                    default=Path(os.environ.get("EMBEDDED_EVAL_PREFIX", Path.home() / ".local/share/embedded-eval")))
    ap.add_argument("--keep", action="store_true", help="keep variant work directories for inspection")
    ap.add_argument("--strict", action="store_true", help="treat NOT_RUN verdicts as failure")
    ap.add_argument("--list", action="store_true", help="validate definitions and list variants without running")
    args = ap.parse_args(argv)
    if yaml is None:
        print("error: PyYAML is required; run: uv run --with pyyaml python3 tools/run_evals.py", file=sys.stderr)
        return 2
    values = placeholders(args.prefix.expanduser().resolve())
    values["_path"] = tool_path(Path(values["prefix"]))
    rules = load_rules()
    names = args.projects or sorted(p.name for p in EVALS.iterdir() if (p / "eval.yaml").is_file())
    try:
        projects = [load_project(EVALS / n, rules) for n in names]
    except (DefinitionError, FileNotFoundError, yaml.YAMLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.list:
        for proj in projects:
            print(f"{proj['project']}: " + ", ".join(proj["variants"]))
        return 0

    report = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "commit": git_commit(),
              "prefix": values["prefix"], "projects": [], "summary": {MATCH: 0, MISMATCH: 0, NOT_RUN: 0}}
    for proj in projects:
        results = []
        for name in proj["variants"]:
            res = run_variant(proj, name, values, args.keep)
            report["summary"][res["verdict"]] += 1
            results.append(res)
            flag = "" if res["verdict"] == MATCH else f"  mismatches={res['mismatches']} unverified={res['unverified']}"
            print(f"{proj['project']}/{name}: {res['verdict']}  detected_by={res['detected_by']}{flag}", flush=True)
        report["projects"].append({"project": proj["project"], "profile": proj.get("profile"),
                                   "summary": proj.get("summary", ""), "checks": list(proj["checks"]),
                                   "results": results})
    report["rule_coverage"] = rule_coverage(projects, rules)
    if args.json:
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.report:
        args.report.write_text(render_markdown(report), encoding="utf-8")
    s = report["summary"]
    print(f"summary: {s[MATCH]} MATCH, {s[MISMATCH]} MISMATCH, {s[NOT_RUN]} NOT_RUN")
    if s[MISMATCH] or (args.strict and s[NOT_RUN]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
