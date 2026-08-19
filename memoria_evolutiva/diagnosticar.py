"""diagnosticar — inventário factual, determinístico e sem escrita no projeto."""

from __future__ import annotations

import json
import subprocess
from collections import Counter
from functools import lru_cache
from pathlib import Path

from .lib import barras, config, identidade_arquivo, raiz, sha256_canonico


PULAR = {
    ".git", ".idea", ".memoria", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".venv", ".vscode", "__pycache__", "build", "coverage", "dist",
    "node_modules", "skill-memoria-evolutiva", "vendor", "venv", "graphify-out",
}

MANIFESTOS = (
    "pyproject.toml", "requirements.txt", "Pipfile", "poetry.lock",
    "composer.json", "composer.lock", "package.json", "package-lock.json",
    "pnpm-lock.yaml", "yarn.lock", "Cargo.toml", "go.mod", "pom.xml",
    "build.gradle", "build.gradle.kts", "Gemfile", "mix.exs",
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml",
    "compose.yaml",
)

CATEGORIAS = {
    "testes": {"test", "tests", "spec", "specs", "__tests__"},
    "migracoes": {"migration", "migrations", "migracao", "migracoes"},
    "rotas": {"route", "routes", "router", "routers", "rotas"},
    "controladores": {"controller", "controllers", "controlador", "controladores"},
    "modelos": {"model", "models", "entity", "entities", "modelo", "modelos"},
    "servicos": {"service", "services", "servico", "servicos"},
    "filas_jobs": {"job", "jobs", "queue", "queues", "worker", "workers"},
    "configuracao": {"config", "configuration", "settings"},
}


@lru_cache(maxsize=1)
def _arquivos() -> list[Path]:
    base = Path(raiz())
    encontrados = []
    for arquivo in base.rglob("*"):
        if not arquivo.is_file() or arquivo.is_symlink():
            continue
        rel = arquivo.relative_to(base)
        if any(parte in PULAR for parte in rel.parts):
            continue
        encontrados.append(arquivo)
    return sorted(encontrados, key=lambda p: barras(str(p.relative_to(base))).lower())


