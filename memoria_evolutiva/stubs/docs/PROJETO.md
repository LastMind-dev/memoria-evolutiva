---
id: PROJETO
tipo: entrada
projeto: <NOME-DO-PROJETO>
titulo: Porta de entrada para agentes e humanos
status: rascunho
verificado_em: <AAAA-MM-DD>
verificado_commit: <sha>
---

# <NOME-DO-PROJETO> — Porta de entrada

> **Se você é um modelo de linguagem, este é o único arquivo que você precisa saber que existe.**
> Tudo começa aqui. `CLAUDE.md`, `AGENTS.md`, `.cursor/`, `.windsurf/` e similares são
> apenas atalhos que apontam para cá.

---

## 1. Leia nesta ordem — 4 arquivos, ~5 minutos

| # | Arquivo | O que você aprende |
|---|---|---|
| 1 | **este arquivo** | regras de operação, jurisdição, o que é proibido |
| 2 | `docs/ESTADO.md` | onde o projeto está agora, e as próximas ações |
| 3 | `docs/cronologia/` — **o mês corrente e o anterior** | o que aconteceu e por quê |
| 4 | `docs/ABERTO.md` | o que está em conflito — **não resolva sozinho** |

> ⚠️ **Nunca fixe o mês na linha 3.** Liste `docs/cronologia/` e pegue os dois arquivos
> mais recentes. Referência fixa envelhece e faz o agente perder o mês corrente inteiro.

**Este arquivo sozinho não responde "onde o projeto está".** Ele dá as regras; o estado
vive no `ESTADO.md` e no histórico do versionador.

---

## 2. O que é o projeto, em três frases

<!-- O que faz, para quem, e qual o custo de errar. Se o erro tem consequência
     financeira, operacional ou legal, diga qual — muda como o agente age. -->

**Stack:** <linguagens, frameworks e versões — as reais, conferidas no arquivo de dependências>

---

## 3. Jurisdição — onde cada fato mora

<!-- Liste só os acervos que existem de verdade. Um acervo sem jurisdição exclusiva
     é o começo da bifurcação. -->

| Acervo | Manda em | Autoridade |
|---|---|---|
| **`docs/` neste repositório** | todo fato sobre o código | **canônica** |
| <acervo secundário, se houver> | <assunto exclusivo> | canônica **só fora do código** |
| Hindsight local — ver `padrao.json` → `memoria` | busca por significado nos documentos | **zero. sempre derivado** |
| Graphify — ver `padrao.json` → `grafo` | estrutura do código: quem chama o quê, impacto de mudança | **zero. sempre derivado do código** |

### Ordem de desempate quando as fontes divergirem

```
1. o código                              (verdade última)
2. docs/gerado/                          (extraído do código, reprodutível)
3. docs/ com status: verificado
4. docs/ com status: rascunho
5. <acervo secundário>
6. Hindsight, apenas como ponteiro para as fontes acima
```

**Duas regras que acompanham:**

- **Resultado de busca semântica nunca é resposta final.** É ponteiro: suba até a fonte
  canônica pela origem declarada, e responda de lá.
- **O grafo de código responde "como funciona", nunca "por quê".** Ele mapeia
  o que o código É — inclusive quando o código está errado. O porquê mora em `docs/`.
- **Divergência entre dois níveis segue a política autônoma.** Aplique a ordem de
  autoridade, registre os dois lados e continue; sem desempate, use `indeterminado`.

### Direção do fluxo

```
exploração ──promove──► docs/ ──indexa──► índice
    ▲                                       │
    └──────────  nunca volta  ◄─────────────┘
```

Quando uma descoberta vira fato estável sobre o código, ela é **movida** para `docs/` com
âncora de arquivo, e no lugar de origem fica um link de uma linha. **Cópia é proibida nas
duas direções** — é a cópia que produz a bifurcação.

---

## 4. Regras invioláveis

### 4.1 Ambientes

| Ambiente | Endereço | Política |
|---|---|---|
| Local | — | livre. Reproduza e corrija aqui primeiro |
| <homologação> | <endereço> | leitura por padrão; escrita exige autorização |
| <produção> | <endereço> | somente leitura. Escrita exige autorização **a cada ação** |

<!-- ⚠️ Documente aqui toda armadilha de ambiente que já causou susto: nome de banco
     que engana, ambientes no mesmo host, configuração local que aponta para remoto.
     Este bloco é o que evita o acidente caro. -->

**Fluxo de promoção obrigatório:** local → <homologação> → <produção>.
Proibido alterar ambiente remoto como primeira etapa.

### 4.2 Nunca

<!-- Cada linha deve ser verificável e ter consequência conhecida. Prefira
     "nunca X porque Y" a "tenha cuidado com X". -->

- <ação proibida> — <o que acontece se fizer>
- Commitar sem autorização explícita.

### 4.3 Exige autorização explícita

<!-- Toda ação irreversível ou com efeito em ambiente remoto. -->

**Formato aceito:**

