# Avaliação RAG e catraca de evolução

Na versão 6.0, `memoria avaliar` mede o gateway neutro com um corpus versionado. A
avaliação não pergunta a uma LLM se a resposta “parece boa”: compara fontes e termos
esperados por regras determinísticas.

## Artefatos

| Artefato | Papel | Autoridade |
|---|---|---|
| `docs/avaliacao/casos-rag-v1.json` | perguntas, resposta esperada, termos, fontes, perfil e escopo | canônica |
| `docs/politicas/baseline-rag-v1.json` | linha de base assinada das métricas | canônica, alterada apenas por `medir` |
| `docs/gerado/relatorio-avaliacao-rag-v1.json` | resultados por caso, perfil e categoria | derivada |
| `docs/gerado/manifesto-avaliacao-rag-v1.json` | assinaturas, drift, gate e candidatas à promoção | derivada |

O corpus exige casos separados de engenharia, atendimento e automação. Casos positivos
declaram fontes e termos esperados. Casos negativos de atendimento exigem ausência de
fonte e podem proibir caminhos internos, provando o isolamento em vez de apenas medir
relevância.

## Métricas

- `hit_1`: a primeira fonte é esperada;
- `hit_3`: ao menos uma das três primeiras fontes é esperada;
- `cobertura_citacao`: proporção das fontes esperadas efetivamente citadas;
- `cobertura_resposta`: proporção dos termos esperados presente nos trechos confirmados;
- `sem_fonte`: casos positivos que não receberam fonte;
- `negativos_ok`: casos negativos sem vazamento nem fonte indevida.

As métricas são agregadas globalmente, por perfil e por categoria. O relatório registra
drift do algoritmo de fragmentação, fingerprint, provedor e modelo de embedding, além
do delta de cada métrica por perfil.

## Fluxo

```bash
memoria avaliar verificar       # somente leitura; usado no CI e no executor
memoria avaliar gerar           # reconstrói relatório/manifesto e aplica a catraca
memoria avaliar medir           # cria nova baseline deliberada
memoria avaliar verificar --json
```

`medir` recusa uma recuperação que já esteja abaixo dos limites ou contenha caso
reprovado. Mudar o corpus invalida a baseline e não a sobrescreve. Trocar algoritmo,
chunking, modelo ou provedor é permitido sem decisão humana quando o corpus continua
igual, as métricas absolutas passam e nenhum perfil ultrapassa a regressão permitida.

O campo `promocoes_candidatas` lista documentos citados com sucesso no número mínimo de
casos configurado. É evidência para promoção ao núcleo, não autorização para reescrever
`memoria.nucleo` nem para publicar qualquer mudança.

## Reconstrução e limites

Relatório e manifesto possuem SHA-256 e são comparados byte a byte com uma reconstrução
atual. Hindsight e Graphify continuam derivados e com autoridade zero. A avaliação mede
o contexto recuperado; ela não mede redação livre de uma LLM e não converte uma resposta
sem fonte em verdade.
