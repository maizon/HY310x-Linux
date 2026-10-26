# Maizon HY310X Linux · ARM32 Kexec Lab

[![CI](https://github.com/maizon/HY310x-Linux/actions/workflows/ci.yml/badge.svg)](https://github.com/maizon/HY310x-Linux/actions/workflows/ci.yml)

**Estado: investigação / NÃO PRONTO PARA BOOT.** O objetivo imediato é construir um **kernel ARM32 H713 + initramfs BusyBox + kexec-tools ARMv7 estático** para estudar um shell Linux mínimo por Kexec, **sem substituir Android, U-Boot, BOOT0, env, boot_a ou partições internas**.

> **NÃO execute `kexec -e`, `reboot -f`, `dd of=/dev/block/...`, `sunxi_flash write` nem scripts de flash deste repositório.** Nenhum Kexec no HY310X foi validado; o kernel e o DTB produzidos são protótipos e podem travar o SoC. Um retorno ao Android após queda de energia é esperado somente se o boot original e a eMMC permanecerem intactos: **não existe recuperação autônoma testada**. Não confundir `kexec -l` com um teste inofensivo de hardware.

## Evidência da unidade estudada

| Item | Origem / resultado |
|---|---|
| SoC | Allwinner **H713 / sun50iw12p1**, compatível `allwinner,tv303` |
| Firmware | Android 11, `Projector.20251013.1058`, Magisk com `su` |
| Kernel ativo | **Linux 5.4.99 ARM32** (config `CONFIG_AUTO_ZRELADDR=y`, ABI `armeabi-v7a`) |
| Kexec | `CONFIG_KEXEC=y`, `CONFIG_KEXEC_CORE=y`, `kexec_load_disabled=0` |
| CPU | 4× Cortex-A53; PSCI 1.0 por SMC; root privilegiado confirmado |
| RAM | ~960888 kB; BL31, OP-TEE, cpu_comm, MIPS e framebuf reservados |
| Placa | HY310X: diferenças em fan/NTC/PWM/GPIO com o HY310 do projeto base |
| Ponto pendente | Nenhuma execução `kexec -l` ou `kexec -e` e nenhum boot secundário testados |
| Backup | 21 imagens selecionadas, **não** dump completo da eMMC; restauração externa não validada |

Fonte primária: [laboratório Maizon](https://github.com/maizon/Magcubic-HY310X-and-H713-H723-Root-/blob/main/docs/HY310X-LAB-NOTES.md), [inventário sanitizado](https://github.com/maizon/Magcubic-HY310X-and-H713-H723-Root-/blob/main/reference/h713-hy310x-20251024.json) e registros locais do proprietário.

## Arquitetura proposta

```text
Android 11 ARM32 original (eMMC; NÃO modificar)
  └─ kexec-tools ARMv7 estático [carregamento exige validação]
       ├─ zImage ARM32 (port H713 baseado em cstenger)
       ├─ DTB experimental (NÃO aprovado para HY310X)
       └─ initramfs BusyBox estático
            └─ /init -> serial console ttyS0 / shell mínimo
```

Não há Android nem vídeo depois de um Kexec bem-sucedido: o novo kernel toma controle, e ADB perde conexão. O proprietário **não tem UART**: o initramfs agora inclui **diagnóstico opt-in por pendrive FAT32/exFAT** em `MAIZON/KEXEC.LOG`, **somente se /init e o USB funcionarem**. Não há log para falhas antes de /init. **A existência do logger NÃO autoriza o teste de boot**; veja [docs/USB-DIAGNOSTICO.md](docs/USB-DIAGNOSTICO.md) e [docs/GO-NOGO.md](docs/GO-NOGO.md).

## Conteúdo do projeto

- `docs/HARDWARE.md`: matriz HY310X × HY310, proveniência e bloqueios reais.
- `docs/GO-NOGO.md`: regras para impedir execução prematura.
- `tools/read_only_preflight.sh`: pesquisa somente leitura no Android/root.
- `tools/validate_kit.py`: checa estrutura zImage, DTB, initramfs, ELF ARM32, hashes.
- `initramfs/init`: initramfs mínimo com tentativa de relatório **somente no pendrive USB** (FAT32/exFAT); não monta eMMC.
- `scripts/build_kit.sh`: tentativa reproduzível de compilação cruzada via ferramentas abertas; não realiza boot.
- `.github/workflows/ci.yml`: testes estáticos sem hardware.
- `.github/workflows/build.yml`: compilação experimental sob acionamento manual.

O alvo inicial é **ARM32**, não ARM64. O port [cstenger/allwinner-h713-linux](https://github.com/cstenger/allwinner-h713-linux) demonstrou Linux ARM32 via U-Boot original no **HY310**, **não via Kexec** no HY310X. O port [well0nez/allwinner-h713-linux](https://github.com/well0nez/allwinner-h713-linux) usa outra cadeia de boot para ARM64; não transplante seu flash/DTB para este aparelho.

## Testes seguros

Em um computador ou GitHub Actions, para auditar o repositório:

```sh
python3 -m unittest discover -s tests -v
sh -n tools/read_only_preflight.sh scripts/build_kit.sh initramfs/init
```

Somente leitura **no Android** (execução não aciona Kexec):

```sh
su -c 'sh /sdcard/Download/read_only_preflight.sh'
```

Não use a imagem experimental em `boot_a`, `boot_b`, `env_a` ou qualquer caminho `/dev/block`.

## Créditos e licenças

Pesquisa de hardware: Maizon. Port H713 ARM32 de referência: **cstenger**, incluindo trabalho de **well0nez**. Port ARM64 e código aberto de inicialização: **well0nez**, **cstenger** e respectivos autores. Código incorporado de terceiros deve preservar suas licenças e avisos; este repositório não inclui `display.bin`, chaves HDCP, imagens de partição nem blobs da unidade.
