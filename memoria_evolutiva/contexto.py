"""Gateway neutro, verificável e independente de LLM para contexto de projeto."""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import sys
import unicodedata
from functools import lru_cache
from pathlib import Path

from . import __version__, fragmentos, grafo, hindsight, indice, seguranca
from .lib import barras, config, raiz


SCHEMA = 2
MCP_PROTOCOL = "2026-07-28"
PERFIS = {
    "engenharia-leitura": {
        "classificacoes": {"publico", "interno", "restrito"},
        "prefixos": None,
        "codigo": True,
    },
    "engenharia-documentacao": {
        "classificacoes": {"publico", "interno", "restrito"},
        "prefixos": None,
        "codigo": True,
    },
    "automacao-codigo": {
        "classificacoes": {"publico", "interno", "restrito"},
        "prefixos": None,
        "codigo": True,
    },
    # Atendimento e operação exigem produto+tenant explícitos e nunca recebem código.
    "atendimento": {
        "classificacoes": {"publico"},
        "prefixos": ("docs/produto/", "docs/funcional/", "docs/runbooks/"),
        "codigo": False,
    },
    "operacao-assistida": {
        "classificacoes": {"publico"},
        "prefixos": ("docs/produto/", "docs/funcional/", "docs/runbooks/"),
        "codigo": False,
    },
}


class ContextoErro(RuntimeError):
    pass


def _cfg() -> dict:
    valor = config().get("contexto", {})
    if not isinstance(valor, dict):
        raise ContextoErro("`contexto` precisa ser um objeto em `padrao.json`")
    return valor


def _inteiro(nome: str, padrao: int, minimo: int, maximo: int) -> int:
    valor = _cfg().get(nome, padrao)
    if isinstance(valor, bool) or not isinstance(valor, int) or not minimo <= valor <= maximo:
        raise ContextoErro(
            f"`contexto.{nome}` precisa ser inteiro entre {minimo} e {maximo}"
        )
    return valor


def _normalizar(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto.casefold())
    sem_acentos = "".join(c for c in decomposto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9_./-]+", " ", sem_acentos).strip()


def _tokens(texto: str) -> list[str]:
    return [t for t in _normalizar(texto).split() if len(t) > 1]


def _pontuacao(pergunta: str, texto: str) -> float:
    consulta = _tokens(pergunta)
    if not consulta:
        return 0.0
    normalizado = _normalizar(texto)
    presentes = sum(1 for token in set(consulta) if token in normalizado)
    frequencia = sum(min(normalizado.count(token), 3) for token in set(consulta))
    frase = 6.0 if _normalizar(pergunta) in normalizado else 0.0
    return frase + 4.0 * presentes / len(set(consulta)) + 0.25 * frequencia


def _permitido(fragmento: dict, perfil: str,
               produto: str | None, tenant: str | None) -> bool:
    regra = PERFIS[perfil]
    if fragmento.get("classificacao") not in regra["classificacoes"]:
        return False
    caminho = str(fragmento.get("source_uri", "")).split("#", 1)[0]
    prefixos = regra["prefixos"]
    if prefixos is not None and not any(caminho.startswith(p) for p in prefixos):
        return False
    audiencia = fragmento.get("audience", [])
    if audiencia and perfil not in audiencia:
        return False
    return seguranca.escopo_permite(fragmento, produto, tenant)


