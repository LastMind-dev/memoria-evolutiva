# Exemplo — um `docs/PROJETO.md` preenchido

Material de referência. **Não copie para dentro do seu projeto** — o template em branco
é `docs/PROJETO.md`, e é dele que você parte. Este arquivo existe só para você ver como
fica quando alguém responde de verdade, porque template em branco não ensina o nível de
detalhe que faz diferença.

O projeto é fictício: uma API de reservas de restaurante. Repare que quase toda linha
útil aqui é **específica** — nome de ambiente, nome de tabela, o susto que já aconteceu.
Linha genérica ("tenha cuidado com produção") não protege ninguém.

---

```markdown
---
id: PROJETO
tipo: entrada
projeto: reservas
titulo: Porta de entrada para agentes e humanos
status: verificado
verificado_em: 2026-08-04
verificado_commit: 7f3a91c
---

# reservas — Porta de entrada

> **Se você é um modelo de linguagem, este é o único arquivo que você precisa saber que existe.**

## 1. Leia nesta ordem — 4 arquivos, ~5 minutos

| # | Arquivo | O que você aprende |
|---|---|---|
| 1 | este arquivo | regras de operação, jurisdição, o que é proibido |
| 2 | `docs/ESTADO.md` | onde o projeto está agora |
| 3 | `docs/cronologia/` — o mês corrente e o anterior | o que aconteceu e por quê |
| 4 | `docs/ABERTO.md` | o que está em conflito — não resolva sozinho |

> ⚠️ Nunca fixe o mês na linha 3. Liste a pasta e pegue os dois mais recentes.

## 2. O que é o projeto, em três frases

API que recebe reservas de mesa de três canais — site próprio, telefone (operador) e um
agregador parceiro — e as concilia contra a lotação real de cada turno. Quem usa: os
sete restaurantes do grupo, mais o call center.

**O custo de errar é operacional e imediato:** uma reserva perdida vira mesa vazia; uma
reserva duplicada vira cliente na porta sem lugar, na frente de outros clientes. Não há
desfazer útil depois das 19h de uma sexta.

**Stack:** PHP 8.3, Slim 4, MySQL 8.0, Redis 7 para fila. Sem framework de front — o
painel é servido por outro repositório (`reservas-painel`).

## 3. Jurisdição — onde cada fato mora

| Acervo | Manda em | Autoridade |
|---|---|---|
| **`docs/` neste repositório** | todo fato sobre o código | **canônica** |
| Notion "Operação Restaurantes" | procedimento de salão, escala, contrato com o agregador | canônica **só fora do código** |
| — | não temos índice semântico | — |

### Ordem de desempate

```
1. o código
2. docs/gerado/
3. docs/ com status: verificado
4. docs/ com status: rascunho
5. Notion "Operação Restaurantes"
```

O Notion **não manda em nada de código**. Se uma página dele descreve comportamento da
API, ela está descrevendo o que alguém achou que era — registre em `ABERTO.md`.

### Direção do fluxo

Discussão nasce no Notion. Quando vira fato sobre o código, é **movida** para `docs/`
com âncora, e no Notion fica um link. Cópia é proibida nas duas direções.

## 4. Regras invioláveis

### 4.1 Ambientes

| Ambiente | Endereço | Política |
|---|---|---|
| Local | `docker compose up` | livre. Reproduza e corrija aqui primeiro |
| Homologação | `hml.reservas.interno` | leitura livre; escrita exige autorização |
| Produção | `api.reservas.com.br` | somente leitura. Escrita exige autorização **a cada ação** |

> ⚠️ **A armadilha desta casa:** o banco de homologação chama-se `reservas_prod_espelho`.
> O nome tem "prod" e **não é produção** — é uma cópia noturna. Já houve quem se recusasse
> a rodar migração em homologação achando que era produção, e já houve o contrário: quem
> apontou o `.env` local para `reservas_prod_espelho` e passou uma tarde depurando dado
> que era de ontem. **Produção é `reservas_live`, e só.**

**Fluxo de promoção obrigatório:** local → homologação → produção.

### 4.2 Nunca

- **Nunca apagar linha de `reservas`** — a auditoria do agregador exige o histórico
  completo; cancelamento é `status = cancelada`, nunca `DELETE`.
- **Nunca alterar `turnos.capacidade` sem conferir as reservas já confirmadas do dia** —
  reduzir capacidade não cancela reserva existente, gera overbooking silencioso.
- **Nunca rodar `php bin/reconciliar.php` sem `--dry-run` antes.** Ele escreve.
- **Nunca commitar sem autorização explícita.**

### 4.3 Exige autorização explícita

Migração em qualquer ambiente remoto · qualquer escrita em produção · reprocessar fila ·
alterar credencial · publicar release.

**Formato aceito:**

```
Autorizo <ação específica> em <ambiente>,
com escopo <limite exato>,
rollback <plano>,
durante <janela ou "uma execução">.
```

Autorização genérica — "pode", "manda ver" — **não autoriza nada**.

## 5. Como o dono trabalha

1. **Idioma:** português do Brasil, sempre.
2. Antes de executar algo com mais de três passos, me mostre o plano em tópicos.
3. Prefiro uma opção recomendada com o porquê a três opções neutras.
4. Se encontrar dois caminhos e eu não estiver por perto: escolha o reversível e anote
   em `ABERTO.md` o que ficou em aberto.
5. Não me poupe de má notícia. Se o número piorou, o número piorou.

## 6. Onde encontrar cada coisa

| Quero saber | Leia |
|---|---|
| Onde o projeto está agora | `docs/ESTADO.md` |
| O que está em conflito | `docs/ABERTO.md` |
| Termos do domínio (turno, no-show, janela) | `docs/GLOSSARIO.md` |
| Por que decidimos X | `docs/decisoes/` |
| Regra de negócio da conciliação | `docs/dominio/conciliacao.md` |
| Como o sistema é organizado | `docs/arquitetura/` |
| Como operar alguma coisa | `docs/runbooks/` |
| O que rodou, quando, com que resultado | `docs/evidencia/` |
| Mapa de diretórios | `docs/gerado/` — **gerado, nunca editado à mão** |
| Como validar uma alteração | `composer test && composer lint` |

## 7. Ao terminar a sessão, você DEVE

Seguir `docs/runbooks/sessao.md`, seção "Fechamento". Resumo: cronologia, ESTADO,
ABERTO, regerar derivados, rodar os três validadores. **Não commitar** — quem commita
sou eu, ao revisar.

> **Os passos acima e o "não commitar" se contradizem de propósito, e a saída é esta:**
> grave os arquivos e **deixe a árvore suja**. Duas sessões podem acumular alteração não
> commitada, e tudo bem. O que não vale é commitar para "deixar limpo".
>
> Ao começar, **rode `git status` antes de qualquer coisa**. Alteração não commitada de
> uma sessão anterior é contexto, não sujeira.

## 8. Frontmatter obrigatório

<!-- igual ao template; ver docs/PROJETO.md -->
```

---

## O que este exemplo faz que um preenchimento apressado não faz

- **§2 diz o custo de errar.** "Mesa vazia" e "cliente na porta sem lugar" mudam como um
  agente age diante de uma dúvida — muito mais que "sistema importante".
- **§3 declara que o Notion não manda em código.** Sem essa frase, todo agente que
  encontrar uma página do Notion vai tratá-la como especificação.
- **§4.1 documenta a armadilha do nome do banco**, com os dois acidentes que ela já
  causou — um em cada direção. É o bloco mais valioso do documento inteiro.
- **§4.2 diz o porquê de cada proibição.** "Nunca apagar linha de `reservas`" sozinho
  vira regra que alguém contorna quando ficar inconveniente; com "a auditoria do
  agregador exige", não vira.
- **§5 item 5** — "não me poupe de má notícia" — é o tipo de linha que parece supérflua
  e é a que mais muda o comportamento na prática.
