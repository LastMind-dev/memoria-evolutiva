# memoria-evolutiva

Memória de projeto que **sobrevive à troca de ferramenta** e **falha o build quando
mente**: `docs/` canônico com frontmatter verificado, cadeia PRD → FDD → HLD → LLD → ADR,
cronologia append-only, catraca de dívida legada e CI de integridade.

O padrão instala também dois bancos locais derivados, sem jurisdição própria:
**Hindsight** para significado e histórico em `docs/`, e **Graphify** para relações e
impacto no código. A IA consulta ambos; a resposta final continua sendo confirmada nas
fontes canônicas.

O acervo e a verificação estrutural não dependem de fornecedor. São arquivos markdown
versionados no seu repositório, verificados por um pacote Python **sem nenhuma
dependência além da biblioteca padrão**; Hindsight e Graphify são caches substituíveis.
Qualquer LLM — hoje ou daqui a dois anos, em qualquer ferramenta — abre o repositório e
sabe onde o projeto está. E se todas as ferramentas de IA sumirem, a memória continua lá.

## Instalar

```bash
pipx install --include-deps "memoria-evolutiva[local] @ git+https://github.com/LastMind-dev/memoria-evolutiva.git@main"
cd meu-projeto
memoria instalar --projeto="meu-app" --codigo=src
```

O extra `local` traz Hindsight Embed e Graphify na mesma instalação. O perfil global do
Hindsight ou as variáveis `HINDSIGHT_API_LLM_*` continuam definindo o modelo sem
acoplá-lo ao projeto. O instalador inicia o daemon local sob demanda e falha
objetivamente se algum provedor não confirmar; não pede que uma pessoa julgue o resultado.

O instalador publica a árvore, detecta as linguagens presentes, calcula a cobertura
integral dos bytes de cada fonte configurada, gera o núcleo estrutural, congela a primeira linha de base, valida e
sincroniza os dois bancos. Cada
arquivo analisado fica registrado com SHA-256 em `docs/gerado/cobertura-codigo.md`.
Além disso, `docs/gerado/manifesto-fragmentos-v2.json` descreve o corpus futuro do RAG
com fragmentos, ACL, âncoras, hashes e fingerprint reproduzíveis. Na versão 6.0 ele roda em
modo sombra: é verificado junto dos bancos, sem migrar o Hindsight existente.
O corpus `docs/avaliacao/casos-rag-v1.json` mede hit@1, hit@3, citações, cobertura da
resposta, ausência de fonte e isolamento por perfil antes de aceitar mudança de RAG.
`docs/gerado/manifesto-adaptadores-v1.json` deriva as entradas de Codex, Claude,
Cursor, Windsurf e Hermes da mesma fonte, sem copiar fatos para arquivos de IDE.
Antes do Hindsight, redaction determinística remove credenciais e dados pessoais; a
classificação `secreto-nao-indexar` exclui o documento inteiro. Atendimento e operação
exigem produto+tenant explícitos e usam match exato antes da entrega.
O hash prova cobertura, não compreensão semântica. A skill do projeto percorre esse
manifesto, usa o grafo para impacto e promove fatos demonstráveis para os blocos
evolutivos preservados ou para PRD/FDD/HLD/LLD/ADR; sem prova, usa `indeterminado`.
Conteúdo preexistente do núcleo é arquivado em `.memoria/legado-documentacao/` antes de
o documento gerenciado assumir a jurisdição; demais documentos não são sobrescritos.

Depois de instalar, a manutenção usa dois gatilhos objetivos:

```bash
memoria ciclo iniciar --plataforma=codex --perfil=engenharia-leitura --json
memoria ciclo atualizar --plataforma=codex --perfil=engenharia-leitura --json
memoria agendador status --json  # tarefa diária criada pela instalação completa
memoria documentar  # relê, documenta, valida e sincroniza Hindsight+Graphify
memoria bancos consultar --pergunta="como funciona a autenticação?"
memoria contexto --pergunta="como funciona a autenticação?" --perfil=engenharia-leitura --json
memoria adaptadores canary --plataforma=codex --perfil=engenharia-leitura --json
memoria autoteste   # prova que os validadores ainda reprovam falhas reais
memoria executar --run-id=cron-2026-08-13 --acao=documentar --json
memoria avaliar verificar --json
```