def _carregar_manifesto() -> dict:
    if fragmentos.verificar(silencioso=True) != 0:
        raise ContextoErro(
            "manifesto de fragmentos ausente ou defasado; rode `memoria fragmentos gerar`"
        )
    try:
        dados = json.loads(fragmentos._manifesto_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContextoErro(f"manifesto de fragmentos inválido: {exc}") from exc
    if dados.get("schema") != 2 or not isinstance(dados.get("fragmentos"), list):
        raise ContextoErro("manifesto de fragmentos não segue o contrato v2")
    return dados


def _origem_resultado(resultado: dict) -> str | None:
    metadados = resultado.get("metadata")
    if isinstance(metadados, dict) and metadados.get("source_uri"):
        return barras(str(metadados["source_uri"])).split("#", 1)[0]
    if resultado.get("source"):
        return barras(str(resultado["source"])).split("#", 1)[0]
    documento = str(resultado.get("document_id") or "")
    marcador = ":docs/"
    if marcador in documento:
        return "docs/" + documento.split(marcador, 1)[1]
    return None


def _sinais_semanticos(
    pergunta: str, max_tokens: int,
) -> tuple[dict[str, list[tuple[float, str]]], list[str], bool]:
    cfg_memoria = config().get("memoria", {})
    if not cfg_memoria.get("ativo"):
        return {}, ["Hindsight desativado explicitamente; busca semântica não executada."], True
    if indice.verificar(silencioso=True) != 0:
        return {}, ["Hindsight defasado; resultados semânticos foram ignorados."], False
    try:
        hindsight.verificar_ao_vivo()
        resposta = hindsight.consultar(pergunta, max_tokens=min(max_tokens, 4096))
    except hindsight.HindsightErro as exc:
        return {}, [f"Hindsight indisponível; resultados semânticos ignorados: {exc}"], False
    resultados = resposta.get("results", [])
    if not isinstance(resultados, list):
        return {}, ["Hindsight devolveu `results` inválido; sinal semântico ignorado."], False
    sinais: dict[str, list[tuple[float, str]]] = {}
    sem_origem = 0
    for ordem, resultado in enumerate(resultados):
        if not isinstance(resultado, dict):
            continue
        origem = _origem_resultado(resultado)
        if not origem:
            sem_origem += 1
            continue
        sinais.setdefault(origem, []).append((
            8.0 / (ordem + 1), str(resultado.get("text") or "")
        ))
    avisos = []
    if sem_origem:
        avisos.append(
            f"Hindsight devolveu {sem_origem} resultado(s) sem `source_uri`; foram ignorados."
        )
    return sinais, avisos, True


def _relativo_codigo(valor: object, arquivos: dict[str, str]) -> str | None:
    fonte = barras(str(valor or ""))
    if not fonte:
        return None
    base = barras(str(Path(raiz()).resolve())).rstrip("/") + "/"
    if fonte.casefold().startswith(base.casefold()):
        fonte = fonte[len(base):]
    while fonte.startswith("./"):
        fonte = fonte[2:]
    por_caixa = {p.casefold(): p for p in arquivos}
    if fonte.casefold() in por_caixa:
        return por_caixa[fonte.casefold()]
    candidatos = [p for p in arquivos if fonte.casefold().endswith("/" + p.casefold())]
    return sorted(candidatos)[0] if candidatos else None


def _linha_no(no: dict) -> int | None:
    for chave in ("start_line", "line_start", "line", "lineno"):
        valor = no.get(chave)
        if isinstance(valor, int) and valor >= 1:
            return valor
    return None


def _descricao_no(no: dict) -> str:
    chaves = (
        "name", "qualified_name", "full_name", "type", "kind", "label",
        "signature", "id", "source_file",
    )
    partes = [str(no[c]) for c in chaves if isinstance(no.get(c), (str, int, float))]
    return " ".join(partes)[:4000]


def _melhor_linha(linhas: list[str], pergunta: str) -> tuple[int, float]:
    melhor = (1, 0.0)
    for numero, linha in enumerate(linhas, 1):
        score = _pontuacao(pergunta, linha)
        if score > melhor[1]:
            melhor = (numero, score)
    return melhor


def _trecho_codigo(linhas: list[str], linha: int) -> str:
    inicio = max(0, linha - 3)
    fim = min(len(linhas), linha + 2)
    return "\n".join(
        f"{numero:>6} | {linhas[numero - 1]}" for numero in range(inicio + 1, fim + 1)
    )


def _candidatos_codigo(pergunta: str, permitir: bool) -> tuple[list[dict], list[str], bool]:
    if not permitir:
        return [], [], True
    cfg_grafo = config().get("grafo", {})
    ativo = bool(cfg_grafo.get("ativo"))
    grafo_fresco = ativo and grafo.verificar(silencioso=True, exigir_comando=False) == 0
    avisos: list[str] = []
    if ativo and not grafo_fresco:
        avisos.append("Graphify defasado; sinais estruturais foram ignorados.")
    elif not ativo:
        avisos.append("Graphify desativado explicitamente; apenas busca literal no código foi usada.")

    if grafo_fresco:
        try:
            marcador = json.loads(grafo._marcador().read_text(encoding="utf-8"))
            arquivos = marcador.get("arquivos", {})
            conteudo_grafo = json.loads(grafo._grafo().read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, AttributeError, TypeError, grafo.GrafoErro) as exc:
            return [], [f"Graphify inválido; sinais estruturais ignorados: {exc}"], False
        if not isinstance(arquivos, dict) or not isinstance(conteudo_grafo.get("nodes"), list):
            return [], ["Graphify não possui marcador/nós no formato esperado."], False
    else:
        try:
            arquivos = grafo._arquivos()
        except OSError as exc:
            return [], [f"Código local não pôde ser lido; busca ignorada: {exc}"], False
        conteudo_grafo = {"nodes": []}

    base = Path(raiz())
    fontes: dict[str, tuple[list[str], str]] = {}
    for rel, digest in sorted(arquivos.items()):
        caminho = (base / rel).resolve()
        if not caminho.is_relative_to(base.resolve()) or not caminho.is_file():
            continue
        try:
            bruto = caminho.read_bytes()
            texto = bruto.decode("utf-8", errors="replace")
        except OSError:
            continue
        atual = hashlib.sha256(bruto).hexdigest()
        if grafo_fresco and atual != digest:
            continue
        fontes[rel] = (texto.splitlines(), atual)

    candidatos: dict[tuple[str, int], dict] = {}
    for rel, (linhas, digest) in fontes.items():
        linha, score = _melhor_linha(linhas, pergunta)
        if score <= 0:
            continue
        candidatos[(rel, linha)] = {
            "source_uri": f"{rel}#L{linha}",
            "source_sha256": digest,
            "no_id": None,
            "trecho": _trecho_codigo(linhas, linha),
            "estrategias": ["literal-codigo"],
            "_score": score,
        }

    for no in conteudo_grafo.get("nodes", []):
        if not isinstance(no, dict):
            continue
        rel = _relativo_codigo(no.get("source_file"), arquivos)
        if not rel or rel not in fontes:
            continue
        estrutural = _pontuacao(pergunta, _descricao_no(no))
        if estrutural <= 0:
            continue
        linhas, digest = fontes[rel]
        linha = _linha_no(no) or _melhor_linha(linhas, pergunta)[0]
        linha = max(1, min(linha, max(1, len(linhas))))
        chave = (rel, linha)
        existente = candidatos.get(chave)
        if existente:
            existente["_score"] += estrutural + 2.0
            existente["estrategias"] = sorted(set(existente["estrategias"] + ["estrutural"]))
            if existente["no_id"] is None and no.get("id") is not None:
                existente["no_id"] = str(no["id"])
            continue
        candidatos[chave] = {
            "source_uri": f"{rel}#L{linha}",
            "source_sha256": digest,
            "no_id": str(no.get("id")) if no.get("id") is not None else None,
            "trecho": _trecho_codigo(linhas, linha),
            "estrategias": ["estrutural"],
            "_score": estrutural + 2.0,
        }
    return list(candidatos.values()), avisos, not ativo or grafo_fresco


@lru_cache(maxsize=128)
def _commit_da_fonte(base: str, rel: str, source_sha256: str,
                     head: str | None) -> str | None:
    if not head:
        return None
    try:
        conteudo = subprocess.run(
            ["git", "-C", base, "show", f"{head}:{rel}"],
            capture_output=True, timeout=15,
        )
        if conteudo.returncode != 0:
            return None
        if hashlib.sha256(conteudo.stdout).hexdigest() != source_sha256:
            return None
        return head
    except (OSError, subprocess.TimeoutExpired):
        return None


def _head_atual(base: str) -> str | None:
    try:
        commit = subprocess.run(
            ["git", "-C", base, "rev-parse", "HEAD"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
        )
        return commit.stdout.strip() if commit.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _confirmar_fragmento(fragmento: dict, head: str | None) -> dict:
    source_uri = str(fragmento.get("source_uri") or "")
    rel, separador, ancora = source_uri.partition("#")
    base = Path(raiz()).resolve()
    caminho = (base / rel).resolve()
    if separador != "#" or not ancora or not caminho.is_relative_to(base) or not caminho.is_file():
        raise ContextoErro(f"fragmento aponta para fonte inválida: `{source_uri}`")
    try:
        bruto = caminho.read_bytes()
        texto = bruto.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    except (OSError, UnicodeDecodeError) as exc:
        raise ContextoErro(f"não foi possível reler `{source_uri}`: {exc}") from exc
    digest = hashlib.sha256(bruto).hexdigest()
    if digest != fragmento.get("source_sha256"):
        raise ContextoErro(f"hash da fonte divergiu para `{source_uri}`")
    corpo = fragmentos._sem_frontmatter(texto)
    ancoras = {c["ancora"] for c in fragmentos._cabecalhos(corpo)}
    if ancora not in ancoras:
        raise ContextoErro(f"âncora `{ancora}` não existe mais em `{rel}`")
    conteudo_sha = hashlib.sha256(str(fragmento["texto"]).encode("utf-8")).hexdigest()
    if conteudo_sha != fragmento.get("conteudo_sha256"):
        raise ContextoErro(f"hash do fragmento divergiu para `{source_uri}`")
    return {
        "source_uri": source_uri,
        "source_commit": _commit_da_fonte(str(base), rel, digest, head),
        "source_sha256": digest,
        "doc_id": fragmento["doc_id"],
        "doc_tipo": fragmento["doc_tipo"],
        "status": fragmento["doc_status"],
        "classificacao": fragmento["classificacao"],
        "audience": fragmento["audience"],
        "produtos": fragmento["produtos"],
        "tenants": fragmento["tenants"],
        "fragment_id": fragmento["fragment_id"],
        "conteudo_sha256": conteudo_sha,
        "trecho": fragmento["texto"],
        "truncado": False,
        "estrategias": sorted(set(fragmento.get("_estrategias", []))),
        "pontuacao": round(float(fragmento.get("_score", 0.0)), 6),
    }


def _estimar_tokens(texto: str) -> int:
    return max(1, math.ceil(len(re.findall(r"\S+", texto)) * 1.5))


def _recortar(item: dict, limite: int) -> tuple[dict, int] | None:
    custo = _estimar_tokens(item["trecho"])
    if custo <= limite:
        return item, custo
    max_palavras = max(0, math.floor(limite / 1.5) - 1)
    if max_palavras < 8:
        return None
    unidades = re.findall(r"\S+\s*", item["trecho"])
    item = dict(item)
    item["trecho"] = "".join(unidades[:max_palavras]).rstrip() + " …"
    item["truncado"] = True
    return item, _estimar_tokens(item["trecho"])


def construir(pergunta: object, perfil: object, max_tokens: int | None = None,
              produto: object = None, tenant: object = None) -> dict:
    if not isinstance(pergunta, str) or not pergunta.strip():
        raise ContextoErro("a pergunta precisa ser texto não vazio")
    pergunta = pergunta.strip()
    if len(pergunta) > 4000 or len(_tokens(pergunta)) > 500:
        raise ContextoErro("a pergunta excede o limite de 500 termos")
    if not isinstance(perfil, str) or not perfil.strip():
        raise ContextoErro("o perfil precisa ser texto não vazio e explícito")
    perfil = perfil.strip()
    if perfil not in PERFIS:
        raise ContextoErro(f"perfil desconhecido: `{perfil}`")
    try:
        produto_escopo, tenant_escopo = seguranca.normalizar_escopo(
            perfil, produto, tenant
        )
    except seguranca.SegurancaErro as exc:
        raise ContextoErro(str(exc)) from exc
    orcamento = max_tokens if max_tokens is not None else _inteiro(
        "max_tokens", 2048, 64, 32768
    )
    if isinstance(orcamento, bool) or not isinstance(orcamento, int) or not 64 <= orcamento <= 32768:
        raise ContextoErro("`max_tokens` precisa ser inteiro entre 64 e 32768")
    max_fontes = _inteiro("max_fontes", 8, 1, 100)
    max_codigo = _inteiro("max_codigo", 5, 0, 100)

    manifesto = _carregar_manifesto()
    candidatos_docs: list[dict] = []
    for original in fragmentos.consultaveis(manifesto):
        if not _permitido(original, perfil, produto_escopo, tenant_escopo):
            continue
        item = dict(original)
        item["_score"] = _pontuacao(
            pergunta, f"{item['source_uri']} {item['doc_id']} {item['texto']}"
        )
        item["_estrategias"] = ["literal"] if item["_score"] > 0 else []
        candidatos_docs.append(item)

    if perfil in seguranca.PERFIS_COM_ESCOPO:
        sinais, avisos, semantico_fresco = {}, [
            "Consulta de cliente não foi enviada ao Hindsight; recuperação local com escopo."
        ], True
    else:
        sinais, avisos, semantico_fresco = _sinais_semanticos(pergunta, orcamento)
    fontes_permitidas = {
        item["source_uri"].split("#", 1)[0] for item in candidatos_docs
    }
    sinais = {rel: fatos for rel, fatos in sinais.items() if rel in fontes_permitidas}
    for item in candidatos_docs:
        rel = item["source_uri"].split("#", 1)[0]
        if rel in sinais:
            item["_score"] += max(
                base + _pontuacao(fato, item["texto"])
                for base, fato in sinais[rel]
            )
            item["_estrategias"].append("semantica")
    candidatos_docs = [item for item in candidatos_docs if item["_score"] > 0]

    codigo, avisos_codigo, grafo_fresco = _candidatos_codigo(
        pergunta, bool(PERFIS[perfil]["codigo"])
    )
    avisos.extend(avisos_codigo)

    # Conteúdo igual aparece uma vez; a maior pontuação e o desempate lexical vencem.
    unicos: dict[str, dict] = {}
    for item in candidatos_docs:
        chave = item["conteudo_sha256"]
        anterior = unicos.get(chave)
        if anterior is None or (-item["_score"], item["source_uri"]) < (
            -anterior["_score"], anterior["source_uri"]
        ):
            unicos[chave] = item
    ordenados_docs = sorted(
        unicos.values(), key=lambda item: (-item["_score"], item["source_uri"], item["fragment_id"])
    )[:max_fontes]
    ordenados_codigo = sorted(
        codigo, key=lambda item: (-item["_score"], item["source_uri"], str(item["no_id"]))
    )[:max_codigo]

    head = _head_atual(str(Path(raiz()).resolve()))
    combinados = [
        ("fontes", _confirmar_fragmento(item, head), item["_score"]) for item in ordenados_docs
    ] + [("codigo", {
        **{k: v for k, v in item.items() if not k.startswith("_")},
        "conteudo_sha256": hashlib.sha256(item["trecho"].encode("utf-8")).hexdigest(),
        "truncado": False,
        "pontuacao": round(float(item["_score"]), 6),
    }, item["_score"]) for item in ordenados_codigo]
    combinados.sort(key=lambda valor: (-valor[2], 0 if valor[0] == "fontes" else 1,
                                       valor[1]["source_uri"]))

    saida_fontes: list[dict] = []
    saida_codigo: list[dict] = []
    consumidos = 0
    for tipo, item, _ in combinados:
        ajustado = _recortar(item, orcamento - consumidos)
        if ajustado is None:
            continue
        pronto, custo = ajustado
        consumidos += custo
        (saida_fontes if tipo == "fontes" else saida_codigo).append(pronto)
    if not saida_fontes and not saida_codigo:
        avisos.append(
            "Cobertura ausente: nenhuma fonte atual, permitida e no escopo respondeu à pergunta."
        )

    estrategias = sorted({
        estrategia
        for item in [*saida_fontes, *saida_codigo]
        for estrategia in item.get("estrategias", [])
    })
    return {
        "schema": SCHEMA,
        "projeto": str(manifesto["projeto"]),
        "pergunta": pergunta,
        "perfil": perfil,
        "escopo": {"produto": produto_escopo, "tenant": tenant_escopo},
        "cobertura": "confirmada" if saida_fontes or saida_codigo else "ausente",
        "frescor": "confirmado" if semantico_fresco and grafo_fresco else "parcial",
        "orcamento_tokens": orcamento,
        "tokens_estimados": consumidos,
        "estrategias": estrategias,
        "comparacao_sombra": {
            "documentos_semanticos": len(sinais),
            "fragmentos_ranqueados": len(ordenados_docs),
            "fontes_documentais_entregues": len(saida_fontes),
            "migracao_hindsight_liberada": False,
        },
        "fontes": saida_fontes,
        "codigo": saida_codigo,
        "avisos": list(dict.fromkeys(avisos)),
        # Este gateway é estritamente read-only. Perfil descreve visibilidade, não
        # concede capacidade operacional ao modelo chamador.
        "acoes_permitidas": [],
    }


def _argumentos_contexto(
    payload: object,
) -> tuple[object, object, int | None, object, object]:
    """Aplica no transporte o mesmo contrato estrito publicado no inputSchema."""
    if not isinstance(payload, dict):
        raise ContextoErro("os argumentos precisam ser um objeto")
    extras = sorted(set(payload) - {
        "pergunta", "perfil", "max_tokens", "produto", "tenant"
    })
    if extras:
        raise ContextoErro("argumento(s) desconhecido(s): " + ", ".join(extras))
    max_tokens = payload.get("max_tokens")
    if "max_tokens" in payload and (
        isinstance(max_tokens, bool) or not isinstance(max_tokens, int)
    ):
        raise ContextoErro("`max_tokens` precisa ser inteiro entre 64 e 32768")
    return (
        payload.get("pergunta"), payload.get("perfil"), max_tokens,
        payload.get("produto"), payload.get("tenant"),
    )


@lru_cache(maxsize=1)
def schema_contexto() -> dict:
    caminho = Path(__file__).resolve().parent / "schemas/contexto-v2.schema.json"
    return json.loads(caminho.read_text(encoding="utf-8"))


def _meta_servidor() -> dict:
    return {
        "io.modelcontextprotocol/protocolVersion": MCP_PROTOCOL,
        "io.modelcontextprotocol/serverInfo": {
            "name": "memoria-evolutiva",
            "version": __version__,
        },
    }


def _ferramenta_mcp() -> dict:
    return {
        "name": "memoria_contexto",
        "title": "Memória verificável do projeto",
        "description": (
            "Recupera contexto read-only com fontes atuais, hashes e perfil explícito."
        ),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "pergunta": {"type": "string", "minLength": 1, "maxLength": 4000},
                "perfil": {"type": "string", "enum": sorted(PERFIS)},
                "max_tokens": {"type": "integer", "minimum": 64, "maximum": 32768},
                "produto": {"type": "string", "pattern": "^[a-z0-9][a-z0-9._-]{0,63}$"},
                "tenant": {"type": "string", "pattern": "^[a-z0-9][a-z0-9._-]{0,63}$"},
            },
            "required": ["pergunta", "perfil"],
            "allOf": [{
                "if": {
                    "properties": {
                        "perfil": {"enum": sorted(seguranca.PERFIS_COM_ESCOPO)}
                    },
                    "required": ["perfil"],
                },
                "then": {"required": ["produto", "tenant"]},
            }],
        },
        "outputSchema": schema_contexto(),
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    }


