---
id: ADR-00XX
tipo: adr
projeto: <nome>
titulo: <a decisão em uma frase, no imperativo>
status: verificado
verificado_em: AAAA-MM-DD
verificado_commit: <sha>
deriva_de:
  - <o documento que MOTIVOU esta decisão — FDD, PRD ou HLD. Pode ficar vazio>
supersede: []
ancoras:
  - <arquivo que implementa esta decisão>
---

# <título>

> **ADR — registro de decisão de arquitetura.** Atravessa a cadeia: pode nascer de um PRD,
> de um FDD, de um HLD, ou de nada além de uma discussão. É o único documento da cadeia
> que **nunca é editado depois de aceito** — decisão que mudou vira ADR novo, e o antigo
> passa a `status: superado` com `supersede` apontando dos dois lados.
>
> Editar um ADR antigo apaga a informação mais valiosa que ele carrega: **o que se
> acreditava na época.** Sem isso, ninguém entende por que a decisão fazia sentido.
>
> ⚠️ **Direção:** este ADR depende do documento que o motivou. Quem **implementa** a
> decisão — HLD, LLD — é que depende deste ADR, declarando o id em `deriva_de`. Nunca os
> dois sentidos entre o mesmo par: o validador reprova ciclo.

## Contexto

<A situação que forçou a decisão. O que estava travado, o que ia quebrar, qual prazo
apertava. Escreva no presente da época — este documento é um registro histórico.>

## Decisão

<Uma frase. O que foi decidido, sem justificativa ainda.>

## O que foi descartado

> **Esta é a seção que faz o ADR valer alguma coisa daqui a um ano.** Sem ela, alguém
> refaz a mesma análise, chega à mesma conclusão e gasta o mesmo tempo — ou pior, chega
> a outra e desfaz a decisão sem saber o que ela protegia.

| Alternativa | Por que perdeu |
|---|---|
| <opção> | <razão concreta, não "não se encaixava"> |

## Consequências

**O que passa a ser verdade:**
<O que fica mais fácil, o que fica garantido.>

**O que fica pior, e aceitamos:**
<Toda decisão tem custo. ADR que só lista benefício não foi uma decisão, foi uma
preferência — e a próxima pessoa vai descobrir o custo sozinha, no pior momento.>

**O que quebra se alguém ignorar:**
<A consequência concreta de violar esta decisão.>

## Quem depende desta decisão

<Liste os documentos que a implementam. **Cada um deles precisa ter o id deste ADR em
`deriva_de`** — é isso que faz o build quebrar quando esta decisão cair. Citação em
prosa não conta: nada lê prosa.>

## Como conferir que está valendo

<Comando, teste, contador da catraca. Se não houver, escreva "não é verificável hoje" —
isso é informação, não vergonha, e é candidato a virar contador.>

## Quando revisitar

<O gatilho concreto que deve fazer alguém reabrir isto: um volume, um prazo, uma
dependência que muda. "Quando fizer sentido" não é gatilho.>
