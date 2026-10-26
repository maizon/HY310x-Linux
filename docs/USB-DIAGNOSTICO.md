# Diagnóstico por pendrive FAT32 ou exFAT (SEM UART)

**Estado: implementação experimental, NÃO habilitada para boot real.** Este documento descreve o comportamento pretendido do `initramfs/init` após o novo kernel atingir o `/init`. Não prova suporte USB nem handoff Kexec no HY310X.

## Por que o pendrive?

O proprietário não dispõe de UART. Na troca via Kexec, Android/ADB deixam de funcionar. Uma tela preta não indica se o kernel iniciou. Portanto, o initramfs foi adaptado para escrever **apenas em um disco USB**, quando explicitamente autorizado por marcador. Isto **não** captura travamentos de Kexec, boot inicial, clock, Device Tree ou drivers ocorridos **antes** de `/init`.

## Preparar um pendrive

1. Use uma partição **FAT32 (preferencial)**; também há suporte de compilação para **exFAT**, sujeito à inicialização do driver.
2. Na raiz do pendrive, crie um **arquivo vazio** com nome exato `MAIZON.OK` (não pasta).
3. Opcional: crie também `MAIZON.RBT` para **autorizar uma tentativa de reboot** somente depois da gravação completa e desmontagem do relatório. A reinicialização é tentativa, pode falhar ou travar; **não** substitui recuperação física.
4. Não use o pendrive com dados insubstituíveis. Faça backup dos arquivos antes.
5. Quando houver um teste de boot explicitamente aprovado (atualmente NÃO aprovado), o pendrive precisará estar conectado **antes** da troca de kernel.

Se `/init` alcançar o controlador USB, identificar um disco realmente conectado por USB, montar a partição com sucesso, encontrar `MAIZON.OK` e conseguir gravar, criará/substituirá:

```text
<pendrive>/
  MAIZON.OK       # arquivo vazio, habilita escrita do relatório
  MAIZON.RBT      # opcional: tentar reboot APÓS salvar
  MAIZON/
    KEXEC.LOG     # informações do kernel (sobrescrito a cada teste)
```

O arquivo conterá `/init REACHED`, kernel, argumentos de boot, memória, núcleos e últimas mensagens de `dmesg`. Após reinicialização ou desligamento físico, volte ao Android e abra `MAIZON/KEXEC.LOG`.

## Limites cruciais

- Se `KEXEC.LOG` **não aparecer**, não há como distinguir um travamento inicial de uma falha USB, falta do marcador ou incompatibilidade FAT32/exFAT; nenhuma dessas hipóteses prova que o kernel chegou a `/init`.
- O novo kernel experimental desativa `CONFIG_MMC` para **não fornecer acesso à eMMC** no ambiente mínimo; não copia nem monta partições internas.
- O programa verifica a ancestralidade `/sys/block/sd*/device` em USB antes de acessar a partição; outras mídias são ignoradas.
- As opções `MAIZON.OK` e `MAIZON.RBT` não fazem absolutamente nada no Android; são interpretadas **somente pelo initramfs do Linux experimental**, se ele iniciar.
- O controle de energia USB pode depender de GPIOs específicos do HY310X. Ainda não validamos o Device Tree; não reutilizar indiscriminadamente configurações de ventoinha/energia do HY310.
- O arquivo `KEXEC.LOG` pode conter informações técnicas locais do dispositivo; não publique logs completos sem revisá-los.
- Não execute `kexec -l` ou `kexec -e` com o kit atual; `config/hardware.json` permanece `boot_allowed: false` e `docs/GO-NOGO.md` continua bloqueando boot real.
- Esta implementação usa `busybox` estático; a compilação de drivers USB, armazenamento e VFAT/exFAT é exigida como **built-in** no kernel, já que o initramfs não carrega módulos.
- Não existe forma garantida de observar falhas pré-`/init` sem UART ou outra instrumentação independente.

## O que podemos testar agora

Compilação em CI, checagem `sha256sum` dos artefatos, configuração do kernel, integridade do arquivo `initramfs.cpio.gz`, sintaxe `sh -n initramfs/init` e testes estáticos. Isso **não** valida um dispositivo real nem autoriza o handoff.
