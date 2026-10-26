# ARM32 Image bruto no Kexec — investigação estática, sem boot

**NO-GO para kexec -l/-e no HY310X.** A imagem OEM do backup privado
foi classificada por heurística como `raw-Image-CANDIDATE`, sem a assinatura
ARM zImage no offset 0x24. Isso **não significa automaticamente** que
kexec-tools v2.0.32 a rejeite.

## O que o código-fonte da versão realmente faz

Fonte de referência, mesma versão fixada no build:

- `horms/kexec-tools`, tag `v2.0.32`,
  `kexec/arch/arm/kexec-arm.c`: tipos de arquivo `uImage` e `zImage`.
- `horms/kexec-tools`, tag `v2.0.32`,
  `kexec/arch/arm/kexec-zImage-arm.c`: a função
  `zImage_arm_probe()` retorna 0 sem verificar a assinatura.
- A função `zImage_arm_load()` aceita o buffer e define
  `extra_size = 0x8000` (TEXT_OFFSET), localiza espaço livre
  com `locate_hole()`, coloca o kernel em `base + extra_size`
  e define esse endereço como entrypoint.
- Sem metadados de zImage, o cálculo do espaço de memória reservado
  ao kernel usa uma aproximação (`len * 5` após incremento de folga).
  A rotina pode também modificar um FDT em `/chosen` e inserir initrd.
- A estrutura de boot Android interpretada nesse loader é a antiga,
  **não** um parser de Android boot header v3/v4. Não passar o boot.img
  OEM v3 inteiro diretamente e presumir que foi interpretado corretamente.

Links de código-fonte:
- https://github.com/horms/kexec-tools/blob/v2.0.32/kexec/arch/arm/kexec-arm.c
- https://github.com/horms/kexec-tools/blob/v2.0.32/kexec/arch/arm/kexec-zImage-arm.c

## Conclusão prática

O loader ARM **pode aceitar** um Image bruto, mas a aceitação do
arquivo não equivale a um boot correto. É necessário verificar o
endereço físico para o qual o kernel OEM foi ligado, relocação,
TEXT_OFFSET, tamanho de BSS, memreserve, PSCI, DTB, caches e estado
dos periféricos. O Image bruto pode ter pressupostos diferentes de
um zImage comprimido. Não converter o arquivo adicionando uma magic
falsa e não fazer tentativa cega no dispositivo.

A ferramenta `tools/inspect_android_boot.py` apenas classifica e
extrai localmente o payload e o FDT; a ferramenta
`tools/analyze_fdt.py` valida estruturas e memória reservada.
Nenhuma delas habilita boot ou grava partições.

**Status:** build/QEMU userspace confirmado; handoff ARM32 e
recuperação física do HY310X não validados.
