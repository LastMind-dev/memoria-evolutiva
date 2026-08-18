# Instalar — um comando até o primeiro build verde

Este é o caminho prático. O **porquê** de cada peça está no `METODO.md`; leia depois,
ou quando alguma decisão da Parte IV parecer arbitrária.

> **O caminho recomendado é via pipx** — os validadores ficam no pacote, com um
> dono só, e `pipx upgrade` corrige todos os seus projetos de uma vez. Quando o kit
> era copiado para dentro de cada projeto, cada cópia dos scripts era uma bifurcação
> esperando acontecer: bug corrigido no kit não chegava a projeto nenhum. É o próprio
> método aplicado a ele mesmo — um fato, um dono.

---

## O que este kit é

Uma estrutura de documentação que **falha o build quando mente**, e um método para
manter a história do projeto de forma que qualquer modelo de linguagem — hoje ou daqui
a dois anos, em qualquer ferramenta — consiga abrir o repositório e saber onde o
projeto está sem que ninguém precise explicar.

O acervo canônico não depende de fornecedor. São arquivos markdown no seu repositório,
mais um pacote Python de validadores sem dependência além da biblioteca padrão. Se todas as
ferramentas de IA que você usa hoje desaparecerem, a memória continua lá.

---

## 0. Antes de copiar nada

Em projeto existente, o instalador inventaria o acervo atual antes de escrever e preserva
arquivos que não sejam gerenciados pelo motor. Conflitos entram na política de autoridade;
não existe uma parada obrigatória para revisão humana.

`docs/` é a jurisdição canônica instalada. Fontes externas permanecem ponteiros até que
uma IA consiga confrontá-las com código, testes, configuração e histórico.

Projeto novo: pode pular direto para o passo 1.

---

## 1. Instale o pacote

```bash
pipx install git+https://github.com/LastMind-dev/memoria-evolutiva.git@main
```

O pacote ainda não foi publicado no PyPI. O `@main` acima é somente o bootstrap. O
instalador descobre a procedência PEP 610 do pacote e fixa o workflow documental no
commit Git exato de 40 caracteres; se não houver uma origem Git pública e verificável,
fixa a versão exata `memoria-evolutiva==6.0.0`. Uma URL com credencial embutida nunca é
copiada para o projeto.

Isso traz o comando `memoria` para o seu PATH. **Nenhum script é copiado para o seu
repositório** — no projeto só vai morar o que é seu. `pipx upgrade memoria-evolutiva`
atualiza os validadores para todos os projetos de uma vez.

Os documentos do método (`METODO.md`, `RAG.md`, este arquivo, o exemplo preenchido)
ficam no repositório do pacote — leia de lá, não copie.

> **O projeto não é Python?** Não importa: o pacote só precisa de um Python ≥ 3.10 na
> máquina (e no runner de CI). O projeto documentado pode ser em qualquer linguagem —
> o que o gerador varre é configurável, e os extratores próprios rodam na linguagem
> do projeto.

Se o projeto já tem um `CLAUDE.md` ou `AGENTS.md`, o instalador preserva o conteúdo e
insere somente um bloco gerenciado de descoberta. A IA extrai fatos verificáveis para
`docs/`; adaptadores nunca viram uma segunda memória.

## 2. Rode o instalador — na raiz do projeto

Antes, deixe o Hindsight local acessível em `http://127.0.0.1:8888` e instale o
Graphify (`graphifyy`) de forma que `graphify` esteja no PATH. O Hindsight usa a
configuração de modelo local/credencial do próprio serviço; segredo nunca entra em
`padrao.json`.

```bash
memoria instalar --projeto="meu-app" --codigo=src
```

