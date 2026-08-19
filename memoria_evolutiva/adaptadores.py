"""Adaptadores derivados para clientes de IA, sem duplicar fatos do projeto."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from . import __version__, contexto, fragmentos
from .lib import barras, config, raiz, sha256_canonico, titulo


SCHEMA = 1
PLATAFORMAS = ("codex", "claude", "cursor", "windsurf", "hermes")
INICIO = "<!-- memoria-evolutiva:adaptador-inicio -->"
FIM = "<!-- memoria-evolutiva:adaptador-fim -->"
TOML_INICIO = "# memoria-evolutiva:adaptador-inicio"
TOML_FIM = "# memoria-evolutiva:adaptador-fim"
SERVIDOR = "memoria-evolutiva"


class AdaptadoresErro(RuntimeError):
    pass


def _sha256_bytes(valor: bytes) -> str:
    return sha256_canonico(valor)


def _sha256_texto(valor: str) -> str:
    return _sha256_bytes(valor.encode("utf-8"))


def _cfg() -> dict:
    valor = config().get("adaptadores", {})
    if not isinstance(valor, dict):
        raise AdaptadoresErro("`adaptadores` precisa ser um objeto em `padrao.json`")
    return valor


def _manifesto_path() -> Path:
    rel = _cfg().get("manifesto", "docs/gerado/manifesto-adaptadores-v1.json")
    if not isinstance(rel, str) or not rel.strip():
        raise AdaptadoresErro("`adaptadores.manifesto` precisa ser caminho não vazio")
    base = Path(raiz()).resolve()
    destino = (base / rel).resolve()
    if not destino.is_relative_to(base) or destino.suffix.lower() != ".json":
        raise AdaptadoresErro("`adaptadores.manifesto` precisa ser JSON dentro do projeto")
    return destino


def _perfil_canary() -> str:
    perfil = _cfg().get("perfil_canary", "engenharia-leitura")
    if not isinstance(perfil, str) or perfil not in contexto.PERFIS:
        raise AdaptadoresErro("`adaptadores.perfil_canary` não identifica perfil válido")
    return perfil


def _plataformas() -> tuple[str, ...]:
    valores = _cfg().get("plataformas", list(PLATAFORMAS))
    if not isinstance(valores, list) or not valores:
        raise AdaptadoresErro("`adaptadores.plataformas` precisa ser lista não vazia")
    if any(not isinstance(item, str) or item not in PLATAFORMAS for item in valores):
        raise AdaptadoresErro("`adaptadores.plataformas` contém plataforma desconhecida")
    if len(set(valores)) != len(valores):
        raise AdaptadoresErro("`adaptadores.plataformas` não aceita duplicatas")
    return tuple(item for item in PLATAFORMAS if item in valores)


def _bloco_instrucao(
    plataforma: str, perfil_canary: str, cabecalho: bool = False
) -> str:
    frente = (
        "---\n"
        "description: Memória verificável do projeto\n"
        "alwaysApply: true\n"
        "---\n\n"
        if cabecalho else ""
    )
    return frente + f"""{INICIO}
## Memória evolutiva — {plataforma}

Bloco derivado; fatos vivem somente em `docs/`.
- Início: `memoria ciclo iniciar --plataforma={plataforma} --perfil={perfil_canary} --json`; ele prepara os provedores e repara estado velho antes do canary.
- Consulta: MCP `memoria_contexto`; fallback CLI `memoria contexto --pergunta="..." --perfil=PERFIL --json`.
- Perfis: leitura/análise=`engenharia-leitura`; documentação=`engenharia-documentacao`; código=`automacao-codigo`.
- `atendimento`/`operacao-assistida` exigem `produto`+`tenant` da identidade autenticada; nunca reutilize escopo ou conversa anterior.
- Entrada canônica: `docs/PROJETO.md`; sem fonte atual, registre `indeterminado`.
- Gateway read-only não autoriza commit, push, deploy ou mutação externa.
- Após mudar código/docs: `memoria ciclo atualizar --plataforma={plataforma} --perfil={perfil_canary} --json`; a manutenção diária usa somente `memoria agendador executar --json`, sem shell, SQL ou capacidade inventada.
- Antes de aceitar troca de algoritmo/modelo/provedor: `memoria avaliar verificar`; baseline só muda por `memoria avaliar medir` deliberado.
{FIM}
"""


def _bloco_codex_toml() -> str:
    return f"""{TOML_INICIO}
