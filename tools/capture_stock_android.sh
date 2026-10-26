#!/system/bin/sh
# PRIVATE rooted Android capture. Reads only active boot partition and running FDT.
# Writes ONLY inside the explicitly selected removable USB path. NEVER boots/flashes.
set -eu
umask 077
if [ "$#" -ne 1 ]; then
    echo "Uso: su -c 'sh capture_stock_android.sh /storage/USB-ID/HY310X-PRIVATE'" >&2
    exit 2
fi
TARGET="$1"
case "$TARGET" in
    /storage/emulated/*|/storage/self/*|/sdcard/*)
        echo "ERRO: armazenamento Android interno recusado" >&2
        exit 2 ;;
    /storage/*/*|/mnt/media_rw/*/*) ;;
    *) echo "ERRO: escolha pasta no pendrive removivel /storage/USB-ID/Pasta" >&2; exit 2 ;;
esac
SLOT="$(getprop ro.boot.slot_suffix 2>/dev/null)"
case "$SLOT" in _a|_b) ;; *) echo "ERRO: slot desconhecido" >&2; exit 2 ;; esac
BOOT="/dev/block/by-name/boot$SLOT"
[ -b "$BOOT" ] || { echo "ERRO: particao ativa nao encontrada" >&2; exit 2; }
[ -r /sys/firmware/fdt ] || { echo "ERRO: /sys/firmware/fdt nao legivel" >&2; exit 2; }
[ -d "$(dirname "$TARGET")" ] || { echo "ERRO: USB nao montado" >&2; exit 2; }
[ ! -e "$TARGET" ] || { echo "ERRO: pasta ja existe; nao sobrescrever" >&2; exit 2; }
mkdir "$TARGET"
echo "Capturando copia PRIVADA em pendrive, leitura de $BOOT e FDT..."
dd if="$BOOT" of="$TARGET/boot-active.img" bs=1048576 2>/dev/null
cat /sys/firmware/fdt > "$TARGET/stock.fdt"
{
  echo "HY310X PRIVATE. NAO PUBLICAR NO GITHUB."
  echo "Slot ativo: $SLOT"
  sha256sum "$TARGET/boot-active.img" "$TARGET/stock.fdt"
} > "$TARGET/CHECKSUMS-PRIVATE.txt"
echo "Captura concluida. NENHUMA particao alterada. NENHUM Kexec."
