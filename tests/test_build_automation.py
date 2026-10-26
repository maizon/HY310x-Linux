import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class BuildAutomationTests(unittest.TestCase):
    def test_build_workflow_has_readonly_permissions_and_automatic_checks(self):
        flow = (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
        self.assertIn("contents: read", flow)
        self.assertIn("cancel-in-progress: true", flow)
        self.assertIn("Validate complete kit", flow)
        self.assertIn("QEMU ARM32 userspace smoke test", flow)
        self.assertIn("HY310X-BUILD-FAILURE-DIAGNOSTICS", flow)
        self.assertIn("NO-GO", flow)
        for danger in ("sudo dd", "kexec -e", "sunxi_flash write", "fw_setenv"):
            self.assertNotIn(danger, flow)

    def test_busybox_does_not_compile_obsolete_tc_cbq(self):
        build = (ROOT / "scripts/build_kit.sh").read_text(encoding="utf-8")
        self.assertIn("CONFIG_TC=y", build)
        self.assertIn("# CONFIG_TC is not set", build)
        self.assertIn("UAPI CBQ", build)
        self.assertIn("CONFIG_STATIC=y", build)

    def test_smoke_checks_all_required_applets(self):
        smoke = (ROOT / "tools/smoke_arm32_userspace.sh").read_text()
        self.assertIn('qemu-arm-static "$BUSYBOX" --list', smoke)
        self.assertIn('grep -Fxq "$app"', smoke)

    def test_expensive_build_not_triggered_by_python_only_tests(self):
        flow = (ROOT / ".github/workflows/build.yml").read_text()
        self.assertNotIn("'tests/**'", flow)
        self.assertNotIn("'tools/**'", flow)
        self.assertIn("'tools/smoke_arm32_userspace.sh'", flow)

    def test_smoke_does_not_attempt_kernel_boot(self):
        smoke = (ROOT / "tools/smoke_arm32_userspace.sh").read_text(encoding="utf-8")
        self.assertIn("qemu-arm-static", smoke)
        self.assertIn("MAIZON_ARM32_OK", smoke)
        for danger in ("kexec -e", "kexec -l", "qemu-system-arm", "/dev/block", "dd of="):
            self.assertNotIn(danger, smoke)

if __name__ == "__main__":
    unittest.main()