O pacote ainda não foi publicado no PyPI. O `@main` acima serve apenas para o primeiro
bootstrap. Ao instalar o padrão no projeto, o workflow gerado é fixado automaticamente
no commit Git de 40 caracteres que originou o pacote; numa instalação de distribuição,
usa `memoria-evolutiva==6.0.0`. Assim, a automação nunca depende de uma branch mutável.
URLs de origem que contenham usuário ou senha não são propagadas para o workflow.

## Os comandos

| Comando | Faz | Falha quando |
|---|---|---|
| `memoria instalar` | instala, documenta, valida e cria/sincroniza os dois bancos locais | etapa autônoma ou provedor local não confirma |
| `memoria documentar` | relê as fontes, atualiza o núcleo, gera, valida e sincroniza os bancos | política, cobertura, estrutura ou banco diverge |
| `memoria diagnosticar` | inventário factual da estrutura, stack declarada, testes e CI | configuração inválida |
| `memoria analisar` | consolida evidências observáveis e perguntas ainda sem resposta | configuração inválida |
| `memoria propor-documentacao` | compatibilidade legada; cria rascunhos opcionais fora do canônico | proposta existente seria sobrescrita |
| `memoria gerar` | mapas, diagnóstico, análise e cobertura SHA-256 derivados | extrator declarado não existe |
| `memoria validar` | frontmatter, vocabulário, ids, **âncoras**, **cadeia**, derivados, ponteiros | âncora morta; derivado editado à mão; `deriva_de` quebrado, invertido ou circular; documento vivo pendurado em pai superado |
| `memoria catraca` | mede a dívida congelada (`--medir` grava a base) | algum contador aumentou |
| `memoria bancos sincronizar` | substitui o corpus no Hindsight e atualiza o Graphify | gravação/leitura de confirmação ou build falha |
| `memoria bancos consultar --pergunta=...` | consulta significado e estrutura, após verificar frescor | qualquer banco está velho ou indisponível |
| `memoria bancos status` | confirma documentos no Hindsight e integridade/cobertura do grafo | provedor ausente, banco vazio, artefato corrompido ou fonte alterada |
| `memoria bancos status --offline` | verifica somente artefatos e marcadores locais | uso explícito em CI sem Hindsight |
| `memoria fragmentos gerar` | reconstrói o manifesto determinístico do RAG em modo sombra | fonte UTF-8, perfil ou caminho é inválido |
| `memoria fragmentos verificar` | compara manifesto, fontes, algoritmo e fingerprint | qualquer fragmento, fonte ou configuração diverge |
| `memoria contexto --pergunta=... --perfil=... --json` | contexto neutro v2, citado, com escopo e cobertura | manifesto velho, escopo ausente ou entrada inválida |
| `memoria contexto mcp` | a mesma função por MCP stdio | requisição MCP inválida |
| `memoria contexto http` | REST `/contexto` e MCP `/mcp`, somente em loopback | bind, origem ou credencial recusados |
| `memoria adaptadores gerar` | gera manifesto e entradas para cinco clientes sem copiar fatos | configuração ou arquivo do cliente é inválido |
| `memoria adaptadores verificar` | confere schema, manifesto e conteúdo gerenciado | instrução ou conector foi adulterado/ficou velho |
| `memoria adaptadores canary` | confirma projeto, bank, perfil, commit e frescor antes da consulta | qualquer identidade ou provedor ativo não confirma |
| `memoria ciclo iniciar` | prepara os provedores, faz canary e auto-repara estado velho | dependência, documentação, banco ou identidade não confirma |
| `memoria ciclo atualizar` | documenta, valida, sincroniza e repete o canary após mudanças | qualquer etapa do ciclo não confirma |
| `memoria agendador instalar` | registra atualização diária fechada às 02:15 | o agendador do usuário recusa o registro |
| `memoria agendador status` | confirma a tarefa identificada deste projeto | tarefa ausente ou configuração insegura |
| `memoria agendador executar` | atualiza docs, Hindsight e Graphify sob lock compartilhado | ciclo, banco de memória, grafo ou canary falha |
| `memoria indice` | compatibilidade: verifica a cópia documental no Hindsight | documento do núcleo mudou |
| `memoria verificar` | estrutura + catraca + bancos + frescor da skill gerada | qualquer etapa falha |
| `memoria autoteste` | quebra uma cópia de propósito e confere que os validadores reclamam | um validador parou de pegar o que promete |
| `memoria executar ... --json` | ação fechada com lock, checkpoint e isolamento | falha, timeout, lock ou capacidade recusada |
| `memoria avaliar gerar` | reconstrói métricas, drift e manifesto da recuperação | limite absoluto, caso ou baseline regride |
| `memoria avaliar verificar` | gate read-only do corpus, relatório, manifesto e baseline | artefato velho, adulteração ou regressão |
| `memoria avaliar medir` | cria deliberadamente nova linha de base aprovada | caso ou limite atual já está reprovado |
| `memoria skill` | gera a peça de procedimento (skill/comando) a partir do runbook | `--conferir` falha se fonte, gerador ou artefato divergir |

