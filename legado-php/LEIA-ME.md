# Motor legado em PHP — arquivado, não mantido

Esta pasta guarda a primeira implementação do padrão, em PHP, **congelada em
2026-08-05**. O motor mantido é o pacote Python na raiz do repositório
(`memoria_evolutiva/`), instalável via `pipx install memoria-evolutiva`.

## Por que foi aposentado

O padrão em si é neutro de linguagem — os validadores só leem arquivos e comparam
hashes. A implementação Python foi validada com **paridade byte a byte** contra esta,
na mesma árvore real (DAZASYNC, 1969 arquivos):

- os 7 contadores da catraca devolvem os mesmos números;
- o marcador de índice gravado por um motor é lido verde pelo outro;
- os arquivos derivados saem byte-idênticos (fora a linha `> Gerado por ...`);
- o autoteste (15 cenários) passa igual nos dois.

Um motor só, num ecossistema maior (pipx/PyPI), custa menos que dois em paridade
eterna.

## Isto continua funcionando

`composer require lastmind-dev/memoria-evolutiva` continua instalando este motor e o
`vendor/bin/memoria` continua operando — projetos que já o usam não quebram. Mas
correções e regras novas entram **só no motor Python**. Para trocar:

```bash
pipx install memoria-evolutiva
memoria gerar        # regere os derivados UMA vez: a linha "Gerado por" muda de motor
memoria verificar
```

Os extratores próprios do projeto continuam valendo nas duas direções — o protocolo é
neutro (executável que imprime JSON; ver `exemplos/extratores-projeto.py` e o
MIGRAR.md da raiz).

## O que há aqui

- `bin/memoria` — o proxy de subcomandos que o Composer instala em `vendor/bin/`
- `scripts/` — os oito scripts do motor (a lógica, com os comentários de porquê)
- `stubs/` — cópia congelada dos stubs da época do arquivamento (o canônico vive em
  `memoria_evolutiva/stubs/`)
