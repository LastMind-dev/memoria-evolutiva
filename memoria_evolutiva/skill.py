"""Gera e verifica a peça portátil de procedimento do projeto.

A fonte continua sendo o runbook versionado. Depois que a skill é gerada, qualquer
divergência entre fonte, gerador e artefato é falha dura: uma peça antiga ensina o
agente a operar por um contrato que o projeto já abandonou.
"""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

from . import __version__
from .lib import (
    barras, commit_atual, hash_do_conteudo, pacote, raiz, relativo,
    sha256_canonico, titulo,
)

FONTES = {
    "docs/runbooks/sessao.md": "references/sessao-do-projeto.md",
    # Compatibilidade com projetos antigos. Se os dois existirem, o canônico acima
    # prevalece e não é silenciosamente sobrescrito pelo nome legado.
    "docs/runbooks/fim-de-sessao.md": "references/sessao-do-projeto.md",
    "docs/runbooks/indexacao.md": "references/indexacao-do-projeto.md",
    "docs/runbooks/documentacao-autonoma.md": "references/documentacao-autonoma.md",
}

PULAR = {".git", "node_modules", "vendor", "__pycache__"}
PASTAS_GERENCIADAS = ("assets/kit", "references", "agents")
REFERENCIAS_OBRIGATORIAS = {
    "references/sessao-do-projeto.md",
    "references/documentacao-autonoma.md",
}


def _copiar(de: Path, para: Path) -> int:
    para.mkdir(parents=True, exist_ok=True)
    n = 0
    for item in de.iterdir():
        if item.name in PULAR:
            continue
        destino = para / item.name
        if item.is_dir():
            n += _copiar(item, destino)
        else:
            shutil.copy2(item, destino)
            n += 1
    return n


def _fontes_efetivas() -> dict[str, str]:
    escolhidas: dict[str, str] = {}
    destinos: set[str] = set()
    for origem, destino in FONTES.items():
        if destino in destinos or not (Path(raiz()) / origem).is_file():
            continue
        escolhidas[origem] = destino
        destinos.add(destino)
    return escolhidas


def _hash_arquivo(arquivo: Path) -> str:
    return sha256_canonico(arquivo.read_bytes())


def _saida_registrada(saida: Path) -> str:
    base = Path(raiz()).resolve()
    resolvida = saida.resolve()
    if resolvida.is_relative_to(base):
        return barras(str(resolvida.relative_to(base)))
    return barras(str(resolvida))


def _saida_do_registro(valor: object) -> Path | None:
    if not isinstance(valor, str) or not valor.strip():
        return None
    caminho = Path(valor)
    return caminho.resolve() if caminho.is_absolute() else (Path(raiz()) / caminho).resolve()


def _artefatos_obrigatorios(fontes: dict[str, str]) -> set[str]:
    return {"SKILL.md", "agents/openai.yaml", *REFERENCIAS_OBRIGATORIAS, *fontes.values()}


def _preparar_saida(saida: Path) -> str | None:
    """Limpa somente a árvore que pertence ao gerador, dentro de uma saída segura."""
    base = Path(raiz()).resolve()
    origem_pacote = Path(pacote()).resolve()
    resolvida = saida.resolve()
    if (
        resolvida == base
        or resolvida == origem_pacote
        or origem_pacote.is_relative_to(resolvida)
        or resolvida.is_relative_to(origem_pacote)
    ):
        return "a saída não pode coincidir nem se sobrepor ao projeto ou ao pacote-fonte"

    try:
        resolvida.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return f"não foi possível preparar a pasta: {exc}"
    for relativo_dir in PASTAS_GERENCIADAS:
        alvo = resolvida / relativo_dir
        # Um pai redirecionado poderia levar a remoção para fora da saída declarada.
        if not alvo.is_symlink() and not alvo.resolve().is_relative_to(resolvida):
            return f"caminho gerenciado escapa da saída: {relativo_dir}"
        if alvo.is_symlink() or alvo.is_file():
            alvo.unlink()
        elif alvo.is_dir():
            shutil.rmtree(alvo)

    skill_md = resolvida / "SKILL.md"
    if skill_md.is_symlink() or skill_md.is_file():
        skill_md.unlink()
    elif skill_md.exists():
        return "o caminho gerenciado SKILL.md existe, mas não é arquivo"
    return None


