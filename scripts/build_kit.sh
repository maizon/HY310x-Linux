#!/usr/bin/env bash
# Experimental toolchain-only build. Never interacts with /dev/block or reboots a device.
set -Eeuo pipefail
export LC_ALL=C

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKDIR="${WORKDIR:-$ROOT/.build}"
OUT="$WORKDIR/out"
SOURCES="$WORKDIR/src"
JOBS="${JOBS:-2}"
CC_PREFIX="${CC_PREFIX:-arm-linux-gnueabi-}"
CSTENGER_COMMIT="bcf1b2c694302a8723b66e899207cb95e32de9ca"
KERNEL_VERSION="6.16.7"
BUSYBOX_VERSION="1.36.1"
KEXEC_VERSION="2.0.32"

mkdir -p "$OUT" "$SOURCES"
for tool in curl tar patch git make python3 cpio gzip cpp "${CC_PREFIX}gcc" "${CC_PREFIX}readelf"; do
    command -v "$tool" >/dev/null || { echo "Falta ferramenta: $tool" >&2; exit 1; }
done
fetch() {
    local url="$1" dest="$2"
    if [ ! -s "$dest" ]; then
        echo "Obtendo fonte: $url"
        curl --fail --location --retry 3 --show-error --silent "$url" -o "$dest"
    fi
}

echo "[1/6] Upstream H713 ARM32: cstenger (commit fixo)"
if [ ! -d "$SOURCES/cstenger/.git" ]; then
    git clone -q https://github.com/cstenger/allwinner-h713-linux.git "$SOURCES/cstenger"
fi
git -C "$SOURCES/cstenger" checkout -q "$CSTENGER_COMMIT"
test "$(git -C "$SOURCES/cstenger" rev-parse HEAD)" = "$CSTENGER_COMMIT"

echo "[2/6] Kernel $KERNEL_VERSION + patches H713"
KERNEL_TAR="$SOURCES/linux-$KERNEL_VERSION.tar.xz"
fetch "https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-$KERNEL_VERSION.tar.xz" "$KERNEL_TAR"
if [ ! -d "$SOURCES/linux-$KERNEL_VERSION" ]; then
    tar -xJf "$KERNEL_TAR" -C "$SOURCES"
fi
KERNEL="$SOURCES/linux-$KERNEL_VERSION"
if [ ! -f "$KERNEL/.maizon-patched" ]; then
    while IFS= read -r name; do
        [ -n "$name" ] || continue
        echo "  patch $name"
        (cd "$KERNEL" && patch --batch --forward -p1 < "$SOURCES/cstenger/patches/$name")
    done < "$SOURCES/cstenger/patches/series"
    touch "$KERNEL/.maizon-patched"
fi
cp "$SOURCES/cstenger/config/hy310_defconfig" "$KERNEL/arch/arm/configs/maizon_hy310x_lab_defconfig"
make -s -C "$KERNEL" ARCH=arm CROSS_COMPILE="$CC_PREFIX" maizon_hy310x_lab_defconfig
# Disable board-specific fan manager and focus motor from UNVERIFIED reference DTS.
# These options stay disabled until the OEM HY310X FDT is reviewed.
"$KERNEL/scripts/config" --file "$KERNEL/.config" \
    -e BLK_DEV_INITRD -e RD_GZIP -e DEVTMPFS -e DEVTMPFS_MOUNT \
    -e SERIAL_8250 -e SERIAL_8250_CONSOLE \
    -e USB -e USB_EHCI_HCD -e USB_EHCI_HCD_PLATFORM \
    -e USB_OHCI_HCD -e USB_OHCI_HCD_PLATFORM -e USB_STORAGE \
    -e PHY_SUN4I_USB -e SCSI -e BLK_DEV_SD \
    -e FAT_FS -e VFAT_FS -e EXFAT_FS \
    -e NLS_CODEPAGE_437 -e NLS_ISO8859_1 \
    -d MMC -d HY310_BOARD_MGR -d HY310_KEYSTONE_MOTOR
make -s -C "$KERNEL" ARCH=arm CROSS_COMPILE="$CC_PREFIX" olddefconfig
# USB read/write reporting must be built into the kernel, not modules: initramfs loads no .ko.
for setting in CONFIG_USB_STORAGE CONFIG_USB_EHCI_HCD CONFIG_USB_OHCI_HCD CONFIG_PHY_SUN4I_USB CONFIG_SCSI CONFIG_BLK_DEV_SD CONFIG_VFAT_FS CONFIG_EXFAT_FS; do
    grep -qx "$setting=y" "$KERNEL/.config" || { echo "ERRO: $setting precisa estar built-in" >&2; exit 1; }
done
grep -qx '# CONFIG_MMC is not set' "$KERNEL/.config" || { echo "ERRO: eMMC nao deve ser exposta no primeiro teste" >&2; exit 1; }
make -C "$KERNEL" ARCH=arm CROSS_COMPILE="$CC_PREFIX" -j"$JOBS" zImage scripts
cp "$KERNEL/arch/arm/boot/zImage" "$OUT/zImage"

echo "[3/6] DTB de referencia - NAO APROVADO PARA HY310X"
DTS="$WORKDIR/hy310x-candidate.dts"
python3 - "$SOURCES/cstenger/dts/sun50i-h713-hy310.dts" "$DTS" <<'PY'
import pathlib, re, sys
source = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
# Kernel + CPIO only; no use of external root filesystem.
cmdline = "console=ttyS0,115200 earlycon loglevel=7 rdinit=/init maxcpus=1 panic=15 clk_ignore_unused pd_ignore_unused cma=24M"
source, n = re.subn(r'bootargs\s*=\s*"[^"]*";', f'bootargs = "{cmdline}";', source)
assert n == 1, "DTS original diferente do esperado"
source = source.replace('model = "HY310 Projector H713";',
                        'model = "Maizon HY310X H713 - CANDIDATE NOT VERIFIED";')
