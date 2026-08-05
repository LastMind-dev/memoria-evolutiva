"""instalar — publica o padrão num projeto, novo ou existente.

O que faz: publica os stubs (SEM sobrescrever nada), garante a árvore com .gitkeep,
escreve/ajusta o padrao.json, troca <NOME-DO-PROJETO> pelo nome real, transforma o
modelo de cronologia no mês corrente.

O que NÃO faz, de propósito: não preenche o PROJETO.md (as oito decisões são suas — um
PROJETO.md genérico é pior que nenhum, porque parece pronto), não roda gerador, não mede
catraca, não commita. É seguro rodar de novo.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import date
from pathlib import Path

from .lib import barras, markdowns, morre, pacote

ARVORE = [
    "docs/cronologia", "docs/produto", "docs/funcional", "docs/arquitetura",
    "docs/decisoes", "docs/runbooks", "docs/evidencia", "docs/politicas",
    "docs/gerado", "docs/_templates", "docs/_arquivo",
]

GITKEEP = ("Marcador para o git preservar esta pasta enquanto ela estiver vazia.\n"
           "Pode apagar quando houver conteúdo aqui.\n")


def _publicar(de: Path, para: Path, criados: list, existiam: list) -> None:
    """Copiar SEM SOBRESCREVER — o que já existe é decisão de alguém e não se toca."""
    if not de.is_dir():
        return
    for item in sorted(de.iterdir()):
        destino = para / item.name
        if item.is_dir():
            destino.mkdir(parents=True, exist_ok=True)
            _publicar(item, destino, criados, existiam)
        elif destino.is_file():
            existiam.append(str(destino))
        else:
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, destino)
            criados.append(str(destino))


def _config_nova(projeto: str, codigo: str, indice: bool, ferramenta: str | None,
                 grafo: str | None, raiz_: str) -> dict:
    return {
        "projeto": projeto,
        "acervos": {
            "canonico": "docs",
            "exploracao": None,
            "indice": "externo" if indice else None,
            "ignorar": ["docs/_templates/", "docs/_arquivo/"],
        },
        "vocabulario": {
            "tipo": ["entrada", "estado", "cronologia", "prd", "fdd", "hld", "lld",
                     "adr", "runbook", "politica", "evidencia", "gerado"],
            "status": ["rascunho", "verificado", "superado"],
            "obrigatorios": ["id", "tipo", "projeto", "titulo", "status"],
        },
        "cadeia": {
            "niveis": {"prd": 0, "fdd": 1, "hld": 2, "lld": 3},
            "livres": ["adr"],
            "exige_origem": ["fdd", "hld", "lld"],
        },
        "externos": {"pastas": []},
        # Só entram os ponteiros que EXISTEM — declarar ausente vira aviso permanente,
        # e aviso permanente é ruído que treina todo mundo a não ler a saída.
        "ponteiros": {
            "limite_de_linhas": 40,
            "arquivos": [p for p in
                         ["CLAUDE.md", "AGENTS.md", ".cursor/rules/projeto.mdc", ".windsurfrules"]
                         if (Path(raiz_) / p).is_file()],
        },
        "gerado": {
            "diretorio": "docs/gerado",
            "raiz": codigo,
            "extensoes": ["php"],
            "extratores": ["mapa-diretorios", "cadeia-documentos"],
            "extensao_do_projeto": None,
        },
        "catraca": {
            "linha_de_base": "docs/politicas/baseline.json",
            "contadores": [{
                "chave": "docs_sem_frontmatter",
                "rotulo": "estrutura · documento sem frontmatter",
                "tipo": "markdown_sem_frontmatter",
                "onde": "docs",
                "excluir": ["docs/_arquivo/", "docs/_templates/"],
            }],
        },
        "memoria": {
            "ativo": indice,
            "ferramenta": ferramenta,
            "marcador": "docs/.indexado.json",
            "nucleo": ["docs/PROJETO.md", "docs/ESTADO.md", "docs/ABERTO.md",
                       "docs/GLOSSARIO.md", "docs/cronologia/", "docs/produto/",
                       "docs/funcional/", "docs/arquitetura/", "docs/decisoes/",
                       "docs/politicas/", "docs/runbooks/", "docs/evidencia/",
                       "docs/gerado/"],
            "ignorar": ["docs/_arquivo/", "docs/_templates/"],
        },
        "grafo": {"ativo": grafo is not None, "ferramenta": grafo, "comando_de_build": None},
    }


def main(argv: list[str]) -> int:
    args: dict[str, str | bool] = {}
    for a in argv:
        m = re.match(r"^--([a-z]+)(?:=(.*))?$", a)
        if m:
            args[m.group(1)] = m.group(2) if m.group(2) is not None else True

    projeto = args.get("projeto")
    codigo = str(args.get("codigo", "src"))
    indice_opt = args.get("indice")
    indice = indice_opt is not None and indice_opt is not False
    ferramenta = indice_opt.lower() if isinstance(indice_opt, str) and indice_opt else None
    grafo_opt = args.get("grafo")
    grafo = grafo_opt.lower() if isinstance(grafo_opt, str) and grafo_opt else None

    if not isinstance(projeto, str) or not projeto:
        print("Faltou --projeto.\n")
        print('  memoria instalar --projeto="meu-app" --codigo=src\n')
        print("Opções:")
        print("  --projeto=NOME    obrigatório. Vai no frontmatter de todo documento.")
        print("  --codigo=PASTA    onde o código vive (padrão: src). O gerador varre daí.")
        print("  --indice[=NOME]   o projeto usa RAG/índice semântico (ex.: --indice=hindsight).")
        print("  --grafo=NOME      o projeto usa grafo de código (ex.: --grafo=code-review-graph).")
        return 2

    # A raiz do projeto é o CWD — rode o instalador na raiz. (raiz() da lib procuraria
    # padrao.json acima, o que num projeto virgem também acaba no cwd.)
    raiz_ = barras(os.getcwd())
    criados: list[str] = []
    existiam: list[str] = []
    ajustados: list[str] = []

    # ------------------------------------------------- publicar os stubs do pacote
    _publicar(Path(pacote()) / "stubs", Path(raiz_), criados, existiam)

    # ferramenta declarada já entra no runbook de indexação publicado
    run_idx = Path(raiz_) / "docs/runbooks/indexacao.md"
    if ferramenta and run_idx.is_file():
        t = run_idx.read_text(encoding="utf-8")
        run_idx.write_text(t.replace("<qual — Hindsight, pgvector, Qdrant...>", ferramenta),
                           encoding="utf-8")

    # ------------------------------------------------------------------- árvore
    # git não versiona diretório vazio: sem .gitkeep a árvore some no clone e o
    # PROJETO.md nasce apontando para pastas que, para quem clonou, não existem.
    for d in ARVORE:
        p = Path(raiz_) / d
        p.mkdir(parents=True, exist_ok=True)
        guarda = p / ".gitkeep"
        if not guarda.is_file():
            guarda.write_text(GITKEEP, encoding="utf-8")

    # ------------------------------------------------------------- padrao.json
    # Nunca sobrescreva DECISÃO DE ALGUÉM — mas placeholder não é decisão de ninguém.
    # (Numa instalação real o nome de exemplo ficou e TODO derivado saiu carimbado
    # errado, com build verde.)
    arq_config = Path(raiz_) / "padrao.json"
    config_ = _config_nova(projeto, codigo, indice, ferramenta, grafo, raiz_)

    if not arq_config.is_file():
        arq_config.write_text(json.dumps(config_, ensure_ascii=False, indent=4) + "\n",
                              encoding="utf-8")
        criados.append(str(arq_config))
    else:
        try:
            atual = json.loads(arq_config.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            morre(f"`padrao.json` existe mas não é JSON válido: {e.msg}\n"
                  "Conserte ou apague o arquivo e rode de novo.\n")

        placeholders = ["", "meu-projeto", "<NOME-DO-PROJETO>", "nome-do-projeto"]
        if str(atual.get("projeto", "")) in placeholders:
            atual["projeto"] = projeto
            ajustados.append(f"projeto → {projeto}")
        elif atual.get("projeto") != projeto:
            ajustados.append(f"projeto MANTIDO como `{atual['projeto']}` (já estava preenchido; "
                             f"você pediu `{projeto}` — se quis mesmo trocar, edite à mão)")

        if atual.get("gerado", {}).get("raiz") in ("", "src", None) and codigo != "src":
            atual.setdefault("gerado", {})["raiz"] = codigo
            ajustados.append(f"gerado.raiz → {codigo}")

        if indice and not atual.get("memoria", {}).get("ativo"):
            atual.setdefault("memoria", {})["ativo"] = True
            ajustados.append("memoria.ativo → true")
        if ferramenta and not atual.get("memoria", {}).get("ferramenta"):
            atual.setdefault("memoria", {})["ferramenta"] = ferramenta
            ajustados.append(f"memoria.ferramenta → {ferramenta}")
        if grafo and not atual.get("grafo", {}).get("ativo"):
            atual["grafo"] = {"ativo": True, "ferramenta": grafo, "comando_de_build": None}
            ajustados.append(f"grafo.ferramenta → {grafo}")
        if "ponteiros" not in atual:
            atual["ponteiros"] = config_["ponteiros"]
            ajustados.append("ponteiros → " + ", ".join(config_["ponteiros"]["arquivos"]))
        else:
            atual["ponteiros"]["arquivos"] = [
                p for p in atual["ponteiros"].get("arquivos", [])
                if (Path(raiz_) / p).is_file()
            ]

        if ajustados:
            arq_config.write_text(json.dumps(atual, ensure_ascii=False, indent=4) + "\n",
                                  encoding="utf-8")
        else:
            existiam.append(str(arq_config))

    # ---------------------------------------------- modelo de cronologia → mês real
    mes = date.today().strftime("%Y-%m")
    modelo_cr = Path(raiz_) / "docs/cronologia/AAAA-MM.md"
    mes_cr = Path(raiz_) / f"docs/cronologia/{mes}.md"

    if modelo_cr.is_file() and not mes_cr.is_file():
        texto = modelo_cr.read_text(encoding="utf-8")
        texto = texto.replace("AAAA-MM", mes).replace("<mês> de <ano>", mes)
        mes_cr.write_text(texto, encoding="utf-8")
        modelo_cr.unlink()
        criados.append(str(mes_cr))
    # o mês já existia (todo projeto vivo tem) → o modelo publicado sairia órfão
    if modelo_cr.is_file() and mes_cr.is_file():
        modelo_cr.unlink()

    if not mes_cr.is_file():
        mes_cr.write_text(
            f"---\nid: CRONOLOGIA-{mes}\ntipo: cronologia\nprojeto: {projeto}\n"
            f"titulo: Cronologia — {mes}\nstatus: rascunho\n---\n\n"
            f"# Cronologia — {mes}\n\n"
            "> **Append-only.** Entradas antigas não são editadas — correção entra como entrada\n"
            "> nova referenciando a anterior. Mais recente no topo.\n\n---\n\n",
            encoding="utf-8")
        criados.append(str(mes_cr))

    # ------------------------------------- placeholder → nome real (idempotente)
    trocados: list[str] = []
    for md in markdowns(str(Path(raiz_) / "docs")):
        texto = Path(md).read_text(encoding="utf-8")
        if "<NOME-DO-PROJETO>" not in texto:
            continue
        Path(md).write_text(texto.replace("<NOME-DO-PROJETO>", projeto), encoding="utf-8")
        trocados.append(barras(md).replace(raiz_ + "/", ""))

    faltando = [f"docs/{e}.md" for e in ("PROJETO", "ESTADO", "ABERTO", "GLOSSARIO")
                if not (Path(raiz_) / f"docs/{e}.md").is_file()]

    # ------------------------------------------------------------------- relatório
    print(f"\nEstrutura do padrão — {projeto}")
    print("─" * 60)
    if criados:
        print("\nCriados:")
        for c_ in sorted(criados):
            print("  + " + barras(c_).replace(raiz_ + "/", ""))
    if existiam:
        print("\nJá existiam, não toquei:")
        for c_ in sorted(existiam)[:15]:
            print("  = " + barras(c_).replace(raiz_ + "/", ""))
        if len(existiam) > 15:
            print(f"  = ... e mais {len(existiam) - 15}")
    if ajustados:
        print("\nAjustado no padrao.json que já existia:")
        for a in ajustados:
            print(f"  ~ {a}")
    if trocados:
        print("\nNome do projeto preenchido em:")
        for t in trocados:
            print(f"  ~ {t}")
    if faltando:
        print("\nATENÇÃO — faltam arquivos de entrada:")
        for f in faltando:
            print(f"  ! {f}")

    print("\n" + "─" * 60)
    print("PRÓXIMOS PASSOS, nesta ordem:\n")
    print("  1. Preencha, nesta ordem, os arquivos de entrada que já estão em docs/:")
    print("       docs/PROJETO.md    ← as OITO DECISÕES. Sem elas nada funciona.")
    print("       docs/ESTADO.md     ← onde o projeto está hoje")
    print("       docs/ABERTO.md     ← comece vazio; ele enche sozinho")
    print("       docs/GLOSSARIO.md  ← os termos que você já explicou duas vezes")
    print("     Documento novo? copie o molde de docs/_templates/.\n")
    print("  2. memoria gerar")
    print("  3. memoria catraca --medir      ← congela a dívida atual")
    print("  4. memoria validar              ← precisa passar")
    print("  5. memoria autoteste            ← o alarme de incêndio")
    if indice:
        print("  6. indexe o núcleo e rode: memoria indice --marcar")
    print("\n  Por último — e é o critério de aceitação de verdade:")
    print("  abra uma sessão nova, num modelo que nunca viu o projeto, e mande:")
    print('  "comece por docs/PROJETO.md, siga a ordem de leitura, e me diga onde o')
    print('  projeto está e o que eu não posso fazer".')
    print("\n  Leia a parte que ele errar com mais atenção do que a que ele acertar.")
    return 0
