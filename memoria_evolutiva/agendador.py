"""Agendamento portátil e fechado da atualização da memória do projeto.

O agendador registra somente um comando construído pela biblioteca. Não recebe shell,
SQL, URL nem credencial do usuário e nunca conhece o banco de negócio da aplicação.
No Windows usa o Agendador de Tarefas; em sistemas POSIX mantém uma linha identificada
no crontab do usuário. Os scripts e logs ficam em ``.memoria/agendador/``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from . import ciclo
from .lib import config, raiz


SCHEMA = 1
ACOES = {"instalar", "status", "executar", "remover"}


class AgendadorErro(RuntimeError):
    pass


def _cfg() -> dict:
    valor = config().get("agendamento", {})
    esperados = {
        "ativo": True,
        "registrar_na_instalacao": True,
        "frequencia": "diaria",
        "comando": "memoria-agendador-v1",
        "banco_negocio": "proibido",
        "publicacao_automatica": False,
    }
    if not isinstance(valor, dict):
        raise AgendadorErro("`agendamento` precisa ser objeto")
    for chave, esperado in esperados.items():
        if valor.get(chave) != esperado:
            raise AgendadorErro(f"`agendamento.{chave}` precisa ser {esperado!r}")
    horario = valor.get("horario_local", "02:15")
    match = re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)", str(horario))
    if not match:
        raise AgendadorErro("`agendamento.horario_local` precisa usar HH:MM entre 00:00 e 23:59")
    return valor


def _base() -> Path:
    return Path(raiz()).resolve()


def _estado() -> Path:
    return _base() / ".memoria" / "agendador"


def _identidade() -> str:
    canonico = os.path.normcase(str(_base())).encode("utf-8")
    return hashlib.sha256(canonico).hexdigest()[:12]


def _nome_tarefa() -> str:
    nome = re.sub(r"[^A-Za-z0-9_-]+", "-", _base().name).strip("-")[:32] or "projeto"
    return f"MemoriaEvolutiva-{nome}-{_identidade()}"


def _marcador_cron() -> str:
    return f"# memoria-evolutiva:{_identidade()}"


def _script_windows() -> tuple[Path, str]:
    destino = _estado() / "atualizar.ps1"

    def ps(valor: str) -> str:
        return "'" + valor.replace("'", "''") + "'"

    runner = _estado() / "runner.py"
    texto = (
        "$ErrorActionPreference = 'Continue'\n"
        f"Set-Location -LiteralPath {ps(str(_base()))}\n"
        f"& {ps(sys.executable)} {ps(str(runner))}\n"
        "exit $LASTEXITCODE\n"
    )
    return destino, texto


def _script_posix() -> tuple[Path, str]:
    destino = _estado() / "atualizar.sh"
    runner = _estado() / "runner.py"
    comando = " ".join([shlex.quote(sys.executable), shlex.quote(str(runner))])
    texto = (
        "#!/bin/sh\n"
        "set -u\n"
        f"cd -- {shlex.quote(str(_base()))} || exit 1\n"
        f"{comando}\n"
    )
    return destino, texto


def _runner() -> tuple[Path, str]:
    """Bootstrap explícito: não depende do PYTHONPATH herdado pelo serviço do SO."""
    destino = _estado() / "runner.py"
    pacote_base = Path(__file__).resolve().parent.parent
    log = _estado() / "execucoes.jsonl"
    texto = f'''# Gerado por memoria-evolutiva; não editar.
import contextlib
import runpy
import sys
import traceback
from pathlib import Path

sys.path.insert(0, {str(pacote_base)!r})
sys.argv = ["memoria", "agendador", "executar", "--json"]
codigo = 0
with Path({str(log)!r}).open("a", encoding="utf-8", newline="\\n") as arquivo:
    with contextlib.redirect_stdout(arquivo), contextlib.redirect_stderr(arquivo):
        try:
            runpy.run_module("memoria_evolutiva", run_name="__main__")
        except SystemExit as exc:
            codigo = exc.code if isinstance(exc.code, int) else 1
        except BaseException:
            traceback.print_exc()
            codigo = 1
raise SystemExit(codigo)
'''
    return destino, texto


def _escrever_script() -> Path:
    destino, texto = _script_windows() if os.name == "nt" else _script_posix()
    destino.parent.mkdir(parents=True, exist_ok=True)
    for arquivo, conteudo in ((destino, texto), _runner()):
        temporario = arquivo.with_suffix(arquivo.suffix + ".tmp")
        temporario.write_text(conteudo, encoding="utf-8", newline="\n")
        os.replace(temporario, arquivo)
    if os.name != "nt":
        destino.chmod(0o700)
    return destino


def _subprocess(comando: list[str], *, entrada: str | None = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            comando, input=entrada, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AgendadorErro(f"não foi possível operar o agendador do sistema: {exc}") from exc


def _acao_windows(script: Path) -> tuple[str, str]:
    return (
        "powershell.exe",
        f'-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{script}"',
    )


def _linha_cron(script: Path) -> str:
    hora, minuto = str(_cfg()["horario_local"]).split(":")
    return f"{minuto} {hora} * * * {shlex.quote(str(script))} {_marcador_cron()}"


def _status_sistema() -> bool:
    if os.name == "nt":
        resultado = _subprocess([
            "schtasks.exe", "/Query", "/TN", _nome_tarefa(), "/XML",
        ])
        if resultado.returncode != 0:
            return False
        try:
            arvore = ET.fromstring(resultado.stdout)
        except ET.ParseError:
            return False
        campos: dict[str, list[str]] = {}
        for elemento in arvore.iter():
            nome = elemento.tag.rsplit("}", 1)[-1]
            if elemento.text is not None:
                campos.setdefault(nome, []).append(elemento.text)
        comando, argumentos = _acao_windows(_estado() / "atualizar.ps1")
        horario = str(_cfg()["horario_local"])
        inicios = campos.get("StartBoundary", [])
        return (
            campos.get("Command") == [comando]
            and campos.get("Arguments") == [argumentos]
            and campos.get("DaysInterval") == ["1"]
            and len(inicios) == 1
            and re.search(rf"T{re.escape(horario)}(?::00)?(?:[+-]|Z|$)", inicios[0]) is not None
        )
    atual = _subprocess(["crontab", "-l"])
    if atual.returncode not in {0, 1}:
        raise AgendadorErro("não foi possível ler o crontab do usuário")
    esperada = _linha_cron(_estado() / "atualizar.sh")
    return any(linha.strip() == esperada for linha in atual.stdout.splitlines())


def _registrar(script: Path) -> None:
    horario = str(_cfg()["horario_local"])
    if os.name == "nt":
        comando, argumentos = _acao_windows(script)
        tarefa = f"{comando} {argumentos}"
        resultado = _subprocess([
            "schtasks.exe", "/Create", "/F", "/SC", "DAILY", "/ST", horario,
            "/TN", _nome_tarefa(), "/TR", tarefa,
        ])
        if resultado.returncode != 0:
            raise AgendadorErro("o Windows recusou o registro da tarefa da memória")
        return

    atual = _subprocess(["crontab", "-l"])
    if atual.returncode not in {0, 1}:
        raise AgendadorErro("não foi possível ler o crontab do usuário")
    existentes = [
        linha for linha in atual.stdout.splitlines()
        if not linha.rstrip().endswith(_marcador_cron())
    ]
    linha = _linha_cron(script)
    conteudo = "\n".join([*existentes, linha]).strip() + "\n"
    gravado = _subprocess(["crontab", "-"], entrada=conteudo)
    if gravado.returncode != 0:
        raise AgendadorErro("o sistema recusou o registro no crontab do usuário")


def _remover() -> None:
    if os.name == "nt":
        resultado = _subprocess(["schtasks.exe", "/Delete", "/F", "/TN", _nome_tarefa()])
        if resultado.returncode != 0:
            existe = _subprocess([
                "schtasks.exe", "/Query", "/TN", _nome_tarefa(),
            ]).returncode == 0
            if existe:
                raise AgendadorErro("o Windows recusou a remoção da tarefa da memória")
        return
    atual = _subprocess(["crontab", "-l"])
    if atual.returncode == 1:
        return
    if atual.returncode != 0:
        raise AgendadorErro("não foi possível ler o crontab do usuário")
    restantes = [
        linha for linha in atual.stdout.splitlines()
        if not linha.rstrip().endswith(_marcador_cron())
    ]
    gravado = _subprocess(["crontab", "-"], entrada="\n".join(restantes).strip() + "\n")
    if gravado.returncode != 0:
        raise AgendadorErro("o sistema recusou a atualização do crontab do usuário")


def executar() -> tuple[int, dict]:
    """Atualiza os dois bancos e os derivados usando identidade já padronizada."""
    try:
        _cfg()
        adaptadores = config().get("adaptadores", {})
        plataformas = adaptadores.get("plataformas", []) if isinstance(adaptadores, dict) else []
        perfil = adaptadores.get("perfil_canary") if isinstance(adaptadores, dict) else None
        if not plataformas or not isinstance(plataformas[0], str) or not isinstance(perfil, str):
            raise AgendadorErro("adaptador canary ausente; rode `memoria instalar` novamente")
        rc, saida = ciclo.executar("atualizar", plataformas[0], perfil)
        saida = dict(saida)
        saida["origem"] = "agendador"
        saida["banco_negocio"] = "nao_acessado"
        return rc, saida
    except (AgendadorErro, OSError, SystemExit) as exc:
        return 1, {
            "schema": SCHEMA, "ok": False, "origem": "agendador",
            "banco_negocio": "nao_acessado", "publicado": False,
            "commit_criado": False, "erro": str(exc) or "configuração inválida",
        }
    except Exception as exc:
        return 1, {
            "schema": SCHEMA, "ok": False, "origem": "agendador",
            "banco_negocio": "nao_acessado", "publicado": False,
            "commit_criado": False,
            "erro": f"falha interna controlada ({type(exc).__name__})",
        }


def operar(acao: str) -> tuple[int, dict]:
    if acao == "executar":
        return executar()
    base = {
        "schema": SCHEMA, "ok": False, "acao": acao,
        "agendador": "windows-task-scheduler" if os.name == "nt" else "crontab-usuario",
        "identidade": _identidade(), "banco_negocio": "nao_acessado",
        "publicado": False, "commit_criado": False, "erro": None,
    }
    try:
        cfg = _cfg()
        if acao == "instalar":
            script = _escrever_script()
            _registrar(script)
            base["script"] = str(script)
        elif acao == "remover":
            _remover()
        elif acao != "status":
            raise AgendadorErro("ação de agendamento desconhecida")
        base["registrado"] = _status_sistema()
        base["horario_local"] = cfg["horario_local"]
        base["ok"] = base["registrado"] if acao != "remover" else not base["registrado"]
        return (0 if base["ok"] else 1), base
    except (AgendadorErro, OSError, SystemExit) as exc:
        base["erro"] = str(exc) or "configuração inválida"
        return 1, base
    except Exception as exc:
        base["erro"] = f"falha interna controlada ({type(exc).__name__})"
        return 1, base


def main(argv: list[str]) -> int:
    acao = argv[0] if argv else None
    if acao not in ACOES or argv[1:] != ["--json"]:
        print(json.dumps({
            "schema": SCHEMA, "ok": False,
            "erro": "uso: memoria agendador instalar|status|executar|remover --json",
            "banco_negocio": "nao_acessado", "publicado": False,
            "commit_criado": False,
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2
    rc, saida = operar(acao)
    print(json.dumps(saida, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return rc
