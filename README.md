# memoria-evolutiva

Memória de projeto que **sobrevive à troca de ferramenta** e **falha o build quando
mente**: `docs/` canônico com frontmatter verificado, cadeia PRD → FDD → HLD → LLD → ADR,
cronologia append-only, catraca de dívida legada e CI de integridade.

Nada aqui depende de fornecedor. São arquivos markdown versionados no seu repositório,
verificados por scripts PHP sem nenhuma dependência externa. Qualquer LLM — hoje ou daqui
a dois anos, em qualquer ferramenta — abre o repositório e sabe onde o projeto está. E se
todas as ferramentas de IA sumirem, a memória continua lá.

## Instalar

```bash
composer require --dev lastmind-dev/memoria-evolutiva
vendor/bin/memoria instalar --projeto="meu-app" --codigo=src
```

O instalador publica no projeto o que é **do projeto** — a árvore `docs/` com os quatro
arquivos de entrada, os moldes de PRD/FDD/HLD/LLD/ADR, o `padrao.json` comentado, os
ponteiros (`CLAUDE.md`, `AGENTS.md`, `.cursor/`, `.windsurfrules`) e o workflow de CI.
Nunca sobrescreve nada que já exista. Os validadores ficam no `vendor/`, onde `composer
update` os atualiza — no projeto não mora nenhuma cópia de script para divergir.

Depois de preencher os quatro arquivos de entrada (leia o `INSTALAR.md` — ele conduz as
oito decisões, e `EXEMPLO-PROJETO-PREENCHIDO.md` mostra como fica um `PROJETO.md` de
verdade):

```bash
vendor/bin/memoria gerar             # extrai do código o que não se escreve à mão
vendor/bin/memoria catraca --medir   # congela a dívida atual (só na instalação)
vendor/bin/memoria verificar         # validar + catraca + indice
vendor/bin/memoria autoteste         # os validadores pegam mesmo o que prometem?
git add -A && git commit -m "estrutura de memória evolutiva"
```

Enquanto o pacote não estiver no Packagist, instale direto do GitHub acrescentando ao
`composer.json` do projeto:

```json
"repositories": [
    { "type": "vcs", "url": "https://github.com/LastMind-dev/memoria-evolutiva" }
]
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

## O que fica onde — e por quê

| | Mora em | Atualiza como |
|---|---|---|
| validadores e gerador | `vendor/` | `composer update` |
| `padrao.json`, `docs/`, workflow | **seu repositório** | são seus; o pacote nunca os toca depois de publicados |
| METODO, RAG, exemplos | `vendor/lastmind-dev/memoria-evolutiva/` | material de referência; leia de lá, não copie |

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

PHP ≥ 8.1 com as extensões padrão. Só isso — sem framework, sem banco, sem serviço. O
projeto documentado pode ser em qualquer linguagem: o que o gerador varre é configurável
em `padrao.json` → `gerado`.
