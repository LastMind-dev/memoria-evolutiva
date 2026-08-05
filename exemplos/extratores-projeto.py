#!/usr/bin/env python3
"""extratores-projeto.py — modelo de extratores PRÓPRIOS do projeto.

PROTOCOLO (neutro de linguagem): este arquivo é um EXECUTÁVEL que imprime no stdout
um JSON com a lista de documentos derivados:

    [{"nome": "...", "id": "GERADO-...", "titulo": "...", "corpo": "markdown..."}]

O `memoria gerar` roda este arquivo (declarado em `padrao.json` →
`gerado.extensao_do_projeto`) com o cwd na raiz do projeto, lê o JSON e escreve um
`docs/gerado/<nome>.md` por item — com o frontmatter e o aviso de arquivo gerado por
conta dele. Um `nome` igual ao de um extrator embutido (`mapa-diretorios`,
`cadeia-documentos`) SOBRESCREVE o embutido.

Cada `nome` precisa estar declarado também em `padrao.json` → `gerado.extratores`.

Este arquivo é DO PROJETO: versione-o no seu repositório (por convenção em
`scripts/`), e escreva na linguagem que o projeto já fala — .py, .php, .sh e .js
são reconhecidos pela extensão. O primeiro projeto migrado manteve os dele em PHP;
este modelo mostra o mesmo protocolo em Python.

REGRA DE OURO: só extraia o que dá para extrair DO CÓDIGO. O que exige julgamento
humano é documento escrito à mão, não gerado.
"""

import json
import re
from pathlib import Path

RAIZ = Path.cwd()  # `memoria gerar` roda o extrator com cwd na raiz do projeto


def dependencias() -> dict:
    """Exemplo: lista as dependências diretas declaradas — sem resolver versões.

    Troque pelo que o SEU projeto tem de extraível: tabelas do banco, rotas,
    comandos de CLI, feature flags, filas...
    """
    linhas = []
    pyproject = RAIZ / "pyproject.toml"
    if pyproject.is_file():
        texto = pyproject.read_text(encoding="utf-8")
        m = re.search(r"^dependencies\s*=\s*\[(.*?)\]", texto, re.S | re.M)
        if m:
            for dep in re.findall(r'"([^"]+)"', m.group(1)):
                linhas.append(f"- `{dep}`")
    pacote_json = RAIZ / "package.json"
    if pacote_json.is_file():
        j = json.loads(pacote_json.read_text(encoding="utf-8"))
        for nome, versao in sorted(j.get("dependencies", {}).items()):
            linhas.append(f"- `{nome}` {versao}")

    corpo = "Dependências diretas declaradas nos manifestos do projeto.\n\n"
    corpo += "\n".join(linhas) + "\n" if linhas else "_Nenhum manifesto encontrado._\n"
    return {
        "nome": "dependencias",
        "id": "GERADO-DEPENDENCIAS",
        "titulo": "Dependências diretas",
        "corpo": corpo,
    }


if __name__ == "__main__":
    print(json.dumps([dependencias()], ensure_ascii=False))
