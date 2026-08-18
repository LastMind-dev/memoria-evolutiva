"""Orquestra os dois bancos derivados obrigatórios: Hindsight e Graphify."""

from __future__ import annotations

import json

from . import fragmentos, grafo, hindsight, indice
from .lib import config, titulo


def status(ao_vivo: bool = True) -> int:
    rc = max(
        fragmentos.verificar(),
        indice.verificar(),
        grafo.verificar(exigir_comando=ao_vivo),
    )
    if rc != 0 or not ao_vivo or not config().get("memoria", {}).get("ativo"):
        return rc
    try:
        prova = hindsight.verificar_ao_vivo()
        print(
            f"Hindsight confirmado ao vivo: banco `{prova['banco']}` · "
            f"{prova['documentos']} documentos · {prova['memorias_persistidas']} memórias."
        )
    except hindsight.HindsightErro as exc:
        print(f"ERRO Hindsight ao vivo — {exc}")
        return 1
    return 0


def sincronizar() -> int:
    falhas: list[str] = []
    if fragmentos.gerar() != 0:
        print("ERRO — sincronização bloqueada porque o corpus sombra não foi produzido.")
        return 1
    if config().get("memoria", {}).get("ativo"):
        try:
            prova = hindsight.sincronizar()
            print(
                f"Hindsight sincronizado: banco `{prova['banco']}` · "
                f"{prova['documentos']} documentos."
            )
        except hindsight.HindsightErro as exc:
            falhas.append(str(exc))
            print(f"ERRO Hindsight — {exc}")
    if (config().get("grafo", {}).get("ativo")
            and grafo.verificar(silencioso=True, exigir_comando=True) != 0):
        try:
            prova = grafo.sincronizar()
            print(f"Graphify sincronizado: {len(prova['arquivos'])} arquivos de código.")
        except grafo.GrafoErro as exc:
            falhas.append(str(exc))
            print(f"ERRO Graphify — {exc}")
    elif config().get("grafo", {}).get("ativo"):
        print("Graphify já estava em dia; sincronização dispensada.")
    if falhas:
        print("\nOs bancos não ficaram prontos; nenhum marcador de etapa falha foi forjado.")
        return 1
    return status(ao_vivo=True)


def consultar(pergunta: str) -> int:
    if not pergunta.strip():
        print("Informe `--pergunta=...`.")
        return 2
    if (not config().get("memoria", {}).get("ativo")
            or not config().get("grafo", {}).get("ativo")):
        print("Consulta conjunta exige Hindsight e Graphify ativos.")
        return 2
    if status(ao_vivo=True) != 0:
        print("\nConsulta bloqueada: um banco está desatualizado.")
        return 1
    try:
        lembrancas = hindsight.consultar(pergunta)
        estrutura = grafo.consultar(pergunta)
    except (hindsight.HindsightErro, grafo.GrafoErro) as exc:
        print(f"ERRO — {exc}")
        return 1
    titulo("Hindsight — significado e histórico documental")
    print(json.dumps(lembrancas, ensure_ascii=False, indent=2))
    titulo("Graphify — estrutura e impacto no código")
    print(estrutura or "(sem resultado)")
    print("\nOs dois resultados têm autoridade zero; confirme nos `source_uri` e no código.")
    return 0


def main(argv: list[str]) -> int:
    acao = argv[0] if argv else "status"
    resto = argv[1:]
    if acao == "status":
        desconhecidos = [a for a in resto if a != "--offline"]
        if desconhecidos:
            print("Opção desconhecida: " + ", ".join(desconhecidos))
            return 2
        return status(ao_vivo="--offline" not in resto)
    if acao == "sincronizar" and not resto:
        return sincronizar()
    if acao == "consultar":
        pergunta = next((a.split("=", 1)[1] for a in resto if a.startswith("--pergunta=")), "")
        desconhecidos = [a for a in resto if not a.startswith("--pergunta=")]
        if desconhecidos:
            print("Opção desconhecida: " + ", ".join(desconhecidos))
            return 2
        return consultar(pergunta)
    print("Uso: memoria bancos [status|sincronizar|consultar --pergunta=...]" )
    return 2
