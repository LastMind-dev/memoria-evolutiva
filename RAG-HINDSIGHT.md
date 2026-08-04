# Anexo — o guia de RAG traduzido para o Hindsight

Anexo do `RAG.md`. **Leia aquele primeiro** — aqui só está a tradução de cada decisão
para as ferramentas do Hindsight.

Este arquivo é **descartável de propósito.** Quando você trocar de ferramenta, jogue-o
fora e escreva outro; o `RAG.md` continua valendo inteiro. É essa separação que faz o
método sobreviver à troca — e é por isso que o específico mora num anexo e não no corpo
do guia.

---

## Mapa dos conceitos

| No guia | No Hindsight |
|---|---|
| índice / acervo de busca | **bank** (`get_bank` mostra o corrente) |
| registro | **memory**, criada com `retain` |
| agrupador de registros de uma mesma origem | **document** (`document_id` no `retain`) |
| proveniência | `metadata` + `tags` do `retain` |
| busca | `recall` |
| purga de um registro | `list_memories` / `get_memory` para achar o `memory_id`, depois `invalidate_memory` |
| purga de um documento inteiro | `delete_document` |
| purga do bank inteiro | `clear_memories` |

O `document_id` é a peça que mais economiza trabalho depois: **use o caminho do arquivo
como `document_id`.** Assim, quando o documento mudar, `delete_document` remove todos os
registros dele de uma vez, e você reindexa limpo — sem duplicata e sem sobra.

---

## Indexar um documento

Um `retain` por seção, seguindo o fatiamento do guia.

```
mcp__hindsight__retain(
  content:     "docs/PROJETO.md · ## 4. Regras invioláveis\n\n<corpo da seção>",
  document_id: "docs/PROJETO.md",
  context:     "reservas",
  tags:        ["projeto:reservas", "tipo:entrada", "status:verificado",
                "doc:PROJETO", "commit:7f3a91c"],
  metadata:    {
    "source_uri":    "docs/PROJETO.md#4-regras-invioláveis",
    "source_commit": "7f3a91c",
    "indexed_at":    "2026-08-04",
    "doc_id":        "PROJETO",
    "doc_tipo":      "entrada",
    "doc_status":    "verificado",
    "projeto":       "reservas"
  }
)
```

Três detalhes que fazem diferença:

**O `content` repete o nome do documento e o da seção.** O `recall` devolve o texto do
registro; se ele não disser de onde veio, quem lê não sabe interpretar.

**Os mesmos dados vão em `tags` e em `metadata`.** Não é redundância boba: as `tags` são
o que o `recall` filtra; o `metadata` é o que você lê para subir até a fonte. As duas
coisas são usadas em momentos diferentes.

**`context` recebe o nome do projeto.** É o primeiro corte quando um bank atende mais de
um projeto — e um bank quase sempre acaba atendendo mais de um.

### Convenção de tags

```
projeto:<nome>        obrigatória — separa projetos no mesmo bank
tipo:<prd|fdd|...>    o tipo do frontmatter
status:<...>          rascunho | verificado | superado
doc:<ID>              o id do frontmatter, para achar tudo de um documento
commit:<sha>          contra qual versão foi indexado
```

Prefixo com dois-pontos porque tag solta (`verificado`) colide entre dimensões e vira
inútil quando o acervo cresce.

---

## Buscar — e o passo que ninguém pode pular

```
mcp__hindsight__recall(
  query: "como tratamos reserva duplicada",
  tags:  ["projeto:reservas"],
  tags_match: "all"
)
```

Depois do `recall`, **sempre**:

1. leia o `source_uri` de cada resultado que for usar;
2. **abra o arquivo** e leia de lá;
3. confira `status` no frontmatter, e o `deriva_de` — `superado` não é resposta, e pai
   superado torna o filho suspeito mesmo estando verificado;
4. responda a partir do arquivo, e cite o caminho.

> O `recall` devolve texto convincente. É a sua única defesa contra responder com um
> registro de três meses atrás: **subir até a fonte antes de afirmar.**

Para excluir o que já caiu, filtre por status na chamada:

```
tags: ["projeto:reservas", "status:verificado"], tags_match: "all"
```

---

## Reindexar quando um documento muda

A sequência, na ordem — e a ordem importa:

```
1. delete_document(document_id: "docs/funcional/FDD-0003.md")
2. retain(...) uma vez por seção, com o commit NOVO
3. php scripts/validar-indice.php --marcar
```

Apagar antes de gravar evita o erro mais comum e mais silencioso desta ferramenta:
**duas versões da mesma seção convivendo no bank**, uma velha e uma nova, ambas
plausíveis, com a busca escolhendo por semelhança e não por atualidade.

O passo 3 só depois do 2. Marcar antes de indexar é o teatro que o guia descreve.

---

## Purgar registro sem proveniência

`list_documents` mostra o que existe. Registro que não tem `source_uri` no `metadata`
não tem origem conferível — e a regra do guia é purgar, não corrigir.

**Antes de apagar qualquer coisa, leia.** Numa reestruturação real, requisitos de negócio
que não existiam em nenhum outro lugar estavam guardados dentro de registros de
importação antigos, sem proveniência nenhuma. Foram resgatados para `docs/` primeiro. Se
a purga tivesse vindo antes, teriam sumido sem que ninguém soubesse o que se perdeu.

```
1. list_documents()                      → o que existe
2. get_document / recall                 → LEIA antes de apagar
3. salve em docs/ o que for único        → com frontmatter e âncora
4. delete_document(...)                  → só agora
```

> ⚠️ **`delete_document` apaga TODOS os registros daquele documento.** Se de oito
> registros só um está sem proveniência, o passo 4 leva os sete bons junto.
>
> Para tirar um registro isolado: `list_memories` para achar o `memory_id`, `get_memory`
> para confirmar que é ele mesmo, e `invalidate_memory` nesse id. Use `delete_document`
> quando o documento inteiro vai ser reindexado de qualquer forma — que é o caso normal
> de reindexação, e por isso ele aparece primeiro no procedimento acima.

`clear_memories` apaga o bank inteiro. É a ferramenta certa quando você muda o
fatiamento ou o modelo de embedding — e a ferramenta errada em qualquer outra situação.

---

## O que NÃO colocar no bank

Além da lista do guia, duas específicas de assistente com memória:

**Não use `retain` para preferência de conversa como se fosse fato de projeto.** "O
usuário prefere respostas curtas" é memória de assistente; "a conciliação roda às 3h" é
fato de projeto e mora em `docs/`. Misturar os dois faz o `recall` devolver preferência
pessoal quando alguém pergunta sobre o sistema.

**Não deixe `retain` automático gravar decisão de arquitetura.** Decisão vira ADR em
`docs/decisoes/`, e o ADR é que vai para o índice — nunca o contrário. Decisão que só
existe no bank é decisão que some quando você trocar de ferramenta, e é exatamente o
princípio 1 do método sendo violado.

---

## Checklist de uma sessão

```
abertura   recall com tags:["projeto:<nome>"] para o contexto acumulado
           → e sempre subir até docs/ antes de afirmar qualquer coisa

fecho      documento do núcleo mudou?
             delete_document → retain por seção → validar-indice.php --marcar
           documento virou superado?
             delete_document, e reindexe com status:superado (não purgue — é a resposta
             para "por que mudamos", que alguém procura seis meses depois)
           php scripts/validar-indice.php  → tem que ficar verde
```
