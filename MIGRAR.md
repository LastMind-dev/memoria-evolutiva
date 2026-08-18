# Migrar da geração 1 (scripts copiados) para o pacote

Para projetos que instalaram o kit quando os validadores eram copiados para `scripts/`
do próprio repositório. Este guia foi **destilado de uma migração real** — o DAZASYNC,
1.969 arquivos, 167 documentos, 107 legados — e cada passo existe porque um atrito
apareceu lá.

A regra que governa tudo: **a migração troca a ferramenta, nunca o conteúdo.** Os seus
documentos e a sua baseline atravessam intactos. Marcadores de versões anteriores não
são aceitos como prova da política de segurança v4: `memoria bancos sincronizar` cria a
nova confirmação com redaction e fingerprint. Se algum passo pedir para reescrever
conteúdo canônico sem arquivá-lo, desconfie do passo.

---

## 0. Antes — numa cópia ou branch

```bash
git checkout -b migracao-memoria-v2
git add -A && git commit -m "foto de entrada: pré-migração"
```

## 1. Instale o pacote

```bash
pipx install git+https://github.com/LastMind-dev/memoria-evolutiva.git@main
```

Não rode `memoria instalar` ainda — primeiro o `padrao.json`, senão o instalador escreve
um padrão genérico que não descreve o seu projeto.

## 2. Escreva o `padrao.json` a partir da REALIDADE do projeto

Os scripts da geração 1 tinham a configuração hardcoded. Agora ela vira declaração — e
precisa ser a **sua**, não a do exemplo:

| Campo | De onde tirar |
|---|---|
| `projeto` | do frontmatter dos seus docs: `grep -h "^projeto:" docs/PROJETO.md`. **Exatamente igual, caixa incluída** — o validador compara |
| `vocabulario.tipo` | censo real: `grep -rh "^tipo:" docs --include="*.md" \| sort -u`. **Mantenha os tipos antigos** (`decisao`, `dominio`...) e acrescente os da cadeia. Ids `DEC-XXXX` não se renomeiam |
| `cadeia.livres` | inclua `"decisao"` junto com `"adr"` — os ADRs antigos entram no mapa sem mudar de nome |
| `externos.pastas` | as pastas com convenção de outra ferramenta (ex.: `docs/stories/` do Codex) |
| `memoria` | **o marcador da v1** (`docs/.rag-indexado.json`), o núcleo da constante `NUCLEO` do script antigo, e a ferramenta real. A normalização de hash é a mesma — o marcador v1 é lido sem re-marcar |
| `catraca.contadores` | porte um a um (passo 3) |

## 3. Porte os contadores — e prove a paridade SEM remedir

**Nunca rode `--medir` numa migração.** A baseline é história congelada; remedir apaga a
prova de que a régua não mudou.

Porte cada contador do script antigo para o formato de config (`regex`,
`arquivo_sem_padrao`, `markdown_sem_frontmatter` — exclusões viram `excluir`, exigências
viram `exige`), e então:

```bash
memoria catraca      # SEM --medir
```

**Todo contador tem que bater exatamente com a base antiga.** Na migração de referência:
107/24/71/6/3/0/275 — sete de sete, idênticos. Qualquer divergência é regex portado
errado, não "o projeto mudou". Conserte o porte até bater.

## 4. Porte os extratores próprios

Os geradores específicos do projeto (tabelas, rotas, comandos...) saem do script antigo
e viram `scripts/extratores-projeto.php` — arquivo **do projeto**, declarado em
`padrao.json` → `gerado.extensao_do_projeto`. A chave `mapa-diretorios` sobrescreve o
extrator genérico do pacote, se o seu mapa era customizado.

Sem este passo os arquivos gerados ficam **órfãos**: passam na verificação para sempre
(nada os regenera, nada os muda) e envelhecem em silêncio — a mentira exata que o método
combate.

Depois: `memoria gerar` e **commite** — o envelope dos arquivos muda uma vez
(cabeçalho novo), o conteúdo não deve mudar. Leia o diff para confirmar.

## 5. Rode o instalador — e reconcilie o que ele publica

```bash
memoria instalar --projeto="<o-mesmo-do-padrao.json>" --codigo=<pasta> --adiar-bancos
```

Ele nunca sobrescreve; mas **publica coisas que o seu projeto v1 talvez já tenha com
outro nome**, e aí nascem duas jurisdições para o mesmo assunto:

| Publicado | Se o projeto já tem | Faça |
|---|---|---|
| `docs/runbooks/sessao.md` | um runbook de sessão próprio (ex.: `fim-de-sessao.md`) | **apague o publicado** — o do projeto é o canônico |
| `docs/produto/`, `docs/funcional/`, `docs/evidencia/` vazios | `docs/prd/`, `docs/evidence/` etc. com conteúdo | **apague as pastas vazias publicadas** — um assunto, um lugar |
| `docs/runbooks/indexacao.md` | (a v1 não tinha) | mantenha e preencha |

## 6. Varra os comandos antigos da documentação — TODA ela

```bash
grep -rn "php scripts/" docs/ *.md | grep -v _arquivo
```

Cada ocorrência vira o comando `memoria` equivalente. **Não confie só no
validador aqui**: âncoras quebradas ele pega (o runbook que ancorava nos scripts
arquivados quebrou o build na hora), mas **comando citado em prosa ele não lê** — na
migração de referência, o `PROJETO.md` §6/§7 ficou mandando rodar scripts extintos e só
a leitura fria pegou.

