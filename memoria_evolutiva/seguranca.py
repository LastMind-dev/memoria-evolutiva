"""Política determinística de acesso e redaction da memória do projeto.

Este módulo não autentica usuários nem autoriza ações. Ele reduz o corpus documental
antes da retenção e aplica escopo exato antes da entrega ao modelo. A aplicação dona do
agente continua responsável por identidade autenticada, permissões e auditoria.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Callable

from .lib import config, frontmatter


CLASSIFICACOES = ("publico", "interno", "restrito", "secreto-nao-indexar")
PERFIS = (
    "atendimento", "automacao-codigo", "engenharia-documentacao",
    "engenharia-leitura", "operacao-assistida",
)
PERFIS_COM_ESCOPO = {"atendimento", "operacao-assistida"}
MARCADOR = "[DADO-REMOVIDO:{}]"
IDENTIFICADOR = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


class SegurancaErro(ValueError):
    pass


def _cfg() -> dict:
    valor = config().get("seguranca_memoria", {})
    if not isinstance(valor, dict):
        raise SegurancaErro("`seguranca_memoria` precisa ser objeto em `padrao.json`")
    return valor


def lista_frontmatter(valor: object, campo: str) -> list[str]:
    if valor in (None, "", []):
        return []
    itens = valor if isinstance(valor, list) else [valor]
    if any(not isinstance(item, str) or not IDENTIFICADOR.fullmatch(item) for item in itens):
        raise SegurancaErro(
            f"`{campo}` aceita somente identificadores minúsculos de até 64 caracteres"
        )
    if len(set(itens)) != len(itens):
        raise SegurancaErro(f"`{campo}` não aceita valores duplicados")
    return sorted(itens)


def metadados(conteudo_ou_fm: str | dict | None) -> dict:
    fm = (frontmatter(conteudo_ou_fm) or {}) if isinstance(conteudo_ou_fm, str) else (
        conteudo_ou_fm or {}
    )
    classificacao = str(fm.get("classificacao") or "interno")
    if classificacao not in CLASSIFICACOES:
        raise SegurancaErro(f"classificação desconhecida: `{classificacao}`")
    audiencia = lista_frontmatter(fm.get("audience"), "audience")
    desconhecidos = sorted(set(audiencia) - set(PERFIS))
    if desconhecidos:
        raise SegurancaErro("`audience` contém perfil desconhecido: " + ", ".join(desconhecidos))
    return {
        "classificacao": classificacao,
        "audience": audiencia,
        "produtos": lista_frontmatter(fm.get("produtos"), "produtos"),
        "tenants": lista_frontmatter(fm.get("tenants"), "tenants"),
    }


def indexavel(conteudo_ou_fm: str | dict | None) -> bool:
    return metadados(conteudo_ou_fm)["classificacao"] != "secreto-nao-indexar"


def normalizar_escopo(perfil: str, produto: object = None,
                      tenant: object = None) -> tuple[str | None, str | None]:
    def normalizar(valor: object, campo: str) -> str | None:
        if valor in (None, ""):
            return None
        if not isinstance(valor, str) or not IDENTIFICADOR.fullmatch(valor):
            raise SegurancaErro(
                f"`{campo}` precisa ser identificador minúsculo de até 64 caracteres"
            )
        return valor

    produto_normalizado = normalizar(produto, "produto")
    tenant_normalizado = normalizar(tenant, "tenant")
    if perfil in PERFIS_COM_ESCOPO and (
        produto_normalizado is None or tenant_normalizado is None
    ):
        raise SegurancaErro(
            f"perfil `{perfil}` exige `produto` e `tenant` explícitos"
        )
    return produto_normalizado, tenant_normalizado


def escopo_permite(item: dict, produto: str | None, tenant: str | None) -> bool:
    produtos = item.get("produtos", [])
    tenants = item.get("tenants", [])
    if not isinstance(produtos, list) or not isinstance(tenants, list):
        return False
    if produtos and produto not in produtos:
        return False
    if tenants and tenant not in tenants:
        return False
    return True


def _substituir_grupo(regra: str) -> Callable[[re.Match[str]], str]:
    def substituir(match: re.Match[str]) -> str:
        prefixo = match.group(1) if match.lastindex else ""
        return prefixo + MARCADOR.format(regra)
    return substituir


REGRAS: tuple[tuple[str, re.Pattern[str], str | Callable[[re.Match[str]], str]], ...] = (
    (
        "chave-privada",
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----.*?"
            r"-----END (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----",
            re.I | re.S,
        ),
        MARCADOR.format("chave-privada"),
    ),
    (
        "credencial-url",
        re.compile(r"\b(https?://)[^\s/@:]+:[^\s/@]+@", re.I),
        lambda m: m.group(1) + MARCADOR.format("credencial-url") + "@",
    ),
    (
        "bearer-token",
        re.compile(r"(?i)(\bBearer\s+)[A-Za-z0-9._~+/=-]{8,}"),
        _substituir_grupo("bearer-token"),
    ),
    (
        "segredo-configuracao",
        re.compile(
            r"(?im)(\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|"
            r"client[_-]?secret|password|passwd|senha|secret)\b\s*[:=]\s*)"
            r"(?:['\"])?[^\s'\"`]{6,}(?:['\"])?"
        ),
        _substituir_grupo("segredo-configuracao"),
    ),
    (
        "email",
        re.compile(r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w.-])", re.I),
        MARCADOR.format("email"),
    ),
    (
        "cpf-cnpj",
        re.compile(
            r"(?<![A-Za-z0-9])(?:\d{3}[.\s-]?\d{3}[.\s-]?\d{3}[-\s]?\d{2}|"
            r"\d{2}[.\s-]?\d{3}[.\s-]?\d{3}[/\s-]?\d{4}[-\s]?\d{2})(?![A-Za-z0-9])"
        ),
        MARCADOR.format("cpf-cnpj"),
    ),
)


def redigir(conteudo: str) -> tuple[str, dict]:
    if not isinstance(conteudo, str):
        raise SegurancaErro("redaction aceita somente texto")
    if _cfg().get("redaction_antes_retain") is not True:
        raise SegurancaErro("`seguranca_memoria.redaction_antes_retain` precisa ser true")
    resultado = conteudo
    contagens: dict[str, int] = {}
    for nome, padrao, substituto in REGRAS:
        resultado, quantidade = padrao.subn(substituto, resultado)
        if quantidade:
            contagens[nome] = quantidade
    return resultado, {
        "algoritmo": "redaction-deterministica-v1",
        "ocorrencias": sum(contagens.values()),
        "por_regra": contagens,
        "conteudo_sha256": hashlib.sha256(resultado.encode("utf-8")).hexdigest(),
    }


def fingerprint() -> str:
    politica = {
        "algoritmo": "redaction-deterministica-v1",
        "classificacoes": CLASSIFICACOES,
        "perfis_com_escopo": sorted(PERFIS_COM_ESCOPO),
        "redaction": [
            {"nome": nome, "padrao": padrao.pattern, "flags": padrao.flags}
            for nome, padrao, _ in REGRAS
        ],
        "global_sem_escopo_permitido": True,
        "match_escopo": "exato",
    }
    return hashlib.sha256(json.dumps(
        politica, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
