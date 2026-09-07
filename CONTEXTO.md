# Gateway neutro de contexto

`memoria contexto` é a porta de leitura portátil da memória evolutiva. Ele não chama
uma LLM, não escreve no projeto e não expõe o JSON particular do Hindsight ou a saída
textual do Graphify.

## Contrato

```bash
memoria contexto \
  --pergunta="onde a autenticação é implementada e por quê?" \
  --perfil=engenharia-leitura \
  --max-tokens=2048 \
  --json
```

O stdout contém somente um envelope JSON v2. Cada fonte documental possui
`source_uri`, SHA-256 da fonte e do fragmento, status, identificador estável e o commit
quando os bytes atuais forem exatamente os bytes de `HEAD`. Resultado sem fonte atual é
descartado.

Para atendimento e operação, o escopo é obrigatório e nunca é herdado:

```bash
memoria contexto --pergunta="como acompanhar?" --perfil=atendimento \
  --produto=pedidos --tenant=cliente-123 --json
```

A recuperação combina:

1. busca literal determinística nos fragmentos;
2. recall do Hindsight como sinal semântico por documento;
3. nós do Graphify como sinal estrutural;
4. busca literal no código atual;
5. deduplicação por hash e corte por orçamento estimado de tokens.

O Hindsight continua indexando documentos inteiros. `comparacao_sombra` registra, por
consulta, quantos documentos semânticos e fragmentos participaram. A migração permanece
explicitamente bloqueada até a catraca mensurada da Fase 6.

## Perfis

| Perfil | Documentação | Código | Escrita |
|---|---|---|---|
| `engenharia-leitura` | pública, interna e restrita | sim | nenhuma |
| `engenharia-documentacao` | pública, interna e restrita | sim | nenhuma pelo gateway |
| `automacao-codigo` | pública, interna e restrita | sim | nenhuma pelo gateway |
| `atendimento` | somente `publico`, diretório permitido, audiência e produto/tenant exatos | não | nenhuma |
| `operacao-assistida` | somente `publico`, diretório permitido, audiência e produto/tenant exatos | não | nenhuma |

O perfil é obrigatório em todos os transportes; ausência nunca cai silenciosamente num
perfil mais amplo. `audience`, quando presente, restringe ainda mais o fragmento.
`atendimento` e `operacao-assistida` exigem `produto` e `tenant` explícitos. O chamador
deve derivá-los da identidade autenticada, nunca da conversa ou da escolha da LLM.
`acoes_permitidas` é sempre uma lista vazia nesta versão.

## Transportes

Todos chamam `contexto.construir()` e devolvem o mesmo envelope.

### MCP stdio

```bash
memoria contexto mcp
```

Ferramenta exposta: `memoria_contexto`. O servidor aceita `tools/list`, `tools/call`,
`ping` e descoberta; o resultado inclui `structuredContent` e uma cópia JSON textual.
O protocolo atual declarado é `2026-07-28`; `initialize` antigo é aceito apenas para
compatibilidade de clientes em transição.
O handshake inclui instruções read-only autocontidas; configurações por cliente e o
canary estão em `ADAPTADORES.md`.

### HTTP local

```bash
memoria contexto http
```

- `POST /contexto`: corpo `{ "pergunta", "perfil", "produto", "tenant", "max_tokens" }`;
- `POST /mcp`: JSON-RPC MCP stateless;
- `GET /health`: saúde do transporte, não prova frescor dos bancos.

O servidor aceita apenas `127.0.0.1`, `localhost` ou `::1`, valida `Host` e `Origin` e
nunca faz bind em `0.0.0.0`. Defina `MEMORIA_CONTEXTO_TOKEN` para exigir
`Authorization: Bearer ...`. Corpo maior que 1 MiB é recusado.

## Frescor e falhas

- manifesto ausente ou defasado: consulta falha;
- fonte/fragmento/ancora com hash divergente: item falha antes de ser entregue;
- Hindsight ou Graphify ativo, mas defasado/indisponível: resposta fica `parcial` e traz
  aviso; o provedor não confirmado não contribui;
- provedor explicitamente desativado: a busca local continua, com aviso;
- nenhuma fonte permitida: `cobertura: ausente`, lista vazia e aviso, nunca resposta inventada;
- fontes entregues que não cobrem todos os termos da pergunta: `cobertura: parcial`;
- todos os termos da pergunta presentes no material entregue: `cobertura: confirmada`.

Classificação, audiência, isolamento e redaction estão especificados em
`SEGURANCA-MEMORIA.md`. O gateway filtra o manifesto antes de entregar resultados; o
Hindsight recebe conteúdo redigido e continua sendo apenas sinal semântico.

Referências: [recall do Hindsight](https://hindsight.vectorize.io/developer/api/recall)
e [MCP 2026-07-28](https://blog.modelcontextprotocol.io/posts/2026-07-28/).
