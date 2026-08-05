"""gerar — extrai do código o que não deve ser escrito à mão.

REGRA DE OURO: a saída precisa ser REPRODUTÍVEL. Rodar duas vezes produz bytes
idênticos. Tudo ordenado, nada de timestamp além do carimbo normalizado, caminhos
sempre relativos.

EXTRATORES DO PROJETO — protocolo NEUTRO DE LINGUAGEM (mudou no porte para Python):

    `gerado.extensao_do_projeto` aponta para um EXECUTÁVEL do projeto — PHP, Python,
    shell, o que o projeto tiver. O gerador o executa e lê JSON do stdout:

        [{"nome": "tabelas", "id": "GERADO-TABELAS", "titulo": "...", "corpo": "..."}]

    Por que executável e não módulo importado: o core não pode ditar a linguagem dos
    projetos. O DAZASYNC escreve extratores em PHP (é o que ele tem); um projeto Python
    escreve em .py — e o mesmo core serve os dois. `nome` repetido SOBRESCREVE um
    extrator embutido; o nome vira o arquivo `<nome>.md`.
"""

from __future__ import annotations

import glob as _glob
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

from .lib import (acervo, arquivos_por_extensao, barras, comeca_com, commit_atual,
                  config, frontmatter, markdowns, morre, pacote, raiz, relativo, titulo)


def cabecalho(id_: str, titulo_: str, projeto: str, commit: str) -> str:
    return (
        "---\n"
        f"id: {id_}\n"
        "tipo: gerado\n"
        f"projeto: {projeto}\n"
        f"titulo: {titulo_}\n"
        "status: verificado\n"
        f"verificado_em: {date.today().isoformat()}\n"
        f"verificado_commit: {commit}\n"
        "---\n\n"
        "> ⚠️ **ARQUIVO GERADO AUTOMATICAMENTE.** Não edite à mão — sua alteração será sobrescrita.\n"
        f"> Gerado por `memoria gerar` em `{commit}`.\n\n"
    )


def tem_algum_arquivo(dir_: str) -> bool:
    """Recursivo, porque git não versiona diretório vazio — uma pasta que sobrou de uma
    troca de branch existe na máquina de quem trabalha e NÃO existe no runner, e sem
    esta checagem a saída diverge entre os dois sem nada de errado ter acontecido."""
    p = Path(dir_)
    return p.is_dir() and any(f.is_file() for f in p.rglob("*"))


# ═══════════════════════════════════════════════════════════ extratores embutidos

def extrator_mapa_diretorios(c: dict) -> tuple[str, str]:
    raiz_codigo = raiz() + "/" + c["gerado"]["raiz"].strip("/")
    exts = c["gerado"].get("extensoes", ["php"])

    if not Path(raiz_codigo).is_dir():
        return ("Mapa de diretórios", f"Diretório `{c['gerado']['raiz']}` não existe.\n")

    def conta(dir_: str) -> int:
        return sum(len(arquivos_por_extensao(dir_, e)) for e in exts)

    dirs = sorted(barras(d) for d in _glob.glob(raiz_codigo + "/*") if Path(d).is_dir())
    linhas: list[str] = []
    total = 0

    # ARQUIVOS SOLTOS NA RAIZ CONTAM — a primeira versão só via subpastas e escrevia
    # "Total: 0" num projeto com tudo solto em src/, passando na verificação porque a
    # saída era reprodutível. Reprodutível e falsa.
    na_raiz = sum(
        1 for e in exts for f in _glob.glob(raiz_codigo + "/*." + e) if Path(f).is_file()
    )
    if na_raiz:
        total += na_raiz
        linhas.append(f"| `{c['gerado']['raiz'].strip('/')}/` *(raiz)* | {na_raiz} | — |")

    for d in dirs:
        if not tem_algum_arquivo(d):
            continue
        n = conta(d)
        total += n
        subs = []
        for sub in sorted(barras(s) for s in _glob.glob(d + "/*") if Path(s).is_dir()):
            cn = conta(sub)
            if cn > 0:
                subs.append(f"`{Path(sub).name}` ({cn})")
        linhas.append(
            f"| `{c['gerado']['raiz'].strip('/')}/{Path(d).name}/` | {n} | "
            + (" · ".join(subs) if subs else "—") + " |"
        )

    corpo = f"Contagem de arquivos por diretório em `{c['gerado']['raiz'].strip('/')}/`.\n"
    corpo += "Extensões consideradas: `" + "`, `".join(exts) + "`.\n\n"
    corpo += "Diretório sem nenhum arquivo é ignorado — git não versiona pasta vazia,\n"
    corpo += "então ela existiria só na máquina de quem trabalha.\n\n"
    corpo += "| Diretório | Arquivos | Subdiretórios com conteúdo |\n|---|---:|---|\n"
    corpo += ("\n".join(linhas) if linhas else "| — | 0 | — |") + "\n\n"
    n = len(linhas)
    corpo += (
        f"**Total: {total} " + ("arquivo" if total == 1 else "arquivos")
        + f" em {n} " + ("diretório" if n == 1 else "diretórios") + ".**\n"
    )
    return ("Mapa de diretórios", corpo)


