#!/usr/bin/env python3
"""Bounded structural audit of a PRIVATE OEM FDT. No hardware access or boot.

Reports memory and reservation layout only; never prints private bootargs,
device IDs or property values. This is NOT proof of physical Kexec readiness.
"""
import argparse
import json
from pathlib import Path
import struct

MAGIC = 0xD00DFEED
BEGIN_NODE, END_NODE, PROP, NOP, END = 1, 2, 3, 4, 9
MAX_BYTES = 16 * 1024 * 1024
MAX_RANGES = 256


def u32(blob, offset):
    if offset < 0 or offset + 4 > len(blob):
        raise ValueError("FDT truncated integer")
    return struct.unpack_from(">I", blob, offset)[0]


def align4(value):
    return (value + 3) & ~3


def cstring(blob, offset, end):
    if offset >= end:
        raise ValueError("FDT string offset out of bounds")
    stop = blob.find(b"\0", offset, end)
    if stop < 0:
        raise ValueError("FDT unterminated string")
    return blob[offset:stop].decode("ascii", "replace"), stop + 1


def cell_count(blob, label):
    if len(blob) != 4:
        raise ValueError(f"{label}: malformed cell count")
    return struct.unpack(">I", blob)[0]


def decode_reg(blob, address_cells, size_cells, label):
    if address_cells not in (1, 2) or size_cells not in (1, 2):
        raise ValueError(f"{label}: unsupported address/size cells {address_cells}/{size_cells}")
    stride = (address_cells + size_cells) * 4
    if not blob or len(blob) % stride:
        raise ValueError(f"{label}: malformed reg")
    regions = []
    for offset in range(0, len(blob), stride):
        address = int.from_bytes(blob[offset:offset + address_cells * 4], "big")
        size = int.from_bytes(blob[offset + address_cells * 4:offset + stride], "big")
        if not size or address + size > 1 << 64:
            raise ValueError(f"{label}: zero/overflowing region")
        regions.append((address, size))
    return regions


