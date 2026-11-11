"""tools/run_evals.py 回归测试：用合成的小工程覆盖判定语义与定义校验。python3 -m unittest discover -s tests -v"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "run_evals.py"


def load_runner():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("run_evals", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["run_evals"] = module
    spec.loader.exec_module(module)
    return module


re_ = load_runner()
RULES = re_.load_rules()


class RunnerTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.values = re_.placeholders(self.root / "prefix")
        self.values["_path"] = os.environ.get("PATH", "")

    def tearDown(self):
        self._tmp.cleanup()

    def project(self, eval_yaml, files=None, name="demo"):
        path = self.root / name
        (path / "good").mkdir(parents=True)
        (path / "good" / "keep.txt").write_text("x", encoding="utf-8")
        for rel, text in (files or {}).items():
            target = path / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        (path / "eval.yaml").write_text(textwrap.dedent(eval_yaml), encoding="utf-8")
        return path

    def load(self, path):
        return re_.load_project(path, RULES)


# good 中没有 marker；变体叠加 marker 后 check 失败
BASE = """\
project: demo
profile: mcu-baremetal
checks:
  marker:
    run: "test ! -f marker"
    rules: [ARCH-001]
variants:
  good: {}
  bad-marker:
    violates: [ARCH-001]
    expect: {marker: FAIL}
