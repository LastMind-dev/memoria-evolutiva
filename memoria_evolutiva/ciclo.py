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
    """Executa sem sujar a saída JSON do ciclo, mas devolve o que foi impresso.

    O ciclo roda sob `--json` e não pode deixar a etapa escrever no stdout. Descartar
    o texto, porém, tornava toda falha diária indiagnosticável: o operador recebia
    `a atualização documental autônoma falhou` e o motivo real morria aqui, sem chegar
    ao journal. Devolver o capturado deixa quem chama decidir se vaza no erro.
    """
    fluxo = io.StringIO()
    try:
        with contextlib.redirect_stdout(fluxo), contextlib.redirect_stderr(fluxo):
            return funcao(*args, **kwargs), fluxo.getvalue()
    except BaseException as excecao:
        # `lib.morre()` escreve o motivo e levanta `SystemExit(2)`; sem guardar o
        # capturado aqui, o operador recebe `erro: "2"` — exatamente a opacidade que
        # este módulo passou a evitar no caminho de retorno.
        # Best-effort: uma excecao que recuse atribuicao (frozen dataclass,
        # `__setattr__` proprio) nao pode virar `AttributeError` e engolir a
        # falha real justo no caminho cujo proposito e diagnosticar.
        with contextlib.suppress(Exception):
            excecao._impresso = fluxo.getvalue()
        raise


_MARCA_ERRO = re.compile(r"^(x\s|ERROS?\b|FALHOU\b)", re.IGNORECASE)
_CREDENCIAL_NA_URL = re.compile(
    r"([a-z][a-z0-9+.-]*://)(?:[^\s/@]*@)?([^\s/?#]+)\S*", re.IGNORECASE
)
_SEGREDO_SOLTO = re.compile(
    r"\b(bearer\s+|"
    r"(?:token|senha|secret|api[_-]?key|access[_-]?token)[\"']?\s*[=:]\s*[\"']?)"
    r"[^\s\"',}]+",
    re.IGNORECASE,
)


def _sem_credencial(texto: str) -> str:
    """Reduz qualquer URL a esquema+host.

    `hindsight._pedir` inclui o endpoint verbatim no erro, e o endpoint aceita token
    em query ou em userinfo. `provisao.garantir()` omite o endpoint de propósito —
    deixar passar por aqui reabriria a invariante que aquele teste fecha.
    """
    texto = _CREDENCIAL_NA_URL.sub(r"\1\2", texto)
    return _SEGREDO_SOLTO.sub(r"\1[removido]", texto)


def _com_motivo(mensagem: str, impresso: str, limite: int = 3, largura: int = 200) -> str:
    """Anexa as linhas que explicam a falha — não simplesmente as últimas.

    `documentar.executar` imprime o rodapé DEPOIS de `validar` e `catraca` e só então
    decide o `rc`, então as últimas linhas costumam ser boilerplate. Prefira as linhas
    marcadas como erro e caia para as finais apenas quando não houver marca alguma.
    """
    linhas = [linha.strip() for linha in impresso.strip().splitlines() if linha.strip()]
    # Janela a partir da PRIMEIRA linha marcada, e nao so as linhas marcadas: um
    # cabecalho como `ERRO - faltam runbooks obrigatorios:` vem seguido da lista,
    # e a lista e o que o operador precisa. Sem marca alguma, cai para o fim.
    marcadas = [i for i, linha in enumerate(linhas) if _MARCA_ERRO.match(linha)]
    inicio = marcadas[0] if marcadas else max(0, len(linhas) - limite)
    escolhidas = linhas[inicio:inicio + limite]
    motivo = " | ".join(_sem_credencial(linha)[:largura] for linha in escolhidas)
    mensagem = _sem_credencial(mensagem)
    return f"{mensagem}: {motivo}" if motivo else mensagem


def _lock_mutacao():
    """Compartilha o lock do executor para impedir duas atualizações concorrentes."""
    cfg_executor = executor._cfg()
    return executor._Lock("ciclo-memoria", cfg_executor.get("lock_expira_segundos", 1200))


def _mensagem_de_excecao(exc: BaseException) -> str:
    """Mensagem legivel para o campo `erro`.

    `SystemExit(2)` vira `str(exc) == "2"`, e um erro que comeca com `2:` no journal
    parece codigo truncado em vez de diagnostico.
    """
    texto = str(exc).strip()
    if not texto:
        return "configuração inválida"
    if texto.isdigit():
        return f"a etapa encerrou com {type(exc).__name__} {texto}"
    return texto


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
            (rc, canary), impresso_canary = _silencioso(
                adaptadores.canary, plataforma, perfil
            )
            if rc != 0 and cfg.get("auto_reparar_no_inicio") is True:
                with _lock_mutacao():
                    rc_doc, impresso = _silencioso(documentar.executar)
                    if rc_doc != 0:
                        saida["canary"] = canary
                        saida["erro"] = _com_motivo(
                            "a reparação documental autônoma falhou", impresso
                        )
                        return 1, saida
                saida["auto_reparado"] = True
                (rc, canary), impresso_canary = _silencioso(
                    adaptadores.canary, plataforma, perfil
                )
        else:
            with _lock_mutacao():
                rc_doc, impresso = _silencioso(documentar.executar)
                if rc_doc != 0:
                    saida["erro"] = _com_motivo(
                        "a atualização documental autônoma falhou", impresso
                    )
                    return 1, saida
            (rc, canary), impresso_canary = _silencioso(
                adaptadores.canary, plataforma, perfil
            )
        saida["canary"] = canary
        saida["ok"] = rc == 0
        if rc != 0:
            saida["erro"] = _com_motivo(
                "o canary não confirmou identidade, fontes e frescor", impresso_canary
            )
        return (0 if saida["ok"] else 1), saida
    except (provisao.ProvisaoErro, executor.ExecutorErro, OSError, SystemExit) as exc:
        saida["erro"] = _com_motivo(
            _mensagem_de_excecao(exc), getattr(exc, "_impresso", "")
        )
        return 1, saida
    except Exception as exc:
        saida["erro"] = _com_motivo(
            f"falha interna controlada ({type(exc).__name__})",
            getattr(exc, "_impresso", ""),
        )
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
