"""固定 arena 的边界、全局 new/delete 入口和锁定行为（主机）及 ARM 编译。"""

import resource
import shutil
import signal
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUARD = ROOT / "skills/embedded-engineering/assets/cpp/templates/bsp/heap_guard.cpp"
PROBE = ROOT / "tests/cpp/heap_guard_probe.cpp"


def no_core():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


class HeapGuardTest(unittest.TestCase):
    def test_host_entrypoints_and_boundaries(self):
        compilers = [p for p in ("g++", "clang++") if shutil.which(p)]
        if not compilers:
            self.skipTest("no host C++ toolchain")
        with tempfile.TemporaryDirectory() as tmp:
            for compiler in compilers:
                for standard in ("c++17", "c++20"):
                    with self.subTest(compiler=compiler, standard=standard):
                        exe = Path(tmp) / f"{compiler}-{standard}"
                        proc = subprocess.run([compiler, f"-std={standard}", "-O0", "-fno-exceptions",
                                               "-fno-rtti", "-fsized-deallocation", "-Wall", "-Wextra",
                                               "-Werror", str(GUARD), str(PROBE), "-o", str(exe)],
                                              capture_output=True, text=True, check=False)
                        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
                        for mode in ("before", "capacity", "overflow", "padding", "invalid-align", "zero",
                                     "delete-null", "lock2", "lock3", "lock6", "lock7"):
                            proc = subprocess.run([str(exe), mode], capture_output=True, text=True,
                                                  check=False, preexec_fn=no_core)
                            self.assertEqual(proc.returncode, 0, f"{mode}: {proc.stdout}{proc.stderr}")
                            self.assertIn(f"HEAP_PASS:{mode}", proc.stdout)
                        for mode in ["lock0", "lock1", "lock4", "lock5", "oversize",
                                     *("free" + chr(ord("A") + i) for i in range(12))]:
                            proc = subprocess.run([str(exe), mode], capture_output=True, text=True,
                                                  check=False, preexec_fn=no_core)
                            self.assertIn(proc.returncode, (-signal.SIGILL, -signal.SIGTRAP),
                                          f"{mode}: {proc.returncode} {proc.stdout}{proc.stderr}")
                            self.assertIn(f"HEAP_EXPECT_TRAP:{mode}", proc.stdout)

    @unittest.skipUnless(shutil.which("arm-none-eabi-g++"), "ARM cross toolchain missing")
    def test_arm_compile_matrix_and_exported_overloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            obj = Path(tmp) / "guard.o"
            for standard in ("c++17", "c++20"):
                for cpu in ("cortex-m0plus", "cortex-m4", "cortex-m7"):
                    with self.subTest(standard=standard, cpu=cpu):
                        proc = subprocess.run(["arm-none-eabi-g++", f"-std={standard}", f"-mcpu={cpu}",
                                               "-mthumb", "-fno-exceptions", "-fno-rtti", "-Wall",
                                               "-Wextra", "-Werror", "-c", str(GUARD), "-o", str(obj)],
                                              capture_output=True, text=True, check=False)
                        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
                        proc = subprocess.run(["arm-none-eabi-nm", "-C", "--defined-only", str(obj)],
                                              capture_output=True, text=True, check=False)
                        self.assertEqual(proc.returncode, 0, proc.stderr)
                        names = [line for line in proc.stdout.splitlines() if " T operator " in line]
                        self.assertEqual(len([n for n in names if "operator new" in n]), 8, names)
                        self.assertEqual(len([n for n in names if "operator delete" in n]), 12, names)


if __name__ == "__main__":
    unittest.main()
