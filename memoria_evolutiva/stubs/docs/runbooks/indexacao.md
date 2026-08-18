---
id: RUN-BANCOS-MEMORIA
tipo: runbook
projeto: <NOME-DO-PROJETO>
titulo: Hindsight local e grafo de código Graphify
status: verificado
verificado_em: 2026-08-13
verificado_commit: pacote
ancoras:
  - padrao.json
---

# Bancos derivados obrigatórios

O projeto usa dois bancos locais com jurisdições diferentes:

| Banco | Responde | Fonte real | Autoridade |
|---|---|---|---|
| Hindsight | significado, histórico e decisões documentadas | `docs/` | zero |
| Graphify | símbolos, relações e impacto estrutural | código | zero |
| Manifesto RAG sombra | fragmentos reproduzíveis e proveniência | núcleo de `docs/` | zero |

Não há escolha de fornecedor por sessão. A configuração padrão está em `padrao.json`:
Hindsight em `http://127.0.0.1:8888`, bank igual ao projeto; Graphify por `graphify`,
com saída local em `graphify-out/`.

## Sincronização

```bash
memoria bancos sincronizar
memoria bancos status
memoria fragmentos verificar
memoria avaliar verificar
# Em runner sem Hindsight, somente para conferir artefatos versionados:
memoria bancos status --offline
```

O Hindsight recebe um documento lógico estável por arquivo, com `update_mode: replace`,
tags/metadados estritos e `source_uri`. O lote envia somente fontes alteradas; cada uma é
lida de volta e precisa conter memórias. O Graphify executa `extract . --code-only`
na primeira vez e `update . --force` nas seguintes. O `--force` é seguro aqui porque o
grafo é exclusivamente AST; uma reconstrução recusada bloqueia o marcador mesmo se o
processo devolver código zero.

Antes dos provedores, o sincronizador gera
`docs/gerado/manifesto-fragmentos-v2.json`. Ele fatia por seção, item de `ABERTO`, termo
do glossário e entrada da cronologia; preserva tabelas e cercas de código. O perfil de
chunking e embedding entra no fingerprint. Na Fase 1 esse corpus é sombra: permite
comparação e falha de frescor, mas não converte o bank atual de documentos inteiros.

A qualidade desse modo sombra é medida pelo corpus em
`docs/avaliacao/casos-rag-v1.json`. `memoria avaliar verificar` compara as métricas com
`docs/politicas/baseline-rag-v1.json`; relatório e manifesto em `docs/gerado/` precisam
ser reconstruíveis. Mudança de corpus exige `memoria avaliar medir` explícito e aprovado.

Marcadores só são gravados após sucesso do provedor. Não existe comando de marcação
manual. Mudança em documento ou código invalida a consulta até nova sincronização.

## Consulta obrigatória antes de explorar

```bash
memoria bancos consultar --pergunta="onde é implementada a autenticação e por quê?"
memoria contexto --pergunta="onde é implementada a autenticação e por quê?" --perfil=engenharia-leitura --json
```

O comando consulta os dois bancos, mas bloqueia se algum estiver velho. Use o Hindsight
para orientar significado e o Graphify para orientar estrutura; então abra os
`source_uri` e o código. Resultado derivado nunca é a resposta final.

## Segurança e descarte

- segredos não entram em `docs/` nem nos bancos;
- chave opcional do Hindsight vem da variável nomeada em `memoria.api_key_env`;
- `graphify-out/graph.json`, o manifesto RAG e marcadores podem ser versionados;
  somente cache, manifesto interno do Graphify e caminhos locais são ignorados pelo Git;
- ambos os bancos podem ser apagados e reconstruídos das fontes canônicas;
- commit, push, deploy e escrita remota continuam fora deste runbook.