def extrator_cadeia_documentos(c: dict) -> tuple[str, str]:
    """Mapa da cadeia PRD → FDD → HLD → LLD → ADR, extraído do frontmatter.

    Ninguém mantém à mão uma visão que depende de ler o cabeçalho do acervo inteiro —
    e visão errada da cadeia é pior que nenhuma, porque é o que se consulta para decidir
    o que revisar.
    """
    niveis = c.get("cadeia", {}).get("niveis", {})
    livres = c.get("cadeia", {}).get("livres", [])
    ignorar = c["acervos"].get("ignorar", [])
    dir_ger = c["gerado"].get("diretorio", "docs/gerado").strip("/")
    subir = "../" * (dir_ger.count("/") + 1)

    def na_cadeia(t: str) -> bool:
        return t in niveis or t in livres

    docs: dict[str, dict] = {}
    for f in markdowns(acervo()):
        rel = relativo(f)
        if comeca_com(rel, ignorar):
            continue
        fm = frontmatter(Path(f).read_text(encoding="utf-8"))
        if not fm or not fm.get("id") or not na_cadeia(fm.get("tipo", "")):
            continue
        pais = fm.get("deriva_de") or []
        if isinstance(pais, str):
            pais = [pais]
        docs[fm["id"]] = {
            "tipo": fm["tipo"],
            "titulo": fm.get("titulo", "(sem título)"),
            "status": fm.get("status", "?"),
            "rel": rel,
            "pais": [p for p in pais if p],
        }

    if not docs:
        tipos = "`, `".join(list(niveis.keys()) + list(livres))
        return ("Cadeia de documentos",
                f"Nenhum documento da cadeia (`{tipos}`) foi escrito ainda.\n\n"
                "Isso é um estado válido — a cadeia serve para o que precisa de rastro entre\n"
                "requisito e código, e nem todo projeto precisa dos quatro níveis.\n")

    filhos: dict[str, list[str]] = {}
    for id_, d in docs.items():
        for p in d["pais"]:
            filhos.setdefault(p, []).append(id_)
    for lista in filhos.values():
        lista.sort()

    marca = {"verificado": "✅", "rascunho": "📝", "superado": "🗑️"}

    corpo = (
        "Extraído do campo `deriva_de` do frontmatter. **A ordem é do problema para o\n"
        "código:** PRD (por que fazer) → FDD (o que o sistema faz) → HLD (como está\n"
        "organizado) → LLD (como está construído). O ADR atravessa todos.\n\n"
        "Use esta tabela para responder à pergunta que evita documentação podre:\n"
        "**quando este documento mudar, o que mais preciso revisar?** — é a coluna\n"
        '"quem depende deste".\n\n'
        "> ⚠️ **Esta coluna só enxerga o que está declarado em `deriva_de`.** Documento\n"
        "> que cita outro apenas em prosa aparece aqui como se ninguém dependesse dele —\n"
        "> e some da revisão exatamente quando mais importa, no dia em que a origem cai.\n\n"
        "| Documento | Tipo | Estado | Depende de | Quem depende deste |\n|---|---|:-:|---|---|\n"
    )
    for id_ in sorted(docs):
        d = docs[id_]
        dep = "`" + "`, `".join(d["pais"]) + "`" if d["pais"] else "—"
        qd = "`" + "`, `".join(filhos[id_]) + "`" if id_ in filhos else "—"
        corpo += (f"| [`{id_}`]({subir}{d['rel']}) — {d['titulo']} | `{d['tipo']}` | "
                  f"{marca.get(d['status'], '❔')} | {dep} | {qd} |\n")

    raizes = sorted(i for i, d in docs.items() if not d["pais"])
    if raizes:
        corpo += "\n## Árvore\n\n```\n"

        def desenhar(id_: str, prefixo: str, vistos: frozenset) -> str:
            # `vistos` impede o laço infinito com ciclo — aconteceu de verdade: o
            # processo consumiu a memória da máquina e foi morto pelo sistema.
            if id_ in vistos:
                return f"{prefixo}↻ {id_} · (ciclo — ver `memoria validar`)\n"
            d = docs[id_]
            s = f"{prefixo}{marca.get(d['status'], '❔')} {id_} · {d['titulo']}\n"
            for f_ in filhos.get(id_, []):
                s += desenhar(f_, prefixo + "    ", vistos | {id_})
            return s

        for r in raizes:
            corpo += desenhar(r, "", frozenset())
        corpo += "```\n"

    # Superado que ninguém aponta é suspeito: ou era isolado, ou quem dependia dele o
    # citava só em prosa — e agora está fora de toda revisão, com o build verde.
    orfaos = sorted(i for i, d in docs.items() if d["status"] == "superado" and i not in filhos)
    if orfaos:
        corpo += "\n## ⚠️ Superados que ninguém declara depender\n\n"
        corpo += "`" + "`, `".join(orfaos) + "`\n\n"
        corpo += ("Confira se é mesmo isolado. **Se algum documento descrevia o efeito de um\n"
                  "destes sem citá-lo em `deriva_de`, ele está agora fora de toda revisão** —\n"
                  "afirmando um comportamento que o projeto abandonou, com o build verde.\n\n"
                  "Como procurar o que o frontmatter não pega:\n\n"
                  f"```\ngrep -rn \"{orfaos[0]}\" docs/\n```\n\n"
                  "E depois pelo assunto, não pelo id — é assim que estes casos se escondem.\n")

    por_tipo: dict[str, int] = {}
    for d in docs.values():
        por_tipo[d["tipo"]] = por_tipo.get(d["tipo"], 0) + 1
    resumo = " · ".join(f"{n} `{t}`" for t, n in sorted(por_tipo.items()))
    corpo += f"\n**Total: {len(docs)} documentos na cadeia — {resumo}.**\n"
    corpo += "\nLegenda: ✅ verificado · 📝 rascunho · 🗑️ superado\n"
    return ("Cadeia de documentos", corpo)


