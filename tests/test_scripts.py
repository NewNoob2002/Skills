"""embedded-engineering 脚本回归测试（仅标准库）：python3 -m unittest discover -s tests -v"""

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent / "skills" / "embedded-engineering"
ARCH_LINT = SKILL / "scripts" / "arch_lint.py"
DETECT = SKILL / "scripts" / "detect_profile.py"
TEMPLATES = SKILL / "assets" / "templates"


def write(root, rel, text=""):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run(script, *args):
    proc = subprocess.run([sys.executable, "-I", str(script), *map(str, args)],
                          capture_output=True, text=True, check=False)
    return proc.returncode, proc.stdout, proc.stderr


class ArchLintTest(unittest.TestCase):
    def make_clean_repo(self, root):
        for sub in ("interface", "module"):
            for f in (TEMPLATES / sub).iterdir():
                write(root, f"{sub}/{f.name}", f.read_text(encoding="utf-8"))
        write(root, "bsp/board_led.c", '#include "gpio_if.h"\n#include "stm32g4xx_hal.h"\n'
                                       "static void x(void) { HAL_GPIO_WritePin(GPIOA, 1, 1); }\n")
        write(root, "platform/stm32g4/hal/stm32g4xx_hal.h", "/* vendor */\n")
        write(root, "app/main.c", '#include "ledctl.h"\n#include "board_led.h"\n#include "FreeRTOS.h"\n')
        write(root, "bsp/board_led.h", '#include "gpio_if.h"\n')

    def test_templates_layout_is_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.make_clean_repo(tmp)
            code, out, err = run(ARCH_LINT, tmp)
            self.assertEqual(code, 0, out + err)
            self.assertIn("0 violation(s)", out)

    def test_detects_violations(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.make_clean_repo(tmp)
            write(tmp, "module/motor/motor.c",
                  '#include "stm32g4xx_hal.h"\n#include "task.h"\n#include "board_led.h"\n'
                  '#include "imu.h"\n'
                  "/* GPIOA->ODR in a comment is ignored */\n"
                  'static const char * s = "TIM1->CNT";\n'
                  "void motor_run(void) { TIM1->CCR1 = 5U; HAL_Delay(1); }\n")
            write(tmp, "module/motor/motor.h", "")
            write(tmp, "module/imu/imu.h", '#include "motor.h"\n')
            write(tmp, "interface/bad_if.h", '#include "ledctl.h"\n')
            code, out, _ = run(ARCH_LINT, tmp, "--json")
            self.assertEqual(code, 1)
            report = json.loads(out)
            kinds = [(v["file"], v["kind"]) for v in report["violations"]]
            self.assertIn(("module/motor/motor.c", "layer_dependency"), kinds)   # module -> platform/bsp
            self.assertIn(("module/motor/motor.c", "forbidden_include"), kinds)  # task.h (external RTOS)
            self.assertIn(("module/motor/motor.c", "register_access"), kinds)
            self.assertIn(("module/motor/motor.c", "hal_call"), kinds)
            self.assertIn(("interface/bad_if.h", "layer_dependency"), kinds)
            self.assertTrue(any(k == "cycle" for _, k in kinds), kinds)
            reg_lines = [v["line"] for v in report["violations"] if v["kind"] == "register_access"]
            self.assertEqual(reg_lines, [7], "comments and strings must not be flagged")

    def test_cpp_templates_follow_layering(self):
        code, out, err = run(ARCH_LINT, SKILL / "assets" / "cpp" / "templates")
        self.assertEqual(code, 0, out + err)

    def test_cpp_files_are_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "interface/register_bus.hpp", "#pragma once\n")
            write(tmp, "module/motor/motor.hpp", '#include "register_bus.hpp"\n')
            write(tmp, "module/motor/motor.cpp",
                  '#include "motor.hpp"\n#include "stm32g4xx_hal.h"\n#include "cmsis_os2.h"\n'
                  "void proj::Motor::run() { HAL_GPIO_TogglePin(GPIOA, 1); TIM1->CCR1 = 5U; }\n")
            write(tmp, "platform/stm32g4/stm32g4xx_hal.h", "")
            code, out, _ = run(ARCH_LINT, tmp, "--json")
            self.assertEqual(code, 1)
            kinds = {(v["file"], v["kind"]) for v in json.loads(out)["violations"]}
            self.assertIn(("module/motor/motor.cpp", "layer_dependency"), kinds)
            self.assertIn(("module/motor/motor.cpp", "forbidden_include"), kinds)
            self.assertIn(("module/motor/motor.cpp", "hal_call"), kinds)
            self.assertIn(("module/motor/motor.cpp", "register_access"), kinds)

    def test_unmapped_repo_is_not_a_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "src/main.c", "int main(void) { return 0; }\n")
            code, _, err = run(ARCH_LINT, tmp)
            self.assertEqual(code, 2)
            self.assertIn("no file matched", err)

    def test_bad_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "bad.json"
            cfg.write_text('{"layers": [{"name": "a", "globs": ["a/**"], "allow": ["b"]}]}')
            code, _, err = run(ARCH_LINT, tmp, "--config", cfg)
            self.assertEqual(code, 2)
            self.assertIn("unknown layers", err)