Rode sempre a partir da raiz do projeto. Só `documentar`/`bancos` acessam os provedores
locais configurados; validação estrutural e geração continuam determinísticas.

## Extratores próprios do projeto

O gerador aceita extratores **do projeto**, em qualquer linguagem: um executável
declarado em `padrao.json` → `gerado.extensao_do_projeto` que imprime JSON no stdout —
`[{"nome","id","titulo","corpo"}]`. Um `nome` igual ao de um extrator embutido o
sobrescreve. Modelo pronto em [`exemplos/extratores-projeto.py`](exemplos/extratores-projeto.py);
o primeiro projeto migrado mantém os dele em PHP, pelo mesmo protocolo.
`nome` vira nome de arquivo e aceita apenas letras ASCII, números, ponto, `_` e `-`,
sem barras ou caminho.

> **Limite de confiança:** declarar `gerado.extensao_do_projeto` autoriza a execução
> desse programa por `memoria gerar`, `memoria validar` e `memoria autoteste`. Ele pode
> fazer tudo que o usuário do processo puder fazer, inclusive rede e escrita externa.
> Em CI de contribuição não confiável, revise o extrator antes de executar o pacote.

## O que fica onde — e por quê

| | Mora em | Atualiza como |
|---|---|---|
| validadores e gerador | o pacote (pipx/pip) | `pipx upgrade memoria-evolutiva` |
| `padrao.json`, `docs/`, workflow, extratores próprios | **seu repositório** | `memoria documentar` atualiza o núcleo gerenciado e os derivados |
| serviço Hindsight | máquina local | reconstruído de `docs/`; autoridade zero |
| `docs/gerado/manifesto-fragmentos-v2.json` | seu repositório | `memoria fragmentos gerar`; corpus sombra reproduzível com ACL |
| `docs/gerado/manifesto-adaptadores-v1.json` | seu repositório | `memoria adaptadores gerar`; descoberta reproduzível por cliente |
| `.memoria/executor/` | estado local ignorado | runs, worktrees e patches idempotentes; nunca fonte canônica |
| `docs/avaliacao/` + `baseline-rag-v1.json` | seu repositório | corpus e linha de base versionados; baseline nunca é refeito silenciosamente |
| `docs/gerado/*avaliacao-rag-v1.json` | seu repositório | relatório e manifesto reconstruíveis por `memoria avaliar gerar` |
| `graphify-out/graph.json`, relatórios e marcadores | seu repositório | prova versionável do grafo e da última sincronização; cache e caminhos locais ficam ignorados |
| METODO, RAG, exemplos | este repositório | material de referência; leia daqui, não copie |

