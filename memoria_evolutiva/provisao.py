"""Preparação objetiva dos provedores locais exigidos pela memória evolutiva.

O módulo não instala pacotes durante a execução e não escolhe provedor/modelo de LLM.
Essas dependências entram no extra ``local`` do pacote. Quando o Hindsight embutido já
está configurado, o daemon pode ser iniciado sob demanda; segredos permanecem somente no
ambiente ou no perfil global mantido pelo próprio Hindsight.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

from . import grafo, hindsight
from .lib import config, raiz


class ProvisaoErro(RuntimeError):
    pass


def _executavel(nome: str) -> str | None:
    candidatos: list[Path] = []
    encontrado = shutil.which(nome)
    if encontrado:
        return encontrado
    scripts = Path(sys.executable).resolve().parent
    candidatos.append(scripts / nome)
    candidatos.append(Path.home() / ".local" / "bin" / nome)
    if os.name == "nt" and not nome.casefold().endswith(".exe"):
        candidatos = [item.with_suffix(".exe") for item in candidatos] + candidatos
    for candidato in candidatos:
        if candidato.is_file():
            return str(candidato)
    return None


def _porta_aberta(endpoint: str, timeout: float = 0.5) -> bool:
    partes = urllib.parse.urlsplit(endpoint)
    host = partes.hostname
    if not host:
        return False
    try:
        porta = partes.port or (443 if partes.scheme == "https" else 80)
        with socket.create_connection((host, porta), timeout=timeout):
            return True
    except (OSError, ValueError):
        return False


def _cfg() -> dict:
    valor = config().get("ciclo", {})
    if not isinstance(valor, dict) or valor.get("ativo") is not True:
        raise ProvisaoErro(
            "ciclo autônomo ausente ou desativado; rode `memoria instalar` com a versão atual"
        )
    return valor


def _iniciar_hindsight(endpoint: str, cfg: dict) -> str:
    partes = urllib.parse.urlsplit(endpoint)
    try:
        porta = partes.port or 80
    except ValueError as exc:
        raise ProvisaoErro("endpoint local do Hindsight possui porta inválida") from exc
    if (
        partes.scheme != "http"
        or partes.hostname not in {"127.0.0.1", "localhost", "::1"}
        or porta != 8888
        or partes.path not in {"", "/"}
        or partes.query
        or partes.fragment
    ):
        raise ProvisaoErro(
            "Hindsight indisponível e o endpoint não é o daemon local padrão; "
            "a biblioteca não inicia serviços externos ou endpoints personalizados"
        )
    if cfg.get("iniciar_hindsight_embed") is not True:
        raise ProvisaoErro(
            "Hindsight local indisponível e `ciclo.iniciar_hindsight_embed` está desativado"
        )
    comando = _executavel("hindsight-embed")
    if not comando:
        raise ProvisaoErro(
            "Hindsight local indisponível e `hindsight-embed` não foi encontrado. "
            "Instale a biblioteca com o extra `local`."
        )
    timeout = cfg.get("timeout_inicializacao_segundos", 180)
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 10 <= timeout <= 600:
        raise ProvisaoErro(
            "`ciclo.timeout_inicializacao_segundos` precisa ficar entre 10 e 600"
        )
    try:
        processo = subprocess.run(
            [comando, "daemon", "start"], cwd=raiz(), capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProvisaoErro("Hindsight embutido não iniciou dentro do prazo") from exc
    if processo.returncode != 0:
        # A saída pode conter configuração de provedor ou caminhos privados. O contrato
        # deliberadamente não a propaga para agentes nem para artefatos do projeto.
        raise ProvisaoErro(
            "Hindsight embutido recusou a inicialização; confira o perfil global ou "
            "as variáveis HINDSIGHT_API_LLM_*"
        )
    limite = time.monotonic() + timeout
    while time.monotonic() < limite:
        if _porta_aberta(endpoint):
            return comando
        time.sleep(0.25)
    raise ProvisaoErro("Hindsight embutido iniciou, mas não abriu o endpoint local no prazo")


def garantir() -> dict:
    """Confirma executáveis e inicia somente o daemon Hindsight local, se necessário."""
    try:
        cfg = _cfg()
        projeto = config()
    except SystemExit as exc:
        raise ProvisaoErro("configuração do projeto inválida") from exc
    resultado = {
        "hindsight": {"ativo": False, "estado": "desativado", "iniciado": False},
        "graphify": {"ativo": False, "estado": "desativado", "versao": None},
    }
    memoria_cfg = projeto.get("memoria", {})
    if isinstance(memoria_cfg, dict) and memoria_cfg.get("ativo") is True:
        try:
            endpoint = hindsight._endpoint()
        except hindsight.HindsightErro as exc:
            raise ProvisaoErro(str(exc)) from exc
        resultado["hindsight"] = {
            "ativo": True,
            "estado": "disponivel" if _porta_aberta(endpoint) else "indisponivel",
            "iniciado": False,
        }
        if resultado["hindsight"]["estado"] == "indisponivel":
            _iniciar_hindsight(endpoint, cfg)
            resultado["hindsight"]["estado"] = "disponivel"
            resultado["hindsight"]["iniciado"] = True

    grafo_cfg = projeto.get("grafo", {})
    if isinstance(grafo_cfg, dict) and grafo_cfg.get("ativo") is True:
        try:
            comando = grafo._comando()
        except grafo.GrafoErro as exc:
            raise ProvisaoErro(
                "Graphify não foi encontrado. Instale a biblioteca com o extra `local`."
            ) from exc
        versao = grafo._versao_comando(comando)
        if not versao:
            raise ProvisaoErro("Graphify foi encontrado, mas não confirmou sua versão")
        resultado["graphify"] = {
            "ativo": True,
            "estado": "disponivel",
            "versao": versao,
        }
    return resultado