```
Autorizo <ação específica> em <ambiente/alvo>,
com escopo <limite exato>,
rollback <plano>,
durante <janela ou "uma execução">.
```

Autorização genérica — "pode", "manda ver", "resolve isso" — **não autoriza nada**.

---

## 5. Como o dono trabalha

<!-- Parece supérfluo e é o que mais economiza tempo. Idioma, nível de detalhe, se quer
     opções antes da execução, o que nunca fazer sem perguntar. -->

1. **Idioma:** <>
2. <preferência>
3. <preferência>

---

## 6. Onde encontrar cada coisa

| Quero saber | Leia | Tipo |
|---|---|---|
| Onde o projeto está agora | `docs/ESTADO.md` | `estado` |
| O que está em conflito | `docs/ABERTO.md` | `estado` |
| Termos do domínio | `docs/GLOSSARIO.md` | `entrada` |
| **Por que fazer** — problema e resultado esperado | `docs/produto/` | `prd` |
| **O que o sistema faz** — comportamento, regras, exceções | `docs/funcional/` | `fdd` |
| **Como está organizado** — componentes, fronteiras, fluxos | `docs/arquitetura/` | `hld` |
| **Como está construído** — invariantes, contratos internos | `docs/arquitetura/` | `lld` |
| **Por que decidimos assim** | `docs/decisoes/` | `adr` |
| Como operar alguma coisa | `docs/runbooks/` | `runbook` |
| Regra que o projeto se impõe | `docs/politicas/` | `politica` |
| O que rodou, quando, com que resultado | `docs/evidencia/` | `evidencia` |
| Mapa de diretórios, cadeia de documentos | `docs/gerado/` — **gerado do código, nunca editado à mão** | `gerado` |
| Como validar uma alteração | <comandos reais de teste e lint deste projeto> | — |

### A cadeia, e para que ela serve

```
PRD ──────► FDD ──────► HLD ──────► LLD
por quê     o que faz   como é      como está
fazer                   organizado  construído
      └───────────── ADR ─────────────┘
        por que decidimos assim
```

Todo documento da cadeia declara `deriva_de` no frontmatter — a lista de documentos dos
quais ele depende, incluindo **todo ADR que restringe o que ele afirma**. Isso existe para
responder a **uma** pergunta, que é a que evita metade da documentação podre:

> Quando este documento mudar, o que mais preciso revisar?

O mapa atual está em `docs/gerado/cadeia-documentos.md` — **gerado**, portanto nunca
desatualizado. A verificação reprova `deriva_de` apontando para documento inexistente,
direção invertida, ciclo, e documento `verificado` pendurado num pai já `superado`.

---

## 7. Ao terminar a sessão, você DEVE

1. **Acrescentar uma entrada** em `docs/cronologia/<ano>-<mês>.md`, no topo. Nunca edite
   entradas antigas — a cronologia é append-only.
2. **Reescrever** `docs/ESTADO.md`. Ele não acumula; máximo uma página.
3. **Registrar em** `docs/ABERTO.md` qualquer divergência que encontrou e não resolveu.
4. `memoria bancos sincronizar` e `memoria bancos status`
5. **Rodar `memoria verificar` e `memoria autoteste`.** A verificação inclui a skill
   derivada quando ela já foi gerada.
6. **Não commitar** sem autorização explícita.

> **Os itens 1–5 e o 6 se contradizem de propósito, e a saída é esta:** você grava os
> arquivos e **deixa a árvore suja**. Quem commita é <quem>, quando revisar. Duas sessões
> seguidas podem acumular alterações não commitadas, e isso é aceitável. O que não é
> aceitável é commitar para "deixar limpo".
>
> Ao começar uma sessão, **rode `git status` antes de qualquer coisa**. Alteração não
> commitada de uma sessão anterior é contexto, não sujeira.

---

## 8. Frontmatter obrigatório

```yaml
---
id: ADR-0007                 # chave estável, nunca muda
tipo: adr                    # ver vocabulário em padrao.json
projeto: <nome>
titulo: <frase que diz o que é>
status: verificado           # rascunho | verificado | superado
verificado_em: 2026-08-04
verificado_commit: a1b2c3d   # contra qual versão do código foi conferido
deriva_de:                   # de quem este documento DEPENDE — a cadeia
  - HLD-0002
supersede: []                # ids que este documento torna obsoletos
ancoras:                     # arquivos que este documento descreve
  - src/Servicos/Pagamento.php
---
```

**Dois campos carregam quase todo o valor da verificação:**

`ancoras` amarra o documento ao **código**. É o que transforma "documento desatualizado"
de opinião em fato verificável — a verificação confere que cada caminho existe.

`deriva_de` amarra o documento aos **outros documentos**. É o que permite responder
"quando isto mudar, o que mais preciso revisar?", e o que faz a verificação reprovar um
documento vivo pendurado num pai já superado.

Sem o primeiro, a documentação descola do código. Sem o segundo, ela descola de si mesma.