# Do not guess GPIO/NTC/PWM values for the HY310X. The reference DTS is a NO-GO.
pathlib.Path(sys.argv[2]).write_text(source, encoding="utf-8")
PY
cpp -nostdinc -I "$KERNEL/include" -I "$KERNEL/scripts/dtc/include-prefixes" \
    -undef -D__DTS__ -x assembler-with-cpp "$DTS" | \
    "$KERNEL/scripts/dtc/dtc" -I dts -O dtb -W no-unit_address_vs_reg \
       -o "$OUT/hy310x-candidate.dtb" -

echo "[4/6] BusyBox estatico ARM32 e initramfs de diagnostico USB FAT32/exFAT"
BUSY_TAR="$SOURCES/busybox-$BUSYBOX_VERSION.tar.bz2"
fetch "https://busybox.net/downloads/busybox-$BUSYBOX_VERSION.tar.bz2" "$BUSY_TAR"
if [ ! -d "$SOURCES/busybox-$BUSYBOX_VERSION" ]; then
    tar -xjf "$BUSY_TAR" -C "$SOURCES"
fi
BUSY="$SOURCES/busybox-$BUSYBOX_VERSION"
make -s -C "$BUSY" ARCH=arm CROSS_COMPILE="$CC_PREFIX" defconfig
# For Android host compatibility BusyBox must be static (no Android glibc loader).
sed -i 's/^# CONFIG_STATIC is not set/CONFIG_STATIC=y/' "$BUSY/.config"
grep -q '^CONFIG_STATIC=y$' "$BUSY/.config" || { echo "CONFIG_STATIC ausente"; exit 1; }
make -s -C "$BUSY" ARCH=arm CROSS_COMPILE="$CC_PREFIX" oldconfig
make -C "$BUSY" ARCH=arm CROSS_COMPILE="$CC_PREFIX" -j"$JOBS"
CPIO_ROOT="$WORKDIR/initramfs-root"
rm -rf "$CPIO_ROOT"
mkdir -p "$CPIO_ROOT/bin" "$CPIO_ROOT/dev" "$CPIO_ROOT/proc" "$CPIO_ROOT/sys" "$CPIO_ROOT/run" "$CPIO_ROOT/tmp"
cp "$BUSY/busybox" "$CPIO_ROOT/bin/busybox"
for app in sh mount umount mkdir uname cat sleep echo ls dmesg sync readlink head tail reboot; do
    ln -s busybox "$CPIO_ROOT/bin/$app"
done
cp "$ROOT/initramfs/init" "$CPIO_ROOT/init"
chmod 0755 "$CPIO_ROOT/init" "$CPIO_ROOT/bin/busybox"
(cd "$CPIO_ROOT" && find . -print0 | cpio --quiet --null -o -H newc --owner=0:0) | gzip -9 > "$OUT/initramfs.cpio.gz"

echo "[5/6] kexec-tools estatico ARM32"
KEXEC_TAR="$SOURCES/kexec-tools-$KEXEC_VERSION.tar.xz"
fetch "https://www.kernel.org/pub/linux/utils/kernel/kexec/kexec-tools-$KEXEC_VERSION.tar.xz" "$KEXEC_TAR"
if [ ! -d "$SOURCES/kexec-tools-$KEXEC_VERSION" ]; then
    tar -xJf "$KEXEC_TAR" -C "$SOURCES"
fi
KEXEC="$SOURCES/kexec-tools-$KEXEC_VERSION"
(
    cd "$KEXEC"
    ./configure --host=arm-linux-gnueabi CC="${CC_PREFIX}gcc" LDFLAGS="-static"
    make -j"$JOBS"
)
KEXEC_EXE=""
for candidate in "$KEXEC/build/sbin/kexec" "$KEXEC/kexec/kexec"; do
    if [ -f "$candidate" ]; then KEXEC_EXE="$candidate"; break; fi
done
[ -n "$KEXEC_EXE" ] || { echo "Nao encontrado binario kexec ARM32"; exit 1; }
cp "$KEXEC_EXE" "$OUT/kexec"
chmod 0755 "$OUT/kexec"
if "${CC_PREFIX}readelf" -l "$OUT/kexec" | grep -q INTERP; then
    echo "ERRO: kexec tem carregador dinamico, incompatibilidade com Android"
    exit 1
fi

echo "[6/6] Manifesto e marcador de bloqueio"
cat > "$OUT/NO-GO.txt" <<EOF
MAIZON HY310X ARM32 KEXEC PROTOTIPO
NÃO EXECUTAR NO PROJETOR.
SEM DTB VERIFICADO PARA A PLACA.
SEM TESTE DE KEXEC/HANDOFF E SEM RECUPERAÇÃO INDEPENDENTE.
O DTS fornecido é baseado no HY310 do cstenger; GPIO fan/NTC/PWM divergem do HY310X.
Somente compilação e validação estática.
Kernel Linux $KERNEL_VERSION; cstenger $CSTENGER_COMMIT
BusyBox $BUSYBOX_VERSION; kexec-tools $KEXEC_VERSION
EOF
(cd "$OUT" && sha256sum zImage hy310x-candidate.dtb initramfs.cpio.gz kexec > manifest.sha256)
python3 "$ROOT/tools/validate_kit.py" "$OUT"
echo "Resultado: $OUT (NO-GO para boot)"
