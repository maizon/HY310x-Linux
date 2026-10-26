import pathlib
import struct
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from analyze_fdt import analyze_fdt
from inspect_android_boot import prepare, ZIMAGE_MAGIC


def mock_fdt(memory=True, reserve=True, corrupt=False, missing_end=False):
    names = ("#address-cells", "#size-cells", "reg", "device_type")
    strings = b"".join(name.encode() + b"\0" for name in names)
    offsets = {name: strings.index(name.encode() + b"\0") for name in names}
    body = bytearray()

    def token(value):
        body.extend(struct.pack(">I", value))

    def begin(name):
        token(1)
        raw = name.encode() + b"\0"
        body.extend(raw + b"\0" * (-len(raw) % 4))

    def prop(name, raw):
        token(3)
        body.extend(struct.pack(">II", len(raw), offsets[name]))
        body.extend(raw + b"\0" * (-len(raw) % 4))

    begin("")
    prop("#address-cells", struct.pack(">I", 2))
    prop("#size-cells", struct.pack(">I", 2))
    if memory:
        begin("memory@40000000")
        prop("device_type", b"memory\0")
        prop("reg", struct.pack(">IIII", 0, 0x40000000, 0, 0x10000000))
        token(2)
    if reserve:
        begin("reserved-memory")
        prop("#address-cells", struct.pack(">I", 2))
        prop("#size-cells", struct.pack(">I", 2))
        begin("framebuffer@4f000000")
        prop("reg", struct.pack(">IIII", 0, 0x4f000000, 0, 0x1000000))
        token(2)
        token(2)
    token(2)
    if not missing_end:
        token(9)
    reservations = struct.pack(">QQQQ", 0x41000000, 0x1000, 0, 0)
    off_struct = 40 + len(reservations)
    off_strings = off_struct + len(body)
    total = off_strings + len(strings)
    header = struct.pack(">10I", 0xd00dfeed, total, off_struct, off_strings,
                         40, 17, 16, 0, len(strings), len(body))
    data = bytearray(header + reservations + body + strings)
    if corrupt:
        struct.pack_into(">I", data, 4, total + 100)
    return bytes(data)


class FdtAnalysisTests(unittest.TestCase):
    def test_memory_and_reservations(self):
        result = analyze_fdt(mock_fdt())
        self.assertTrue(result["memory_node_present"])
        self.assertEqual(result["memory_ranges"], [["0x40000000", "0x10000000"]])
        self.assertEqual(result["reserved_memory_ranges"], [["0x4f000000", "0x1000000"]])
        self.assertEqual(result["memreserve_ranges"], [["0x41000000", "0x1000"]])
        self.assertFalse(result["boot_approved"])

    def test_no_memory_stays_no_go(self):
        result = analyze_fdt(mock_fdt(memory=False))
        self.assertFalse(result["memory_node_present"])
        self.assertTrue(result["warnings"])

    def test_truncated_fdt_rejected(self):
        with self.assertRaisesRegex(ValueError, "size"):
            analyze_fdt(mock_fdt(corrupt=True))

    def test_missing_end_rejected(self):
        with self.assertRaisesRegex(ValueError, "END"):
            analyze_fdt(mock_fdt(missing_end=True))

    def test_unterminated_memreserve_rejected(self):
        data = bytearray(mock_fdt())
        struct.pack_into(">QQ", data, 56, 0x42000000, 0x1000)
        with self.assertRaisesRegex(ValueError, "terminator"):
            analyze_fdt(bytes(data))

    def test_bad_property_offset_rejected(self):
        data = bytearray(mock_fdt())
        off = struct.unpack_from(">I", data, 8)[0]
        struct.pack_into(">I", data, off + 16, 9999)
        with self.assertRaisesRegex(ValueError, "property out of bounds"):
            analyze_fdt(bytes(data))

    def test_private_boot_inspector_integrates_fdt_audit(self):
        with tempfile.TemporaryDirectory() as td:
            base = pathlib.Path(td)
            kernel = bytearray(4096)
            struct.pack_into("<I", kernel, 0x24, ZIMAGE_MAGIC)
            header = bytearray(4096)
            header[:8] = b"ANDROID!"
            struct.pack_into("<4I", header, 8, len(kernel), 0, 0, 1580)
            struct.pack_into("<I", header, 40, 3)
            (base / "boot.img").write_bytes(header + kernel)
            (base / "stock.fdt").write_bytes(mock_fdt())
            result = prepare(base / "boot.img", base / "stock.fdt", base / "private")
            self.assertTrue(result["fdt_audit"]["memory_node_present"])
            self.assertFalse(result["fdt_audit"]["boot_approved"])


if __name__ == "__main__":
    unittest.main()