# ═══════════════════════════════════════════════════════════ execução

def _extratores_do_projeto(c: dict) -> dict[str, dict]:
    ext = c.get("gerado", {}).get("extensao_do_projeto")
    if not ext:
        return {}
    abs_ = Path(raiz()) / ext
    if not abs_.is_file():
        morre(f"`gerado.extensao_do_projeto` aponta para `{ext}`, que não existe.\n"
              "Crie o arquivo ou remova a chave do padrao.json.\n")

    # Executável em qualquer linguagem, decidido pela extensão; saída = JSON no stdout.
    sufixo = abs_.suffix.lower()
    interpretes = {".php": ["php"], ".py": [sys.executable], ".sh": ["bash"], ".js": ["node"]}
    cmd = interpretes.get(sufixo, []) + [str(abs_)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=raiz(), timeout=120)
    except FileNotFoundError:
        morre(f"Para rodar `{ext}` preciso de `{cmd[0]}`, que não está instalado.\n")
    if r.returncode != 0:
        morre(f"`{ext}` falhou (exit {r.returncode}):\n{r.stderr[:500]}\n")
    try:
        lista = json.loads(r.stdout)
    except json.JSONDecodeError:
        morre(f"`{ext}` precisa imprimir JSON no stdout: uma lista de "
              '{"nome","id","titulo","corpo"}.\n'
              f"Recebi: {r.stdout[:200]!r}\n")

    extras: dict[str, dict] = {}
    for item in lista:
        if not all(k in item for k in ("nome", "id", "titulo", "corpo")):
            morre(f"Extrator em `{ext}` sem os campos nome/id/titulo/corpo: {item.get('nome')!r}\n")
        extras[item["nome"]] = item
    return extras


def main() -> int:
    c = config()
    saida = Path(raiz()) / c["gerado"]["diretorio"].strip("/")
    saida.mkdir(parents=True, exist_ok=True)
    commit = commit_atual() or "desconhecido"

    embutidos = {
        "mapa-diretorios": ("GERADO-MAPA", extrator_mapa_diretorios),
        "cadeia-documentos": ("GERADO-CADEIA", extrator_cadeia_documentos),
    }
    extras = _extratores_do_projeto(c)

    feitos = []
    for nome in c["gerado"].get("extratores", []):
        if nome in extras:
            item = extras[nome]
            id_, titulo_, corpo = item["id"], item["titulo"], item["corpo"]
        elif nome in embutidos:
            id_, fn = embutidos[nome]
            titulo_, corpo = fn(c)
        else:
            morre(f"Extrator `{nome}` declarado em padrao.json mas não existe — nem embutido, "
                  "nem na extensão do projeto.\n")
        arq = saida / f"{nome}.md"
        arq.write_text(
            cabecalho(id_, titulo_, c["projeto"], commit) + f"# {titulo_}\n\n" + corpo,
            encoding="utf-8",
        )
        feitos.append(relativo(str(arq)))

    titulo(f"Derivados gerados em `{commit}`")
    for f in feitos:
        print(f"  {f}")
    print("\nNunca edite estes arquivos à mão — `memoria validar` reprova se você editar.")
    return 0
