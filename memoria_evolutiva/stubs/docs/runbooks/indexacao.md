---
id: RUN-INDEXACAO
tipo: runbook
projeto: <NOME-DO-PROJETO>
titulo: Indexação e manutenção do índice semântico
status: rascunho
ancoras:
  - padrao.json
---

# Indexação — procedimento deste projeto

> **Se este projeto não tem índice semântico**, ponha `memoria.ativo: false` no
> `padrao.json` e apague este arquivo. O resto do padrão funciona inteiro sem índice, e
> um runbook que descreve algo que não existe é a primeira mentira do acervo.
>
> O raciocínio por trás de cada decisão aqui está no `RAG.md` do kit. Este documento é só
> o procedimento **deste** projeto — preencha os `<colchetes>`.

## Ferramenta

**Índice:** `<qual — Hindsight, pgvector, Qdrant...>`
**Onde vive:** `<endereço ou identificador do acervo>`
**Quem alcança:** `<a máquina de quem trabalha, não o runner do CI>`

## O que entra

**Núcleo** — falha dura quando defasa. A lista real está em `padrao.json` →
`memoria.nucleo`; não a duplique aqui, aponte para lá.

**Nunca entra:** `docs/gerado/` · `docs/_arquivo/` · `docs/_templates/` · código ·
qualquer segredo.

> `_arquivo/` é assunto que deixou de existir. **Decisão superada não é isso** — ela
> continua no acervo e **é** indexada, com `doc_status: superado`, fora da busca padrão.

## Fatiamento

Uma seção de segundo nível (`##`) por registro, com o título do documento e o da seção
repetidos dentro do texto. `ABERTO.md` fatia por entrada, `GLOSSARIO.md` por termo,
cronologia por entrada datada. Nunca cortar tabela ou bloco de código no meio.

## Campos obrigatórios de cada registro

```
source_uri     caminho#ancora do documento de origem
source_commit  sha curto do commit indexado
indexed_at     AAAA-MM-DD
doc_id         id do frontmatter
doc_tipo       tipo do frontmatter
doc_status     rascunho | verificado | superado
projeto        <NOME-DO-PROJETO>
```

> **Registro sem `source_uri` e `source_commit` é purgado, não corrigido.** Antes de
> purgar, leia: conteúdo único que só existe no índice é um achado, e vai para `docs/`
> primeiro.

## Comandos deste projeto

```bash
# reindexar um documento que mudou — APAGAR ANTES DE GRAVAR, sempre
<comando de apagar todos os registros daquele documento>
<comando de gravar os registros novos, com o commit novo>

# conferir se o índice está em dia
vendor/bin/memoria indice

# registrar que foi indexado — DEPOIS de indexar de verdade
vendor/bin/memoria indice --marcar
```

Gravar por cima sem apagar deixa duas versões da mesma seção convivendo, e a busca
escolhe por semelhança — não por atualidade. É o erro mais comum e mais silencioso.

## Consulta — o passo que não se pula

```
1. buscar no índice
2. abrir o source_uri e LER O DOCUMENTO
3. conferir status e a cadeia deriva_de
4. responder a partir do documento, citando o caminho
```

**Resultado de busca nunca é resposta final.** É ponteiro.

## Perguntas de referência

`<aponte para o arquivo em docs/evidencia/ com as 10–20 perguntas reais e a resposta
certa de cada uma>`

Rode-as a cada trimestre e conte quantas trazem a resposta certa entre os três primeiros
resultados. Abaixo de dois terços, alguma coisa está errada. É a única forma de saber se
o índice piorou.

## Quando reindexar tudo do zero

- mudou a estratégia de fatiamento
- trocou o modelo de embedding
- o acervo foi reestruturado

Nos três casos: limpe o acervo inteiro e reconstrua. Reindexação parcial por cima de
esquema antigo deixa registros incompatíveis convivendo.

## Teste de descartabilidade

**Uma vez por semestre, num ambiente de teste:** apague o índice inteiro e reconstrua a
partir de `docs/`.

O que não voltar era conteúdo único morando no lugar errado — e o lugar errado é qualquer
lugar que não seja versionado. Salve em `docs/` antes de repetir.

Se este teste for assustador de fazer, o índice deixou de ser derivado e virou acervo.
Isso é o diagnóstico, não a conclusão: o conserto é trazer o conteúdo para `docs/`.
