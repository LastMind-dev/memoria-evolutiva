# Hindsight local + Graphify — contrato do padrão

`docs/` e o código continuam sendo as únicas fontes de autoridade. Os dois bancos são
derivados locais, reconstruíveis e complementares:

```text
docs/  ──replace + leitura de confirmação──> Hindsight ── significado/histórico
  └────fragmentação determinística─────────> manifesto sombra ── corpus futuro
código ──AST code-only + assinatura────────> Graphify  ── estrutura/impacto
```

## Decisões fechadas

| Questão | Decisão padrão |
|---|---|
| Banco documental | Hindsight local em `http://127.0.0.1:8888` |
| Identidade do bank | nome do projeto |
| Isolamento de consulta | tags `memoria-evolutiva`, `projeto:<nome>` e `documentacao-canonica`, com `all_strict` |
| Atualização documental | um `document_id` estável por arquivo, lote somente dos alterados, `update_mode: replace` |
| Prova de persistência | `GET` de cada documento, igualdade de `original_text` e `memory_unit_count >= 1` por fonte |
| RAG fragmentado | manifesto v2 com ACL versionável, em modo sombra, sem migrar o Hindsight atual |
| Segurança antes do retain | exclui `secreto-nao-indexar` e aplica `redaction-deterministica-v1` |
| Perfil de embedding declarado | `local` + `BAAI/bge-small-en-v1.5`; qualquer mudança altera o fingerprint e força reconstrução |
| Grafo | Graphify local (`graphifyy`), primeira extração `--code-only` |
| Atualização do grafo | `graphify update . --force` no grafo code-only; recusa conhecida bloqueia marcador |
| Telemetria de consulta Graphify | desativada pelo processo com `GRAPHIFY_QUERY_LOG_DISABLE=1` |
| Autoridade | zero; todo resultado aponta de volta a `docs/` ou código |
| Revisão humana | não é necessária para documentar, sincronizar ou verificar |

O Hindsight recebe cada documento indexável do núcleo separadamente, já redigido, com
`source_uri`, tipo, status, classificação, audiência, produto, tenant, id e commit em
metadados e tags. `secreto-nao-indexar` nunca é enviado. `docs/gerado/` não entra: fatos de código são verificados no código e a
orientação estrutural pertence ao Graphify. O marcador `docs/.hindsight-indexado.json`
só nasce depois da leitura de confirmação de todas as fontes. `status` fala com o
Hindsight por padrão; `status --offline` é a exceção explícita para CI.

Em paralelo, `memoria fragmentos gerar` reconstrói
`docs/gerado/manifesto-fragmentos-v2.json`. SHA-256 de fonte e conteúdo, algoritmo,
limites, tratamento especial e perfil declarado de embedding compõem sua prova. O
manifesto não é enviado ao Hindsight na Fase 1; logo, atualizar a biblioteca não apaga,
converte nem duplica o bank existente.

Lotes com pelo menos `memoria.assincrono_acima_de_bytes` (1 MB por padrão) usam o
retain assíncrono e aguardam a operação terminar antes da leitura de confirmação. O
polling usa `memoria.intervalo_poll_segundos`; lotes menores permanecem síncronos.

O Graphify varre extensões de código em todo o projeto, exceto diretórios descartáveis,
`docs/` e o próprio `graphify-out/`. `.memoria/bancos/graphify.json` guarda SHA-256 por
fonte, hash do grafo, contagem de nós e cobertura fonte→nó. Arquivo alterado, grafo
corrompido, cobertura insuficiente ou redução anormal bloqueia a consulta.

## Fluxo autônomo

```bash
# cria documentação e sincroniza os dois bancos
memoria instalar --projeto="meu-app" --codigo=src

# ciclo normal após qualquer mudança
memoria documentar

# consulta conjunta: primeiro verifica frescor, depois pergunta aos dois
memoria bancos consultar --pergunta="como funciona o fechamento de pedido e onde muda?"

# contrato portátil recomendado para IDEs e agentes
memoria contexto --pergunta="como funciona o fechamento de pedido e onde muda?" \
  --perfil=engenharia-leitura --json

# inspeção explícita
memoria bancos status
memoria bancos sincronizar
```

`memoria documentar` encerra antes da sincronização se validação/catraca falhar. Se um
provedor falhar, o outro ainda é tentado para diagnóstico, mas a saída geral é falha e
nenhum marcador é criado para a etapa não confirmada.

## Preparação dos provedores

O Hindsight é um serviço independente porque precisa de armazenamento, embeddings e
modelo de extração. A instalação oficial recomenda Docker e expõe API em `8888`; também
há modo Python embutido. O padrão declara no `padrao.json` o perfil oficial local
(`BAAI/bge-small-en-v1.5`) para tornar mudanças de configuração visíveis no fingerprint;
o serviço Hindsight deve usar esse mesmo perfil. Como a configuração estática de
embedding pertence ao servidor e não ao bank, a Fase 1 prova a identidade declarada do
perfil, mas a paridade efetiva será medida antes da migração nas Fases 2 e 6. Se houver
token, `padrao.json` guarda somente o nome da variável em `memoria.api_key_env`.

O Graphify é distribuído como pacote `graphifyy`, mas o executável é `graphify`. Ele
precisa estar no PATH usado pelo comando `memoria`.

O instalador oferece duas exceções explícitas:

- `--adiar-bancos`: mantém os dois obrigatórios na configuração, mas não sincroniza
  nesta execução;
- `--sem-bancos`: opt-out deliberado; documentação/validadores continuam funcionando,
  mas consultas persistentes ficam desativadas.

Essas opções existem para bootstrap e ambientes reduzidos; não introduzem uma decisão
para a IA. Sem opção, o contrato é Hindsight + Graphify.

## Fronteiras de segurança

- não envie credencial para `docs/`; redaction é defesa em profundidade, e segredo
  documental conhecido usa `secreto-nao-indexar`;
- `grafo.comando` executa um processo local com as permissões do usuário;
- `graphify-out/graph.json`, relatórios portáveis e o marcador são versionáveis para
  que outra máquina valide o mesmo grafo sem reconstrução prévia; cache, manifesto e
  caminhos locais entram automaticamente no `.gitignore`;
- instalar/documentar não autoriza commit, push, deploy nem escrita em ambiente remoto;
- respostas dos bancos são orientação, nunca substituem leitura da fonte indicada.

Referências oficiais: [Hindsight](https://github.com/vectorize-io/hindsight),
[API de retenção](https://hindsight.vectorize.io/developer/api/retain),
[API de operações](https://hindsight.vectorize.io/developer/api/operations),
[API de documentos](https://hindsight.vectorize.io/developer/api/documents),
[configuração do Hindsight](https://hindsight.vectorize.io/developer/configuration) e
[Graphify](https://github.com/Graphify-Labs/graphify).
