import pathlib
import struct
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from inspect_android_boot import PAGE, ZIMAGE_MAGIC, parse_boot_header, require_arm32_zimage, parse_fdt_header, prepare


def mock_boot(payload, version=3):
    header = bytearray(PAGE)
    header[:8] = b"ANDROID!"
    struct.pack_into("<4I", header, 8, len(payload), 0, 0, 1580 if version == 3 else 1584)
    struct.pack_into("<I", header, 40, version)
    return bytes(header) + payload


def mock_fdt():
    data = bytearray(128)
    struct.pack_into(">10I", data, 0, 0xd00dfeed, 128, 48, 80, 64, 17, 16, 0, 48, 16)
    return bytes(data)


class PrivateAutoKexecTests(unittest.TestCase):
    def test_extract_kernel_and_original_fdt(self):
        with tempfile.TemporaryDirectory() as td:
            base = pathlib.Path(td)
            kernel = bytearray(2048)
            struct.pack_into("<I", kernel, 0x24, ZIMAGE_MAGIC)
            (base / "boot.img").write_bytes(mock_boot(kernel))
            (base / "original.fdt").write_bytes(mock_fdt())
            report = prepare(base / "boot.img", base / "original.fdt", base / "private")
            self.assertIn("NO-GO", report["status"])
            self.assertEqual((base / "private/stock-zImage").read_bytes(), bytes(kernel))
            self.assertEqual((base / "private/stock-original.fdt").read_bytes(), mock_fdt())
            with self.assertRaisesRegex(ValueError, "vazia"):
                prepare(base / "boot.img", base / "original.fdt", base / "private")

    def test_non_arm32_payload_rejected(self):
        with self.assertRaisesRegex(ValueError, "nao identificado"):
            require_arm32_zimage(b"x" * 2048)

    def test_android_magic_and_truncated_rejected(self):
        with self.assertRaises(ValueError):
            parse_boot_header(b"x" * PAGE, PAGE)
        with self.assertRaisesRegex(ValueError, "truncada"):
            parse_boot_header(mock_boot(b"x" * 512)[:PAGE], PAGE)

    def test_fdt_invalid_rejected(self):
        with self.assertRaises(ValueError):
            parse_fdt_header(b"x" * 100)

    def test_capture_read_only_evidence(self):
        text = (ROOT / "tools/capture_stock_android.sh").read_text()
        self.assertIn('if="$BOOT"', text)
        self.assertIn("cat /sys/firmware/fdt", text)
        self.assertIn('getprop ro.boot.slot_suffix', text)
        for bad in ("kexec -l", "kexec -e", "dd of=/dev/block", "sunxi_flash write"):
            self.assertNotIn(bad, text)


if __name__ == "__main__":
    unittest.main()
