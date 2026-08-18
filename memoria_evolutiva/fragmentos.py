"""Fragmentação determinística do acervo canônico para o RAG portátil.

O manifesto é um artefato derivado versionável. Nesta primeira fase ele roda em
modo sombra: descreve exatamente o corpus futuro, mas não substitui os documentos
inteiros já mantidos no Hindsight.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import unicodedata
from pathlib import Path

from . import indice, seguranca
from .lib import barras, config, frontmatter, raiz, relativo, titulo


ALGORITMO = "markdown-secoes-v2-acl"
ESPECIAIS = {"aberto": "item", "glossario": "termo", "cronologia": "entrada"}


class FragmentosErro(RuntimeError):
    pass


def _sha256(dados: bytes | str) -> str:
    bruto = dados.encode("utf-8") if isinstance(dados, str) else dados
    return hashlib.sha256(bruto).hexdigest()


def _cfg() -> dict:
    valor = config().get("rag", {})
    if not isinstance(valor, dict):
        raise FragmentosErro("`rag` precisa ser um objeto em `padrao.json`")
    return valor


def _perfil() -> dict:
    rag = _cfg()
    max_palavras = rag.get("max_palavras", 450)
    min_palavras = rag.get("min_palavras", 25)
    if (
        isinstance(max_palavras, bool) or not isinstance(max_palavras, int)
        or isinstance(min_palavras, bool) or not isinstance(min_palavras, int)
    ):
        raise FragmentosErro("limites do RAG precisam ser números inteiros")
    if max_palavras < 1 or min_palavras < 0 or min_palavras > max_palavras:
        raise FragmentosErro(
            "`rag.max_palavras` deve ser positivo e `rag.min_palavras` deve ficar "
            "entre zero e o máximo"
        )
    modo = str(rag.get("modo", "sombra"))
    if modo != "sombra":
        raise FragmentosErro(
            "a Fase 1 aceita somente `rag.modo=sombra`; migração do Hindsight ainda não foi liberada"
        )
    embedding_provedor = str(rag.get("embedding_provedor", "local")).strip()
    embedding_modelo = str(rag.get(
        "embedding_modelo", "BAAI/bge-small-en-v1.5"
    )).strip()
    if not embedding_provedor or not embedding_modelo:
        raise FragmentosErro(
            "`rag.embedding_provedor` e `rag.embedding_modelo` precisam identificar o perfil"
        )
    return {
        "max_palavras": max_palavras,
        "min_palavras": min_palavras,
        "especiais": dict(ESPECIAIS),
        "hindsight": {
            "modo": modo,
            "contrato": 2,
            "embedding_provedor": embedding_provedor,
            "embedding_modelo": embedding_modelo,
        },
        "seguranca": {
            "politica_fingerprint": seguranca.fingerprint(),
            "classificacoes": list(seguranca.CLASSIFICACOES),
            "redaction_antes_retain": True,
            "escopo": "produto-tenant-exato-v1",
        },
    }


def _manifesto_path() -> Path:
    base = Path(raiz()).resolve()
    configurado = _cfg().get(
        "manifesto", "docs/gerado/manifesto-fragmentos-v2.json"
    )
    if not isinstance(configurado, str) or not configurado.strip():
        raise FragmentosErro("`rag.manifesto` precisa ser um caminho não vazio")
    valor = configurado.strip("/")
    destino = (base / valor).resolve()
    if not destino.is_relative_to(base) or destino == base:
        raise FragmentosErro("`rag.manifesto` precisa ser um arquivo dentro da raiz do projeto")
    return destino


def _sem_frontmatter(texto: str) -> str:
    if not texto.startswith("---\n"):
        return texto
    fim = texto.find("\n---", 4)
    if fim == -1:
        return texto
    seguinte = texto.find("\n", fim + 4)
    return "" if seguinte == -1 else texto[seguinte + 1:]


def _limpar_titulo(texto: str) -> str:
    # Link mantém o rótulo visível; apenas o destino deixa de participar da âncora.
    texto = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", texto)
    texto = re.sub(r"<[^>]+>", "", texto)
    texto = re.sub(r"[`*_~\[\]]", "", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _slug(texto: str) -> str:
    limpo = _limpar_titulo(texto).lower()
    caracteres = []
    for caractere in limpo:
        categoria = unicodedata.category(caractere)
        if caractere.isalnum() or caractere in {"-", "_", " "} or categoria.startswith("M"):
            caracteres.append(caractere)
    return re.sub(r"\s+", "-", "".join(caracteres).strip()) or "secao"


def _cabecalhos(texto: str) -> list[dict]:
    linhas = texto.splitlines()
    resultado: list[dict] = []
    contagem: dict[str, int] = {}
    cerca: tuple[str, int] | None = None
    em_comentario = False

    def registrar(numero: int, nivel: int, titulo_: str, inicio: int | None = None) -> None:
        base = _slug(titulo_)
        repeticao = contagem.get(base, 0)
        contagem[base] = repeticao + 1
        ancora = base if repeticao == 0 else f"{base}-{repeticao}"
        resultado.append({
            "linha": numero,
            "inicio": numero + 1 if inicio is None else inicio,
            "nivel": nivel,
            "titulo": titulo_,
            "ancora": ancora,
        })

    for numero, linha in enumerate(linhas):
        marcador = re.match(r"^\s*(`{3,}|~{3,})", linha)
        if marcador:
            atual = marcador.group(1)
            if cerca is None:
                cerca = (atual[0], len(atual))
            elif atual[0] == cerca[0] and len(atual) >= cerca[1]:
                cerca = None
            continue
        if cerca is not None:
            continue
        restante = linha
        if em_comentario:
            if "-->" not in restante:
                continue
            restante = restante.split("-->", 1)[1]
            em_comentario = False
        while "<!--" in restante:
            antes, depois = restante.split("<!--", 1)
            if "-->" not in depois:
                restante = antes
                em_comentario = True
                break
            restante = antes + depois.split("-->", 1)[1]
        linha = restante
        setext = (
            re.match(r"^\s*(=+|-+)\s*$", linhas[numero + 1])
            if linha.strip() and numero + 1 < len(linhas) else None
        )
        if setext:
            registrar(
                numero, 1 if setext.group(1).startswith("=") else 2,
                linha.strip(), numero + 2,
            )
            continue
        match = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", linha)
        if not match:
            continue
        titulo_ = match.group(2).strip()
        registrar(numero, len(match.group(1)), titulo_)
    for indice_, cabecalho in enumerate(resultado):
        cabecalho["fim"] = (
            resultado[indice_ + 1]["linha"] if indice_ + 1 < len(resultado) else len(linhas)
        )
    return resultado


def _palavras(texto: str) -> int:
    return len(re.findall(r"\S+", texto))


def _blocos_markdown(corpo: str) -> list[str]:
    """Separa parágrafos sem cortar cercas de código nem tabelas Markdown."""
    blocos: list[str] = []
    atual: list[str] = []
    cerca: tuple[str, int] | None = None

    def fechar() -> None:
        if atual:
            blocos.append("\n".join(atual).rstrip())
            atual.clear()

    for linha in corpo.strip("\n").splitlines():
        marcador = re.match(r"^\s*(`{3,}|~{3,})", linha)
        if marcador:
            marca = marcador.group(1)
            if cerca is None:
                fechar()
                cerca = (marca[0], len(marca))
                atual.append(linha)
                continue
            atual.append(linha)
            if marca[0] == cerca[0] and len(marca) >= cerca[1]:
                cerca = None
                fechar()
            continue
        if cerca is not None:
            atual.append(linha)
            continue
        if not linha.strip():
            fechar()
            continue
        eh_tabela = linha.lstrip().startswith("|")
        atual_eh_tabela = bool(atual and atual[0].lstrip().startswith("|"))
        if atual and eh_tabela != atual_eh_tabela:
            fechar()
        atual.append(linha)
    fechar()
    return blocos


def _atomico(bloco: str) -> bool:
    primeira = bloco.lstrip()
    linhas = bloco.splitlines()
    tabela_sem_bordas = bool(
        len(linhas) > 1 and "|" in linhas[0]
        and re.match(r"^\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)+$", linhas[1])
    )
    codigo_indentado = bool(linhas and all(
        not linha.strip() or linha.startswith("    ") for linha in linhas
    ))
    return (
        primeira.startswith("```") or primeira.startswith("~~~")
        or primeira.startswith("|") or tabela_sem_bordas or codigo_indentado
    )


def _partir_texto(titulo_secao: str, corpo: str, maximo: int, minimo: int) -> list[str]:
    prefixo = f"## {titulo_secao}".strip()
    blocos = _blocos_markdown(corpo)
    if not blocos:
        return [prefixo]

    partes: list[str] = []
    atual: list[str] = []
    for bloco in blocos:
        candidato = "\n\n".join([prefixo, *atual, bloco])
        if atual and _palavras(candidato) > maximo:
            partes.append("\n\n".join([prefixo, *atual]).strip())
            atual = []
        if _palavras("\n\n".join([prefixo, bloco])) <= maximo:
            atual.append(bloco)
            continue
        if _atomico(bloco):
            if atual:
                partes.append("\n\n".join([prefixo, *atual]).strip())
                atual = []
            # O limite é alvo, não licença para publicar meia tabela ou meio código.
            partes.append(f"{prefixo}\n\n{bloco}".strip())
            continue
        palavras = bloco.split()
        disponivel = max(1, maximo - _palavras(prefixo))
        for inicio in range(0, len(palavras), disponivel):
            trecho = " ".join(palavras[inicio:inicio + disponivel])
            if atual:
                partes.append("\n\n".join([prefixo, *atual]).strip())
                atual = []
            partes.append(f"{prefixo}\n\n{trecho}".strip())
    if atual:
        partes.append("\n\n".join([prefixo, *atual]).strip())
    if len(partes) > 1 and _palavras(partes[-1]) < minimo:
        combinado = partes[-2] + "\n\n" + partes[-1].split("\n\n", 1)[-1]
        if _palavras(combinado) <= maximo:
            partes[-2:] = [combinado]
    return partes


def _id_unico(base: str, usados: set[str]) -> str:
    candidato = base
    contador = 1
    while candidato in usados:
        candidato = f"{base}-{contador}"
        contador += 1
    usados.add(candidato)
    return candidato


def _fragmento(doc: dict, ancora: str, texto: str, identidade: str,
                ordem: int, usados: set[str]) -> dict:
    texto_contextualizado = f"# {doc['doc_titulo']}\n\n{texto.strip()}"
    item = {
        "fragment_id": _id_unico(f"{doc['doc_id']}:{identidade}", usados),
        "source_uri": f"{doc['source_uri']}#{ancora}",
        "source_sha256": doc["source_sha256"],
        "conteudo_sha256": _sha256(texto_contextualizado),
        "doc_id": doc["doc_id"],
        "doc_tipo": doc["doc_tipo"],
        "doc_status": doc["doc_status"],
        "ordem": ordem,
        "classificacao": doc["classificacao"],
        "audience": doc["audience"],
        "produtos": doc["produtos"],
        "tenants": doc["tenants"],
        "texto": texto_contextualizado,
    }
    return item


def _secoes_gerais(texto: str, doc: dict, perfil: dict, usados: set[str]) -> list[dict]:
    corpo = _sem_frontmatter(texto)
    linhas = corpo.splitlines()
    todos_cabecalhos = _cabecalhos(corpo)
    if not todos_cabecalhos:
        raise FragmentosErro(
            f"`{doc['source_uri']}` não possui título Markdown que possa virar âncora"
        )
    # Prosa é fatiada no título e nas seções de segundo nível. Subtítulos ficam com
    # a seção-pai e só influenciam a quebra quando o limite de palavras for atingido.
    cabecalhos = [c.copy() for c in todos_cabecalhos if c["nivel"] <= 2]
    if not cabecalhos:
        cabecalhos = [todos_cabecalhos[0].copy()]
    for indice_, cabecalho in enumerate(cabecalhos):
        cabecalho["fim"] = (
            cabecalhos[indice_ + 1]["linha"]
            if indice_ + 1 < len(cabecalhos) else len(linhas)
        )
    saida: list[dict] = []
    for cabecalho in cabecalhos:
        inicio = cabecalho["inicio"]
        trecho = "\n".join(linhas[inicio:cabecalho["fim"]]).strip()
        # Um H1 usado apenas como título de documento não é conhecimento recuperável.
        # O título já é repetido em cada fragmento real por `_fragmento`.
        if not trecho and len(cabecalhos) > 1:
            continue
        partes = _partir_texto(
            cabecalho["titulo"], trecho,
            perfil["max_palavras"], perfil["min_palavras"],
        )
        for parte_numero, parte in enumerate(partes, 1):
            identidade = f"secao:{cabecalho['ancora']}:parte-{parte_numero}"
            saida.append(_fragmento(
                doc, cabecalho["ancora"], parte, identidade, len(saida), usados
            ))
    if not saida:
        primeiro = todos_cabecalhos[0]
        saida.append(_fragmento(
            doc, primeiro["ancora"], f"## {primeiro['titulo']}",
            f"secao:{primeiro['ancora']}:parte-1", 0, usados,
        ))
    return saida


def _aberto(texto: str, doc: dict, perfil: dict, usados: set[str]) -> list[dict]:
    corpo = _sem_frontmatter(texto)
    linhas = corpo.splitlines()
    itens: list[tuple[dict, str]] = []
    for cabecalho in _cabecalhos(corpo):
        match = re.match(r"^(ABERTO-[0-9A-Za-z_-]+)\b", cabecalho["titulo"], re.I)
        if cabecalho["nivel"] == 3 and match:
            itens.append((cabecalho, match.group(1)))
    if not itens:
        return _secoes_gerais(texto, doc, perfil, usados)
    saida = []
    for cabecalho, item_id in itens:
        conteudo = "\n".join(linhas[cabecalho["linha"]:cabecalho["fim"]]).strip()
        for parte_numero, parte in enumerate(_partir_texto(
            cabecalho["titulo"], conteudo.split("\n", 1)[-1],
            perfil["max_palavras"], perfil["min_palavras"],
        ), 1):
            saida.append(_fragmento(
                doc, cabecalho["ancora"], parte,
                f"item:{_slug(item_id)}:parte-{parte_numero}", len(saida), usados,
            ))
    return saida


def _cronologia(texto: str, doc: dict, perfil: dict, usados: set[str]) -> list[dict]:
    corpo = _sem_frontmatter(texto)
    linhas = corpo.splitlines()
    entradas = [
        c for c in _cabecalhos(corpo)
        if c["nivel"] == 2 and re.match(r"^\d{4}-\d{2}-\d{2}\b", c["titulo"])
    ]
    if not entradas:
        return _secoes_gerais(texto, doc, perfil, usados)
    saida = []
    for cabecalho in entradas:
        conteudo = "\n".join(linhas[cabecalho["linha"]:cabecalho["fim"]]).strip()
        for parte_numero, parte in enumerate(_partir_texto(
            cabecalho["titulo"], conteudo.split("\n", 1)[-1],
            perfil["max_palavras"], perfil["min_palavras"],
        ), 1):
            saida.append(_fragmento(
                doc, cabecalho["ancora"], parte,
                f"entrada:{cabecalho['ancora']}:parte-{parte_numero}", len(saida), usados,
            ))
    return saida


def _glossario(texto: str, doc: dict, perfil: dict, usados: set[str]) -> list[dict]:
    corpo = _sem_frontmatter(texto)
    cabecalhos = _cabecalhos(corpo)
    linhas = corpo.splitlines()
    termos: list[tuple[str, str, str, str]] = []
    secao = next((c for c in cabecalhos if c["nivel"] == 1), None)
    por_linha = {c["linha"]: c for c in cabecalhos}
    for numero, linha in enumerate(linhas):
        if numero in por_linha:
            secao = por_linha[numero]
        match = re.match(r"^\|\s*\*\*(.+?)\*\*\s*\|\s*(.+?)\s*\|\s*$", linha)
        if not match or "<termo>" in match.group(1).casefold():
            continue
        termo, definicao = match.group(1).strip(), match.group(2).strip()
        ancora = secao["ancora"] if secao else "glossario"
        titulo_secao = secao["titulo"] if secao else "Glossário"
        termos.append((termo, definicao, ancora, titulo_secao))
    if not termos:
        return _secoes_gerais(texto, doc, perfil, usados)
    saida = []
    for termo, definicao, ancora, titulo_secao in termos:
        conteudo = f"## {titulo_secao}\n\n**{termo}:** {definicao}"
        saida.append(_fragmento(
            doc, ancora, conteudo, f"termo:{_slug(termo)}", len(saida), usados
        ))
    return saida


def _documento(rel: str, perfil: dict, usados: set[str]) -> tuple[dict, list[dict]]:
    caminho = Path(raiz()) / rel
    try:
        bruto = caminho.read_bytes()
        texto = bruto.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise FragmentosErro(f"não foi possível ler `{rel}` como UTF-8: {exc}") from exc
    # O hash continua provando os bytes exatos. A análise usa LF canônico para que o
    # mesmo Markdown seja reconhecido em Windows (CRLF), Linux e arquivos legados CR.
    texto = texto.replace("\r\n", "\n").replace("\r", "\n")
    fm = frontmatter(texto) or {}
    acesso = seguranca.metadados(fm)
    doc = {
        "source_uri": rel,
        "source_sha256": _sha256(bruto),
        "doc_id": str(fm.get("id") or Path(rel).stem),
        "doc_titulo": str(fm.get("titulo") or fm.get("id") or Path(rel).stem),
        "doc_tipo": str(fm.get("tipo") or "indeterminado"),
        "doc_status": str(fm.get("status") or "indeterminado"),
        **acesso,
    }
    if doc["doc_id"] == "ABERTO":
        fragmentos = _aberto(texto, doc, perfil, usados)
    elif doc["doc_id"] == "GLOSSARIO":
        fragmentos = _glossario(texto, doc, perfil, usados)
    elif doc["doc_tipo"] == "cronologia":
        fragmentos = _cronologia(texto, doc, perfil, usados)
    else:
        fragmentos = _secoes_gerais(texto, doc, perfil, usados)
    return doc, fragmentos


def construir() -> dict:
    perfil = _perfil()
    algoritmo = str(_cfg().get("algoritmo", ALGORITMO))
    if algoritmo != ALGORITMO:
        raise FragmentosErro(
            f"algoritmo `{algoritmo}` não é suportado por esta versão; esperado `{ALGORITMO}`"
        )
    nucleo, _ = indice.documentos_do_nucleo()
    if not nucleo:
        raise FragmentosErro("o núcleo documental está vazio")
    usados: set[str] = set()
    ids_documentos: set[str] = set()
    documentos: dict[str, dict] = {}
    fragmentos: list[dict] = []
    for rel in sorted(nucleo):
        doc, itens = _documento(rel, perfil, usados)
        if doc["doc_id"] in ids_documentos:
            raise FragmentosErro(f"id documental duplicado no corpus: `{doc['doc_id']}`")
        ids_documentos.add(doc["doc_id"])
        documentos[rel] = {
            "doc_id": doc["doc_id"],
            "doc_tipo": doc["doc_tipo"],
            "doc_status": doc["doc_status"],
            "source_sha256": doc["source_sha256"],
            "fragmentos": len(itens),
            "classificacao": doc["classificacao"],
            "audience": doc["audience"],
            "produtos": doc["produtos"],
            "tenants": doc["tenants"],
        }
        fragmentos.extend(itens)
    perfil_fingerprint = _sha256(json.dumps(
        {"algoritmo": algoritmo, "perfil_indice": perfil},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ))
    base = {
        "schema": 2,
        "projeto": str(config()["projeto"]),
        "algoritmo": algoritmo,
        "perfil_fingerprint": perfil_fingerprint,
        "perfil_indice": perfil,
        "documentos": documentos,
        "fragmentos": fragmentos,
    }
    base["assinatura"] = _sha256(json.dumps(
        base, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ))
    return base


def serializar(manifesto: dict) -> str:
    return json.dumps(manifesto, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _gravar_atomico(destino: Path, conteudo: str) -> None:
    temporario: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", prefix=f".{destino.name}.",
            suffix=".tmp", dir=destino.parent, delete=False,
        ) as arquivo:
            arquivo.write(conteudo)
            arquivo.flush()
            os.fsync(arquivo.fileno())
            temporario = Path(arquivo.name)
        os.replace(temporario, destino)
        temporario = None
    finally:
        if temporario is not None:
            temporario.unlink(missing_ok=True)


def gerar(silencioso: bool = False) -> int:
    try:
        manifesto = construir()
        destino = _manifesto_path()
        destino.parent.mkdir(parents=True, exist_ok=True)
        _gravar_atomico(destino, serializar(manifesto))
        legado = destino.with_name("manifesto-fragmentos-v1.json")
        if destino.name == "manifesto-fragmentos-v2.json" and legado.is_file():
            legado.unlink()
    except (FragmentosErro, OSError, ValueError) as exc:
        if not silencioso:
            print(f"ERRO — manifesto de fragmentos não foi gerado: {exc}")
        return 1
    if not silencioso:
        titulo("RAG determinístico — modo sombra")
        print(f"  {relativo(str(destino))}")
        print(
            f"  {len(manifesto['documentos'])} documentos · "
            f"{len(manifesto['fragmentos'])} fragmentos · {manifesto['algoritmo']}"
        )
        print("  Hindsight atual não foi migrado nem substituído.")
    return 0


def verificar(silencioso: bool = False) -> int:
    try:
        destino = _manifesto_path()
        if not destino.is_file():
            raise FragmentosErro(
                f"não existe `{relativo(str(destino))}`; rode `memoria fragmentos gerar`"
            )
        atual = destino.read_text(encoding="utf-8")
        esperado = serializar(construir())
        if atual != esperado:
            raise FragmentosErro(
                "manifesto diverge das fontes, do algoritmo ou do perfil; "
                "rode `memoria fragmentos gerar`"
            )
        manifesto = json.loads(atual)
    except (FragmentosErro, OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        if not silencioso:
            print(f"ERRO — RAG determinístico desatualizado: {exc}")
        return 1
    if not silencioso:
        titulo("RAG determinístico — modo sombra")
        print(
            f"  íntegro: {len(manifesto['documentos'])} documentos · "
            f"{len(manifesto['fragmentos'])} fragmentos"
        )
        print(f"  perfil: {manifesto['perfil_fingerprint']}")
    return 0


def consultaveis(manifesto: dict | None = None) -> list[dict]:
    """Corpus da futura consulta normal; conteúdo superado continua no histórico."""
    dados = construir() if manifesto is None else manifesto
    return [f for f in dados["fragmentos"] if f["doc_status"] != "superado"]


def main(argv: list[str]) -> int:
    acao = argv[0] if argv else "verificar"
    if len(argv) > 1 or acao not in {"gerar", "verificar", "status"}:
        print("Uso: memoria fragmentos [gerar|verificar|status]")
        return 2
    return gerar() if acao == "gerar" else verificar()
