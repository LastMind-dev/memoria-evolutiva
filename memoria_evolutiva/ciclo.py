"""Ciclo de vida comum a qualquer agente ou IDE conectado ao projeto."""

from __future__ import annotations

import contextlib
import io
import json
import re
import sys

from . import adaptadores, documentar, executor, provisao
from .lib import config


def _cfg() -> dict:
    valor = config().get("ciclo", {})
    if not isinstance(valor, dict) or valor.get("ativo") is not True:
        raise provisao.ProvisaoErro(
            "ciclo autônomo ausente ou desativado; rode `memoria instalar` com a versão atual"
        )
    return valor


def _silencioso(funcao, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return funcao(*args, **kwargs)


def _lock_mutacao():
    """Compartilha o lock do executor para impedir duas atualizações concorrentes."""
    cfg_executor = executor._cfg()
    return executor._Lock("ciclo-memoria", cfg_executor.get("lock_expira_segundos", 1200))


def executar(acao: str, plataforma: str, perfil: str) -> tuple[int, dict]:
    saida = {
        "schema": 1,
        "ok": False,
        "acao": acao,
        "plataforma": plataforma,
        "perfil": perfil,
        "auto_reparado": False,
        "publicado": False,
        "commit_criado": False,
        "provedores": None,
        "canary": None,
        "erro": None,
    }
    try:
        cfg = _cfg()
        if acao not in {"iniciar", "atualizar"}:
            raise provisao.ProvisaoErro("ação de ciclo desconhecida")
        if plataforma not in adaptadores._plataformas():
            raise provisao.ProvisaoErro(
                f"plataforma não declarada no projeto: `{plataforma}`"
            )
        perfil_esperado = adaptadores._perfil_canary()
        if perfil != perfil_esperado:
            raise provisao.ProvisaoErro(
                f"perfil do ciclo diverge: esperado `{perfil_esperado}`, recebido `{perfil}`"
            )
        saida["provedores"] = provisao.garantir()
        if acao == "iniciar":
            rc, canary = _silencioso(adaptadores.canary, plataforma, perfil)
            if rc != 0 and cfg.get("auto_reparar_no_inicio") is True:
                with _lock_mutacao():
                    if _silencioso(documentar.executar) != 0:
                        saida["canary"] = canary
                        saida["erro"] = "a reparação documental autônoma falhou"
                        return 1, saida
                saida["auto_reparado"] = True
                rc, canary = _silencioso(adaptadores.canary, plataforma, perfil)
        else:
            with _lock_mutacao():
                if _silencioso(documentar.executar) != 0:
                    saida["erro"] = "a atualização documental autônoma falhou"
                    return 1, saida
            rc, canary = _silencioso(adaptadores.canary, plataforma, perfil)
        saida["canary"] = canary
        saida["ok"] = rc == 0
        if rc != 0:
            saida["erro"] = "o canary não confirmou identidade, fontes e frescor"
        return (0 if saida["ok"] else 1), saida
    except (provisao.ProvisaoErro, executor.ExecutorErro, OSError, SystemExit) as exc:
        saida["erro"] = str(exc) or "configuração inválida"
        return 1, saida
    except Exception as exc:
        saida["erro"] = f"falha interna controlada ({type(exc).__name__})"
        return 1, saida


def main(argv: list[str]) -> int:
    acao = argv[0] if argv else None
    opcoes: dict[str, str | bool] = {}
    invalidos: list[str] = []
    for argumento in argv[1:]:
        match = re.fullmatch(r"--([a-z-]+)(?:=(.*))?", argumento)
        if not match or match.group(1) in opcoes:
            invalidos.append(argumento)
            continue
        opcoes[match.group(1)] = match.group(2) if match.group(2) is not None else True
    if (
        acao not in {"iniciar", "atualizar"}
        or invalidos
        or set(opcoes) - {"plataforma", "perfil", "json"}
        or opcoes.get("json") is not True
        or not isinstance(opcoes.get("plataforma"), str)
        or not isinstance(opcoes.get("perfil"), str)
    ):
        print(json.dumps({
            "schema": 1,
            "ok": False,
            "erro": "uso: memoria ciclo iniciar|atualizar --plataforma=ID --perfil=PERFIL --json",
            "publicado": False,
            "commit_criado": False,
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 2
    rc, saida = executar(
        acao, str(opcoes["plataforma"]), str(opcoes["perfil"])
    )
    print(json.dumps(saida, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return rc
