import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class USBLoggerTests(unittest.TestCase):
    def test_usb_mount_is_opt_in_and_scoped(self):
        script = (ROOT / "initramfs/init").read_text()
        self.assertIn('MAIZON.OK', script)
        self.assertIn('MAIZON/KEXEC.LOG', script)
        self.assertIn('*/usb[0-9]*/*)', script)
        self.assertIn('mount -t "$filesystem" -o ro,', script)
        self.assertIn('mount -t "$filesystem" -o rw,sync,', script)
        self.assertIn('umount "$MNT"', script)
        for forbidden in ("/dev/block", "/dev/mmcblk", "sunxi_flash", "kexec -e", "dd of="):
            self.assertNotIn(forbidden, script)
    def test_reboot_is_marker_gated(self):
        script = (ROOT / "initramfs/init").read_text()
        self.assertIn('MAIZON.RBT', script)
        self.assertIn('if [ "$auto_return" -eq 1 ]; then', script)
        self.assertIn('reboot -f', script)
        self.assertIn('if ! umount "$MNT"', script)
    def test_kernel_rejects_internal_emmc_and_builtins_usb(self):
        script = (ROOT / "scripts/build_kit.sh").read_text()
        self.assertIn('-d MMC', script)
        self.assertIn("grep -qx '# CONFIG_MMC is not set'", script)
        for flag in ('CONFIG_USB_STORAGE', 'CONFIG_USB_EHCI_HCD',
                     'CONFIG_USB_OHCI_HCD', 'CONFIG_PHY_SUN4I_USB',
                     'CONFIG_VFAT_FS', 'CONFIG_EXFAT_FS'):
            self.assertIn(flag, script)
    def test_busybox_has_needed_applets(self):
        script = (ROOT / "scripts/build_kit.sh").read_text()
        for app in ('readlink', 'umount', 'head', 'tail', 'reboot'):
            self.assertIn(app, script)

if __name__ == "__main__":
    unittest.main()
