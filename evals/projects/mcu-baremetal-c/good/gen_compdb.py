"""为 clang-tidy 生成 compile_commands.json（目录写绝对路径）。用法：python3 gen_compdb.py <源文件...>"""
import json
import os
import sys

INCLUDES = ["-Iinterface", "-Imodule/ledctl", "-Ibsp", "-Iplatform/board"]
cwd = os.getcwd()
entries = [{"directory": cwd, "file": f,
            "arguments": ["clang", "-x", "c", "-std=c99", "-Wall", *INCLUDES, "-c", f]} for f in sys.argv[1:]]
with open("compile_commands.json", "w", encoding="utf-8") as fh:
    json.dump(entries, fh, indent=1)
