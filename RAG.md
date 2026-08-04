# Planejamento de índice semântico (RAG)

Material de referência do método, como o `METODO.md`. **Não copie para dentro do
projeto** — o que vai para o projeto é o `docs/runbooks/indexacao.md`, que o kit traz
pronto para preencher.

Vale para qualquer ferramenta: Hindsight, pgvector, Qdrant, Weaviate, Chroma, ou o que
vier depois. Há um anexo com a tradução para o Hindsight em `RAG-HINDSIGHT.md`.

---

## O que um índice semântico é dentro deste método

**Um atalho de busca. Nada mais.**

Ele existe porque `grep` não encontra "como a gente lida com pedido duplicado" quando o
documento diz "conciliação de reservas repetidas". Busca por significado resolve isso, e
é a única coisa que ela resolve.

Duas consequências, e as duas são incômodas:

**O índice tem autoridade zero.** É o último item da ordem de desempate, abaixo do
documento rascunho. Um registro do índice nunca é resposta final — é ponteiro para a
fonte, e a resposta sai de lá.

**O índice é reconstruível e descartável.** Se ele for apagado inteiro hoje, nada de
valor se perde: um comando o reconstrói a partir de `docs/`. **Se essa frase não for
verdadeira no seu projeto, você não tem um índice — tem um acervo disfarçado de índice**,
e é o caso mais perigoso desta página, porque ninguém versiona, ninguém revisa e ninguém
sabe o que tem lá dentro.

> O teste, e vale fazer antes de qualquer outra coisa: **apague o índice inteiro num
> ambiente de teste e reconstrua.** O que não voltar era conteúdo único morando no lugar
> errado. Salve isso em `docs/` **antes** de tocar no índice de verdade.

---

## Por que o índice erra em silêncio, que é o problema real

Um registro do índice foi extraído de um documento numa data. O documento mudou. O
registro não.

A busca continua devolvendo o texto antigo **com a mesma confiança de um texto correto**.
Não há sinal, não há erro, não há aviso. Quem consulta recebe um fato desatualizado e age
sobre ele.

É o pior modo de errar que existe num sistema de informação, e é a razão de todo o resto
desta página.

Três defesas, nesta ordem de importância:

1. **Proveniência obrigatória** — todo registro carrega de onde veio e de qual versão.
2. **Detecção de defasagem** — algo compara o estado indexado com o estado atual e falha.
3. **Purga, não correção** — registro sem proveniência é apagado, não consertado.

---

## Decisão 1 — O que entra no índice

### O núcleo: entra sempre

Os documentos que qualquer agente precisa para saber onde o projeto está.

```
docs/PROJETO.md      docs/ESTADO.md      docs/ABERTO.md      docs/GLOSSARIO.md
docs/cronologia/     docs/produto/       docs/funcional/     docs/arquitetura/
docs/decisoes/       docs/politicas/     docs/runbooks/
```

O núcleo é o que **falha duro** quando fica defasado. É pequeno de propósito: indexar
tudo é caro, e fazer de tudo uma falha deixaria o build vermelho sem consertar nada.

### O resto: medido, não bloqueante

Tudo o mais em `docs/` é contado e reportado, sem quebrar o build. Quando um documento
começa a ser consultado de verdade, promova-o ao núcleo.

### O que NUNCA entra

| Não indexe | Por quê |
|---|---|
| **`docs/gerado/`** | é derivado do código; se você quer a resposta certa, leia o código ou o arquivo gerado. Indexar derivado cria um terceiro nível de cópia — e o índice passa a devolver mapa de diretórios de três meses atrás |
| **`docs/_arquivo/`** | é documento cujo assunto deixou de existir — módulo removido, integração desligada. Não confunda com decisão superada: essa **continua** no acervo e **é** indexada, com `doc_status: superado` |
| **`docs/_templates/`** | são moldes com placeholder. A busca vai devolver `<preencha aqui>` como se fosse conteúdo |
| **o próprio código** | mudança de código é diária; o índice nunca acompanha. Para código existe ferramenta melhor: o próprio repositório, com busca literal. **Grafo de símbolos é outra coisa e pode valer — o que não vale é embutir trechos de código num índice semântico que ninguém reindexa** |
| **segredo de qualquer natureza** | senha, token, chave, dado pessoal. O índice costuma ser o lugar do sistema com menos controle de acesso e menos auditoria de todo o projeto |
| **anexo binário** | PDF e planilha entram só depois de virarem markdown em `docs/`. Se o conteúdo importa, ele merece um documento com frontmatter |

