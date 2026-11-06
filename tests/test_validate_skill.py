"""tools/validate_skill.py 回归测试（仅标准库）：python3 -m unittest discover -s tests -v

做法：把真实技能复制到临时目录，逐项注入一个缺陷，断言对应检查为 FAIL、其余检查不受影响；
另有误报防护用例（代码块、./ 前缀路径）和 YAML 子集解析器单元测试。
"""

import importlib.util
import json
import os
import re
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


def run_tool(*args, env=None, no_site=False):
    # no_site：用 -S 屏蔽 site-packages，确定性地模拟“没有 PyYAML”的环境
    flags = ["-I", "-S"] if no_site else ["-I"]
    proc = subprocess.run([sys.executable, *flags, str(TOOL), *map(str, args)],
                          capture_output=True, text=True, check=False, env=env)
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

    def statuses(self, skill=None, expect_exit=None, env=None, no_site=False):
        skill = skill or self.skill
        code, out, err = run_tool("--json", "--config", CONFIG, skill, env=env, no_site=no_site)
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

    # -- 计数声明

    def test_stale_profile_count(self):
        replace(self.skill / "SKILL.md", "六个 profile", "五个 profile")
        self.assert_only_fails("counts")
        self.assertIn("profiles count says 5, actual 6", self.messages("counts"))

    def test_stale_repo_doc_counts(self):
        repo = self.tmp / "repo"
        skill = repo / "skills" / "embedded-engineering"
        shutil.copytree(self.skill, skill, symlinks=True)
        proj = repo / "evals" / "projects" / "demo"
        proj.mkdir(parents=True)
        (proj / "eval.yaml").write_text("variants:\n  good: {}\n  bad-a: {}\n", encoding="utf-8")
        (repo / "README.md").write_text(
            "```text\nrules.yaml  # 1 条带 ID 的规则\n```\n\n1 个验证工程、3 个变体\n", encoding="utf-8")
        got = self.statuses(skill, expect_exit=1)
        self.assertEqual(got["counts"], "FAIL")
        msgs = self.messages("counts")
        self.assertTrue(any(m.startswith("rules count says 1,") for m in msgs), msgs)
        self.assertIn("variants count says 3, actual 2", msgs)
        self.assertFalse(any(m.startswith("projects") for m in msgs), msgs)

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
        # P0 遗漏过的写法：不带 .md 的旧文件名 + §N。features.md 自己就有 §3，
        # 旧实现会把它算到当前文件而漏报；现在必须报“归属不明”
        append(self.skill / "references" / "cpp" / "features.md", "\n见 cpp-coding §3。\n")
        self.assert_only_fails("sections")
        self.assertTrue(any("ambiguous" in m for m in self.messages("sections")))

    def test_section_ref_with_connector_word(self):
        # “[x](a.md) 的 §9”：中间的连接词不应让归属丢失（coding.md 有 §9，features.md 没有）
        append(self.skill / "references" / "cpp" / "features.md", "\n见 [cpp/coding.md](coding.md) 的 §9。\n")
        self.assertEqual(self.statuses(expect_exit=0), self.baseline)

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

    def test_whitelisted_external_path_passes(self):
        append(self.skill / "references" / "profiles.md", "\n内核树中运行 `./scripts/checkpatch.pl --strict`。\n")
        self.assertEqual(self.statuses(expect_exit=0), self.baseline)

    def test_dot_slash_skill_path_is_checked(self):
        # 回归：曾把所有 ./ 路径视为外部而放过技能自身的坏路径
        append(self.skill / "references" / "profiles.md", "\n运行 `./scripts/nope.py`。\n")
        self.assert_only_fails("paths")

    def test_parent_path_escaping_skill(self):
        append(self.skill / "references" / "profiles.md", "\n见 `../references/nope.md`。\n")
        self.assert_only_fails("paths")
        self.assertTrue(any("escapes" in m for m in self.messages("paths")))

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


