"""validar — a documentação canônica não pode mentir sem alguém perceber.

FALHA DURA, para todo documento que TEM frontmatter:
  1. campos obrigatórios preenchidos
  2. `tipo` e `status` dentro do vocabulário
  3. `id` não duplicado · `projeto` bate com o padrao.json
  4. TODA ÂNCORA APONTA PARA ARQUIVO QUE EXISTE   ← a verificação que mais rende
  5. o diretório gerado bate com a saída atual do gerador
  6. os ponteiros da raiz continuam ponteiros — não viraram fonte paralela
  7. a cadeia está íntegra: sem id fantasma, sem inversão, sem ciclo, sem filho vivo
     pendurado em pai superado

NÃO REPROVA: documento legado sem frontmatter (é dívida, medida pela catraca) e pastas
declaradas em `externos` (outro dono, outro formato).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .lib import (acervo, comeca_com, config, frontmatter, hash_do_conteudo,
                  markdowns, raiz, relativo, titulo)


def main() -> int:
    c = config()
    externos = c.get("externos", {}).get("pastas", [])
    # `_templates/` tem placeholder no lugar de caminho — é molde, não afirmação sobre o
    # código. `_arquivo/` é assunto que DEIXOU DE EXISTIR; decisão superada NÃO vem para
    # cá — ela fica onde está, com `status: superado`, senão sai da verificação de cadeia.
    ignorar = c["acervos"].get("ignorar", ["docs/_templates/", "docs/_arquivo/"])
    vocab = c["vocabulario"]

    erros: list[str] = []
    avisos: list[str] = []
    legados: list[str] = []
    fora_da_regua: list[str] = []
    ids_vistos: dict[str, str] = {}
    por_id: dict[str, dict] = {}

    arquivos = markdowns(acervo())

    for f in arquivos:
        rel = relativo(f)
        if comeca_com(rel, ignorar):
            continue
        if comeca_com(rel, externos):
            fora_da_regua.append(rel)
            continue

        fm = frontmatter(Path(f).read_text(encoding="utf-8"))

        # DOCUMENTO SEM FRONTMATTER É DÍVIDA, NÃO ERRO — reprovar o passivo deixa o
        # build vermelho desde o dia um, e build que nasce vermelho ninguém olha.
        if fm is None:
            legados.append(rel)
            continue

        for campo in vocab.get("obrigatorios", []):
            if not fm.get(campo):
                erros.append(f"{rel}: falta o campo obrigatório `{campo}`")

        # O nome do projeto bate com o padrao.json — numa instalação real a config ficou
        # com o nome de exemplo e TODO derivado saiu carimbado errado, com build verde.
        if fm.get("projeto") and fm["projeto"] != c["projeto"]:
            erros.append(
                f"{rel}: `projeto: {fm['projeto']}` não bate com o `padrao.json` "
                f"(`{c['projeto']}`). Ou o documento veio de outro repositório, ou a "
                "configuração ficou com o nome de exemplo."
            )

        if "tipo" in fm and fm["tipo"] not in vocab.get("tipo", []):
            erros.append(f"{rel}: tipo `{fm['tipo']}` fora do vocabulário")
        if "status" in fm and fm["status"] not in vocab.get("status", []):
            erros.append(f"{rel}: status `{fm['status']}` fora do vocabulário")

        if fm.get("id"):
            if fm["id"] in ids_vistos:
                erros.append(f"{rel}: id `{fm['id']}` duplicado (também em {ids_vistos[fm['id']]})")
            ids_vistos[fm["id"]] = rel
            por_id[fm["id"]] = {"fm": fm, "rel": rel}

        # ÂNCORA QUEBRADA É O CORAÇÃO DESTA VERIFICAÇÃO — documento que cita caminho
        # morto vira mentira silenciosa, e é o tipo de erro que sobrevive anos.
        ancoras = fm.get("ancoras") or []
        if isinstance(ancoras, str):
            ancoras = [ancoras]
        for anc in ancoras:
            if anc and not (Path(raiz()) / anc).exists():
                erros.append(f"{rel}: âncora quebrada — `{anc}` não existe")

        if fm.get("status") == "verificado" and not fm.get("verificado_commit"):
            avisos.append(f"{rel}: `status: verificado` sem `verificado_commit`")

    # ------------------------------------------------------- 5: derivados vivos
    dir_gerado = Path(raiz()) / c["gerado"].get("diretorio", "").strip("/")
    if dir_gerado.is_dir():
        antes = {g.name: g.read_text(encoding="utf-8") for g in sorted(dir_gerado.glob("*.md"))}

        # O GERADOR ESCREVE; PRECISAMOS DESFAZER. Reexecutar é a única forma honesta de
        # saber se a saída commitada corresponde ao código de hoje — mas verificação que
        # altera o que verifica não é verificação, então a árvore volta ao que era.
        r = subprocess.run([sys.executable, "-m", "memoria_evolutiva", "gerar"],
                           capture_output=True, text=True, cwd=raiz())
        if r.returncode != 0:
            saida = (r.stderr or r.stdout).strip().splitlines()[:3]
            erros.append("o gerador falhou: " + " | ".join(saida))
        else:
            for nome, conteudo in antes.items():
                agora = (dir_gerado / nome).read_text(encoding="utf-8") if (dir_gerado / nome).exists() else ""
                if hash_do_conteudo(conteudo) != hash_do_conteudo(agora):
                    erros.append(
                        f"{c['gerado']['diretorio']}/{nome}: desatualizado ou editado à mão. "
                        "Rode `memoria gerar` e commite a saída."
                    )
        for nome, conteudo in antes.items():
            (dir_gerado / nome).write_text(conteudo, encoding="utf-8")

    # ------------------------------------------------------- 7: cadeia de origem
    # `deriva_de` = "de quem eu dependo — se algum cair, eu preciso ser revisto".
    cadeia = c.get("cadeia", {})
    niveis = cadeia.get("niveis", {})
    exigem = cadeia.get("exige_origem", [])

    for id_, d in por_id.items():
        fm, rel = d["fm"], d["rel"]
        tipo = fm.get("tipo", "")
        pais = fm.get("deriva_de") or []
        if isinstance(pais, str):
            pais = [pais]
        pais = [p for p in pais if p]

        if not pais and tipo in exigem and fm.get("status") != "superado":
            avisos.append(
                f"{rel}: `{tipo}` sem `deriva_de`. De qual documento este veio? "
                "Um detalhamento sem origem declarada é um detalhamento que ninguém "
                "conferiu contra requisito nenhum."
            )

        for pai_id in pais:
            if pai_id == id_:
                erros.append(f"{rel}: `deriva_de` aponta para si mesmo")
                continue
            if pai_id not in por_id:
                erros.append(f"{rel}: `deriva_de: {pai_id}` — não existe documento com esse id")
                continue
            pai = por_id[pai_id]["fm"]
            if tipo in niveis and pai.get("tipo", "") in niveis and niveis[pai["tipo"]] > niveis[tipo]:
                erros.append(
                    f"{rel}: cadeia invertida — `{tipo}` não pode derivar de "
                    f"`{pai['tipo']}` ({pai_id}). A origem tem que estar mais perto do "
                    "problema, não mais perto do código."
                )
            if pai.get("status") == "superado" and fm.get("status") == "verificado":
                erros.append(
                    f"{rel}: está `verificado`, mas deriva de `{pai_id}`, que está "
                    "`superado`. Revise e marque como `superado` também, ou reaponte "
                    "para o documento que substituiu o pai."
                )
            vf, vp = fm.get("verificado_em", ""), pai.get("verificado_em", "")
            if vf and vp and str(vp) > str(vf):
                avisos.append(
                    f"{rel}: o pai `{pai_id}` foi reverificado em {vp}, depois deste "
                    f"({vf}). Pode estar em dia — mas ninguém olhou desde então."
                )

    # CICLO — fácil de cometer (cada seta isolada parece certa) e fatal para "quem
    # depende deste". A primeira versão do gerador entrou em laço infinito com um ciclo.
    estado: dict[str, int] = {}
    pilha: list[str] = []
    ciclos: list[str] = []

    def visita(id_: str) -> None:
        estado[id_] = 1
        pilha.append(id_)
        pais = por_id[id_]["fm"].get("deriva_de") or []
        if isinstance(pais, str):
            pais = [pais]
        for pai_id in pais:
            if not pai_id or pai_id not in por_id:
                continue
            if estado.get(pai_id, 0) == 1:
                corte = pilha[pilha.index(pai_id):]
                ciclos.append(" → ".join(corte) + f" → {pai_id}")
            elif estado.get(pai_id, 0) == 0:
                visita(pai_id)
        pilha.pop()
        estado[id_] = 2

    for id_ in por_id:
        if estado.get(id_, 0) == 0:
            visita(id_)

    for ciclo in dict.fromkeys(ciclos):
        erros.append(
            f"cadeia circular: {ciclo}\n"
            "      Entre dois documentos a dependência aponta UMA vez só. Decida qual dos\n"
            "      dois levanta a pergunta que o outro responde — esse é o pai — e apague\n"
            "      a seta de volta. ADR costuma depender do documento que motivou a\n"
            "      decisão; quem implementa a decisão é que depende do ADR, nunca os dois."
        )

    # ------------------------------------------------------ 6: ponteiros da raiz
    # CLAUDE.md, AGENTS.md e afins são ATALHOS para a entrada. O modo como isso apodrece:
    # alguém acrescenta "só uma observação", depois outra, e em três meses existem duas
    # portas de entrada divergindo. Régua grosseira de propósito.
    pont = c.get("ponteiros", {})
    limite = int(pont.get("limite_de_linhas", 40))
    entrada = c["acervos"]["canonico"].strip("/") + "/PROJETO.md"

    for p in pont.get("arquivos", []):
        abs_ = Path(raiz()) / p
        if not abs_.is_file():
            avisos.append(f"{p}: declarado em `ponteiros.arquivos` mas não existe")
            continue
        texto = abs_.read_text(encoding="utf-8")
        linhas = texto.rstrip().count("\n") + 1
        if entrada not in texto and "AGENTS.md" not in texto:
            erros.append(
                f"{p}: é ponteiro, mas não cita `{entrada}` nem `AGENTS.md`. "
                "Um agente que só lê este arquivo nunca chega à porta de entrada."
            )
        if linhas > limite:
            erros.append(
                f"{p}: {linhas} linhas (limite {limite}). Ponteiro que cresce virou "
                f"fonte paralela — mova o conteúdo para `{entrada}` ou para o documento "
                "de assunto e deixe só o apontamento."
            )

    # ---------------------------------------------------------------------- saída
    ignorados = sum(1 for f in arquivos if comeca_com(relativo(f), ignorar))
    verificados = len(arquivos) - len(legados) - len(fora_da_regua) - ignorados

    titulo(f"Estrutura da documentação — {c['projeto']}")
    print(f"  documentos verificados: {verificados}")
    if legados:
        print(f"  legados sem frontmatter (medidos pela catraca): {len(legados)}")
    if fora_da_regua:
        print(f"  fora da régua por convenção de outra ferramenta: {len(fora_da_regua)}"
              f" ({', '.join(externos)})")

    if avisos:
        print(f"\nAVISOS ({len(avisos)}):")
        for a in avisos:
            print(f"  ~ {a}")

    if erros:
        print(f"\nERROS ({len(erros)}):")
        for e in erros:
            print(f"  x {e}")
        print("\nFalhou.")
        return 1

    print("\nTudo certo.")
    return 0
