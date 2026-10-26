#!/usr/bin/env python3
"""Deterministic CPIO newc initramfs with /dev/console and /dev/null.

Linux can attempt opening /dev/console BEFORE executing /init.
Ordinary cpio packing on a non-root CI runner would omit these character
devices; generate their device metadata without requiring mknod/root.
No operations on host /dev, mounted filesystems or device partitions.
"""
import argparse
import gzip
from pathlib import Path
import stat


def pad4(raw):
    return raw + b"\0" * (-len(raw) % 4)


def record(name, mode, payload, ino, rdevmajor=0, rdevminor=0):
    filename = name.encode("utf-8") + b"\0"
    fields = (
        ino, mode, 0, 0, 2 if stat.S_ISDIR(mode) else 1, 0,
        len(payload), 0, 0, rdevmajor, rdevminor, len(filename), 0,
    )
    header = b"070701" + b"".join(f"{value:08x}".encode("ascii") for value in fields)
    assert len(header) == 110
    return header + filename + b"\0" * (-(110 + len(filename)) % 4) + pad4(payload)


SPECIAL = {
    "dev/console": (5, 1, 0o600),
    "dev/null": (1, 3, 0o666),
}


def build_archive(root: Path):
    if not root.is_dir() or not (root / "init").is_file() or not (root / "bin/busybox").is_file():
        raise ValueError("Missing rootfs, /init or /bin/busybox")
    entries = [(".", root)] + [
        ("./" + path.relative_to(root).as_posix(), path)
        for path in root.rglob("*")
    ]
    entries.sort(key=lambda pair: pair[0])
    seen = set()
    result = bytearray()
    ino = 1
    for name, path in entries:
        relative = name.removeprefix("./")
        if relative in SPECIAL:
            raise ValueError("Do not create special device nodes on CI host: " + relative)
        if path.is_symlink():
            target = path.readlink().as_posix()
            if target.startswith("/") or ".." in Path(target).parts:
                raise ValueError("Unsafe initramfs symlink target: " + name)
            mode, payload = stat.S_IFLNK | 0o777, target.encode("utf-8")
        elif path.is_dir():
            mode, payload = stat.S_IFDIR | (path.stat().st_mode & 0o777), b""
        elif path.is_file():
            mode, payload = stat.S_IFREG | (path.stat().st_mode & 0o777), path.read_bytes()
        else:
            raise ValueError("Unsupported initramfs host entry: " + name)
        if relative in seen:
            raise ValueError("Duplicate initramfs file")
        seen.add(relative)
        result.extend(record(name, mode, payload, ino))
        ino += 1
    if "dev" not in seen:
        raise ValueError("/dev directory required")
    for name, (major, minor, perms) in sorted(SPECIAL.items()):
        result.extend(record("./" + name, stat.S_IFCHR | perms, b"", ino, major, minor))
        ino += 1
    result.extend(record("TRAILER!!!", 0, b"", ino))
    result.extend(b"\0" * (-len(result) % 512))
    return bytes(result)


def make_initramfs(root: Path, output: Path):
    raw = build_archive(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(gzip.compress(raw, compresslevel=9, mtime=0))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    make_initramfs(args.root, args.output)
    print("Initramfs generated with early console/null devices (NO-GO for physical boot)")


if __name__ == "__main__":
    main()
