---
id: RUN-DOCUMENTACAO-AUTONOMA
tipo: runbook
projeto: <NOME-DO-PROJETO>
titulo: Documentação autônoma do projeto
status: verificado
verificado_em: 2026-08-13
verificado_commit: pacote
ancoras:
  - padrao.json
---

# Documentação autônoma

## Algoritmo obrigatório

1. No início, rode `memoria ciclo iniciar --plataforma=PLATAFORMA --perfil=engenharia-leitura --json`; ele prepara os provedores, confirma o canary e repara estado velho.
2. Consulte o gateway com `memoria contexto --pergunta="..." --perfil=engenharia-leitura --json` antes de
   abrir arquivos brutos.
3. Confirme que cada fonte relevante aparece no manifesto; ajuste `gerado.raiz` e
   `gerado.extensoes` se a jurisdição estiver incompleta.
4. Identifique pontos de entrada, contratos, dados, integrações e testes pela ordem de
   autoridade de `docs/politicas/AUTONOMIA.md`.
5. Documente contexto e blocos com C4, comportamento com FDD, construção com HLD/LLD,
   decisões significativas com ADR e operação com runbooks.
6. Cada afirmação verificada recebe `ancoras`. Uma intenção não demonstrada recebe
   `indeterminado`; nunca uma explicação plausível inventada.
7. Conflito é resolvido pela fonte superior. Empate sem condição observável mantém os
   dois comportamentos documentados e o ponto fica `indeterminado`.
8. Rode `memoria ciclo atualizar --plataforma=PLATAFORMA --perfil=engenharia-leitura --json`. Só encerre com os dois bancos, validação e
   autoteste verdes. A catraca `memoria avaliar verificar` precisa manter hit@1, hit@3,
   cobertura de citação, cobertura da resposta e taxa sem fonte dentro do baseline.

Revisão humana não faz parte deste algoritmo. Autorização para commit, publicação,
banco, ambiente remoto ou ação irreversível continua sendo uma fronteira separada.

## Execução por cron

A instalação completa registra `memoria agendador executar --json` diariamente às
02:15. Confirme com `memoria agendador status --json`. O comando é fechado: atualiza
somente documentação, Hindsight e Graphify sob o lock comum; não aceita shell ou SQL,
não acessa o banco de negócio, não cria commit e não publica. Para produzir um patch
isolado e retomável sob demanda, use o executor com um `run-id` explícito; ele mantém
checkpoints e usa worktree própria.

## Evolução mensurada

O corpus vive em `docs/avaliacao/casos-rag-v1.json`. Rode `memoria avaliar gerar` após
mudança normal e `memoria avaliar verificar` no gate. `memoria avaliar medir` cria uma
nova linha de base e só deve acompanhar uma mudança deliberada do corpus. Trocar
algoritmo, embedding, modelo ou provedor sem manter as métricas reprova automaticamente.
