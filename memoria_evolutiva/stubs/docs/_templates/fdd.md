---
id: FDD-00XX
tipo: fdd
projeto: <nome>
titulo: <a funcionalidade em uma frase>
status: rascunho
verificado_em: AAAA-MM-DD
verificado_commit: <sha>
deriva_de:
  - PRD-00XX
  - <ADR ANTERIOR a este documento, que já restringia estas regras>
supersede: []
ancoras:
  - <arquivo que implementa este comportamento>
---

# <título>

> **FDD descreve comportamento observável, não implementação.** Fala em "o sistema
> rejeita", não em "o `ValidadorService` lança exceção". Se trocar o banco, o framework
> e a linguagem inteira, este documento continua valendo — é esse o teste.
>
> É também o documento que mais evita retrabalho, porque é onde as exceções aparecem
> antes de virarem bug.

## Contexto

<Duas ou três frases ligando ao PRD de origem. O que este documento resolve daquele problema.>

## Vocabulário

<Só os termos que este documento usa de um jeito específico. Se o termo vale para o
projeto inteiro, ele mora no `docs/GLOSSARIO.md` — aqui fica o link.>

## Comportamento

### Fluxo principal

<Passo a passo do que acontece quando tudo dá certo. Numerado.>

1. <ator> <ação>
2. o sistema <reação observável>

### Regras

<Cada regra numerada e testável. **"Nunca X porque Y"** vale mais que "deve-se evitar X".>

| # | Regra | O que acontece se violada |
|---|---|---|
| R1 | <regra> | <consequência concreta> |

### Exceções e casos de borda

> **Esta é a seção que separa um FDD útil de um FDD decorativo.** O fluxo principal
> qualquer um escreve; o que custa caro depois é o caso que ninguém pensou.

| Situação | O que o sistema faz | Por quê |
|---|---|---|
| <entrada inválida> | <reação> | <razão de negócio> |
| <recurso indisponível> | <reação> | <razão> |
| <ação repetida / duplicada> | <reação> | <razão> |
| <dado que já existia e mudou> | <reação> | <razão> |

### O que o sistema NÃO faz

<Comportamento que alguém vai supor que existe e não existe. Escrever isto evita o
chamado de suporte que começa com "mas eu achei que...".>

## Dados que este comportamento usa

<Em linguagem de negócio: "a reserva guarda quem reservou, para quando, e por qual canal".
Nome de tabela e coluna é assunto do LLD, não daqui.>

## Como conferir que está valendo

<Cenários de teste, em linguagem de comportamento. Se existem testes automatizados
correspondentes, aponte o arquivo — e ele vira âncora.>

| Dado que | Quando | Então |
|---|---|---|
| <estado inicial> | <ação> | <resultado observável> |

## Decisões que amarram estas regras

- `ADR-00XX` — <a decisão em meia linha>

> **Cuidado com a direção, é aqui que se cria ciclo sem perceber.**
>
> ADR que **já existia** e restringia estas regras: entra em `deriva_de` deste documento.
>
> ADR que **nasceu depois**, respondendo a uma dúvida que este FDD deixou em aberto: o
> ADR é que declara `deriva_de: [este FDD]`. Não declare a volta — a seta entre dois
> documentos aponta uma vez só, e o validador reprova o ciclo.

## Em aberto

<O que ficou indefinido. **Toda entrada aqui tem uma correspondente em `docs/ABERTO.md`**
— aqui fica o resumo no contexto do documento, lá fica a fila que alguém varre. Se não
vale abrir entrada lá, também não vale escrever aqui: vira nota solta que ninguém revisita.>