def processar_mcp(mensagem: object) -> dict | None:
    if not isinstance(mensagem, dict) or mensagem.get("jsonrpc") != "2.0":
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid Request"}}
    identificador = mensagem.get("id")
    metodo = mensagem.get("method")
    if identificador is None:
        return None
    if metodo in {"initialize", "server/discover"}:
        versao = MCP_PROTOCOL
        if metodo == "initialize" and isinstance(mensagem.get("params"), dict):
            solicitada = mensagem["params"].get("protocolVersion")
            if solicitada in {"2025-06-18", "2025-11-25", MCP_PROTOCOL}:
                versao = str(solicitada)
        return {
            "jsonrpc": "2.0", "id": identificador,
            "result": {
                "protocolVersion": versao,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "memoria-evolutiva", "version": __version__},
                "instructions": (
                    "Memória de projeto estritamente read-only. Antes da primeira consulta, "
                    "execute o canary do cliente. Use perfil explícito e sustente afirmações "
                    "somente nas fontes atuais devolvidas por memoria_contexto."
                ),
                "_meta": _meta_servidor(),
            },
        }
    if metodo == "ping":
        return {"jsonrpc": "2.0", "id": identificador, "result": {"_meta": _meta_servidor()}}
    if metodo == "tools/list":
        return {
            "jsonrpc": "2.0", "id": identificador,
            "result": {"tools": [_ferramenta_mcp()], "_meta": _meta_servidor()},
        }
    if metodo == "tools/call":
        parametros = mensagem.get("params")
        if not isinstance(parametros, dict) or parametros.get("name") != "memoria_contexto":
            return {"jsonrpc": "2.0", "id": identificador,
                    "error": {"code": -32602, "message": "Invalid tool name or parameters"}}
        try:
            pergunta, perfil, max_tokens, produto, tenant = _argumentos_contexto(
                parametros.get("arguments", {})
            )
            envelope = construir(pergunta, perfil, max_tokens, produto, tenant)
        except (ContextoErro, SystemExit) as exc:
            detalhe = str(exc) if isinstance(exc, ContextoErro) else "configuração do projeto inválida"
            return {
                "jsonrpc": "2.0", "id": identificador,
                "result": {
                    "content": [{"type": "text", "text": detalhe}],
                    "isError": True,
                    "_meta": _meta_servidor(),
                },
            }
        serializado = json.dumps(envelope, ensure_ascii=False, sort_keys=True)
        return {
            "jsonrpc": "2.0", "id": identificador,
            "result": {
                "content": [{"type": "text", "text": serializado}],
                "structuredContent": envelope,
                "isError": False,
                "_meta": _meta_servidor(),
            },
        }
    return {"jsonrpc": "2.0", "id": identificador,
            "error": {"code": -32601, "message": "Method not found"}}