class DetectProfileTest(unittest.TestCase):
    def detect(self, root):
        code, out, err = run(DETECT, root)
        self.assertEqual(code, 0, err)
        return json.loads(out)

    def test_zephyr(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "app/CMakeLists.txt", "find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})\n")
            write(tmp, "app/prj.conf", "CONFIG_GPIO=y\n")
            write(tmp, "app/boards/nrf52840dk_nrf52840.overlay", "/ {};\n")
            write(tmp, "west.yml", "manifest: {}\n")
            self.assertEqual(self.detect(tmp)["suggested"], "zephyr")

    def test_freertos_beats_baremetal(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "platform/stm32g4/startup/startup_stm32g474xx.s")
            write(tmp, "platform/stm32g4/linker/STM32G474RETX_FLASH.ld")
            write(tmp, "middleware/freertos/FreeRTOSConfig.h")
            write(tmp, "project.yml", ":project:\n  :build_root: build\n")
            report = self.detect(tmp)
            self.assertEqual(report["suggested"], "mcu-rtos")
            self.assertEqual(report["test_baseline_present"]["ceedling"], ["project.yml"])

    def test_linux_kernel_driver(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "drivers/iio/foo.c", 'MODULE_LICENSE("GPL");\n')
            write(tmp, "drivers/iio/Makefile", "obj-$(CONFIG_FOO) += foo.o\n")
            write(tmp, "Kbuild", "obj-y += drivers/\n")
            self.assertEqual(self.detect(tmp)["suggested"], "linux-kernel")

    def test_cpp_languages_and_tier_from_linker_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "middleware/freertos/FreeRTOSConfig.h")
            write(tmp, "linker/app.ld", "MEMORY\n{\n  FLASH (rx) : ORIGIN = 0x08000000, LENGTH = 2M\n"
                                        "  RAM (xrw) : ORIGIN = 0x20000000, LENGTH = 0x00080000\n}\n")
            write(tmp, "module/motor.cpp")
            write(tmp, "module/motor.hpp")
            write(tmp, "third_party/etl/include/etl/platform.h")
            write(tmp, "CMakeLists.txt", "set(CMAKE_CXX_STANDARD 20)\n")
            write(tmp, "tests/test_motor.cpp", '#include "CppUTest/TestHarness.h"\n')
            report = self.detect(tmp)
            self.assertEqual(report["languages"]["cpp_standard"], ["20"])
            self.assertEqual(report["languages"]["cpp_libraries"], ["etl"])
            self.assertEqual(report["languages"]["cpp_sources_and_headers"], 3)
            self.assertEqual(report["resource_tier"]["suggested"], "T2")
            self.assertEqual(report["test_baseline_present"]["cpputest"], ["tests/test_motor.cpp"])

    def test_small_mcu_is_t0(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "startup_stm32c011xx.s")
            write(tmp, "STM32C011F6PX_FLASH.ld", "MEMORY\n{\n  RAM (xrw) : ORIGIN = 0x20000000, LENGTH = 6K\n"
                                                "  FLASH (rx) : ORIGIN = 0x08000000, LENGTH = 32K\n}\n")
            report = self.detect(tmp)
            self.assertEqual(report["suggested"], "mcu-baremetal")
            self.assertEqual(report["resource_tier"]["suggested"], "T0")

    def test_kernel_has_no_cpp_tier(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "Kbuild", "obj-y += foo.o\n")
            self.assertIsNone(self.detect(tmp)["resource_tier"]["suggested"])

    def test_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(self.detect(tmp)["suggested"])


