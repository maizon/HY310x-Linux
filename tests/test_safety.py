import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class SafetyTests(unittest.TestCase):
    def test_boot_is_explicitly_blocked(self):
        data = json.loads((ROOT / "config/hardware.json").read_text())
        self.assertIs(data["boot_allowed"], False)
        self.assertIs(data["boot_validated"], False)
        self.assertIs(data["kexec"]["kexec_load_tested"], False)
        self.assertIs(data["kexec"]["kexec_execute_tested"], False)

    def test_readonly_preflight_does_not_execute_kexec(self):
        s = (ROOT / "tools/read_only_preflight.sh").read_text()
        for bad in ("kexec -l", "kexec -e", "dd of=", "sunxi_flash write", "reboot -f"):
            self.assertNotIn(bad, s)

    def test_init_has_no_storage_writes(self):
        s = (ROOT / "initramfs/init").read_text()
        for bad in ("/dev/mmcblk", "/dev/block", "sunxi_flash", "kexec -e"):
            self.assertNotIn(bad, s)


if __name__ == "__main__":
    unittest.main()
