"""autoteste — os validadores realmente pegam o que prometem?

Verificador que não reprova nada é indistinguível de verificador quebrado — os dois
imprimem "tudo certo". Este comando quebra o projeto DE PROPÓSITO, numa CÓPIA
temporária, uma coisa por vez, e confere que o validador certo reclama. É o teste do
alarme de incêndio: você aperta o botão.

Nada é alterado no seu projeto.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .lib import config, raiz, titulo

PULAR = {".git", "node_modules", "vendor", "__pycache__", ".code-review-graph"}


def _copiar(de: Path, para: Path) -> None:
    para.mkdir(parents=True, exist_ok=True)
    for item in de.iterdir():
        if item.name in PULAR:
            continue
        destino = para / item.name
        if item.is_dir():
            _copiar(item, destino)
        else:
            try:
                shutil.copy2(item, destino)
            except OSError:
                pass


def _escrever(arquivo: Path, conteudo: str) -> None:
    """Cria o diretório antes — git não versiona pasta vazia, e num CLONE a pasta que
    existe na sua máquina pode simplesmente não estar lá. Quatro testes já falharam no
    CI por isso, passando na máquina de quem escreveu."""
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(conteudo, encoding="utf-8")


def _cabecalho(id_: str, tipo: str, status: str, pais: list[str], projeto: str) -> str:
    fm = (f"---\nid: {id_}\ntipo: {tipo}\nprojeto: {projeto}\n"
          f"titulo: documento de teste do autoteste\nstatus: {status}\n"
          "verificado_em: 2026-01-01\nverificado_commit: 0000000\n")
    if pais:
        fm += "deriva_de:\n" + "".join(f"  - {p}\n" for p in pais)
    return fm + "ancoras:\n  - padrao.json\n---\n\n# documento de teste\n"


def _rodar(tmp: Path, comando: str) -> tuple[int, str]:
    r = subprocess.run([sys.executable, "-m", "memoria_evolutiva", *comando.split()],
                       capture_output=True, text=True, cwd=str(tmp))
    return r.returncode, r.stdout + r.stderr


def main() -> int:
    c = config()
    projeto = c["projeto"]
    origem = Path(raiz())
    ger_dir = c["gerado"].get("diretorio", "docs/gerado").strip("/")
    tem_cadeia = len(c.get("cadeia", {}).get("niveis", {})) > 1
    tem_ponteiros = bool(c.get("ponteiros", {}).get("arquivos"))
    tem_autonomia = bool(c.get("autonomia", {}).get("ativo"))
    tem_grafo = bool(c.get("grafo", {}).get("ativo"))
    tem_fragmentos = isinstance(c.get("rag", {}), dict)
    tem_adaptadores = isinstance(c.get("adaptadores", {}), dict)
    tem_avaliacao = isinstance(c.get("avaliacao", {}), dict)
    tem_ciclo_autonomo = isinstance(c.get("ciclo", {}), dict)
    tem_agendamento = isinstance(c.get("agendamento", {}), dict)

    def quebra_gerado(t: Path) -> None:
        for g in sorted((t / ger_dir).glob("*.md")):
            g.write_text(g.read_text(encoding="utf-8") + "\nlinha intrusa\n", encoding="utf-8")
            return

    def quebra_ponteiro(t: Path) -> None:
        p = t / c["ponteiros"]["arquivos"][0]
        p.write_text(p.read_text(encoding="utf-8") + "linha extra\n" * 60, encoding="utf-8")

    def quebra_ciclo(t: Path) -> None:
        _escrever(t / "docs/funcional/_a.md", _cabecalho("FDD-TESTE", "fdd", "rascunho", ["ADR-TESTE"], projeto))
        _escrever(t / "docs/decisoes/_b.md", _cabecalho("ADR-TESTE", "adr", "rascunho", ["HLD-TESTE"], projeto))
        _escrever(t / "docs/arquitetura/_c.md", _cabecalho("HLD-TESTE", "hld", "rascunho", ["FDD-TESTE"], projeto))

    def quebra_cadeia_ok(t: Path) -> None:
        _escrever(t / "docs/produto/_pai.md", _cabecalho("PRD-TESTE", "prd", "verificado", [], projeto))
        _escrever(t / "docs/funcional/_filho.md", _cabecalho("FDD-TESTE", "fdd", "verificado", ["PRD-TESTE"], projeto))
        # o mapa da cadeia é derivado: regerar antes mantém este teste medindo a cadeia,
        # não a defasagem do derivado
        subprocess.run([sys.executable, "-m", "memoria_evolutiva", "gerar"],
                       capture_output=True, cwd=str(t))

    def quebra_politica_autonoma(t: Path) -> None:
        politica = t / str(c["autonomia"]["politica"])
        politica.write_text(
            politica.read_text(encoding="utf-8").replace(
                "comportamento executado", "preferência arbitrária"
            ),
            encoding="utf-8",
        )

    def quebra_cobertura(t: Path) -> None:
        codigo = t / c.get("gerado", {}).get("raiz", "").strip("/")
        extensoes = {
            "." + str(ext).lower().lstrip(".")
            for ext in c.get("gerado", {}).get("extensoes", [])
        }
        for fonte in sorted(codigo.rglob("*")):
            if fonte.is_file() and fonte.suffix.lower() in extensoes:
                fonte.write_bytes(fonte.read_bytes() + b"\n")
                return

    def quebra_grafo(t: Path) -> None:
        grafo = t / str(c.get("grafo", {}).get("arquivo", "graphify-out/graph.json"))
        grafo.write_text("{corrompido", encoding="utf-8")

    def quebra_fragmentos(t: Path) -> None:
        manifesto = t / str(c.get("rag", {}).get(
            "manifesto", "docs/gerado/manifesto-fragmentos-v2.json"
        ))
        manifesto.write_text(
            manifesto.read_text(encoding="utf-8") + "\n",
            encoding="utf-8",
        )

    def quebra_adaptador(t: Path) -> None:
        caminho = t / ".cursor/rules/memoria-evolutiva.mdc"
        caminho.write_text(
            caminho.read_text(encoding="utf-8").replace("Gateway read-only", "Gateway read-write"),
            encoding="utf-8",
        )

    def quebra_redaction(t: Path) -> None:
        caminho = t / "padrao.json"
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        dados["seguranca_memoria"]["redaction_antes_retain"] = False
        caminho.write_text(
            json.dumps(dados, ensure_ascii=False, indent=4) + "\n", encoding="utf-8"
        )

    def quebra_executor(t: Path) -> None:
        caminho = t / "padrao.json"
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        dados["executor"]["publicacao_automatica"] = True
        caminho.write_text(
            json.dumps(dados, ensure_ascii=False, indent=4) + "\n", encoding="utf-8"
        )

    def quebra_ciclo_autonomo(t: Path) -> None:
        caminho = t / "padrao.json"
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        dados["ciclo"]["publicacao_automatica"] = True
        caminho.write_text(
            json.dumps(dados, ensure_ascii=False, indent=4) + "\n", encoding="utf-8"
        )

    def quebra_agendamento(t: Path) -> None:
        caminho = t / "padrao.json"
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        dados["agendamento"]["banco_negocio"] = "permitido"
        caminho.write_text(
            json.dumps(dados, ensure_ascii=False, indent=4) + "\n", encoding="utf-8"
        )

    def quebra_avaliacao(t: Path) -> None:
        caminho = t / str(c["avaliacao"]["relatorio"])
        caminho.write_text(
            caminho.read_text(encoding="utf-8") + "\n", encoding="utf-8"
        )

    testes: list[dict] = [
        dict(nome="âncora apontando para arquivo inexistente",
             quebra=lambda t: _escrever(t / "docs/arquitetura/_teste.md",
                 _cabecalho("TESTE-ANCORA", "hld", "rascunho", [], projeto).replace(
                     "  - padrao.json", "  - caminho/que/nao/existe.php")),
             comando="validar", esperado=1, contem="âncora quebrada"),
        dict(nome="tipo fora do vocabulário",
             quebra=lambda t: _escrever(t / "docs/arquitetura/_teste.md",
                 _cabecalho("TESTE-VOCAB", "inventado", "rascunho", [], projeto)),
             comando="validar", esperado=1, contem="fora do vocabulário"),
        dict(nome="nome de projeto divergente do padrao.json",
             quebra=lambda t: _escrever(t / "docs/arquitetura/_teste.md",
                 _cabecalho("TESTE-PROJ", "hld", "rascunho", [], "outro-repositorio")),
             comando="validar", esperado=1, contem="não bate com o"),
        dict(nome="id duplicado",
             quebra=lambda t: (
                 _escrever(t / "docs/arquitetura/_a.md", _cabecalho("TESTE-DUP", "hld", "rascunho", [], projeto)),
                 _escrever(t / "docs/arquitetura/_b.md", _cabecalho("TESTE-DUP", "hld", "rascunho", [], projeto))),
             comando="validar", esperado=1, contem="duplicado"),
        dict(nome="arquivo derivado editado à mão",
             quebra=quebra_gerado, comando="validar", esperado=1, contem="editado à mão"),
        dict(nome="política autônoma adulterada",
             quebra=quebra_politica_autonoma, comando="validar", esperado=1,
             contem="política autônoma alterada", aplica=tem_autonomia),
        dict(nome="fonte mudou sem atualizar a cobertura",
             quebra=quebra_cobertura, comando="validar", esperado=1,
             contem="cobertura-codigo.md", aplica=tem_autonomia),
        dict(nome="ponteiro da raiz virou fonte paralela",
             quebra=quebra_ponteiro, comando="validar", esperado=1, contem="fonte paralela",
             aplica=tem_ponteiros),
        dict(nome="deriva_de apontando para documento inexistente",
             quebra=lambda t: _escrever(t / "docs/funcional/_teste.md",
                 _cabecalho("FDD-TESTE", "fdd", "rascunho", ["PRD-QUE-NAO-EXISTE"], projeto)),
             comando="validar", esperado=1, contem="não existe documento com esse id",
             aplica=tem_cadeia),
        dict(nome="cadeia invertida — requisito derivando de detalhe",
             quebra=lambda t: (
                 _escrever(t / "docs/arquitetura/_pai.md", _cabecalho("LLD-TESTE", "lld", "rascunho", [], projeto)),
                 _escrever(t / "docs/produto/_filho.md", _cabecalho("PRD-TESTE", "prd", "rascunho", ["LLD-TESTE"], projeto))),
             comando="validar", esperado=1, contem="cadeia invertida", aplica=tem_cadeia),
        dict(nome="documento vivo pendurado em pai superado",
             quebra=lambda t: (
                 _escrever(t / "docs/produto/_pai.md", _cabecalho("PRD-TESTE", "prd", "superado", [], projeto)),
                 _escrever(t / "docs/funcional/_filho.md", _cabecalho("FDD-TESTE", "fdd", "verificado", ["PRD-TESTE"], projeto))),
             comando="validar", esperado=1, contem="superado", aplica=tem_cadeia),
        dict(nome="cadeia circular",
             quebra=quebra_ciclo, comando="validar", esperado=1, contem="cadeia circular",
             aplica=tem_cadeia),
        # o laço infinito com ciclo aconteceu de verdade: o processo comeu a memória da
        # máquina até ser morto. Aqui se mede que o gerador TERMINA.
        dict(nome="ciclo não trava o gerador",
             quebra=quebra_ciclo, comando="gerar", esperado=0, contem=None, aplica=tem_cadeia),
        dict(nome="cadeia bem formada NÃO reprova",
             quebra=quebra_cadeia_ok, comando="validar", esperado=0, contem=None, aplica=tem_cadeia),
        dict(nome="documento novo sem frontmatter aumenta a dívida",
             quebra=lambda t: _escrever(
                 t / c["acervos"]["canonico"].strip("/") / "_teste_legado.md",
                 "# sem frontmatter\n"),
             comando="catraca", esperado=1, contem="dívida aumentou"),
        dict(nome="documento sem frontmatter NÃO é erro de estrutura",
             quebra=lambda t: _escrever(
                 t / c["acervos"]["canonico"].strip("/") / "_teste_legado.md",
                 "# sem frontmatter\n"),
             comando="validar", esperado=0, contem=None),
        dict(nome="grafo corrompido reprova mesmo com hashes de fonte iguais",
             quebra=quebra_grafo, comando="bancos status --offline", esperado=1,
             contem="marcador do Graphify inválido", aplica=tem_grafo),
        dict(nome="manifesto de fragmentos adulterado reprova",
             quebra=quebra_fragmentos, comando="fragmentos verificar", esperado=1,
             contem="manifesto diverge", aplica=tem_fragmentos),
        dict(nome="adaptador de agente adulterado reprova",
             quebra=quebra_adaptador, comando="adaptadores verificar", esperado=1,
             contem="adaptador", aplica=tem_adaptadores),
        dict(nome="redaction antes do retain não pode ser desativada",
             quebra=quebra_redaction, comando="validar", esperado=1,
             contem="redaction_antes_retain"),
        dict(nome="executor não pode habilitar publicação automática",
             quebra=quebra_executor, comando="validar", esperado=1,
             contem="executor.publicacao_automatica"),
        dict(nome="ciclo dos agentes não pode habilitar publicação automática",
             quebra=quebra_ciclo_autonomo, comando="validar", esperado=1,
             contem="ciclo.publicacao_automatica", aplica=tem_ciclo_autonomo),
        dict(nome="agendador não pode acessar o banco de negócio",
             quebra=quebra_agendamento, comando="validar", esperado=1,
             contem="agendamento.banco_negocio", aplica=tem_agendamento),
        dict(nome="relatório de avaliação RAG adulterado reprova",
             quebra=quebra_avaliacao, comando="avaliar verificar", esperado=1,
             contem="relatório RAG", aplica=tem_avaliacao),
        dict(nome="projeto intacto passa nas verificações locais",
             quebra=lambda t: None, comando=None, esperado=0, contem=None),
    ]

    titulo(f"Autoteste do padrão — {projeto}")
    print("  cópia de trabalho: temporária; nada é alterado no seu projeto\n")

    passou = falhou = pulados = 0
    relatos: list[tuple[str, str, str]] = []

    # A cópia deliberadamente não leva `.git` nem dependências. Refaça uma vez os
    # derivados dependentes da raiz/commit e os adaptadores com caminho absoluto; sem
    # essa preparação, um projeto Git com `vendor/` falha intacto e cria falso positivo.
    with tempfile.TemporaryDirectory(prefix="autoteste-base-") as base_s:
        base = Path(base_s) / "projeto"
        _copiar(origem, base)
        for cmd in ("gerar", "adaptadores gerar"):
            rc_base, saida_base = _rodar(base, cmd)
            if rc_base != 0:
                print(f"\nNão foi possível preparar a cópia-base com `{cmd}`:\n{saida_base}")
                return 1

        for t in testes:
            if not t.get("aplica", True):
                pulados += 1
                relatos.append(("·", t["nome"], "não se aplica a este projeto"))
                continue

            with tempfile.TemporaryDirectory(prefix="autoteste-memoria-") as tmp_s:
                tmp = Path(tmp_s) / "projeto"
                _copiar(base, tmp)
                t["quebra"](tmp)

                comandos = ([t["comando"]] if t["comando"]
                            else ["validar", "catraca", "bancos status --offline",
                                  "avaliar verificar"])
                rc_final, saida_final = 0, ""
                for cmd in comandos:
                    rc, saida = _rodar(tmp, cmd)
                    saida_final += saida
                    if rc != 0:
                        rc_final = rc

            ok_codigo = (rc_final != 0) if t["esperado"] == 1 else (rc_final == 0)
            ok_texto = t["contem"] is None or t["contem"] in saida_final

            if ok_codigo and ok_texto:
                passou += 1
                relatos.append(("✔", t["nome"], ""))
            else:
                falhou += 1
                motivo = ("deveria reprovar e não reprovou" if t["esperado"] == 1 and not ok_codigo
                          else f"reprovou e não deveria (saída {rc_final})" if not ok_codigo
                          else f"reprovou, mas a mensagem não menciona `{t['contem']}`")
                relatos.append(("✘", t["nome"], motivo))

    for sinal, nome, obs in relatos:
        print(f"  {sinal}  {nome}" + (f"\n        → {obs}" if obs else ""))

    print("\n" + "─" * 60)
    extra = f" · {pulados} não se aplicam" if pulados else ""
    print(f"{passou} passaram · {falhou} falharam{extra}")

    if falhou:
        print("\nUm validador que não reprova o que deveria é pior que nenhum: dá confiança")
        print("falsa. Conserte antes de confiar no build verde.")
        return 1
    print("\nOs validadores pegam o que prometem.")
    return 0
