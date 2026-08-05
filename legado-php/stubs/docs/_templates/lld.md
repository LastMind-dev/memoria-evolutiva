---
id: LLD-00XX
tipo: lld
projeto: <nome>
titulo: <o componente que este documento detalha>
status: rascunho
verificado_em: AAAA-MM-DD
verificado_commit: <sha>
deriva_de:
  - HLD-00XX
  - <TODO ADR que amarra alguma invariante abaixo>
supersede: []
ancoras:
  - <os arquivos exatos que este documento descreve>
---

# <título>

> ⚠️ **LLD é o documento que apodrece mais rápido de toda a cadeia**, porque é o que fica
> mais perto do código. Antes de escrever, faça a pergunta que economiza mais trabalho
> neste método inteiro:
>
> **Isto pode ser gerado do código em vez de escrito?**
>
> Esquema de tabelas, lista de rotas, assinaturas públicas, comandos disponíveis, variáveis
> de ambiente — tudo isso deve sair de um extrator em `docs/gerado/`, nunca da sua mão.
> Um LLD escrito à mão que repete o que o código já diz é uma segunda fonte da verdade,
> e vai divergir.
>
> **Escreva LLD só para o que o código não consegue dizer sozinho:** por que o algoritmo
> é esse, qual invariante precisa ser mantida, o que quebra se alguém "simplificar".

## O que é gerado, e não está aqui

<Aponte para os arquivos de `docs/gerado/` que cobrem este componente. Esta seção
existe para impedir que alguém duplique aqui o que já é extraído.>

## Invariantes

<O que precisa ser verdade sempre, e que o código sozinho não anuncia. **É a seção mais
valiosa do documento** — invariante quebrada é o bug que ninguém entende.>

| # | Invariante | O que quebra se violada | Verificado por |
|---|---|---|---|
| I1 | <sempre verdade> | <consequência> | <teste ou "nada hoje"> |

## Decisões de implementação não óbvias

<Onde alguém, lendo o código, pensaria "isto está mais complicado do que precisa". Explique
por quê — senão será "simplificado" por alguém bem-intencionado e o bug volta.>

### <o trecho>

**Parece:** <o que parece à primeira vista>
**É:** <o que realmente é>
**Se simplificar:** <o que quebra>

## Contratos internos

<Formato de dado que atravessa fronteira dentro deste componente: fila, evento, cache,
arquivo. O que é público e o que é detalhe interno que pode mudar sem aviso.>

## Concorrência e ordem

<O que pode rodar em paralelo, o que não pode, o que precisa de trava, o que acontece se
a mesma coisa for processada duas vezes. Se não se aplica, escreva "não se aplica" — a
ausência da seção é ambígua, a frase não é.>

## Falhas e recuperação

| Falha | Detecção | Recuperação | Perde dado? |
|---|---|---|---|
| <o que pode dar errado> | <como se percebe> | <o que fazer> | <sim/não/qual> |

> **Não há seção "como conferir" aqui de propósito.** Ela existe no FDD (cenários de
> comportamento) e no ADR (a decisão ainda vale?). Neste documento a verificação mora na
> coluna "Verificado por" da tabela de invariantes, onde ela é específica. Repetir a
> mesma pergunta em três níveis produziu, num teste real, a mesma frase escrita três
> vezes — que é o sinal de que a seção virou ritual.