def _hashes_artefatos(saida: Path) -> tuple[dict[str, str], list[str]]:
    base = saida.resolve()
    hashes: dict[str, str] = {}
    falhas: list[str] = []
    if not base.is_dir():
        return {}, ["pasta da skill não existe"]
    for arquivo in sorted(base.rglob("*")):
        rel_path = arquivo.relative_to(base)
        if any(parte in PULAR for parte in rel_path.parts):
            continue
        rel = barras(str(rel_path))
        if arquivo.is_symlink():
            falhas.append(f"artefato não pode ser link simbólico: {rel}")
        elif arquivo.is_file():
            hashes[rel] = _hash_arquivo(arquivo)
    return hashes, falhas


def _conferir(marcador: Path, saida_argumento: Path | None) -> int:
    if not marcador.is_file():
        print("Skill ainda não foi gerada; não existe artefato derivado para conferir.")
        return 0
    try:
        estado = json.loads(marcador.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"ERRO — marcador da skill inválido: {exc}")
        return 1
    if not isinstance(estado, dict) or estado.get("schema") != 2:
        print("ERRO — marcador da skill usa contrato antigo ou inválido. Rode: `memoria skill`.")
        return 1

    saida_marcada = _saida_do_registro(estado.get("saida"))
    saida = saida_argumento.resolve() if saida_argumento is not None else saida_marcada
    falhas: list[str] = []
    if saida is None:
        falhas.append("marcador não identifica a pasta da skill")
    elif saida_marcada != saida:
        falhas.append(
            f"saída informada `{_saida_registrada(saida)}` diverge da registrada "
            f"`{estado.get('saida')}`"
        )

    fontes = _fontes_efetivas()
    atuais = {
        origem: hash_do_conteudo((Path(raiz()) / origem).read_text(encoding="utf-8"))
        for origem in fontes
    }
    registradas = estado.get("fontes")
    if not isinstance(registradas, dict) or registradas != atuais:
        falhas.append("runbooks de origem mudaram, surgiram ou foram removidos")
    if estado.get("gerador_versao") != __version__:
        falhas.append(
            f"gerador mudou: skill={estado.get('gerador_versao')!r}, pacote={__version__!r}"
        )

    obrigatorios = _artefatos_obrigatorios(fontes)
    registrados = estado.get("artefatos")
    if not isinstance(registrados, dict) or not obrigatorios.issubset(registrados):
        falhas.append("manifesto de artefatos da skill diverge do contrato atual")
    elif saida is not None:
        hashes, falhas_arquivo = _hashes_artefatos(saida)
        falhas.extend(falhas_arquivo)
        removidos = sorted(set(registrados) - set(hashes))
        adicionados = sorted(set(hashes) - set(registrados))
        alterados = sorted(
            rel for rel in set(hashes) & set(registrados)
            if hashes[rel] != registrados[rel]
        )
        falhas.extend(f"artefato removido depois da geração: {rel}" for rel in removidos)
        falhas.extend(f"artefato acrescentado depois da geração: {rel}" for rel in adicionados)
        falhas.extend(f"artefato alterado depois da geração: {rel}" for rel in alterados)

    titulo(f"Skill derivada — gerada em {estado.get('gerada_em', '?')}")
    if not falhas:
        print("  Em dia com os runbooks, o gerador e os artefatos publicados.")
        return 0
    print("  FALHA — a skill derivada não representa o contrato atual:")
    for falha in falhas:
        print(f"    - {falha}")
    print("\n  Regere antes de permitir que outro agente use a peça:")
    print("    memoria skill")
    return 1


