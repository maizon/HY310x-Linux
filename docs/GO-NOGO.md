# Critérios de avanço: não confundir compilação com boot

**Status atual: NO-GO para `kexec -l` e `kexec -e`.**

O objetivo do laboratório é gerar binários verificáveis sem alterar a eMMC. O comando `kexec -l` instala segmentos em memória de kernel; **não é um teste puramente read-only**, embora não execute o salto. O comando `kexec -e` abandona Android, pode deixar a tela preta, travar o SoC ou corromper dados ainda pendentes de escrita.

## Etapas

| Fase | Critério | Estado |
|---|---|---|
| A. Inventário | Processador, kernel, kexec e memória reservada lidos | OK (proprietário) |
| B. Build | Kernel ARM32, BusyBox initramfs, utilitário ARMv7 estático | Pendente de CI verde |
| C. Auditoria DTB | DTB específico do HY310X com pinos, fan, clocks e reservas revisados | **Não** |
| D. Observabilidade sem UART | Logger USB FAT32/exFAT de /init (não registra falhas anteriores) e retorno testável | **Parcial: código não validado em hardware** |
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

O initramfs usa `/dev/console` e `ttyS0`, caso haja porta UART habilitada. **Sem UART**, procura exclusivamente discos **USB** em `/sys/block/sd*`, verifica o arquivo `MAIZON.OK` no FAT32/exFAT e, se conseguir, escreve `MAIZON/KEXEC.LOG` no próprio pendrive. A opção `MAIZON.RBT` autoriza tentativa de reinicialização **somente após salvar e desmontar o USB**; se falhar, é necessário desligar fisicamente. O novo kernel **não possui driver MMC/eMMC no kit mínimo**, e o initramfs não monta partições internas. Sem inicialização do USB, não há relatório. Não existe log do que ocorrer antes de chegar ao `/init`, e tela preta não prova sucesso ou falha. Consulte `docs/USB-DIAGNOSTICO.md`.

## Como obter evidência no futuro

Inspecionar e comparar o Device Tree original `/sys/firmware/fdt` *localmente* com um DTS proposto, sem publicar segredos. Validar comando kernel, drivers de fan e USB, disponibilidade real do pendrive durante o handoff e recuperação física antes de habilitar o boot. USB log não substitui UART para falhas antes do /init.

Não há percentual de sucesso medido no HY310X.