class ReviewRegressionTest(MutationTest):
    """P0/P1 审查发现（2026-11-05，omp + GPT-6.1-Sol · Codex）的回归用例，编号对应审查报告。"""

    def entry(self):
        return self.skill / "SKILL.md"

    def set_frontmatter(self, body):
        text = self.entry().read_text(encoding="utf-8")
        rest = text.split("\n---\n", 1)[1]
        # 不能 rstrip：keep chomping 用例依赖结束符前的空行
        body = body if body.endswith("\n") else body + "\n"
        self.entry().write_text("---\n" + body + "---\n" + rest, encoding="utf-8")

    def test_01_indented_delimiter_does_not_end_frontmatter(self):
        self.set_frontmatter("name: embedded-engineering\ndescription: |-\n  Use when x\n  ---\n  " + "x" * 1024)
        self.assert_only_fails("frontmatter")
        self.assertTrue(any("1024" in m for m in self.messages("frontmatter")))

    def test_02_keep_chomping_counts_trailing_newlines(self):
        self.set_frontmatter("name: embedded-engineering\ndescription: |+\n  Use when " + "x" * 1014 + "\n\n\n")
        self.assert_only_fails("frontmatter")

    def test_02_folded_more_indented_keeps_newline(self):
        self.set_frontmatter("name: embedded-engineering\ndescription: >-\n  Use when " + "x" * 1012 + "\n    y")
        self.assert_only_fails("frontmatter")

    def test_03_colon_space_in_plain_scalar_is_invalid(self):
        self.set_frontmatter("name: embedded-engineering\ndescription: Use when: firmware")
        self.assert_only_fails("frontmatter")
        self.assertTrue(any("not valid YAML" in m for m in self.messages("frontmatter")))

    def test_03_integer_metadata_key_and_hex_value(self):
        self.set_frontmatter("name: embedded-engineering\ndescription: Use when testing\nmetadata:\n"
                             "  123: quoted\n  version: 0x10")
        self.assert_only_fails("frontmatter")
        self.assertEqual(len([m for m in self.messages("frontmatter") if "metadata." in m]), 2)

    def test_04_duplicate_name_in_frontmatter(self):
        self.set_frontmatter("name: embedded-engineering\nname: embedded-engineering\ndescription: Use when x")
        self.assert_only_fails("frontmatter")

    def test_04_root_flow_mapping_is_not_misparsed(self):
        self.set_frontmatter("{name: embedded-engineering, description: Use when testing}")
        got = self.statuses()
        # 以被测进程的能力为准（基线 data-yaml 为 NOT_RUN 即该进程没有 PyYAML），而不是测试进程
        if self.baseline["data-yaml"] == "NOT_RUN":
            self.assertEqual(got["frontmatter"], "NOT_RUN")
        else:
            self.assertEqual(got["frontmatter"], "PASS", self.messages("frontmatter"))

    def test_04_unsupported_yaml_without_pyyaml_is_not_run(self):
        self.set_frontmatter("{name: embedded-engineering, description: Use when testing}")
        code, _out, err = run_tool("--json", "--config", CONFIG, self.skill, no_site=True)
        self.assertEqual(code, 2)
        self.assertIn("error: PyYAML is required; run: uv run --with pyyaml python3 tools/validate_skill.py", err)

    def test_04_flow_mapping_metadata_without_pyyaml(self):
        self.set_frontmatter('name: embedded-engineering\ndescription: Use when testing\nmetadata: {author: "qa"}')
        code, _out, err = run_tool("--json", "--config", CONFIG, self.skill, no_site=True)
        self.assertEqual(code, 2)
        self.assertIn("error: PyYAML is required; run: uv run --with pyyaml python3 tools/validate_skill.py", err)

    def test_04_heterogeneous_keys_do_not_crash(self):
        self.set_frontmatter("name: embedded-engineering\ndescription: Use when testing\n0: zero\nother: value")
        self.assert_only_fails("frontmatter")
        msgs = " ".join(self.messages("frontmatter"))
        self.assertIn("must be a string", msgs)
        self.assertIn("unknown frontmatter field: other", msgs)

    def test_04_comment_before_nested_mapping(self):
        self.set_frontmatter('name: embedded-engineering\ndescription: Use when testing\n'
                             'metadata: # release metadata\n  version: "1"')
        self.assertEqual(self.statuses(expect_exit=0), self.baseline)

    def test_05_explicit_null_is_type_checked(self):
        self.set_frontmatter("name: embedded-engineering\ndescription: Use when testing\n"
                             "compatibility: null\nmetadata: null")
        self.assert_only_fails("frontmatter")
        self.assertEqual(len(self.messages("frontmatter")), 2)

    def test_06_missing_shell_is_not_run(self):
        env = dict(os.environ, PATH=str(self.tmp / "empty-path"))
        got = self.statuses(env=env, expect_exit=0)
        self.assertEqual(got["scripts"], "NOT_RUN")

    def test_09_reference_style_links(self):
        append(self.skill / "references" / "profiles.md", "\n见 [缺失][r]。\n\n[r]: missing.md\n")
        self.assert_only_fails("links")

    def test_09_undefined_reference_label(self):
        append(self.skill / "references" / "profiles.md", "\n见 [文字][no-such-label]。\n")
        self.assert_only_fails("links")

    def test_09_reference_style_link_counts_for_reachability(self):
        text = self.entry().read_text(encoding="utf-8")
        self.assertGreaterEqual(text.count("[profiles.md](references/profiles.md)"), 2)
        text = text.replace("[profiles.md](references/profiles.md)", "[profiles.md][profiles-route]")
        text += "\n[profiles-route]: references/profiles.md\n"
        self.entry().write_text(text, encoding="utf-8")
        self.assertNotIn("(references/profiles.md)", self.entry().read_text(encoding="utf-8"))
        self.assertEqual(self.statuses(expect_exit=0), self.baseline)
    def test_10_icon_outside_skill(self):
        (self.tmp / "outside.png").write_bytes(b"\x89PNG")
        append(self.skill / "agents" / "openai.yaml", '  icon_small: "../outside.png"\n')
        self.assert_only_fails("openai-yaml")
        self.assertTrue(any("outside" in m for m in self.messages("openai-yaml")))

    def test_11_dependency_field_types(self):
        append(self.skill / "agents" / "openai.yaml",
               "dependencies:\n  tools:\n    - type:\n        nested: true\n      value: 123\n")
        self.assert_only_fails("openai-yaml")
        self.assertEqual(len([m for m in self.messages("openai-yaml") if "must be a non-empty string" in m]), 2)

    def test_12_non_utf8_reference_does_not_crash(self):
        (self.skill / "references" / "profiles.md").write_bytes(b"# x\n\xff\xfe broken\n")
        got = self.statuses(expect_exit=1)  # statuses() 解析 JSON：崩溃会在这里失败
        self.assertEqual(got["hygiene"], "FAIL")

    def test_12_non_utf8_entry_does_not_crash(self):
        self.entry().write_bytes(b"---\nname: x\n---\n\xff\n")
        got = self.statuses(expect_exit=1)
        self.assertEqual(got["frontmatter"], "FAIL")

    # -- 第二轮审查发现（R2-1 至 R2-10、D1、D3）回归测试

    def test_r2_01_keep_chomping_boundary_and_blank_space_line(self):
        # 1025 字符（含分隔符前的换行）必须 FAIL；1024 字符必须 PASS
        self.set_frontmatter("name: embedded-engineering\ndescription: |+\n  Use when " + "x" * 1013 + "\n\n\n")
        self.assert_only_fails("frontmatter")
        self.assertTrue(any("1025" in m for m in self.messages("frontmatter")), self.messages("frontmatter"))

        self.set_frontmatter("name: embedded-engineering\ndescription: |+\n  Use when " + "x" * 1012 + "\n\n\n")
        self.assertEqual(self.statuses(expect_exit=0), self.baseline)

        # literal block 中间超出块缩进的纯空格行属于内容，不能被清空
        self.set_frontmatter("name: embedded-engineering\ndescription: |\n  Use when\n"
                             + " " * 100 + "\n  " + "x" * 920)
        self.assert_only_fails("frontmatter")
        self.assertTrue(any("1029" in m for m in self.messages("frontmatter")), self.messages("frontmatter"))

    def test_r2_02_ambiguous_scalars_rejected_in_flow_mapping(self):
        for snippet in ("metadata: {version: 0o17}", "metadata: {version: 1e3}", 'metadata: {yes: "1"}'):
            with self.subTest(snippet=snippet):
                self.set_frontmatter("name: embedded-engineering\ndescription: Use when testing\n" + snippet)
                self.assert_only_fails("frontmatter")
                self.assertTrue(any("quote it" in m for m in self.messages("frontmatter")),
                                self.messages("frontmatter"))

    def test_r2_03_colon_tab_and_nul_rejected(self):
        for bad in ("name: embedded-engineering\ndescription: Use when:\tfirmware",
                    "name: embedded-engineering\ndescription: Use when firmware\x00"):
            with self.subTest(bad=bad):
                self.set_frontmatter(bad)
                self.assert_only_fails("frontmatter")

    def test_r2_04_valid_yaml_constructs_and_merge_accepted(self):
        self.set_frontmatter('name: embedded-engineering\ndescription:\n  Use when\n  testing\n'
                             'metadata:\n  build#id: "1"\n  urn:tool: "qa"')
        self.assertEqual(self.statuses(expect_exit=0), self.baseline)

        self.set_frontmatter("name: embedded-engineering\ndescription: |-\n  Use when\n  \ttesting")
        self.assertEqual(self.statuses(expect_exit=0), self.baseline)

        self.set_frontmatter('name: embedded-engineering\ndescription: Use when testing\n'
                             'metadata:\n  <<: &base {a: "1", b: "2"}\n  b: "3"')
        self.assertEqual(self.statuses(expect_exit=0), self.baseline)

        replace(self.skill / "standards" / "rules.yaml",
                "    profiles: [mcu-baremetal, mcu-rtos]\n",
                "    profiles: [mcu-baremetal, mcu-rtos,]\n")
        self.assertEqual(self.statuses(expect_exit=0), self.baseline)
    def test_r2_05_huge_integer_does_not_crash_cli(self):
        self.set_frontmatter("name: embedded-engineering\ndescription: Use when testing\nmetadata:\n  n: "
                             + "9" * 5000)
        self.assert_only_fails("frontmatter")
        self.assertTrue(any("line 4" in m for m in self.messages("frontmatter")), self.messages("frontmatter"))

    def test_r2_06_unused_ref_def_not_reachable_and_ref_section_resolved(self):
        orig = self.entry().read_text(encoding="utf-8")
        # 删除所有指向 profiles.md 的 inline 链接，仅留未使用的引用定义 → reachability 必须 FAIL
        no_inline = orig.replace("[profiles.md](references/profiles.md)", "profiles.md")
        self.entry().write_text(no_inline + "\n[unused]: references/profiles.md\n", encoding="utf-8")
        self.assert_only_fails("reachability")

        # 恢复入口，在 features.md 中用引用式链接指向 coding.md §9（coding.md 有 §9，features.md 没有）
        self.entry().write_text(orig, encoding="utf-8")
        feat = self.skill / "references" / "cpp" / "features.md"
        feat_orig = feat.read_text(encoding="utf-8")
        feat.write_text(feat_orig + "\n见 [coding][c] §9、[c][] 的 §9 与 [c] §9。\n\n[c]: coding.md\n",
                        encoding="utf-8")
        self.assertEqual(self.statuses(expect_exit=0), self.baseline)

        # 指向 coding.md 不存在的 §99 必须报在 coding.md 上
        feat.write_text(feat_orig + "\n见 [coding][c] §99。\n\n[c]: coding.md\n", encoding="utf-8")
        self.assert_only_fails("sections")
        self.assertTrue(any("§99 not found in coding.md" in m for m in self.messages("sections")),
                        self.messages("sections"))

    def test_r2_07_normalized_paths_and_boundary(self):
        prof = self.skill / "references" / "profiles.md"
        orig = prof.read_text(encoding="utf-8")
        prof.write_text(orig + "\n运行 `././scripts/nope.py`。\n", encoding="utf-8")
        self.assert_only_fails("paths")
        self.assertTrue(any("path not found: ././scripts/nope.py" in m for m in self.messages("paths")),
                        self.messages("paths"))

        (self.tmp / "README.md").write_text("# outside\n", encoding="utf-8")
        prof.write_text(orig + "\n见 `scripts/../../../README.md`。\n", encoding="utf-8")
        self.assert_only_fails("paths")
        self.assertTrue(any("escapes skill directory: scripts/../../../README.md" in m
                            for m in self.messages("paths")),
                        self.messages("paths"))

    def test_r2_08_unreadable_doc_blocks_and_empty_rules_fails(self):
        bad_doc = self.tmp / "README.md"
        bad_doc.write_bytes(b"\xff\xfe invalid utf-8\n")
        code, out, err = run_tool("--json", "--config", CONFIG, self.skill, "--doc", bad_doc)
        self.assertEqual(code, 1, err)
        doc_res = [r for r in json.loads(out)["results"] if r["kind"] == "doc"][0]
        doc_statuses = {c["id"]: c["status"] for c in doc_res["checks"]}
        self.assertEqual(doc_statuses, {"links": "FAIL", "paths": "BLOCKED", "sections": "BLOCKED"})

        (self.skill / "standards" / "rules.yaml").write_text("", encoding="utf-8")
        got = self.statuses(expect_exit=1)
        self.assertEqual(got["rules"], "FAIL")
        self.assertEqual(got["profiles"], "BLOCKED")

    def test_r2_09_wrong_field_types_and_internal_error_guard(self):
        rules_path = self.skill / "standards" / "rules.yaml"
        orig_rules = rules_path.read_text(encoding="utf-8")
        mutated = orig_rules.replace("level: mandatory", "level: []", 1)
        mutated = mutated.replace("method: review", "method: []", 1)
        mutated = mutated.replace("tool: arch_lint", "tool: []", 1)
        mutated = mutated.replace("conflicts: [ZEP-001, LNXK-001]", "conflicts: 1", 1)
        rules_path.write_text(mutated, encoding="utf-8")
        got = self.statuses(expect_exit=1)
        self.assertEqual(got["rules"], "FAIL")

        rules_path.write_text(orig_rules, encoding="utf-8")
        replace(self.skill / "profiles" / "zephyr.yaml", "  - tool: twister\n", "  - tool: []\n")
        self.assert_only_fails("profiles")

        vs = load_tool_module()
        orig_check_json = vs.check_json
        try:
            def boom(_skill, _check):
                raise RuntimeError("synthetic failure")
            vs.check_json = boom
            res = vs.validate_skill(self.skill, {})
        finally:
            vs.check_json = orig_check_json
        by_id = {c["id"]: c for c in res["checks"]}
        self.assertEqual(by_id["data-json"]["status"], "FAIL")
        self.assertTrue(any("internal error: RuntimeError: synthetic failure" in f["message"]
                            for f in by_id["data-json"]["findings"]))
        self.assertEqual(by_id["frontmatter"]["status"], "PASS")
        self.assertEqual(by_id["rules"]["status"], "PASS")

    def test_r2_10_non_empty_strings_inside_refs_and_d3_check_capability(self):
        rules_path = self.skill / "standards" / "rules.yaml"
        orig_rules = rules_path.read_text(encoding="utf-8")
        mutated = orig_rules.replace('external: "west twister -T <dir>"', "external: null", 1)
        mutated = mutated.replace("path: scripts/barrc/check.sh", 'path: ""', 1)
        mutated = mutated.replace("      method: auto\n      tool: barrc_check\n",
                                  "      method: auto\n      tool: barrc_check\n      check: not_a_real_check\n", 1)
        rules_path.write_text(mutated, encoding="utf-8")
        got = self.statuses(expect_exit=1)
        self.assertEqual(got["rules"], "FAIL")
        msgs = " ".join(self.messages("rules"))
        self.assertIn("verify_tools.twister.external", msgs)
        self.assertIn("verify_tools.barrc_check.path", msgs)
        self.assertIn("barrc_check", msgs)
        self.assertIn("check", msgs)

        rules_path.write_text(orig_rules, encoding="utf-8")
        (self.tmp / "outside.md").write_text("# outside\n", encoding="utf-8")
        zep = self.skill / "profiles" / "zephyr.yaml"
        ztext = zep.read_text(encoding="utf-8")
        ztext = ztext.replace('summary: "Zephyr RTOS 应用、驱动与模块"', "summary: null")
        ztext = ztext.replace("  - references/platforms/zephyr.md\n",
                              "  - references/platforms/zephyr.md\n  - ../outside.md\n")
        ztext = ztext.replace('    run: "west twister -T <tests/dir>"', "    run: null")
        zep.write_text(ztext, encoding="utf-8")
        self.assert_only_fails("profiles")
        pmsgs = " ".join(self.messages("profiles"))
        self.assertIn("summary", pmsgs)
        self.assertIn("outside", pmsgs)
        self.assertIn("gates", pmsgs)

    def test_r2_12_13_14_d2_auto_coverage_and_gap_validation(self):
        vs = load_tool_module()
        rules_path = self.skill / "standards" / "rules.yaml"
        orig_text = rules_path.read_text(encoding="utf-8")
        data = vs.load_yaml(orig_text)
        by_id = {r["id"]: r for r in data["rules"]}
        must_be_partial = {
            "C-006", "C-009", "C-011", "C-015", "CFMT-003", "CFMT-005",
            "CPP-003", "CPP-004", "CPP-005", "CPP-006", "CPP-007", "CPP-008", "CPP-009",
        }
        for rid, rule in by_id.items():
            verify = rule["verify"]
            if verify["method"] == "auto":
                self.assertIn(verify.get("coverage"), ("full", "partial"), f"{rid} missing coverage")
                if verify.get("coverage") == "partial":
                    self.assertTrue(isinstance(verify.get("gap"), str) and verify["gap"].strip(),
                                    f"{rid} partial missing gap")
            else:
                self.assertNotIn("coverage", verify, f"{rid} non-auto has coverage")
        for rid in must_be_partial:
            self.assertEqual(by_id[rid]["verify"].get("coverage"), "partial", f"{rid} must be partial")

        # auto 缺少 coverage 报错
        rules_path.write_text(orig_text.replace("      coverage: full\n", "", 1), encoding="utf-8")
        self.assert_only_fails("rules")
        self.assertTrue(any("coverage" in m for m in self.messages("rules")), self.messages("rules"))

        # partial 缺少 gap 报错
        no_gap = re.sub(r"      coverage: partial\n      gap: [^\n]+\n", "      coverage: partial\n",
                        orig_text, count=1)
        rules_path.write_text(no_gap, encoding="utf-8")
        self.assert_only_fails("rules")
        self.assertTrue(any("gap" in m for m in self.messages("rules")), self.messages("rules"))

        # 非 auto 写了 coverage 报错
        rules_path.write_text(orig_text.replace("      method: review\n",
                                                "      method: review\n      coverage: full\n", 1),
                              encoding="utf-8")
        self.assert_only_fails("rules")
        self.assertTrue(any("coverage" in m for m in self.messages("rules")), self.messages("rules"))


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

    def test_cited_unknown_rule_id(self):
        append(self.skill / "references" / "profiles.md", "\n违反 `ISR-099` 时……\n")
        self.assert_only_fails("rules")
        self.assertTrue(any("ISR-099" in m for m in self.messages("rules")))

    def test_rules_file_missing_is_not_run_but_profiles_fail(self):
        self.rules().unlink()
        got = self.statuses(expect_exit=1)
        self.assertEqual(got["rules"], "NOT_RUN")
        self.assertEqual(got["profiles"], "FAIL")


class YamlLoaderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vs = load_tool_module()

    def test_folded_and_literal_blocks(self):
        data = self.vs.load_yaml("a: >-\n  one\n  two\n\n  three\nb: |\n  x\n  y\nc: plain # note\n")
        self.assertEqual(data, {"a": "one two\nthree", "b": "x\ny\n", "c": "plain"})

    def test_nested_map_list_and_scalars(self):
        text = ("interface:\n  display_name: \"Name\"\npolicy:\n  allow_implicit_invocation: false\n"
                "dependencies:\n  tools:\n    - type: \"mcp\"\n      url: https://x.test/mcp\n    - plain\n")
        data = self.vs.load_yaml(text)
        self.assertEqual(data["interface"], {"display_name": "Name"})
        self.assertIs(data["policy"]["allow_implicit_invocation"], False)
        self.assertEqual(data["dependencies"]["tools"], [{"type": "mcp", "url": "https://x.test/mcp"}, "plain"])

    def test_numbers_and_quotes(self):
        data = self.vs.load_yaml("v: 1.0\nq: \"1.0\"\ns: 'it''s'\n")
        self.assertEqual(data, {"v": 1.0, "q": "1.0", "s": "it's"})

    BLOCK_CASES = [
        ("a: |+\n  x\n\n\n", "x\n\n\n"), ("a: |-\n  x\n\n", "x"), ("a: |\n  x\n\n", "x\n"),
        ("a: >-\n  aa\n    y\n", "aa\n  y"), ("a: >\n  a\n  b\n\n  c\n", "a b\nc\n"),
        ("a: >\n  a\n\n\n  b\n", "a\n\nb\n"), ("a: >\n  a\n    more\n  b\n", "a\n  more\nb\n"),
        ("a: >-\n\n  a\n", "\na"), ("a: |\n  a\n   b\n", "a\n b\n"), ("a: >+\n  a\n  b\n\n", "a b\n\n"),
        ("a: >\n  a\n    m1\n    m2\n  b\n", "a\n  m1\n  m2\nb\n"), ("a: |-\n", ""),
        ("a: >\n  a\n\n    m\n\n  b\n", "a\n\n  m\n\nb\n"),
    ]

    def test_block_scalars_match_yaml_spec(self):
        for text, expected in self.BLOCK_CASES:
            with self.subTest(text=text):
                self.assertEqual(self.vs.load_yaml(text)["a"], expected)

    def test_core_schema_scalars(self):
        data = self.vs.load_yaml("h: 0x10\ni: .inf\nn: ~\nb: TRUE\ns: plain text\n")
        self.assertEqual(data["h"], 16)
        self.assertEqual(data["i"], float("inf"))
        self.assertIsNone(data["n"])
        self.assertIs(data["b"], True)
        self.assertEqual(data["s"], "plain text")

    def test_ambiguous_and_invalid_scalars_are_errors(self):
        for bad in ("a: yes\n", "a: off\n", "a: 012\n", "a: 0o17\n", "a: 2026-11-05\n", "a: 1e3\n",
                    "a: x: y\n", "a: `x`\n", "a: 1:20\n", "{a: 0o17}\n", "{yes: 1}\n",
                    "a: Use when:\tfirmware\n", "a: Use when\x00\n", "a: " + "9" * 5000 + "\n"):
            with self.subTest(bad=bad[:40]), self.assertRaises(self.vs.YamlSyntaxError):
                self.vs.load_yaml(bad)

    def test_merge_and_duplicate_keys(self):
        merged = self.vs.load_yaml("base: &b\n  a: 1\n  b: 2\nchild:\n  <<: *b\n  b: 3\n")
        self.assertEqual(merged["child"], {"a": 1, "b": 3})
        for bad in ("name: a\nname: b\n", "base: &b {a: 1}\nchild: {<<: *b, x: 1, x: 2}\n",
                    "a:\n\tb: 1\n", "*undef: v\n"):
            with self.subTest(bad=bad), self.assertRaises(self.vs.YamlSyntaxError):
                self.vs.load_yaml(bad)

    def test_flow_sequences(self):
        data = self.vs.load_yaml('a: [x, "y z", \'w\',]\nb: []\nc: [1, true]  # note\n')
        self.assertEqual(data, {"a": ["x", "y z", "w"], "b": [], "c": [1, True]})
        for bad in ("a: [x,, y]\n", "a: [x] tail\n", "a: [x\n"):
            with self.subTest(bad=bad), self.assertRaises(self.vs.YamlSyntaxError):
                self.vs.load_yaml(bad)

    def test_rules_and_profiles_parse(self):
        for path in [SKILL / "standards" / "rules.yaml", *sorted((SKILL / "profiles").glob("*.yaml"))]:
            with self.subTest(path=path.name):
                self.assertIsInstance(self.vs.load_yaml(path.read_text(encoding="utf-8")), dict)

    def test_real_frontmatter(self):
        raw, _body, _end = self.vs.split_frontmatter((SKILL / "SKILL.md").read_text(encoding="utf-8"))
        meta = self.vs.load_yaml(raw)
        self.assertEqual(meta["name"], "embedded-engineering")
        self.assertIn("Use when", meta["description"])
        self.assertNotIn("\n", meta["description"].split("嵌入式")[0])

if __name__ == "__main__":
    unittest.main()
