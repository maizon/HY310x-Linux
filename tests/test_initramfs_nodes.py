import gzip
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from make_initramfs import make_initramfs
from validate_kit import validate_initramfs


class EarlyDeviceNodesTests(unittest.TestCase):
    def rootfs(self, home):
        root = home / "root"
        (root / "bin").mkdir(parents=True)
        (root / "dev").mkdir()
        (root / "init").write_text("#!/bin/sh\n")
        (root / "bin" / "busybox").write_bytes(b"MOCK")
        os.chmod(root / "init", 0o755)
        os.chmod(root / "bin/busybox", 0o755)
        (root / "bin/sh").symlink_to("busybox")
        return root

    def test_console_and_null_exist_before_devtmpfs(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            target = home / "archive.gz"
            make_initramfs(self.rootfs(home), target)
            entries = validate_initramfs(target.read_bytes())
            self.assertEqual(entries["dev/console"][1:3], (5, 1))
            self.assertEqual(entries["dev/null"][1:3], (1, 3))
            self.assertTrue(stat.S_ISCHR(entries["dev/console"][0]))

    def test_reproducible_gzip(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            root = self.rootfs(home)
            a, b = home / "a.gz", home / "b.gz"
            make_initramfs(root, a)
            make_initramfs(root, b)
            self.assertEqual(a.read_bytes(), b.read_bytes())

    def test_reject_wrong_console_major(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            target = home / "archive.gz"
            make_initramfs(self.rootfs(home), target)
            raw = gzip.decompress(target.read_bytes())
            name_offset = raw.index(b"./dev/console")
            header_offset = raw.rfind(b"070701", 0, name_offset)
            major_offset = header_offset + 6 + 9 * 8
            corrupted = raw[:major_offset] + b"00000009" + raw[major_offset + 8:]
            with self.assertRaisesRegex(ValueError, "dev/console"):
                validate_initramfs(gzip.compress(corrupted, mtime=0))

    def test_refuse_fake_host_console(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            root = self.rootfs(home)
            (root / "dev/console").write_bytes(b"NOT A CHARACTER DEVICE")
            with self.assertRaisesRegex(ValueError, "special device"):
                make_initramfs(root, home / "out.gz")


if __name__ == "__main__":
    unittest.main()