Essa divisão é o próprio método aplicado a ele mesmo: os scripts têm **um dono** (este
pacote), e o conteúdo do projeto tem outro (você). Quando o kit era copiado para dentro
de cada projeto, cada cópia era uma bifurcação esperando acontecer — um bug corrigido no
kit não chegava a projeto nenhum.

## Documentos de referência

| Arquivo | O quê |
|---|---|
| [`INSTALAR.md`](INSTALAR.md) | instalação autônoma, política de evidências e limites operacionais |
| [`MIGRAR.md`](MIGRAR.md) | da geração 1 (scripts copiados) para o pacote — destilado de uma migração real |
| [`METODO.md`](METODO.md) | os 14 princípios, a cadeia de documentos, e o erro concreto que gerou cada regra |
| [`RAG.md`](RAG.md) | planejamento de índice semântico, independente de fornecedor |
| [`RAG-HINDSIGHT.md`](RAG-HINDSIGHT.md) | o mesmo, traduzido para o Hindsight — descartável quando trocar |
| [`BANCOS.md`](BANCOS.md) | contrato implementado de Hindsight local + Graphify, confirmação e frescor |
| [`CONTEXTO.md`](CONTEXTO.md) | gateway neutro, perfis, envelope JSON e transportes CLI/MCP/HTTP |
| [`ADAPTADORES.md`](ADAPTADORES.md) | manifesto, descoberta e canary para Codex, Claude, Cursor, Windsurf e Hermes |
| [`CICLO.md`](CICLO.md) | instalação única, bootstrap local e manutenção zero-touch comum aos agentes |
| [`SEGURANCA-MEMORIA.md`](SEGURANCA-MEMORIA.md) | classificação, produto/tenant, audiência, redaction e fallback sem cobertura |
| [`AVALIACAO-RAG.md`](AVALIACAO-RAG.md) | corpus, métricas, baseline, drift e promoção baseada em uso medido |
| [`EVOLUCAO-RAG-AGENTES.md`](EVOLUCAO-RAG-AGENTES.md) | arquitetura-alvo e fases verificáveis para RAG portátil, atendimento e automações |
| [`EXEMPLO-PROJETO-PREENCHIDO.md`](EXEMPLO-PROJETO-PREENCHIDO.md) | um `PROJETO.md` real de ponta a ponta |

## Base metodológica

A estrutura autônoma combina referências complementares, sem deixar a IA escolher um
formato diferente por projeto:

- [arc42](https://arc42.org/overview) para objetivos, restrições, contexto, blocos,
  runtime, implantação, decisões, qualidade, riscos e glossário;
- [C4](https://c4model.com/abstractions) para sistema, containers, componentes e código;
- [Diátaxis](https://diataxis.fr/start-here/) para separar tutorial, procedimento,
  referência e explicação;
- [ADR no arc42](https://docs.arc42.org/section-9/) para contexto, decisão, alternativas
  e consequências de decisões arquiteturalmente significativas.

## Requisitos

Python ≥ 3.10 para o pacote (biblioteca padrão apenas), Hindsight local e Graphify. O
projeto documentado pode ser em qualquer linguagem: o que o gerador varre é configurável
em `padrao.json` → `gerado`, e os extratores próprios rodam na linguagem do projeto.

Para uma instalação deliberadamente sem bancos use `--sem-bancos`; para somente gerar a
estrutura enquanto os serviços locais são preparados, use `--adiar-bancos`. São exceções
explícitas — o padrão normal exige os dois.

## Motor legado em PHP

A primeira implementação, em PHP, está arquivada em [`legado-php/`](legado-php/LEIA-ME.md)
— congelada com paridade byte a byte comprovada contra o motor Python, funcional via
`composer require lastmind-dev/memoria-evolutiva`, mas sem manutenção. Correções e regras
novas entram só aqui. Para trocar de motor: `pipx install --include-deps
"memoria-evolutiva[local] @ git+https://github.com/LastMind-dev/memoria-evolutiva.git@main"`, depois
`memoria gerar` uma vez (a linha `> Gerado por ...` dos derivados muda) e `memoria
verificar`.
