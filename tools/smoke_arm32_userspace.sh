#!/usr/bin/env bash
# QEMU linux-user does not emulate H713, drivers, PSCI, or the kexec handoff.
# These checks prove only that the BusyBox and kexec ARM32 executables can start.
set -Eeuo pipefail
BUILD="${1:-.build}"
BUSYBOX="$BUILD/initramfs-root/bin/busybox"
KEXEC="$BUILD/out/kexec"
command -v qemu-arm-static >/dev/null || { echo "qemu-arm-static absent" >&2; exit 1; }
for f in "$BUSYBOX" "$KEXEC"; do
  test -s "$f" || { echo "Missing ARM32 executable: $f" >&2; exit 1; }
  file "$f"
done
echo "[smoke] BusyBox ARM32 launches under userspace emulation"
qemu-arm-static "$BUSYBOX" --help >/dev/null
out="$(qemu-arm-static "$BUSYBOX" sh -c 'printf MAIZON_ARM32_OK')"
test "$out" = MAIZON_ARM32_OK || { echo "Unexpected BusyBox output: $out" >&2; exit 1; }
echo "[smoke] kexec-tools can print usage under QEMU user mode"
qemu-arm-static "$KEXEC" --help >/dev/null
echo "PASS: userspace ARM32 binaries run in QEMU; H713 physical boot NOT validated"
