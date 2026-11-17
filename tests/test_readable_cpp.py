"""真实主机工程验收；所有变体在临时目录，不触碰固件与设备。"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills/embedded-engineering"
GATE = SKILL / "scripts/style_gate.py"
STYLE = SKILL / "assets/cpp/readable-cpp"


def run(*args, cwd=None, env=None):
    return subprocess.run([str(a) for a in args], cwd=cwd, env=env, capture_output=True,
                          text=True, check=False)


def put(root, name, text):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def configure(root):
    proc = run("cmake", "-S", root, "-B", root / "build", "-G", "Ninja",
               "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON")
    if proc.returncode:
        raise RuntimeError(proc.stdout + proc.stderr)


def make_mcu(root):
    # G474 风格的边界/命名工程；主机验证，不是 G474 HAL 或 MCU 运行证据。
    put(root, "board.ioc", "Mcu.Name=STM32G474RET6\n")
    for name in (".clang-format", ".clang-tidy"):
        (root / "cpp").mkdir(exist_ok=True)
        (root / "c").mkdir(exist_ok=True)
        shutil.copy(STYLE / name, root / "cpp" / name)
        shutil.copy(SKILL / "assets/barr-c" / name, root / "c" / name)
    shutil.copy(SKILL / "assets/cpp/abi/backlight.h", root / "c/backlight.h")
    shutil.copy(SKILL / "assets/cpp/abi/backlight.cpp", root / "cpp/backlight.cpp")
    shutil.copy(STYLE / "examples/brightness.hpp", root / "cpp/brightness.hpp")
    put(root, "cpp/test.cpp", '#include "brightness.hpp"\n\n'
        '/// @brief Exercise the owned C++ interface on the host. No hardware.\n'
        'void testBrightness()\n{\n    display_ui::Brightness brightness;\n'
        '    brightness.setLevel(0);\n}\n')
    put(root, "c/main.c", '#include "backlight.h"\n\n'
        '/** @brief Verify the C-to-C++ call on the host. Owns no resources. */\n'
        'int main(void)\n{\n    return (backlight_clamp(0U) == 0U) ? 0 : 1;\n}\n')
    put(root, "CMakeLists.txt", 'cmake_minimum_required(VERSION 3.20)\n'
        'project(g474_boundary LANGUAGES C CXX)\nset(CMAKE_CXX_STANDARD 17)\n'
        'add_executable(app c/main.c cpp/backlight.cpp cpp/test.cpp)\n'
        'target_include_directories(app PRIVATE c cpp)\n'
        'target_compile_options(app PRIVATE -Wall -Wextra -Werror)\n'
        'enable_testing()\nadd_test(NAME abi COMMAND app)\n')
    for path in [root / "c/main.c", root / "c/backlight.h", *root.glob("cpp/*.cpp"),
                 *root.glob("cpp/*.hpp")]:
        proc = run("clang-format", "-i", "--style=file", path)
        if proc.returncode:
            raise RuntimeError(proc.stderr)
    manifest = {"version": 1, "llvm_major": 23, "style": "project",
                "compile_commands": "build/compile_commands.json", "cpp": ["cpp/*.cpp"],
                "cpp_headers": ["cpp/*.hpp"], "c": ["c/*.c", "c/*.h"], "doxygen": True}
    put(root, "style-gate.json", json.dumps(manifest))
    configure(root)
    return manifest


@unittest.skipUnless(all(shutil.which(p) for p in ("cmake", "ninja", "clang-format", "clang-tidy",
                                                   "clang", "clang++", "gcc", "g++")),
                     "host LLVM/CMake toolchain unavailable")
class ReadableCppTest(unittest.TestCase):
    def gate(self, root):
        return run(sys.executable, GATE, "--root", root, "--manifest", root / "style-gate.json")

    def assert_ok(self, proc):
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_g474_mixed_abi_naming_documentation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_mcu(root)
            self.assert_ok(run("cmake", "--build", root / "build"))
            self.assert_ok(run("ctest", "--test-dir", root / "build", "--output-on-failure"))
            self.assert_ok(self.gate(root))
            # 两种语言独立包含同一 ABI 头。
            for compiler, lang in (("gcc", "c"), ("g++", "c++")):
                self.assert_ok(run(compiler, "-x", lang, "-fsyntax-only", root / "c/backlight.h"))
            self.assert_ok(run("g++", "-x", "c++", "-fsyntax-only", root / "cpp/brightness.hpp"))
            path = root / "cpp/brightness.hpp"
            original = path.read_text()
            path.write_text(original.replace("setLevel", "set_level"))
            caller = root / "cpp/test.cpp"
            caller_original = caller.read_text()
            caller.write_text(caller_original.replace("setLevel", "set_level"))
            proc = self.gate(root)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("[readability-identifier-naming,", proc.stdout)
            self.assertNotIn("DOC-001 cpp/", proc.stdout)
            caller.write_text(caller_original)
            path.write_text(original.replace("    /// @brief Set the requested level. Thread context only; owns no resources.\n", "")
                            .replace("    /// @param requestedLevel Desired percent; values above 100 are clamped.\n", ""))
            proc = self.gate(root)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("missing Doxygen block for setLevel", proc.stdout)
            self.assertNotIn("CPPF-002", proc.stdout)
            # 类级注释不能代替方法级；普通注释也不算 Doxygen。
            path.write_text(path.read_text().replace("class Brightness", "/// @brief A level.\nclass Brightness")
                            .replace("    void setLevel", "    // Ordinary comment is not Doxygen.\n    void setLevel"))
            self.assertIn("missing Doxygen block for setLevel", self.gate(root).stdout)

    def test_main_header_include_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_mcu(root)
            put(root, "cpp/other.hpp", "#pragma once\n")
            put(root, "cpp/include_order.hpp", "#pragma once\n")
            put(root, "cpp/include_order.cpp",
                '#include "other.hpp"\n#include "include_order.hpp"\n\n'
                '/// @brief Return a fixed value for the include-order fixture.\n'
                'int includeOrderValue()\n{\n    return 0;\n}\n')
            cmake = root / "CMakeLists.txt"
            cmake.write_text(cmake.read_text().replace("cpp/test.cpp)",
                                                     "cpp/test.cpp cpp/include_order.cpp)"))
            configure(root)
            proc = self.gate(root)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("CPPF-001", proc.stdout)
            put(root, "cpp/include_order.cpp",
                '#include "include_order.hpp"\n#include "other.hpp"\n\n'
                '/// @brief Return a fixed value for the include-order fixture.\n'
                'int includeOrderValue()\n{\n    return 0;\n}\n')
            self.assert_ok(self.gate(root))

    def test_layout_negative_and_project_precedence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = make_mcu(root)
            shutil.copy(STYLE / "examples/bad_brightness.hpp", root / "cpp/brightness.hpp")
            # 使用反例的调用名，使失败不来自 C++ 语法/符号。
            path = root / "cpp/test.cpp"
            path.write_text(path.read_text().replace("setLevel", "set_level"))
            proc = self.gate(root)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("CPPF-001", proc.stdout)
            self.assertIn("[readability-identifier-naming,", proc.stdout)
            manifest["style"] = "readable-cpp"
            put(root, "style-gate.json", json.dumps(manifest))
            proc = self.gate(root)
            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
            self.assertIn("project config exists", proc.stderr)

    def test_rk3588_project_style_no_mcu_constraints(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            put(root, ".clang-format", "BasedOnStyle: LLVM\nIndentWidth: 2\n")
            put(root, ".clang-tidy", "Checks: '-*,readability-identifier-naming'\n"
                "CheckOptions:\n  readability-identifier-naming.FunctionCase: lower_case\n")
            put(root, "main.cxx", '#include <linux/can.h>\n#include <linux/can/raw.h>\n'
                '#include <sys/epoll.h>\n#include <sys/socket.h>\n#include <unistd.h>\n'
                '#include <stdexcept>\n#include <typeinfo>\n'
                '/// @brief Return a fixed value for the host test.\n'
                'int project_function() { return 0; }\n'
                '/// @brief Exercise the SocketCAN/epoll host path.\n'
                'int main() {\n  try { throw std::runtime_error("host"); }\n'
                '  catch (const std::exception& error) { (void)typeid(error); }\n'
                '  const int socket_fd = socket(PF_CAN, SOCK_RAW, CAN_RAW);\n'
                '  if (socket_fd < 0) { return 1; }\n'
                '  const int epoll_fd = epoll_create1(EPOLL_CLOEXEC);\n'
                '  close(socket_fd);\n'
                '  if (epoll_fd < 0) { return 1; }\n  close(epoll_fd);\n'
                '  return project_function();\n}\n')
            self.assert_ok(run("clang-format", "-i", root / "main.cxx"))
            put(root, "CMakeLists.txt", 'cmake_minimum_required(VERSION 3.20)\n'
                'project(rk3588_host LANGUAGES CXX)\nadd_executable(app main.cxx)\n'
                'enable_testing()\nadd_test(NAME posix COMMAND app)\n')
            put(root, "style-gate.json", json.dumps({"version": 1, "llvm_major": 23,
                "style": "project", "compile_commands": "build/compile_commands.json",
                "cpp": ["*.cxx"], "c": []}))
            configure(root)
            self.assert_ok(run("cmake", "--build", root / "build"))
            self.assert_ok(run("ctest", "--test-dir", root / "build", "--output-on-failure"))
            self.assert_ok(self.gate(root))
            proc = run(sys.executable, SKILL / "scripts/detect_profile.py", root)
            self.assert_ok(proc)
            report = json.loads(proc.stdout)
            self.assertEqual(report["suggested"], "linux-userspace")
            self.assertEqual(report["resource_tier"]["suggested"], "T3")
            commands = (root / "build/compile_commands.json").read_text()
            self.assertNotIn("-fno-exceptions", commands)
            self.assertNotIn("-fno-rtti", commands)
            self.assertNotIn("linker_discard", (root / "build/build.ninja").read_text())

    def test_doxygen_defaults_to_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = make_mcu(root)
            del manifest["doxygen"]
            put(root, "style-gate.json", json.dumps(manifest))
            path = root / "cpp/brightness.hpp"
            text = path.read_text()
            doc = ("    /// @brief Set the requested level. Thread context only; owns no resources.\n"
                   "    /// @param requestedLevel Desired percent; values above 100 are clamped.\n")
            self.assertIn(doc, text)
            path.write_text(text.replace(doc, ""))
            proc = self.gate(root)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("DOC-001 cpp/brightness.hpp", proc.stdout)
            self.assertIn("missing Doxygen block for setLevel", proc.stdout)
            path.write_text(text)
            c_main = root / "c/main.c"
            c_text = c_main.read_text()
            c_doc = "/** @brief Verify the C-to-C++ call on the host. Owns no resources. */\n"
            self.assertIn(c_doc, c_text)
            c_main.write_text(c_text.replace(c_doc, ""))
            proc = self.gate(root)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("DOC-001 c/main.c", proc.stdout)
            self.assertIn("missing Doxygen block for main", proc.stdout)
            manifest["doxygen"] = False
            put(root, "style-gate.json", json.dumps(manifest))
            self.assert_ok(self.gate(root))

    def test_internal_linkage_docs_do_not_cross_translation_units(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_mcu(root)
            for name, comment in (("first", "/// @brief Return a fixed level."),
                                  ("second", "// Ordinary comment, not documentation.")):
                path = put(root, f"cpp/doc_{name}.cpp", f"{comment}\n"
                    "static int localValue() { return 0; }\nnamespace {\n"
                    f"{comment}\nint hiddenValue() {{ return 0; }}\n}}\n"
                    f"/// @brief Use both local helpers.\nint {name}Value()\n"
                    "{ return localValue() + hiddenValue(); }\n")
                self.assert_ok(run("clang-format", "-i", path))
            path = root / "CMakeLists.txt"
            path.write_text(path.read_text().replace("cpp/test.cpp)",
                            "cpp/test.cpp cpp/doc_first.cpp cpp/doc_second.cpp)"))
            configure(root)
            proc = self.gate(root)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("DOC-001 cpp/doc_second.cpp", proc.stdout)
            self.assertIn("missing Doxygen block for localValue", proc.stdout)
            self.assertIn("missing Doxygen block for hiddenValue", proc.stdout)
            self.assertNotIn("CPPF-002", proc.stdout)

    def test_empty_config_tool_and_database_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            put(root, "stray.cpp", "int WrongName() { return 0; }\n")
            manifest = {"version": 1, "cpp": [], "c": [], "style": "readable-cpp"}
            put(root, "style-gate.json", json.dumps(manifest))
            proc = run(sys.executable, GATE, "--root", root, "--manifest", root / "style-gate.json",
                       env=dict(os.environ, PATH=""))
            self.assert_ok(proc)
            self.assertIn("PASS EMPTY", proc.stdout)
            manifest.update(cpp=["*.cpp"], compile_commands="missing.json")
            put(root, "style-gate.json", json.dumps(manifest))
            proc = run(sys.executable, GATE, "--root", root, "--manifest", root / "style-gate.json",
                       env=dict(os.environ, PATH=""))
            self.assertEqual(proc.returncode, 3)
            self.assertIn("TOOL_MISSING", proc.stderr)
            proc = self.gate(root)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("CONFIG_ERROR", proc.stderr)
            put(root, ".clang-format", "ThisOptionDoesNotExist: true\n")
            put(root, ".clang-tidy", "Checks: '-*,readability-identifier-naming'\n")
            manifest["style"] = "project"
            put(root, "style-gate.json", json.dumps(manifest))
            proc = self.gate(root)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("unknown key", proc.stderr)


class CppDetectionRegression(unittest.TestCase):
    def test_linux_suffixes_and_mixed_repository(self):
        for suffix in (".c", ".cpp", ".cc", ".cxx"):
            for include in ("sys/epoll.h", "linux/can.h", "linux/can/raw.h"):
                with self.subTest(suffix=suffix, include=include), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    put(root, "app" + suffix, f"#include <{include}>\n")
                    proc = run(sys.executable, SKILL / "scripts/detect_profile.py", root)
                    report = json.loads(proc.stdout)
                    self.assertEqual(report["suggested"], "linux-userspace")
                    put(root, "firmware/startup_stm32g474.s", "")
                    put(root, "firmware/core_cm4.h", "")
                    report = json.loads(run(sys.executable, SKILL / "scripts/detect_profile.py", root).stdout)
                    self.assertIn("linux-userspace", {p["profile"] for p in report["candidates"]})


if __name__ == "__main__":
    unittest.main()