Ele publica a árvore e os moldes, detecta as linguagens, calcula SHA-256 de todas as
fontes configuradas, produz o núcleo estrutural, mede a dívida inicial, valida, atualiza
cada documento no Hindsight e cria o grafo Graphify. A cobertura por hash não é chamada
de compreensão semântica: a skill autônoma percorre o manifesto e registra fatos
demonstráveis nos blocos evolutivos preservados.
Também gera o manifesto neutro e as entradas de Codex, Claude, Cursor, Windsurf e Hermes.
Uma sessão nova inicia pelo canary específico e não pede avaliação humana do conteúdo.
O instalador cria ainda três casos mínimos de avaliação, mede uma baseline somente se
todos passarem e grava relatório/manifesto reconstruíveis da qualidade do RAG.

`--codigo` é a pasta que o gerador varre (`src`, `app`, `lib`, `packages`...). Hindsight
e Graphify já são padrão; não existe decisão por projeto sobre qual ferramenta usar.
`--adiar-bancos` apenas adia a primeira sincronização e `--sem-bancos` é opt-out explícito.

Ele troca `<NOME-DO-PROJETO>` pelo nome real nos modelos e transforma
`docs/cronologia/AAAA-MM.md` no mês corrente. O `padrao.json` publicado vem com o nome
de exemplo; o instalador preenche o real **só se o valor ainda for o do exemplo** —
decisão sua ele nunca sobrescreve. Rodar de novo não estraga nada.

> Se o `padrao.json` ficasse com o nome de exemplo, todo documento gerado sairia
> carimbado errado **com o build verde**. Por isso o `memoria validar` compara o
> `projeto:` de cada documento com o do `padrao.json` — confira na saída do instalador
> que o nome que apareceu é o seu.

## 3. Manutenção autônoma

```bash
memoria documentar
memoria avaliar verificar
```

O comando atualiza apenas documentos marcados como gerenciados, regenera os derivados,
valida e sincroniza Hindsight+Graphify. Não há proposta intermediária nem promoção humana.

## 4. Como a IA decide

| Arquivo | Função automática |
|---|---|
| `docs/PROJETO.md` | fatos comprovados, ordem de leitura e limites operacionais. |
| `docs/ESTADO.md` | fotografia reproduzível da versão e da cobertura analisada. |
| `docs/ABERTO.md` | fila de investigação autônoma; ausência de prova vira `indeterminado`. |
| `docs/GLOSSARIO.md` | termos sustentados por uso observável, sem significado inventado. |

A ordem obrigatória é: runtime/esquema, testes, código, configuração, CI, histórico,
documentação e, por último, inferência. O contrato completo fica versionado em
`docs/politicas/AUTONOMIA.md` e o validador reprova alterações manuais nessa política.

### Engenharia sem decisões em aberto para a IA

O kit combina uma cobertura mecânica completa com uma estrutura semântica padronizada:

- arc42 organiza objetivos, restrições, contexto, blocos, runtime, implantação, decisões,
  qualidade, riscos e glossário;
- C4 define sistema, containers, componentes e código sem obrigar níveis sem evidência;
- PRD → FDD → HLD → LLD mantém rastreabilidade do problema à implementação;
- ADR registra contexto, decisão, alternativas e consequências;
- Diátaxis separa tutorial, procedimento, referência e explicação.

A IA não decide qual estrutura prefere: usa esta. Também não decide se uma hipótese
"parece provável": sem fonte suficiente, escreve `indeterminado` e segue para o próximo
item de `docs/ABERTO.md`.

## 5. Verificação automática

```bash
memoria documentar
memoria autoteste
memoria executar --run-id=primeira-verificacao --acao=verificar --json
```

O primeiro comando relê fontes, atualiza os documentos gerenciados, regenera derivados e
valida. O segundo quebra uma cópia temporária e comprova que política alterada, cobertura
velha, âncora morta, cadeia inválida e dívida crescente não passam silenciosamente.

### Os dois bancos locais

O Hindsight guarda uma cópia substituível por documento do núcleo listado em
`memoria.nucleo`, com tags estritas, metadados e `source_uri`. Depois do `retain` em lote,
o motor lê cada documento de volta e exige ao menos uma memória por fonte. O Graphify extrai AST
localmente e mantém uma assinatura por arquivo de código.

