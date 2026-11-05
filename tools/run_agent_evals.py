#!/usr/bin/env python3
"""Agent 行为评测：在装有技能的沙箱仓库中运行 Claude Code / Codex，按 evals/agent/cases.yaml 判定。

用法：
  python3 tools/run_agent_evals.py [--agents claude,codex] [--cases T01,G01] [--jobs 3]
                                   [--judge-model MODEL] [--no-judge] [--report FILE]

判定分两层：
  确定性检查   技能是否被读取/调用（expect_skill）、回答必须包含的内容、不得出现的说法
  评委检查     rubric 逐条交给独立评委模型（默认 omp 的 Gemini 4 Argon，与两个被测 Agent 不同厂商）

用例状态：PASS / FAIL / NOT_RUN（Agent CLI 不可用，或确定性检查通过但评委未运行）/ BLOCKED（Agent 运行出错或超时）。
被测 Agent 只读：Claude Code 禁用 Bash/Edit/Write 等工具并只加载项目级设置、不加载 MCP；Codex 使用 read-only 沙箱。
原始事件流写入 evals/agent/runs/<时间戳>/（不入库），汇总写入 --report。依赖 PyYAML。
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:
    import yaml  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    yaml = None

REPO = Path(__file__).resolve().parent.parent
CASES = REPO / "evals" / "agent" / "cases.yaml"
RUNS = REPO / "evals" / "agent" / "runs"
SKILL_NAME = "embedded-engineering"
DEFAULT_JUDGE = "magpie/antigravity/gemini-4-argon"
PASS, FAIL, NOT_RUN, BLOCKED = "PASS", "FAIL", "NOT_RUN", "BLOCKED"
CLAUDE_DENIED = "Bash Edit Write NotebookEdit WebFetch WebSearch"
CASE_KEYS = {"id", "category", "prompt", "expect_skill", "contains_all", "not_contains", "rubric"}


# --------------------------------------------------------------------------- 用例

def load_cases(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    seen = set()
    for case in data["cases"]:
        unknown = set(case) - CASE_KEYS
        if unknown or not case.get("id") or not case.get("prompt") or not case.get("category"):
            raise ValueError(f"bad case {case.get('id')}: needs id/category/prompt, unknown keys {sorted(unknown)}")
        if case["id"] in seen:
            raise ValueError(f"duplicate case id {case['id']}")
        seen.add(case["id"])
        if "expect_skill" not in case and not case.get("contains_all") and not case.get("rubric") \
                and not case.get("not_contains"):
            raise ValueError(f"case {case['id']} has nothing to check")
    return data


# --------------------------------------------------------------------------- 沙箱

def make_sandbox(agent: str, sandbox_project: str, root: Path) -> Path:
    """复制验证工程的 good/ 为 git 仓库，并用 install.sh 安装技能（与用户实际安装方式一致）。"""
    repo = root / f"repo-{agent}"
    shutil.copytree(REPO / "evals" / "projects" / sandbox_project / "good", repo)
    git = ["git", "-C", str(repo), "-c", "user.email=eval@example.invalid", "-c", "user.name=eval"]
    subprocess.run(git[:3] + ["init", "-q"], check=True)
    subprocess.run(git + ["add", "-A"], check=True)
    subprocess.run(git + ["commit", "-qm", "sandbox"], check=True)
    subprocess.run(["sh", str(REPO / "install.sh"), "--agent", agent, "--project-dir", str(repo)],
                   check=True, capture_output=True)
    return repo


# --------------------------------------------------------------------------- Agent 运行与解析

def run_claude(prompt: str, repo: Path, raw: Path, timeout: int) -> dict:
    cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose", "--setting-sources", "project",
           "--strict-mcp-config", "--no-session-persistence", "--disallowedTools", CLAUDE_DENIED]
    proc = subprocess.run(cmd, cwd=repo, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                          timeout=timeout, check=False)
    raw.write_text(proc.stdout, encoding="utf-8")
    return {"exit_code": proc.returncode, **parse_claude(proc.stdout),
            "stderr_tail": proc.stderr.strip().splitlines()[-5:]}


def parse_claude(stdout: str) -> dict:
    """解析 claude -p --output-format stream-json 的事件流。"""
    tools, final, cost, skill = [], "", None, False
    for line in stdout.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if not isinstance(ev, dict):
            continue  # 合法 JSON 但不是事件对象（例如日志字符串）
        if ev.get("type") == "assistant":
            for c in ev.get("message", {}).get("content", []):
                if c.get("type") == "tool_use":
                    blob = json.dumps(c.get("input", {}), ensure_ascii=False)
                    tools.append(f"{c['name']} {blob[:100]}")
                    # Skill 工具调用，或直接读取技能文件，都算使用了技能
                    if (c["name"] == "Skill" and SKILL_NAME in blob) or f"skills/{SKILL_NAME}/" in blob:
                        skill = True
        elif ev.get("type") == "result":
            final = ev.get("result") or ""
            cost = ev.get("total_cost_usd")
    return {"final": final, "skill_used": skill, "tools": tools, "cost_usd": cost}


def run_codex(prompt: str, repo: Path, raw: Path, timeout: int) -> dict:
    cmd = ["codex", "exec", "--json", "--sandbox", "read-only", "--skip-git-repo-check", "--ephemeral",
           "-C", str(repo), prompt]
    proc = subprocess.run(cmd, cwd=repo, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                          timeout=timeout, check=False)
    raw.write_text(proc.stdout, encoding="utf-8")
    return {"exit_code": proc.returncode, **parse_codex(proc.stdout),
            "stderr_tail": proc.stderr.strip().splitlines()[-5:]}


def parse_codex(stdout: str) -> dict:
    """解析 codex exec --json 的事件流（JSONL）。"""
    tools, final, usage, skill = [], "", None, False
    for line in stdout.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if not isinstance(ev, dict):
            continue  # 合法 JSON 但不是事件对象（例如日志字符串）
        item = ev.get("item") or {}
        if ev.get("type") == "item.completed" and item.get("type") not in (None, "agent_message", "reasoning"):
            blob = json.dumps(item, ensure_ascii=False)
            tools.append(f"{item.get('type')} {str(item.get('command', ''))[:100]}")
            if f"skills/{SKILL_NAME}/" in blob:
                skill = True
        if item.get("type") == "agent_message":
            final = item.get("text") or final
        if ev.get("type") == "turn.completed":
            usage = ev.get("usage")
    return {"final": final, "skill_used": skill, "tools": tools, "usage": usage}


RUNNERS = {"claude": run_claude, "codex": run_codex}


# --------------------------------------------------------------------------- 判定

def deterministic_checks(case: dict, run: dict) -> list[dict]:
    text = run["final"].casefold()
    results = []
    if "expect_skill" in case:
        ok = run["skill_used"] == case["expect_skill"]
        results.append({"check": "expect_skill", "pass": ok,
                        "detail": f"expected {case['expect_skill']}, skill_used={run['skill_used']}"})
    for item in case.get("contains_all") or []:
        options = item if isinstance(item, list) else [item]
        ok = any(str(o).casefold() in text for o in options)
        results.append({"check": "contains", "pass": ok, "detail": " | ".join(map(str, options))})
    for pattern in case.get("not_contains") or []:
        hit = re.search(pattern, run["final"], re.IGNORECASE)
        results.append({"check": "not_contains", "pass": hit is None, "detail": pattern})
    return results


JUDGE_PROMPT = """你是独立评审。下面是用户给一个编程 Agent 的请求，以及该 Agent 的最终回答。
请逐条判断回答是否满足“要求”中的每一条。只依据回答文本本身判断；不要因语气、篇幅或格式加分或减分；
回答没有明确做到的，判为不满足。

