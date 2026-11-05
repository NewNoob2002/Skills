"""tools/validate_skill.py 回归测试（仅标准库）：python3 -m unittest discover -s tests -v

做法：把真实技能复制到临时目录，逐项注入一个缺陷，断言对应检查为 FAIL、其余检查不受影响；
另有误报防护用例（代码块、./ 前缀路径）和 YAML 子集解析器单元测试。
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "validate_skill.py"
CONFIG = ROOT / "tools" / "validate_skill.json"
SKILL = ROOT / "skills" / "embedded-engineering"


def run_tool(*args):
    proc = subprocess.run([sys.executable, "-I", str(TOOL), *map(str, args)],
                          capture_output=True, text=True, check=False)
    return proc.returncode, proc.stdout, proc.stderr


def load_tool_module():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("validate_skill", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["validate_skill"] = module  # dataclass 需要模块已注册
    spec.loader.exec_module(module)
    return module


def append(path, text):
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(text)


def replace(path, old, new):
    text = Path(path).read_text(encoding="utf-8")
    assert old in text, (path, old)
    Path(path).write_text(text.replace(old, new, 1), encoding="utf-8")


class ValidateRealRepoTest(unittest.TestCase):
    def test_repo_skills_and_readme_pass(self):
        code, out, err = run_tool("--json")
        self.assertEqual(code, 0, out + err)
        data = json.loads(out)
        self.assertEqual(data["summary"]["FAIL"], 0)
        kinds = {r["kind"] for r in data["results"]}
        self.assertEqual(kinds, {"skill", "doc"})

    def test_bad_config_is_usage_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "cfg.json"
            cfg.write_text('{"skills": {"embedded-engineering": {"typo": 1}}}', encoding="utf-8")
            code, _out, err = run_tool("--config", cfg, SKILL)
            self.assertEqual(code, 2)
            self.assertIn("unknown keys", err)

    def test_missing_dir_is_usage_error(self):
        code, _out, _err = run_tool("/nonexistent/skill-dir")
        self.assertEqual(code, 2)


class MutationTest(unittest.TestCase):
    """每个用例：复制技能 → 注入一个缺陷 → 期望的检查 FAIL，其余检查保持原状。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.skill = self.tmp / "embedded-engineering"  # 目录名必须与 name 一致
        shutil.copytree(SKILL, self.skill, symlinks=True)
        self.baseline = self.statuses()

    def tearDown(self):
        self._tmp.cleanup()

    def statuses(self, skill=None, expect_exit=None):
        skill = skill or self.skill
        code, out, err = run_tool("--json", "--config", CONFIG, skill)
        self.assertIn(code, (0, 1), err)
        if expect_exit is not None:
            self.assertEqual(code, expect_exit, out)
        result = json.loads(out)["results"][0]
        self.last = result
        return {c["id"]: c["status"] for c in result["checks"]}

    def messages(self, check_id):
        for chk in self.last["checks"]:
            if chk["id"] == check_id:
                return [f["message"] for f in chk["findings"]]
        return []

    def assert_only_fails(self, *check_ids, skill=None):
        got = self.statuses(skill, expect_exit=1)
        for cid in check_ids:
            self.assertEqual(got[cid], "FAIL", f"{cid} should FAIL; findings: {self.messages(cid)}")
        for cid, status in got.items():
            if cid not in check_ids:
                self.assertEqual(status, self.baseline[cid], f"{cid} changed unexpectedly: {self.messages(cid)}")

    # -- 基线

    def test_copy_baseline_passes(self):
        for cid, status in self.baseline.items():
            # data-yaml 在没有 PyYAML 的环境里是 NOT_RUN，不算失败
            self.assertIn(status, ("PASS", "NOT_RUN") if cid == "data-yaml" else ("PASS",), cid)

    # -- frontmatter

    def test_uppercase_name(self):
        replace(self.skill / "SKILL.md", "name: embedded-engineering", "name: Embedded-Engineering")
        self.assert_only_fails("frontmatter")

    def test_name_must_match_directory(self):
        other = self.tmp / "renamed-skill"
        self.skill.rename(other)
        # 配置按目录名匹配，改名后 external_paths 不再生效，paths 也会 FAIL；这里只断言 name 检查
        got = self.statuses(other, expect_exit=1)
        self.assertEqual(got["frontmatter"], "FAIL")
        self.assertTrue(any("does not match directory" in m for m in self.messages("frontmatter")))

    def test_description_too_long(self):
        replace(self.skill / "SKILL.md", "description: >-\n", "description: >-\n  " + "x" * 1100 + "\n")
        self.assert_only_fails("frontmatter")
        self.assertTrue(any("1024" in m for m in self.messages("frontmatter")))

    def test_unknown_field_and_numeric_metadata(self):
        replace(self.skill / "SKILL.md", "name: embedded-engineering\n",
                "name: embedded-engineering\nversion: 2\nmetadata:\n  version: 1.0\n")
        self.assert_only_fails("frontmatter")
        msgs = " ".join(self.messages("frontmatter"))
        self.assertIn("unknown frontmatter field: version", msgs)
        self.assertIn("metadata.version", msgs)

    def test_missing_frontmatter(self):
        path = self.skill / "SKILL.md"
        text = path.read_text(encoding="utf-8")
        path.write_text(text.split("---", 2)[2], encoding="utf-8")
        got = self.statuses(expect_exit=1)
        self.assertEqual(got["frontmatter"], "FAIL")

    def test_skill_md_over_budget(self):
        append(self.skill / "SKILL.md", "\n" + "filler\n" * 200)
        self.assert_only_fails("frontmatter")

    # -- 引用

    def test_broken_link(self):
        append(self.skill / "references" / "profiles.md", "\n见 [不存在](missing.md)。\n")
        self.assert_only_fails("links")

    def test_link_escaping_skill(self):
        (self.tmp / "outside.md").write_text("# outside\n", encoding="utf-8")
        append(self.skill / "SKILL.md", "\n[外部](../outside.md)\n")
        self.assert_only_fails("links")
        self.assertTrue(any("escapes" in m for m in self.messages("links")))

    def test_missing_backtick_path(self):
        append(self.skill / "references" / "profiles.md", "\n运行 `scripts/nope.py <repo>`。\n")
        self.assert_only_fails("paths")

    def test_missing_section_same_file(self):
        append(self.skill / "references" / "profiles.md", "\n详见 §99。\n")
        self.assert_only_fails("sections")

    def test_missing_section_other_file(self):
        append(self.skill / "references" / "profiles.md", "\n见 [c/barr-c.md](c/barr-c.md) §42、§2。\n")
        self.assert_only_fails("sections")
        msgs = self.messages("sections")
        self.assertEqual(len(msgs), 1, msgs)  # §2 存在，只有 §42 报错
        self.assertIn("§42", msgs[0])

    def test_stale_bare_name_section_ref(self):
        # P0 遗漏过的写法：不带 .md 的旧文件名 + §N，被当作本文件章节而报错
        append(self.skill / "references" / "cpp" / "features.md", "\n见 cpp-coding §9。\n")
        self.assert_only_fails("sections")

    def test_unlinked_reference(self):
        (self.skill / "references" / "orphan.md").write_text("# orphan\n", encoding="utf-8")
        self.assert_only_fails("reachability")

    def test_orphan_script(self):
        extra = self.skill / "scripts" / "extra.py"
        extra.write_text("#!/usr/bin/env python3\nprint('x')\n", encoding="utf-8")
        extra.chmod(0o755)
        self.assert_only_fails("orphans")

    # -- 误报防护

    def test_fenced_code_is_ignored(self):
        append(self.skill / "references" / "profiles.md",
               "\n```sh\n# 1. 这是 shell 注释\n见 §99，运行 `scripts/nope.py`，[x](missing.md)\n```\n")
        got = self.statuses(expect_exit=0)
        self.assertEqual(got, self.baseline)

    def test_dot_slash_paths_are_external(self):
        append(self.skill / "references" / "profiles.md", "\n内核树中运行 `./scripts/checkpatch.pl --strict`。\n")
        self.assertEqual(self.statuses(expect_exit=0), self.baseline)

    # -- 脚本与数据

    def test_python_syntax_error(self):
        append(self.skill / "scripts" / "detect_profile.py", "\ndef broken(:\n")
        self.assert_only_fails("scripts")

    def test_shebang_not_executable(self):
        (self.skill / "scripts" / "arch_lint.py").chmod(0o644)
        self.assert_only_fails("scripts")

    def test_shell_syntax_error(self):
        append(self.skill / "scripts" / "bench" / "run.sh", "\nif then fi\n")
        self.assert_only_fails("scripts")

    def test_invalid_json(self):
        append(self.skill / "assets" / "arch_layers.json", "{")
        self.assert_only_fails("data-json")

    def test_invalid_yaml_asset(self):
        append(self.skill / "assets" / "ceedling" / "project.yml", "\n  bad: [unclosed\n")
        if self.baseline["data-yaml"] == "NOT_RUN":
            self.assertEqual(self.statuses()["data-yaml"], "NOT_RUN")
        else:
            self.assert_only_fails("data-yaml")

    def test_openai_yaml_bad_color_and_icon(self):
        append(self.skill / "agents" / "openai.yaml", '  brand_color: "blue"\n  icon_small: "./assets/none.svg"\n')
        self.assert_only_fails("openai-yaml")
        self.assertEqual(len(self.messages("openai-yaml")), 2)

    # -- 打包卫生

    def test_pycache_inside_skill(self):
        cache = self.skill / "scripts" / "__pycache__"
        cache.mkdir()
        (cache / "x.cpython-314.pyc").write_bytes(b"\0")
        self.assert_only_fails("hygiene")

    def test_symlink_outside_skill(self):
        (self.tmp / "secret.txt").write_text("x", encoding="utf-8")
        os.symlink(self.tmp / "secret.txt", self.skill / "assets" / "link.txt")
        got = self.statuses(expect_exit=1)
        self.assertEqual(got["hygiene"], "FAIL")


