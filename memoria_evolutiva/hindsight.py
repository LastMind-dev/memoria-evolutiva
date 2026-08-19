"""Adaptador mínimo da API oficial do Hindsight, sem guardar segredos no projeto."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import BoundedSemaphore, Lock

from . import __version__, indice, seguranca
from .lib import commit_atual, config, frontmatter, raiz


class HindsightErro(RuntimeError):
    pass


_SEMAFOROS: dict[tuple[str, str, int], BoundedSemaphore] = {}
_SEMAFOROS_LOCK = Lock()
_CACHE_CONSULTAS: OrderedDict[tuple, dict] = OrderedDict()
_CACHE_CONSULTAS_LOCK = Lock()


def _limite_consultas() -> int:
    valor = _cfg().get("consultas_paralelas", 2)
    if isinstance(valor, bool) or not isinstance(valor, int) or not 1 <= valor <= 32:
        raise HindsightErro("`memoria.consultas_paralelas` precisa ficar entre 1 e 32")
    return valor


def _semaforo_consultas(endpoint: str, banco: str, limite: int) -> BoundedSemaphore:
    chave = (endpoint, banco, limite)
    with _SEMAFOROS_LOCK:
        return _SEMAFOROS.setdefault(chave, BoundedSemaphore(limite))


def _token_cache() -> str:
    marcador = indice.marcador_path()
    try:
        estado = marcador.stat()
        marcador_token = f"{estado.st_mtime_ns}:{estado.st_size}"
    except OSError:
        marcador_token = "sem-marcador"
    ttl = _cfg().get("cache_consulta_ttl_segundos", 30)
    if isinstance(ttl, bool) or not isinstance(ttl, int) or not 0 <= ttl <= 3600:
        raise HindsightErro(
            "`memoria.cache_consulta_ttl_segundos` precisa ficar entre 0 e 3600"
        )
    janela = int(time.monotonic() // ttl) if ttl else time.monotonic_ns()
    return f"{marcador_token}:{janela}"


def _limpar_cache_consultas() -> None:
    with _CACHE_CONSULTAS_LOCK:
        _CACHE_CONSULTAS.clear()


def _consultar_cache(endpoint: str, banco: str, tags: tuple[str, ...],
                     pergunta: str, max_tokens: int, budget: str,
                     token_cache: str, limite: int) -> dict:
    pergunta_sha = hashlib.sha256(pergunta.encode("utf-8")).hexdigest()
    chave = (
        endpoint, banco, tags, pergunta_sha, max_tokens, budget, token_cache, limite,
    )
    with _CACHE_CONSULTAS_LOCK:
        anterior = _CACHE_CONSULTAS.get(chave)
        if anterior is not None:
            _CACHE_CONSULTAS.move_to_end(chave)
            return anterior
    with _semaforo_consultas(endpoint, banco, limite):
        resposta = _requisitar(
            "POST",
            f"/v1/default/banks/{urllib.parse.quote(banco, safe='')}/memories/recall",
            {
                "query": pergunta,
                "types": ["world", "experience", "observation"],
                "max_tokens": max_tokens,
                "budget": budget,
                "include_chunks": True,
                "tags": list(tags),
                "tags_match": "all_strict",
            },
        )
    with _CACHE_CONSULTAS_LOCK:
        _CACHE_CONSULTAS[chave] = resposta
        _CACHE_CONSULTAS.move_to_end(chave)
        while len(_CACHE_CONSULTAS) > 256:
            _CACHE_CONSULTAS.popitem(last=False)
    return resposta


class _SemRedirecionamento(urllib.request.HTTPRedirectHandler):
    """Um serviço de loopback não pode redirecionar a credencial para outra origem."""

    def redirect_request(
        self, req: urllib.request.Request, fp: object, code: int,
        msg: str, headers: object, newurl: str,
    ) -> None:
        return None


def _cfg() -> dict:
    return config().get("memoria", {})


def _endpoint() -> str:
    endpoint = os.environ.get(
        "MEMORIA_HINDSIGHT_URL", str(_cfg().get("endpoint", "http://127.0.0.1:8888"))
    ).rstrip("/")
    partes = urllib.parse.urlsplit(endpoint)
    if partes.scheme not in {"http", "https"} or not partes.hostname:
        raise HindsightErro("`memoria.endpoint` precisa ser uma URL HTTP(S) válida")
    if partes.username is not None or partes.password is not None:
        raise HindsightErro("credencial não pode fazer parte de `memoria.endpoint`")
    if _cfg().get("modo") == "local" and partes.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise HindsightErro("Hindsight em modo local só aceita endpoint de loopback")
    return endpoint


def _banco() -> str:
    banco = str(_cfg().get("banco") or config()["projeto"]).strip()
    if not banco or any(ch in banco for ch in "/?#"):
        raise HindsightErro("`memoria.banco` precisa ser um identificador não vazio, sem /, ? ou #")
    return banco


def _tags() -> list[str]:
    projeto = str(config()["projeto"])
    return ["memoria-evolutiva", f"projeto:{projeto}", "documentacao-canonica"]


def _headers() -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "User-Agent": f"memoria-evolutiva/{__version__}",
    }
    nome_env = str(_cfg().get("api_key_env") or "").strip()
    if nome_env and os.environ.get(nome_env):
        headers["Authorization"] = f"Bearer {os.environ[nome_env]}"
    return headers


def _requisitar(metodo: str, caminho: str, payload: dict | None = None,
                aceitar_404: bool = False) -> dict:
    url = _endpoint() + caminho
    dados = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url, data=dados,
        headers=_headers(), method=metodo,
    )
    try:
        # Endpoint local deve ser acessado diretamente, sem proxy do ambiente.
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _SemRedirecionamento()
        )
        with opener.open(req, timeout=float(_cfg().get("timeout_segundos", 300))) as resp:
            corpo = resp.read().decode("utf-8", errors="replace")
            return json.loads(corpo) if corpo.strip() else {"status_http": resp.status}
    except urllib.error.HTTPError as exc:
        if exc.code == 404 and aceitar_404:
            return {"status_http": 404}
        detalhe = exc.read().decode("utf-8", errors="replace")[:1000]
        raise HindsightErro(f"Hindsight respondeu HTTP {exc.code}: {detalhe}") from exc
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise HindsightErro(f"Hindsight indisponível em {_endpoint()}: {exc}") from exc


def _documentos() -> tuple[dict[str, str], dict[str, str]]:
    try:
        hashes, _ = indice.documentos_do_nucleo()
    except seguranca.SegurancaErro as exc:
        raise HindsightErro(f"política de segurança documental inválida: {exc}") from exc
    documentos: dict[str, str] = {}
    base = Path(raiz())
    for rel in hashes:
        conteudo = (base / rel).read_text(encoding="utf-8", errors="replace")
        documentos[rel] = conteudo
    return documentos, hashes


def _document_id(rel: str) -> str:
    return f"memoria-evolutiva:{config()['projeto']}:{rel}"


def _conteudo_indexado(rel: str, conteudo: str) -> str:
    try:
        redigido, _ = seguranca.redigir(conteudo)
    except seguranca.SegurancaErro as exc:
        raise HindsightErro(f"redaction recusada em `{rel}`: {exc}") from exc
    return (
        f"<!-- source_uri: {rel} -->\n"
        f"<!-- seguranca_fingerprint: {seguranca.fingerprint()} -->\n"
        f"# FONTE: {rel}\n\n{redigido.rstrip()}\n"
    )


def _item(rel: str, conteudo: str) -> dict:
    fm = frontmatter(conteudo) or {}
    try:
        acesso = seguranca.metadados(fm)
        _, auditoria = seguranca.redigir(conteudo)
    except seguranca.SegurancaErro as exc:
        raise HindsightErro(f"política de segurança recusou `{rel}`: {exc}") from exc
    commit = commit_atual()
    tags = [*_tags(), f"source:{rel}"]
    for chave in ("tipo", "status", "id"):
        if fm.get(chave):
            tags.append(f"{chave}:{fm[chave]}")
    if fm.get("status") != "superado":
        tags.append("vigente")
    tags.append(f"classificacao:{acesso['classificacao']}")
    tags.extend(f"audience:{valor}" for valor in acesso["audience"])
    tags.extend(f"produto:{valor}" for valor in acesso["produtos"])
    tags.extend(f"tenant:{valor}" for valor in acesso["tenants"])
    if commit:
        tags.append(f"commit:{commit}")
    metadata = {
        "source_uri": rel,
        "source_commit": commit or "",
        "doc_id": str(fm.get("id") or ""),
        "doc_tipo": str(fm.get("tipo") or ""),
        "doc_status": str(fm.get("status") or ""),
        "projeto": str(config()["projeto"]),
        "classificacao": str(acesso["classificacao"]),
        # A API oficial tipa metadata como map[string, string]. Preserve listas em
        # JSON canônico: isso mantém a estrutura auditável sem depender de coerção
        # permissiva do servidor (Hindsight 0.9.1 responde 422 para listas/inteiros).
        "audience": json.dumps(acesso["audience"], ensure_ascii=False, separators=(",", ":")),
        "produtos": json.dumps(acesso["produtos"], ensure_ascii=False, separators=(",", ":")),
        "tenants": json.dumps(acesso["tenants"], ensure_ascii=False, separators=(",", ":")),
        "redaction_algoritmo": str(auditoria["algoritmo"]),
        "redaction_ocorrencias": str(auditoria["ocorrencias"]),
        "redacted_sha256": str(auditoria["conteudo_sha256"]),
    }
    return {
        "content": _conteudo_indexado(rel, conteudo),
        "context": f"Documentação canônica do projeto {config()['projeto']}; fonte {rel}.",
        "document_id": _document_id(rel),
        "metadata": metadata,
        "tags": tags,
        "update_mode": "replace",
        "timestamp": "unset",
    }


def _confirmar_documento(banco: str, rel: str, conteudo: str) -> int:
    documento = _requisitar(
        "GET",
        f"/v1/default/banks/{urllib.parse.quote(banco, safe='')}/documents/"
        f"{urllib.parse.quote(_document_id(rel), safe='')}",
    )
    if documento.get("original_text") != conteudo:
        raise HindsightErro(f"leitura de confirmação divergiu em `{rel}`")
    unidades = documento.get("memory_unit_count")
    if not isinstance(unidades, int) or unidades < 1:
        raise HindsightErro(f"leitura de confirmação não encontrou memórias para `{rel}`")
    return unidades


def _reter(banco: str, items: list[dict]) -> None:
    if not items:
        return
    tamanho = sum(len(str(item["content"]).encode("utf-8")) for item in items)
    limite = int(_cfg().get("assincrono_acima_de_bytes", 1_000_000))
    assincrono = tamanho >= limite
    payload: dict = {
        "items": items,
        "document_tags": _tags(),
        "async": assincrono,
    }
    if assincrono:
        # Cada reconstrução recebe uma operação nova. Reutilizar um UUID derivado do
        # conteúdo faria um banco apagado reencontrar a operação antiga já concluída sem
        # executar o retain novamente.
        payload["operation_id"] = str(uuid.uuid4())
    resposta = _requisitar(
        "POST",
        f"/v1/default/banks/{urllib.parse.quote(banco, safe='')}/memories",
        payload,
    )
    if resposta.get("success") is False:
        raise HindsightErro(f"retain em lote não confirmado: {resposta}")
    if not assincrono:
        return

    operation_id = str(resposta.get("operation_id") or payload["operation_id"])
    prazo = time.monotonic() + float(_cfg().get("timeout_segundos", 300))
    intervalo = float(_cfg().get("intervalo_poll_segundos", 1))
    while time.monotonic() < prazo:
        estado = _requisitar(
            "GET",
            f"/v1/default/banks/{urllib.parse.quote(banco, safe='')}/operations/"
            f"{urllib.parse.quote(operation_id, safe='')}",
        )
        status = estado.get("status")
        if status == "completed":
            return
        if status in {"failed", "cancelled"}:
            raise HindsightErro(
                f"operação Hindsight {operation_id} terminou como {status}: "
                f"{estado.get('error_message') or 'sem detalhe'}"
            )
        time.sleep(max(0.05, intervalo))
    raise HindsightErro(f"operação Hindsight {operation_id} excedeu o tempo limite")


def verificar_ao_vivo() -> dict:
    """Confirma identidade, conteúdo e ao menos uma memória por documento atual."""
    documentos, hashes = _documentos()
    if not documentos:
        raise HindsightErro("o núcleo documental está vazio")
    banco = _banco()
    tarefas = [
        (rel, _conteudo_indexado(rel, conteudo))
        for rel, conteudo in documentos.items()
    ]
    trabalhadores = max(1, min(int(_cfg().get("confirmacoes_paralelas", 8)), len(tarefas)))
    with ThreadPoolExecutor(max_workers=trabalhadores) as executor:
        unidades = sum(executor.map(
            lambda item: _confirmar_documento(banco, item[0], item[1]), tarefas
        ))
    return {
        "endpoint": _endpoint(),
        "banco": banco,
        "documentos": len(hashes),
        "memorias_persistidas": unidades,
        "confirmado": True,
    }


def sincronizar() -> dict:
    """Atualiza documentos individualmente, confirma todos e só então marca."""
    _limpar_cache_consultas()
    documentos, hashes = _documentos()
    if not documentos:
        raise HindsightErro("o núcleo documental está vazio; nada foi enviado ao Hindsight")
    banco = _banco()
    estado_anterior: dict = {}
    marcador = indice.marcador_path()
    if marcador.is_file():
        try:
            estado_anterior = json.loads(marcador.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            estado_anterior = {}
    hashes_anteriores = estado_anterior.get("documentos", {})
    if not isinstance(hashes_anteriores, dict):
        hashes_anteriores = {}

    # Documento removido precisa sair do banco; do contrário fatos superados continuam
    # aparecendo mesmo com todos os hashes locais verdes.
    for rel in sorted(set(hashes_anteriores) - set(hashes)):
        _requisitar(
            "DELETE",
            f"/v1/default/banks/{urllib.parse.quote(banco, safe='')}/documents/"
            f"{urllib.parse.quote(_document_id(rel), safe='')}",
            aceitar_404=True,
        )

    alterados = [
        rel for rel, digest in hashes.items()
        if hashes_anteriores.get(rel) != digest
    ]
    # Mesmo sem alteração local, a leitura ao vivo abaixo repara clone novo, banco
    # limpo ou marcador copiado de outra máquina.
    if alterados:
        _reter(banco, [_item(rel, documentos[rel]) for rel in alterados])

    try:
        prova = verificar_ao_vivo()
    except HindsightErro:
        # Marcador aparentemente fresco pode pertencer a um banco vazio. Reenvie todos
        # uma vez e confirme novamente, sem confiar no cache local.
        if alterados == list(hashes):
            raise
        _reter(banco, [_item(rel, documentos[rel]) for rel in hashes])
        prova = verificar_ao_vivo()
    prova["document_ids"] = {rel: _document_id(rel) for rel in hashes}
    prova["conteudo_sha256"] = hashlib.sha256(
        "\n".join(f"{rel}:{hashes[rel]}" for rel in hashes).encode("utf-8")
    ).hexdigest()
    try:
        auditorias = [seguranca.redigir(documentos[rel])[1] for rel in sorted(documentos)]
    except seguranca.SegurancaErro as exc:
        raise HindsightErro(f"auditoria de redaction falhou: {exc}") from exc
    prova["seguranca_fingerprint"] = seguranca.fingerprint()
    prova["redaction"] = {
        "algoritmo": "redaction-deterministica-v1",
        "documentos": len(auditorias),
        "ocorrencias": sum(item["ocorrencias"] for item in auditorias),
    }
    legado_id = estado_anterior.get("prova_do_provedor", {}).get("document_id")
    if legado_id and legado_id not in prova["document_ids"].values():
        _requisitar(
            "DELETE",
            f"/v1/default/banks/{urllib.parse.quote(banco, safe='')}/documents/"
            f"{urllib.parse.quote(str(legado_id), safe='')}",
            aceitar_404=True,
        )
    indice.gravar_marcador(prova)
    return prova


def consultar(pergunta: str, max_tokens: int = 4096) -> dict:
    if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens < 1:
        raise HindsightErro("`max_tokens` da consulta precisa ser inteiro positivo")
    budget = str(_cfg().get("consulta_budget", "mid"))
    if budget not in {"low", "mid", "high"}:
        raise HindsightErro("`memoria.consulta_budget` precisa ser low, mid ou high")
    resposta = _consultar_cache(
        _endpoint(), _banco(), tuple([*_tags(), "vigente"]), pergunta,
        max_tokens, budget, _token_cache(), _limite_consultas(),
    )
    return copy.deepcopy(resposta)
