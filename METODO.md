# Método da Memória Evolutiva

## Como fazer um projeto ter memória que sobrevive à troca de ferramenta

**Versão 1 · 2026-08-04 · destilado da reestruturação do DAZASYNC**

---

## Para quem é isto

Você tem um projeto de software. Trabalha nele com ajuda de LLM — talvez mais de uma. Quer que:

- qualquer modelo, em qualquer ferramenta, entenda o projeto em cinco minutos e opere com segurança;
- o que foi decidido em março continue explicando o código em novembro;
- a documentação **não possa** mentir sem que alguém perceba;
- nada essencial dependa de um fornecedor específico continuar existindo.

Este documento é o método. Os arquivos que o acompanham são o kit.

**Termos técnicos são explicados entre parênteses na primeira aparição.**

---

## PARTE I — O problema

### 1. Por que documentação apodrece

Não é preguiça. É estrutural, e tem três causas que se reforçam:

**O documento e o código vivem em ritmos diferentes.** O código muda todo dia; o documento muda quando alguém lembra. A diferença cresce sozinha.

**Nada verifica.** Um documento errado se parece exatamente com um documento certo. Não há compilador para prosa. Quem lê não sabe se pode confiar, e quem escreveu já esqueceu.

**Cópia se bifurca.** No instante em que o mesmo fato existe em dois lugares, os dois começam a divergir. E o lado que diverge mais é sempre aquele onde ninguém trabalha — que é o mesmo lado onde alguém vai procurar depois.

### 2. Por que a memória de IA não resolve

A resposta intuitiva é usar a memória da ferramenta: memória do ChatGPT, Projects do Claude, um banco vetorial.

Três problemas, em ordem de gravidade:

**Não é portátil.** Some quando você troca de ferramenta, e nenhuma outra consegue ler.

**Não tem as três coisas que o git dá de graça:** cronologia real (cada commit é datado), diff (dá para ver o que mudou entre duas versões), e revisão (alguém aprova antes de virar verdade).

**Erra em silêncio.** Um fato extraído há seis meses de um documento que mudou continua sendo devolvido com a mesma confiança de um fato correto. É o pior modo de errar, porque não há sinal.

> **Princípio 1 — O que mora dentro de uma ferramenta é cache, não memória.**
> Memória é arquivo versionado. Tudo mais é conveniência descartável.

### 3. O sintoma que denuncia

Se você reconhece algum destes, o problema já existe no seu projeto:

- Duas versões do mesmo documento em lugares diferentes, com datas diferentes
- Um documento que cita caminho de arquivo que não existe mais
- Uma decisão "em aberto" num lugar e "fechada" em outro
- Um agente de IA que reabre discussão já encerrada
- Alguém perguntando "onde está a versão certa disso?"

Nenhum é grave sozinho. Juntos, significam que **ninguém consegue mais confiar em nada sem conferir**, e conferir custa mais que reescrever.

---

## PARTE II — Os princípios

Catorze. Cada um nasceu de um erro concreto, e o erro está anotado — porque princípio sem a história que o gerou vira slogan.

### 1. O que mora dentro de uma ferramenta é cache, não memória

Já enunciado. É o que decide todo o resto.

**Consequência prática:** se um procedimento importante só existe como skill instalada, prompt salvo ou memória de assistente, ele não existe. Traga para arquivo versionado e trate a cópia dentro da ferramenta como artefato gerado.

### 2. Um fato, um dono

**Acervo** é qualquer lugar onde documentação do projeto se acumula: a pasta `docs/` do
repositório, um cofre de notas pessoais, uma wiki, uma base de RAG. Todo projeto tem pelo
menos um; a maioria descobre tarde que tem três.

Cada acervo manda em um assunto **exclusivo**. Nunca dois.

| Acervo típico | Manda em | Autoridade |
|---|---|---|
| `/docs` no repositório | todo fato sobre o código | canônica |
| Notas pessoais / vault | metodologia, exploração, contexto que cruza projetos | canônica **fora do código** |
| Índice semântico / RAG | recuperação por significado | **zero. sempre derivado** |

*O erro que gerou:* um mesmo documento de especificação funcional em v1.4 no repositório e v1.1 no cofre de notas. A decisão de usar uma API como principal estava fechada num lado e redigida como pergunta em aberto no outro. Ninguém tinha copiado de má-fé — o documento nasceu num lugar, foi copiado "só para consultar" no outro, e os dois seguiram evoluindo.

### 3. Ordem de desempate literal

Escrita, numerada, no documento de entrada. Não implícita.

```
1. o código                    (verdade última)
2. o que é gerado do código    (derivado, reprodutível)
3. documento verificado
4. documento rascunho
5. acervo secundário
6. índice semântico
```

**Sem ela, o agente inventa** — e inventa razoavelmente, escolhendo o documento mais recente, que é frequentemente o mais errado.

### 4. Fluxo de mão única

```
exploração ──promove──► canônico ──indexa──► índice
    ▲                                          │
    └────────── nunca volta ◄─────────────────┘
```

