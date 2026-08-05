"""indice — impede o índice semântico de apodrecer em silêncio.

O índice é derivado: quando o documento muda e ninguém reindexa, a busca devolve o fato
antigo com a MESMA confiança de um correto. Este comando NÃO reindexa (o índice é
alcançado pela máquina de quem trabalha, não pelo runner): torna visível que precisa, e
falha até alguém fazer.

NÚCLEO falha duro; o resto é medido e não bloqueia. `--marcar` grava o estado — DEPOIS
de indexar de verdade, nunca antes: marcar sem indexar transforma a verificação em
teatro.

COMPATIBILIDADE: lê e grava o mesmo formato de marcador da era PHP (`documentos` com
`hash_do_conteudo` idêntico) — os marcadores existentes continuam válidos.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .lib import (acervo, comeca_com, commit_atual, config, hash_do_conteudo,
                  markdowns, relativo, raiz, titulo)


def _eh_nucleo(rel: str, definicao: list[str]) -> bool:
    for n in definicao:
        if rel == n or (n.endswith("/") and rel.startswith(n)):
            return True
    return False


def main(argv: list[str]) -> int:
    c = config()
    m = c.get("memoria", {})

    if not m.get("ativo"):
        print("Índice semântico desativado em `padrao.json` → `memoria.ativo`.")
        print("Nada a verificar. O resto do padrão funciona sem.")
        return 0

    marcar = "--marcar" in argv
    ferramenta = str(m.get("ferramenta") or "")
    rotulo = f"Índice ({ferramenta})" if ferramenta else "Índice"
    marcador = Path(raiz()) / m.get("marcador", "docs/.indexado.json").strip("/")
    nucleo_def = m.get("nucleo", [])
    ignorar = m.get("ignorar", [])

    nucleo: dict[str, str] = {}
    resto: dict[str, str] = {}
    for f in markdowns(acervo()):
        rel = relativo(f)
        if comeca_com(rel, ignorar):
            continue
        h = hash_do_conteudo(Path(f).read_text(encoding="utf-8", errors="replace"))
        (nucleo if _eh_nucleo(rel, nucleo_def) else resto)[rel] = h
    nucleo = dict(sorted(nucleo.items()))
    resto = dict(sorted(resto.items()))

    if marcar:
        marcador.write_text(json.dumps({
            "indexado_em": date.today().isoformat(),
            "commit": commit_atual(),
            "nota": "Estado do NÚCLEO na última indexação. Rode --marcar DEPOIS de "
                    "indexar de verdade, nunca antes: marcar sem indexar transforma "
                    "esta verificação em teatro.",
            "fora_do_nucleo": len(resto),
            "documentos": nucleo,
        }, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
        print(f"Marcador gravado: {len(nucleo)} documentos do núcleo em {commit_atual() or '(sem git)'}.")
        print(f"Fora do núcleo, não indexados: {len(resto)}.")
        return 0

    if not marcador.is_file():
        print(f"ERRO — não existe `{relativo(str(marcador))}`.\n")
        print("Sem ele não dá para saber se o índice está velho. Indexe os documentos do")
        print("núcleo e rode:\n\n  memoria indice --marcar")
        return 1

    j = json.loads(marcador.read_text(encoding="utf-8"))
    ref = j.get("documentos", {})
    quando = j.get("indexado_em", "?")
    onde_sha = j.get("commit", "?")

    mudou = [r for r, h in nucleo.items() if r in ref and ref[r] != h]
    novo = [r for r in nucleo if r not in ref]
    sumiu = [r for r in ref if r not in nucleo]

    titulo(f"{rotulo} — última indexação em {quando}, commit {onde_sha}")
    print(f"  núcleo: {len(nucleo)} documentos · indexados: {len(ref)}")
    print(f"  fora do núcleo, não indexados: {len(resto)} (medido, não bloqueia)")

    if not mudou and not novo and not sumiu:
        print("\nO núcleo está em dia com os documentos.")
        if resto:
            print(f"\nDívida visível: {len(resto)} documentos fora do índice.")
            print("Quando um deles for indexado, acrescente ao `memoria.nucleo` do padrao.json.")
        return 0

    if mudou:
        print(f"\nMUDARAM desde a indexação ({len(mudou)}) — o índice devolve o texto antigo:")
        for r in mudou:
            print(f"  ~ {r}")
    if novo:
        print(f"\nNUNCA INDEXADOS ({len(novo)}) — invisíveis para a busca:")
        for r in novo:
            print(f"  + {r}")
    if sumiu:
        print(f"\nSUMIRAM ({len(sumiu)}) — o índice guarda fato de documento que não existe mais:")
        for r in sumiu:
            print(f"  - {r}")

    print("\nComo resolver:")
    print("  1. reindexe estes documentos, com origem e versão em cada registro")
    print("  2. memoria indice --marcar\n")
    print("Registro sem proveniência é purgado, não corrigido.")
    return 1
