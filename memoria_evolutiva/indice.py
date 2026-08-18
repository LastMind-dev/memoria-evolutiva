"""Validação da cópia documental mantida no Hindsight.

O marcador só pode ser gravado pelo sincronizador depois de uma resposta bem-sucedida
do banco. Assim, um arquivo JSON local nunca consegue fingir que houve indexação real.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from . import seguranca
from .lib import (acervo, comeca_com, commit_atual, config, hash_do_conteudo,
                  markdowns, morre, relativo, raiz, titulo)


def _eh_nucleo(rel: str, definicao: list[str]) -> bool:
    return any(rel == n or (n.endswith("/") and rel.startswith(n)) for n in definicao)


def documentos_do_nucleo() -> tuple[dict[str, str], dict[str, str]]:
    """Devolve hashes do núcleo e do restante, com a seleção canônica do padrão."""
    m = config().get("memoria", {})
    nucleo: dict[str, str] = {}
    resto: dict[str, str] = {}
    for arquivo in markdowns(acervo()):
        if Path(arquivo).is_symlink():
            continue
        rel = relativo(arquivo)
        if comeca_com(rel, m.get("ignorar", [])):
            continue
        conteudo = Path(arquivo).read_text(encoding="utf-8", errors="replace")
        if not seguranca.indexavel(conteudo):
            resto[rel] = hash_do_conteudo(conteudo)
            continue
        destino = nucleo if _eh_nucleo(rel, m.get("nucleo", [])) else resto
        destino[rel] = hash_do_conteudo(conteudo)
    return dict(sorted(nucleo.items())), dict(sorted(resto.items()))


def marcador_path() -> Path:
    m = config().get("memoria", {})
    base = Path(raiz()).resolve()
    destino = (base / str(m.get("marcador", "docs/.hindsight-indexado.json")).strip("/")).resolve()
    if not destino.is_relative_to(base):
        morre("`memoria.marcador` precisa ficar dentro da raiz do projeto.\n")
    return destino


def gravar_marcador(prova: dict) -> None:
    """Uso interno: chame somente depois do Hindsight confirmar o retain."""
    nucleo, resto = documentos_do_nucleo()
    destino = marcador_path()
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps({
        "schema": 4,
        "provedor": "hindsight",
        "indexado_em": datetime.now(timezone.utc).isoformat(),
        "commit": commit_atual(),
        "fora_do_nucleo": len(resto),
        "documentos": nucleo,
        "prova_do_provedor": prova,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def verificar(silencioso: bool = False) -> int:
    m = config().get("memoria", {})
    if not m.get("ativo"):
        if not silencioso:
            print("Hindsight desativado explicitamente em `padrao.json`.")
        return 0

    try:
        nucleo, resto = documentos_do_nucleo()
    except seguranca.SegurancaErro as exc:
        if not silencioso:
            print(f"ERRO — política de segurança documental inválida: {exc}")
        return 1
    marcador = marcador_path()
    if not marcador.is_file():
        if not silencioso:
            print(f"ERRO — não existe `{relativo(str(marcador))}`.")
            print("O Hindsight ainda não foi sincronizado. Rode: `memoria bancos sincronizar`.")
        return 1

    try:
        estado = json.loads(marcador.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        if not silencioso:
            print(f"ERRO — marcador do Hindsight inválido: {exc}")
        return 1

    ref = estado.get("documentos", {})
    prova = estado.get("prova_do_provedor", {})
    identidade_atual = {
        "endpoint": os.environ.get(
            "MEMORIA_HINDSIGHT_URL", str(m.get("endpoint", ""))
        ).rstrip("/"),
        "banco": str(m.get("banco") or config()["projeto"]),
    }
    if (estado.get("schema") != 4 or estado.get("provedor") != "hindsight"
            or not isinstance(ref, dict) or not isinstance(prova, dict)
            or prova.get("confirmado") is not True
            or not isinstance(prova.get("memorias_persistidas"), int)
            or prova.get("memorias_persistidas", 0) < len(ref)
            or prova.get("endpoint") != identidade_atual["endpoint"]
            or prova.get("banco") != identidade_atual["banco"]
            or prova.get("seguranca_fingerprint") != seguranca.fingerprint()
            or not isinstance(prova.get("redaction"), dict)
            or prova["redaction"].get("algoritmo") != "redaction-deterministica-v1"):
        if not silencioso:
            print("ERRO — marcador não confirma todos os documentos no Hindsight configurado.")
        return 1
    mudou = [r for r, h in nucleo.items() if r in ref and ref[r] != h]
    novo = [r for r in nucleo if r not in ref]
    sumiu = [r for r in ref if r not in nucleo]

    if not silencioso:
        titulo(
            "Hindsight — última sincronização em "
            f"{estado.get('indexado_em', '?')}, commit {estado.get('commit') or '(sem git)'}"
        )
        print(f"  núcleo: {len(nucleo)} documentos · sincronizados: {len(ref)}")
        print(f"  fora do núcleo: {len(resto)} (não entra no banco)")

    if not mudou and not novo and not sumiu:
        if not silencioso:
            print("\nO banco documental está em dia.")
        return 0

    if not silencioso:
        if mudou:
            print("\nMUDARAM desde a sincronização:")
            for rel in mudou:
                print(f"  ~ {rel}")
        if novo:
            print("\nNUNCA SINCRONIZADOS:")
            for rel in novo:
                print(f"  + {rel}")
        if sumiu:
            print("\nSUMIRAM do acervo canônico:")
            for rel in sumiu:
                print(f"  - {rel}")
        print("\nRode: `memoria bancos sincronizar`.")
    return 1


def main(argv: list[str]) -> int:
    if "--marcar" in argv:
        print("`--marcar` foi removido: marcador manual não prova indexação real.")
        print("Use `memoria bancos sincronizar`; ele só marca após o Hindsight confirmar.")
        return 2
    if argv:
        print("`memoria indice` não aceita opções.")
        return 2
    return verificar()