def servir_stdio() -> int:
    for linha in sys.stdin.buffer:
        if len(linha) > 1_048_576:
            resposta = {"jsonrpc": "2.0", "id": None,
                        "error": {"code": -32600, "message": "Request too large"}}
        else:
            try:
                resposta = processar_mcp(json.loads(linha))
            except json.JSONDecodeError:
                resposta = {"jsonrpc": "2.0", "id": None,
                            "error": {"code": -32700, "message": "Parse error"}}
        if resposta is not None:
            sys.stdout.write(json.dumps(resposta, ensure_ascii=False, sort_keys=True) + "\n")
            sys.stdout.flush()
    return 0


def _opcoes(argv: list[str]) -> tuple[dict[str, str | bool], list[str]]:
    opcoes: dict[str, str | bool] = {}
    invalidos: list[str] = []
    for argumento in argv:
        match = re.match(r"^--([a-z-]+)(?:=(.*))?$", argumento)
        if not match:
            invalidos.append(argumento)
            continue
        opcoes[match.group(1)] = match.group(2) if match.group(2) is not None else True
    return opcoes, invalidos


def main(argv: list[str]) -> int:
    if argv and argv[0] == "mcp":
        if len(argv) != 1:
            print("`memoria contexto mcp` não aceita opções.", file=sys.stderr)
            return 2
        return servir_stdio()
    if argv and argv[0] == "http":
        from . import contexto_http
        return contexto_http.main(argv[1:])

    opcoes, invalidos = _opcoes(argv)
    desconhecidas = sorted(set(opcoes) - {
        "pergunta", "perfil", "max-tokens", "produto", "tenant", "json"
    })
    if invalidos or desconhecidas:
        print("Opção desconhecida: " + ", ".join([*invalidos, *desconhecidas]), file=sys.stderr)
        return 2
    pergunta = opcoes.get("pergunta")
    perfil = opcoes.get("perfil")
    if not isinstance(pergunta, str) or not isinstance(perfil, str):
        print(
            "Uso: memoria contexto --pergunta=TEXTO --perfil=PERFIL "
            "[--produto=ID --tenant=ID] [--max-tokens=N] --json",
            file=sys.stderr,
        )
        return 2
    max_tokens: int | None = None
    if "max-tokens" in opcoes:
        try:
            max_tokens = int(str(opcoes["max-tokens"]))
        except ValueError:
            print("`--max-tokens` precisa ser inteiro.", file=sys.stderr)
            return 2
    try:
        envelope = construir(
            pergunta, perfil, max_tokens, opcoes.get("produto"), opcoes.get("tenant")
        )
    except ContextoErro as exc:
        print(f"ERRO — {exc}", file=sys.stderr)
        return 1
    compacto = bool(opcoes.get("json"))
    print(json.dumps(
        envelope, ensure_ascii=False, sort_keys=True,
        indent=None if compacto else 2,
        separators=(",", ":") if compacto else None,
    ))
    return 0