Descoberta nasce sem cerimônia no acervo de exploração. Quando vira fato estável, é **movida** — não copiada — para o canônico, e no lugar de origem fica um link de uma linha.

**Cópia é proibida nas duas direções.** É a cópia que produz a bifurcação.

### 5. Derivado nunca é editado à mão

O que é gerado do código fica em pasta própria, com aviso no topo, e é **reprodutível**: rodar o gerador duas vezes produz saída idêntica.

A verificação compara a saída atual com a commitada. Divergiu, é porque o código mudou e ninguém regerou — ou porque alguém editou à mão.

*Detalhe que custou uma rodada:* se o gerador produzir saída não determinística — ordem de leitura do sistema de arquivos, timestamp, caminho absoluto — o diff acusa mudança sem nada ter mudado, e a verificação vira ruído. **Ordene tudo. Não carimbe o que não precisa.**

Essas três são as causas que aparecem primeiro, não as únicas. A família é maior: ordem de iteração de dicionário em linguagens que não a garantem, ordenação dependente de *locale*, hash com semente aleatória por processo, número de trabalhadores em paralelo. O teste é sempre o mesmo e não exige saber a lista: **rode duas vezes seguidas e compare byte a byte** — e rode uma terceira numa máquina diferente da sua, porque é lá que a diferença aparece.

*Erro que este princípio quase não pegou:* o único extrator deste kit, na primeira versão, só contava arquivos dentro de subpastas. Num projeto com tudo solto na raiz, ele escrevia "Total: 0 arquivos" — e **passava na verificação**, porque a saída era perfeitamente reprodutível. Reprodutível e falsa. A verificação de derivado confere consistência, não veracidade; a veracidade ainda depende de alguém ler a saída pelo menos uma vez.

### 6. Âncora verificada

Documento que descreve código declara, no cabeçalho, quais arquivos descreve:

```yaml
ancoras:
  - src/servicos/Pagamento.php
  - config/pagamento.php
```

E a verificação confere que cada um existe.

**É a peça de melhor retorno pelo que custa.** Duas linhas de cabeçalho e uma checagem de existência de arquivo — e é o único mecanismo que decide sozinho se um documento envelheceu. Documento que cita caminho morto vira mentira silenciosa, e é o tipo de erro que sobrevive anos.

*O erro que gerou:* uma nota especificava uma rota e um componente que nunca foram criados. O código implementou outros caminhos **no mesmo dia**, e ninguém percebeu por mais de um mês.

### 7. Trava é código, não prompt

Regra que existe só em instrução de agente não é regra, é intenção.

Todo documento normativo carrega um campo dizendo **qual código a verifica**. Vazio significa "isto ainda é só texto" — e ficar vazio é informação, não vergonha.

*Medida real:* três políticas de segurança e de filas existiam desde o começo de um projeto. Nenhuma era verificada por nada. A primeira medição encontrou 24 violações de uma, 71 de outra, 6 de outra.

### 8. Catraca para dívida legada

Quando a regra nasce depois do código, o passivo já existe. Reprovar tudo trava o time sem consertar nada — e **build que nasce vermelho ninguém olha**.

A catraca congela a contagem atual num arquivo de linha de base e **falha só se algum número aumentar**. O passivo fica visível e imóvel; código novo já nasce dentro da regra. Quando um número chega a zero, a regra é promovida a falha dura.

**A escolha entre catraca e falha dura é por área, não por projeto.** No mesmo repositório: estrutura de documento nasce com régua integral, porque não há dívida; regra de código entra por catraca, porque há.

### 9. Proveniência ou purga

Todo registro do índice semântico carrega de onde veio e de qual versão: `origem` + `versão` + `quando foi indexado`.

**Registro sem proveniência é purgado, não corrigido.** Não dá para consertar um fato do qual você não sabe a origem — só dá para recriá-lo a partir da fonte.

### 10. Divergência não se resolve, se registra

Quando duas fontes discordam, o agente **não escolhe**. Registra numa fila de arbitragem, com número, e para.

Isso parece burocracia até a primeira vez em que um agente "resolve" uma divergência escolhendo o lado errado com muita confiança.

**A fila também é a saúde do projeto.** Ela cresce quando o entendimento cresce, e itens antigos que ninguém fecha são o sinal mais honesto de dívida.

### 11. História é append-only; estado se reescreve

Dois documentos com regras opostas, e a diferença importa:

**Estado** — onde o projeto está agora. Reescrito a cada sessão. Máximo uma página. Não acumula.

**Cronologia** — o que aconteceu e por quê. **Nunca editada.** Correção entra como entrada nova referenciando a anterior.

*Por que append-only:* se cada sessão pode reescrever o passado, você perde a capacidade de responder "por que decidimos isso em julho?". E é essa pergunta que faz a memória valer alguma coisa.

*O erro que gerou:* um documento onde a §7 dizia que o commit foi feito e a §9, logo abaixo, recomendava decidir se autorizava o commit. Alguém atualizou uma parte e esqueceu a outra.

### 12. O número medido vai no documento

Quando você mede algo — quantas violações, quantos testes, quanto tempo — **escreva o número**, não a impressão.

