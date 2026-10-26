# Critérios de avanço: não confundir compilação com boot

**Status atual: NO-GO para `kexec -l` e `kexec -e`.**

O objetivo do laboratório é gerar binários verificáveis sem alterar a eMMC. O comando `kexec -l` instala segmentos em memória de kernel; **não é um teste puramente read-only**, embora não execute o salto. O comando `kexec -e` abandona Android, pode deixar a tela preta, travar o SoC ou corromper dados ainda pendentes de escrita.

## Etapas

| Fase | Critério | Estado |
|---|---|---|
| A. Inventário | Processador, kernel, kexec e memória reservada lidos | OK (proprietário) |
| B. Build | Kernel ARM32, BusyBox initramfs, utilitário ARMv7 estático | Pendente de CI verde |
| C. Auditoria DTB | DTB específico do HY310X com pinos, fan, clocks e reservas revisados | **Não** |
| D. Log UART | Caminho físico independente de Android e vídeo | **Não** |
| E. Recuperação | Mecanismo prático provado de recuperação quando Android não responde | **Não** |
| F. Ensaio carga | Teste controlado de `kexec -l` em dispositivo, sem salto | **Não** |
| G. Handoff | Somente após A-F, ensaio `kexec -e` supervisionado | **Não** |

Um arquivo que passou `validate_kit.py` só passou checagem de **formato**, NÃO uma validação de drivers, entry point, layout RAM, PSCI ou suporte do Kexec da OEM.

## Proibições do projeto

- Nenhum workflow ou shell script executa `kexec -l`, `kexec -e`, `reboot` no projetor, `dd of=/dev/block` ou `sunxi_flash write`.
- Não adicionar atualização OTA/auto_update USB por conta própria: scripts `auto_update.txt` podem gravar firmware inteiro.
- Não usar DTB do HY310 como se fosse HY310X: alterações em fan/NTC/PWM podem ser perigosas.
- Não assumir que slot B é fallback real sem ensaio. O backup de 21 imagens não cobre `super` nem eMMC completa.
- Não publicar `boot.img`, `private`, `metadata`, `env`, `misc`, HDCP, números de série, MACs ou arquivos de firmware OEM.

## Observabilidade mínima do shell

O initramfs usa `/dev/console` e `ttyS0`, caso haja porta UART habilitada. Não dispõe de compositor, ADB, Wi-Fi, nem grava status na eMMC. Com apenas projeção e sem UART, o kernel pode iniciar **sem qualquer indicação visível**. Uma tela preta não é prova de sucesso ou falha.

## Como obter evidência no futuro

Inspecionar e comparar o Device Tree original `/sys/firmware/fdt` *localmente* com um DTS proposto, sem publicar segredos. Validar comando kernel, drivers de fan e USB e a recuperação física antes de habilitar o handoff.

Não há percentual de sucesso medido no HY310X.
