"""analisar — transforma o inventário em evidências e perguntas, sem inventar fatos."""

from __future__ import annotations

import json

from .diagnosticar import coletar


def lacunas(d: dict) -> list[str]:
    repo = d["repositorio"]
    perguntas = [
        "Qual problema o projeto resolve, para quem e qual é o custo de errar?",
        "Quais ambientes existem e quais operações exigem autorização explícita?",
        "Quais são os fluxos funcionais principais e suas exceções?",
        "Quais bancos, filas, APIs e serviços externos participam do sistema?",
        "Quais decisões arquiteturais fecharam alternativas importantes, e por quê?",
        "Como validar, publicar e reverter uma mudança em cada ambiente?",
    ]
    if repo["arquivos_de_teste"] == 0:
        perguntas.append("Não foram detectados testes: como o comportamento é verificado hoje?")
    if not repo["workflows"]:
        perguntas.append("Não foi detectado CI em `.github/workflows`: onde a integração roda?")
    if not repo["manifestos"]:
        perguntas.append("Nenhum manifesto foi detectado na raiz: onde a stack é declarada?")
    return perguntas


def consolidar(d: dict) -> dict:
    repo = d["repositorio"]
    codigo = d["codigo"]
    return {
        "schema": 1,
        "projeto": d["projeto"],
        "evidencias": {
            "versao": d["git"],
            "codigo": codigo,
            "manifestos": repo["manifestos"],
            "workflows": repo["workflows"],
            "testes_detectados": repo["arquivos_de_teste"],
            "areas_detectadas": {
                k: v for k, v in repo["diretorios_relevantes"].items() if v
            },
        },
        "lacunas_para_confirmar": lacunas(d),
    }


def como_markdown(a: dict) -> str:
    e = a["evidencias"]
    linhas = [
        "Análise inicial baseada somente em evidência observável. Toda lacuna abaixo",
        "precisa de confirmação antes de virar documentação canônica.\n",
        "## Evidências confirmadas automaticamente\n",
        f"- Código configurado: **{e['codigo']['arquivos']} arquivos** em "
        f"`{e['codigo']['raiz'] or '.'}`.",
        "- Manifestos: " + (", ".join(f"`{m}`" for m in e["manifestos"]) or "nenhum"),
        f"- Workflows detectados: **{len(e['workflows'])}**.",
        f"- Arquivos de teste detectados: **{e['testes_detectados']}**.",
    ]
    if e["areas_detectadas"]:
        linhas.append("- Áreas estruturais detectadas:")
        for categoria, dirs in e["areas_detectadas"].items():
            linhas.append(f"  - {categoria.replace('_', ' ')}: " + ", ".join(f"`{d}`" for d in dirs))
    linhas.extend(["\n## Lacunas que impedem documentação verificada\n"])
    for i, pergunta in enumerate(a["lacunas_para_confirmar"], 1):
        linhas.append(f"{i}. {pergunta}")
    linhas.extend([
        "\n## Próximo passo seguro\n",
        "Use `memoria documentar` para promover automaticamente os fatos demonstráveis.",
        "O que não tiver evidência suficiente ficará explícito como `indeterminado`.",
    ])
    return "\n".join(linhas).rstrip() + "\n"


def main(argv: list[str]) -> int:
    desconhecidos = [a for a in argv if a != "--json"]
    if desconhecidos:
        print("Opção desconhecida em `memoria analisar`: " + ", ".join(desconhecidos))
        return 2
    analise = consolidar(coletar())
    if "--json" in argv:
        print(json.dumps(analise, ensure_ascii=False, indent=2))
    else:
        print(como_markdown(analise), end="")
    return 0
