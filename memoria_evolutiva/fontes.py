"""Seleção de fontes antes de qualquer leitura de conteúdo."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


EXEMPLOS_ENV = {".env.example", ".env.sample", ".env.template", ".env.dist"}
RUNTIME = (
    "bootstrap/cache/", "storage/framework/cache/", "storage/framework/sessions/",
    "storage/framework/views/", "storage/logs/",
)


def permitido(relativo: Path, ignorar: set[str]) -> bool:
    """Recusa caminhos de ambiente antes de abrir ou calcular hashes."""
    if relativo.is_absolute() or ".." in relativo.parts:
        return False
    for parte in relativo.parts:
        nome = parte.lower()
        if parte in ignorar or nome == ".phpunit.cache":
            return False
        if (nome == ".env" or nome.startswith(".env.")) and nome not in EXEMPLOS_ENV:
            return False
    if (relativo.as_posix().lower().startswith(RUNTIME)
            and relativo.name not in {".gitignore", ".gitkeep"}):
        return False
    return True


class FontesErro(OSError):
    """A seleção não pôde ser provada; não autoriza uma varredura mais ampla."""


def _candidatos_git(base: Path) -> list[Path] | None:
    tem_git = any((p / ".git").exists() or (p / ".git").is_symlink()
                  for p in (base, *base.parents))
    env = os.environ.copy()
    # A seleção pertence ao projeto, não ao índice/working tree de um shell pai.
    for nome in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"):
        env.pop(nome, None)
    env.update(LC_ALL="C", GIT_OPTIONAL_LOCKS="0")
    try:
        processo = subprocess.run(
            ["git", "-C", str(base), "ls-files", "-z", "--cached", "--others",
             "--exclude-standard", "--", "."],
            capture_output=True, timeout=30, env=env,
        )
    except FileNotFoundError as exc:
        if not tem_git:
            return None
        raise FontesErro("Git indisponível para selecionar as fontes do repositório") from exc
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise FontesErro("Git não concluiu a seleção de fontes") from exc
    if processo.returncode == 0:
        return [Path(os.fsdecode(p)) for p in processo.stdout.split(b"\0") if p]
    if not tem_git and b"not a git repository" in processo.stderr:
        return None
    raise FontesErro(f"Git recusou a seleção de fontes (saída {processo.returncode})")


def _candidatos_locais(base: Path, ignorar: set[str]) -> list[Path]:
    def erro(exc: OSError) -> None:
        raise FontesErro("Não foi possível enumerar as fontes locais") from exc

    encontrados = []
    for pasta, dirs, nomes in os.walk(base, followlinks=False, onerror=erro):
        local = Path(pasta)
        dirs[:] = [d for d in dirs if permitido(Path(d), ignorar)
                   and not (local / d).is_symlink()]
        encontrados.extend((local / nome).relative_to(base) for nome in nomes)
    return encontrados


def arquivos(base: Path, ignorar: set[str]) -> list[Path]:
    """Mantém fontes novas, mas não inclui arquivos ignorados pelo Git."""
    base = base.resolve()
    relativos = _candidatos_git(base)
    if relativos is None:
        relativos = _candidatos_locais(base, ignorar)
    encontrados = []
    for relativo in set(relativos):
        if not permitido(relativo, ignorar):
            continue
        # Um diretório rastreado pode ter sido substituído por link no working tree.
        if any((base / Path(*relativo.parts[:i])).is_symlink()
               for i in range(1, len(relativo.parts) + 1)):
            continue
        arquivo = base / relativo
        if not arquivo.resolve().is_relative_to(base) or not arquivo.is_file():
            continue
        encontrados.append(arquivo)
    return sorted(encontrados, key=lambda p: (p.relative_to(base).as_posix().lower(),
                                              p.relative_to(base).as_posix()))