*O erro que gerou, e é o mais instrutivo de todos:* um verificador comparava caminho de arquivo de um jeito que nunca casava no Windows. A contagem saía errada **sem erro nenhum** — 73 em vez de 71, 8 em vez de 6.

Foi pego porque os documentos tinham os números certos escritos, e eles não bateram.

> **Foi a documentação que pegou o bug do verificador, não o contrário.**

Se o número não estivesse escrito, a linha de base teria sido congelada errada, e a catraca nasceria com folga permanente.

### 13. Verificação não altera o que verifica

Parece óbvio e é fácil de violar.

*O erro que gerou:* o validador de documentos regenerava a pasta derivada para comparar — e a deixava modificada. O validador seguinte via arquivos alterados e reprovava, não porque algo estava errado, mas porque o validador anterior tinha acabado de mexer neles.

**Se precisar alterar para comparar, restaure depois.** Ou compare em área temporária.

### 14. Exceção declarada, nunca regra silenciosamente quebrada

Toda regra encontra o caso em que aplicá-la causaria dano. Quando isso acontecer, **declare a exceção em texto**, com o motivo e a condição de saída.

*O caso real:* a regra dizia que registro sem proveniência é purgado. Um lote inteiro se enquadrava — e era o único registro existente de um mês de trabalho. Purgar apagaria fato sem ter de onde recriar. A exceção foi escrita em três lugares, incluindo dentro do próprio índice, ensinando qualquer agente a tratar aquele lote como pista e nunca como afirmação.

A alternativa — aplicar a regra e perder o fato, ou ignorá-la em silêncio — é pior nos dois sentidos.

---

## PARTE III — A estrutura

### As camadas

```
L0  o código                    verdade última, sempre
     ↓ gera
L1  docs/gerado/                extraído automaticamente, reprodutível
     ↓ complementa
L2  docs/ escrito à mão         fatos estáveis sobre o código
     ↓ registra ao longo do tempo
L3  docs/cronologia/            a vida do projeto, append-only
     ↕ (fora do código)
L4  acervo de exploração        metodologia, rascunho, contexto de negócio
     ↓ tudo alimenta
L5  índice semântico            busca. derivado. reconstruível. zero autoridade.
```

**L4 e L5 são opcionais.** Um projeto pequeno vive muito bem com L0 a L3, e a portabilidade entre LLMs — que é o objetivo principal — está inteira em L2 e L3.

**Há um segundo índice opcional, irmão do L5: o grafo de código** (code-review-graph, Graphify e similares). O L5 busca por *significado* nos documentos; o grafo responde *estrutura* no código — quem chama o quê, o que quebra se mexer aqui. Perguntas diferentes, mesma regra: **derivado, reconstruível, autoridade zero.** O grafo descreve o que o código É com fidelidade perfeita — inclusive quando o código está errado; é o FDD que permite perceber isso. Declare-o em `padrao.json` → `grafo` e na tabela de jurisdição, e o método não precisa verificá-lo: essas ferramentas se reindexam sozinhas.

**Onde ficam os quatro arquivos de entrada nesse esquema:** `PROJETO.md` e `ABERTO.md` são L2 (fatos estáveis — as regras do projeto e a lista de conflitos abertos mudam devagar). `cronologia/` é L3, por definição. `ESTADO.md` é o único fora da escala: ele é **um recorte do L3**, o topo da cronologia reescrito em prosa curta para leitura imediata. Por isso é o único documento que pode ser jogado fora e reconstruído a partir da cronologia — e por isso ele é reescrito em vez de acumulado. As regras de frontmatter valem para os quatro, sem exceção.

### Os quatro arquivos de entrada

Este é o coração. **Qualquer LLM lê os quatro em cinco minutos e sabe operar.**

| Arquivo | O que é | Regra |
|---|---|---|
| `docs/PROJETO.md` | porta única: jurisdição, ordem de desempate, proibições, formato de autorização, como o dono trabalha | o único arquivo que precisa ser conhecido |
| `docs/ESTADO.md` | onde estamos agora, e as próximas ações | reescrito, máximo uma página |
| `docs/cronologia/AAAA-MM.md` | o que aconteceu e por quê | append-only, mais recente no topo |
| `docs/ABERTO.md` | o que está em conflito ou indefinido | numerado, nunca apagado |

Tudo o mais é detalhe que se lê quando a tarefa exigir.

> O kit que acompanha este método traz os quatro em branco, com os comentários no lugar de cada resposta, e um **`PROJETO.md` preenchido de ponta a ponta** em `EXEMPLO-PROJETO-PREENCHIDO.md`. Vale olhar o exemplo antes de começar: template em branco não ensina o nível de detalhe que faz diferença, e a diferença entre um `PROJETO.md` que funciona e um que não funciona é quase toda especificidade.