def analyze_fdt(data: bytes) -> dict:
    if not (40 <= len(data) <= MAX_BYTES):
        raise ValueError("FDT size out of bounds")
    (magic, total, struct_off, strings_off, reserve_off, version,
     compatible, _bootcpu, strings_size, struct_size) = struct.unpack_from(">10I", data)
    if magic != MAGIC or not (40 <= total <= len(data)):
        raise ValueError("FDT invalid magic or total size")
    if version < 16 or compatible > 17 or compatible > version:
        raise ValueError("FDT unsupported version")
    if not (40 <= reserve_off < total and 40 <= struct_off < total and 40 <= strings_off < total):
        raise ValueError("FDT invalid offsets")
    if reserve_off % 8 or struct_off % 4 or strings_off % 4:
        raise ValueError("FDT unaligned offsets")
    if not struct_size or not strings_size or struct_off + struct_size > total or strings_off + strings_size > total:
        raise ValueError("FDT truncated struct/string blocks")
    reservations = []
    cursor = reserve_off
    while True:
        if cursor + 16 > struct_off:
            raise ValueError("FDT memreserve terminator missing")
        address, size = struct.unpack_from(">QQ", data, cursor)
        cursor += 16
        if address == size == 0:
            break
        if not size or address + size > 1 << 64:
            raise ValueError("FDT invalid memreserve range")
        reservations.append((address, size))
        if len(reservations) > MAX_RANGES:
            raise ValueError("FDT excessive memreserve ranges")

    nodes, stack = [], []
    cursor, struct_end = struct_off, struct_off + struct_size
    finished = False
    while cursor < struct_end:
        token = u32(data, cursor)
        cursor += 4
        if token == BEGIN_NODE:
            name, cursor = cstring(data, cursor, struct_end)
            cursor = align4(cursor)
            if len(stack) >= 64:
                raise ValueError("FDT excessive node nesting")
            if not stack and nodes:
                raise ValueError("FDT duplicate root node")
            if not stack and name not in ("", "/"):
                raise ValueError("FDT malformed root")
            nodes.append({"name": name, "parent": stack[-1] if stack else None, "props": {}})
            stack.append(len(nodes) - 1)
        elif token == END_NODE:
            if not stack:
                raise ValueError("FDT unbalanced node")
            stack.pop()
        elif token == PROP:
            if not stack or cursor + 8 > struct_end:
                raise ValueError("FDT invalid property placement")
            length, name_offset = struct.unpack_from(">II", data, cursor)
            cursor += 8
            if name_offset >= strings_size or cursor + length > struct_end:
                raise ValueError("FDT property out of bounds")
            name, _ = cstring(data, strings_off + name_offset, strings_off + strings_size)
            if name in ("#address-cells", "#size-cells", "reg", "device_type", "status"):
                nodes[stack[-1]]["props"][name] = data[cursor:cursor + length]
            cursor = align4(cursor + length)
        elif token == NOP:
            continue
        elif token == END:
            if stack:
                raise ValueError("FDT premature END")
            finished = True
            break
        else:
            raise ValueError(f"FDT unknown token {token}")
    if not finished or not nodes:
        raise ValueError("FDT missing END/root")

    root = nodes[0]["props"]
    root_address = cell_count(root.get("#address-cells", struct.pack(">I", 2)), "root address")
    root_size = cell_count(root.get("#size-cells", struct.pack(">I", 1)), "root size")
    memory, reserved = [], []
    unresolved = 0
    for node in nodes[1:]:
        parent = node["parent"]
        props = node["props"]
        is_memory = parent == 0 and (
            node["name"] == "memory" or node["name"].startswith("memory@") or
            props.get("device_type", b"").rstrip(b"\0") == b"memory"
        )
        if is_memory and props.get("status", b"").rstrip(b"\0") != b"disabled":
            if "reg" in props:
                memory.extend(decode_reg(props["reg"], root_address, root_size, "memory"))
        if parent is not None and nodes[parent]["parent"] == 0 and nodes[parent]["name"] == "reserved-memory":
            rp = nodes[parent]["props"]
            a = cell_count(rp.get("#address-cells", struct.pack(">I", root_address)), "reserved address")
            s = cell_count(rp.get("#size-cells", struct.pack(">I", root_size)), "reserved size")
            if "reg" in props:
                reserved.extend(decode_reg(props["reg"], a, s, "reserved-memory"))
            else:
                unresolved += 1
    if len(memory) > MAX_RANGES or len(reserved) > MAX_RANGES:
        raise ValueError("FDT excessive reg ranges")
    warnings = []
    if not memory:
        warnings.append("No enabled /memory reg; handoff NOT approved")
    if unresolved:
        warnings.append("Dynamic reserved-memory entries unresolved")
    for i, (addr, size) in enumerate(memory):
        if any(addr < other + length and other < addr + size for other, length in memory[:i]):
            warnings.append("Overlapping /memory ranges")
            break
    for addr, size in reservations + reserved:
        if memory and not any(addr >= start and addr + size <= start + length for start, length in memory):
            warnings.append("Reserved range outside /memory; manual OEM review needed")
            break
    encode = lambda regions: [[f"0x{a:x}", f"0x{s:x}"] for a, s in regions]
    return {
        "fdt_structurally_valid": True,
        "memory_node_present": bool(memory),
        "memory_ranges": encode(memory),
        "memreserve_ranges": encode(reservations),
        "reserved_memory_ranges": encode(reserved),
        "unresolved_reserved_nodes": unresolved,
        "warnings": warnings,
        "boot_approved": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fdt", type=Path, help="Private local FDT; never upload")
    args = parser.parse_args()
    try:
        result = analyze_fdt(args.fdt.read_bytes())
    except (ValueError, OSError) as exc:
        parser.exit(2, f"NO-GO: {exc}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
