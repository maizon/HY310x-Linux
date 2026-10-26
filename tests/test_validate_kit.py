import gzip
import pathlib
import struct
import sys
import tempfile
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
from validate_kit import (
    validate_zimage, validate_dtb, validate_initramfs,
    validate_kexec_arm32_static, check_dir,
)


def make_valid_files(directory):
    z = bytearray(512)
    struct.pack_into("<I", z, 0x24, 0x016F2818)
    dtb = bytearray(48)
    dtb[:4] = b"\xd0\x0d\xfe\xed"
    struct.pack_into(">I", dtb, 4, len(dtb))
    elf = bytearray(64)
    elf[:6] = b"\x7fELF\x01\x01"
    struct.pack_into("<H", elf, 18, 40)
    blobs = {
        "zImage": bytes(z),
        "hy310x-candidate.dtb": bytes(dtb),
        "initramfs.cpio.gz": gzip.compress(b"070701" + b"0" * 256),
        "kexec": bytes(elf),
    }
    import hashlib
    for name, value in blobs.items():
        (directory / name).write_bytes(value)
    (directory / "NO-GO.txt").write_text("NÃO EXECUTAR")
    (directory / "manifest.sha256").write_text(
        "".join(f"{hashlib.sha256(value).hexdigest()}  {name}\n" for name, value in blobs.items())
    )
    return blobs


class ValidatorTests(unittest.TestCase):
    def test_formats_and_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            d = pathlib.Path(td)
            make_valid_files(d)
            check_dir(d)

    def test_wrong_zimage_magic(self):
        with self.assertRaisesRegex(ValueError, "magic"):
            validate_zimage(b"\0" * 100)

    def test_wrong_dtb(self):
        with self.assertRaisesRegex(ValueError, "DTB"):
            validate_dtb(b"INVALID")

    def test_wrong_initramfs(self):
        with self.assertRaisesRegex(ValueError, "gzip"):
            validate_initramfs(b"no gzip")

    def test_non_arm_elf(self):
        with self.assertRaisesRegex(ValueError, "arquitetura"):
            elf = bytearray(64)
            elf[:6] = b"\x7fELF\x01\x01"
            struct.pack_into("<H", elf, 18, 3)
            validate_kexec_arm32_static(elf)

    def test_dynamic_elf_blocked(self):
        elf = bytearray(128)
        elf[:6] = b"\x7fELF\x01\x01"
        struct.pack_into("<H", elf, 18, 40)
        struct.pack_into("<I", elf, 28, 52)
        struct.pack_into("<HH", elf, 42, 32, 1)
        struct.pack_into("<I", elf, 52, 3)
        with self.assertRaisesRegex(ValueError, "PT_INTERP"):
            validate_kexec_arm32_static(elf)

    def test_hash_tamper(self):
        with tempfile.TemporaryDirectory() as td:
            d = pathlib.Path(td)
            make_valid_files(d)
            (d / "manifest.sha256").write_text("bad\n")
            with self.assertRaisesRegex(ValueError, "sha256"):
                check_dir(d)


if __name__ == "__main__":
    unittest.main()
