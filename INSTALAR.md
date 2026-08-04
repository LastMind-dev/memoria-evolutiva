# Instalar — 20 minutos até o primeiro build verde

Este é o caminho prático. O **porquê** de cada peça está no `METODO.md`; leia depois,
ou quando alguma decisão da Parte IV parecer arbitrária.

> **O caminho recomendado é via Composer** — os validadores ficam no `vendor/`, com um
> dono só, e `composer update` corrige todos os seus projetos de uma vez. Quando o kit
> era copiado para dentro de cada projeto, cada cópia dos scripts era uma bifurcação
> esperando acontecer: bug corrigido no kit não chegava a projeto nenhum. É o próprio
> método aplicado a ele mesmo — um fato, um dono.

---

## O que este kit é

Uma estrutura de documentação que **falha o build quando mente**, e um método para
manter a história do projeto de forma que qualquer modelo de linguagem — hoje ou daqui
a dois anos, em qualquer ferramenta — consiga abrir o repositório e saber onde o
projeto está sem que ninguém precise explicar.

Não depende de nenhum fornecedor. São arquivos markdown no seu repositório, mais um pacote
Composer de validadores sem dependência externa. Se todas as ferramentas de IA que você usa hoje
desaparecerem, a memória continua lá.

---

## 0. Antes de copiar nada

**Se o projeto já existe, audite antes de criar.** É o erro que mais custa: gente que
instala a estrutura por cima de um projeto que já tem documentação e acaba com duas —
a antiga que ninguém apaga e a nova que ninguém preenche.

Liste o que já existe e responda: **onde a verdade mora hoje?** Pastas de documentação,
notas fora do repositório, wiki, README com instruções de execução, base de RAG. Cada
uma dessas vai precisar ganhar uma jurisdição exclusiva ou ser aposentada — a Parte V,
Fase 2 do `METODO.md` conduz isso.

Projeto novo: pode pular direto para o passo 1.

---

## 1. Instale o pacote

```bash
composer require --dev rechi/memoria-evolutiva
```

Enquanto não estiver no Packagist, acrescente antes ao `composer.json` do projeto:

```json
"repositories": [
    { "type": "vcs", "url": "https://github.com/<seu-usuario>/memoria-evolutiva" }
]
```

Isso traz os validadores para `vendor/` e o comando `vendor/bin/memoria`. **Nenhum
script é copiado para o seu repositório** — no projeto só vai morar o que é seu.

Os documentos do método (`METODO.md`, `RAG.md`, este arquivo, o exemplo preenchido)
ficam em `vendor/rechi/memoria-evolutiva/` — leia de lá, não copie.

> **Projeto sem Composer?** Baixe o repositório do pacote para qualquer pasta fora do
> projeto e rode `php <pasta>/scripts/iniciar-estrutura.php` a partir da raiz do
> projeto. Tudo funciona igual; só os comandos ficam mais longos, e o workflow de CI
> publicado assume Composer — ajuste-o.

Se o projeto já tem um `CLAUDE.md` ou `AGENTS.md` com conteúdo, atenção no passo
seguinte: o instalador nunca sobrescreve nada, mas o conteúdo que estiver lá é fato de
projeto e o lugar dele é `docs/PROJETO.md`. **Mover é trabalho seu** — mova, e só então
deixe o ponteiro.

## 2. Rode o instalador — na raiz do projeto

```bash
vendor/bin/memoria instalar --projeto="meu-app" --codigo=src
```

Ele publica no projeto o que é do projeto: a árvore `docs/` com os quatro arquivos de
entrada e os moldes de PRD/FDD/HLD/LLD/ADR, o `padrao.json` comentado, os ponteiros de
raiz (`CLAUDE.md`, `AGENTS.md`, `.cursor/`, `.windsurfrules`) e o workflow de CI.

`--codigo` é a pasta que o gerador varre (`src`, `app`, `lib`, `packages`...).
Acrescente `--indice` se o projeto usa RAG ou índice semântico.

Ele troca `<NOME-DO-PROJETO>` pelo nome real nos modelos e transforma
`docs/cronologia/AAAA-MM.md` no mês corrente. O `padrao.json` publicado vem com o nome
de exemplo; o instalador preenche o real **só se o valor ainda for o do exemplo** —
decisão sua ele nunca sobrescreve. Rodar de novo não estraga nada.

> Se o `padrao.json` ficasse com o nome de exemplo, todo documento gerado sairia
> carimbado errado **com o build verde**. Por isso o `memoria validar` compara o
> `projeto:` de cada documento com o do `padrao.json` — confira na saída do instalador
> que o nome que apareceu é o seu.

