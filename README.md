# memoria-evolutiva

Memória de projeto que **sobrevive à troca de ferramenta** e **falha o build quando
mente**: `docs/` canônico com frontmatter verificado, cadeia PRD → FDD → HLD → LLD → ADR,
cronologia append-only, catraca de dívida legada e CI de integridade.

Nada aqui depende de fornecedor. São arquivos markdown versionados no seu repositório,
verificados por um pacote Python **sem nenhuma dependência além da biblioteca padrão**.
Qualquer LLM — hoje ou daqui a dois anos, em qualquer ferramenta — abre o repositório e
sabe onde o projeto está. E se todas as ferramentas de IA sumirem, a memória continua lá.

## Instalar

```bash
pipx install memoria-evolutiva     # ou: pip install memoria-evolutiva
cd meu-projeto
memoria instalar --projeto="meu-app" --codigo=src
```

O instalador publica no projeto o que é **do projeto** — a árvore `docs/` com os quatro
arquivos de entrada, os moldes de PRD/FDD/HLD/LLD/ADR, o `padrao.json` comentado, os
ponteiros (`CLAUDE.md`, `AGENTS.md`, `.cursor/`, `.windsurfrules`) e o workflow de CI.
Nunca sobrescreve nada que já exista. Os validadores ficam no pacote, onde `pipx
upgrade` os atualiza — no projeto não mora nenhuma cópia de script para divergir.

Depois de preencher os quatro arquivos de entrada (leia o `INSTALAR.md` — ele conduz as
oito decisões, e `EXEMPLO-PROJETO-PREENCHIDO.md` mostra como fica um `PROJETO.md` de
verdade):

```bash
memoria gerar             # extrai do código o que não se escreve à mão
memoria catraca --medir   # congela a dívida atual (só na instalação)
memoria verificar         # validar + catraca + indice
memoria autoteste         # os validadores pegam mesmo o que prometem?
git add -A && git commit -m "estrutura de memória evolutiva"
```

Enquanto o pacote não estiver no PyPI, instale direto do GitHub:

```bash
pipx install git+https://github.com/LastMind-dev/memoria-evolutiva.git
```

## Os comandos

| Comando | Faz | Falha quando |
|---|---|---|
| `memoria instalar` | publica a estrutura no projeto | — |
| `memoria gerar` | mapa de diretórios, mapa da cadeia — tudo que é derivado | extrator declarado não existe |
| `memoria validar` | frontmatter, vocabulário, ids, **âncoras**, **cadeia**, derivados, ponteiros | âncora morta; derivado editado à mão; `deriva_de` quebrado, invertido ou circular; documento vivo pendurado em pai superado |
| `memoria catraca` | mede a dívida congelada (`--medir` grava a base) | algum contador aumentou |
| `memoria indice` | o índice semântico está em dia? (`--marcar` registra indexação) | documento do núcleo mudou e ninguém reindexou |
| `memoria verificar` | os três acima, devolvendo o pior resultado | qualquer um deles |
| `memoria autoteste` | quebra uma cópia de propósito e confere que os validadores reclamam | um validador parou de pegar o que promete |
| `memoria skill` | gera a peça de procedimento (skill/comando) a partir do runbook | — (`--conferir` avisa quando ela ficou para trás) |

Rode sempre a partir da raiz do projeto. Nenhum comando sobe framework, toca banco ou
faz rede.

## Extratores próprios do projeto

O gerador aceita extratores **do projeto**, em qualquer linguagem: um executável
declarado em `padrao.json` → `gerado.extensao_do_projeto` que imprime JSON no stdout —
`[{"nome","id","titulo","corpo"}]`. Um `nome` igual ao de um extrator embutido o
sobrescreve. Modelo pronto em [`exemplos/extratores-projeto.py`](exemplos/extratores-projeto.py);
o primeiro projeto migrado mantém os dele em PHP, pelo mesmo protocolo.

## O que fica onde — e por quê

| | Mora em | Atualiza como |
|---|---|---|
| validadores e gerador | o pacote (pipx/pip) | `pipx upgrade memoria-evolutiva` |
| `padrao.json`, `docs/`, workflow, extratores próprios | **seu repositório** | são seus; o pacote nunca os toca depois de publicados |
| METODO, RAG, exemplos | este repositório | material de referência; leia daqui, não copie |

Essa divisão é o próprio método aplicado a ele mesmo: os scripts têm **um dono** (este
pacote), e o conteúdo do projeto tem outro (você). Quando o kit era copiado para dentro
de cada projeto, cada cópia era uma bifurcação esperando acontecer — um bug corrigido no
kit não chegava a projeto nenhum.

## Documentos de referência

| Arquivo | O quê |
|---|---|
| [`INSTALAR.md`](INSTALAR.md) | o passo a passo completo, incluindo as oito decisões que só você pode tomar |
| [`MIGRAR.md`](MIGRAR.md) | da geração 1 (scripts copiados) para o pacote — destilado de uma migração real |
| [`METODO.md`](METODO.md) | os 14 princípios, a cadeia de documentos, e o erro concreto que gerou cada regra |
| [`RAG.md`](RAG.md) | planejamento de índice semântico, independente de fornecedor |
| [`RAG-HINDSIGHT.md`](RAG-HINDSIGHT.md) | o mesmo, traduzido para o Hindsight — descartável quando trocar |
| [`EXEMPLO-PROJETO-PREENCHIDO.md`](EXEMPLO-PROJETO-PREENCHIDO.md) | um `PROJETO.md` real de ponta a ponta |

## Requisitos

Python ≥ 3.10, biblioteca padrão apenas — sem framework, sem banco, sem serviço. O
projeto documentado pode ser em qualquer linguagem: o que o gerador varre é configurável
em `padrao.json` → `gerado`, e os extratores próprios rodam na linguagem do projeto.

## Motor legado em PHP

A primeira implementação, em PHP, está arquivada em [`legado-php/`](legado-php/LEIA-ME.md)
— congelada com paridade byte a byte comprovada contra o motor Python, funcional via
`composer require lastmind-dev/memoria-evolutiva`, mas sem manutenção. Correções e regras
novas entram só aqui. Para trocar de motor: `pipx install memoria-evolutiva`, depois
`memoria gerar` uma vez (a linha `> Gerado por ...` dos derivados muda) e `memoria
verificar`.