> A regra que resume as seis linhas: **indexe o que é canônico e escrito à mão. Nunca o
> derivado, nunca o morto, nunca o secreto.**

---

## Decisão 2 — Como fatiar

Um documento inteiro é grande demais para ser um registro: a busca devolve um `PROJETO.md`
de trezentas linhas quando você perguntou sobre uma regra de autorização. Uma linha é
pequena demais: perde o contexto que dá sentido a ela.

**Fatie por seção de segundo nível (`##`), mantendo o cabeçalho junto.**

```
┌─ registro ──────────────────────────────────────┐
│ docs/PROJETO.md · "## 4. Regras invioláveis"    │  ← título do documento + da seção
│                                                  │     REPETIDOS dentro do texto
│ <o corpo da seção>                              │
└──────────────────────────────────────────────────┘
```

Três regras que evitam os erros comuns:

**Repita o título do documento e o da seção dentro do texto do registro.** Um trecho que
começa em "…exige autorização explícita a cada ação" sem dizer de onde veio é um trecho
que a busca devolve e ninguém sabe interpretar.

**Seção maior que ~1500 palavras vira dois registros, cortando em `###`.** Seção menor que
~50 palavras junta-se à vizinha. Trecho minúsculo casa com quase tudo e polui todo
resultado.

**Nunca corte no meio de uma tabela ou de um bloco de código.** Meia tabela é pior que
nenhuma: parece completa.

### Documento em forma de lista — e por que a regra do `##` não basta

Fatiar por `##` foi pensado para prosa: PROJETO, FDD, HLD, ADR. Três documentos deste
padrão não são prosa, e aplicar a regra padrão neles produz registro ruim.

| Documento | Forma | Fatie por |
|---|---|---|
| `docs/ABERTO.md` | fila numerada que só cresce | **uma entrada por registro** (`ABERTO-0007`), com o número no texto |
| `docs/GLOSSARIO.md` | lista de termos | **um termo por registro**, com o termo repetido no texto |
| `docs/cronologia/` | entradas datadas | **uma entrada por registro**, com a data no texto |

O padrão comum: **onde o documento é uma lista de itens independentes, o item é o
registro.** Juntar cinco entradas de `ABERTO.md` num registro faz a busca devolver quatro
conflitos que ninguém perguntou, e o item certo enterrado no meio.

E onde o documento é uma lista de **regras curtas e relacionadas** — como a seção "Nunca"
do `PROJETO.md` — mantenha juntas. Uma proibição isolada, sem as irmãs, perde o contexto
que faz alguém entender por que aquela lista existe.

> A regra por trás das duas: **fatie na fronteira onde o leitor para de precisar do
> vizinho.** Se ler o item 7 sem o 6 funciona, são dois registros. Se não funciona, é um.

### O caso especial da cronologia

A cronologia é append-only e cresce para sempre. Fatie **por entrada** (`## AAAA-MM-DD —
título`), nunca por arquivo, e inclua a data no texto do registro — porque a pergunta que
se faz à cronologia é quase sempre "quando" ou "por que naquela época".

---

## Decisão 3 — O que cada registro carrega

**Este é o coração da página.** Registro sem estes campos não é indexado; se já estiver
lá, é purgado.

| Campo | Exemplo | Para que serve |
|---|---|---|
| `source_uri` | `docs/funcional/FDD-0003.md#regras` | subir até a fonte canônica. **Sem isto o registro é impossível de verificar e impossível de atualizar** |
| `source_commit` | `7f3a91c` | saber contra qual versão do repositório aquilo era verdade |
| `indexed_at` | `2026-08-04` | saber quanto tempo faz |
| `doc_id` | `FDD-0003` | ligar ao frontmatter, e à cadeia de dependências |
| `doc_tipo` | `fdd` | filtrar por tipo, e aplicar a ordem de desempate. Os valores são os do `padrao.json` → `vocabulario.tipo` — no kit: `entrada`, `estado`, `cronologia`, `prd`, `fdd`, `hld`, `lld`, `adr`, `runbook`, `politica`, `evidencia`. **Copie do seu `padrao.json`, não desta tabela** — vocabulário é decisão de projeto |
| `doc_status` | `verificado` | **não devolver `superado` como se fosse atual** |
| `projeto` | `reservas` | separar projetos que dividem a mesma base |