## 3. Preencha os quatro arquivos de entrada — nesta ordem

Esta é a única parte que ninguém pode fazer por você.

| Arquivo | O que vai dentro |
|---|---|
| `docs/PROJETO.md` | o que o projeto é, a jurisdição de cada acervo, o que é proibido, o formato de autorização, como você trabalha. |
| `docs/ESTADO.md` | onde o projeto está hoje. Uma página, no máximo. |
| `docs/ABERTO.md` | normalmente começa vazio — **menos** o que sobrar do passo abaixo. |
| `docs/GLOSSARIO.md` | os termos que você já explicou duas vezes. |

### E a documentação de engenharia?

O kit traz os moldes de **PRD, FDD, HLD, LLD e ADR** em `docs/_templates/`, cada um com as
seções que importam e o comentário dizendo o erro que cada seção evita.

**Não escreva nenhum deles agora.** A regra que evita o padrão morrer de burocracia:

> Nenhum documento é obrigatório. A cadeia é obrigatória quando existe.

Você pode ter um FDD sem PRD, um ADR solto, um HLD cobrindo três funcionalidades. O que
não pode é um documento que não diz de onde veio — é para isso que serve o campo
`deriva_de`, e é ele que o validador confere. A Parte III-B do `METODO.md` explica a cadeia
inteira; o mapa dela é **gerado** em `docs/gerado/cadeia-documentos.md`.

**As oito decisões da Parte IV do MÉTODO moram em dois lugares**, e é bom saber qual é
qual antes de começar:

| # | Decisão | Onde vai |
|---|---|---|
| 1 | quais acervos existem, quem manda em quê | `docs/PROJETO.md` |
| 2 | vocabulário de `tipo` e `status` | `padrao.json` → `vocabulario` (passo 4) |
| 3 | o que é gerado, por qual script | `padrao.json` → `gerado` (passo 4) |
| 4 | quais regras viram catraca | `padrao.json` → `catraca` (passo 4) |
| 5 | tem índice? qual o núcleo? | `padrao.json` → `memoria` (passo 4) |
| 6 | quem commita, e quando | `docs/PROJETO.md` |
| 7 | formato de autorização para ação irreversível | `docs/PROJETO.md` |
| 8 | como o dono trabalha | `docs/PROJETO.md` |

> **Um `PROJETO.md` genérico é pior que nenhum**, porque parece pronto. Se você não sabe
> responder a uma das oito, **escreva que ainda não está decidido e abra a entrada em
> `ABERTO.md`** — isso é informação verdadeira e útil, e é por isso que o `ABERTO.md`
> costuma nascer com uma ou duas entradas em vez de vazio. Preencher com o que soa
> razoável é o que produz documento que mente.

**Antes de escrever o `PROJETO.md`, leia `EXEMPLO-PROJETO-PREENCHIDO.md`.** É um
`PROJETO.md` real de ponta a ponta, com a explicação do que cada seção faz que um
preenchimento apressado não faz. Economiza a primeira versão inútil.

## 4. Configure os contadores da catraca

Abra `padrao.json` → `catraca.contadores`. Vem um só: documento sem frontmatter. O
bloco `_exemplos_de_contador`, no fim do arquivo, tem moldes para copiar.

Vira catraca a regra que um `grep` decide sozinho. Regra que exige entender semântica —
"o nome da variável faz sentido?" — não vira contador; fica documental, em
`docs/politicas/`.

Duas coisas que só se descobrem lendo o código dos scripts, então estão aqui:

- **`excluir` casa por trecho de caminho, não por pasta.** `"/config/"` exclui qualquer
  caminho que contenha `/config/`. Se o seu projeto não tem pasta `config/` e sim uma
  classe `src/Config.php`, o trecho a excluir é `"Config.php"`.
- **`onde` é relativo à raiz do repositório**, e o contador varre recursivamente.

Este é também o momento de decidir as decisões 2, 3 e 5 da tabela acima — vocabulário, o
que é gerado e o núcleo do índice. Elas moram neste arquivo, não no `PROJETO.md`.

## 5. Gere, meça, verifique

```bash
vendor/bin/memoria gerar                  # extrai do código o que não se escreve à mão
vendor/bin/memoria catraca --medir     # congela a dívida atual como linha de base
vendor/bin/memoria validar                # precisa passar
vendor/bin/memoria autoteste                   # os validadores pegam mesmo o que prometem?
```