> **`ABERTO.md` é a fila de arbitragem do princípio 10.** São a mesma coisa; o princípio descreve o comportamento, o arquivo é onde ele acontece. Formato mínimo de uma entrada: número sequencial que nunca é reaproveitado, o que cada lado afirma **com caminho de arquivo**, a evidência que separa os dois, e o estado. Ao resolver, não se apaga: marca-se `✅ resolvido em <data>` e escreve-se **como** foi resolvido. Entrada apagada é lição perdida — e a mesma divergência volta em seis meses sem que ninguém lembre que já foi discutida.

### Frontmatter

Todo documento em `docs/` começa com um bloco de metadados. É ele que permite verificação automática.

```yaml
---
id: ADR-0007                    # chave estável, nunca muda
tipo: adr                       # roteia e define o que validar
projeto: meu-projeto
titulo: Usar fila para notificação em lote
status: verificado              # rascunho | verificado | superado
verificado_em: 2026-08-04
verificado_commit: a1b2c3d      # contra qual versão do código foi conferido
deriva_de: [HLD-0002]           # de quem este documento DEPENDE — a cadeia
supersede: [ADR-0003]           # o que este documento torna obsoleto
ancoras:                        # arquivos que este documento descreve
  - src/Jobs/NotificarLote.php
---
```

**O campo que mais rende é `ancoras`.** Não porque seja o mais importante — o princípio 3, a ordem de desempate, resolve um problema mais fundamental. É o que mais rende porque tem a melhor relação entre o que custa e o que pega: são duas linhas de frontmatter e uma checagem de existência de arquivo, e mesmo assim é o **único** campo que transforma "este documento está desatualizado" de opinião de quem leu em fato que uma máquina decide. Todos os outros campos descrevem o documento; este o amarra ao código.

**`verificado_commit` e `supersede` — o que fazem e o que não fazem.**

`verificado_commit` registra contra qual versão do código alguém conferiu o documento. Ele **não** é comparado automaticamente com nada: não existe "falhou porque o arquivo âncora mudou depois", porque mudança de arquivo não implica que o documento envelheceu, e reprovar por isso encheria o build de falso positivo até ninguém olhar mais. O que ele dá é datação honesta na hora da leitura — um documento verificado há trezentos commits merece desconfiança, e isso fica visível. Fechar essa lacuna com verificação automática é assunto em aberto, não resolvido; se o seu projeto encontrar um critério que funcione, ele vale mais que este parágrafo.

`supersede` é preenchido à mão por quem toma a decisão nova, e **é responsabilidade dele mudar o `status` do documento antigo para `superado` no mesmo commit**. Nada verifica isso hoje. Dois documentos `verificado` afirmando coisas contrárias sobre o mesmo assunto é uma falha real que o método ainda não pega sozinha — é exatamente o tipo de coisa que vira entrada no `ABERTO.md` do seu projeto.

### A pasta de derivados

`docs/gerado/` contém só o que sai de um script. Cada arquivo abre com aviso:

```markdown
> ⚠️ ARQUIVO GERADO AUTOMATICAMENTE. Não edite à mão.
> Gerado por `php scripts/gerar-docs.php`.
```

O que costuma valer a pena gerar, em ordem de utilidade — é lista de candidatos, não receita fechada. Quem decide é a regra da decisão 3 da Parte IV: **assunto sobre o qual um documento escrito à mão já errou uma vez é candidato a gerado.**

1. **Mapa de diretórios** com contagem de arquivos — é o documento que mais mente quando escrito à mão, e é o único que vale em qualquer projeto
2. **Comandos disponíveis** — CLI, scripts, tarefas
3. **Esquema de dados** — tabelas, coleções, migrações
4. **Rotas ou endpoints**

Comece pelo primeiro. Os outros três dependem do que o seu projeto tem, e gerar o que ninguém lê é trabalho que só produz mais arquivo para manter.

---

## PARTE III-B — A cadeia de documentos de engenharia

Até aqui a estrutura resolve *onde* cada fato mora. Falta resolver *como um fato leva a outro* — e é essa ligação que faz a documentação evoluir em vez de ser escrita uma vez e abandonada.

### Os cinco documentos, e o que cada um responde

A indústria já nomeou estes documentos, e o método adota os nomes em vez de inventar os seus — quem chega já sabe o que esperar de cada um.

| Tipo | Nome | Responde | Sobrevive a |
|---|---|---|---|
| `prd` | Product Requirements Document | **por que fazer** — o problema, quem sofre, o resultado esperado | trocar a solução inteira |
| `fdd` | Functional Design Document | **o que o sistema faz** — comportamento, regras, exceções | trocar linguagem e banco |
| `hld` | High Level Design | **como está organizado** — componentes, fronteiras, fluxos, donos de dado | refatorar dentro de um componente |
| `lld` | Low Level Design | **como está construído** — invariantes, contratos internos, concorrência | quase nada; é o que apodrece mais rápido |
| `adr` | Architecture Decision Record | **por que decidimos assim** — a decisão, o descartado, o custo aceito | tudo. É registro histórico, nunca reescrito |

A coluna da direita é a que decide o esforço. **Escreva com cuidado proporcional à durabilidade.** Um PRD bem-feito rende cinco anos; um LLD bem-feito rende até o próximo refactor — e por isso a maior parte dele deveria ser *gerada*, não escrita.

