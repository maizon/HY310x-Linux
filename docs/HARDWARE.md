# Evidências do HY310X e diferenças com o HY310

**Alvo validado de inventário, NÃO de boot.** Os dados abaixo vieram dos comandos `su -c` executados pelo proprietário e do inventário sanitizado do [repositório de pesquisa Maizon](https://github.com/maizon/Magcubic-HY310X-and-H713-H723-Root-). Não representam validação de placas com o mesmo nome comercial.

| Campo | HY310X (unidade) | DTS de referência cstenger HY310 | Impacto |
|---|---|---|---|
| SoC | H713 / sun50iw12p1 | H713 | Base CPU compatível |
| Kernel em execução | 5.4.99 **ARM32** | 6.16.7 **ARM32** | Kexec entre ARM32 é plausível; não provado |
| Root | Magisk 30.7 | Linux direto | Capacidades elevadas observadas |
| ABI Android | armeabi-v7a | Debian armhf | Não implica kernel ARM64 |
| Kexec | compilado/habilitado | Não demonstrado via Kexec | **Bloqueio** |
| PSCI | 1.0 SMC | PSCI 0.2 no DTS | Confirmar compatibilidade, não usar SMC arbitrários |
| Memória | ~939 MiB disponível ao kernel | 1 GiB DDR3 físico | Conservar reservas |
| MIPS/vídeo | pré-inicializado pelo U-Boot | pré-inicializado pelo U-Boot | Kexec não reinicia firmware MIPS |
| Fan tach | PH13 | PH17 | **Conflito físico** |
| Fan power | PB6 (hipótese do DT stock, pinagem não medida) | PB5 | **Conflito físico** |
| PWM | IDs 3 | ID 0 | **Conflito** |
| NTC | ntc_num=1 | ntc_num=0 | **Conflito** |
| Limite térmico | warn 64 °C, poweroff 70 °C | diferente | Necessita validação |
| Display | ProjectID 0x30 (1080p60) | HY310 0x30 | Coincidência não garante painel/driver |
| eMMC | 8 GiB, partições A/B, slot _a | HY310 variação | Não gravar |

A saída do inventário read-only mostrou: `CONFIG_KEXEC=y`, `CONFIG_KEXEC_CORE=y`, `CONFIG_HOTPLUG_CPU=y`, `CONFIG_ARM_PSCI=y`, `kexec_load_disabled=0`, `CapEff: 0000003fffffffff`. Mostrou também a lista `bl31`, `optee`, `cpu_comm`, `decd`, `framebuf`, `mipsloader` das regiões reservadas.

**A referência cstenger não é um Device Tree pronto para a placa Maizon.** A compilação experimental do kernel baseada nessa referência precisa ser confrontada com o FDT original, especialmente fan/pinmux/power e reservas. Não corrigir GPIOs por suposição e **não fazer boot antes de comprovar a pinagem e recuperação**.

Fontes:
- [Inventário Maizon](https://github.com/maizon/Magcubic-HY310X-and-H713-H723-Root-/blob/main/reference/h713-hy310x-20251024.json)
- [Recuperação e lacunas de backup](https://github.com/maizon/Magcubic-HY310X-and-H713-H723-Root-/blob/main/docs/RECOVERY.md)
- [DTS de referência, cstenger](https://github.com/cstenger/allwinner-h713-linux/blob/master/dts/sun50i-h713-hy310.dts)
- [Port ARM64 (cadeia personalizada, não Kexec)](https://github.com/well0nez/allwinner-h713-linux)
