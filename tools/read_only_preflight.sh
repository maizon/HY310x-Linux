#!/system/bin/sh
# HY310X only: inventário sem gravação nem kexec. Pode executar via 'sh' no Android.
echo "=== MAIZON HY310X KEXEC | READ-ONLY ==="
echo "Data: $(date 2>/dev/null)"
echo "Kernel: $(uname -a)"
echo "Android ABI: $(getprop ro.product.cpu.abi 2>/dev/null)"
echo "Slot: $(getprop ro.boot.slot_suffix 2>/dev/null)"
echo "UID: $(id -u 2>/dev/null)"
if [ -r /proc/sys/kernel/kexec_load_disabled ]; then
  echo "kexec_load_disabled: $(cat /proc/sys/kernel/kexec_load_disabled)"
else
  echo "kexec_load_disabled: indisponivel"
fi
if [ -r /proc/config.gz ]; then
  echo "CONFIG_* (kernel):"
  zcat /proc/config.gz 2>/dev/null | grep -E '^(CONFIG_KEXEC|CONFIG_KEXEC_CORE|CONFIG_ARM_PSCI|CONFIG_HOTPLUG_CPU|CONFIG_AUTO_ZRELADDR|CONFIG_CRASH_DUMP)=' || :
fi
echo "CPU online: $(cat /sys/devices/system/cpu/online 2>/dev/null)"
if [ -r /proc/device-tree/model ]; then
  printf 'DT model: '
  tr '\000' ' ' < /proc/device-tree/model
  echo
fi
if [ -r /proc/device-tree/compatible ]; then
  printf 'DT compatible: '
  tr '\000' ' ' < /proc/device-tree/compatible
  echo
fi
echo "Memoria:"
grep -E '^(MemTotal|MemAvailable|CmaTotal|CmaFree):' /proc/meminfo 2>/dev/null || :
echo "DT reserved-memory (nomes):"
ls /proc/device-tree/reserved-memory 2>/dev/null || :
echo "UART (nomes, nao abre):"
ls /dev/ttyS* 2>/dev/null || :
echo "=== RESULTADO: diagnostico apenas; NENHUM BOOT / NENHUMA GRAVACAO ==="
