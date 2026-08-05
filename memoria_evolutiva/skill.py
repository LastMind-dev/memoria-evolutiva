"""skill — reconstrói o pacote de skill/procedimento a partir dos arquivos versionados.

A FONTE do protocolo de sessão é `docs/runbooks/sessao.md` (ou o runbook do projeto),
versionado. A skill instalada numa ferramenta é ARTEFATO DERIVADO — princípio 1 do
método aplicado a ele mesmo. `--conferir` avisa quando a fonte mudou depois da última
geração: aviso, não erro — skill velha não quebra o produto, só ensina o procedimento
antigo.
"""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

from .lib import commit_atual, hash_do_conteudo, pacote, raiz, relativo, titulo

FONTES = {
    "docs/runbooks/sessao.md": "references/sessao-do-projeto.md",
    "docs/runbooks/fim-de-sessao.md": "references/sessao-do-projeto.md",
    "docs/runbooks/indexacao.md": "references/indexacao-do-projeto.md",
}

PULAR = {".git", "node_modules", "vendor", "__pycache__"}


def _copiar(de: Path, para: Path) -> int:
    para.mkdir(parents=True, exist_ok=True)
    n = 0
    for item in de.iterdir():
        if item.name in PULAR:
            continue
        destino = para / item.name
        if item.is_dir():
            n += _copiar(item, destino)
        else:
            shutil.copy2(item, destino)
            n += 1
    return n


def main(argv: list[str]) -> int:
    conferir = "--conferir" in argv
    saida = Path(raiz()) / "skill-memoria-evolutiva"
    for a in argv:
        if a.startswith("--saida="):
            saida = Path(a.split("=", 1)[1])

    marcador = Path(raiz()) / "docs/.skill-gerada.json"

    if conferir:
        if not marcador.is_file():
            print("Nunca foi gerada. Rode `memoria skill` quando quiser o pacote.")
            return 0
        j = json.loads(marcador.read_text(encoding="utf-8"))
        ref = j.get("fontes", {})
        velhas = []
        for orig in FONTES:
            abs_ = Path(raiz()) / orig
            if not abs_.is_file():
                continue
            h = hash_do_conteudo(abs_.read_text(encoding="utf-8"))
            if ref.get(orig) != h:
                velhas.append(orig)
        titulo(f"Skill derivada — gerada em {j.get('gerada_em', '?')}")
        if not velhas:
            print("  Em dia com os arquivos de origem.")
            return 0
        print("  Mudaram desde a última geração:")
        for v in velhas:
            print(f"    ~ {v}")
        print("\n  A skill instalada está ensinando a versão antiga. Rode:")
        print("    memoria skill")
        print("\n  Aviso, não erro: skill velha não quebra o produto — só faz o agente")
        print("  seguir um procedimento que o projeto já mudou.")
        return 0

    (saida / "references").mkdir(parents=True, exist_ok=True)
    (saida / "assets").mkdir(parents=True, exist_ok=True)
    copiados = _copiar(Path(pacote()), saida / "assets/kit")

    levados: dict[str, str] = {}
    for orig, dest in FONTES.items():
        abs_ = Path(raiz()) / orig
        if not abs_.is_file():
            continue
        destino = saida / dest
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(abs_, destino)
        levados[orig] = hash_do_conteudo(abs_.read_text(encoding="utf-8"))

    marcador.write_text(json.dumps({
        "gerada_em": date.today().isoformat(),
        "commit": commit_atual(),
        "nota": "A skill é ARTEFATO DERIVADO. A fonte do protocolo é o runbook de sessão "
                "do projeto — editar a skill instalada não muda nada aqui; edite o "
                "runbook e regere.",
        "fontes": levados,
    }, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")

    titulo("Pacote da skill montado")
    print(f"  {relativo(str(saida))}")
    print(f"  {copiados} arquivos do kit · {len(levados)} runbook(s) do projeto")
    print("\n  Falta a SKILL.md: a redação é trabalho de escrita, não de template.")
    print("  A partir de agora, `memoria skill --conferir` avisa quando o runbook mudar.")
    return 0
