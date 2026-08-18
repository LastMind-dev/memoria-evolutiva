"""Avaliação versionada e determinística do gateway de contexto.

O corpus é canônico; relatório e manifesto são derivados. A linha de base só muda por
``memoria avaliar medir`` e nunca é promovida automaticamente por uma execução comum.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
import unicodedata
from pathlib import Path

from . import contexto, fragmentos, seguranca
from .lib import config, raiz, relativo, titulo


SCHEMA = 1
CATEGORIAS = {"engenharia", "atendimento", "automacao"}
METRICAS_MAIORES = (
    "hit_1", "hit_3", "cobertura_citacao", "cobertura_resposta", "negativos_ok",
)
METRICAS_MENORES = ("sem_fonte",)


class AvaliacaoErro(RuntimeError):
    pass


_ULTIMA_FALHA: str | None = None


def _sha_bytes(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


def _sha_obj(valor: object) -> str:
    return _sha_bytes(json.dumps(
        valor, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8"))


def _cfg() -> dict:
    valor = config().get("avaliacao", {})
    if not isinstance(valor, dict) or valor.get("ativo") is not True:
        raise AvaliacaoErro(
            "avaliação ausente ou desativada; rode `memoria instalar` com a versão atual"
        )
    caminhos = {
        "corpus": "docs/avaliacao/casos-rag-v1.json",
        "baseline": "docs/politicas/baseline-rag-v1.json",
        "relatorio": "docs/gerado/relatorio-avaliacao-rag-v1.json",
        "manifesto": "docs/gerado/manifesto-avaliacao-rag-v1.json",
    }
    for chave, esperado in caminhos.items():
        if valor.get(chave) != esperado:
            raise AvaliacaoErro(f"`avaliacao.{chave}` precisa ser `{esperado}`")
    for chave, padrao in (
        ("min_hit_1", 0.5), ("min_hit_3", 1.0),
        ("min_cobertura_citacao", 1.0), ("min_cobertura_resposta", 1.0),
        ("max_sem_fonte", 0.0), ("min_negativos_ok", 1.0),
        ("regressao_maxima", 0.0),
    ):
        item = valor.get(chave, padrao)
        if (isinstance(item, bool) or not isinstance(item, (int, float))
                or not 0 <= float(item) <= 1):
            raise AvaliacaoErro(f"`avaliacao.{chave}` precisa ser número entre 0 e 1")
    usos = valor.get("min_usos_promocao", 2)
    if isinstance(usos, bool) or not isinstance(usos, int) or not 1 <= usos <= 100:
        raise AvaliacaoErro(
            "`avaliacao.min_usos_promocao` precisa ser inteiro entre 1 e 100"
        )
    return valor


def _caminho(chave: str, padrao: str) -> Path:
    base = Path(raiz()).resolve()
    valor = _cfg().get(chave, padrao)
    if not isinstance(valor, str) or not valor.strip():
        raise AvaliacaoErro(f"`avaliacao.{chave}` precisa ser caminho não vazio")
    destino = (base / valor.strip("/")).resolve()
    if destino == base or not destino.is_relative_to(base):
        raise AvaliacaoErro(f"`avaliacao.{chave}` precisa ficar dentro do projeto")
    return destino


def corpus_path() -> Path:
    return _caminho("corpus", "docs/avaliacao/casos-rag-v1.json")


def baseline_path() -> Path:
    return _caminho("baseline", "docs/politicas/baseline-rag-v1.json")


def relatorio_path() -> Path:
    return _caminho("relatorio", "docs/gerado/relatorio-avaliacao-rag-v1.json")


def manifesto_path() -> Path:
    return _caminho("manifesto", "docs/gerado/manifesto-avaliacao-rag-v1.json")


def _serializar(valor: dict) -> str:
    return json.dumps(valor, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _gravar_atomico(destino: Path, valor: dict) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", prefix=f".{destino.name}.",
            suffix=".tmp", dir=destino.parent, delete=False,
        ) as arquivo:
            arquivo.write(_serializar(valor))
            arquivo.flush()
            os.fsync(arquivo.fileno())
            temporario = Path(arquivo.name)
        os.replace(temporario, destino)
        temporario = None
    finally:
        if temporario is not None:
            temporario.unlink(missing_ok=True)


def _lista_texto(caso: dict, chave: str) -> list[str]:
    valor = caso.get(chave, [])
    if (not isinstance(valor, list)
            or any(not isinstance(item, str) or not item.strip() for item in valor)
            or len(valor) != len(set(valor))):
        raise AvaliacaoErro(f"caso `{caso.get('id')}`: `{chave}` precisa ser lista única de textos")
    return valor


def _validar_fontes(caso: dict, chave: str) -> list[str]:
    fontes = _lista_texto(caso, chave)
    for fonte in fontes:
        caminho = fonte.rstrip("/")
        if ("\\" in fonte or "#" in fonte or fonte.startswith("/")
                or not caminho or ".." in Path(caminho).parts):
            raise AvaliacaoErro(
                f"caso `{caso.get('id')}`: `{chave}` contém caminho inválido"
            )
    return fontes


def _carregar_corpus() -> tuple[dict, str]:
    caminho = corpus_path()
    try:
        bruto = caminho.read_bytes()
        dados = json.loads(bruto.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AvaliacaoErro(f"corpus de avaliação inválido: {exc}") from exc
    if not isinstance(dados, dict) or dados.get("schema") != SCHEMA:
        raise AvaliacaoErro("corpus de avaliação precisa seguir o schema 1")
    if dados.get("projeto") != config().get("projeto"):
        raise AvaliacaoErro("projeto do corpus de avaliação diverge do padrao.json")
    casos = dados.get("casos")
    if not isinstance(casos, list) or len(casos) < 3:
        raise AvaliacaoErro("corpus precisa ter ao menos três casos")
    ids: set[str] = set()
    categorias: set[str] = set()
    positivos_por_categoria: set[str] = set()
    negativos_por_categoria: set[str] = set()
    for caso in casos:
        if not isinstance(caso, dict):
            raise AvaliacaoErro("cada caso do corpus precisa ser objeto")
        id_ = caso.get("id")
        if not isinstance(id_, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", id_):
            raise AvaliacaoErro("caso de avaliação possui id inválido")
        if id_ in ids:
            raise AvaliacaoErro(f"id de caso duplicado: `{id_}`")
        ids.add(id_)
        categoria = caso.get("categoria")
        perfil = caso.get("perfil")
        if categoria not in CATEGORIAS:
            raise AvaliacaoErro(f"caso `{id_}` possui categoria inválida")
        if perfil not in contexto.PERFIS:
            raise AvaliacaoErro(f"caso `{id_}` possui perfil inválido")
        perfis_categoria = {
            "engenharia": {"engenharia-leitura", "engenharia-documentacao"},
            "automacao": {"automacao-codigo"},
            "atendimento": {"atendimento", "operacao-assistida"},
        }
        if perfil not in perfis_categoria[str(categoria)]:
            raise AvaliacaoErro(
                f"caso `{id_}` usa perfil incompatível com a categoria `{categoria}`"
            )
        categorias.add(str(categoria))
        pergunta = caso.get("pergunta")
        resposta = caso.get("resposta_esperada")
        if not isinstance(pergunta, str) or not pergunta.strip() or len(pergunta) > 4000:
            raise AvaliacaoErro(f"caso `{id_}` possui pergunta inválida")
        if not isinstance(resposta, str) or not resposta.strip():
            raise AvaliacaoErro(f"caso `{id_}` precisa declarar `resposta_esperada`")
        fontes = _validar_fontes(caso, "fontes_esperadas")
        _validar_fontes(caso, "fontes_proibidas")
        termos = _lista_texto(caso, "termos_esperados")
        sem_fonte = caso.get("espera_sem_fonte", False)
        if not isinstance(sem_fonte, bool):
            raise AvaliacaoErro(f"caso `{id_}`: `espera_sem_fonte` precisa ser booleano")
        if sem_fonte and (fontes or termos):
            raise AvaliacaoErro(f"caso negativo `{id_}` não pode exigir fonte ou termo")
        if not sem_fonte and (not fontes or not termos):
            raise AvaliacaoErro(f"caso positivo `{id_}` precisa exigir fontes e termos")
        (negativos_por_categoria if sem_fonte else positivos_por_categoria).add(
            str(categoria)
        )
        if perfil in seguranca.PERFIS_COM_ESCOPO:
            for chave in ("produto", "tenant"):
                if not isinstance(caso.get(chave), str) or not caso[chave].strip():
                    raise AvaliacaoErro(f"caso `{id_}` exige `{chave}` explícito")
    if categorias != CATEGORIAS:
        raise AvaliacaoErro(
            "corpus precisa separar casos de engenharia, atendimento e automacao"
        )
    if not {"engenharia", "automacao"}.issubset(positivos_por_categoria):
        raise AvaliacaoErro(
            "corpus precisa ter caso positivo de engenharia e de automacao"
        )
    if "atendimento" not in negativos_por_categoria:
        raise AvaliacaoErro(
            "corpus precisa ter caso negativo de atendimento para medir isolamento"
        )
    return dados, _sha_bytes(bruto)


def _normalizar(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto.casefold())
    return " ".join("".join(
        caractere for caractere in base if not unicodedata.combining(caractere)
    ).split())


def _fonte_base(valor: object) -> str:
    return str(valor or "").replace("\\", "/").split("#", 1)[0]


def _proibida(fonte: str, proibidas: list[str]) -> bool:
    return any(
        fonte == item.rstrip("/") or fonte.startswith(item.rstrip("/") + "/")
        for item in proibidas
    )


def _executar_caso(caso: dict) -> dict:
    envelope = contexto.construir(
        caso["pergunta"], caso["perfil"],
        produto=caso.get("produto"), tenant=caso.get("tenant"),
    )
    itens_fontes = list(envelope["fontes"])
    fontes = [_fonte_base(item.get("source_uri")) for item in itens_fontes]
    fontes = list(dict.fromkeys(fonte for fonte in fontes if fonte))
    esperadas = caso.get("fontes_esperadas", [])
    proibidas = caso.get("fontes_proibidas", [])
    negativas = bool(caso.get("espera_sem_fonte", False))
    hit_1 = bool(esperadas and fontes and fontes[0] in esperadas)
    hit_3 = bool(set(fontes[:3]) & set(esperadas)) if esperadas else False
    citadas = sorted(set(fontes) & set(esperadas))
    vazou = sorted(fonte for fonte in fontes if _proibida(fonte, proibidas))
    texto = _normalizar("\n".join(
        str(item.get("trecho") or "") for item in itens_fontes
        if _fonte_base(item.get("source_uri")) in esperadas
    ))
    termos = caso.get("termos_esperados", [])
    termos_encontrados = [termo for termo in termos if _normalizar(termo) in texto]
    cobertura_resposta = len(termos_encontrados) / len(termos) if termos else None
    if negativas:
        ok = not fontes and not vazou
    else:
        ok = (
            hit_3 and len(citadas) == len(esperadas)
            and cobertura_resposta == 1.0 and not vazou
        )
    return {
        "id": caso["id"],
        "categoria": caso["categoria"],
        "perfil": caso["perfil"],
        "espera_sem_fonte": negativas,
        "fontes_esperadas": esperadas,
        "fontes_retornadas": fontes,
        "fontes_top_3": fontes[:3],
        "fontes_citadas": citadas,
        "fontes_proibidas_retornadas": vazou,
        "termos_esperados": termos,
        "termos_encontrados": termos_encontrados,
        "hit_1": hit_1,
        "hit_3": hit_3,
        "cobertura_citacao": (
            round(len(citadas) / len(esperadas), 6) if esperadas else None
        ),
        "cobertura_resposta": (
            round(cobertura_resposta, 6) if cobertura_resposta is not None else None
        ),
        "sem_fonte": not fontes,
        "ok": ok,
    }


def _metricas(casos: list[dict]) -> dict:
    positivos = [caso for caso in casos if not caso["espera_sem_fonte"]]
    negativos = [caso for caso in casos if caso["espera_sem_fonte"]]
    total_fontes = sum(len(caso["fontes_esperadas"]) for caso in positivos)
    citadas = sum(len(caso["fontes_citadas"]) for caso in positivos)
    total_termos = sum(len(caso["termos_esperados"]) for caso in positivos)
    termos = sum(len(caso["termos_encontrados"]) for caso in positivos)
    return {
        "casos": len(casos),
        "positivos": len(positivos),
        "negativos": len(negativos),
        "hit_1": round(sum(caso["hit_1"] for caso in positivos) / len(positivos), 6)
        if positivos else None,
        "hit_3": round(sum(caso["hit_3"] for caso in positivos) / len(positivos), 6)
        if positivos else None,
        "cobertura_citacao": round(citadas / total_fontes, 6) if total_fontes else None,
        "cobertura_resposta": round(termos / total_termos, 6) if total_termos else None,
        "sem_fonte": round(sum(caso["sem_fonte"] for caso in positivos) / len(positivos), 6)
        if positivos else None,
        "negativos_ok": round(sum(caso["ok"] for caso in negativos) / len(negativos), 6)
        if negativos else None,
    }


def _agrupar(casos: list[dict], chave: str) -> dict[str, dict]:
    valores = sorted({str(caso[chave]) for caso in casos})
    return {
        valor: _metricas([caso for caso in casos if caso[chave] == valor])
        for valor in valores
    }


def _perfil_rag() -> dict:
    manifesto = fragmentos._manifesto_path()
    try:
        dados = json.loads(manifesto.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AvaliacaoErro(f"manifesto RAG inválido: {exc}") from exc
    rag = config().get("rag", {})
    return {
        "algoritmo": dados.get("algoritmo"),
        "perfil_fingerprint": dados.get("perfil_fingerprint"),
        "embedding_provedor": rag.get("embedding_provedor"),
        "embedding_modelo": rag.get("embedding_modelo"),
    }


def _relatorio_base() -> dict:
    if fragmentos.verificar(silencioso=True) != 0:
        raise AvaliacaoErro("manifesto RAG está ausente ou defasado")
    corpus, corpus_sha = _carregar_corpus()
    resultados = [_executar_caso(caso) for caso in corpus["casos"]]
    usos: dict[str, dict] = {}
    for caso in resultados:
        for fonte in caso["fontes_citadas"]:
            item = usos.setdefault(fonte, {"fonte": fonte, "casos": [], "hits_3": 0})
            item["casos"].append(caso["id"])
            item["hits_3"] += int(fonte in caso["fontes_top_3"])
    minimo_usos = _cfg().get("min_usos_promocao", 2)
    promocoes = [
        {**item, "casos": sorted(item["casos"])} for item in usos.values()
        if len(item["casos"]) >= minimo_usos and item["hits_3"] == len(item["casos"])
    ]
    return {
        "schema": SCHEMA,
        "projeto": str(config()["projeto"]),
        "corpus": relativo(str(corpus_path())),
        "corpus_sha256": corpus_sha,
        "perfil_rag": _perfil_rag(),
        "metricas": {
            "global": _metricas(resultados),
            "por_perfil": _agrupar(resultados, "perfil"),
            "por_categoria": _agrupar(resultados, "categoria"),
        },
        "casos": resultados,
        "promocoes_candidatas": sorted(promocoes, key=lambda item: item["fonte"]),
    }


def _limites_absolutos() -> dict[str, float]:
    cfg = _cfg()
    return {
        "hit_1": float(cfg.get("min_hit_1", 0.5)),
        "hit_3": float(cfg.get("min_hit_3", 1.0)),
        "cobertura_citacao": float(cfg.get("min_cobertura_citacao", 1.0)),
        "cobertura_resposta": float(cfg.get("min_cobertura_resposta", 1.0)),
        "sem_fonte": float(cfg.get("max_sem_fonte", 0.0)),
        "negativos_ok": float(cfg.get("min_negativos_ok", 1.0)),
    }


def _baseline_de(relatorio: dict) -> dict:
    base = {
        "schema": SCHEMA,
        "projeto": relatorio["projeto"],
        "corpus_sha256": relatorio["corpus_sha256"],
        "perfil_rag": relatorio["perfil_rag"],
        "metricas": relatorio["metricas"],
    }
    base["assinatura"] = _sha_obj(base)
    return base


def _carregar_baseline() -> dict:
    caminho = baseline_path()
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AvaliacaoErro(
            f"baseline RAG ausente ou inválido: {exc}; rode `memoria avaliar medir`"
        ) from exc
    campos_baseline = {
        "schema", "projeto", "corpus_sha256", "perfil_rag", "metricas", "assinatura",
    }
    if (not isinstance(dados, dict) or dados.get("schema") != SCHEMA
            or set(dados) != campos_baseline):
        raise AvaliacaoErro("baseline RAG não segue o schema 1")
    assinatura = dados.get("assinatura")
    sem_assinatura = {chave: valor for chave, valor in dados.items() if chave != "assinatura"}
    if assinatura != _sha_obj(sem_assinatura):
        raise AvaliacaoErro("assinatura do baseline RAG diverge")
    perfil_rag = dados.get("perfil_rag")
    campos_perfil = {
        "algoritmo", "perfil_fingerprint", "embedding_provedor", "embedding_modelo",
    }
    if (dados.get("projeto") != config().get("projeto")
            or not re.fullmatch(r"[0-9a-f]{64}", str(dados.get("corpus_sha256") or ""))
            or not isinstance(perfil_rag, dict)
            or set(perfil_rag) != campos_perfil
            or any(not isinstance(perfil_rag.get(chave), str) or not perfil_rag[chave]
                   for chave in campos_perfil)
            or not re.fullmatch(r"[0-9a-f]{64}", perfil_rag["perfil_fingerprint"])
            or not isinstance(dados.get("metricas"), dict)
            or set(dados["metricas"]) != {"global", "por_perfil", "por_categoria"}
            or not isinstance(dados["metricas"].get("global"), dict)
            or not isinstance(dados["metricas"].get("por_perfil"), dict)
            or not isinstance(dados["metricas"].get("por_categoria"), dict)):
        raise AvaliacaoErro("estrutura do baseline RAG é inválida")
    por_perfil = dados["metricas"]["por_perfil"]
    por_categoria = dados["metricas"]["por_categoria"]
    if (len(por_perfil) < 3 or not set(por_perfil).issubset(contexto.PERFIS)
            or set(por_categoria) != CATEGORIAS):
        raise AvaliacaoErro("dimensões do baseline RAG são inválidas")
    grupos = [dados["metricas"]["global"]]
    grupos.extend(por_perfil.values())
    grupos.extend(por_categoria.values())
    if any(not isinstance(grupo, dict) for grupo in grupos):
        raise AvaliacaoErro("grupos de métricas do baseline são inválidos")
    campos_grupo = {
        "casos", "positivos", "negativos", *METRICAS_MAIORES, *METRICAS_MENORES,
    }
    for grupo in grupos:
        if set(grupo) != campos_grupo:
            raise AvaliacaoErro("grupo de métricas do baseline é ambíguo")
        contagens = [grupo[chave] for chave in ("casos", "positivos", "negativos")]
        if (any(isinstance(valor, bool) or not isinstance(valor, int) or valor < 0
                for valor in contagens)
                or grupo["positivos"] + grupo["negativos"] != grupo["casos"]):
            raise AvaliacaoErro("contagens do baseline são inválidas")
        for metrica in (*METRICAS_MAIORES, *METRICAS_MENORES):
            valor = grupo.get(metrica)
            if valor is None:
                continue
            if (isinstance(valor, bool) or not isinstance(valor, (int, float))
                    or not math.isfinite(float(valor)) or not 0 <= float(valor) <= 1):
                raise AvaliacaoErro(f"métrica `{metrica}` inválida no baseline")
        metricas_positivas = (
            "hit_1", "hit_3", "cobertura_citacao", "cobertura_resposta", "sem_fonte",
        )
        if any((grupo[metrica] is None) == (grupo["positivos"] > 0)
               for metrica in metricas_positivas):
            raise AvaliacaoErro("presença de métricas positivas diverge das contagens")
        if (grupo["negativos_ok"] is None) == (grupo["negativos"] > 0):
            raise AvaliacaoErro("presença de `negativos_ok` diverge das contagens")
    global_ = dados["metricas"]["global"]
    for dimensao in (por_perfil, por_categoria):
        for chave in ("casos", "positivos", "negativos"):
            if sum(grupo[chave] for grupo in dimensao.values()) != global_[chave]:
                raise AvaliacaoErro(f"agregação `{chave}` do baseline diverge do global")
    return dados


def _delta(atual: object, anterior: object) -> float | None:
    if not isinstance(atual, (int, float)) or isinstance(atual, bool):
        return None
    if not isinstance(anterior, (int, float)) or isinstance(anterior, bool):
        return None
    return round(float(atual) - float(anterior), 6)


def _aplicar_gate(relatorio: dict, baseline: dict | None) -> dict:
    erros: list[str] = []
    limites = _limites_absolutos()
    global_ = relatorio["metricas"]["global"]
    for metrica in METRICAS_MAIORES:
        valor = global_.get(metrica)
        if valor is None:
            erros.append(f"métrica global ausente: {metrica}")
        elif valor < limites[metrica]:
            erros.append(f"{metrica}={valor:.6f} abaixo de {limites[metrica]:.6f}")
    valor_sem_fonte = global_.get("sem_fonte")
    if valor_sem_fonte is None:
        erros.append("métrica global ausente: sem_fonte")
    elif valor_sem_fonte > limites["sem_fonte"]:
        erros.append(
            f"sem_fonte={valor_sem_fonte:.6f} acima de {limites['sem_fonte']:.6f}"
        )
    reprovados = [caso["id"] for caso in relatorio["casos"] if not caso["ok"]]
    if reprovados:
        erros.append("casos reprovados: " + ", ".join(reprovados))

    drift = {
        "baseline_sha256": None,
        "perfil_rag_alterado": False,
        "componentes_rag": {},
        "global": {},
        "por_perfil": {},
    }
    if baseline is not None:
        if baseline.get("projeto") != relatorio["projeto"]:
            erros.append("projeto do baseline diverge")
        if baseline.get("corpus_sha256") != relatorio["corpus_sha256"]:
            erros.append("corpus mudou; rode `memoria avaliar medir` deliberadamente")
        contagens = ("casos", "positivos", "negativos")
        for dimensao in ("global", "por_perfil", "por_categoria"):
            atual_dimensao = relatorio["metricas"][dimensao]
            anterior_dimensao = baseline["metricas"][dimensao]
            atuais = {"global": atual_dimensao} if dimensao == "global" else atual_dimensao
            anteriores = (
                {"global": anterior_dimensao} if dimensao == "global" else anterior_dimensao
            )
            assinatura_atual = {
                chave: tuple(grupo[item] for item in contagens)
                for chave, grupo in atuais.items()
            }
            assinatura_anterior = {
                chave: tuple(grupo[item] for item in contagens)
                for chave, grupo in anteriores.items()
            }
            if assinatura_atual != assinatura_anterior:
                erros.append(f"contagens da baseline divergem em {dimensao}")
        drift["baseline_sha256"] = _sha_bytes(_serializar(baseline).encode("utf-8"))
        drift["perfil_rag_alterado"] = baseline.get("perfil_rag") != relatorio["perfil_rag"]
        perfil_anterior = baseline.get("perfil_rag", {})
        for componente, atual in relatorio["perfil_rag"].items():
            anterior = perfil_anterior.get(componente)
            drift["componentes_rag"][componente] = {
                "anterior": anterior,
                "atual": atual,
                "alterado": anterior != atual,
            }
        regressao = float(_cfg().get("regressao_maxima", 0.0))
        anterior_global = baseline.get("metricas", {}).get("global", {})
        for metrica in (*METRICAS_MAIORES, *METRICAS_MENORES):
            delta = _delta(global_.get(metrica), anterior_global.get(metrica))
            drift["global"][metrica] = delta
            if delta is None:
                continue
            if metrica in METRICAS_MAIORES and delta < -regressao:
                erros.append(f"regressão global em {metrica}: {delta:.6f}")
            if metrica in METRICAS_MENORES and delta > regressao:
                erros.append(f"regressão global em {metrica}: +{delta:.6f}")
        perfis_anteriores = baseline.get("metricas", {}).get("por_perfil", {})
        for perfil, metricas in relatorio["metricas"]["por_perfil"].items():
            anterior = perfis_anteriores.get(perfil, {})
            deltas = {
                metrica: _delta(metricas.get(metrica), anterior.get(metrica))
                for metrica in (*METRICAS_MAIORES, *METRICAS_MENORES)
            }
            drift["por_perfil"][perfil] = deltas
            for metrica, delta in deltas.items():
                if delta is None:
                    continue
                if metrica in METRICAS_MAIORES and delta < -regressao:
                    erros.append(f"regressão em {perfil}.{metrica}: {delta:.6f}")
                if metrica in METRICAS_MENORES and delta > regressao:
                    erros.append(f"regressão em {perfil}.{metrica}: +{delta:.6f}")
    relatorio = dict(relatorio)
    relatorio["drift"] = drift
    relatorio["gate"] = {
        "aprovado": not erros,
        "limites": limites,
        "regressao_maxima": float(_cfg().get("regressao_maxima", 0.0)),
        "erros": erros,
    }
    sem_assinatura = {chave: valor for chave, valor in relatorio.items() if chave != "assinatura"}
    relatorio["assinatura"] = _sha_obj(sem_assinatura)
    return relatorio


def _manifesto(relatorio: dict) -> dict:
    base = {
        "schema": SCHEMA,
        "projeto": relatorio["projeto"],
        "corpus_sha256": relatorio["corpus_sha256"],
        "perfil_rag": relatorio["perfil_rag"],
        "metricas": relatorio["metricas"],
        "drift": relatorio["drift"],
        "gate": relatorio["gate"],
        "promocoes_candidatas": relatorio["promocoes_candidatas"],
        "relatorio_sha256": _sha_bytes(_serializar(relatorio).encode("utf-8")),
    }
    base["assinatura"] = _sha_obj(base)
    return base


def construir(com_baseline: bool = True) -> tuple[dict, dict]:
    relatorio = _relatorio_base()
    baseline = _carregar_baseline() if com_baseline else None
    relatorio = _aplicar_gate(relatorio, baseline)
    return relatorio, _manifesto(relatorio)


def medir(silencioso: bool = False) -> int:
    global _ULTIMA_FALHA
    try:
        base = _relatorio_base()
        preliminar = _aplicar_gate(base, None)
        if not preliminar["gate"]["aprovado"]:
            raise AvaliacaoErro(
                "não é permitido medir baseline reprovado: "
                + "; ".join(preliminar["gate"]["erros"])
            )
        baseline = _baseline_de(preliminar)
        relatorio = _aplicar_gate(base, baseline)
        manifesto = _manifesto(relatorio)
        _gravar_atomico(relatorio_path(), relatorio)
        _gravar_atomico(manifesto_path(), manifesto)
        # A baseline é a peça canônica desta operação; grave-a por último. Uma queda
        # antes daqui deixa derivados recusáveis, nunca uma nova linha de base parcial.
        _gravar_atomico(baseline_path(), baseline)
    except (AvaliacaoErro, contexto.ContextoErro, OSError, ValueError,
            TypeError, AttributeError, KeyError) as exc:
        _ULTIMA_FALHA = str(exc)
        if not silencioso:
            print(f"ERRO — baseline RAG não foi medido: {exc}")
        return 1
    if not silencioso:
        titulo("Avaliação RAG — baseline medido")
        print(f"  {relativo(str(baseline_path()))}")
        print(f"  {len(relatorio['casos'])} casos · gate aprovado")
    return 0


def gerar(silencioso: bool = False) -> int:
    global _ULTIMA_FALHA
    try:
        relatorio, manifesto = construir(com_baseline=True)
        _gravar_atomico(relatorio_path(), relatorio)
        _gravar_atomico(manifesto_path(), manifesto)
    except (AvaliacaoErro, contexto.ContextoErro, OSError, ValueError,
            TypeError, AttributeError, KeyError) as exc:
        _ULTIMA_FALHA = str(exc)
        if not silencioso:
            print(f"ERRO — avaliação RAG não foi gerada: {exc}")
        return 1
    if not silencioso:
        titulo("Avaliação RAG — evolução mensurada")
        print(f"  {len(relatorio['casos'])} casos · hit@1 {relatorio['metricas']['global']['hit_1']}")
        for erro in relatorio["gate"]["erros"]:
            print(f"  ERRO — {erro}")
    if not relatorio["gate"]["aprovado"]:
        _ULTIMA_FALHA = "; ".join(relatorio["gate"]["erros"])
        return 1
    return 0


def verificar(silencioso: bool = False) -> int:
    global _ULTIMA_FALHA
    try:
        relatorio, manifesto = construir(com_baseline=True)
        if relatorio_path().read_text(encoding="utf-8") != _serializar(relatorio):
            raise AvaliacaoErro("relatório RAG ausente ou defasado; rode `memoria avaliar gerar`")
        if manifesto_path().read_text(encoding="utf-8") != _serializar(manifesto):
            raise AvaliacaoErro("manifesto de avaliação ausente ou defasado")
        if not relatorio["gate"]["aprovado"]:
            raise AvaliacaoErro("catraca RAG reprovada: " + "; ".join(relatorio["gate"]["erros"]))
    except (AvaliacaoErro, contexto.ContextoErro, OSError, ValueError,
            TypeError, AttributeError, KeyError) as exc:
        _ULTIMA_FALHA = str(exc)
        if not silencioso:
            print(f"ERRO — avaliação RAG inválida: {exc}")
        return 1
    if not silencioso:
        titulo("Avaliação RAG — evolução mensurada")
        print(
            f"  íntegra: {len(relatorio['casos'])} casos · "
            f"hit@1 {relatorio['metricas']['global']['hit_1']} · "
            f"hit@3 {relatorio['metricas']['global']['hit_3']}"
        )
    return 0


def _saida_json(acao: str, rc: int) -> int:
    payload: dict = {"schema": SCHEMA, "acao": acao, "ok": rc == 0, "exit_code": rc}
    try:
        caminho = relatorio_path()
        if caminho.is_file():
            payload["relatorio"] = json.loads(caminho.read_text(encoding="utf-8"))
    except (AvaliacaoErro, OSError, json.JSONDecodeError):
        payload["relatorio"] = None
    if rc != 0:
        payload["erro"] = _ULTIMA_FALHA or "avaliação RAG reprovada"
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return rc


def main(argv: list[str]) -> int:
    global _ULTIMA_FALHA
    _ULTIMA_FALHA = None
    json_ = "--json" in argv
    argumentos = [item for item in argv if item != "--json"]
    acao = argumentos[0] if argumentos else "verificar"
    if len(argumentos) > 1 or acao not in {"medir", "gerar", "verificar", "status"}:
        if json_:
            print(json.dumps({
                "schema": SCHEMA, "acao": acao, "ok": False, "exit_code": 2,
                "erro": "uso: memoria avaliar [medir|gerar|verificar|status] [--json]",
            }, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        else:
            print("Uso: memoria avaliar [medir|gerar|verificar|status] [--json]")
        return 2
    funcao = medir if acao == "medir" else gerar if acao == "gerar" else verificar
    rc = funcao(silencioso=json_)
    return _saida_json(acao, rc) if json_ else rc
