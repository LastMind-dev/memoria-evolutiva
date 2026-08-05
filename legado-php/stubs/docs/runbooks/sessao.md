---
id: RUN-SESSAO
tipo: runbook
projeto: <NOME-DO-PROJETO>
titulo: Abertura e fechamento de sessão
status: rascunho
ancoras: []
---

# Sessão — como abrir e como fechar

> Este é o runbook que mantém a estrutura viva. Sem ele o padrão vira uma pasta bonita
> que ninguém alimenta: os documentos existem, param no tempo, e em dois meses estão
> mentindo com a mesma confiança de antes.
>
> **Se você é um agente, o fechamento não é opcional.** Sessão que produziu mudança e
> não registrou nada é trabalho que o próximo agente vai refazer do zero.

---

## Abertura — 5 minutos, sempre igual

1. Leia `docs/PROJETO.md`.
2. Leia `docs/ESTADO.md`.
3. Liste `docs/cronologia/` e leia **os dois arquivos mais recentes**. Não presuma o mês.
4. Leia `docs/ABERTO.md` — o que está lá **não se resolve sozinho**.
5. Rode as verificações antes de tocar em qualquer coisa:

   ```
   vendor/bin/memoria validar
   vendor/bin/memoria catraca
   vendor/bin/memoria indice
   ```

   Se alguma já falha **antes** de você mexer, isso é o achado da sessão: registre e
   trate. Começar a trabalhar por cima de uma verificação vermelha faz sua mudança
   herdar a culpa de um problema que não é seu.

**Antes de afirmar qualquer coisa sobre o código, abra o código.** Documento é a melhor
pista disponível, não a fonte. A ordem de desempate está no `PROJETO.md`.

---

## Durante — quatro reflexos

**Divergiu? não escolha.** Documento diz A, código faz B: abra entrada em
`docs/ABERTO.md`, cite os dois lados com caminho de arquivo, e siga. Escolher em
silêncio é como uma divergência vira um mês de retrabalho.

**Explicou a mesma coisa duas vezes? vira documento.** A segunda explicação é o sinal.
Copie o molde certo de `docs/_templates/` e escreva enquanto o assunto está fresco.

**Decidiu algo que fecha porta? vira ADR.** `docs/decisoes/`, com o que foi descartado e
por quê. Decisão sem alternativa descartada não é decisão, é anotação — e daqui a seis
meses alguém vai refazer a discussão inteira.

**Mudou um documento da cadeia? siga os filhos.** Abra `docs/gerado/cadeia-documentos.md`
e olhe a coluna "quem depende deste" do documento que você mexeu. Cada filho precisa ser
revisado ou marcado. É a pergunta que quase ninguém faz — *quando isto muda, o que mais
preciso revisar?* — e não fazê-la é a causa de metade da documentação podre que existe.

---

## Fechamento — a parte que não pode ser pulada

### 1. O que mudou no código já está refletido nos documentos?

Para cada arquivo que você tocou, pergunte: **existe documento que fala sobre isto?**
Procure pelas âncoras:

```
grep -rn "caminho/do/arquivo" docs/
```

Se existir e estiver desatualizado, atualize agora. Não em seguida, não amanhã.

### 2. Regerar os derivados

```
vendor/bin/memoria gerar
```

Se a saída mudou, é porque o código mudou. Commite junto — derivado que fica para trás
é a próxima mentira.

### 3. Registrar na cronologia

**Append-only, mais recente no topo**, em `docs/cronologia/<ano>-<mês>.md`:

```markdown
## AAAA-MM-DD — <o que aconteceu, em uma linha>
**tipo:** entrega | decisão | correção | descoberta · **por:** <quem>

<Dois a cinco parágrafos. O que mudou, POR QUE, e o que isso fecha ou abre.>

**Arquivos:** `caminho/a.php`, `caminho/b.php`
**Commit:** `<sha>`
**Abriu:** ABERTO-00XX <se for o caso>
```

> Nunca edite uma entrada antiga para corrigi-la. Entrada nova, referenciando a
> anterior. A cronologia registra o que se acreditou na época — inclusive quando estava
> errado. Reescrever apaga a lição.

### 4. Reescrever o ESTADO

`docs/ESTADO.md` é o oposto da cronologia: **substituído, não acumulado.** Máximo uma
página. O que sobrar vai para a cronologia.

### 5. Fechar e abrir o que couber em ABERTO

Resolveu algo que estava lá? Marque `✅ resolvido em <data>` e diga **como**. Não apague.
Descobriu algo que não dá para resolver hoje? Abra a entrada agora, com evidência.

### 6. Reindexar, se o projeto tem índice

Documento do núcleo que mudou precisa ser reindexado — com origem e versão em cada
registro. O procedimento deste projeto está em `docs/runbooks/indexacao.md`.

**Só depois de indexar de verdade:**

```
vendor/bin/memoria indice --marcar
```

Marcar sem indexar transforma a verificação em teatro, e teatro é pior que nada: dá
confiança falsa.

### 7. Rodar tudo de novo

```
vendor/bin/memoria validar
vendor/bin/memoria catraca
vendor/bin/memoria indice
```

As três precisam passar.

### 8. Commitar

Um commit por assunto. A mensagem diz **por quê**, não o quê — o diff já diz o quê.

---

## Autorização

Ação irreversível — apagar dado, rodar migração, publicar, mexer em produção — pede
autorização explícita, no formato definido em `docs/PROJETO.md`. Não presuma
autorização a partir de "faça o que for preciso".

---

## Como transformar isto numa peça de procedimento da sua ferramenta

Skill, comando, prompt salvo, regra de editor — cada ferramenta chama de um jeito. Vale
para qualquer uma a mesma regra: **este arquivo é a fonte; a peça é derivada.**

```bash
vendor/bin/memoria skill              # monta o pacote a partir deste runbook e do kit
vendor/bin/memoria skill --conferir   # a peça instalada ainda bate com este arquivo?
```

O `--conferir` avisa quando este runbook mudou depois da última geração. É **aviso, não
erro**: peça velha não quebra o produto, só faz o agente seguir um procedimento que o
projeto já mudou. Vale rodar junto com as verificações do passo 7.

Escrever o procedimento dentro da ferramenta e deixar este documento para trás recria
exatamente o problema que o método existe para resolver — só que agora dentro da peça que
deveria preveni-lo.