> **`source_commit` é o campo que quase todo mundo esquece, e é o que permite responder
> "isto ainda vale?".** Sem ele resta a data, que não diz nada — um documento pode ter
> mudado dez vezes desde então, ou nenhuma.

### A regra que dispensa argumento

> **Registro sem proveniência é purgado, não corrigido.**

Parece severo e não é. Um registro sem origem não pode ser verificado, não pode ser
atualizado quando a fonte muda, e não pode ser comparado com nada. Tentar consertar
significa adivinhar de onde ele veio — e adivinhação vira fato com carimbo de verificado.

Se o conteúdo dele for valioso e não existir em `docs/`, **isso é um achado**: alguém
guardou informação única no lugar errado. Salve em `docs/`, com frontmatter, e reindexe
de lá. Só então purgue.

---

## Decisão 4 — Quando reindexar

| Gatilho | O que reindexar | Quem dispara |
|---|---|---|
| documento do núcleo mudou | **o documento inteiro**, refatiado do zero | fim de sessão |
| documento novo no núcleo | o documento inteiro | fim de sessão |
| documento virou `superado` | apaga e **reindexa com `doc_status: superado`** | fim de sessão |
| documento saiu do acervo | **purga**, sem reindexar | fim de sessão |
| mudou o jeito de fatiar ou o esquema | tudo, do zero | quando você mexer nesta página |
| trocou o modelo de embedding | tudo, do zero | inevitável |

As duas últimas linhas doem, e é bom saber disso antes: **mudar a estratégia de
fatiamento ou o modelo de embedding invalida o índice inteiro.** Decida o fatiamento com
calma agora; reindexar tudo depois é caro e ninguém faz na hora certa.

> **"O documento inteiro", não "a seção que mudou".** Reindexar por seção parece mais
> barato e é uma armadilha: mudar uma seção costuma deslocar as fronteiras das vizinhas, e
> você fica sem saber quais registros antigos ainda correspondem a alguma coisa. Refatiar
> um documento inteiro custa pouco; descobrir seis meses depois qual metade do índice está
> podre custa muito.

### Apague antes de gravar. Sempre.

Reindexar um documento que mudou é **duas operações, nesta ordem**:

```
1. apague TODOS os registros daquele documento
2. gere os registros novos, com o commit novo
```

Nunca só a segunda. Se você gravar por cima sem apagar, as seções que mudaram de tamanho
ou de título viram registros novos e **os antigos ficam**. Aí o índice tem duas versões da
mesma seção, ambas plausíveis, e a busca escolhe por semelhança — não por atualidade.

É o erro mais comum e mais silencioso desta ferramenta, e é a versão vetorial exata do
problema que este método inteiro existe para resolver. Por isso vale agrupar os registros
por documento de origem desde o começo: sem esse agrupamento, "apague todos os registros
daquele documento" não é uma operação que você consiga fazer.

### `superado` não é purga

São duas coisas diferentes, e confundi-las custa nos dois sentidos:

**Documento superado continua no índice**, reindexado com `doc_status: superado`. A busca
padrão o exclui; ele volta sob pedido explícito ("o que a gente decidia antes disso").
Purgar de verdade apagaria a resposta para "por que mudamos", que é justamente o que
alguém procura seis meses depois.

**Documento que saiu do acervo é purgado**, sem reindexar. Não existe mais fonte para
apontar, e registro sem fonte é registro que não pode ser verificado.

### Por que o CI não reindexa

Porque o índice quase sempre é alcançado por ferramenta que roda na máquina de quem
trabalha, não no runner. O `validar-indice.php` **não reindexa** — ele torna visível que
precisa, e falha até alguém fazer.

É a mesma filosofia da catraca: a ferramenta não conserta, mas impede que o problema
cresça sem ninguém ver.

### O marcador

`docs/.indexado.json` guarda o hash de cada documento do núcleo na última indexação. O
verificador compara com o estado atual e aponta o que mudou, o que é novo e o que sumiu.

**O hash ignora `verificado_em`, `verificado_commit` e a linha de carimbo do gerador** —
esses mudam a cada commit sem que o fato mude, e sem essa normalização o índice estaria
permanentemente "defasado" por causa de um carimbo.

