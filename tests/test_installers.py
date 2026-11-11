"""安装器回归：故障注入只作用于临时目录，不安装真实工具。"""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent


class InstallerTest(unittest.TestCase):
    def test_install_swap_and_failure_recovery(self):
        for failure in ("none", "copy", "backup", "replace"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                dest = root / "skill directory"
                target = dest / "embedded-engineering"
                target.mkdir(parents=True)
                (target / "old.txt").write_text("old version", encoding="utf-8")
                fake_bin = root / "bin"
                fake_bin.mkdir()
                for command in ("cp", "mv"):
                    actual = shutil.which(command)
                    self.assertIsNotNone(actual)
                    wrapper = fake_bin / command
                    wrapper.write_text(
                        '#!/bin/sh\n'
                        'case "$INSTALL_FAILURE:$1:$2" in\n'
                        '  copy:-R:*) [ "' + command + '" != cp ] || exit 41 ;;\n'
                        '  backup:*/embedded-engineering:*) exit 42 ;;\n'
                        '  replace:*/.embedded-engineering.tmp.*:*) exit 43 ;;\n'
                        'esac\n'
                        f'exec "{actual}" "$@"\n', encoding="utf-8")
                    wrapper.chmod(0o755)
                env = dict(os.environ, PATH=str(fake_bin) + os.pathsep + os.environ["PATH"],
                           INSTALL_FAILURE=failure)
                proc = subprocess.run(["sh", str(ROOT / "install.sh"), "--dest", str(dest), "--overwrite"],
                                      env=env, capture_output=True, text=True, check=False)
                if failure == "none":
                    self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
                    self.assertTrue((target / "SKILL.md").is_file())
                    self.assertFalse((target / "old.txt").exists())
                else:
                    self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
                    self.assertEqual((target / "old.txt").read_text(), "old version")
                    self.assertEqual(list(target.iterdir()), [target / "old.txt"])
                self.assertEqual(list(dest.iterdir()), [target])

    def test_dry_run_preserves_old_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "embedded-engineering"
            target.mkdir()
            marker = target / "old.txt"
            marker.write_text("old", encoding="utf-8")
            proc = subprocess.run(["sh", str(ROOT / "install.sh"), "--dest", tmp,
                                   "--overwrite", "--dry-run"], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(marker.read_text(), "old")
            self.assertEqual(list(Path(tmp).iterdir()), [target])

    def test_west_pinned_failure_does_not_install_latest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_uv = root / "uv"
            calls = root / "calls"
            fake_uv.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$INSTALL_CALLS"\n'
                               'echo "pinned install failed" >&2\nexit 42\n', encoding="utf-8")
            fake_uv.chmod(0o755)
            env = dict(os.environ, PATH=tmp + os.pathsep + os.environ["PATH"], INSTALL_CALLS=str(calls))
            proc = subprocess.run(["sh", str(ROOT / "tools/install_eval_tools.sh"), str(root / "prefix")],
                                  env=env, capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 42, proc.stdout + proc.stderr)
            self.assertEqual(calls.read_text().splitlines(), ["tool install --quiet west==1.4.0"])
            self.assertIn("pinned install failed", proc.stderr)
