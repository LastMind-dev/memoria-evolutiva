# Executor autônomo e cron

`memoria executar` é a porta não interativa introduzida na versão 5.0 e mantida na 6.0.
Ele aceita somente ações
fechadas pelo motor; não recebe comando de shell, prompt livre, URL, SQL nem nome de
ferramenta arbitrária.

## Uso

```bash
memoria executar --run-id=cron-diario-2026-08-13 --acao=documentar --json
memoria executar --run-id=verificacao-2026-08-13 --acao=verificar --json
```

`run_id` aceita 1 a 64 caracteres minúsculos em `[a-z0-9._-]`. A mesma combinação de
`run_id`, ação, versão do motor e capacidades sempre representa a mesma execução. Reusar
o ID com outro contrato é recusado; repetir uma execução concluída devolve
`replay: true` sem repetir efeitos.

## Isolamento

- `documentar` cria `memoria/run-<id>-<hash>` e uma worktree em
  `.memoria/executor/worktrees/<run_id>`;
- `verificar` é estritamente read-only e roda na raiz atual sob lock;
- estado e patch ficam em `.memoria/executor/runs/` e são ignorados pelo Git;
- o repositório original não recebe os arquivos produzidos pela ação;
- o executor não cria commit, não faz push e não publica.

O JSON final traz branch, worktree, checkpoints, arquivos modificados, SHA-256 e caminho
do patch. Esse diff é evidência para uma etapa posterior; não é autorização para
publicação.

## Checkpoints, lock e retomada

Uma execução de escrita passa por:

1. `preparar-worktree`;
2. `executar-acao`;
3. `validar`;
4. `registrar-diff`;
5. opcionalmente `sincronizar-bancos`, `avaliar-pos-sincronizacao` e
   `registrar-diff-final`.

Cada checkpoint só é gravado depois do sucesso e não é repetido na retomada. O lock é
único por projeto; execução simultânea recebe código 73. Lock do mesmo host cujo processo
morreu é recuperável. `lock_expira_segundos` precisa ser maior que o timeout global para
uma execução viva nunca ser tomada por outra apenas por duração.

Retry usa backoff exponencial limitado por `max_tentativas`. O timeout é global: inclui
etapas, tentativas e backoff. O subprocesso é encerrado pelo runtime quando o prazo acaba.

Na versão 6.0, os checkpoints de validação incluem `memoria avaliar verificar`. Quando
há sincronização externa, `avaliar-pos-sincronizacao` reconstrói e aplica o gate outra vez
antes do diff final. Assim, um cron não conclui se o estado final da recuperação piorar em
relação ao corpus e à baseline versionados.

## Capacidades

O padrão é negação total:

```json
"capacidades_permitidas": []
```

A única capacidade reconhecida nesta fase é `sincronizar-bancos`. Ela exige duas
condições simultâneas:

1. estar previamente concedida em `executor.capacidades_permitidas` no `padrao.json`;
2. ser solicitada naquela execução com `--capacidades=sincronizar-bancos`.

O executor revalida a concessão imediatamente antes do checkpoint externo. A capacidade
sincroniza somente Hindsight e Graphify configurados; ela não autoriza commit, push,
deploy, publicação, banco de negócio, API de cliente nem produção.

## Códigos de saída

| Código | Significado |
|---:|---|
| 0 | execução concluída ou replay idempotente |
| 1 | etapa falhou após as tentativas |
| 2 | argumento ou ação inválida |
| 3 | configuração/capacidade recusada |
| 73 | projeto já possui execução viva |
| 75 | interrupção controlada; pode retomar com o mesmo `run_id` |
| 124 | timeout global |

O stdout contém um único JSON inclusive nos erros. Logs persistidos guardam hashes e um
resumo submetido à mesma redaction da memória; stdout/stderr completos não são retidos.

## Exemplo de cron

```cron
15 2 * * * cd /srv/projeto && memoria executar --run-id=documentar-$(date +\%F) --acao=documentar --json >> /var/log/memoria-executor.jsonl
```

O agendador deve fornecer um `run_id` estável para a ocorrência lógica. Reexecutar a
mesma data retoma ou faz replay; mudar o ID cria outra execução deliberada.
