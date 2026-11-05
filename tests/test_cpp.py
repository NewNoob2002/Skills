"""C++ 模块回归测试：python3 -m unittest discover -s tests -v

- CppCostParseTest：cpp_cost.py 的解析与等级策略，不需要工具链。
- CppCostElfTest：用 arm-none-eabi-g++ 现场构建小 ELF，验证各类受限符号的检出（无工具链则跳过）。
- CppTemplateTest：tests/cpp/run_cpp_checks.sh（需要 arm-none-eabi-g++ 与环境变量 ETL_INCLUDE）。
- CppUTestTemplateTest：构建并运行 CppUTest 测试模板（需要 ETL_INCLUDE 与 CPPUTEST_PREFIX，以及 cmake）。
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
SKILL = ROOT / "skills" / "embedded-engineering"
COST = SKILL / "scripts" / "cpp_cost.py"
BENCH_SRC = SKILL / "scripts" / "bench" / "src"
CXX = shutil.which("arm-none-eabi-g++")


def load_cost_module():
    # 不在技能目录中写 __pycache__：install.sh 会原样复制技能目录到用户项目。
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("cpp_cost", COST)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CppCostParseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_cost_module()

    def test_parse_nm_defined_keeps_demangled_names_with_spaces(self):
        text = ("08000100 T main\n08000200 T operator new(unsigned int)\n"
                "         U _sbrk\n08000300 R typeinfo for Base\n")
        names = self.mod.parse_nm_defined(text)
        self.assertIn("operator new(unsigned int)", names)
        self.assertIn("typeinfo for Base", names)
        self.assertNotIn("_sbrk", names)  # 未定义符号不计入

    def test_parse_size(self):
        sizes = self.mod.parse_berkeley_size("   text\t   data\t    bss\t    dec\t    hex\tfilename\n"
                                             "    448\t      8\t     40\t    496\t    1f0\ta.elf\n")
        self.assertEqual(sizes, {"text": 448, "data": 8, "bss": 40, "flash": 456, "ram": 48})

    def test_tier_policy_and_allow(self):
        hits = self.mod.classify({"malloc", "__cxa_guard_acquire", "__gxx_personality_v0", "main"})
        t1 = {f["class"]: f["level"] for f in self.mod.evaluate(hits, "T1", set())}
        self.assertEqual(t1, {"heap": "warn", "local_static_guard": "warn", "exceptions": "fail"})
        t0 = {f["class"]: f["level"] for f in self.mod.evaluate(hits, "T0", {"heap"})}
        self.assertEqual(t0["heap"], "info")
        self.assertEqual(t0["exceptions"], "fail")
        t3 = {f["level"] for f in self.mod.evaluate(hits, "T3", set())}
        self.assertEqual(t3, {"info"})

    def test_budget(self):
        over = self.mod.check_budget({"text": 10, "data": 2, "bss": 5, "flash": 12, "ram": 7},
                                     {"flash_max": 11, "ram_max": 100})
        self.assertEqual(over, [{"metric": "flash", "actual": 12, "max": 11}])

    def test_missing_file_is_tool_error(self):
        proc = subprocess.run([sys.executable, "-I", str(COST), "check", "/nonexistent.elf", "--tier", "T1"],
                              capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("file not found", proc.stderr)


@unittest.skipUnless(CXX, "arm-none-eabi-g++ not installed")
class CppCostElfTest(unittest.TestCase):
    ARCH = ["-mcpu=cortex-m4", "-mthumb", "-mfloat-abi=soft"]

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        out = Path(cls.tmp.name)
        cc = CXX[:-3] + "gcc"
        subprocess.run([cc, *cls.ARCH, "-Os", f"-I{BENCH_SRC}", "-c", str(BENCH_SRC / "common.c"),
                        "-o", str(out / "common.o")], check=True)
        cls.elf = {}
        for name, src, extra in [("base", "a1_baseline.cpp", []),
                                 ("exceptions", "f01_exceptions.cpp", ["-fexceptions"]),
                                 ("guard", "f08_local_static.cpp", []),
                                 ("vector", "f06_std_vector.cpp", [])]:
            flags = [*cls.ARCH, "-Os", "-std=c++20", "-ffunction-sections", "-fdata-sections",
                     "-fno-rtti", f"-I{BENCH_SRC}", *(extra or ["-fno-exceptions"])]
            obj, elf = out / f"{name}.o", out / f"{name}.elf"
            subprocess.run([CXX, *flags, "-c", str(BENCH_SRC / src), "-o", str(obj)], check=True)
            subprocess.run([CXX, *cls.ARCH, "-Wl,--gc-sections", "--specs=nano.specs", "--specs=nosys.specs",
                            *extra, str(obj), str(out / "common.o"), "-o", str(elf)],
                           check=True, capture_output=True)
            cls.elf[name] = str(elf)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def check(self, name, tier, *extra):
        proc = subprocess.run([sys.executable, "-I", str(COST), "--json", "check", self.elf[name],
                               "--tier", tier, *extra], capture_output=True, text=True, check=False)
        return proc.returncode, json.loads(proc.stdout)

    def test_baseline_passes_t0(self):
        code, report = self.check("base", "T0")
        self.assertEqual(code, 0, report)
        self.assertEqual(report["findings"], [])

    def test_exceptions_fail_t1(self):
        code, report = self.check("exceptions", "T1")
        self.assertEqual(code, 1)
        self.assertIn("exceptions", {f["class"] for f in report["findings"]})

    def test_local_static_guard_warns_t1_fails_t0(self):
        self.assertEqual(self.check("guard", "T1")[0], 0)
        self.assertEqual(self.check("guard", "T0")[0], 1)

    def test_std_vector_pulls_heap_and_throw_helpers(self):
        code, report = self.check("vector", "T1")
        classes = {f["class"] for f in report["findings"]}
        self.assertEqual(code, 1)
        self.assertTrue({"heap", "throw_helpers"} <= classes, classes)
        # 已评审允许后，heap 降为 info；throw_helpers 仍失败
        code, _ = self.check("vector", "T1", "--allow", "heap")
        self.assertEqual(code, 1)

    def test_diff_reports_growth(self):
        proc = subprocess.run([sys.executable, "-I", str(COST), "--json", "diff", self.elf["base"],
                               self.elf["vector"]], capture_output=True, text=True, check=True)
        report = json.loads(proc.stdout)
        self.assertGreater(report["sections"]["text"]["delta"], 500)
        self.assertTrue(any(d["state"] == "added" for d in report["symbols"]))


@unittest.skipUnless(CXX and os.environ.get("ETL_INCLUDE"), "needs arm-none-eabi-g++ and ETL_INCLUDE")
class CppTemplateTest(unittest.TestCase):
    def test_run_cpp_checks(self):
        proc = subprocess.run(["bash", str(ROOT / "tests" / "cpp" / "run_cpp_checks.sh")],
                              capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stdout[-3000:] + proc.stderr[-2000:])
        self.assertNotIn("FAIL", proc.stdout)


@unittest.skipUnless(os.environ.get("ETL_INCLUDE") and os.environ.get("CPPUTEST_PREFIX") and shutil.which("cmake"),
                     "needs ETL_INCLUDE, CPPUTEST_PREFIX (CppUTest install prefix) and cmake")
class CppUTestTemplateTest(unittest.TestCase):
    def test_host_tests_pass(self):
        with tempfile.TemporaryDirectory() as build:
            src = SKILL / "assets" / "cpp" / "templates" / "tests"
            cfg = subprocess.run(["cmake", "-S", str(src), "-B", build,
                                  f"-DETL_INCLUDE_DIR={os.environ['ETL_INCLUDE']}",
                                  f"-DCMAKE_PREFIX_PATH={os.environ['CPPUTEST_PREFIX']}"],
                                 capture_output=True, text=True, check=False)
            self.assertEqual(cfg.returncode, 0, cfg.stdout[-2000:] + cfg.stderr[-2000:])
            bld = subprocess.run(["cmake", "--build", build], capture_output=True, text=True, check=False)
            self.assertEqual(bld.returncode, 0, bld.stdout[-3000:] + bld.stderr[-2000:])
            run = subprocess.run([str(Path(build) / "host_tests"), "-r2", "-s"],
                                 capture_output=True, text=True, check=False)
            self.assertEqual(run.returncode, 0, run.stdout[-2000:])
            self.assertIn("OK (5 tests", run.stdout)


if __name__ == "__main__":
    unittest.main()
