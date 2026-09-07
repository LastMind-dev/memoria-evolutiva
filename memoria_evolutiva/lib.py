"""lib — o que todos os comandos do padrão compartilham.

Porte fiel de scripts/lib-padrao.php (a versão de referência até a paridade ser provada;
depois, esta é a canônica e a PHP fica arquivada). Tudo aqui existe porque foi bug em
produção pelo menos uma vez — os comentários dizem qual. Apagar o comentário costuma ser
o primeiro passo para o bug voltar.

COMPATIBILIDADE É CONTRATO: `hash_do_conteudo` preserva o algoritmo legado; identidades
de arquivo persistidas canonizam LF/CRLF e os leitores aceitam a identidade física
legada somente quando ela prova exatamente o arquivo atual. Uma migração nunca pode
invalidar todos os projetos sem que o conteúdo tenha mudado de verdade.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.parse
from functools import lru_cache
from pathlib import Path


def barras(caminho: str) -> str:
    """Normaliza separador para barra normal.

    ESTE É O BUG MAIS PERIGOSO DA FAMÍLIA, porque não dá erro nenhum. No Windows os
    caminhos vêm com ``\\``, e uma comparação como ``'/Services/' in caminho``
    simplesmente não casa — o filtro passa batido e a contagem sai errada em silêncio.
    Num caso real: 73 em vez de 71, percebido só porque o número certo estava escrito
    num documento.
    """
    return caminho.replace("\\", "/")


ENDPOINT_HINDSIGHT_PADRAO = "http://127.0.0.1:8888"


def endpoint_bruto(memoria_cfg: dict) -> str:
    """Resolve o endpoint configurado, sem validar.

    Vive aqui porque os dois lados da identidade do marcador precisam do mesmo
    resolvedor E do mesmo default: `hindsight` caia no loopback e `indice` caia em
    string vazia era assimetria suficiente para deixar o marcador defasado para
    sempre num projeto cujo `padrao.json` nao declarasse a chave.
    """
    do_ambiente = os.environ.get("MEMORIA_HINDSIGHT_URL")
    if do_ambiente is not None:
        return do_ambiente.rstrip("/")
    return str(memoria_cfg.get("endpoint") or ENDPOINT_HINDSIGHT_PADRAO).rstrip("/")


def url_sem_query(valor: str) -> str:
    """Reduz uma URL a esquema, host e path, descartando query e fragmento.

    Os dois lados da identidade do marcador precisam da MESMA normalizacao: o que
    `hindsight.verificar_ao_vivo` grava em `prova_do_provedor` e o que
    `indice.verificar` reconstroi para comparar. Normalizar so a escrita deixaria o
    marcador permanentemente defasado. Vive aqui, e nao em `hindsight`, porque
    `hindsight` importa `indice` — o caminho de volta seria ciclo.
    """
    if not valor:
        return valor
    partes = urllib.parse.urlsplit(valor)
    if not partes.scheme and not partes.query and not partes.fragment:
        # Nao e URL absoluta e nao ha nada a descartar: devolve intacto.
        return valor
    return urllib.parse.urlunsplit((partes.scheme, partes.netloc, partes.path, "", ""))


def bytes_canonicos(conteudo: bytes) -> bytes:
    """Normaliza LF/CRLF em texto UTF-8 antes de calcular identidade.

    Git pode materializar o mesmo blob com finais de linha diferentes conforme o
    sistema operacional e ``core.autocrlf``. Binários e textos fora de UTF-8 continuam
    sendo provados byte a byte.
    """
    if b"\0" in conteudo:
        return conteudo
    try:
        texto = conteudo.decode("utf-8")
    except UnicodeDecodeError:
        return conteudo
    return texto.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def sha256_canonico(conteudo: bytes | str) -> str:
    """SHA-256 portátil para texto e estrito para conteúdo binário."""
    bruto = conteudo.encode("utf-8") if isinstance(conteudo, str) else conteudo
    return hashlib.sha256(bytes_canonicos(bruto)).hexdigest()


def identidade_arquivo(arquivo: Path) -> tuple[int, str]:
    """Tamanho e SHA-256 canônicos usados por derivados persistidos."""
    canonico = bytes_canonicos(arquivo.read_bytes())
    return len(canonico), hashlib.sha256(canonico).hexdigest()


@lru_cache(maxsize=1)
def raiz() -> str:
    """Raiz do PROJETO — não do pacote.

    Sobe do diretório corrente até achar ``padrao.json``. É o que faz o mesmo código
    funcionar instalado via pipx, via vendor, ou avulso — e chamado de um subdiretório.
    Num projeto virgem (instalador) devolve o cwd: RODE O INSTALADOR NA RAIZ.
    """
    declarada = os.environ.get("MEMORIA_PROJETO_RAIZ")
    if declarada:
        resolvida = Path(declarada).resolve()
        if (resolvida / "padrao.json").is_file():
            return barras(str(resolvida))
    dir_ = barras(os.getcwd())
    sobe = Path(dir_)
    while True:
        if (sobe / "padrao.json").is_file():
            return barras(str(sobe))
        if sobe.parent == sobe:
            return dir_
        sobe = sobe.parent


def pacote() -> str:
    """Raiz do PACOTE — onde moram stubs/ e os documentos do método."""
    return barras(str(Path(__file__).resolve().parent))


def morre(mensagem: str) -> "None":
    sys.stderr.write(mensagem)
    raise SystemExit(2)


@lru_cache(maxsize=1)
def config() -> dict:
    """Lê e valida o padrao.json. Morre com mensagem útil se estiver quebrado."""
    arquivo = Path(raiz()) / "padrao.json"
    if not arquivo.is_file():
        morre(
            "Não encontrei `padrao.json` na raiz do projeto.\n"
            "Ele é o único arquivo que você edita para adaptar o padrão.\n"
            "Rode: memoria instalar\n"
        )
    try:
        c = json.loads(arquivo.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        morre(f"`padrao.json` não é JSON válido: {e.msg}\n")
    if not isinstance(c, dict):
        morre("`padrao.json` não é JSON válido: raiz precisa ser objeto\n")
    for obrigatorio in ("projeto", "acervos", "vocabulario"):
        if obrigatorio not in c:
            morre(f"`padrao.json` não tem a chave obrigatória `{obrigatorio}`.\n")
    if not c["acervos"].get("canonico"):
        morre("`padrao.json`: `acervos.canonico` é obrigatório — é onde a verdade mora.\n")
    return c


def acervo() -> str:
    """Caminho absoluto do acervo canônico."""
    return raiz() + "/" + config()["acervos"]["canonico"].strip("/")


def arquivos_por_extensao(dir_: str, ext: str) -> list[str]:
    """Todos os arquivos de uma extensão dentro de um diretório, recursivo e ORDENADO.

    Ordenado porque saída de gerador precisa ser reprodutível — a ordem de leitura do
    sistema de arquivos não é garantida, e um diff que muda sem nada ter mudado vira
    ruído que todo mundo aprende a ignorar.
    """
    p = Path(dir_)
    if not p.is_dir():
        return []
    ext = ext.lower()
    out = [barras(str(f)) for f in p.rglob("*") if f.is_file() and f.suffix.lower() == "." + ext]
    out.sort()
    return out


def markdowns(dir_: str) -> list[str]:
    return arquivos_por_extensao(dir_, "md")


def relativo(absoluto: str) -> str:
    """Converte caminho do projeto sem depender da grafia usada pelo Windows.

    O mesmo diretório pode chegar como ``RUNNER~1`` e ``runneradmin``. Comparar as
    strings deixa o caminho absoluto vazar para artefatos derivados e os torna
    diferentes depois de um clone. ``resolve`` canoniza os dois lados antes de
    calcular a relação; caminhos externos continuam sendo apenas normalizados.
    """
    caminho = Path(absoluto)
    base = Path(raiz())
    try:
        return barras(str(caminho.resolve().relative_to(base.resolve())))
    except (OSError, ValueError):
        return barras(absoluto)


def comeca_com(caminho: str, prefixos: list[str]) -> bool:
    caminho = barras(caminho)
    for p in prefixos or []:
        if not p:
            continue
        if caminho.startswith(p.rstrip("/") + "/") or caminho == p.rstrip("/"):
            return True
    return False


def contem_algum(caminho: str, trechos: list[str]) -> bool:
    """Usado pelas exclusões dos contadores: casa por TRECHO de caminho, não por pasta."""
    caminho = barras(caminho)
    return any(t and t in caminho for t in trechos or [])


def frontmatter(conteudo: str) -> dict | None:
    """Frontmatter YAML simples — `chave: valor`, listas com `- ` e blocos `>-`.

    Deliberadamente não usa parser YAML completo: o padrão só precisa de chave/valor e
    lista, e uma dependência externa tornaria o kit mais difícil de instalar do que o
    problema que ele resolve. Porte 1:1 do PHP — o comportamento nos casos estranhos
    precisa ser o MESMO, senão a paridade quebra em documento de borda.
    """
    if not conteudo.startswith("---\n"):
        return None
    fim = conteudo.find("\n---", 4)
    if fim == -1:
        return None
    bloco = conteudo[4:fim]

    dados: dict = {}
    chave: str | None = None
    dobra = False

    for linha in bloco.split("\n"):
        if dobra:
            if re.match(r"^\s+\S", linha):
                dados[chave] = (str(dados[chave]) + " " + linha.strip()).strip()
                continue
            dobra = False
        m = re.match(r"^([a-z_]+):\s*>-?\s*$", linha)
        if m:
            chave = m.group(1)
            dados[chave] = ""
            dobra = True
            continue
        m = re.match(r"^\s+-\s+(.+)$", linha)
        if m and chave is not None and isinstance(dados.get(chave), list):
            dados[chave].append(m.group(1).strip().strip("\"'"))
            continue
        m = re.match(r"^([a-z_]+):\s*(.*)$", linha)
        if m:
            chave = m.group(1)
            valor = m.group(2).strip()
            if valor == "":
                dados[chave] = []
            elif valor == "[]":
                dados[chave] = []
                chave = None
            else:
                dados[chave] = valor.strip(" \"'")
                chave = None
    return dados


def hash_do_conteudo(conteudo: str) -> str:
    """Hash do conteúdo ignorando o carimbo de geração.

    `verificado_em`, `verificado_commit` e a linha "Gerado ... em `sha`." mudam a cada
    commit sem que o fato mude. Sem esta normalização o índice viveria "defasado" por
    causa de um carimbo.

    ⚠️ CONTRATO DE COMPATIBILIDADE: precisa produzir EXATAMENTE o mesmo hash da versão
    PHP — os marcadores existentes (`docs/.rag-indexado.json` e afins) foram gravados
    por ela. O teste de paridade compara os dois byte a byte.
    """
    limpo = re.sub(r"^verificado_(em|commit): .*$", "X", conteudo, flags=re.M)
    # Restrito ao carimbo que o gerador realmente produz. A expressão antiga casava
    # qualquer frase terminada em "em `...`.", fazendo mudanças como produção →
    # homologação desaparecerem do hash de um documento escrito à mão.
    limpo = re.sub(
        r"^(> Gerado por `(?:memoria gerar|vendor/bin/memoria gerar)` em )`[^`]*`\.$",
        r"\1`X`.",
        limpo,
        flags=re.M,
    )
    return hashlib.sha256(limpo.encode("utf-8")).hexdigest()[:16]


def commit_atual() -> str:
    """Sha curto do commit atual, ou string vazia se não houver git."""
    try:
        r = subprocess.run(
            ["git", "-C", raiz(), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=15,
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def titulo(texto: str) -> None:
    print(f"\n{texto}")
    print("─" * min(len(texto), 72))


def preparar_saida() -> None:
    """Evita que caracteres de apresentação derrubem a CLI em consoles legados.

    Em Windows, stdout redirecionado pode usar CP1252 mesmo quando o terminal interativo
    aceita UTF-8. Os textos em português continuam representáveis; separadores, setas e
    emojis viram ``?`` quando necessário, em vez de abortarem depois de uma gravação.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass


def limpar_caches() -> None:
    """Para o autoteste, que roda vários projetos no mesmo processo — nunca em CLI normal."""
    raiz.cache_clear()
    config.cache_clear()