**Olhe a saída do gerador pelo menos uma vez.** A verificação de derivado confere se a
saída é *reprodutível*, não se ela é *verdadeira* — um extrator com bug produz o mesmo
resultado errado toda vez e passa. Abra `docs/gerado/` e confira se os números batem com
o que você sabe do seu projeto.

O `memoria autoteste` quebra uma **cópia temporária** do projeto de propósito, uma coisa por
vez, e confere que o validador certo reclama. Nada é alterado no seu repositório. É o
teste do alarme de incêndio: apertar o botão. Rode-o de novo sempre que mexer no
`padrao.json`.

O `--medir` só na instalação. Dali em diante, qualquer número que **aumente** quebra o
build; o passivo antigo fica congelado e visível. Quando um contador chegar a zero,
promova a regra a falha dura.

### Se o projeto tem índice semântico (RAG)

Antes de indexar qualquer coisa, **leia o `RAG.md`** — ele decide o que entra, como fatiar,
quais metadados cada registro carrega e quando reindexar. Errar o fatiamento agora custa
uma reindexação completa depois.

Preencha `docs/runbooks/indexacao.md` com o procedimento deste projeto, indexe o núcleo
listado em `padrao.json` → `memoria.nucleo`, e **só então**:

```bash
vendor/bin/memoria indice --marcar
```

Marcar sem indexar de verdade transforma a verificação em teatro.

Se o projeto **não** tem índice: `memoria.ativo: false` no `padrao.json` e apague
`docs/runbooks/indexacao.md`. O método funciona inteiro sem índice — e um runbook que
descreve algo inexistente é a primeira mentira do acervo.

## 6. Commite e confira o CI

```bash
git add -A && git commit -m "estrutura de memória evolutiva"
```

As verificações rodam a cada push e a cada pull request. **Precisa ficar verde no
primeiro commit** — é por isso que a catraca existe. Build que nasce vermelho ninguém
olha, e em duas semanas a verificação inteira vira ruído que todo mundo aprende a
ignorar.

> O workflow dispara em `push` para **`main`**. Se o seu repositório usa `master` ou
> outro nome, ajuste `branches:` em `.github/workflows/documentacao.yml` — senão o CI
> nunca roda no push e você vai achar que está verde sem nunca ter sido testado.

---

## 7. O teste que realmente importa

Abra uma sessão nova, num modelo que **nunca viu este projeto**, e mande:

> Comece por `docs/PROJETO.md` e siga a ordem de leitura que ele indica. Depois me diga:
> onde o projeto está, o que está em conflito, e o que eu não posso fazer sem
> autorização.

O pedido é "comece por `PROJETO.md` **e siga a ordem que ele indica**", não "leia só o
`PROJETO.md`". O `PROJETO.md` de propósito não responde onde o projeto está — isso é
jurisdição do `ESTADO.md`. O que está sendo testado é se ele **conduz** até lá sozinho.

**Leia a parte que ele errar com muito mais atenção do que a parte que ele acertar.**
Cada erro é um buraco no documento, não um defeito do modelo. Corrija o documento e
repita com uma sessão nova — nunca com a mesma, que já foi contaminada pela resposta
anterior.

Na prática esse teste encontra mais defeito que qualquer revisão feita por quem escreveu.
Numa aplicação real, ele encontrou dezessete — incluindo pastas descritas como vazias
que tinham conteúdo, uma ordem de leitura congelada num mês que já tinha passado, e três
significados diferentes para a mesma palavra que ninguém tinha percebido.

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
| `memoria instalar` | instala | — |
| `memoria gerar` | extrai do código o que não deve ser escrito à mão | extrator declarado não existe |
| `memoria validar` | frontmatter, vocabulário, ids, **âncoras**, derivados, ponteiros | âncora aponta para arquivo inexistente; derivado editado à mão ou desatualizado; ponteiro virou fonte paralela |
| `memoria catraca` | mede a dívida congelada | algum contador aumentou |
| `memoria indice` | o índice semântico está em dia com os documentos | documento do núcleo mudou desde a última indexação |
| `memoria autoteste` | quebra uma cópia de propósito e confere que os validadores reclamam | algum validador parou de pegar o que promete |
| `memoria skill` | monta a peça de procedimento (skill/comando) a partir do runbook | — (`--conferir` avisa quando a peça ficou para trás) |

Nenhum sobe framework, toca banco ou faz rede. Rodam em Linux, macOS e Windows.

**Não edite os scripts.** Se precisar mudar comportamento, provavelmente falta uma opção
no `padrao.json` — abra uma entrada em `docs/ABERTO.md` em vez de editar. Script alterado
localmente é a primeira peça a divergir quando o kit for atualizado.
