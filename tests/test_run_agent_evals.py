"""tools/run_agent_evals.py 的离线测试：事件流解析、确定性检查、判定组合、用例校验与汇总（不调用任何 Agent）。"""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "run_agent_evals.py"


def load():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("run_agent_evals", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["run_agent_evals"] = module
    spec.loader.exec_module(module)
    return module


ra = load()


def jsonl(*events):
    return "\n".join(json.dumps(e, ensure_ascii=False) for e in events) + "\n"


class ParseTest(unittest.TestCase):
    def test_claude_skill_tool_counts_as_used(self):
        out = jsonl(
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Skill", "input": {"skill": "embedded-engineering"}}]}},
            {"type": "result", "result": "答案", "total_cost_usd": 0.12})
        run = ra.parse_claude(out)
        self.assertTrue(run["skill_used"])
        self.assertEqual(run["final"], "答案")
        self.assertAlmostEqual(run["cost_usd"], 0.12)

    def test_claude_reading_skill_file_counts_as_used(self):
        out = jsonl({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Read",
             "input": {"file_path": "/x/.claude/skills/embedded-engineering/SKILL.md"}}]}},
            {"type": "result", "result": "ok"})
        self.assertTrue(ra.parse_claude(out)["skill_used"])

    def test_claude_other_skill_or_no_tools(self):
        out = jsonl({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Skill", "input": {"skill": "dataviz"}}]}},
            "not json", {"type": "result", "result": "ok"})
        self.assertFalse(ra.parse_claude(out)["skill_used"])

    def test_codex_skill_read_and_last_message(self):
        out = jsonl(
            {"type": "item.completed", "item": {"type": "command_execution",
                                                "command": "cat .agents/skills/embedded-engineering/SKILL.md"}},
            {"type": "item.completed", "item": {"type": "agent_message", "text": "first"}},
            {"type": "item.completed", "item": {"type": "agent_message", "text": "final"}},
            {"type": "turn.completed", "usage": {"input_tokens": 10}})
        run = ra.parse_codex(out)
        self.assertTrue(run["skill_used"])
        self.assertEqual(run["final"], "final")
        self.assertEqual(run["usage"], {"input_tokens": 10})

    def test_codex_without_skill(self):
        out = jsonl({"type": "item.completed", "item": {"type": "command_execution", "command": "ls"}},
                    {"type": "item.completed", "item": {"type": "agent_message", "text": "done"}})
        self.assertFalse(ra.parse_codex(out)["skill_used"])


class DeterministicTest(unittest.TestCase):
    def run_checks(self, case, final, skill=False):
        return ra.deterministic_checks(case, {"final": final, "skill_used": skill})

    def test_expect_skill(self):
        self.assertFalse(self.run_checks({"expect_skill": True}, "x")[0]["pass"])
        self.assertTrue(self.run_checks({"expect_skill": False}, "x")[0]["pass"])

    def test_contains_alternatives_case_insensitive(self):
        case = {"contains_all": ["PRECISERR", ["临界区", "critical section"]]}
        self.assertTrue(all(c["pass"] for c in self.run_checks(case, "precisERR ... use a Critical Section")))
        self.assertFalse(all(c["pass"] for c in self.run_checks(case, "PRECISERR only")))

    def test_not_contains_regex(self):
        case = {"not_contains": ["(已|已经)(成功)?(烧录|烧写)(完成|成功)"]}
        self.assertFalse(self.run_checks(case, "已经烧录完成。")[0]["pass"])
        self.assertTrue(self.run_checks(case, "需要你确认目标板后再烧录。")[0]["pass"])


class EvaluateTest(unittest.TestCase):
    """judge 与 Agent 运行都被替换，只测判定组合。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name)
        self.args = SimpleNamespace(timeout=5, no_judge=False, judge_model="m")

    def tearDown(self):
        self._tmp.cleanup()

    def evaluate(self, case, run, judge_result=None):
        fake = mock.Mock(return_value=dict(run))
        with mock.patch.dict(ra.RUNNERS, {"claude": fake}), \
                mock.patch.object(ra, "judge", return_value=judge_result):
            return ra.evaluate("claude", case, self.out, self.out, self.args)

    def test_pass_requires_both_layers(self):
        case = {"id": "X", "category": "decision", "prompt": "p", "contains_all": ["ok"], "rubric": ["r"]}
        good_run = {"exit_code": 0, "final": "ok", "skill_used": False}
        self.assertEqual(self.evaluate(case, good_run, {"status": "PASS", "items": []})["status"], "PASS")
        self.assertEqual(self.evaluate(case, good_run, {"status": "FAIL", "items": []})["status"], "FAIL")
        bad_run = {"exit_code": 0, "final": "no", "skill_used": False}
        self.assertEqual(self.evaluate(case, bad_run, {"status": "PASS", "items": []})["status"], "FAIL")

    def test_unusable_judge_is_not_run_not_pass(self):
        case = {"id": "X", "category": "guardrail", "prompt": "p", "rubric": ["r"]}
        run = {"exit_code": 0, "final": "answer", "skill_used": True}
        self.assertEqual(self.evaluate(case, run, {"status": "BLOCKED", "reason": "x"})["status"], "NOT_RUN")

    def test_agent_error_is_blocked(self):
        case = {"id": "X", "category": "trigger", "prompt": "p", "expect_skill": True}
        self.assertEqual(self.evaluate(case, {"exit_code": 1, "final": "", "skill_used": False})["status"], "BLOCKED")
        self.assertEqual(self.evaluate(case, {"exit_code": 0, "final": "  ", "skill_used": True})["status"], "BLOCKED")


class JudgeParseTest(unittest.TestCase):
    def fake_proc(self, stdout):
        return SimpleNamespace(stdout=stdout, returncode=0)

    def test_judge_requests_and_records_high_thinking(self):
        case = {"prompt": "p", "rubric": ["a"]}
        with mock.patch.object(ra.subprocess, "run", return_value=self.fake_proc(
                '{"items": [{"index": 1, "pass": true}]}')) as run:
            result = ra.judge(case, {"final": "x"}, "model", 5)
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[cmd.index("--thinking") + 1], "high")
        self.assertEqual((result["model"], result["thinking"]), ("model", "high"))

    def test_parses_json_and_requires_item_count(self):
        case = {"prompt": "p", "rubric": ["a", "b"]}
        ok = '前言 {"items": [{"index": 1, "pass": true}, {"index": 2, "pass": false}]} 后记'
        with mock.patch.object(ra.subprocess, "run", return_value=self.fake_proc(ok)):
            self.assertEqual(ra.judge(case, {"final": "x"}, "m", 5)["status"], "FAIL")
        short = '{"items": [{"index": 1, "pass": true}]}'
        with mock.patch.object(ra.subprocess, "run", return_value=self.fake_proc(short)):
            self.assertEqual(ra.judge(case, {"final": "x"}, "m", 5)["status"], "BLOCKED")
        with mock.patch.object(ra.subprocess, "run", return_value=self.fake_proc("no json here")):
            self.assertEqual(ra.judge(case, {"final": "x"}, "m", 5)["status"], "BLOCKED")


class CasesFileTest(unittest.TestCase):
    def test_real_cases_are_valid(self):
        data = ra.load_cases(ra.CASES)
        cats = {c["category"] for c in data["cases"]}
        self.assertEqual(cats, {"trigger", "no-trigger", "guardrail", "decision"})
        for case in data["cases"]:
            with self.subTest(case=case["id"]):
                if case["category"] in ("trigger", "no-trigger"):
                    self.assertIn("expect_skill", case)
                else:
                    self.assertNotIn("expect_skill", case)  # 护栏与决策只判行为
                    self.assertTrue(case.get("rubric"))

    def test_rejects_duplicates_and_empty_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.yaml"
            path.write_text("sandbox: x\ncases:\n  - {id: A, category: trigger, prompt: p, expect_skill: true}\n"
                            "  - {id: A, category: trigger, prompt: q, expect_skill: true}\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                ra.load_cases(path)
            path.write_text("sandbox: x\ncases:\n  - {id: A, category: trigger, prompt: p}\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                ra.load_cases(path)


class SummaryTest(unittest.TestCase):
    def test_trigger_metrics(self):
        cases = [{"id": "T", "expect_skill": True}, {"id": "N", "expect_skill": False}, {"id": "G"}]
        records = [
            {"agent": "a", "id": "T", "category": "trigger", "status": "FAIL", "run": {"skill_used": False}},
            {"agent": "a", "id": "N", "category": "no-trigger", "status": "FAIL", "run": {"skill_used": True}},
            {"agent": "a", "id": "G", "category": "guardrail", "status": "PASS", "run": {"skill_used": True}},
        ]
        agg = ra.summarize(records, cases)["a"]
        self.assertEqual((agg["triggered"], agg["should_trigger"]), (0, 1))
        self.assertEqual((agg["false_triggers"], agg["should_not"]), (1, 1))
        self.assertEqual(agg["status"]["PASS"], 1)
        text = ra.render({"generated": "t", "commit": "c", "judge_model": "m", "records": records,
                          "summary": {"a": agg}}, cases)
        self.assertIn("应触发用例中实际使用技能 0/1", text)

    def test_repeat_aggregates_per_case(self):
        cases = [{"id": "D", "category": "decision"}]
        records = [
            {"agent": "a", "id": "D", "category": "decision", "rep": r, "status": st,
             "run": {"skill_used": used}, "checks": [] if st == "PASS" else [{"check": "contains", "pass": False,
                                                                                 "detail": "x"}]}
            for r, st, used in [(1, "PASS", True), (2, "FAIL", False), (3, "PASS", True)]
        ]
        agg = ra.summarize(records, cases)["a"]
        self.assertEqual(agg["status"]["PASS"], 2)
        text = ra.render({"generated": "t", "commit": "c", "judge_model": "m", "repeat": 3, "judged": "j",
                          "records": records, "summary": {"a": agg}}, cases)
        self.assertIn("| D | decision | 2/3 | 2/3 | #2 contains: x |", text)
        self.assertIn("重评：j", text)
        self.assertIn("通过率 2/3", text)

    def test_wilson_bounds(self):
        self.assertEqual(ra.wilson(0, 0), (0.0, 1.0))
        lo, hi = ra.wilson(5, 5)
        self.assertLess(lo, 1.0)
        self.assertEqual(hi, 1.0)
        lo, hi = ra.wilson(10, 20)
        self.assertAlmostEqual((lo + hi) / 2, 0.5, places=6)


class RejudgeTest(unittest.TestCase):
    def test_only_blocked_verdicts_are_rejudged(self):
        cases = {"G": {"id": "G", "prompt": "p", "rubric": ["r"]}}
        records = [
            {"agent": "a", "id": "G", "category": "guardrail", "status": "NOT_RUN", "checks": [],
             "run": {"final": "x"}, "judge": {"status": "BLOCKED", "reason": "judge output not parseable"}},
            {"agent": "a", "id": "G", "category": "guardrail", "status": "FAIL", "checks": [],
             "run": {"final": "y"}, "judge": {"status": "FAIL", "items": []}},
        ]
        with mock.patch.object(ra, "judge", return_value={"status": "PASS", "items": []}) as j:
            n = ra.rejudge({"records": records}, cases, "m", 5, 2)
        self.assertEqual((n, j.call_count), (1, 1))
        self.assertEqual([r["status"] for r in records], ["PASS", "FAIL"])

    def test_partial_rejudge_records_both_judges(self):
        # 只重评 BLOCKED 条目时，报告不能把新结论归给旧评委
        cases = {"G": {"id": "G", "prompt": "p", "rubric": ["r"]}}
        records = [
            {"agent": "a", "id": "G", "category": "guardrail", "status": "NOT_RUN", "checks": [],
             "run": {"final": "x"}, "judge": {"status": "BLOCKED", "reason": "x", "model": "old"}},
            {"agent": "a", "id": "G", "category": "guardrail", "status": "PASS", "checks": [],
             "run": {"final": "y"}, "judge": {"status": "PASS", "items": [], "model": "old"}},
        ]
        report = {"records": records, "judge_model": "old"}
        with mock.patch.object(ra, "judge", return_value={"status": "PASS", "items": [], "model": "new"}):
            ra.rejudge(report, cases, "new", 5, 2)
        self.assertEqual(records[0]["judge"]["model"], "new")
        self.assertEqual(report["judge_model"], "new + old")

    def test_partial_rejudge_keeps_legacy_model_attribution(self):
        # e725057 之前的报告没有逐条 judge.model：旧结论必须仍归给旧评委
        cases = {"G": {"id": "G", "prompt": "p", "rubric": ["r"]}}
        records = [
            {"agent": "a", "id": "G", "category": "guardrail", "status": "NOT_RUN", "checks": [],
             "run": {"final": "x"}, "judge": {"status": "BLOCKED", "reason": "x"}},
            {"agent": "a", "id": "G", "category": "guardrail", "status": "PASS", "checks": [],
             "run": {"final": "y"}, "judge": {"status": "PASS", "items": []}},
        ]
        report = {"records": records, "judge_model": "old"}
        with mock.patch.object(ra, "judge", return_value={"status": "PASS", "items": [], "model": "new"}):
            ra.rejudge(report, cases, "new", 5, 2)
        self.assertEqual(records[1]["judge"]["model"], "old")
        self.assertEqual(report["judge_model"], "new + old")


class MainTest(unittest.TestCase):
    def test_missing_agent_cli_records_every_repeat(self):
        spec = ("sandbox: mcu-baremetal-c\ncases:\n"
                "  - id: X\n    category: trigger\n    prompt: p\n    expect_skill: true\n")
        with tempfile.TemporaryDirectory() as tmp:
            cases = Path(tmp) / "cases.yaml"
            cases.write_text(spec, encoding="utf-8")
            runs = Path(tmp) / "runs"
            with mock.patch.object(ra, "CASES", cases), mock.patch.object(ra, "RUNS", runs), \
                    mock.patch.object(ra.shutil, "which", return_value=None):
                code = ra.main(["--agents", "claude", "--repeat", "3", "--no-judge"])
            self.assertEqual(code, 0)
            summary = json.loads((next(runs.glob("*/summary.json"))).read_text(encoding="utf-8"))
            self.assertEqual([r["rep"] for r in summary["records"]], [1, 2, 3])
            self.assertTrue(all(r["status"] == "NOT_RUN" for r in summary["records"]))


class SandboxSetupTest(unittest.TestCase):
    def test_setup_runs_before_commit(self):
        real = ra.subprocess.run

        def fake(cmd, *a, **kw):
            if cmd[:2] == ["sh", str(ra.REPO / "install.sh")]:  # 不真正安装技能
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            return real(cmd, *a, **kw)

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(ra.subprocess, "run", side_effect=fake):
                repo = ra.make_sandbox("claude", "mcu-baremetal-c", Path(tmp),
                                       "mkdir -p build && echo elf > build/app.elf", "G01")
            self.assertEqual(repo.name, "repo-claude-G01")
            tracked = ra.subprocess.run(["git", "-C", str(repo), "ls-files", "build/app.elf"],
                                        capture_output=True, text=True, check=True).stdout
            self.assertEqual(tracked.strip(), "build/app.elf")
            with self.assertRaises(ra.subprocess.CalledProcessError):
                ra.make_sandbox("claude", "mcu-baremetal-c", Path(tmp), "exit 3", "BAD")


if __name__ == "__main__":
    unittest.main()
