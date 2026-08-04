---
id: HLD-00XX
tipo: hld
projeto: <nome>
titulo: <o recorte de arquitetura que este documento cobre>
status: rascunho
verificado_em: AAAA-MM-DD
verificado_commit: <sha>
deriva_de:
  - FDD-00XX
  - <TODO ADR que restringe este desenho — ver a seção "Decisões" abaixo>
supersede: []
ancoras:
  - <diretório ou arquivo que materializa este desenho>
---

# <título>

> **HLD responde "como está organizado", não "como está construído".** Componentes,
> fronteiras, quem chama quem, onde o dado mora, o que acontece quando uma parte cai.
> Nome de classe e assinatura de método são assunto do LLD.
>
> O teste: um desenvolvedor novo consegue, lendo só isto, saber **em qual componente
> mexer** para uma mudança dada? Se sim, o HLD está fazendo o trabalho dele.

## Escopo

<O que este documento cobre e o que ele não cobre. HLD que tenta cobrir o sistema
inteiro não é lido; HLD por recorte é.>

## Componentes

| Componente | Responsabilidade | Onde no código |
|---|---|---|
| <nome> | <uma frase — se precisar de duas, provavelmente são dois componentes> | `caminho/` |

> Cada caminho desta última coluna deve entrar em `ancoras`. É o que impede este
> documento de descrever uma organização que já não existe.

## Fluxo

<Diagrama em texto ou lista numerada. Texto simples envelhece melhor que imagem, e
aparece no diff.>

```
<origem> ──<o que trafega>──► <componente> ──► <destino>
```

## Fronteiras e contratos

<O que atravessa cada fronteira, e o que cada lado pode presumir do outro. **A fronteira
mal definida é a origem da maioria dos acoplamentos que ninguém consegue desfazer depois.**>

| Fronteira | O que atravessa | Quem pode presumir o quê |
|---|---|---|
| <A → B> | <dado / evento / chamada> | <contrato> |

## Onde o dado mora

<Qual componente é dono de qual dado. **Um dado, um dono** — a mesma regra que vale para
documento vale para estado. Dois componentes escrevendo no mesmo lugar é a versão em
código do problema que este método existe para resolver.>

## O que acontece quando falha

| Se isto cai | O sistema | O usuário percebe |
|---|---|---|
| <componente> | <degrada assim> | <o quê> |

> Sistema sem esta seção só foi desenhado para o dia bom.

## Decisões que sustentam este desenho

> ⚠️ **Cada ADR listado aqui precisa TAMBÉM estar em `deriva_de`, lá em cima.**
>
> Citar em prosa não basta — nada lê prosa. É a linha do frontmatter que faz o build
> quebrar quando a decisão cair, e sem ela este documento sobrevive descrevendo um
> comportamento que o projeto já abandonou. Aconteceu num teste real do método: a decisão
> caiu, o mapa gerado mostrou "ninguém depende desta", e os dois documentos afetados só
> foram encontrados porque alguém conhecia o domínio.

- `ADR-00XX` — <a decisão em meia linha>

Se uma escolha estruturante não tem ADR, ela vai ser desfeita por alguém que não sabia
por que ela existia.

## Restrições que este desenho respeita

<Do PRD ou de fora: latência, volume, regulação, compatibilidade, custo.>

## Em aberto

<O que ainda não foi decidido neste nível. **Toda entrada aqui tem uma correspondente em
`docs/ABERTO.md`** — aqui o resumo, lá a fila.>