只输出一个 JSON 对象，不要输出其他任何文字：
{{"items": [{{"index": 1, "pass": true, "reason": "一句话理由"}}]}}

【用户请求】
{prompt}

【要求】
{rubric}

【Agent 的最终回答】
{answer}
"""


def judge(case: dict, run: dict, model: str, timeout: int) -> dict:
    rubric = "\n".join(f"{i}. {r}" for i, r in enumerate(case["rubric"], 1))
    prompt = JUDGE_PROMPT.format(prompt=case["prompt"], rubric=rubric, answer=run["final"][:12000])
    cmd = ["omp", "-p", "--model", model, "--thinking", "low", "--no-tools", "--no-session", "--no-skills",
           "--no-rules", "--no-context-files", "--no-extensions", prompt]
    try:
        proc = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout,
                              check=False, cwd=tempfile.gettempdir())
    except subprocess.TimeoutExpired:
        return {"status": BLOCKED, "reason": "judge timeout"}
    match = re.search(r"\{.*\}", proc.stdout, re.DOTALL)
    try:
        items = json.loads(match.group(0))["items"] if match else None
    except (ValueError, KeyError, TypeError):
        items = None
    if not isinstance(items, list) or len(items) != len(case["rubric"]):
        return {"status": BLOCKED, "reason": "judge output not parseable", "raw": proc.stdout[-800:]}
    return {"status": PASS if all(bool(i.get("pass")) for i in items) else FAIL, "items": items}


def evaluate(agent: str, case: dict, repo: Path, outdir: Path, args) -> dict:
    raw = outdir / agent / f"{case['id']}.jsonl"
    raw.parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    try:
        run = RUNNERS[agent](case["prompt"], repo, raw, args.timeout)
    except subprocess.TimeoutExpired:
        return {"agent": agent, "id": case["id"], "category": case["category"], "status": BLOCKED,
                "reason": f"agent timeout after {args.timeout} s"}
    run["seconds"] = round(time.monotonic() - start, 1)
    record = {"agent": agent, "id": case["id"], "category": case["category"], "run": run}
    if run["exit_code"] != 0 or not run["final"].strip():
        record.update(status=BLOCKED, reason=f"agent exit {run['exit_code']} or empty answer")
        return record
    checks = deterministic_checks(case, run)
    record["checks"] = checks
    det_ok = all(c["pass"] for c in checks)
    if case.get("rubric"):
        if args.no_judge:
            record["judge"] = {"status": NOT_RUN, "reason": "--no-judge"}
        else:
            record["judge"] = judge(case, run, args.judge_model, args.timeout)
        jstat = record["judge"]["status"]
        if not det_ok or jstat == FAIL:
            record["status"] = FAIL
        elif jstat == PASS:
            record["status"] = PASS
        else:
            record["status"] = NOT_RUN  # 确定性检查通过，但评委没有给出可用结论
    else:
        record["status"] = PASS if det_ok else FAIL
    return record


# --------------------------------------------------------------------------- 汇总

def summarize(records: list[dict], cases: list[dict]) -> dict:
    by_agent: dict[str, dict] = {}
    expect = {c["id"]: c.get("expect_skill") for c in cases}
    for rec in records:
        agg = by_agent.setdefault(rec["agent"], {"status": {PASS: 0, FAIL: 0, NOT_RUN: 0, BLOCKED: 0},
                                                 "by_category": {}, "should_trigger": 0, "triggered": 0,
                                                 "should_not": 0, "false_triggers": 0, "cost_usd": 0.0})
        agg["status"][rec["status"]] += 1
        cat = agg["by_category"].setdefault(rec["category"], {PASS: 0, FAIL: 0, NOT_RUN: 0, BLOCKED: 0})
        cat[rec["status"]] += 1
        run = rec.get("run") or {}
        if run.get("cost_usd"):
            agg["cost_usd"] += run["cost_usd"]
        if "skill_used" in run:
            if expect[rec["id"]] is True:
                agg["should_trigger"] += 1
                agg["triggered"] += int(run["skill_used"])
            elif expect[rec["id"]] is False:
                agg["should_not"] += 1
                agg["false_triggers"] += int(run["skill_used"])
    return by_agent


def render(report: dict, cases: list[dict]) -> str:
    lines = ["# Agent 行为评测结果", "",
             f"生成时间：{report['generated']}；技能提交：`{report['commit']}`；评委：`{report['judge_model']}`。"
             "本文件由 `tools/run_agent_evals.py` 生成，不要手改。", "",
             "每个用例每个 Agent 只运行一次；Agent 输出有随机性，单次结果不代表稳定通过率。", ""]
    for agent, agg in report["summary"].items():
        s = agg["status"]
        recall = f"{agg['triggered']}/{agg['should_trigger']}" if agg["should_trigger"] else "—"
        false_rate = f"{agg['false_triggers']}/{agg['should_not']}" if agg["should_not"] else "—"
        lines += [f"## {agent}", "",
                  f"PASS {s[PASS]}，FAIL {s[FAIL]}，NOT_RUN {s[NOT_RUN]}，BLOCKED {s[BLOCKED]}；"
                  f"应触发用例中实际使用技能 {recall}，不应触发用例中误用技能 {false_rate}"
                  + (f"；花费约 ${agg['cost_usd']:.2f}" if agg["cost_usd"] else "") + "。", "",
                  "| 类别 | PASS | FAIL | NOT_RUN | BLOCKED |", "| --- | --- | --- | --- | --- |"]
        for cat, c in sorted(agg["by_category"].items()):
            lines.append(f"| {cat} | {c[PASS]} | {c[FAIL]} | {c[NOT_RUN]} | {c[BLOCKED]} |")
        lines += ["", "| 用例 | 类别 | 结果 | 使用技能 | 未通过的检查 |", "| --- | --- | --- | --- | --- |"]
        for rec in [r for r in report["records"] if r["agent"] == agent]:
            run = rec.get("run") or {}
            failed = [f"{c['check']}: {c['detail']}" for c in rec.get("checks", []) if not c["pass"]]
            jd = rec.get("judge") or {}
            for item in jd.get("items", []) or []:
                if not item.get("pass"):
                    failed.append(f"rubric {item.get('index')}: {str(item.get('reason', ''))[:80]}")
            if jd.get("status") in (NOT_RUN, BLOCKED):
                failed.append(f"judge {jd['status']}: {jd.get('reason', '')}")
            if rec.get("reason"):
                failed.append(rec["reason"])
            cell = "；".join(failed).replace("|", "\\|") or "—"
            used = {True: "是", False: "否"}.get(run.get("skill_used"), "—")
            lines.append(f"| {rec['id']} | {rec['category']} | {rec['status']} | {used} | {cell} |")
        lines.append("")
    return "\n".join(lines)


def git_commit() -> str:
    out = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"], capture_output=True,
                         text=True, check=False).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain", "--", "skills"],
                           capture_output=True, text=True, check=False).stdout.strip()
    return (out + ("-dirty" if dirty else "")) or "unknown"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("--agents", default="claude,codex")
    ap.add_argument("--cases", default="", help="comma-separated case ids (default: all)")
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--judge-model", default=DEFAULT_JUDGE)
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--report", type=Path)
    args = ap.parse_args(argv)
    if yaml is None:
        print("error: PyYAML is required; run: uv run --with pyyaml python3 tools/run_agent_evals.py", file=sys.stderr)
        return 2
    try:
        data = load_cases(CASES)
    except (ValueError, KeyError, yaml.YAMLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    wanted = {c.strip() for c in args.cases.split(",") if c.strip()}
    cases = [c for c in data["cases"] if not wanted or c["id"] in wanted]
    agents = [a.strip() for a in args.agents.split(",") if a.strip()]
    for agent in agents:
        if agent not in RUNNERS:
            print(f"error: unknown agent {agent}", file=sys.stderr)
            return 2
    if not args.no_judge and shutil.which("omp") is None:
        print("warning: omp not found; rubric checks will be NOT_RUN", file=sys.stderr)
        args.no_judge = True

    stamp = time.strftime("%Y%m%d-%H%M%S")
    outdir = RUNS / stamp
    records: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="agent-eval-") as tmp:
        repos = {}
        for agent in agents:
            if shutil.which(agent) is None:
                records += [{"agent": agent, "id": c["id"], "category": c["category"], "status": NOT_RUN,
                             "reason": f"{agent} CLI not found"} for c in cases]
                continue
            repos[agent] = make_sandbox(agent, data["sandbox"], Path(tmp))
        jobs = [(a, c) for a in repos for c in cases]
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = {pool.submit(evaluate, a, c, repos[a], outdir, args): (a, c) for a, c in jobs}
            for fut in concurrent.futures.as_completed(futures):
                rec = fut.result()
                records.append(rec)
                print(f"{rec['agent']}/{rec['id']}: {rec['status']}  skill_used="
                      f"{(rec.get('run') or {}).get('skill_used')}", flush=True)
    order = {c["id"]: i for i, c in enumerate(cases)}
    records.sort(key=lambda r: (r["agent"], order[r["id"]]))
    report = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "commit": git_commit(),
              "judge_model": None if args.no_judge else args.judge_model, "records": records,
              "summary": summarize(records, cases)}
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.report:
        args.report.write_text(render(report, cases), encoding="utf-8")
    for agent, agg in report["summary"].items():
        print(f"{agent}: {agg['status']}  trigger {agg['triggered']}/{agg['should_trigger']}  "
              f"false {agg['false_triggers']}/{agg['should_not']}")
    print(f"raw logs: {outdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
