#!/usr/bin/env python3
"""Offline private inspection of Android 11 boot v3/v4 and original FDT.

No device interaction, boot, flash, or kexec. No OEM files shipped in GitHub.
An extracted zImage/DTB is NOT automatically compatible with kexec.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
from analyze_fdt import analyze_fdt

PAGE = 4096
ZIMAGE_MAGIC = 0x016F2818
MAX_KERNEL = 128 * 1024 * 1024
MAX_FDT = 16 * 1024 * 1024


def parse_boot_header(header, image_size):
    if len(header) != PAGE or header[:8] != b"ANDROID!":
        raise ValueError("Android boot magic/header ausente")
    kernel_size, ramdisk_size, _, header_size = struct.unpack_from("<4I", header, 8)
    version = struct.unpack_from("<I", header, 40)[0]
    if version not in (3, 4) or not (1580 <= header_size <= 4096):
        raise ValueError(f"Android boot version/header inesperado: {version}/{header_size}")
    if not (64 <= kernel_size <= MAX_KERNEL):
        raise ValueError("Tamanho de kernel invalido")
    if PAGE + kernel_size > image_size or ramdisk_size > image_size:
        raise ValueError("Imagem truncada")
    return {"version": version, "kernel_size": kernel_size, "ramdisk_size": ramdisk_size,
            "kernel_offset": PAGE, "header_size": header_size}


def classify_arm32_kernel(data):
    """Classify format, NOT kexec-loadability. ARM Image candidate is not a zImage."""
    if len(data) >= 0x28 and struct.unpack_from("<I", data, 0x24)[0] == ZIMAGE_MAGIC:
        return "zImage", "stock-zImage"
    # A raw ARM32 Image normally enters with an ARM-mode unconditional
    # B/BL instruction; this is only a heuristic, not a provenance proof.
    if len(data) >= PAGE and (struct.unpack_from("<I", data, 0)[0] & 0xFE000000) == 0xEA000000:
        return "raw-Image-CANDIDATE", "stock-Image"
    raise ValueError("Payload OEM desconhecido; nem zImage nem candidato Image ARM32. Investigue offline.")


def parse_fdt_header(data):
    if not (40 <= len(data) <= MAX_FDT) or data[:4] != b"\xd0\x0d\xfe\xed":
        raise ValueError("FDT original invalido")
    total, off_struct, off_strings, off_rsvmap, version, compat, _, size_strings, size_struct = struct.unpack_from(
        ">9I", data, 4
    )
    if total < 40 or total > len(data) or version < 16 or compat > 17:
        raise ValueError("Cabecalho FDT incoerente")
    if not (40 <= off_struct < total and 40 <= off_strings < total and 40 <= off_rsvmap < total):
        raise ValueError("Offsets do FDT invalidos")
    if off_struct + size_struct > total or off_strings + size_strings > total:
        raise ValueError("FDT estrutura/strings fora do arquivo")
    return {"bytes": total, "version": version, "memory_map_reviewed": False}


def prepare(boot: Path, fdt: Path, output: Path):
    if not boot.is_file() or not fdt.is_file():
        raise ValueError("Forneca copia LOCAL do boot original e do /sys/firmware/fdt")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("Pasta de destino deve estar vazia")
    if not 4096 <= boot.stat().st_size <= 256 * 1024 * 1024:
        raise ValueError("Tamanho boot fora dos limites")
    with boot.open("rb") as inp:
        header = parse_boot_header(inp.read(PAGE), boot.stat().st_size)
        inp.seek(header["kernel_offset"])
        kernel = inp.read(header["kernel_size"])
        kernel_format, kernel_file = classify_arm32_kernel(kernel)
    raw_fdt = fdt.read_bytes()
    summary_fdt = parse_fdt_header(raw_fdt)
    # OEM FDTs can have vendor-specific structures. Keep private extraction
    # possible, but mark an incomplete/invalid memory audit as explicit NO-GO.
    try:
        fdt_audit = analyze_fdt(raw_fdt)
    except ValueError as exc:
        fdt_audit = {
            "fdt_structurally_valid": False,
            "boot_approved": False,
            "warnings": [f"FDT structural audit incomplete: {exc}"],
        }
    # Avoid accidentally committing proprietary boot/kernel and raw FDT.
    if any((ancestor / ".git").exists() for ancestor in (output, *output.parents)):
        raise ValueError("Destino dentro de checkout Git: use pasta PRIVADA fora do repositorio")
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    output.chmod(0o700)
    result = {
        "status": "NO-GO: formato verificado; sem validacao do boot por kexec",
        "boot": header,
        "kernel_format": kernel_format,
        "warning": (
            "Raw ARM Image is NOT an ARM zImage. kexec-tools v2.0.32 ARM "
            "probe may accept uncompressed bytes without checking magic, "
            "but entry placement, linkage, memory safety and handoff are "
            "UNVERIFIED. Do not load or execute on HY310X."
        ),
        "fdt": summary_fdt,
        "fdt_audit": fdt_audit,
        "sha256": {
            kernel_file: hashlib.sha256(kernel).hexdigest(),
            "stock-original.fdt": hashlib.sha256(raw_fdt).hexdigest(),
        },
        "note": "Arquivos proprietarios locais; nunca publicar no GitHub.",
    }
    for name, raw in (
        (kernel_file, kernel),
        ("stock-original.fdt", raw_fdt),
        ("LOCAL-REPORT.json", (json.dumps(result, indent=2) + "\n").encode("utf-8")),
    ):
        with (output / name).open("xb") as out:
            out.write(raw)
        (output / name).chmod(0o600)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--boot", required=True, type=Path)
    ap.add_argument("--fdt", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    try:
        report = prepare(args.boot, args.fdt, args.output)
    except (OSError, ValueError) as exc:
        print(f"NO-GO: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