```bash
memoria bancos sincronizar
memoria bancos status
memoria bancos consultar --pergunta="onde esta regra é implementada e por quê?"
memoria contexto --pergunta="onde esta regra é implementada e por quê?" --perfil=engenharia-leitura --json
```

Não existe `--marcar`: o marcador é gravado somente pelo adaptador após confirmação.
Uma mudança em `docs/` ou no código bloqueia consultas até nova sincronização.

## 6. CI e publicação

As verificações rodam a cada push e pull request. Instalar e documentar não autorizam
commit, push ou publicação; essas ações seguem a política operacional do projeto.

> O workflow dispara em `push` para **`main`**. Se o seu repositório usa `master` ou
> outro nome, ajuste `branches:` em `.github/workflows/documentacao.yml` — senão o CI
> nunca roda no push e você vai achar que está verde sem nunca ter sido testado.

---

## 7. Teste de leitura fria automatizado

Uma nova sessão de IA começa em `docs/PROJETO.md`, segue a ordem declarada e confronta as
respostas com o manifesto de cobertura e as âncoras. Divergência abre investigação
autônoma e executa novamente `memoria documentar`; não vira pedido de validação humana.

---

## Depois da instalação

O que mantém isto vivo é `docs/runbooks/sessao.md`: o que ler ao abrir uma sessão e o
que registrar ao fechar. Sem esse ciclo, a estrutura existe e para no tempo.

Comece cada sessão pelo `PROJETO.md`, feche cada sessão pelo runbook, e deixe o
`ABERTO.md` encher. Ele encher é o sistema funcionando.

---

## Os comandos

| Script | O que faz | Falha quando |
|---|---|---|
| `memoria instalar` | instala, documenta, valida e sincroniza os bancos | etapa ou provedor local não confirma |
| `memoria documentar` | relê, atualiza, gera, valida e sincroniza | política, cobertura, estrutura ou banco diverge |
| `memoria diagnosticar` | inventário factual, sem escrita | configuração inválida |
| `memoria analisar` | consolida evidências e lacunas, sem escrita | configuração inválida |
| `memoria propor-documentacao` | compatibilidade legada; rascunhos opcionais | proposta existente seria sobrescrita |
| `memoria gerar` | extrai do código o que não deve ser escrito à mão | extrator declarado não existe |
| `memoria validar` | frontmatter, vocabulário, ids, **âncoras**, derivados, ponteiros | âncora aponta para arquivo inexistente; derivado editado à mão ou desatualizado; ponteiro virou fonte paralela |
| `memoria catraca` | mede a dívida congelada | algum contador aumentou |
| `memoria bancos` | status, sincronização e consulta conjunta | banco ausente, velho ou não confirmado |
| `memoria fragmentos` | gera ou verifica o corpus determinístico do RAG em modo sombra | fonte, âncora, hash, algoritmo ou perfil diverge |
| `memoria contexto` | recupera envelope neutro por CLI, MCP stdio ou HTTP local | fonte, perfil, frescor ou orçamento inválido |
| `memoria indice` | compatibilidade: estado do Hindsight | documento do núcleo mudou |
| `memoria autoteste` | quebra uma cópia de propósito e confere que os validadores reclamam | algum validador parou de pegar o que promete |
| `memoria executar ... --json` | ação não interativa, idempotente e isolada | o envelope identifica falha, timeout, lock ou capacidade recusada |
| `memoria avaliar` | mede/verifica hit@1, hit@3, citações, ausência de fonte e drift | corpus, baseline, perfil ou métrica regride |
| `memoria skill` | monta a peça de procedimento (skill/comando) a partir do runbook | `--conferir` falha se fonte, gerador ou artefato divergir |

Os comandos estruturais não sobem o projeto. `documentar` e `bancos` acessam somente os
provedores configurados; extrator próprio e Graphify operam com as permissões do processo.

**Não edite os scripts.** Se precisar mudar comportamento, provavelmente falta uma opção
no `padrao.json` — abra uma entrada em `docs/ABERTO.md` em vez de editar. Script alterado
localmente é a primeira peça a divergir quando o kit for atualizado.
