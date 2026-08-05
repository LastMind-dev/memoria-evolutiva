"""catraca — a dívida existente fica congelada e visível; falha SÓ SE PIORAR.

Quando a regra nasce depois do código, o passivo já existe. Reprovar tudo trava o time
sem consertar nada — e build que nasce vermelho ninguém olha. Quando um número chega a
zero, promova a regra a falha dura.

TIPOS DE CONTADOR: regex · arquivo_sem_padrao · markdown_sem_frontmatter.

PORTE: os padrões nos padrao.json existentes estão em sintaxe PCRE com delimitadores
(`/.../m`), gravados pela era PHP. `_compila` os traduz — os arquivos dos projetos NÃO
mudam, é contrato.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from .lib import (arquivos_por_extensao, comeca_com, commit_atual, config,
                  contem_algum, markdowns, morre, raiz, relativo, titulo)


def _compila(padrao: str) -> re.Pattern:
    """`/(^|[^_a-zA-Z])env\\(/m` (PCRE com delimitador) → re do Python.

    Só as flags que os contadores reais usam: m, i, s. Padrão sem delimitador também é
    aceito, para projetos novos escritos na era Python.
    """
    m = re.match(r"^/(.*)/([a-zA-Z]*)$", padrao, flags=re.S)
    corpo, letras = (m.group(1), m.group(2)) if m else (padrao, "")
    flags = 0
    if "m" in letras:
        flags |= re.M
    if "i" in letras:
        flags |= re.I
    if "s" in letras:
        flags |= re.S
    return re.compile(corpo, flags)


def main(argv: list[str]) -> int:
    c = config()
    medir = "--medir" in argv
    base = Path(raiz()) / c.get("catraca", {}).get("linha_de_base", "docs/baseline.json").strip("/")
    defs = c.get("catraca", {}).get("contadores", [])

    if not defs:
        print("Nenhum contador declarado em `padrao.json` → `catraca.contadores`.")
        print("A catraca não tem o que medir. Isso é válido — mas veja se não deveria ter.")
        return 0

    atual: dict[str, int] = {}
    detalhe: dict[str, dict[str, int]] = {}
    rotulos: dict[str, str] = {}

    for d in defs:
        chave = d["chave"]
        rotulos[chave] = d.get("rotulo", chave)
        onde = raiz() + "/" + d.get("onde", "").strip("/")
        excl = d.get("excluir", [])
        total = 0
        onde_achou: dict[str, int] = {}
        tipo = d.get("tipo", "regex")

        if tipo == "regex":
            rx = _compila(d["padrao"])
            for f in arquivos_por_extensao(onde, d.get("extensao", "php")):
                if contem_algum(f, excl):
                    continue
                n = len(rx.findall(Path(f).read_text(encoding="utf-8", errors="replace")))
                if n > 0:
                    total += n
                    onde_achou[relativo(f)] = n

        elif tipo == "arquivo_sem_padrao":
            rx = _compila(d["exige"])
            for f in arquivos_por_extensao(onde, d.get("extensao", "php")):
                if contem_algum(f, excl):
                    continue
                if not rx.search(Path(f).read_text(encoding="utf-8", errors="replace")):
                    total += 1
                    onde_achou[relativo(f)] = 1

        elif tipo == "markdown_sem_frontmatter":
            for f in markdowns(onde):
                rel = relativo(f)
                if contem_algum(rel, excl) or comeca_com(rel, c.get("externos", {}).get("pastas", [])):
                    continue
                if not Path(f).read_text(encoding="utf-8", errors="replace").startswith("---\n"):
                    total += 1
                    onde_achou[rel] = 1
        else:
            morre(f"Contador `{chave}`: tipo `{tipo}` desconhecido.\n")

        atual[chave] = total
        detalhe[chave] = dict(sorted(onde_achou.items(), key=lambda kv: -kv[1]))

    if medir:
        base.parent.mkdir(parents=True, exist_ok=True)
        base.write_text(json.dumps({
            "medido_em": date.today().isoformat(),
            "commit": commit_atual(),
            "nota": "Contagem congelada da dívida existente. A verificação falha se algum "
                    "número aumentar. Quando um chegar a zero, promova a regra a falha dura.",
            "contagens": atual,
        }, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
        titulo("Linha de base gravada")
        for k, v in atual.items():
            print(f"  {rotulos[k]:<52} {v}")
        print("\nA partir de agora, qualquer aumento quebra o build.")
        return 0

    if not base.is_file():
        print("Sem linha de base. Meça uma vez:\n\n  memoria catraca --medir")
        return 1

    j = json.loads(base.read_text(encoding="utf-8"))
    ref = j.get("contagens", {})
    # `gerado_em` é a linha de base herdada da geração 1 — quem migrou não deve ver "?"
    quando = j.get("medido_em") or j.get("gerado_em") or "?"
    piorou = [(k, ref.get(k, 0), v) for k, v in atual.items() if v > ref.get(k, 0)]
    melhorou = [(k, ref.get(k, 0), v) for k, v in atual.items() if v < ref.get(k, 0)]

    titulo(f"Catraca — linha de base de {quando}")
    for k, v in atual.items():
        r = ref.get(k, 0)
        sinal = "↑" if v > r else ("↓" if v < r else "=")
        print(f"  {sinal}  {rotulos[k]:<52} {v} (base {r})")

    if melhorou:
        print("\nMelhorou — trave o ganho:")
        for k, r, v in melhorou:
            print(f"  ↓ {rotulos[k]}: {r} → {v}")
        print("  memoria catraca --medir")

    if piorou:
        print("\nERRO — a dívida aumentou:")
        for k, r, v in piorou:
            print(f"\n  x {rotulos[k]}: {r} → {v}")
            for arq in list(detalhe[k])[:8]:
                print(f"      {arq}")
        print("\nO passivo antigo fica congelado, mas não pode crescer.")
        print("Código novo precisa nascer dentro da regra.")
        return 1

    print("\nNada piorou.")
    return 0