"""


class VerdictTest(RunnerTestBase):
    def test_known_gap_is_separate_from_match_and_coverage(self):
        text = BASE.replace('    expect: {marker: FAIL}', '    known_gap: "review only"')
        proj = self.load(self.project(text, {"variants/bad-marker/x.txt": "1"}))
        res = re_.run_variant(proj, "bad-marker", self.values, False)
        self.assertEqual(res["verdict"], "KNOWN_GAP")
        self.assertEqual(res["detected_by"], [])
        coverage = re_.rule_coverage([proj], RULES)
        self.assertNotIn("ARCH-001", coverage["exercised"])
        self.assertNotIn("ARCH-001", coverage["auto_exercised"])

    def test_known_gap_does_not_mask_mismatch_or_not_run(self):
        for command, status in (("false", "MISMATCH"), ("exit 2", "NOT_RUN")):
            with self.subTest(command=command):
                text = BASE.replace('    expect: {marker: FAIL}', '    known_gap: "review only"')
                text = text.replace('run: "test ! -f marker"', f'run: "{command}"\n    blocked_codes: [2]')
                name = "demo-" + status.lower()
                text = text.replace("project: demo", f"project: {name}")
                proj = self.load(self.project(text, {"variants/bad-marker/x.txt": "1"}, name=name))
                self.assertEqual(re_.run_variant(proj, "bad-marker", self.values, False)["verdict"], status)

    def test_known_gap_with_expected_failure_still_matches_but_is_not_coverage(self):
        text = BASE.replace('    expect: {marker: FAIL}',
                            '    expect: {marker: FAIL}\n    known_gap: "partial detection only"')
        proj = self.load(self.project(text, {"variants/bad-marker/marker": "1"}))
        self.assertEqual(re_.run_variant(proj, "bad-marker", self.values, False)["verdict"], "MATCH")
        self.assertNotIn("ARCH-001", re_.rule_coverage([proj], RULES)["exercised"])

    def test_strict_accepts_known_gap_and_reports_it_separately(self):
        text = BASE.replace('    expect: {marker: FAIL}', '    known_gap: "review only"')
        self.project(text, {"variants/bad-marker/x.txt": "1"})
        result = self.root / "result.json"
        markdown = self.root / "result.md"
        with patch.object(re_, "EVALS", self.root), patch.object(re_, "tool_path", return_value=self.values["_path"]):
            self.assertEqual(re_.main(["demo", "--strict", "--json", str(result), "--report", str(markdown)]), 0)
        self.assertEqual(json.loads(result.read_text())["summary"],
                         {"MATCH": 1, "KNOWN_GAP": 1, "MISMATCH": 0, "NOT_RUN": 0})
        self.assertIn("问题变体检出 0 + 已知漏报 1", markdown.read_text())

    def test_failure_requires_matching_diagnostic_from_full_output(self):
        text = BASE.replace('    run: "test ! -f marker"',
                            '    run: "if test -f marker; then cat marker; seq 1 60; exit 1; fi"')
        text += '    expect_output: {marker: "driver/timer[.]h: No such file"}\n'
        proj = self.load(self.project(text, {"variants/bad-marker/marker": "driver/timer.h: No such file"}))
        res = re_.run_variant(proj, "bad-marker", self.values, False)
        self.assertEqual(res["verdict"], "MATCH")
        self.assertNotIn("driver/timer.h", "\n".join(res["checks"]["marker"]["output_tail"]))
        (proj["_path"] / "variants/bad-marker/marker").write_text("unrelated compiler error")
        res = re_.run_variant(proj, "bad-marker", self.values, False)
        self.assertEqual(res["verdict"], "MISMATCH")
        self.assertEqual(res["mismatches"], ["marker"])
        self.assertIn("diagnostic not found", res["checks"]["marker"]["reason"])

    def test_timeout_cannot_satisfy_failure_diagnostic(self):
        text = BASE.replace('    run: "test ! -f marker"', '    run: "sleep 5"\n    timeout: 0.01')
        text += '    expect_output: {marker: "missing header"}\n'
        proj = self.load(self.project(text, {"variants/bad-marker/marker": "1"}))
        self.assertEqual(re_.run_variant(proj, "bad-marker", self.values, False)["verdict"], "MISMATCH")

    def test_match_for_good_and_detected_bad(self):
        proj = self.load(self.project(BASE, {"variants/bad-marker/marker": "1"}))
        self.assertEqual(re_.run_variant(proj, "good", self.values, False)["verdict"], "MATCH")
        bad = re_.run_variant(proj, "bad-marker", self.values, False)
        self.assertEqual(bad["verdict"], "MATCH")
        self.assertEqual(bad["detected_by"], ["marker"])

    def test_mismatch_when_bad_is_not_detected(self):
        # 变体目录存在但没有放 marker：检查通过，与预期 FAIL 不符
        proj = self.load(self.project(BASE, {"variants/bad-marker/other.txt": "1"}))
        res = re_.run_variant(proj, "bad-marker", self.values, False)
        self.assertEqual(res["verdict"], "MISMATCH")
        self.assertEqual(res["mismatches"], ["marker"])

    def test_missing_tool_is_not_run_not_pass(self):
        text = BASE.replace('    run: "test ! -f marker"\n',
                            '    run: "test ! -f marker"\n    requires: [definitely-not-a-real-tool-xyz]\n')
        proj = self.load(self.project(text, {"variants/bad-marker/marker": "1"}))
        res = re_.run_variant(proj, "good", self.values, False)
        self.assertEqual(res["checks"]["marker"]["status"], "NOT_RUN")
        self.assertEqual(res["verdict"], "NOT_RUN")

    def test_missing_path_requirement_is_not_run(self):
        text = BASE.replace('    run: "test ! -f marker"\n',
                            '    run: "test ! -f marker"\n    requires: ["{prefix}/nope/lib.a"]\n')
        proj = self.load(self.project(text, {"variants/bad-marker/marker": "1"}))
        self.assertEqual(re_.run_variant(proj, "good", self.values, False)["checks"]["marker"]["status"], "NOT_RUN")

    def test_needs_blocks_and_expected_blocked_matches(self):
        text = """\
            project: demo
            profile: mcu-baremetal
            checks:
              build:
                run: "test ! -f broken"
                rules: [CPP-008]
              cost:
                run: "true"
                needs: [build]
            variants:
              good: {}
              bad-link:
                violates: [CPP-008]
                expect: {build: FAIL, cost: BLOCKED}
              bad-link-unexpected:
                violates: [CPP-008]
                expect: {build: FAIL}
            """
        proj = self.load(self.project(text, {"variants/bad-link/broken": "1",
                                             "variants/bad-link-unexpected/broken": "1"}))
        res = re_.run_variant(proj, "bad-link", self.values, False)
        self.assertEqual(res["checks"]["cost"]["status"], "BLOCKED")
        self.assertEqual(res["verdict"], "MATCH")
        # 未预期的阻塞不能算通过：结论为 NOT_RUN
        self.assertEqual(re_.run_variant(proj, "bad-link-unexpected", self.values, False)["verdict"], "NOT_RUN")

    def test_blocked_exit_code(self):
        text = BASE.replace('    run: "test ! -f marker"\n', '    run: "exit 2"\n    blocked_codes: [2]\n')
        proj = self.load(self.project(text, {"variants/bad-marker/marker": "1"}))
        self.assertEqual(re_.run_variant(proj, "good", self.values, False)["checks"]["marker"]["status"], "BLOCKED")

    def test_timeout_is_failure(self):
        text = BASE.replace('    run: "test ! -f marker"\n', '    run: "sleep 5"\n    timeout: 1\n')
        proj = self.load(self.project(text, {"variants/bad-marker/marker": "1"}))
        res = re_.run_variant(proj, "good", self.values, False)
        self.assertEqual(res["checks"]["marker"]["status"], "FAIL")
        self.assertIn("timeout", res["checks"]["marker"]["reason"])

    def test_remove_deletes_files_from_good(self):
        text = BASE.replace('    run: "test ! -f marker"\n', '    run: "test -f keep.txt"\n').replace(
            "    expect: {marker: FAIL}\n", "    expect: {marker: FAIL}\n    remove: [keep.txt]\n")
        proj = self.load(self.project(text))
        self.assertEqual(re_.run_variant(proj, "bad-marker", self.values, False)["verdict"], "MATCH")

    def test_placeholders_and_env(self):
        text = BASE.replace('    run: "test ! -f marker"\n',
                            '    run: "test \\"$X\\" = \\"{prefix}/x\\""\n    env: {X: "{prefix}/x"}\n')
        proj = self.load(self.project(text, {"variants/bad-marker/marker": "1"}))
        self.assertEqual(re_.run_variant(proj, "good", self.values, False)["checks"]["marker"]["status"], "PASS")


class DefinitionTest(RunnerTestBase):
    def test_invalid_output_expectations_are_definition_errors(self):
        for expectation in ("[]", '{other: "missing header"}', '{marker: "["}', '{marker: ""}',
                            '{marker: 12}'):
            with self.subTest(expectation=expectation):
                with tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp) / "demo"
                    (path / "good").mkdir(parents=True)
                    (path / "variants/bad-marker").mkdir(parents=True)
                    (path / "eval.yaml").write_text(BASE + f"    expect_output: {expectation}\n")
                    with self.assertRaises(re_.DefinitionError) as ctx:
                        self.load(path)
                    self.assertIn("expect_output", str(ctx.exception))

    def assert_definition_error(self, text, fragment, files=None):
        path = self.project(text, files if files is not None else {"variants/bad-marker/marker": "1"})
        with self.assertRaises(re_.DefinitionError) as ctx:
            self.load(path)
        self.assertIn(fragment, str(ctx.exception))

    def test_unknown_rule(self):
        self.assert_definition_error(BASE.replace("violates: [ARCH-001]", "violates: [ARCH-999]"), "unknown rule")

    def test_bad_variant_needs_rules_or_defect(self):
        self.assert_definition_error(BASE.replace("    violates: [ARCH-001]\n", ""), "violated rules or describe the defect")

    def test_violation_without_detection_needs_known_gap(self):
        text = BASE.replace("violates: [ARCH-001]", "violates: [ISR-001]")
        self.assert_definition_error(text, "known_gap")

    def test_known_gap_allows_undetected_violation(self):
        text = BASE.replace("violates: [ARCH-001]\n    expect: {marker: FAIL}",
                            "violates: [ISR-001]\n    known_gap: \"review only\"")
        self.load(self.project(text, {"variants/bad-marker/x.txt": "1"}))

    def test_expected_blocked_requires_needs(self):
        self.assert_definition_error(BASE.replace("expect: {marker: FAIL}", "expect: {marker: BLOCKED}"),
                                     "requires the check to have needs")

    def test_good_cannot_expect_failures(self):
        self.assert_definition_error(BASE.replace("  good: {}", "  good:\n    expect: {marker: FAIL}"),
                                     "good must not")

    def test_project_name_must_match_directory(self):
        self.assert_definition_error(BASE.replace("project: demo", "project: other"), "directory name")

    def test_variant_without_overlay_or_remove(self):
        self.assert_definition_error(BASE, "neither variants/bad-marker/", files={})

    def test_needs_must_be_defined_earlier(self):
        text = BASE.replace('    rules: [ARCH-001]\n', '    rules: [ARCH-001]\n    needs: [marker]\n')
        self.assert_definition_error(text, "must be defined before it")


class CliTest(unittest.TestCase):
    def test_real_eval_definitions_are_valid(self):
        proc = subprocess.run([sys.executable, "-I", str(TOOL), "--list"], capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for name in ("mcu-baremetal-c", "freertos-cpp", "zephyr-app", "linux-userspace"):
            self.assertIn(name + ":", proc.stdout)


if __name__ == "__main__":
    unittest.main()