Aproveite e confira os ponteiros da raiz: stub que não cita `docs/PROJETO.md` ganha a
linha e entra em `ponteiros.arquivos`.

## 7. Arquive os scripts antigos — não apague

```bash
mkdir -p docs/_arquivo/scripts-v1
git mv scripts/{validar-*,gerar-docs,gerar-skill}.php docs/_arquivo/scripts-v1/
```

Script que não tem equivalente no pacote (verificador de vault, utilitários seus)
**fica** em `scripts/` — o pacote não manda no que é só seu.

## 8. Troque o CI

Copie o stub do pacote (no repositório: `memoria_evolutiva/stubs/.github/workflows/documentacao.yml`)
para `.github/workflows/` do projeto — ou rode `memoria instalar` de novo: ele publica o
que faltar sem sobrescrever o que existe.

Confira `branches:` se o repositório não usa `main`. Se os seus extratores próprios são
noutra linguagem (ex.: PHP), acrescente o interpretador dela no workflow — o stub tem o
comentário indicando onde.

## 9. Índice: o vermelho esperado, e o único jeito honesto de sair dele

`memoria indice` vai reprovar listando exatamente: os docs que a migração
alterou (runbook, gerados) e os que ela criou. **Isso é o sistema funcionando.**

1. Reindexe esses documentos **de verdade** na sua ferramenta (delete → retain, com
   proveniência).
2. Se você alinhar o núcleo à recomendação do `RAG.md` (tirar `docs/gerado/` — derivado
   não se indexa), **purgue os registros de gerado** do índice.
3. Só então: `memoria bancos sincronizar` (o marcador nasce após leitura confirmada).

Marcar sem indexar transforma a verificação em teatro.

## 10. Feche

```bash
memoria verificar && memoria autoteste
```

Entrada na cronologia contando a migração (ferramenta trocada, baseline preservada por
paridade, o que saiu do núcleo), `ESTADO.md` reescrito, commit. E o teste que importa:
uma sessão nova, sem contexto, começando pelo `PROJETO.md` — na migração de referência
ela respondeu 8 de 8 perguntas e ainda achou o que este guia agora manda varrer.

---

## Checklist

- [ ] branch/cópia + commit de entrada
- [ ] `pipx install` (o comando `memoria` no PATH)
- [ ] `padrao.json` escrito da realidade (nome, vocabulário, núcleo, marcador v1)
- [ ] contadores portados · `memoria catraca` **sem** `--medir` · paridade exata
- [ ] extratores próprios em `scripts/extratores-projeto.<ext>` (protocolo neutro: executável → JSON) · `gerar` · diff só de envelope
- [ ] `memoria instalar` · publicados reconciliados (runbook de sessão, pastas duplicadas)
- [ ] `grep -rn "php scripts/" docs/ *.md` → zero fora de `_arquivo`
- [ ] scripts v1 arquivados; os só-seus ficam
- [ ] CI trocado
- [ ] bancos: sincronizar Hindsight+Graphify → `memoria bancos status`
- [ ] `verificar` + `autoteste` verdes · cronologia + ESTADO · leitura fria


---

## Anexo — trocar de MOTOR (PHP legado → Python), sem migrar nada

Para projetos que já estão na geração 2 via Composer (`vendor/bin/memoria`) e vão para o
motor Python. Não é migração: o conteúdo, a baseline e o marcador de índice **já são
compatíveis** (paridade byte a byte, provada na árvore de referência — mesmos números de
catraca, marcador lido verde nos dois sentidos).

```bash
pipx install git+https://github.com/LastMind-dev/memoria-evolutiva.git@main
memoria validar          # deve reprovar SÓ os derivados — ver abaixo
memoria gerar            # a linha "> Gerado por ..." muda de motor; regere UMA vez
memoria verificar        # verde
git add -A && git commit -m "motor de validação: vendor/bin/memoria → memoria (pipx)"
```

1. **Os derivados reprovam uma vez, por desenho.** O envelope dos arquivos gerados
   carimba o motor (`> Gerado por ...`). `memoria gerar` + commit resolve; qualquer
   outra falha de `validar` é problema real — pare e olhe.
2. **Extratores próprios**: o arquivo declarado em `gerado.extensao_do_projeto` precisa
   falar o protocolo neutro — executável que imprime JSON no stdout. Se ele era um
   `return [...]` PHP da era Composer, acrescente o bloco de modo CLI (o do projeto de
   referência, `scripts/extratores-projeto.php`, mostra o padrão: `if (realpath($argv[0])
   === __FILE__) { ... echo json_encode(...); exit(0); }` antes do `return`). O motor
   PHP continua aceitando o mesmo arquivo.
3. **Comandos documentados**: `grep -rn "vendor/bin/memoria" docs/ *.md .github/` e troque
   pelo comando `memoria` — inclusive no workflow de CI (o stub novo instala Python em
   vez de PHP).
4. **Composer**: `composer remove --dev lastmind-dev/memoria-evolutiva` quando nada mais
   citar `vendor/bin/memoria`. Se os extratores próprios são em PHP, o PHP da máquina
   continua sendo usado por eles — só o vendor sai.
