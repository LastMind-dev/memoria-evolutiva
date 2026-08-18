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

1. Rode `memoria documentar`; ele atualiza documentação, Hindsight e Graphify.
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
8. Rode `memoria documentar` novamente. Só encerre com os dois bancos, validação e
   autoteste verdes. A catraca `memoria avaliar verificar` precisa manter hit@1, hit@3,
   cobertura de citação, cobertura da resposta e taxa sem fonte dentro do baseline.

Revisão humana não faz parte deste algoritmo. Autorização para commit, publicação,
banco, ambiente remoto ou ação irreversível continua sendo uma fronteira separada.

## Execução por cron

Use `memoria executar --run-id=ID --acao=documentar --json`. O executor aplica lock,
checkpoints e worktree própria; não cria commit nem publica. Capacidade ausente em
`padrao.json` é negada antes do efeito.

## Evolução mensurada

O corpus vive em `docs/avaliacao/casos-rag-v1.json`. Rode `memoria avaliar gerar` após
mudança normal e `memoria avaliar verificar` no gate. `memoria avaliar medir` cria uma
nova linha de base e só deve acompanhar uma mudança deliberada do corpus. Trocar
algoritmo, embedding, modelo ou provedor sem manter as métricas reprova automaticamente.