def _load_module(name, path):
    import importlib.util
    sys.dont_write_bytecode = True  # 不在技能目录写 __pycache__
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class RulesConsistencyTest(unittest.TestCase):
    """standards/rules.yaml 中声明的 profile 与工具检查项必须与脚本实际实现一致。"""

    @classmethod
    def setUpClass(cls):
        vs = _load_module("validate_skill", SKILL.parent.parent / "tools" / "validate_skill.py")
        cls.rules = vs.parse_yaml_subset((SKILL / "standards" / "rules.yaml").read_text(encoding="utf-8"))

    def test_profiles_match_detect_profile(self):
        detect = _load_module("detect_profile", DETECT)
        detected = {rule[0] for rule in detect.NAME_RULES}
        self.assertEqual(set(self.rules["profiles"]), detected)
        self.assertEqual({p.stem for p in (SKILL / "profiles").glob("*.yaml")}, detected)

    def test_arch_lint_checks_match_implementation(self):
        source = ARCH_LINT.read_text(encoding="utf-8")
        kinds = set(re.findall(r'"kind": "([a-z_]+)"', source)) - {"io_error"}
        config = json.loads((SKILL / "assets" / "arch_layers.json").read_text(encoding="utf-8"))
        kinds |= set(config["code_patterns"])
        self.assertEqual(set(self.rules["verify_tools"]["arch_lint"]["checks"]), kinds)

    def test_cpp_cost_checks_match_implementation(self):
        cost = _load_module("cpp_cost", SKILL / "scripts" / "cpp_cost.py")
        declared = set(self.rules["verify_tools"]["cpp_cost"]["checks"])
        # budget/diff 是 check 的 --budget 与 diff 子命令，其余是符号类别
        self.assertEqual(declared - {"budget", "diff"}, set(cost.SYMBOL_CLASSES))

class WorkflowPagesTest(unittest.TestCase):
    """references/workflows/ 下每个工作流页面都有固定结构，并在 workflow.md §7 目录中登记。"""

    SECTIONS = ("## 概要", "## 步骤", "## 检查点", "## 通过与失败")
    ROWS = ("| 触发 |", "| 输入 |", "| 前置条件 |", "| 角色 |", "| 产物 |", "| 人工审批 |")

    def pages(self):
        return sorted(p for p in (SKILL / "references" / "workflows").glob("*.md") if p.name != "workflow.md")

    def test_ten_workflows(self):
        self.assertEqual(len(self.pages()), 10)

    def test_fixed_structure(self):
        for page in self.pages():
            text = page.read_text(encoding="utf-8")
            with self.subTest(page=page.name):
                for heading in self.SECTIONS:
                    self.assertIn("\n" + heading + "\n", text)
                for row in self.ROWS:
                    self.assertIn(row, text)
                self.assertRegex(text, r"\*\*(?:PASS|ACCEPT)")
                self.assertRegex(text, r"\*\*(?:FAIL|REJECT)")

    def test_catalog_lists_every_page(self):
        catalog = (SKILL / "references" / "workflows" / "workflow.md").read_text(encoding="utf-8")
        for page in self.pages():
            with self.subTest(page=page.name):
                self.assertIn(f"]({page.name})", catalog)

if __name__ == "__main__":
    unittest.main()
