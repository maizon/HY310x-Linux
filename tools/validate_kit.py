#!/usr/bin/env python3
"""Validação estática de formato para artefatos ARM32; não valida capacidade de boot."""
import argparse
import gzip
import hashlib
import pathlib
import struct
import sys

ARM_ZIMAGE_MAGIC = 0x016F2818
FDT_MAGIC = b"\xd0\x0d\xfe\xed"
ARM_MACHINE = 40


def fail(message):
    raise ValueError(message)


def validate_zimage(data):
    if len(data) < 0x28:
        fail("zImage curta demais")
    if struct.unpack_from("<I", data, 0x24)[0] != ARM_ZIMAGE_MAGIC:
        fail("zImage: magic ARM32 invalida (offset 0x24)")


def validate_dtb(data):
    if len(data) < 40 or data[:4] != FDT_MAGIC:
        fail("DTB: magic FDT invalida")
    size = struct.unpack_from(">I", data, 4)[0]
    if size < 40 or size > len(data):
        fail("DTB: tamanho incoerente")


def parse_initramfs_newc(data):
    """Parse CPIO metadata only. Never extract untrusted paths to disk."""
    import stat
    cursor, entries, trailer = 0, {}, False
    while cursor + 110 <= len(data):
        if data[cursor:cursor + 6] not in (b"070701", b"070702"):
            fail("initramfs: CPIO newc invalid header")
        header = data[cursor + 6:cursor + 110]
        try:
            fields = [int(header[n:n + 8], 16) for n in range(0, 104, 8)]
        except ValueError:
            fail("initramfs: CPIO header fields invalid")
        mode, length, major, minor, name_length = fields[1], fields[6], fields[9], fields[10], fields[11]
        if not (1 <= name_length <= 4096) or length > 32 * 1024 * 1024:
            fail("initramfs: CPIO entry oversized")
        cursor += 110
        if cursor + name_length > len(data):
            fail("initramfs: CPIO truncated filename")
        name_raw = data[cursor:cursor + name_length]
        if name_raw[-1] != 0 or b"\0" in name_raw[:-1]:
            fail("initramfs: CPIO invalid filename")
        try:
            name = name_raw[:-1].decode("utf-8")
        except UnicodeDecodeError:
            fail("initramfs: CPIO undecodable filename")
        cursor = (cursor + name_length + 3) & ~3
        if cursor + length > len(data):
            fail("initramfs: CPIO truncated file")
        payload = data[cursor:cursor + length]
        cursor = (cursor + length + 3) & ~3
        if name == "TRAILER!!!":
            if length or mode:
                fail("initramfs: malformed CPIO trailer")
            trailer = True
            break
        relative = name.removeprefix("./")
        if not relative or relative.startswith("/") or ".." in pathlib.PurePosixPath(relative).parts:
            fail("initramfs: CPIO unsafe filename")
        if relative in entries:
            fail("initramfs: duplicate entry")
        entries[relative] = (mode, major, minor, payload)
        if len(entries) > 4096:
            fail("initramfs: excessive entries")
    if not trailer or any(data[cursor:]):
        fail("initramfs: missing CPIO trailer or unexpected data")
    return entries


def validate_initramfs(data):
    import io
    import stat
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
            raw = stream.read(32 * 1024 * 1024 + 1)
    except (OSError, EOFError) as exc:
        fail(f"initramfs gzip invalido: {exc}")
    if len(raw) > 32 * 1024 * 1024:
        fail("initramfs: excede 32 MiB descompactado")
    if not raw.startswith((b"070701", b"070702")):
        fail("initramfs: esperado CPIO newc")
    entries = parse_initramfs_newc(raw)
    for name in ("init", "bin/busybox"):
        entry = entries.get(name)
        if not entry or not stat.S_ISREG(entry[0]) or not entry[0] & 0o111:
            fail(f"initramfs: {name} missing executable file")
    shell = entries.get("bin/sh")
    if not shell or not stat.S_ISLNK(shell[0]) or shell[3] != b"busybox":
        fail("initramfs: /bin/sh must point to busybox")
    for name, major, minor in (("dev/console", 5, 1), ("dev/null", 1, 3)):
        entry = entries.get(name)
        if not entry or not stat.S_ISCHR(entry[0]) or entry[1:3] != (major, minor):
            fail(f"initramfs: {name} missing or wrong character device")
    return entries


def validate_kexec_arm32_static(data):
    if len(data) < 52 or data[:4] != b"\x7fELF":
        fail("kexec: ELF invalido")
    if data[4] != 1 or data[5] != 1:
        fail("kexec: precisa de ELF32 little-endian")
    if struct.unpack_from("<H", data, 18)[0] != ARM_MACHINE:
        fail("kexec: arquitetura diferente de ARM32")
    phoff = struct.unpack_from("<I", data, 28)[0]
    phentsize, phnum = struct.unpack_from("<HH", data, 42)
    if phnum > 128 or phoff + phnum * phentsize > len(data):
        fail("kexec: tabela ELF malformada")
    if phnum and phentsize < 32:
        fail("kexec: program header invalido")
    for i in range(phnum):
        if struct.unpack_from("<I", data, phoff + i * phentsize)[0] == 3:
            fail("kexec: PT_INTERP presente; Android nao fornece carregador GNU ARM32")


def check_dir(directory):
    paths = {
        "zImage": validate_zimage,
        "hy310x-candidate.dtb": validate_dtb,
        "initramfs.cpio.gz": validate_initramfs,
        "kexec": validate_kexec_arm32_static,
    }
    digests = {}
    for name, validator in paths.items():
        blob = (directory / name).read_bytes()
        validator(blob)
        digests[name] = hashlib.sha256(blob).hexdigest()
        print(f"OK {name} ({len(blob)} bytes) {digests[name]}")
    flag = directory / "NO-GO.txt"
    if not flag.exists():
        fail("faltou o marcador obrigatorio NO-GO.txt")
    if not (directory / "manifest.sha256").exists():
        fail("manifest.sha256 ausente")
    manifest = (directory / "manifest.sha256").read_text(encoding="utf-8")
    for name, digest in digests.items():
        if f"{digest}  {name}" not in manifest.splitlines():
            fail(f"sha256 invalido ou ausente para {name}")
    print("FORMATO OK — COMPATIBILIDADE DO HY310X E BOOT NAO TESTADOS")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=pathlib.Path)
    args = parser.parse_args()
    try:
        check_dir(args.directory)
    except (OSError, ValueError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
