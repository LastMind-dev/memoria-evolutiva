"""instalar — publica o padrão num projeto, novo ou existente.

O que faz: publica os stubs (SEM sobrescrever nada), garante a árvore com .gitkeep,
escreve/ajusta o padrao.json, troca <NOME-DO-PROJETO> pelo nome real, transforma o
modelo de cronologia no mês corrente.

Em instalação nova, conclui o núcleo factual, gera derivados e a skill, mede as
catracas, sincroniza os provedores, executa o autoteste e confirma a instalação.
Não commita nem publica. É seguro rodar de novo.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import urllib.parse
from datetime import date
from importlib import metadata
from pathlib import Path

from . import __version__
from .lib import barras, markdowns, morre, pacote

ARVORE = [
    "docs/cronologia", "docs/produto", "docs/funcional", "docs/arquitetura",
    "docs/decisoes", "docs/runbooks", "docs/evidencia", "docs/politicas",
    "docs/avaliacao", "docs/gerado", "docs/_templates", "docs/_arquivo",
]

GITKEEP = ("Marcador para o git preservar esta pasta enquanto ela estiver vazia.\n"
           "Pode apagar quando houver conteúdo aqui.\n")

EXTENSOES_CODIGO = {
    ".c", ".cc", ".cpp", ".cs", ".dart", ".go", ".java", ".js", ".jsx",
    ".kt", ".kts", ".php", ".py", ".rb", ".rs", ".scala", ".sh", ".sql",
    ".svelte", ".ts", ".tsx", ".vue",
}
PULAR_DETECCAO = {
    ".git", ".memoria", ".venv", "build", "dist", "docs", "node_modules",
    "vendor", "venv", "__pycache__", "graphify-out", "skill-memoria-evolutiva",
}
RAIZES_CONVENCIONAIS = {"src", "app", "lib", "packages", "source"}

PLACEHOLDERS_PROJETO = {"", "meu-projeto", "<NOME-DO-PROJETO>", "nome-do-projeto"}


def _nome_projeto(raiz_: str, informado: object | None) -> str:
    """Resolve a identidade sem obrigar a repetir o nome da pasta na CLI."""
    if informado is None:
        arq_config = Path(raiz_) / "padrao.json"
        if arq_config.is_file():
            try:
                existente = json.loads(arq_config.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                existente = None
            if isinstance(existente, dict):
                configurado = existente.get("projeto")
                if isinstance(configurado, str) and configurado not in PLACEHOLDERS_PROJETO:
                    informado = configurado
        if informado is None:
            informado = Path(raiz_).resolve().name

    if not isinstance(informado, str) or not informado:
        raise ValueError(
            "não foi possível detectar o nome do projeto pela pasta atual; "
            "use `--projeto=NOME`"
        )
    if informado != informado.strip() or any(ch in informado for ch in "\r\n"):
        raise ValueError(
            "o nome do projeto não pode começar/terminar com espaço nem conter quebra de linha"
        )
    return informado


def _fontes_de_codigo(raiz_: str) -> list[Path]:
    base = Path(raiz_).resolve()
    fontes: list[Path] = []
    for arquivo in base.rglob("*"):
        if not arquivo.is_file() or arquivo.is_symlink():
            continue
        relativo = arquivo.relative_to(base)
        if any(parte in PULAR_DETECCAO for parte in relativo.parts):
            continue
        if arquivo.suffix.lower() in EXTENSOES_CODIGO:
            fontes.append(relativo)
    return fontes


def _detectar_raiz_codigo(raiz_: str) -> str:
    """Escolhe a menor raiz convencional que ainda cubra todo o código observado."""
    fontes = _fontes_de_codigo(raiz_)
    if not fontes:
        return "src" if (Path(raiz_) / "src").is_dir() else "."

    primeiros = {fonte.parts[0] if len(fonte.parts) > 1 else "." for fonte in fontes}
    if len(primeiros) == 1:
        unica = next(iter(primeiros))
        if unica.lower() in RAIZES_CONVENCIONAIS:
            return unica
    return "."


def _raiz_codigo(raiz_: str, informada: object | None) -> str:
    """Preserva configuração existente ou detecta o escopo sem perguntar ao usuário."""
    if informada is None:
        arq_config = Path(raiz_) / "padrao.json"
        if arq_config.is_file():
            try:
                existente = json.loads(arq_config.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                existente = None
            if isinstance(existente, dict):
                gerado = existente.get("gerado")
                if isinstance(gerado, dict):
                    configurada = gerado.get("raiz")
                    if isinstance(configurada, str) and configurada:
                        informada = configurada
        if informada is None:
            informada = _detectar_raiz_codigo(raiz_)

    if not isinstance(informada, str) or not informada:
        raise ValueError("a raiz do código detectada é inválida")
    return informada


def _fechar_instalacao(*, incluir_bancos: bool, executar_autoteste: bool) -> int:
    """Gera a peça dos agentes e prova o resultado antes de registrar automação."""
    from . import autoteste, skill, verificacao

    if skill.main([]) != 0:
        print("\nA estrutura foi instalada, mas a skill dos agentes não foi gerada.")
        return 1
    if verificacao.executar(incluir_bancos=incluir_bancos) != 0:
        print("\nA estrutura foi instalada, mas a verificação final não aprovou.")
        return 1
    if executar_autoteste and autoteste.main() != 0:
        print("\nA estrutura foi instalada, mas o autoteste encontrou uma catraca ineficaz.")
        return 1
    return 0

GITIGNORE_GRAPHIFY = """# memoria-evolutiva: estado local do Graphify
graphify-out/cache/
graphify-out/.graphify_python
graphify-out/.graphify_root
graphify-out/manifest.json
graphify-out/stat-index.json
"""

GITIGNORE_EXECUTOR = """# memoria-evolutiva: estado local do executor
.memoria/executor/
"""

GITIGNORE_AGENDADOR = """# memoria-evolutiva: scripts e logs locais do agendador
.memoria/agendador/
"""


def _origem_imutavel_ci() -> str:
    """Descobre a origem exata do pacote sem transferir essa escolha ao projeto."""
    try:
        direto = metadata.distribution("memoria-evolutiva").read_text("direct_url.json")
        dados = json.loads(direto) if direto else {}
    except (metadata.PackageNotFoundError, json.JSONDecodeError, OSError):
        dados = {}
    if not isinstance(dados, dict):
        dados = {}
    vcs = dados.get("vcs_info", {})
    if not isinstance(vcs, dict):
        vcs = {}
    url = str(dados.get("url") or "")
    commit = str(vcs.get("commit_id") or "")
    partes = urllib.parse.urlsplit(url)
    url_segura_para_shell = bool(re.fullmatch(r"https?://[A-Za-z0-9._~:/%+-]+", url))
    if (partes.scheme in {"https", "http"} and partes.hostname
            and partes.username is None and partes.password is None
            and not partes.query and not partes.fragment and url_segura_para_shell
            and re.fullmatch(r"[0-9a-fA-F]{40}", commit)):
        return f"git+{url}@{commit}"
    return f"memoria-evolutiva=={__version__}"


def _fixar_workflow(raiz_: str, ajustados: list[str]) -> None:
    workflow = Path(raiz_) / ".github/workflows/documentacao.yml"
    if not workflow.is_file():
        return
    texto = workflow.read_text(encoding="utf-8")
    origem = _origem_imutavel_ci()
    novo = texto.replace("<MEMORIA_EVOLUTIVA_ORIGEM_IMUTAVEL>", origem)
    # Migra somente a linha exata distribuída pelas versões antigas; não toca em
    # comandos personalizados do projeto.
    novo = novo.replace(
        "git+https://github.com/LastMind-dev/memoria-evolutiva.git@main", origem
    )
    # Atualiza somente o pin oficial, em uma etapa `run: pip install` distribuída. Isso
    # mantém o CI no mesmo commit do pacote recém-instalado sem reescrever URLs, forks
    # ou comandos personalizados do projeto.
    novo = re.sub(
        r"(?m)^(\s*run:\s+pip install )"
        r"git\+https://github\.com/LastMind-dev/memoria-evolutiva\.git@[0-9a-fA-F]{40}"
        r"(\s*)$",
        lambda match: match.group(1) + origem + match.group(2),
        novo,
    )
    # Migra somente o pin na linha distribuída. Um uso da biblioteca em outro comando
    # ou texto documental não é alterado por coincidência.
    novo = re.sub(
        r"(?m)^(\s*run:\s+pip install )memoria-evolutiva==\d+\.\d+\.\d+(\s*)$",
        lambda match: match.group(1) + origem + match.group(2),
        novo,
    )
    if novo != texto:
        workflow.write_text(novo, encoding="utf-8")
        ajustados.append(f"workflow documental fixado em `{origem}`")


def _ignorar_estado_local(raiz_: str, ajustados: list[str],
                          incluir_graphify: bool) -> None:
    destino = Path(raiz_) / ".gitignore"
    atual = destino.read_text(encoding="utf-8") if destino.is_file() else ""
    blocos = []
    if (incluir_graphify
            and "# memoria-evolutiva: estado local do Graphify" not in atual):
        blocos.append(GITIGNORE_GRAPHIFY)
        ajustados.append(".gitignore → estado local do Graphify")
    if "# memoria-evolutiva: estado local do executor" not in atual:
        blocos.append(GITIGNORE_EXECUTOR)
        ajustados.append(".gitignore → estado local do executor")
    if "# memoria-evolutiva: scripts e logs locais do agendador" not in atual:
        blocos.append(GITIGNORE_AGENDADOR)
        ajustados.append(".gitignore → scripts e logs locais do agendador")
    if not blocos:
        return
    separador = "" if not atual or atual.endswith("\n") else "\n"
    prefixo = "" if not atual else "\n"
    destino.write_text(
        atual + separador + prefixo + "\n".join(blocos),
        encoding="utf-8",
    )


def _publicar(de: Path, para: Path, criados: list, existiam: list) -> None:
    """Copiar SEM SOBRESCREVER — o que já existe é decisão de alguém e não se toca."""
    if not de.is_dir():
        return
    for item in sorted(de.iterdir()):
        destino = para / item.name
        if item.is_dir():
            destino.mkdir(parents=True, exist_ok=True)
            _publicar(item, destino, criados, existiam)
        elif destino.is_file():
            existiam.append(str(destino))
        else:
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, destino)
            criados.append(str(destino))


def _detectar_extensoes(raiz_: str, codigo: str) -> list[str]:
    base = Path(raiz_) / codigo.strip("/")
    encontradas = {
        arquivo.suffix.lower().lstrip(".")
        for arquivo in base.rglob("*") if base.is_dir() and arquivo.is_file()
        and not arquivo.is_symlink()
        and arquivo.suffix.lower() in EXTENSOES_CODIGO
        and not any(parte in PULAR_DETECCAO for parte in arquivo.relative_to(base).parts)
    }
    return sorted(encontradas) or ["php"]


def _config_nova(projeto: str, codigo: str, bancos_ativos: bool,
                 raiz_: str, extensoes: list[str]) -> dict:
    return {
        "projeto": projeto,
        "acervos": {
            "canonico": "docs",
            "exploracao": None,
            "indice": "externo" if bancos_ativos else None,
            "ignorar": ["docs/_templates/", "docs/_arquivo/"],
        },
        "vocabulario": {
            "tipo": ["entrada", "estado", "cronologia", "prd", "fdd", "hld", "lld",
                     "adr", "runbook", "politica", "evidencia", "gerado"],
            "status": ["rascunho", "verificado", "superado"],
            "obrigatorios": ["id", "tipo", "projeto", "titulo", "status"],
        },
        "cadeia": {
            "niveis": {"prd": 0, "fdd": 1, "hld": 2, "lld": 3},
            "livres": ["adr"],
            "exige_origem": ["fdd", "hld", "lld"],
        },
        "externos": {"pastas": []},
        # Só entram os ponteiros que EXISTEM — declarar ausente vira aviso permanente,
        # e aviso permanente é ruído que treina todo mundo a não ler a saída.
        "ponteiros": {
            "limite_de_linhas": 40,
            "arquivos": [p for p in
                         ["CLAUDE.md", "AGENTS.md", ".cursor/rules/projeto.mdc", ".windsurfrules"]
                         if (Path(raiz_) / p).is_file()],
        },
        "gerado": {
            "diretorio": "docs/gerado",
            "raiz": codigo,
            "extensoes": extensoes,
            "extratores": ["mapa-diretorios", "cadeia-documentos",
                           "diagnostico-projeto", "analise-inicial", "cobertura-codigo"],
            "extensao_do_projeto": None,
        },
        "catraca": {
            "linha_de_base": "docs/politicas/baseline.json",
            "contadores": [{
                "chave": "docs_sem_frontmatter",
                "rotulo": "estrutura · documento sem frontmatter",
                "tipo": "markdown_sem_frontmatter",
                "onde": "docs",
                "excluir": ["docs/_arquivo/", "docs/_templates/"],
            }],
        },
        "memoria": {
            "ativo": bancos_ativos,
            "obrigatorio": bancos_ativos,
            "ferramenta": "hindsight" if bancos_ativos else None,
            "modo": "local",
            "endpoint": "http://127.0.0.1:8888",
            "banco": projeto,
            "api_key_env": None,
            "timeout_segundos": 300,
            "consulta_budget": "mid",
            "consultas_paralelas": 2,
            "cache_consulta_ttl_segundos": 30,
            "marcador": "docs/.hindsight-indexado.json",
            "nucleo": ["docs/PROJETO.md", "docs/ESTADO.md", "docs/ABERTO.md",
                       "docs/GLOSSARIO.md", "docs/cronologia/", "docs/produto/",
                       "docs/funcional/", "docs/arquitetura/", "docs/decisoes/",
                       "docs/politicas/", "docs/runbooks/", "docs/evidencia/",
                       ],
            "ignorar": ["docs/_arquivo/", "docs/_templates/"],
        },
        "rag": {
            "modo": "sombra",
            "manifesto": "docs/gerado/manifesto-fragmentos-v2.json",
            "algoritmo": "markdown-secoes-v2-acl",
            "max_palavras": 450,
            "min_palavras": 25,
            "embedding_provedor": "local",
            "embedding_modelo": "BAAI/bge-small-en-v1.5",
        },
        "contexto": {
            "max_tokens": 2048,
            "max_fontes": 8,
            "max_codigo": 5,
            "http_host": "127.0.0.1",
            "http_porta": 8765,
        },
        "seguranca_memoria": {
            "ativo": True,
            "classificacao_padrao": "interno",
            "nao_indexar": ["secreto-nao-indexar"],
            "escopo": "produto-tenant-exato-v1",
            "perfis_com_escopo_obrigatorio": ["atendimento", "operacao-assistida"],
            "redaction_antes_retain": True,
            "redaction_algoritmo": "redaction-deterministica-v1",
        },
        "adaptadores": {
            "manifesto": "docs/gerado/manifesto-adaptadores-v1.json",
            "perfil_canary": "engenharia-leitura",
            "plataformas": ["codex", "claude", "cursor", "windsurf", "hermes"],
        },
        "ciclo": {
            "ativo": True,
            "auto_reparar_no_inicio": True,
            "iniciar_hindsight_embed": True,
            "timeout_inicializacao_segundos": 180,
            "mutacao_externa": "somente-bancos-locais",
            "publicacao_automatica": False,
        },
        "agendamento": {
            "ativo": True,
            "registrar_na_instalacao": True,
            "frequencia": "diaria",
            "horario_local": "02:15",
            "comando": "memoria-agendador-v1",
            "banco_negocio": "proibido",
            "publicacao_automatica": False,
        },
        "executor": {
            "ativo": True,
            "estado": ".memoria/executor",
            "isolamento": "git-worktree-branch-v1",
            "timeout_global_segundos": 900,
            "max_tentativas": 3,
            "backoff_segundos": 1,
            "lock_expira_segundos": 1200,
            "capacidades_permitidas": [],
            "mutacao_externa_padrao": "negada",
            "publicacao_automatica": False,
        },
        "avaliacao": {
            "ativo": True,
            "corpus": "docs/avaliacao/casos-rag-v1.json",
            "baseline": "docs/politicas/baseline-rag-v1.json",
            "relatorio": "docs/gerado/relatorio-avaliacao-rag-v1.json",
            "manifesto": "docs/gerado/manifesto-avaliacao-rag-v1.json",
            "min_hit_1": 0.5,
            "min_hit_3": 1.0,
            "min_cobertura_citacao": 1.0,
            "min_cobertura_resposta": 1.0,
            "max_sem_fonte": 0.0,
            "min_negativos_ok": 1.0,
            "regressao_maxima": 0.0,
            "min_usos_promocao": 2,
        },
        "grafo": {
            "ativo": bancos_ativos,
            "obrigatorio": bancos_ativos,
            "ferramenta": "graphify" if bancos_ativos else None,
            "modo": "local",
            "comando": ["graphify"],
            "arquivo": "graphify-out/graph.json",
            "marcador": ".memoria/bancos/graphify.json",
            "extensoes_literais": [".sql"],
            "timeout_segundos": 900,
        },
        "autonomia": {
            "ativo": True,
            "revisao_humana_obrigatoria": False,
            "sem_evidencia": "indeterminado",
            "politica": "docs/politicas/AUTONOMIA.md",
        },
    }


def main(argv: list[str]) -> int:
    args: dict[str, str | bool] = {}
    invalidos: list[str] = []
    for a in argv:
        m = re.match(r"^--([a-z-]+)(?:=(.*))?$", a)
        if m:
            args[m.group(1)] = m.group(2) if m.group(2) is not None else True
        else:
            invalidos.append(a)

    desconhecidos = sorted(set(args) - {
        "projeto", "codigo", "sem-bancos", "adiar-bancos", "sem-agendamento",
        "sem-autoteste",
    })
    if desconhecidos or invalidos:
        nomes = [*(f"--{a}" for a in desconhecidos), *invalidos]
        print("Opção desconhecida: " + ", ".join(nomes))
        return 2

    # A raiz do projeto é o CWD. O nome nasce dessa pasta, salvo identidade já
    # consolidada em padrao.json ou nome explícito na primeira instalação.
    raiz_ = barras(os.getcwd())
    try:
        projeto = _nome_projeto(raiz_, args.get("projeto"))
    except ValueError as exc:
        print(f"Nome do projeto inválido: {exc}.")
        return 2

    try:
        codigo = _raiz_codigo(raiz_, args.get("codigo"))
    except ValueError as exc:
        print(f"Raiz do código inválida: {exc}.")
        return 2
    sem_bancos = bool(args.get("sem-bancos"))
    adiar_bancos = bool(args.get("adiar-bancos"))
    sem_agendamento = bool(args.get("sem-agendamento"))
    sem_autoteste = bool(args.get("sem-autoteste"))
    if sem_bancos and adiar_bancos:
        print("Use apenas um: `--sem-bancos` ou `--adiar-bancos`.")
        return 2
    bancos_ativos = not sem_bancos

    codigo_abs = (Path(raiz_) / codigo).resolve()
    if not codigo_abs.is_relative_to(Path(raiz_).resolve()):
        print(f"`--codigo={codigo}` sai da raiz do projeto. Escolha uma pasta interna.")
        return 2
    criados: list[str] = []
    existiam: list[str] = []
    ajustados: list[str] = []

    # ------------------------------------------------- publicar os stubs do pacote
    _publicar(Path(pacote()) / "stubs", Path(raiz_), criados, existiam)
    _fixar_workflow(raiz_, ajustados)
    _ignorar_estado_local(raiz_, ajustados, incluir_graphify=bancos_ativos)

    # Os provedores são decisão do padrão, não uma escolha repetida em cada projeto.
    run_idx = Path(raiz_) / "docs/runbooks/indexacao.md"
    if bancos_ativos and run_idx.is_file():
        t = run_idx.read_text(encoding="utf-8")
        run_idx.write_text(t.replace("<qual — Hindsight, pgvector, Qdrant...>", "hindsight"),
                           encoding="utf-8")

    # ------------------------------------------------------------------- árvore
    # git não versiona diretório vazio: sem .gitkeep a árvore some no clone e o
    # PROJETO.md nasce apontando para pastas que, para quem clonou, não existem.
    for d in ARVORE:
        p = Path(raiz_) / d
        p.mkdir(parents=True, exist_ok=True)
        guarda = p / ".gitkeep"
        if not guarda.is_file():
            guarda.write_text(GITKEEP, encoding="utf-8")

    # ------------------------------------------------------------- padrao.json
    # Nunca sobrescreva DECISÃO DE ALGUÉM — mas placeholder não é decisão de ninguém.
    # (Numa instalação real o nome de exemplo ficou e TODO derivado saiu carimbado
    # errado, com build verde.)
    arq_config = Path(raiz_) / "padrao.json"
    extensoes = _detectar_extensoes(raiz_, codigo)
    config_ = _config_nova(projeto, codigo, bancos_ativos, raiz_, extensoes)

    if not arq_config.is_file():
        arq_config.write_text(json.dumps(config_, ensure_ascii=False, indent=4) + "\n",
                              encoding="utf-8")
        criados.append(str(arq_config))
    else:
        try:
            atual = json.loads(arq_config.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            morre(f"`padrao.json` existe mas não é JSON válido: {e.msg}\n"
                  "Conserte ou apague o arquivo e rode de novo.\n")

        if str(atual.get("projeto", "")) in PLACEHOLDERS_PROJETO:
            atual["projeto"] = projeto
            ajustados.append(f"projeto → {projeto}")
        elif atual.get("projeto") != projeto:
            ajustados.append(f"projeto MANTIDO como `{atual['projeto']}` (já estava preenchido; "
                             f"você pediu `{projeto}` — se quis mesmo trocar, edite à mão)")

        if atual.get("gerado", {}).get("raiz") in ("", "src", None) and codigo != "src":
            atual.setdefault("gerado", {})["raiz"] = codigo
            ajustados.append(f"gerado.raiz → {codigo}")

        # O padrao.json publicado nasce com PHP apenas como fallback histórico. Quando
        # a árvore prova outra stack, a evidência do repositório decide sem pergunta.
        if (atual.get("gerado", {}).get("extensoes") == ["php"]
                and extensoes != ["php"]):
            atual.setdefault("gerado", {})["extensoes"] = extensoes
            ajustados.append("gerado.extensoes → " + ", ".join(extensoes))

        for secao in ("memoria", "grafo"):
            desejado = config_[secao]
            alvo = atual.setdefault(secao, {})
            for chave, valor in desejado.items():
                if chave not in alvo or chave in {"ativo", "obrigatorio", "ferramenta"}:
                    if alvo.get(chave) != valor:
                        alvo[chave] = valor
                        ajustados.append(f"{secao}.{chave} → {json.dumps(valor, ensure_ascii=False)}")
        if atual["memoria"].get("banco") in (None, "", "meu-projeto", "<NOME-DO-PROJETO>"):
            atual["memoria"]["banco"] = projeto
            ajustados.append(f"memoria.banco → {projeto}")
        if "docs/gerado/" in atual["memoria"].get("nucleo", []):
            atual["memoria"]["nucleo"] = [
                item for item in atual["memoria"]["nucleo"] if item != "docs/gerado/"
            ]
            ajustados.append("memoria.nucleo - docs/gerado/ (Graphify cobre o código)")
        indice_desejado = "externo" if bancos_ativos else None
        if atual.setdefault("acervos", {}).get("indice") != indice_desejado:
            atual["acervos"]["indice"] = indice_desejado
            ajustados.append(f"acervos.indice → {indice_desejado or 'null'}")
        if "ponteiros" not in atual:
            atual["ponteiros"] = config_["ponteiros"]
            ajustados.append("ponteiros → " + ", ".join(config_["ponteiros"]["arquivos"]))
        else:
            atual["ponteiros"]["arquivos"] = [
                p for p in atual["ponteiros"].get("arquivos", [])
                if (Path(raiz_) / p).is_file()
            ]

        # O stub comentado é publicado antes de chegar aqui. Ele nasceu sem estas
        # exclusões, embora `_templates` e `_arquivo` estejam fora da régua estrutural.
        # Complete apenas o contador padrão ainda não personalizado.
        for contador in atual.get("catraca", {}).get("contadores", []):
            if (contador.get("chave") == "docs_sem_frontmatter"
                    and "excluir" not in contador):
                contador["excluir"] = ["docs/_arquivo/", "docs/_templates/"]
                ajustados.append("catraca.docs_sem_frontmatter.excluir → templates e arquivo")

        if "autonomia" not in atual:
            atual["autonomia"] = config_["autonomia"]
            ajustados.append("autonomia → protocolo sem revisão humana obrigatória")

        if "rag" not in atual:
            atual["rag"] = config_["rag"]
            ajustados.append("rag → manifesto determinístico em modo sombra")
        else:
            for chave in ("manifesto", "algoritmo"):
                if atual["rag"].get(chave) != config_["rag"][chave]:
                    atual["rag"][chave] = config_["rag"][chave]
                    ajustados.append(f"rag.{chave} → {config_['rag'][chave]}")

        if "contexto" not in atual:
            atual["contexto"] = config_["contexto"]
            ajustados.append("contexto → gateway neutro read-only")

        if "seguranca_memoria" not in atual:
            atual["seguranca_memoria"] = config_["seguranca_memoria"]
            ajustados.append("seguranca_memoria → classificação, escopo e redaction da Fase 4")

        if "adaptadores" not in atual:
            atual["adaptadores"] = config_["adaptadores"]
            ajustados.append("adaptadores → cinco clientes a partir do manifesto neutro")

        if "ciclo" not in atual:
            atual["ciclo"] = config_["ciclo"]
            ajustados.append("ciclo → início auto-reparável e atualização comum a todos os agentes")
        else:
            for chave, valor in config_["ciclo"].items():
                if chave not in atual["ciclo"]:
                    atual["ciclo"][chave] = valor
                    ajustados.append(
                        f"ciclo.{chave} → {json.dumps(valor, ensure_ascii=False)}"
                    )

        if "agendamento" not in atual:
            atual["agendamento"] = config_["agendamento"]
            ajustados.append("agendamento → atualização diária fechada e sem banco de negócio")
        else:
            for chave, valor in config_["agendamento"].items():
                if chave not in atual["agendamento"]:
                    atual["agendamento"][chave] = valor
                    ajustados.append(
                        f"agendamento.{chave} → {json.dumps(valor, ensure_ascii=False)}"
                    )

        if "executor" not in atual:
            atual["executor"] = config_["executor"]
            ajustados.append("executor → runs idempotentes em worktree isolada")
        else:
            for chave, valor in config_["executor"].items():
                if chave not in atual["executor"]:
                    atual["executor"][chave] = valor
                    ajustados.append(f"executor.{chave} → {json.dumps(valor, ensure_ascii=False)}")

        if "avaliacao" not in atual:
            atual["avaliacao"] = config_["avaliacao"]
            ajustados.append("avaliacao → corpus, baseline e catraca RAG da Fase 6")
        else:
            for chave, valor in config_["avaliacao"].items():
                if chave not in atual["avaliacao"]:
                    atual["avaliacao"][chave] = valor
                    ajustados.append(
                        f"avaliacao.{chave} → {json.dumps(valor, ensure_ascii=False)}"
                    )

        extratores = atual.setdefault("gerado", {}).setdefault("extratores", [])
        for nome in ("diagnostico-projeto", "analise-inicial", "cobertura-codigo"):
            if nome not in extratores:
                extratores.append(nome)
                ajustados.append(f"gerado.extratores + {nome}")

        if ajustados:
            arq_config.write_text(json.dumps(atual, ensure_ascii=False, indent=4) + "\n",
                                  encoding="utf-8")
        else:
            existiam.append(str(arq_config))

    # ---------------------------------------------- modelo de cronologia → mês real
    mes = date.today().strftime("%Y-%m")
    modelo_cr = Path(raiz_) / "docs/cronologia/AAAA-MM.md"
    mes_cr = Path(raiz_) / f"docs/cronologia/{mes}.md"

    if modelo_cr.is_file() and not mes_cr.is_file():
        texto = modelo_cr.read_text(encoding="utf-8")
        texto = texto.replace("AAAA-MM", mes).replace("<mês> de <ano>", mes)
        mes_cr.write_text(texto, encoding="utf-8")
        modelo_cr.unlink()
        if str(modelo_cr) in criados:
            criados.remove(str(modelo_cr))
        criados.append(str(mes_cr))
    # o mês já existia (todo projeto vivo tem) → o modelo publicado sairia órfão
    if modelo_cr.is_file() and mes_cr.is_file():
        modelo_cr.unlink()
        if str(modelo_cr) in criados:
            criados.remove(str(modelo_cr))

    if not mes_cr.is_file():
        mes_cr.write_text(
            f"---\nid: CRONOLOGIA-{mes}\ntipo: cronologia\nprojeto: {projeto}\n"
            f"titulo: Cronologia — {mes}\nstatus: rascunho\n---\n\n"
            f"# Cronologia — {mes}\n\n"
            "> **Append-only.** Entradas antigas não são editadas — correção entra como entrada\n"
            "> nova referenciando a anterior. Mais recente no topo.\n\n---\n\n",
            encoding="utf-8")
        criados.append(str(mes_cr))

    # ------------------------------------- placeholder → nome real (idempotente)
    trocados: list[str] = []
    for md in markdowns(str(Path(raiz_) / "docs")):
        texto = Path(md).read_text(encoding="utf-8")
        if "<NOME-DO-PROJETO>" not in texto:
            continue
        Path(md).write_text(texto.replace("<NOME-DO-PROJETO>", projeto), encoding="utf-8")
        trocados.append(barras(md).replace(raiz_ + "/", ""))

    faltando = [f"docs/{e}.md" for e in ("PROJETO", "ESTADO", "ABERTO", "GLOSSARIO")
                if not (Path(raiz_) / f"docs/{e}.md").is_file()]

    # O corpus é fonte versionada e nasce separado dos derivados. Nunca sobrescreva um
    # conjunto já curado pelo projeto; a instalação só cria o mínimo mensurável.
    corpus_avaliacao = Path(raiz_) / "docs/avaliacao/casos-rag-v1.json"
    if not corpus_avaliacao.is_file():
        corpus_avaliacao.parent.mkdir(parents=True, exist_ok=True)
        corpus_avaliacao.write_text(json.dumps({
            "schema": 1,
            "projeto": projeto,
            "casos": [
                {
                    "id": "engenharia-autoridade",
                    "categoria": "engenharia",
                    "perfil": "engenharia-leitura",
                    "pergunta": "qual é a regra operacional sobre autoridade da documentação e ação externa?",
                    "resposta_esperada": "A documentação orienta, mas o comportamento é confirmado nas fontes; ação externa mantém autorização separada.",
                    "fontes_esperadas": ["docs/PROJETO.md"],
                    "fontes_proibidas": [],
                    "termos_esperados": ["Documentação não é autoridade", "ação externa"],
                    "espera_sem_fonte": False,
                },
                {
                    "id": "automacao-cron",
                    "categoria": "automacao",
                    "perfil": "automacao-codigo",
                    "pergunta": "como a execução por cron isola a documentação com checkpoints e worktree?",
                    "resposta_esperada": "O executor usa lock, checkpoints e worktree própria sem criar commit nem publicar.",
                    "fontes_esperadas": ["docs/runbooks/documentacao-autonoma.md"],
                    "fontes_proibidas": [],
                    "termos_esperados": ["checkpoints", "worktree"],
                    "espera_sem_fonte": False,
                },
                {
                    "id": "atendimento-isolamento",
                    "categoria": "atendimento",
                    "perfil": "atendimento",
                    "produto": "exemplo",
                    "tenant": "exemplo",
                    "pergunta": "segredo interno de arquitetura ultravioleta",
                    "resposta_esperada": "Sem fonte pública no escopo, a resposta deve declarar cobertura ausente.",
                    "fontes_esperadas": [],
                    "fontes_proibidas": ["docs/PROJETO.md", "docs/arquitetura/"],
                    "termos_esperados": [],
                    "espera_sem_fonte": True,
                },
            ],
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        criados.append(str(corpus_avaliacao))
    else:
        existiam.append(str(corpus_avaliacao))

    # -------------------------------------------- provedores locais auto-gerenciados
    if bancos_ativos and not adiar_bancos:
        from . import provisao
        try:
            provisao.garantir()
        except provisao.ProvisaoErro as exc:
            print(f"\nA estrutura foi instalada, mas os provedores locais não ficaram prontos: {exc}")
            return 1

    # ------------------------------------------------ documentação autônoma inicial
    from . import documentar
    iniciais = {
        nome for nome in documentar.NUCLEO
        if barras(str(Path(raiz_) / "docs" / nome)) in {barras(p) for p in criados}
    }
    rc_documentar = documentar.executar(
        substituir_iniciais=iniciais,
        sincronizar_bancos=not adiar_bancos,
        inicializar_avaliacao=True,
    )
    if rc_documentar != 0:
        print("\nA estrutura foi instalada, mas a documentação autônoma não validou.")
        return rc_documentar

    # A instalação precisa deixar a peça que os agentes usam pronta, e não apenas
    # ensinar um segundo comando ao operador. A catraca agregada é a mesma da CLI.
    rc_fechamento = _fechar_instalacao(
        incluir_bancos=not adiar_bancos,
        executar_autoteste=not sem_autoteste,
    )
    if rc_fechamento != 0:
        return rc_fechamento

    # O único job registrado chama o comando fechado da biblioteca. Ele atualiza docs,
    # Hindsight e Graphify, mas não recebe conexão nem comando para o banco da aplicação.
    if bancos_ativos and not adiar_bancos and not sem_agendamento:
        from . import agendador
        rc_agendamento, saida_agendamento = agendador.operar("instalar")
        if rc_agendamento != 0:
            print("\nA memória foi instalada, mas o agendamento diário não foi registrado: "
                  + str(saida_agendamento.get("erro") or "falha não detalhada"))
            return rc_agendamento
        ajustados.append(
            "agendamento diário → " + str(saida_agendamento.get("horario_local", "02:15"))
        )

    # ------------------------------------------------------------------- relatório
    print(f"\nEstrutura do padrão — {projeto}")
    print("─" * 60)
    if criados:
        print("\nCriados:")
        for c_ in sorted(criados):
            print("  + " + barras(c_).replace(raiz_ + "/", ""))
    if existiam:
        print("\nJá existiam, não toquei:")
        for c_ in sorted(existiam)[:15]:
            print("  = " + barras(c_).replace(raiz_ + "/", ""))
        if len(existiam) > 15:
            print(f"  = ... e mais {len(existiam) - 15}")
    if ajustados:
        print("\nAjustes aplicados:")
        for a in ajustados:
            print(f"  ~ {a}")
    if trocados:
        print("\nNome do projeto preenchido em:")
        for t in trocados:
            print(f"  ~ {t}")
    if faltando:
        print("\nATENÇÃO — faltam arquivos de entrada:")
        for f in faltando:
            print(f"  ! {f}")

    print("\n" + "─" * 60)
    print("INSTALAÇÃO AUTÔNOMA CONCLUÍDA:\n")
    print("  documentação, RAG, adaptadores, skill e catracas foram confirmados")
    if sem_autoteste:
        print("  autoteste não executado por `--sem-autoteste`")
    else:
        print("  autoteste aprovado em cópia temporária")
    if bancos_ativos:
        if adiar_bancos:
            print("  memoria bancos sincronizar  ← pendente por `--adiar-bancos`")
        else:
            print("  Hindsight local + Graphify foram sincronizados e verificados")
            if sem_agendamento:
                print("  agendamento diário não registrado por `--sem-agendamento`")
            else:
                print("  atualização diária da memória registrada para 02:15")
    print("\nNenhum outro comando de instalação é necessário. A verificação documental")
    print("não depende de aprovação humana. Fato sem prova fica")
    print("`indeterminado`; publicação e ação externa continuam exigindo autorização própria.")
    return 0
