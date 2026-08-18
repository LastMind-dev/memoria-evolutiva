"""Executor não interativo, idempotente e sem shell arbitrário.

Cada ``run_id`` fica ligado ao commit-base, à ação e às capacidades solicitadas. A
execução acontece numa branch/worktree própria; o repositório de origem recebe somente
estado local ignorado pelo Git. Commit, push e publicação não fazem parte deste módulo.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import __version__, seguranca
from .lib import config, raiz


SCHEMA = 1
ACOES = {"documentar", "verificar"}
CAPACIDADES = {"sincronizar-bancos"}
RUN_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
SAIDA_OK = 0
SAIDA_FALHA = 1
SAIDA_USO = 2
SAIDA_CONFIGURACAO = 3
SAIDA_LOCK = 73
SAIDA_INTERROMPIDO = 75
SAIDA_TIMEOUT = 124


class ExecutorErro(RuntimeError):
    codigo = SAIDA_FALHA


class ExecutorConfiguracaoErro(ExecutorErro):
    codigo = SAIDA_CONFIGURACAO


class ExecutorLockErro(ExecutorErro):
    codigo = SAIDA_LOCK


class ExecutorInterrompido(ExecutorErro):
    codigo = SAIDA_INTERROMPIDO


class ExecutorTimeout(ExecutorErro):
    codigo = SAIDA_TIMEOUT


class ExecutorEtapaErro(ExecutorErro):
    def __init__(self, mensagem: str, resultado: dict):
        super().__init__(mensagem)
        self.resultado = resultado


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cfg() -> dict:
    valor = config().get("executor", {})
    if not isinstance(valor, dict) or valor.get("ativo") is not True:
        raise ExecutorConfiguracaoErro(
            "executor ausente ou desativado; rode `memoria instalar` com a versão atual"
        )
    esperados = {
        "estado": ".memoria/executor",
        "isolamento": "git-worktree-branch-v1",
        "publicacao_automatica": False,
        "mutacao_externa_padrao": "negada",
    }
    for chave, esperado in esperados.items():
        if valor.get(chave) != esperado:
            raise ExecutorConfiguracaoErro(
                f"`executor.{chave}` precisa ser {esperado!r}"
            )
    for chave, padrao, minimo, maximo in (
        ("timeout_global_segundos", 900, 1, 86400),
        ("max_tentativas", 3, 1, 10),
        ("backoff_segundos", 1, 0, 300),
        ("lock_expira_segundos", 1200, 30, 172800),
    ):
        item = valor.get(chave, padrao)
        if isinstance(item, bool) or not isinstance(item, int) or not minimo <= item <= maximo:
            raise ExecutorConfiguracaoErro(
                f"`executor.{chave}` precisa ser inteiro entre {minimo} e {maximo}"
            )
    permitidas = valor.get("capacidades_permitidas", [])
    if (not isinstance(permitidas, list)
            or any(not isinstance(item, str) for item in permitidas)
            or len(permitidas) != len(set(permitidas))
            or set(permitidas) - CAPACIDADES):
        raise ExecutorConfiguracaoErro(
            "`executor.capacidades_permitidas` contém capacidade inválida ou duplicada"
        )
    if valor.get("lock_expira_segundos", 1200) <= valor.get("timeout_global_segundos", 900):
        raise ExecutorConfiguracaoErro(
            "`executor.lock_expira_segundos` precisa superar o timeout global"
        )
    return valor


def _base() -> Path:
    return Path(raiz()).resolve()


def _estado_dir() -> Path:
    base = _base()
    destino = (base / str(_cfg()["estado"]).strip("/")).resolve()
    if not destino.is_relative_to(base) or destino == base:
        raise ExecutorConfiguracaoErro("`executor.estado` precisa ficar dentro do projeto")
    return destino


def _estado_path(run_id: str) -> Path:
    return _estado_dir() / "runs" / f"{run_id}.json"


def _patch_path(run_id: str) -> Path:
    return _estado_dir() / "runs" / f"{run_id}.patch"


def _worktree_path(run_id: str) -> Path:
    return _estado_dir() / "worktrees" / run_id


def _branch(run_id: str) -> str:
    seguro = re.sub(r"[^a-z0-9-]+", "-", run_id).strip("-")[:36] or "run"
    sufixo = hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:10]
    return f"memoria/run-{seguro}-{sufixo}"


def _json_atomico(destino: Path, dados: dict) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", prefix=f".{destino.name}.",
            suffix=".tmp", dir=destino.parent, delete=False,
        ) as arquivo:
            json.dump(dados, arquivo, ensure_ascii=False, indent=2, sort_keys=True)
            arquivo.write("\n")
            arquivo.flush()
            os.fsync(arquivo.fileno())
            temporario = Path(arquivo.name)
        os.replace(temporario, destino)
        temporario = None
    finally:
        if temporario is not None:
            temporario.unlink(missing_ok=True)


def _bytes_atomico(destino: Path, dados: bytes) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=f".{destino.name}.", suffix=".tmp",
            dir=destino.parent, delete=False,
        ) as arquivo:
            arquivo.write(dados)
            arquivo.flush()
            os.fsync(arquivo.fileno())
            temporario = Path(arquivo.name)
        os.replace(temporario, destino)
        temporario = None
    finally:
        if temporario is not None:
            temporario.unlink(missing_ok=True)


def _git(cwd: Path, *args: str, timeout: float = 30) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["git", "-C", str(cwd), *args], capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=max(0.05, timeout),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ExecutorErro(f"Git indisponível: {exc}") from exc


def _git_ate(cwd: Path, prazo: float, *args: str) -> subprocess.CompletedProcess:
    restante = prazo - time.monotonic()
    if restante <= 0:
        raise ExecutorTimeout("timeout global esgotado antes da operação Git")
    try:
        return subprocess.run(
            ["git", "-C", str(cwd), *args], capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=restante,
        )
    except subprocess.TimeoutExpired as exc:
        raise ExecutorTimeout("timeout global atingido durante a operação Git") from exc
    except OSError as exc:
        raise ExecutorErro(f"Git indisponível: {exc}") from exc


def _commit_base() -> str:
    resultado = _git(_base(), "rev-parse", "HEAD")
    commit = resultado.stdout.strip()
    if resultado.returncode != 0 or not re.fullmatch(r"[0-9a-fA-F]{40}", commit):
        raise ExecutorConfiguracaoErro("executor exige repositório Git com commit HEAD")
    return commit.lower()


def _confirmar_estado_ignorado() -> None:
    candidato = str((_estado_dir() / "probe").relative_to(_base())).replace("\\", "/")
    resultado = _git(_base(), "check-ignore", "-q", "--", candidato)
    if resultado.returncode != 0:
        raise ExecutorConfiguracaoErro(
            "`.memoria/executor/` precisa estar ignorado pelo Git; rode `memoria instalar`"
        )


def _processo_vivo(pid: object) -> bool:
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return False
    if os.name == "nt":
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


class _Lock:
    def __init__(self, run_id: str, expira: int):
        self.path = _estado_dir() / "lock.json"
        self.run_id = run_id
        self.expira = expira
        self.token = uuid.uuid4().hex

    def _stale(self) -> bool:
        try:
            dados = json.loads(self.path.read_text(encoding="utf-8"))
            idade = time.time() - float(dados.get("timestamp", 0))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return self.path.is_file() and time.time() - self.path.stat().st_mtime > self.expira
        mesma_maquina = dados.get("host") == socket.gethostname()
        morto = mesma_maquina and not _processo_vivo(dados.get("pid"))
        return morto or idade > self.expira

    def __enter__(self) -> "_Lock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(2):
            try:
                descritor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                if self._stale():
                    try:
                        self.path.unlink()
                    except FileNotFoundError:
                        pass
                    continue
                try:
                    dono = json.loads(self.path.read_text(encoding="utf-8"))
                    resumo = f"run_id={dono.get('run_id')} pid={dono.get('pid')}"
                except (OSError, json.JSONDecodeError):
                    resumo = "dono indeterminado"
                raise ExecutorLockErro(f"execução concorrente bloqueada ({resumo})")
            with os.fdopen(descritor, "w", encoding="utf-8", newline="\n") as arquivo:
                json.dump({
                    "schema": 1,
                    "run_id": self.run_id,
                    "pid": os.getpid(),
                    "host": socket.gethostname(),
                    "token": self.token,
                    "timestamp": time.time(),
                    "iniciado_em": _agora(),
                }, arquivo, ensure_ascii=False, sort_keys=True)
                arquivo.write("\n")
                arquivo.flush()
                os.fsync(arquivo.fileno())
            return self
        raise ExecutorLockErro("não foi possível adquirir o lock do projeto")

    def heartbeat(self) -> None:
        try:
            dados = json.loads(self.path.read_text(encoding="utf-8"))
            if dados.get("token") != self.token:
                raise ExecutorLockErro("lock mudou de proprietário durante a execução")
            dados["timestamp"] = time.time()
            _json_atomico(self.path, dados)
        except (OSError, json.JSONDecodeError) as exc:
            raise ExecutorLockErro(f"lock ficou ilegível durante a execução: {exc}") from exc

    def __exit__(self, *_: object) -> None:
        try:
            dados = json.loads(self.path.read_text(encoding="utf-8"))
            if dados.get("token") == self.token:
                self.path.unlink(missing_ok=True)
        except (OSError, json.JSONDecodeError):
            pass


def _resumo_seguro(texto: str) -> str:
    if not texto.strip():
        return ""
    try:
        texto, _ = seguranca.redigir(texto)
    except seguranca.SegurancaErro:
        texto = "[SAIDA-OMITIDA-POR-POLITICA]"
    linhas = [linha.strip() for linha in texto.splitlines() if linha.strip()]
    return " | ".join(linhas[-8:])[-2000:]


def _rodar_com_retry(
    comando: list[str], cwd: Path, prazo: float, max_tentativas: int,
    backoff: int, ao_tentar: Callable[[], None] | None = None,
) -> dict:
    ultimo: dict = {}
    for tentativa in range(1, max_tentativas + 1):
        restante = prazo - time.monotonic()
        if restante <= 0:
            raise ExecutorTimeout("timeout global esgotado antes da etapa")
        if ao_tentar:
            ao_tentar()
        inicio = time.monotonic()
        try:
            processo = subprocess.run(
                comando, cwd=cwd, capture_output=True, timeout=restante,
            )
        except subprocess.TimeoutExpired as exc:
            raise ExecutorTimeout("timeout global atingido durante a etapa") from exc
        except OSError as exc:
            processo = None
            ultimo = {
                "tentativas": tentativa,
                "exit_code": None,
                "duracao_ms": round((time.monotonic() - inicio) * 1000),
                "resumo": f"processo indisponível: {exc}",
            }
        if processo is not None:
            stdout = processo.stdout or b""
            stderr = processo.stderr or b""
            combinado = (stdout + b"\n" + stderr).decode("utf-8", errors="replace")
            ultimo = {
                "tentativas": tentativa,
                "exit_code": processo.returncode,
                "duracao_ms": round((time.monotonic() - inicio) * 1000),
                "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
                "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
                "resumo": _resumo_seguro(combinado),
            }
            if processo.returncode == 0:
                return ultimo
        if tentativa < max_tentativas:
            espera = backoff * (2 ** (tentativa - 1))
            if time.monotonic() + espera >= prazo:
                raise ExecutorTimeout("timeout global esgotado durante o backoff")
            if espera:
                time.sleep(espera)
    raise ExecutorEtapaErro("etapa falhou após o limite de tentativas", ultimo)


def _garantir_worktree(estado: dict, prazo: float, cfg: dict, lock: _Lock) -> dict:
    base = _base()
    worktree = Path(estado["worktree"])
    branch = estado["branch"]
    if worktree.is_dir():
        verificado = _git_ate(worktree, prazo, "rev-parse", "--show-toplevel")
        branch_atual = _git_ate(worktree, prazo, "branch", "--show-current")
        commit_atual = _git_ate(worktree, prazo, "rev-parse", "HEAD")
        if not (
            verificado.returncode == 0
            and Path(verificado.stdout.strip()).resolve() == worktree.resolve()
            and branch_atual.returncode == 0
            and branch_atual.stdout.strip() == branch
            and commit_atual.returncode == 0
            and commit_atual.stdout.strip().lower() == estado["base_commit"]
        ):
            raise ExecutorErro(
                f"worktree existente não pertence ao branch/commit do run: {worktree}"
            )
        return {"reutilizado": True, "tentativas": 0, "exit_code": 0}
    if worktree.exists():
        raise ExecutorErro(f"caminho de worktree existe e não é diretório: {worktree}")
    referencia = _git_ate(base, prazo, "show-ref", "--verify", f"refs/heads/{branch}")
    if referencia.returncode == 0:
        commit_branch = _git_ate(base, prazo, "rev-parse", branch).stdout.strip().lower()
        if commit_branch != estado["base_commit"]:
            raise ExecutorErro("branch isolada existente não aponta para o commit-base do run")
        comando = ["git", "-C", str(base), "worktree", "add", str(worktree), branch]
    else:
        comando = [
            "git", "-C", str(base), "worktree", "add", "-b", branch,
            str(worktree), estado["base_commit"],
        ]
    return _rodar_com_retry(
        comando, base, prazo, cfg["max_tentativas"], cfg["backoff_segundos"], lock.heartbeat
    )


def _comando_documentar() -> list[str]:
    codigo = (
        "from memoria_evolutiva import documentar; "
        "raise SystemExit(documentar.executar(sincronizar_bancos=False))"
    )
    return [sys.executable, "-c", codigo]


def _comando_validar() -> list[str]:
    codigo = (
        "from memoria_evolutiva import validar,catraca,fragmentos,adaptadores,skill,avaliacao; "
        "raise SystemExit(max(validar.main(),catraca.main([]),fragmentos.verificar(),"
        "adaptadores.verificar(),skill.main(['--conferir']),avaliacao.verificar()))"
    )
    return [sys.executable, "-c", codigo]


def _comando_bancos() -> list[str]:
    return [sys.executable, "-m", "memoria_evolutiva", "bancos", "sincronizar"]


def _comando_avaliar() -> list[str]:
    return [sys.executable, "-m", "memoria_evolutiva", "avaliar", "gerar"]


def _registrar_diff(estado: dict, prazo: float, cfg: dict, lock: _Lock) -> dict:
    worktree = Path(estado["worktree"])
    adicionado = _rodar_com_retry(
        ["git", "-C", str(worktree), "add", "-A"], worktree, prazo,
        cfg["max_tentativas"], cfg["backoff_segundos"], lock.heartbeat,
    )
    restante = prazo - time.monotonic()
    if restante <= 0:
        raise ExecutorTimeout("timeout global esgotado antes de produzir o diff")
    try:
        patch = subprocess.run(
            ["git", "-C", str(worktree), "diff", "--cached", "--binary", "--no-ext-diff"],
            capture_output=True, timeout=restante,
        )
    except subprocess.TimeoutExpired as exc:
        raise ExecutorTimeout("timeout global atingido ao produzir o diff") from exc
    except OSError as exc:
        raise ExecutorErro(f"Git indisponível ao produzir o diff: {exc}") from exc
    if patch.returncode != 0:
        raise ExecutorEtapaErro("Git não conseguiu produzir o diff", {
            "exit_code": patch.returncode,
            "resumo": _resumo_seguro((patch.stderr or b"").decode("utf-8", errors="replace")),
        })
    restante = prazo - time.monotonic()
    if restante <= 0:
        raise ExecutorTimeout("timeout global esgotado antes de listar o diff")
    try:
        nomes = subprocess.run(
            ["git", "-C", str(worktree), "diff", "--cached", "--name-only", "-z"],
            capture_output=True, timeout=restante,
        )
    except subprocess.TimeoutExpired as exc:
        raise ExecutorTimeout("timeout global atingido ao listar o diff") from exc
    except OSError as exc:
        raise ExecutorErro(f"Git indisponível ao listar o diff: {exc}") from exc
    if nomes.returncode != 0:
        raise ExecutorEtapaErro("Git não conseguiu listar o diff", {"exit_code": nomes.returncode})
    arquivos = sorted(filter(None, nomes.stdout.decode("utf-8", errors="replace").split("\0")))
    destino = _patch_path(estado["run_id"])
    _bytes_atomico(destino, patch.stdout)
    return {
        **adicionado,
        "patch": str(destino),
        "patch_sha256": hashlib.sha256(patch.stdout).hexdigest(),
        "bytes": len(patch.stdout),
        "arquivos": arquivos,
    }


def _plano(acao: str, capacidades: list[str]) -> list[str]:
    if acao == "verificar":
        return ["executar-acao"]
    etapas = ["preparar-worktree", "executar-acao"]
    if acao == "documentar":
        etapas.append("validar")
    etapas.append("registrar-diff")
    if "sincronizar-bancos" in capacidades:
        etapas.extend([
            "sincronizar-bancos", "avaliar-pos-sincronizacao", "registrar-diff-final",
        ])
    return etapas


def _estado_novo(run_id: str, acao: str, capacidades: list[str], base_commit: str) -> dict:
    agora = _agora()
    escrita = acao == "documentar"
    return {
        "schema": SCHEMA,
        "motor_versao": __version__,
        "projeto": str(config()["projeto"]),
        "run_id": run_id,
        "acao": acao,
        "capacidades_solicitadas": capacidades,
        "base_commit": base_commit,
        "branch": _branch(run_id) if escrita else None,
        "worktree": str(_worktree_path(run_id) if escrita else _base()),
        "isolamento": "git-worktree-branch-v1" if escrita else "raiz-somente-leitura",
        "plano": _plano(acao, capacidades),
        "status": "pendente",
        "exit_code": None,
        "checkpoint_atual": None,
        "checkpoints": {},
        "diff": None,
        "erro": None,
        "criado_em": agora,
        "atualizado_em": agora,
    }


def _validar_estado(estado: object, run_id: str, acao: str,
                    capacidades: list[str], commit_atual: str) -> dict:
    """Recusa estado adulterado antes que ele possa escolher caminhos ou checkpoints."""
    if not isinstance(estado, dict):
        raise ExecutorConfiguracaoErro("estado do run precisa ser um objeto JSON")
    identidade = (
        estado.get("schema"), estado.get("motor_versao"),
        estado.get("run_id"), estado.get("acao"),
        estado.get("capacidades_solicitadas"),
    )
    esperada = (SCHEMA, __version__, run_id, acao, capacidades)
    if identidade != esperada:
        raise ExecutorConfiguracaoErro(
            "run_id já pertence a outra ação, capacidade ou versão de contrato"
        )

    escrita = acao == "documentar"
    invariantes = {
        "projeto": str(config()["projeto"]),
        "branch": _branch(run_id) if escrita else None,
        "worktree": str(_worktree_path(run_id) if escrita else _base()),
        "isolamento": "git-worktree-branch-v1" if escrita else "raiz-somente-leitura",
        "plano": _plano(acao, capacidades),
    }
    divergentes = [
        chave for chave, esperado in invariantes.items()
        if estado.get(chave) != esperado
    ]
    if divergentes:
        raise ExecutorConfiguracaoErro(
            "estado do run viola invariantes do executor: " + ", ".join(divergentes)
        )

    base_commit = estado.get("base_commit")
    if not isinstance(base_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", base_commit):
        raise ExecutorConfiguracaoErro("estado do run contém commit-base inválido")
    existe = _git(_base(), "cat-file", "-e", f"{base_commit}^{{commit}}")
    if existe.returncode != 0:
        raise ExecutorConfiguracaoErro("commit-base do run não existe mais no repositório")
    if not escrita and estado.get("status") != "concluido" and base_commit != commit_atual:
        raise ExecutorConfiguracaoErro(
            "run de verificação interrompido pertence a outro HEAD; use um novo run_id"
        )

    plano = invariantes["plano"]
    checkpoints = estado.get("checkpoints")
    if not isinstance(checkpoints, dict):
        raise ExecutorConfiguracaoErro("checkpoints do run precisam ser um objeto")
    concluidos = list(checkpoints)
    if set(concluidos) != set(plano[:len(concluidos)]):
        raise ExecutorConfiguracaoErro(
            "checkpoints do run não formam um prefixo válido do plano"
        )
    status = estado.get("status")
    if status not in {"pendente", "executando", "interrompido", "falhou", "concluido"}:
        raise ExecutorConfiguracaoErro("status persistido do run é inválido")
    if status == "concluido" and (
        len(concluidos) != len(plano)
        or set(concluidos) != set(plano)
        or estado.get("exit_code") != SAIDA_OK
    ):
        raise ExecutorConfiguracaoErro("run concluído não possui todos os checkpoints")
    return estado


def _carregar_ou_criar(run_id: str, acao: str, capacidades: list[str]) -> dict:
    caminho = _estado_path(run_id)
    base_commit = _commit_base()
    if caminho.is_file():
        try:
            estado = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ExecutorErro(f"estado do run está corrompido: {exc}") from exc
        return _validar_estado(estado, run_id, acao, capacidades, base_commit)
    estado = _estado_novo(run_id, acao, capacidades, base_commit)
    _json_atomico(caminho, estado)
    return estado


def _salvar(estado: dict) -> None:
    estado["atualizado_em"] = _agora()
    _json_atomico(_estado_path(str(estado["run_id"])), estado)


def _resposta(estado: dict, replay: bool = False) -> dict:
    return {
        **estado,
        "ok": estado.get("status") == "concluido",
        "replay": replay,
        "publicado": False,
        "commit_criado": False,
        "mutacoes_externas": (
            ["sincronizar-bancos"]
            if "sincronizar-bancos" in estado.get("checkpoints", {}) else []
        ),
    }


def executar(run_id: str, acao: str, capacidades: list[str]) -> tuple[int, dict]:
    cfg = _cfg()
    _confirmar_estado_ignorado()
    if acao == "verificar" and capacidades:
        raise ExecutorConfiguracaoErro(
            "a ação `verificar` é somente leitura e não aceita capacidades de mutação"
        )
    permitidas = set(cfg.get("capacidades_permitidas", []))
    if set(capacidades) - permitidas:
        negadas = sorted(set(capacidades) - permitidas)
        raise ExecutorConfiguracaoErro(
            "capacidade não pré-concedida em `padrao.json`: " + ", ".join(negadas)
        )
    estado = _carregar_ou_criar(run_id, acao, capacidades)
    if estado.get("status") == "concluido":
        return SAIDA_OK, _resposta(estado, replay=True)

    prazo = time.monotonic() + cfg.get("timeout_global_segundos", 900)
    with _Lock(run_id, cfg.get("lock_expira_segundos", 1200)) as lock:
        estado["status"] = "executando"
        estado["exit_code"] = None
        estado["erro"] = None
        _salvar(estado)
        try:
            for etapa in estado["plano"]:
                if etapa in estado["checkpoints"]:
                    continue
                estado["checkpoint_atual"] = etapa
                _salvar(estado)
                if etapa == "preparar-worktree":
                    resultado = _garantir_worktree(estado, prazo, cfg, lock)
                elif etapa == "executar-acao":
                    comando = _comando_documentar() if acao == "documentar" else _comando_validar()
                    resultado = _rodar_com_retry(
                        comando, Path(estado["worktree"]), prazo,
                        cfg["max_tentativas"], cfg["backoff_segundos"], lock.heartbeat,
                    )
                elif etapa == "validar":
                    resultado = _rodar_com_retry(
                        _comando_validar(), Path(estado["worktree"]), prazo,
                        cfg["max_tentativas"], cfg["backoff_segundos"], lock.heartbeat,
                    )
                elif etapa in {"registrar-diff", "registrar-diff-final"}:
                    resultado = _registrar_diff(estado, prazo, cfg, lock)
                    estado["diff"] = {
                        chave: resultado[chave]
                        for chave in ("patch", "patch_sha256", "bytes", "arquivos")
                    }
                elif etapa == "sincronizar-bancos":
                    if "sincronizar-bancos" not in set(_cfg().get("capacidades_permitidas", [])):
                        raise ExecutorConfiguracaoErro(
                            "capacidade `sincronizar-bancos` foi revogada antes da mutação"
                        )
                    resultado = _rodar_com_retry(
                        _comando_bancos(), Path(estado["worktree"]), prazo,
                        cfg["max_tentativas"], cfg["backoff_segundos"], lock.heartbeat,
                    )
                elif etapa == "avaliar-pos-sincronizacao":
                    resultado = _rodar_com_retry(
                        _comando_avaliar(), Path(estado["worktree"]), prazo,
                        cfg["max_tentativas"], cfg["backoff_segundos"], lock.heartbeat,
                    )
                else:
                    raise ExecutorErro(f"checkpoint desconhecido no estado: {etapa}")
                estado["checkpoints"][etapa] = {"concluido_em": _agora(), **resultado}
                estado["checkpoint_atual"] = etapa
                _salvar(estado)
                if os.environ.get("MEMORIA_EXECUTOR_INTERROMPER_APOS") == etapa:
                    raise ExecutorInterrompido(f"interrupção solicitada após `{etapa}`")
            estado["status"] = "concluido"
            estado["exit_code"] = SAIDA_OK
            estado["checkpoint_atual"] = None
            _salvar(estado)
            return SAIDA_OK, _resposta(estado)
        except ExecutorErro as exc:
            estado["status"] = "interrompido" if isinstance(exc, ExecutorInterrompido) else "falhou"
            estado["exit_code"] = exc.codigo
            estado["erro"] = str(exc)
            if isinstance(exc, ExecutorEtapaErro) and estado.get("checkpoint_atual"):
                estado.setdefault("falhas", {})[estado["checkpoint_atual"]] = exc.resultado
            _salvar(estado)
            return exc.codigo, _resposta(estado)
        except Exception as exc:
            estado["status"] = "falhou"
            estado["exit_code"] = SAIDA_FALHA
            estado["erro"] = f"falha interna controlada ({type(exc).__name__})"
            _salvar(estado)
            return SAIDA_FALHA, _resposta(estado)


def _opcoes(argv: list[str]) -> tuple[dict[str, str | bool], list[str]]:
    opcoes: dict[str, str | bool] = {}
    invalidos: list[str] = []
    for argumento in argv:
        match = re.fullmatch(r"--([a-z-]+)(?:=(.*))?", argumento)
        if not match:
            invalidos.append(argumento)
            continue
        chave = match.group(1)
        if chave in opcoes:
            invalidos.append(argumento)
            continue
        opcoes[chave] = match.group(2) if match.group(2) is not None else True
    return opcoes, invalidos


def _erro_json(codigo: int, mensagem: str, run_id: object = None) -> int:
    print(json.dumps({
        "schema": SCHEMA,
        "ok": False,
        "run_id": run_id if isinstance(run_id, str) else None,
        "status": "recusado",
        "exit_code": codigo,
        "erro": mensagem,
        "publicado": False,
        "commit_criado": False,
        "mutacoes_externas": [],
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return codigo


def main(argv: list[str]) -> int:
    opcoes, invalidos = _opcoes(argv)
    desconhecidas = sorted(set(opcoes) - {"run-id", "acao", "capacidades", "json"})
    if invalidos or desconhecidas or opcoes.get("json") is not True:
        return _erro_json(
            SAIDA_USO,
            "uso: memoria executar --run-id=ID --acao=documentar|verificar "
            "[--capacidades=sincronizar-bancos] --json",
            opcoes.get("run-id"),
        )
    run_id = opcoes.get("run-id")
    acao = opcoes.get("acao")
    if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
        return _erro_json(SAIDA_USO, "run_id inválido", run_id)
    if not isinstance(acao, str) or acao not in ACOES:
        return _erro_json(SAIDA_USO, "ação inválida", run_id)
    bruto = opcoes.get("capacidades", "")
    if not isinstance(bruto, str):
        return _erro_json(SAIDA_USO, "`--capacidades` exige lista separada por vírgula", run_id)
    capacidades = sorted(filter(None, (item.strip() for item in bruto.split(","))))
    if len(capacidades) != len(set(capacidades)) or set(capacidades) - CAPACIDADES:
        return _erro_json(SAIDA_USO, "capacidade desconhecida ou duplicada", run_id)
    try:
        codigo, resposta = executar(run_id, acao, capacidades)
    except ExecutorErro as exc:
        return _erro_json(exc.codigo, str(exc), run_id)
    except SystemExit:
        return _erro_json(SAIDA_CONFIGURACAO, "configuração do projeto inválida", run_id)
    except Exception as exc:
        return _erro_json(
            SAIDA_FALHA, f"falha interna controlada ({type(exc).__name__})", run_id
        )
    print(json.dumps(
        resposta, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ))
    return codigo