Onde moram: `docs/produto/` · `docs/funcional/` · `docs/arquitetura/` (HLD e LLD juntos, de propósito: são o mesmo assunto em dois níveis de zoom, e separá-los faz alguém procurar nas duas pastas sempre) · `docs/decisoes/`.

### A regra que evita a burocracia

Este é o ponto onde a maioria das tentativas de padronizar documentação morre: alguém decide que toda funcionalidade precisa dos cinco documentos, ninguém consegue manter, e em três meses o padrão inteiro é ignorado.

> **Nenhum documento é obrigatório. A cadeia é obrigatória quando existe.**

Ou seja: você pode ter um FDD sem PRD, um ADR solto, um HLD que cobre três funcionalidades. O que **não** pode é um FDD que não diz de onde veio. O documento que existe precisa estar amarrado; o que não existe não precisa nascer.

Três perguntas que decidem se vale escrever um documento:

1. **Alguém já explicou isto duas vezes?** Então já custou mais que escrever.
2. **Errar aqui tem consequência que não dá para desfazer?** Então precisa estar escrito antes.
3. **O código sozinho já diz?** Então gere, não escreva.

### `deriva_de` — o campo que faz a cadeia existir

```yaml
deriva_de:
  - PRD-0001      # o requisito que este documento detalha
  - ADR-0004      # a decisão que amarra este comportamento
```

**Leia o campo como "de quem eu dependo — se algum deles cair, eu preciso ser revisto".** Não é "quem veio antes no tempo". É dependência, e é isso que a verificação usa.

Duas coisas entram nele: **o pai na cadeia** (do problema para o código, nunca ao contrário) e **todo ADR que restringe este documento** — a metade que quase todo mundo esquece, e esquecer custa caro.

```
PRD ──────► FDD ──────► HLD ──────► LLD
 └──────────────── ADR ──────────────┘
```

**A pergunta que este campo responde, e que nenhuma outra coisa responde, é esta:**

> Quando este documento mudar, o que mais preciso revisar?

É a pergunta que quase ninguém faz, e não fazê-la é a causa de metade da documentação podre que existe no mundo. O documento muda, o que dependia dele não muda, e a divergência nasce sem que ninguém tenha errado.

### O ADR citado só em prosa é o buraco desta cadeia

Este é o erro que um leitor sem contexto encontrou testando o método, e é o mais instrutivo de todos porque **a ferramenta ficou verde o tempo inteiro**.

Ele escreveu a cadeia completa de uma funcionalidade. O `ADR-0001` decidia que o estoque saía da filial de origem no momento da solicitação. O `FDD` descrevia esse comportamento; o `LLD` implementava a invariante correspondente. Nenhum dos dois citava `ADR-0001` no frontmatter — o `HLD` citava, mas em prosa, numa seção chamada "Decisões que sustentam este desenho".

Depois a decisão caiu. Ele marcou `ADR-0001` como `superado`, escreveu o `ADR-0003` no lugar, e foi conferir o mapa gerado para saber o que revisar. **A coluna "quem depende deste" do `ADR-0001` estava vazia** — um traço. O `grep` também não ajudou: `FDD` e `LLD` nunca escreviam "ADR-0001", só descreviam a consequência dele.

Ele achou os dois documentos afetados porque conhecia o domínio. Não porque a ferramenta apontou.

> **Citação em prosa não é dependência. Só o frontmatter é.**
>
> Se uma decisão restringe o que um documento afirma, o id dela vai em `deriva_de` — mesmo que o texto já a mencione, mesmo que pareça redundante. É essa linha que faz o build quebrar quando a decisão cai, e é a única coisa entre você e uma documentação que descreve um comportamento que o projeto abandonou.

Vale a pena olhar por que a ferramenta ficou verde e ainda assim errou: ela verificou tudo o que foi declarado, corretamente. O que não foi declarado ela não tinha como ver. **Verificação não substitui declaração — ela só garante que o declarado se sustente.** É o limite estrutural de qualquer método deste tipo, e vale escrever na parede.

O que dá para fazer contra esse limite é torná-lo visível: o mapa gerado lista, em seção própria, **todo documento superado do qual ninguém declara depender**. Não é prova de erro — uma decisão pode ter sido mesmo isolada. É o lugar certo para desconfiar, e é onde estava o buraco no teste acima.

### A seta entre dois documentos aponta uma vez só

Assim que os ADRs entram em `deriva_de`, aparece um erro novo, e ele é fácil de cometer porque cada linha isolada parece certa:

```
FDD-0001  deriva_de: [ADR-0001]     "a regra veio dessa decisão"
ADR-0001  deriva_de: [HLD-0001]     "a decisão nasceu desse desenho"
HLD-0001  deriva_de: [FDD-0001]     "o desenho serve essa funcionalidade"
```

Os três dependem de si mesmos. "Revise quem depende deste" deixa de ter resposta, e a pergunta que a cadeia inteira existe para responder morre em silêncio.

> **Entre dois documentos, decida uma direção e mantenha.** O pai é quem levanta a pergunta que o outro responde.