class RulesMutationTest(MutationTest):
    """standards/rules.yaml 与 profiles/ 的变异测试。"""

    def rules(self):
        return self.skill / "standards" / "rules.yaml"

    def test_duplicate_rule_id(self):
        replace(self.rules(), "  - id: ARCH-002\n", "  - id: ARCH-001\n")
        self.assert_only_fails("rules")
        self.assertTrue(any("duplicate id" in m for m in self.messages("rules")))

    def test_bad_rule_id_format(self):
        replace(self.rules(), "  - id: ARCH-002\n", "  - id: arch-2\n")
        self.assert_only_fails("rules")

    def test_unknown_profile_and_source(self):
        replace(self.rules(), "    profiles: [mcu-rtos]\n    lang: [c, cpp]\n    source: [rovinax]\n",
                "    profiles: [mcu-rtoss]\n    lang: [c, cpp]\n    source: [rovinaxx]\n")
        self.assert_only_fails("rules")
        msgs = " ".join(self.messages("rules"))
        self.assertIn("unknown profile 'mcu-rtoss'", msgs)
        self.assertIn("undeclared source 'rovinaxx'", msgs)

    def test_ref_to_missing_section(self):
        replace(self.rules(), "    ref: references/architecture/mcu-architecture.md §4\n",
                "    ref: references/architecture/mcu-architecture.md §42\n")
        self.assert_only_fails("rules")

    def test_ref_to_missing_file(self):
        replace(self.rules(), "    ref: references/platforms/linux-kernel.md §3\n",
                "    ref: references/platforms/linux-kernal.md §3\n")
        self.assert_only_fails("rules")

    def test_auto_without_tool(self):
        replace(self.rules(), "      method: auto\n      tool: arch_lint\n      check: cycle\n",
                "      method: auto\n")
        self.assert_only_fails("rules")

    def test_unknown_tool_check(self):
        replace(self.rules(), "      check: cycle\n", "      check: cycles\n")
        self.assert_only_fails("rules")

    def test_flag_not_in_flag_file(self):
        replace(self.rules(), '      check: "-Wfloat-equal"\n', '      check: "-Wfloat-equall"\n')
        self.assert_only_fails("rules")

    def test_asymmetric_conflict(self):
        replace(self.rules(), "    conflicts: [CFMT-006]\n", "")
        self.assert_only_fails("rules")
        self.assertTrue(any("not listed on LNXK-003" in m for m in self.messages("rules")))

    def test_bad_level_and_method(self):
        replace(self.rules(), "不复制实现的输出\"\n    level: mandatory\n", "不复制实现的输出\"\n    level: must\n")
        replace(self.rules(), "    ref: references/workflows/workflow.md §5\n    verify:\n      method: review\n",
                "    ref: references/workflows/workflow.md §5\n    verify:\n      method: eyeball\n")
        self.assert_only_fails("rules")
        msgs = " ".join(self.messages("rules"))
        self.assertIn("GEN-006: level", msgs)
        self.assertIn("verify.method", msgs)

    def test_duplicate_key_is_not_masked_by_pyyaml(self):
        # 回归：子集解析器报重复键后曾退回 PyYAML，而 PyYAML 默认后者覆盖，错误被吞掉
        replace(self.rules(), "  - id: GEN-006\n", "  - id: GEN-006\n    level: must\n")
        got = self.statuses(expect_exit=1)
        self.assertEqual(got["rules"], "FAIL")
        self.assertTrue(any("duplicate key" in m for m in self.messages("rules")))
        # rules.yaml 无法解析时 profiles 依赖它，应为 BLOCKED 而不是级联 FAIL
        self.assertEqual(got["profiles"], "BLOCKED")

    def test_duplicate_key_in_yaml_asset(self):
        append(self.skill / "assets" / "ceedling" / "project.yml", "\n:project:\n  :build_root: x\n")
        if self.baseline["data-yaml"] == "NOT_RUN":
            self.skipTest("PyYAML not installed")
        self.assert_only_fails("data-yaml")

    def test_missing_profile_file(self):
        (self.skill / "profiles" / "zephyr.yaml").unlink()
        got = self.statuses(expect_exit=1)
        self.assertEqual(got["profiles"], "FAIL")

    def test_extra_profile_file(self):
        text = (self.skill / "profiles" / "zephyr.yaml").read_text(encoding="utf-8")
        (self.skill / "profiles" / "nuttx.yaml").write_text(text.replace("id: zephyr", "id: nuttx"),
                                                            encoding="utf-8")
        got = self.statuses(expect_exit=1)
        self.assertEqual(got["profiles"], "FAIL")

    def test_profile_gate_unknown_tool(self):
        replace(self.skill / "profiles" / "zephyr.yaml", "  - tool: twister\n", "  - tool: twisterr\n")
        self.assert_only_fails("profiles")

    def test_profile_id_mismatch(self):
        replace(self.skill / "profiles" / "zephyr.yaml", "id: zephyr\n", "id: zephyr-app\n")
        self.assert_only_fails("profiles")

    def test_rules_file_missing_is_not_run_but_profiles_fail(self):
        self.rules().unlink()
        got = self.statuses(expect_exit=1)
        self.assertEqual(got["rules"], "NOT_RUN")
        self.assertEqual(got["profiles"], "FAIL")

class YamlSubsetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vs = load_tool_module()

    def test_folded_and_literal_blocks(self):
        data = self.vs.parse_yaml_subset("a: >-\n  one\n  two\n\n  three\nb: |\n  x\n  y\nc: plain # note\n")
        self.assertEqual(data, {"a": "one two\nthree", "b": "x\ny\n", "c": "plain"})

    def test_nested_map_list_and_scalars(self):
        text = ("interface:\n  display_name: \"Name\"\npolicy:\n  allow_implicit_invocation: false\n"
                "dependencies:\n  tools:\n    - type: \"mcp\"\n      url: https://x.test/mcp\n    - plain\n")
        data = self.vs.parse_yaml_subset(text)
        self.assertEqual(data["interface"], {"display_name": "Name"})
        self.assertIs(data["policy"]["allow_implicit_invocation"], False)
        self.assertEqual(data["dependencies"]["tools"], [{"type": "mcp", "url": "https://x.test/mcp"}, "plain"])

    def test_numbers_and_quotes(self):
        data = self.vs.parse_yaml_subset("v: 1.0\nq: \"1.0\"\ns: 'it''s'\n")
        self.assertEqual(data, {"v": 1.0, "q": "1.0", "s": "it's"})

    def test_rejects_unsupported(self):
        for bad in ("a: {x: 1}\n", "a: &anchor x\n", "a:\n\tb: 1\n", "a: 1\na: 2\n", "key:value\n"):
            with self.subTest(bad=bad), self.assertRaises(self.vs.YamlSubsetError):
                self.vs.parse_yaml_subset(bad)

    def test_flow_sequences(self):
        data = self.vs.parse_yaml_subset('a: [x, "y z", \'w\']\nb: []\nc: [1, true]  # note\n')
        self.assertEqual(data, {"a": ["x", "y z", "w"], "b": [], "c": [1, True]})
        for bad in ("a: [x, [y]]\n", "a: [x,, y]\n", "a: [x] tail\n", "a: [x\n"):
            with self.subTest(bad=bad), self.assertRaises(self.vs.YamlSubsetError):
                self.vs.parse_yaml_subset(bad)

    def test_rules_and_profiles_parse_without_pyyaml(self):
        # 子集解析器必须独立解析全部规则与 profile 文件（没有 PyYAML 的环境不得静默退化）
        for path in [SKILL / "standards" / "rules.yaml", *sorted((SKILL / "profiles").glob("*.yaml"))]:
            with self.subTest(path=path.name):
                self.assertIsInstance(self.vs.parse_yaml_subset(path.read_text(encoding="utf-8")), dict)

    def test_real_frontmatter(self):
        raw, _body, _end = self.vs.split_frontmatter((SKILL / "SKILL.md").read_text(encoding="utf-8"))
        meta = self.vs.parse_yaml_subset(raw)
        self.assertEqual(meta["name"], "embedded-engineering")
        self.assertIn("Use when", meta["description"])
        self.assertNotIn("\n", meta["description"].split("嵌入式")[0])


if __name__ == "__main__":
    unittest.main()
