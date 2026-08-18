"""Ciclo de vida verificável do grafo de código local produzido pelo Graphify."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .diagnosticar import PULAR
from .lib import barras, commit_atual, config, raiz, titulo


# Mantida aqui para o grafo cobrir código de testes e ferramentas fora de `gerado.raiz`.
EXTENSOES = {
    ".c", ".cc", ".cpp", ".cs", ".dart", ".go", ".java", ".js", ".jsx",
    ".kt", ".kts", ".php", ".py", ".rb", ".rs", ".scala", ".sh", ".sql",
    ".svelte", ".ts", ".tsx", ".vue",
}
PULAR_GRAFO = set(PULAR) | {"docs", "graphify-out"}


class GrafoErro(RuntimeError):
    pass


def _cfg() -> dict:
    return config().get("grafo", {})


def _comando() -> list[str]:
    valor = _cfg().get("comando", ["graphify"])
    if isinstance(valor, str):
        valor = [valor]
    if not isinstance(valor, list) or not valor or not all(isinstance(v, str) and v for v in valor):
        raise GrafoErro("`grafo.comando` precisa ser uma lista de argumentos não vazios")
    primeiro = os.environ.get("MEMORIA_GRAPHIFY_BIN", valor[0])
    resolvido = shutil.which(primeiro) or (primeiro if Path(primeiro).is_file() else None)
    if not resolvido:
        raise GrafoErro(
            "Graphify não encontrado. Instale `graphifyy` num Python compatível e rode novamente."
        )
    return [resolvido, *valor[1:]]


def _versao_comando(comando: list[str]) -> str | None:
    try:
        processo = subprocess.run(
            [*comando, "--version"], cwd=raiz(), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if processo.returncode != 0:
        return None
    return (processo.stdout or processo.stderr).strip().splitlines()[0] or None


def _arquivos() -> dict[str, str]:
    base = Path(raiz())
    saida: dict[str, str] = {}
    for arquivo in base.rglob("*"):
        if not arquivo.is_file() or arquivo.is_symlink():
            continue
        rel = arquivo.relative_to(base)
        if any(parte in PULAR_GRAFO for parte in rel.parts):
            continue
        if arquivo.suffix.lower() not in EXTENSOES:
            continue
        saida[barras(str(rel))] = hashlib.sha256(arquivo.read_bytes()).hexdigest()
    return dict(sorted(saida.items()))


def _marcador() -> Path:
    base = Path(raiz()).resolve()
    destino = (base / str(_cfg().get("marcador", ".memoria/bancos/graphify.json")).strip("/")).resolve()
    if not destino.is_relative_to(base):
        raise GrafoErro("`grafo.marcador` precisa ficar dentro da raiz do projeto")
    return destino


def _grafo() -> Path:
    base = Path(raiz()).resolve()
    destino = (base / str(_cfg().get("arquivo", "graphify-out/graph.json")).strip("/")).resolve()
    if not destino.is_relative_to(base):
        raise GrafoErro("`grafo.arquivo` precisa ficar dentro da raiz do projeto")
    return destino


def _fontes_do_grafo(conteudo: dict) -> set[str]:
    base = barras(str(Path(raiz()).resolve())).rstrip("/") + "/"
    fontes: set[str] = set()
    for no in conteudo.get("nodes", []):
        if not isinstance(no, dict) or not no.get("source_file"):
            continue
        fonte = barras(str(no["source_file"]))
        if fonte.casefold().startswith(base.casefold()):
            fonte = fonte[len(base):]
        while fonte.startswith("./"):
            fonte = fonte[2:]
        fontes.add(fonte)
    return fontes


def _validar_conteudo_grafo(conteudo: object, arquivos: dict[str, str],
                            nos_anteriores: int = 0,
                            fontes_anteriores: int = 0) -> dict:
    if not isinstance(conteudo, dict) or not isinstance(conteudo.get("nodes"), list):
        raise GrafoErro("`graph.json` não contém a lista de nós esperada")
    nos = len(conteudo["nodes"])
    if arquivos and nos == 0:
        raise GrafoErro("Graphify produziu grafo vazio para um projeto com código")

    fontes = _fontes_do_grafo(conteudo)
    fontes_normalizadas = {f.casefold() for f in fontes}
    representadas = {
        fonte for fonte in arquivos
        if fonte.casefold() in fontes_normalizadas
        or any(f.endswith("/" + fonte.casefold()) for f in fontes_normalizadas)
    }
    cobertura = len(representadas) / len(arquivos) if arquivos else 1.0
    minima = float(_cfg().get("cobertura_minima", 0.8))
    if arquivos and cobertura < minima:
        raise GrafoErro(
            f"Graphify representou {len(representadas)}/{len(arquivos)} fontes "
            f"({cobertura:.1%}); mínimo configurado: {minima:.1%}"
        )

    reducao_maxima = float(_cfg().get("reducao_maxima_percentual", 50.0))
    if nos_anteriores > 0:
        # Remover metade dos arquivos deve permitir queda proporcional de nós. O limite
        # mede somente o colapso além do que a redução observável das fontes explica.
        proporcao_fontes = (
            min(1.0, len(arquivos) / fontes_anteriores)
            if fontes_anteriores > 0 else 1.0
        )
        esperado = nos_anteriores * proporcao_fontes
        reducao = (esperado - nos) * 100.0 / esperado if esperado else 0.0
        if reducao > reducao_maxima:
            raise GrafoErro(
                f"Graphify produziu {nos} nós; eram esperados cerca de {esperado:.0f} "
                f"pela quantidade de fontes (redução residual {reducao:.1f}%); "
                f"limite: {reducao_maxima:.1f}%"
            )
    return {
        "nos": nos,
        "fontes_representadas": sorted(representadas),
        "cobertura": cobertura,
    }


def sincronizar() -> dict:
    comando = _comando()
    versao = _versao_comando(comando)
    grafo_path = _grafo()
    existente = grafo_path.is_file()
    anterior_bytes = grafo_path.read_bytes() if existente else None
    nos_anteriores = 0
    fontes_anteriores = 0
    if anterior_bytes:
        try:
            anterior_json = json.loads(anterior_bytes.decode("utf-8"))
            nos_anteriores = len(anterior_json.get("nodes", []))
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            nos_anteriores = 0
    marcador_anterior = _marcador()
    if marcador_anterior.is_file():
        try:
            estado_anterior = json.loads(marcador_anterior.read_text(encoding="utf-8"))
            fontes_anteriores = len(estado_anterior.get("arquivos", {}))
        except (json.JSONDecodeError, OSError, AttributeError, TypeError):
            fontes_anteriores = 0
    args = ([*comando, "update", ".", "--force"] if existente
            else [*comando, "extract", ".", "--code-only"])
    env = os.environ.copy()
    env["GRAPHIFY_QUERY_LOG_DISABLE"] = "1"
    try:
        processo = subprocess.run(
            args, cwd=raiz(), env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=float(_cfg().get("timeout_segundos", 900)),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GrafoErro(f"Graphify não concluiu: {exc}") from exc
    if processo.returncode != 0:
        detalhe = (processo.stderr or processo.stdout).strip()[-2000:]
        raise GrafoErro(f"Graphify terminou com saída {processo.returncode}: {detalhe}")
    combinado = f"{processo.stdout}\n{processo.stderr}".lower()
    if "nothing to update or rebuild failed" in combinado:
        raise GrafoErro("Graphify recusou a reconstrução; o marcador anterior foi preservado")
    if not _grafo().is_file():
        raise GrafoErro(f"Graphify não produziu `{barras(str(_grafo().relative_to(Path(raiz()))))}`")

    arquivos = _arquivos()
    try:
        conteudo_grafo = json.loads(grafo_path.read_text(encoding="utf-8"))
        metricas = _validar_conteudo_grafo(
            conteudo_grafo, arquivos, nos_anteriores, fontes_anteriores
        )
    except (json.JSONDecodeError, OSError, GrafoErro) as exc:
        # Uma atualização parcial nunca substitui a última cópia utilizável.
        if anterior_bytes is not None:
            grafo_path.write_bytes(anterior_bytes)
        elif grafo_path.exists():
            grafo_path.unlink()
        if isinstance(exc, GrafoErro):
            raise
        raise GrafoErro(f"`graph.json` inválido após a reconstrução: {exc}") from exc
    comando_registrado = _cfg().get("comando", ["graphify"])
    if isinstance(comando_registrado, str):
        comando_registrado = [comando_registrado]
    prova = {
        "schema": 2,
        "provedor": "graphify",
        "sincronizado_em": datetime.now(timezone.utc).isoformat(),
        "commit": commit_atual(),
        # Não versione caminho absoluto do interpretador/máquina no marcador.
        "comando": [*comando_registrado, "update", ".", "--force"]
        if existente else [*comando_registrado, "extract", ".", "--code-only"],
        "versao": versao or "desconhecida",
        "arquivos": arquivos,
        "grafo_sha256": hashlib.sha256(grafo_path.read_bytes()).hexdigest(),
        **metricas,
        "assinatura": hashlib.sha256(
            "\n".join(f"{p}:{h}" for p, h in arquivos.items()).encode("utf-8")
        ).hexdigest(),
    }
    marcador = _marcador()
    marcador.parent.mkdir(parents=True, exist_ok=True)
    marcador.write_text(json.dumps(prova, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return prova


def verificar(silencioso: bool = False, exigir_comando: bool = False) -> int:
    if not _cfg().get("ativo"):
        if not silencioso:
            print("Graphify desativado explicitamente em `padrao.json`.")
        return 0
    try:
        marcador = _marcador()
        arquivo_grafo = _grafo()
    except GrafoErro as exc:
        if not silencioso:
            print(f"ERRO — {exc}")
        return 1
    if not arquivo_grafo.is_file() or not marcador.is_file():
        if not silencioso:
            print("ERRO — grafo Graphify ou marcador ausente. Rode: `memoria bancos sincronizar`.")
        return 1
    try:
        estado = json.loads(marcador.read_text(encoding="utf-8"))
        if estado.get("schema") != 2 or estado.get("provedor") != "graphify":
            raise ValueError("schema/provedor não confirmam Graphify")
        anterior = estado.get("arquivos", {})
        if not isinstance(anterior, dict):
            raise ValueError("lista de arquivos do marcador não é um objeto")
        conteudo_grafo = json.loads(arquivo_grafo.read_text(encoding="utf-8"))
        metricas = _validar_conteudo_grafo(conteudo_grafo, anterior)
        digest = hashlib.sha256(arquivo_grafo.read_bytes()).hexdigest()
        if estado.get("grafo_sha256") != digest:
            raise ValueError("hash do graph.json diverge do marcador")
        if estado.get("nos") != metricas["nos"]:
            raise ValueError("contagem de nós diverge do marcador")
        if exigir_comando:
            comando = _comando()
            atual_versao = _versao_comando(comando)
            marcada = estado.get("versao")
            if marcada not in (None, "desconhecida") and atual_versao != marcada:
                raise ValueError(
                    f"versão do Graphify mudou: grafo={marcada!r}, executável={atual_versao!r}"
                )
    except (json.JSONDecodeError, OSError, ValueError, GrafoErro) as exc:
        if not silencioso:
            print(f"ERRO — marcador do Graphify inválido: {exc}")
        return 1
    atual = _arquivos()
    mudou = [p for p, h in atual.items() if p in anterior and anterior[p] != h]
    novo = [p for p in atual if p not in anterior]
    sumiu = [p for p in anterior if p not in atual]
    if not silencioso:
        titulo("Graphify — grafo de código local")
        print(f"  fontes atuais: {len(atual)} · fontes no marcador: {len(anterior)}")
    if not mudou and not novo and not sumiu:
        if not silencioso:
            print("\nO grafo está em dia com o código.")
        return 0
    if not silencioso:
        for rotulo, itens, sinal in (("MUDARAM", mudou, "~"), ("NOVAS", novo, "+"), ("SUMIRAM", sumiu, "-")):
            if itens:
                print(f"\n{rotulo}:")
                for item in itens:
                    print(f"  {sinal} {item}")
        print("\nRode: `memoria bancos sincronizar`.")
    return 1


def consultar(pergunta: str) -> str:
    comando = [*_comando(), "query", pergunta]
    env = os.environ.copy()
    env["GRAPHIFY_QUERY_LOG_DISABLE"] = "1"
    try:
        processo = subprocess.run(
            comando, cwd=raiz(), env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=float(_cfg().get("timeout_segundos", 900)),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GrafoErro(f"consulta Graphify falhou: {exc}") from exc
    if processo.returncode != 0:
        raise GrafoErro((processo.stderr or processo.stdout).strip())
    return processo.stdout.rstrip()