Na prática, para ADR: o ADR depende do documento que **motivou** a decisão; quem **implementa** a decisão depende do ADR; nunca os dois sentidos entre o mesmo par.

`validar-docs.php` reprova ciclo, mostrando o caminho completo — `HLD-0001 → FDD-0001 → ADR-0001 → HLD-0001`. Vale saber por que esse erro é falha dura e não aviso: a primeira versão do gerador desenhava a árvore recursivamente e, com um ciclo, consumiu a memória da máquina até o sistema matar o processo. Estrutura circular não degrada a qualidade da resposta — ela impede que exista resposta.

### O que a verificação faz com a cadeia

| Situação | Severidade | Por quê |
|---|---|---|
| `deriva_de` aponta para id inexistente | **erro** | mesma família da âncora quebrada: afirmação conferível e errada |
| direção invertida (PRD deriva de LLD) | **erro** | a cadeia deixou de significar o que significava |
| ciclo | **erro** | não há resposta para "quem depende deste" |
| documento `verificado` com pai `superado` | **erro** | o mais valioso: a origem caiu e o detalhamento seguiu de pé |
| FDD, HLD ou LLD sem `deriva_de` | aviso | detalhamento que ninguém conferiu contra requisito nenhum |
| pai reverificado depois do filho | aviso | não quer dizer errado — quer dizer que ninguém olhou |

Os dois últimos são aviso e não erro **de propósito**. Como falha dura encheriam o build de vermelho por mudança de vírgula no pai, e build que vive vermelho ninguém olha. A régua fica onde há resposta objetiva; onde há julgamento, a ferramenta mostra e o humano decide.

E o mapa da cadeia inteira é **gerado**, em `docs/gerado/cadeia-documentos.md` — porque é uma visão que depende de ler o cabeçalho de dezenas de arquivos, e ninguém mantém isso à mão sem errar.

### Como a cadeia evolui

1. **A realidade muda** — requisito novo, bug que revela regra errada, decisão que caiu.
2. **Atualize o documento do nível mais alto que foi afetado.** Se o problema mudou, é o PRD; se só o desenho mudou, é o HLD. Mexer no nível errado é o que produz PRD cheio de detalhe de implementação.
3. **Marque o antigo, não o apague.** Decisão que caiu vira `status: superado`, com `supersede` apontando dos dois lados. O ADR antigo continua explicando o que se acreditava na época — sem isso, ninguém entende por que a decisão fazia sentido. E ele **fica onde está**: mover para `_arquivo/` o tiraria da verificação, que é o oposto do que se quer.
4. **Siga a coluna "quem depende deste"** do mapa gerado e revise cada filho. A verificação te obriga: filho `verificado` com pai `superado` quebra o build.
5. **Registre na cronologia.** O que mudou, por quê, e quais documentos foram junto.

O passo 4 é o que o resto do método existe para tornar possível. Sem `deriva_de`, ele depende de alguém lembrar — e ninguém lembra.

---

## PARTE IV — As decisões que todo projeto precisa tomar

Oito. Sem elas o kit não funciona, porque são justamente o que ele não pode adivinhar.

### 1. Quais acervos existem, e quem manda em quê

Mínimo: um (o repositório). Comum: dois ou três.

**Não crie acervo sem jurisdição exclusiva.** Um acervo que "também tem documentação" é o começo da bifurcação.

### 2. Qual o vocabulário de `tipo` e `status`

O kit vem com um conjunto sugerido. Corte o que não usar — **vocabulário grande demais faz todo mundo escolher errado**.

```
tipo:   entrada · decisao · dominio · arquitetura · runbook
        politica · evidencia · cronologia · estado · gerado
status: rascunho · verificado · superado
```

### 3. O que é gerado, e por qual script

Comece pelo mapa de diretórios. Acrescente conforme doer.

**Regra:** se um documento escrito à mão já errou uma vez sobre um assunto, esse assunto é candidato a gerado.

### 4. Quais regras viram catraca, com quais contadores

Escolha regras **grepáveis** — que dão para contar com uma expressão regular. Regra que exige entender semântica não vira catraca; fica documental.

Bons candidatos: uso de função proibida, arquivo sem campo obrigatório, padrão perigoso conhecido.

O teste para o caso de fronteira — e a fronteira é onde fica a maioria das regras que interessam — é este: **duas pessoas rodando o mesmo contador no mesmo código chegam obrigatoriamente ao mesmo número?** "Função com mais de 50 linhas" passa: é contável, mesmo sendo uma medida superficial. "Função com mais de uma responsabilidade" não passa: duas pessoas contam diferente, e um contador que discorda de si mesmo transforma a catraca em loteria.

Quando a regra que importa não é contável, não force. Escreva-a em `docs/politicas/` como regra documental, com o número que você mediu à mão e a data. Regra documental honesta vale mais que um contador que mede a coisa errada só para ter um número — o contador errado dá a sensação de estar protegido, que é pior que saber que não está.

### 5. Tem índice semântico? Se sim, qual é o núcleo?

Se sim, divida em dois níveis:

