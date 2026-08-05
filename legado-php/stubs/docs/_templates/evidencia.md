---
id: EVID-AAAA-MM-DD
tipo: evidencia
projeto: <nome>
titulo: <o que foi executado>
status: verificado
verificado_em: AAAA-MM-DD
verificado_commit: <sha>
---

# <título>

> **Pacote de evidência.** Registra o que rodou, quando, e com que resultado medido.
> Vale porque foi capturado **na hora** — evidência reconstruída depois é narrativa.

## O que foi executado

<Comando ou ação, literal.>

## Ambiente

<Onde rodou, com qual configuração, com quais chaves ligadas ou desligadas.>

## Números medidos

<Os valores, não a impressão. "24 testes, 137 asserções", não "os testes passaram".>

## O que isto prova

<E, com igual clareza, **o que não prova**. Teste com dado sintético não prova
comportamento com dado real, e dizer isso evita que alguém conclua demais.>

## Arquivos preservados

<Saída de comando, log, diff. Se você cita um arquivo aqui, ele precisa existir —
a verificação de âncoras confere.>
