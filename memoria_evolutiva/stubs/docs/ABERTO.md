---
id: ABERTO
tipo: estado
projeto: <NOME-DO-PROJETO>
titulo: Fila de conflitos e indefinições
status: rascunho
verificado_em: <AAAA-MM-DD>
verificado_commit: <sha>
---

# Aberto — conflitos e indefinições

> Quando duas fontes divergem, aplique a ordem objetiva de autoridade. Se fontes do
> mesmo nível continuarem inconclusivas, registre `indeterminado` aqui e prossiga no que
> não depender dessa resposta; só a ação afetada fica bloqueada.
> Resolução é sempre **contra o código**, nunca contra a data mais recente — o
> documento mais novo pode ser o mais errado.
>
> Ao resolver: **não apague**. Marque com `status: ✅ resolvido em <data>` e diga como.
> Entrada apagada é lição perdida.

## Como abrir uma entrada

```markdown
### ABERTO-00XX — Título que já diz qual é o problema
**tipo:** divergencia | indefinicao | risco | debito
**registrado_em:** AAAA-MM-DD · **fato_em:** AAAA-MM-DD · **severidade:** alta | media | baixa
**fontes:** onde cada versão do fato está, com caminho de arquivo
**impacto:** o que quebra ou o que se decide errado por causa disso
**resolve-se assim:** o caminho concreto, ou de quem é a decisão
```

`registrado_em` é quando entrou nesta lista. `fato_em` é quando o problema passou a
existir. A diferença entre os dois é a medida de quanto tempo algo ficou invisível.

**Esta fila também é a saúde do projeto.** Ela cresce quando o entendimento cresce.
Item antigo que ninguém fecha é o sinal mais honesto de dívida.

---

## Em aberto

<!-- primeira entrada aqui -->

---

## Resolvidos

*(mover para cá ao resolver, com data, decisão e link)*