def main(argv: list[str]) -> int:
    conferir = "--conferir" in argv
    saida_informada: Path | None = None
    desconhecidos: list[str] = []
    for argumento in argv:
        if argumento == "--conferir":
            continue
        if argumento.startswith("--saida=") and argumento.split("=", 1)[1]:
            if saida_informada is not None:
                desconhecidos.append(argumento)
            else:
                saida_informada = Path(argumento.split("=", 1)[1])
            continue
        desconhecidos.append(argumento)
    if desconhecidos:
        print("Opção desconhecida em `memoria skill`: " + ", ".join(desconhecidos))
        return 2

    marcador = Path(raiz()) / "docs/.skill-gerada.json"
    if conferir:
        return _conferir(marcador, saida_informada)

    fontes = _fontes_efetivas()
    referencias_encontradas = set(fontes.values())
    referencias_ausentes = sorted(REFERENCIAS_OBRIGATORIAS - referencias_encontradas)
    if referencias_ausentes:
        print("ERRO — faltam runbooks obrigatórios para gerar a skill:")
        for referencia in referencias_ausentes:
            print(f"  - {referencia}")
        print("Rode novamente `memoria instalar` para restaurar a estrutura versionada.")
        return 1

    saida = (saida_informada or (Path(raiz()) / "skill-memoria-evolutiva")).resolve()
    erro_saida = _preparar_saida(saida)
    if erro_saida:
        print(f"ERRO — saída insegura para a skill: {erro_saida}.")
        return 2
    (saida / "references").mkdir(parents=True, exist_ok=True)
    (saida / "assets").mkdir(parents=True, exist_ok=True)
    copiados = _copiar(Path(pacote()), saida / "assets/kit")

    levados: dict[str, str] = {}
    for origem, destino_rel in fontes.items():
        arquivo_origem = Path(raiz()) / origem
        destino = saida / destino_rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(arquivo_origem, destino)
        levados[origem] = hash_do_conteudo(arquivo_origem.read_text(encoding="utf-8"))

    (saida / "SKILL.md").write_text(
        """---
name: memoria-evolutiva-projeto
description: Ler, documentar e manter um projeto autonomamente com evidência e cobertura verificável. Use ao instalar a memória evolutiva, analisar um repositório ainda não documentado ou atualizar sua documentação após mudanças no código.
---

# Memória evolutiva autônoma

1. Leia `docs/PROJETO.md` e `docs/politicas/AUTONOMIA.md`.
2. Rode `memoria documentar` antes da análise para atualizar documentação e bancos.
   Nos quatro documentos gerenciados, escreva conhecimento durável somente entre os
   marcadores `memoria-evolutiva:inicio` e `memoria-evolutiva:fim`; esse bloco é preservado.
3. Rode `memoria bancos consultar --pergunta="..."`; use Hindsight para significado e
   Graphify para estrutura antes de abrir arquivos brutos.
4. Abra `docs/gerado/cobertura-codigo.md` e percorra todos os arquivos listados; use
   lotes apenas para controle de contexto, nunca para reduzir a cobertura.
5. Aplique a ordem de autoridade da política. Não peça aprovação documental.
6. Registre fatos com âncoras; sem prova, use `indeterminado` e prossiga.
7. Organize arquitetura por arc42 e C4, comportamento pela cadeia PRD/FDD/HLD/LLD,
   decisões significativas por ADR e conteúdo de uso pelas categorias Diátaxis.
8. Depois de escrever, rode `memoria documentar`, `memoria avaliar verificar`,
   `memoria autoteste` e as verificações do projeto. Só encerre com todas as catracas
   aplicáveis verdes. Não remensure o baseline para esconder uma regressão.

Instalação e documentação não autorizam commit, push, deploy, escrita remota ou ação
irreversível. Essas fronteiras permanecem nas regras operacionais do projeto.

Consulte `references/documentacao-autonoma.md` e `references/sessao-do-projeto.md` para
o procedimento detalhado.
""",
        encoding="utf-8",
    )
    (saida / "agents").mkdir(parents=True, exist_ok=True)
    (saida / "agents/openai.yaml").write_text(
        """interface:
  display_name: "Documentação autônoma do projeto"
  short_description: "Lê o repositório e mantém documentação verificável"
  default_prompt: "Use $memoria-evolutiva-projeto para analisar e documentar este projeto autonomamente."
policy:
  allow_implicit_invocation: true
""",
        encoding="utf-8",
    )

    obrigatorios = _artefatos_obrigatorios(fontes)
    artefatos, falhas = _hashes_artefatos(saida)
    ausentes = sorted(obrigatorios - set(artefatos))
    falhas.extend(f"artefato obrigatório ausente: {rel}" for rel in ausentes)
    if falhas:
        print("ERRO — a skill não foi gerada integralmente:")
        for falha in falhas:
            print(f"  - {falha}")
        return 1
    marcador.parent.mkdir(parents=True, exist_ok=True)
    marcador.write_text(json.dumps({
        "schema": 2,
        "gerada_em": date.today().isoformat(),
        "commit": commit_atual(),
        "gerador_versao": __version__,
        "saida": _saida_registrada(saida),
        "nota": "A skill é artefato derivado. Edite os runbooks e regere; "
                "divergência agora bloqueia a verificação.",
        "fontes": levados,
        "artefatos": artefatos,
    }, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")

    titulo("Pacote da skill montado")
    print(f"  {relativo(str(saida))}")
    print(f"  {copiados} arquivos do kit · {len(levados)} runbook(s) do projeto")
    print("  SKILL.md autônoma criada com o protocolo do projeto.")
    print("\n  `memoria skill --conferir` agora falha se fonte, gerador ou artefato divergir.")
    return 0