> `--marcar` grava "isto está indexado". **Rode depois de indexar de verdade, nunca
> antes.** Marcar sem indexar transforma a verificação em teatro — e teatro é pior que
> nada, porque dá confiança falsa.

---

## Decisão 5 — Como o índice é consultado

A regra que precisa estar escrita no `docs/PROJETO.md` do seu projeto, porque é a que os
agentes violam sozinhos:

> **Resultado de busca semântica nunca é resposta final.** É ponteiro. Suba até a fonte
> canônica pelo `source_uri`, leia de lá, e responda de lá.

O fluxo correto tem quatro passos, e o terceiro é o que todo mundo pula:

```
1. buscar no índice          →  encontra candidatos por significado
2. ler o source_uri          →  vai até o documento de verdade
3. conferir status e cadeia  →  superado? o pai caiu? a âncora ainda existe?
4. responder a partir da fonte
```

No passo 3, "cadeia" é o campo `deriva_de` do frontmatter: a lista de documentos dos quais
aquele depende. Se algum deles está `superado`, o documento que você achou pode estar
descrevendo um comportamento abandonado, mesmo estando `verificado`. A Parte III-B do
`METODO.md` descreve a cadeia inteira.

Se o passo 2 for pulado, o índice virou fonte — e é exatamente o que ele não pode ser.

### Filtros que valem a pena configurar

- **Excluir `doc_status: superado`** da busca padrão. Deixe acessível sob pedido explícito
  ("o que a gente decidia antes"), nunca no resultado normal.
- **Desempatar por `doc_status`**, seguindo a ordem de desempate do método:
  `verificado` > `rascunho`. Não existe `doc_status: superado` no resultado padrão porque
  o filtro acima já o tirou, e não existe registro de `doc_tipo: gerado` porque
  `docs/gerado/` nunca é indexado — quando quiser um fato derivado, leia o arquivo gerado
  ou o código, que é a fonte.
- **Mostrar `indexed_at` no resultado.** Um registro de seis meses atrás merece
  desconfiança, e a data na tela é o que produz essa desconfiança.

---

## Os dois níveis, e por que não é um só

```
NÚCLEO        falha dura.   O que qualquer agente lê para saber onde o projeto está.
O RESTO       medido.       Visível, contado, não bloqueia.
```

Se tudo fosse falha dura, o build viveria vermelho e a verificação viraria ruído. Se nada
fosse, o núcleo apodreceria em silêncio — que é o problema original.

A fronteira entre os dois é uma decisão sua, mora em `padrao.json` → `memoria.nucleo`, e
deve **crescer com o tempo**. Quando um documento fora do núcleo começar a ser consultado
de verdade, promova.

---

## Antes de indexar: monte o conjunto de perguntas de referência

Você vai decidir o fatiamento **uma vez**, e mudá-lo depois invalida o índice inteiro.
Decidir no escuro é caro; e é o que quase todo mundo faz.

O antídoto custa vinte minutos: **escreva de 10 a 20 perguntas reais antes de indexar
qualquer coisa**, com a resposta certa anotada ao lado — o arquivo e a seção onde ela
está. Perguntas de verdade, do jeito que alguém digitaria:

```
"pode apagar linha de reserva?"          → docs/PROJETO.md#4-2-nunca
"o que acontece se o parceiro cair"      → docs/funcional/FDD-0002.md#excecoes
"por que a gente não usa webhook"        → docs/decisoes/ADR-0004.md
"quando foi que mudamos o horário"       → docs/cronologia/2026-05.md
```

Guarde em `docs/evidencia/`. Com isso você consegue três coisas que sem isso são chute:

**Escolher o fatiamento comparando.** Indexe com uma estratégia, rode as perguntas, conte
quantas trazem a resposta certa entre as três primeiras. Mude a estratégia, repita. A
diferença entre fatiar por `##` e por `###` deixa de ser opinião.

**Perceber degradação.** Rode as mesmas perguntas a cada trimestre. Se o número caiu, algo
mudou — e você descobre por medição, não porque alguém reclamou.

**Saber quando desligar.** Se o `grep` acerta o mesmo tanto, o índice não está pagando o
que custa.