def _git(*args: str) -> str:
    try:
        r = subprocess.run(
            ["git", "-C", raiz(), *args], capture_output=True, text=True, timeout=15
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


@lru_cache(maxsize=1)
def inventario_projeto() -> list[dict[str, str | int]]:
    """Lê e identifica todos os arquivos relevantes do repositório.

    O acervo canônico e diretórios descartáveis ficam fora para evitar autorreferência.
    O hash prova o conteúdo canônico, normalizando apenas LF/CRLF em texto UTF-8.
    """
    c = config()
    base = Path(raiz())
    acervo = (base / c.get("acervos", {}).get("canonico", "docs").strip("/")).resolve()
    raiz_codigo = (base / c.get("gerado", {}).get("raiz", "").strip("/")).resolve()
    codigo_dentro_do_acervo = raiz_codigo.is_relative_to(acervo)
    itens: list[dict[str, str | int]] = []
    for arquivo in _arquivos():
        resolvido = arquivo.resolve()
        if (resolvido.is_relative_to(acervo)
                and not (codigo_dentro_do_acervo
                         and resolvido.is_relative_to(raiz_codigo))):
            continue
        tamanho, digest = identidade_arquivo(arquivo)
        itens.append({
            "arquivo": barras(str(arquivo.relative_to(base))),
            "bytes": tamanho,
            "sha256": digest,
        })
    return itens


@lru_cache(maxsize=1)
def inventario_codigo() -> list[dict[str, str | int]]:
    """Recorta do inventário total as fontes da raiz e extensões configuradas."""
    c = config()
    base = Path(raiz())
    raiz_codigo = (base / c.get("gerado", {}).get("raiz", "").strip("/")).resolve()
    extensoes = {
        "." + str(ext).lower().lstrip(".")
        for ext in c.get("gerado", {}).get("extensoes", [])
    }
    return [
        item for item in inventario_projeto()
        if (base / str(item["arquivo"])).resolve().is_relative_to(raiz_codigo)
        and Path(str(item["arquivo"])).suffix.lower() in extensoes
    ]


def coletar(incluir_estado_trabalho: bool = True) -> dict:
    """Coleta apenas fatos observáveis; não interpreta regra de negócio."""
    c = config()
    base = Path(raiz())
    inventario_total = inventario_projeto()
    arquivos = [base / str(item["arquivo"]) for item in inventario_total]
    relativos = [barras(str(a.relative_to(base))) for a in arquivos]
    inventario = inventario_codigo()
    extensoes_codigo = {
        "." + str(ext).lower().lstrip(".")
        for ext in c.get("gerado", {}).get("extensoes", [])
    }
    por_extensao = Counter(
        Path(str(item["arquivo"])).suffix.lower() or "(sem extensão)"
        for item in inventario
    )

    arquivos_codigo = [base / str(item["arquivo"]) for item in inventario]

    dirs_por_categoria: dict[str, list[str]] = {}
    for categoria, nomes in CATEGORIAS.items():
        achados = {
            barras(str(Path(*rel.parts[:i + 1])))
            for arquivo in arquivos_codigo
            for rel in [arquivo.relative_to(base)]
            for i, parte in enumerate(rel.parts[:-1])
            if parte.lower() in nomes
        }
        dirs_por_categoria[categoria] = sorted(achados)

    workflows = sorted(
        rel for rel in relativos
        if rel.startswith(".github/workflows/") and Path(rel).suffix.lower() in {".yml", ".yaml"}
    )
    testes = sorted(
        rel for rel in relativos
        if any(parte.lower() in CATEGORIAS["testes"] for parte in Path(rel).parts)
        or Path(rel).stem.lower().startswith("test_")
        or Path(rel).stem.lower().endswith("_test")
    )

    status = _git("status", "--porcelain") if incluir_estado_trabalho else ""
    return {
        "schema": 1,
        "projeto": c["projeto"],
        "git": {
            "branch": _git("branch", "--show-current"),
            "commit": _git("rev-parse", "--short", "HEAD"),
            "alterado": bool(status) if incluir_estado_trabalho else None,
        },
        "codigo": {
            "raiz": c.get("gerado", {}).get("raiz", ""),
            "extensoes_configuradas": sorted(ext.lstrip(".") for ext in extensoes_codigo),
            "arquivos": sum(por_extensao.values()),
            "por_extensao": dict(sorted(por_extensao.items())),
            "cobertura_sha256": sha256_canonico(
                "\n".join(
                    f"{item['arquivo']}:{item['sha256']}" for item in inventario
                )
            ),
        },
        "repositorio": {
            "arquivos_considerados_no_inventario": len(arquivos),
            "cobertura_sha256": sha256_canonico(
                "\n".join(
                    f"{item['arquivo']}:{item['sha256']}" for item in inventario_total
                )
            ),
            "manifestos": [nome for nome in MANIFESTOS if (base / nome).is_file()],
            "workflows": workflows,
            "arquivos_de_teste": len(testes),
            "diretorios_relevantes": dirs_por_categoria,
        },
    }


def como_markdown(d: dict, mostrar_git: bool = True) -> str:
    codigo = d["codigo"]
    repo = d["repositorio"]
    git = d["git"]
    linhas = ["Inventário factual do repositório. Não infere regra de negócio nem intenção.\n"]
    if mostrar_git:
        linhas.extend([
            "## Versão observada\n",
            f"- Branch: `{git['branch'] or '(sem git)'}`",
            f"- Commit: `{git['commit'] or '(sem commit)'}`",
            f"- Árvore alterada: `{'sim' if git['alterado'] else 'não'}`\n",
        ])
    linhas.extend([
        "## Código configurado\n",
        f"- Raiz: `{codigo['raiz'] or '.'}`",
        f"- Arquivos nas extensões configuradas: **{codigo['arquivos']}**",
    ])
    for ext, total in codigo["por_extensao"].items():
        linhas.append(f"  - `{ext}`: {total}")
    linhas.extend([
        "\n## Sinais do repositório\n",
        "- Manifestos: " + (", ".join(f"`{m}`" for m in repo["manifestos"]) or "nenhum detectado"),
        f"- Workflows de CI: {len(repo['workflows'])}",
        f"- Arquivos de teste detectados: {repo['arquivos_de_teste']}",
        f"- Arquivos considerados no inventário: {repo['arquivos_considerados_no_inventario']}\n",
        "## Diretórios relevantes detectados\n",
        "| Categoria | Diretórios |",
        "|---|---|",
    ])
    for categoria, dirs in repo["diretorios_relevantes"].items():
        valor = ", ".join(f"`{d}`" for d in dirs) if dirs else "—"
        linhas.append(f"| {categoria.replace('_', ' ')} | {valor} |")
    linhas.extend([
        "\n## Limite desta evidência\n",
        "Este diagnóstico prova estrutura observável. Objetivo, usuários, regras de",
        "negócio, ambientes, riscos e motivos arquiteturais precisam ser confirmados",
        "contra fontes primárias verificáveis; sem evidência, ficam indeterminados.",
    ])
    return "\n".join(linhas).rstrip() + "\n"


def main(argv: list[str]) -> int:
    desconhecidos = [a for a in argv if a != "--json"]
    if desconhecidos:
        print("Opção desconhecida em `memoria diagnosticar`: " + ", ".join(desconhecidos))
        return 2
    diagnostico = coletar()
    if "--json" in argv:
        print(json.dumps(diagnostico, ensure_ascii=False, indent=2))
    else:
        print(como_markdown(diagnostico), end="")
    return 0