- **Núcleo** — o que qualquer agente lê para saber onde o projeto está. Falha dura se ficar velho.
- **Resto** — medido e visível, sem bloquear.

Sem essa divisão, ou você indexa tudo (caro) ou o verificador vive vermelho (inútil).

### 6. Quem commita, e quando

Precisa estar escrito, porque **as obrigações de fim de sessão criam alterações que alguém tem que commitar**.

Se o agente não commita, diga que a árvore fica suja de propósito e que isso é aceitável. Se commita, diga em que condições.

*Sem isso, o agente ou commita sem autorização, ou fica paralisado.*

### 7. Formato de autorização para ação irreversível

Genérico não autoriza nada. "Pode", "manda ver", "resolve isso" — nada.

Formato sugerido:

```
Autorizo <ação específica> em <alvo>,
com escopo <limite exato>,
rollback <plano>,
durante <janela ou "uma execução">.
```

### 8. Como o dono trabalha

Idioma, nível de detalhe, se quer opções antes da execução, o que nunca deve ser feito sem perguntar.

**Parece supérfluo e é o que mais economiza tempo.** É a diferença entre um agente que entrega do jeito certo na primeira e um que entrega três vezes.

---

## PARTE V — O ciclo de vida

### Fase 1 — Bootstrap (uma sessão)

1. Criar a estrutura e os quatro arquivos de entrada
2. Preencher o `PROJETO.md` com as oito decisões
3. Rodar o gerador pela primeira vez
4. **Medir a dívida e congelar a linha de base**
5. Instalar as verificações no CI
6. **Teste de leitura fria** (critério de aceitação, abaixo)

Em projeto novo, o passo 4 é trivial — tudo é zero, e a régua vale integral desde o commit inicial.

### Fase 2 — Auditoria (só em projeto existente)

Antes de promover qualquer coisa, **confira o acervo canônico contra o código**. Se ele mente, promover conteúdo para dentro dele só espalha o erro.

O que sempre aparece: mapa de diretórios errado, documento de arquitetura descrevendo menos módulos do que existem, comandos documentados que não existem, e pastas vazias que alguém criou por um plano abandonado.

### Fase 3 — Arbitragem (só em projeto com múltiplos acervos)

O princípio 4 proíbe cópia. Esta fase existe porque a proibição só vale a partir de hoje: **toda a duplicação que você vai arbitrar aqui é anterior ao método.** Depois da arbitragem, esta fase não se repete — se voltar a ser necessária, o fluxo de mão única está sendo furado em algum lugar, e isso é o achado.

Para cada documento duplicado, decida: **promover** (vira canônico), **arquivar** (vira link), ou **conflito** (resolve contra o código, nunca contra a data). A regra "contra o código, nunca contra a data" não é só desta fase — é a mesma do princípio 10, e vale para toda divergência, sempre.

**Leia antes de apagar.** O fato mais valioso de um acervo bagunçado costuma ser o que não existe em nenhum outro lugar — e some no primeiro `rm` bem-intencionado.

### Fase 4 — Operação (cada sessão)

Fim de sessão, sempre:

1. Entrada na cronologia
2. `ESTADO.md` atualizado
3. Divergências encontradas e não resolvidas na fila de arbitragem
4. Se houver índice: reindexar e marcar
5. Validadores verdes

### Fase 5 — Evolução (contínua)

- Contador da catraca chegou a zero → promova a regra a falha dura
- Documento `rascunho` foi conferido → vire `verificado` com o commit
- Regra documental virou grepável → vire catraca
- Módulo ficou importante → entre no núcleo do índice

**O padrão fica mais rígido com o tempo, nunca menos.**

---

## PARTE VI — O critério de aceitação

Não é "os validadores passam". É este:

> **Abra uma sessão nova, num modelo que nunca viu o projeto, dê acesso só ao repositório, e mande: "comece por `docs/PROJETO.md`, siga a ordem de leitura que ele indica, e me diga onde o projeto está e o que eu não posso fazer".**

O pedido é "comece por" e "siga a ordem que ele indica" — não "leia só esse arquivo". O `PROJETO.md` **de propósito não responde** onde o projeto está: isso é jurisdição do `ESTADO.md`, e um `PROJETO.md` que respondesse estaria violando o princípio 2. O que está sendo testado é se ele conduz até lá sozinho, sem que ninguém explique nada.

Passa se o modelo acertar: onde está o código, o que está ligado e desligado, qual o bloqueio principal, a lista de proibições, o formato de autorização, e o que fazer ao encontrar fontes que discordam.

**Faça o teste com um modelo diferente do que você usa para escrever.** O que escreveu preenche lacuna com contexto que não está no arquivo.

*E leia a parte que ele não acertou com atenção maior do que a que ele acertou.* Num teste real, o modelo devolveu 17 defeitos — seções apontando para pastas que já tinham conteúdo, ordem de leitura fixada num mês que já tinha passado, e um esquema de numeração ambíguo que ninguém tinha catalogado.

**Repita a cada mês, ou depois de qualquer mudança grande.** E sempre com uma sessão nova — nunca com a mesma, que já foi contaminada pela resposta anterior e passa a acertar de memória.