> Vinte minutos escrevendo perguntas evitam a reindexação completa que você faria seis
> meses depois ao descobrir que o fatiamento estava errado.

---

## Busca por significado não substitui busca literal

O índice existe porque `grep` não encontra "pedido duplicado" quando o documento diz
"conciliação de reservas repetidas". **O inverso também é verdade, e é esquecido com mais
frequência:** busca semântica é ruim para identificador exato.

Procure por `FDD-0003`, `ADR-0007`, um código de erro, um nome de rota ou de tabela — e a
busca vetorial devolve documentos *parecidos com* aquilo, não aquilo. `grep -rn "ADR-0007"
docs/` acha em milissegundos, com precisão perfeita.

| A pergunta é | Use |
|---|---|
| conceito, sintoma, "como a gente lida com…" | índice semântico |
| identificador, código de erro, nome de arquivo, número | `grep` |
| "tudo de tal tipo/status" | filtro por metadado, não busca |

Se a sua ferramenta oferece busca híbrida — lexical e vetorial combinadas — ligue. Se não
oferece, **não force**: `grep` já está instalado, e saber quando usá-lo vale mais que
qualquer ajuste de embedding.

---

## O que isto custa

Duas contas que ninguém faz antes e todo mundo faz depois:

**Indexar.** Um acervo de algumas centenas de registros é barato em qualquer ferramenta —
ordem de centavos a poucos dólares. Não é aqui que dói.

**Reindexar.** Aqui dói. `ESTADO.md` e a cronologia mudam **toda sessão** — são, por
construção, os documentos de maior rotatividade do acervo. Se o seu fluxo reindexa o
núcleo inteiro a cada fim de sessão em vez de só o que mudou, o custo recorrente é uma
ordem de grandeza maior, para nenhum ganho.

É por isso que o marcador existe e é por isso que a tabela de gatilhos diz "só o documento
que mudou". Não é elegância: é a diferença entre um custo que você esquece e um que você
percebe na fatura.

E um aviso de unidade: os limiares de fatiamento desta página estão em **palavras**,
porque é o que dá para contar lendo. Ferramentas cobram e limitam por **token** — em
português, conte de 1,3 a 2 tokens por palavra. Uma seção de 1500 palavras é da ordem de
2500 tokens, dentro do limite de qualquer modelo de embedding atual, mas confira o seu
antes de subir o corte.

---

## Como saber se o índice está fazendo diferença

Um índice que ninguém consulta é custo sem retorno, e é mais comum do que parece.

**A medição:** rode o conjunto de perguntas de referência e conte quantas trazem a resposta
certa entre os três primeiros resultados. Abaixo de dois terços, alguma coisa está errada
— fatiamento, metadado ou o próprio modelo. Repita a cada trimestre e guarde o número em
`docs/evidencia/`: é a única forma de saber se piorou.

**Os sinais qualitativos**, que valem junto com o número e não no lugar dele:

- alguém encontra por significado algo que não saberia procurar por palavra exata;
- o `validar-indice.php` fica verde sem esforço heroico no fim da sessão.

E o sinal de que **não** vale: se você só consulta o índice para achar arquivo que já
sabe o nome, `grep` faz isso melhor, mais rápido e sem defasagem. Desligue com
`memoria.ativo: false` — o resto do método funciona inteiro sem índice nenhum, e um
índice desligado é melhor que um índice mentindo.

---

## Erros que já custaram caro

**Indexar antes de arrumar a documentação.** O índice devolve o que existe. Se a
documentação está bifurcada, ele devolve as duas versões com igual confiança — e agora a
bifurcação tem um megafone. Arrume `docs/` primeiro, indexe depois.

**Deixar conteúdo único só no índice.** Numa reestruturação real, requisitos de negócio
que não existiam em lugar nenhum foram encontrados dentro de registros de importação
antigos, sem nenhuma proveniência. Foram resgatados para `docs/` antes da purga. Se a
purga tivesse vindo primeiro, teriam sumido — e ninguém saberia o que se perdeu.

**Um índice para vários projetos sem separar.** A busca devolve regra de outro projeto,
que parece plausível, e ninguém percebe. É por isso que `projeto` é campo obrigatório.

**Reindexar tudo a cada mudança.** Caro, lento, e ninguém sustenta por duas semanas.
Reindexe o que mudou — é para isso que serve o marcador.
