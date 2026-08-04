---
id: PRD-00XX
tipo: prd
projeto: <nome>
titulo: <o problema em uma frase, do ponto de vista de quem sofre com ele>
status: rascunho
verificado_em: AAAA-MM-DD
verificado_commit: <sha>
deriva_de: []
supersede: []
ancoras: []
---

# <título>

> **PRD é o único documento da cadeia que não fala de solução.** No instante em que
> aparece nome de tabela, de serviço ou de biblioteca, virou FDD ou HLD escrito no lugar
> errado — e o problema original deixa de estar escrito em algum lugar.
>
> O teste: se a equipe resolvesse este problema de um jeito completamente diferente do
> que você imagina, este documento continuaria válido? Se não, tem solução escondida aqui.

## O problema

<Quem sofre, o que acontece hoje, e com que frequência. **Números medidos, não estimados** —
"o operador refaz a conciliação 4 vezes por semana" vale mais que "o processo é manual e
demorado". Se você não mediu, escreva que não mediu.>

## Por que agora

<O que mudou que faz este problema valer o custo agora e não seis meses atrás. Sem esta
seção, todo PRD parece igualmente urgente — e quando tudo é urgente, a ordem vira quem
gritou por último.>

## Resultado esperado

<O estado do mundo depois. Em linguagem de quem usa, não de quem constrói.>

| Como está hoje | Como fica | Como saberemos |
|---|---|---|
| <número medido> | <número alvo> | <a medição que prova> |

> A terceira coluna é a que dá trabalho e é a que importa. **Resultado sem forma de
> medir não é resultado, é esperança.** Se não houver medição possível, escreva
> "não mensurável" e diga por quê — isso é honesto e ainda dá para decidir.

## Fora de escopo

<O que este PRD deliberadamente NÃO resolve, e que alguém vai perguntar. Escrever isto
economiza a discussão que sempre acontece na terceira semana.>

## Restrições

<Prazo, orçamento, regulação, contrato, integração que não pode quebrar. Restrição é
diferente de requisito: requisito é o que queremos, restrição é o que não podemos
violar mesmo que queiramos.>

## Quem decide

<Nome. Uma pessoa. Quando esta seção diz "o time", ninguém decide.>

## Em aberto

<O que ainda não está resolvido. **Toda entrada aqui tem uma correspondente em
`docs/ABERTO.md`** — aqui fica o resumo no contexto do documento, lá fica a fila que
alguém varre.>