**Aplique o teste ao próprio material de instalação, não só ao projeto.** Este método e o kit que o acompanha passaram por ele: um leitor sem contexto instalou o kit seguindo apenas o `INSTALAR.md` e encontrou, entre outras coisas, uma configuração que ficava congelada no nome de exemplo — com o build verde — e o bug do extrator descrito no princípio 5. Nenhum dos dois tinha sido percebido por quem escreveu.

---

## PARTE VII — Anti-padrões

Os que eu cometi construindo isto. Todos custaram tempo.

### Criar antes de auditar

Criei uma pasta que já existia com outro nome, e a que já existia tinha conteúdo. **É exatamente a colisão que o método existe para evitar** — cometida por quem estava escrevendo o método.

*Antes de criar qualquer pasta, liste o que existe.*

### Afirmar sem varrer a fonte

Escrevi que cinco itens não tinham documentação. Dois tinham — eu não tinha olhado a pasta onde estavam.

*Conferir contra a fonte vale para o repositório e para o que você escreve sobre ele.*

### Construir a peça de procedimento dentro da ferramenta

Empacotei o procedimento de fim de sessão como skill instalável — invisível para as outras ferramentas, perdido se trocar de assistente. **Violei o princípio 1 três dias depois de escrevê-lo.**

*Se é procedimento, é arquivo. O pacote instalável é artefato derivado.*

### Escrever verificador pensando num sistema operacional só

Três bugs da mesma família. O pior não dava erro nenhum: comparação de caminho que nunca casava no Windows, devolvendo contagem errada em silêncio.

*Normalize separador de caminho na entrada. Não use redirecionamento específico de shell.*

### Presumir que a pasta existe do outro lado

Git não versiona diretório vazio. Uma pasta que existe na sua máquina simplesmente não existe num clone — e essa diferença apareceu **três vezes** durante a construção deste kit, em três peças diferentes: o gerador, que listava pastas fantasma e produzia saída divergente no CI; a árvore instalada, que perdia metade das pastas de `docs/` no clone, deixando o `PROJETO.md` apontando para lugares inexistentes; e o próprio autoteste, que escrevia num diretório que não estava lá e reprovava quatro testes com aviso do PHP no meio da saída.

*Qualquer coisa que escreva num diretório do repositório cria o diretório antes. Qualquer coisa que liste diretórios ignora os vazios. E toda pasta que precisa existir vazia ganha um arquivo marcador.*

### Confundir reprodutível com verdadeiro

A verificação de derivado confere que rodar o gerador de novo produz o mesmo resultado. Isso não diz nada sobre o resultado estar certo. Um extrator com bug é perfeitamente reprodutível — devolve o mesmo número errado sempre, e passa.

*Leia a saída do gerador com os próprios olhos pelo menos uma vez, na instalação e a cada extrator novo. Depois disso a verificação cuida da parte que ela sabe cuidar.*

### Escrever verificador e nunca testar se ele reprova

Verificador que não pega nada e verificador quebrado imprimem exatamente a mesma coisa: "tudo certo". A única forma de distinguir é quebrar o projeto de propósito e conferir que o alarme toca.

*Toda régua ganha um teste que a viola. Sem isso, "build verde" é uma afirmação sobre o script, não sobre o projeto.*

### Deixar o validador sujar a árvore

Já enunciado no princípio 13. Custou o primeiro run do CI.

### Fazer a régua nova reprovar o passivo antigo

A primeira versão do validador de estrutura reprovava 112 documentos legados. Build vermelho desde o primeiro dia é build que ninguém olha.

*Régua nova, passivo congelado. Sempre.*

---

## PARTE VIII — O que este método não resolve

**Não faz ninguém escrever.** Ele garante que o que foi escrito não apodreça em silêncio; não gera conteúdo.

**Não substitui teste.** Documento verificado é documento cujas âncoras existem e cuja estrutura é válida — não documento cujo conteúdo é verdadeiro.

**Não impede decisão ruim.** Só garante que ela fique registrada com data e motivo, e que a próxima pessoa saiba que foi deliberada.

**Não funciona sem alguém que se importe.** A catraca impede piorar; ela não melhora nada sozinha. Alguém precisa querer zerar os contadores.

---

## Resumo em uma página

**Problema:** documentação apodrece porque nada verifica, e memória de IA não é portátil.

**Solução:** markdown versionado + jurisdição declarada + verificação automática.

**As quatro peças:** `PROJETO.md` (porta única) · `ESTADO.md` (agora) · `cronologia/` (história, append-only) · `ABERTO.md` (conflitos).

**As verificações:** estrutura e âncoras (falha dura) · regras de código (catraca) · índice em dia (falha dura no núcleo) · e um autoteste que quebra o projeto de propósito para conferir que os três ainda pegam o que prometem.

**O critério:** um modelo que nunca viu o projeto lê a porta de entrada e opera com segurança.

**O princípio que carrega o resto:** o que mora dentro de uma ferramenta é cache. Memória é arquivo versionado.