[mcp_servers.{SERVIDOR}]
command = "memoria"
args = ["contexto", "mcp"]
cwd = "."
required = true
enabled = true
enabled_tools = ["memoria_contexto"]
default_tools_approval_mode = "auto"

[mcp_servers.{SERVIDOR}.env]
MEMORIA_PROJETO_RAIZ = "."
{TOML_FIM}
"""


def _entrada_mcp(plataforma: str) -> dict:
    return {
        "command": "memoria",
        "args": ["contexto", "mcp"],
        "env": {
            "MEMORIA_PROJETO_RAIZ": "${CLAUDE_PROJECT_DIR:-.}"
            if plataforma == "claude" else "."
        },
    }


def _artefatos() -> dict[str, dict]:
    perfil_canary = _perfil_canary()
    return {
        "codex-instrucoes": {
            "plataforma": "codex", "path": "AGENTS.md", "formato": "bloco-markdown",
            "conteudo": _bloco_instrucao("codex", perfil_canary),
        },
        "codex-mcp": {
            "plataforma": "codex", "path": ".codex/config.toml", "formato": "bloco-toml",
            "conteudo": _bloco_codex_toml(),
        },
        "claude-instrucoes": {
            "plataforma": "claude", "path": "CLAUDE.md", "formato": "bloco-markdown",
            "conteudo": _bloco_instrucao("claude", perfil_canary),
        },
        "claude-mcp": {
            "plataforma": "claude", "path": ".mcp.json", "formato": "entrada-json-mcp",
            "conteudo": _entrada_mcp("claude"),
        },
        "cursor-instrucoes": {
            "plataforma": "cursor", "path": ".cursor/rules/memoria-evolutiva.mdc",
            "formato": "arquivo",
            "conteudo": _bloco_instrucao("cursor", perfil_canary, cabecalho=True),
        },
        "cursor-mcp": {
            "plataforma": "cursor", "path": ".cursor/mcp.json",
            "formato": "entrada-json-mcp", "conteudo": _entrada_mcp("cursor"),
        },
        "windsurf-instrucoes": {
            "plataforma": "windsurf", "path": ".windsurf/rules/memoria-evolutiva.md",
            "formato": "arquivo", "conteudo": _bloco_instrucao("windsurf", perfil_canary),
        },
        "hermes-instrucoes": {
            "plataforma": "hermes", "path": ".hermes.md", "formato": "bloco-markdown",
            "conteudo": _bloco_instrucao("hermes", perfil_canary),
        },
    }


def _caminho_artefato(rel: str) -> Path:
    base = Path(raiz()).resolve()
    caminho = base / rel
    if not caminho.resolve().is_relative_to(base):
        raise AdaptadoresErro(f"adaptador escapa da raiz do projeto: `{rel}`")
    atual = caminho
    while atual != base:
        if atual.is_symlink():
            raise AdaptadoresErro(f"adaptador não pode usar link simbólico: `{rel}`")
        atual = atual.parent
    return caminho


def _substituir_bloco(atual: str, novo: str, inicio: str, fim: str) -> str:
    tem_inicio, tem_fim = inicio in atual, fim in atual
    if tem_inicio != tem_fim:
        raise AdaptadoresErro("adaptador possui marcadores incompletos")
    if tem_inicio:
        if atual.count(inicio) != 1 or atual.count(fim) != 1 or atual.index(inicio) > atual.index(fim):
            raise AdaptadoresErro("adaptador possui marcadores duplicados ou invertidos")
        prefixo = atual.split(inicio, 1)[0]
        sufixo = atual.split(fim, 1)[1]
        return prefixo + novo.rstrip("\n") + sufixo
    separador = "" if not atual else ("\n" if atual.endswith("\n") else "\n\n")
    return atual + separador + novo


def _escrever_atomico(caminho: Path, conteudo: str) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", delete=False,
            dir=caminho.parent, prefix=f".{caminho.name}.", suffix=".tmp",
        ) as arquivo:
            arquivo.write(conteudo)
            arquivo.flush()
            os.fsync(arquivo.fileno())
            temporario = Path(arquivo.name)
        os.replace(temporario, caminho)
    finally:
        if temporario is not None and temporario.exists():
            temporario.unlink()


def _gravar_markdown(caminho: Path, conteudo: str) -> None:
    atual = caminho.read_text(encoding="utf-8") if caminho.is_file() else ""
    novo = _substituir_bloco(atual, conteudo, INICIO, FIM)
    _escrever_atomico(caminho, novo)


def _gravar_toml(caminho: Path, conteudo: str) -> None:
    atual = caminho.read_text(encoding="utf-8") if caminho.is_file() else ""
    if TOML_INICIO not in atual and re.search(
        rf"(?m)^\[mcp_servers\.{re.escape(SERVIDOR)}\]\s*$", atual
    ):
        raise AdaptadoresErro(
            f"`{barras(str(caminho))}` já declara `{SERVIDOR}` fora do bloco gerenciado"
        )
    novo = _substituir_bloco(atual, conteudo, TOML_INICIO, TOML_FIM)
    _escrever_atomico(caminho, novo)


def _ler_json(caminho: Path) -> dict:
    if not caminho.is_file():
        return {}
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AdaptadoresErro(f"`{barras(str(caminho))}` não é JSON válido: {exc}") from exc
    if not isinstance(dados, dict):
        raise AdaptadoresErro(f"`{barras(str(caminho))}` precisa ter objeto na raiz")
    return dados


def _gravar_json_mcp(caminho: Path, entrada: dict) -> None:
    dados = _ler_json(caminho)
    servidores = dados.setdefault("mcpServers", {})
    if not isinstance(servidores, dict):
        raise AdaptadoresErro(f"`{barras(str(caminho))}.mcpServers` precisa ser objeto")
    servidores[SERVIDOR] = entrada
    _escrever_atomico(caminho, json.dumps(dados, ensure_ascii=False, indent=2) + "\n")


def _prevalidar(artefatos: dict[str, dict], ativos: set[str]) -> None:
    """Recusa todos os conflitos conhecidos antes da primeira escrita."""
    for artefato in artefatos.values():
        if artefato["plataforma"] not in ativos:
            continue
        caminho = _caminho_artefato(str(artefato["path"]))
        if not caminho.exists():
            continue
        if not caminho.is_file():
            raise AdaptadoresErro(f"`{artefato['path']}` existe, mas não é arquivo")
        formato = artefato["formato"]
        if formato == "arquivo":
            continue
        if formato == "entrada-json-mcp":
            dados = _ler_json(caminho)
            servidores = dados.get("mcpServers", {})
            if not isinstance(servidores, dict):
                raise AdaptadoresErro(f"`{artefato['path']}.mcpServers` precisa ser objeto")
            continue
        atual = caminho.read_text(encoding="utf-8")
        if formato == "bloco-toml":
            if TOML_INICIO not in atual and re.search(
                rf"(?m)^\[mcp_servers\.{re.escape(SERVIDOR)}\]\s*$", atual
            ):
                raise AdaptadoresErro(
                    f"`{artefato['path']}` já declara `{SERVIDOR}` fora do bloco gerenciado"
                )
            _substituir_bloco(atual, str(artefato["conteudo"]), TOML_INICIO, TOML_FIM)
        else:
            _substituir_bloco(atual, str(artefato["conteudo"]), INICIO, FIM)


def _extrair(artefato: dict) -> object:
    caminho = _caminho_artefato(str(artefato["path"]))
    if not caminho.is_file():
        raise AdaptadoresErro(f"adaptador ausente: `{artefato['path']}`")
    formato = artefato["formato"]
    if formato == "entrada-json-mcp":
        dados = _ler_json(caminho)
        servidores = dados.get("mcpServers")
        if not isinstance(servidores, dict) or SERVIDOR not in servidores:
            raise AdaptadoresErro(f"entrada MCP ausente em `{artefato['path']}`")
        return servidores[SERVIDOR]
    texto = caminho.read_text(encoding="utf-8")
    if formato == "arquivo":
        return texto
    inicio, fim = ((TOML_INICIO, TOML_FIM) if formato == "bloco-toml" else (INICIO, FIM))
    if texto.count(inicio) != 1 or texto.count(fim) != 1 or texto.index(inicio) > texto.index(fim):
        raise AdaptadoresErro(f"bloco gerenciado inválido em `{artefato['path']}`")
    return inicio + texto.split(inicio, 1)[1].split(fim, 1)[0] + fim + "\n"


def _hash_valor(valor: object) -> str:
    if isinstance(valor, str):
        return _sha256_texto(valor)
    return _sha256_texto(json.dumps(valor, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def _manifesto(artefatos: dict[str, dict]) -> dict:
    cfg = config()
    frag = fragmentos._manifesto_path()
    if fragmentos.verificar(silencioso=True) != 0 or not frag.is_file():
        raise AdaptadoresErro("manifesto de fragmentos ausente ou defasado")
    schema_contexto = Path(__file__).resolve().parent / "schemas/contexto-v2.schema.json"
    plataformas = _plataformas()
    itens = []
    for id_, artefato in sorted(artefatos.items()):
        if artefato["plataforma"] not in plataformas:
            continue
        atual = _extrair(artefato)
        itens.append({
            "id": id_,
            "plataforma": artefato["plataforma"],
            "path": artefato["path"],
            "formato": artefato["formato"],
            "conteudo_sha256": _hash_valor(atual),
        })
    memoria = cfg.get("memoria", {})
    banco = memoria.get("banco") if memoria.get("ativo") else None
    return {
        "schema": SCHEMA,
        "projeto": str(cfg["projeto"]),
        "banco": str(banco) if banco is not None else None,
        "perfil_canary": _perfil_canary(),
        "plataformas": list(plataformas),
        "gateway": {
            "transporte": "stdio",
            "comando": ["memoria", "contexto", "mcp"],
            "ferramenta": "memoria_contexto",
            "contexto_schema": 2,
            "contexto_schema_sha256": _sha256_bytes(schema_contexto.read_bytes()),
            "fragmentos_manifesto_sha256": _sha256_bytes(frag.read_bytes()),
        },
        "gerador_versao": __version__,
        "artefatos": itens,
    }


def _gravar_artefatos() -> tuple[set[str], dict[str, dict]]:
    ativos = set(_plataformas())
    artefatos = _artefatos()
    _prevalidar(artefatos, ativos)
    for artefato in artefatos.values():
        if artefato["plataforma"] not in ativos:
            continue
        caminho = _caminho_artefato(str(artefato["path"]))
        formato = artefato["formato"]
        if formato == "arquivo":
            _escrever_atomico(caminho, str(artefato["conteudo"]))
        elif formato == "bloco-markdown":
            _gravar_markdown(caminho, str(artefato["conteudo"]))
        elif formato == "bloco-toml":
            _gravar_toml(caminho, str(artefato["conteudo"]))
        elif formato == "entrada-json-mcp":
            _gravar_json_mcp(caminho, dict(artefato["conteudo"]))
        else:
            raise AdaptadoresErro(f"formato de adaptador desconhecido: `{formato}`")
    return ativos, artefatos


def preparar(silencioso: bool = True) -> int:
    """Grava entradas antes da cobertura; o manifesto final espera o RAG novo."""
    try:
        ativos, _ = _gravar_artefatos()
    except (AdaptadoresErro, OSError) as exc:
        if not silencioso:
            print(f"ERRO — entradas dos adaptadores não foram preparadas: {exc}")
        return 1
    if not silencioso:
        print(f"Entradas de {len(ativos)} plataformas preparadas antes da cobertura.")
    return 0


def gerar(silencioso: bool = False) -> int:
    try:
        _, artefatos = _gravar_artefatos()
        manifesto = _manifesto(artefatos)
        destino = _manifesto_path()
        _escrever_atomico(
            destino,
            json.dumps(manifesto, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )
    except (AdaptadoresErro, OSError) as exc:
        if not silencioso:
            print(f"ERRO — adaptadores não foram gerados: {exc}")
        return 1
    if not silencioso:
        titulo("Adaptadores de agentes")
        print(f"  {len(manifesto['plataformas'])} plataformas · manifesto v{SCHEMA}")
        print("  fatos permanecem exclusivamente em `docs/`")
    return 0


def _falhas() -> list[str]:
    try:
        caminho = _manifesto_path()
        if not caminho.is_file():
            return ["manifesto de adaptadores ausente"]
        atual = json.loads(caminho.read_text(encoding="utf-8"))
        if not isinstance(atual, dict) or atual.get("schema") != SCHEMA:
            return ["manifesto de adaptadores usa schema antigo ou inválido"]
        esperado = _manifesto(_artefatos())
    except (AdaptadoresErro, OSError, json.JSONDecodeError, SystemExit) as exc:
        return [str(exc)]
    falhas = []
    if atual != esperado:
        falhas.append("manifesto de adaptadores diverge das entradas atuais")
    registros = atual.get("artefatos", [])
    if not isinstance(registros, list):
        registros = []
    por_id = {item.get("id"): item for item in registros if isinstance(item, dict)}
    for id_, artefato in _artefatos().items():
        if artefato["plataforma"] not in esperado["plataformas"]:
            continue
        try:
            extraido = _extrair(artefato)
        except AdaptadoresErro as exc:
            falhas.append(str(exc))
            continue
        registro = por_id.get(id_)
        if not registro or registro.get("conteudo_sha256") != _hash_valor(extraido):
            falhas.append(f"adaptador alterado ou não registrado: `{artefato['path']}`")
        if _hash_valor(extraido) != _hash_valor(artefato["conteudo"]):
            falhas.append(f"adaptador não segue o contrato atual: `{artefato['path']}`")
    return list(dict.fromkeys(falhas))


def verificar(silencioso: bool = False) -> int:
    falhas = _falhas()
    if not silencioso:
        titulo("Adaptadores de agentes")
        if falhas:
            print("  FALHA — adaptador ou manifesto defasado:")
            for falha in falhas:
                print(f"    - {falha}")
            print("\n  Rode: memoria adaptadores gerar")
        else:
            print("  Em dia com o manifesto neutro e todos os clientes declarados.")
    return 1 if falhas else 0


def _git_estado() -> tuple[str | None, bool | None]:
    try:
        head = subprocess.run(
            ["git", "-C", raiz(), "rev-parse", "HEAD"], capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=15,
        )
        if head.returncode != 0:
            return None, None
        estado = subprocess.run(
            ["git", "-C", raiz(), "status", "--porcelain"], capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=15,
        )
        return head.stdout.strip(), bool(estado.stdout.strip()) if estado.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None, None


def canary(plataforma: str, perfil: str) -> tuple[int, dict]:
    falhas = _falhas()
    try:
        plataformas = _plataformas()
    except (AdaptadoresErro, SystemExit) as exc:
        plataformas = ()
        falhas.append(str(exc) or "configuração de adaptadores inválida")
    if plataforma not in plataformas:
        falhas.append(f"plataforma não declarada: `{plataforma}`")
    if perfil not in contexto.PERFIS:
        falhas.append(f"perfil desconhecido: `{perfil}`")
    else:
        try:
            perfil_esperado = _perfil_canary()
        except (AdaptadoresErro, SystemExit) as exc:
            perfil_esperado = None
            falhas.append(str(exc) or "perfil do canary inválido")
        if perfil_esperado is not None and perfil != perfil_esperado:
            falhas.append(
                f"perfil do canary diverge: esperado `{perfil_esperado}`, recebido `{perfil}`"
            )
    try:
        cfg = config()
    except SystemExit:
        cfg = {}
        falhas.append("configuração do projeto inválida")
    head, sujo = _git_estado()
    if head is None:
        falhas.append("commit Git atual não pôde ser confirmado")
    envelope = None
    if not falhas:
        try:
            envelope = contexto.construir(
                "Qual é o objetivo e o estado atual deste projeto?", perfil, 512
            )
        except (contexto.ContextoErro, SystemExit) as exc:
            falhas.append(
                str(exc) if isinstance(exc, contexto.ContextoErro)
                else "configuração do projeto inválida"
            )
    if envelope is not None:
        if envelope.get("projeto") != cfg.get("projeto"):
            falhas.append("gateway respondeu por outro projeto")
        if envelope.get("perfil") != perfil:
            falhas.append("gateway respondeu com outro perfil")
        if not envelope.get("fontes"):
            falhas.append("gateway não confirmou fonte documental para o canary")
        if envelope.get("frescor") != "confirmado":
            falhas.append("gateway não confirmou o frescor dos provedores ativos")
    memoria = cfg.get("memoria", {})
    ativo = bool(memoria.get("ativo"))
    banco = memoria.get("banco") if ativo else None
    saida = {
        "schema": 1,
        "ok": not falhas,
        "plataforma": plataforma,
        "projeto": str(cfg.get("projeto", "")),
        "banco": str(banco) if banco is not None else None,
        "banco_estado": "confirmado" if ativo and envelope and envelope.get("frescor") == "confirmado"
        else "desativado-explicitamente" if not ativo else "nao-confirmado",
        "perfil": perfil,
        "commit": head,
        "worktree_sujo": sujo,
        "frescor": envelope.get("frescor") if envelope else "nao-confirmado",
        "fontes_confirmadas": len(envelope.get("fontes", [])) if envelope else 0,
        "acoes_permitidas": [],
        "falhas": falhas,
    }
    return (0 if not falhas else 1), saida


def main(argv: list[str]) -> int:
    acao = argv[0] if argv else "status"
    if acao in {"gerar", "verificar", "status"}:
        if len(argv) > 1:
            print(f"`memoria adaptadores {acao}` não aceita opções.")
            return 2
        return gerar() if acao == "gerar" else verificar()
    if acao != "canary":
        print("Uso: memoria adaptadores [gerar|verificar|status|canary --plataforma=ID --perfil=PERFIL --json]")
        return 2
    opcoes: dict[str, str | bool] = {}
    for argumento in argv[1:]:
        match = re.match(r"^--([a-z-]+)(?:=(.*))?$", argumento)
        if not match:
            print(f"Opção desconhecida: {argumento}", file=sys.stderr)
            return 2
        opcoes[match.group(1)] = match.group(2) if match.group(2) is not None else True
    if set(opcoes) - {"plataforma", "perfil", "json"}:
        print("Opção desconhecida em `memoria adaptadores canary`.", file=sys.stderr)
        return 2
    plataforma, perfil = opcoes.get("plataforma"), opcoes.get("perfil")
    if not isinstance(plataforma, str) or not isinstance(perfil, str):
        print("Canary exige `--plataforma=ID --perfil=PERFIL --json`.", file=sys.stderr)
        return 2
    rc, saida = canary(plataforma, perfil)
    print(json.dumps(saida, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return rc
