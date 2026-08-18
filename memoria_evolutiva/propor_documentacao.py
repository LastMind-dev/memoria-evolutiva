"""propor-documentacao — compatibilidade legada para rascunhos fora do canônico."""

from __future__ import annotations

from pathlib import Path

from .analisar import consolidar
from .diagnosticar import coletar
from .lib import raiz, titulo


def _frontmatter(id_: str, tipo: str, projeto: str, titulo_: str) -> str:
    return (
        "---\n"
        f"id: {id_}\n"
        f"tipo: {tipo}\n"
        f"projeto: {projeto}\n"
        f"titulo: {titulo_}\n"
        "status: rascunho\n"
        "---\n\n"
    )


def _propostas() -> dict[str, str]:
    d = coletar()
    a = consolidar(d)
    projeto = d["projeto"]
    git = d["git"]
    codigo = d["codigo"]
    manifestos = d["repositorio"]["manifestos"]

    projeto_md = _frontmatter("PROJETO-PROPOSTO", "entrada", projeto, "Proposta de porta de entrada")
    projeto_md += (
        f"# {projeto} — proposta de porta de entrada\n\n"
        "> **RASCUNHO AUTOMÁTICO.** Nada aqui está verificado. Confirme e mova os fatos\n"
        "> aprovados para `docs/PROJETO.md`; não copie este arquivo inteiro.\n\n"
        "## Evidência técnica inicial\n\n"
        f"- Raiz de código configurada: `{codigo['raiz'] or '.'}`.\n"
        f"- Arquivos nas extensões configuradas: **{codigo['arquivos']}**.\n"
        f"- Manifestos observados: {', '.join(f'`{m}`' for m in manifestos) or 'nenhum'}.\n\n"
        "## Precisa de investigação autônoma nas fontes de autoridade\n\n"
        "- O que o projeto faz, para quem e qual é o custo de errar?\n"
        "- Quais ambientes existem?\n"
        "- O que nunca pode ser feito sem autorização?\n"
        "- Qual é a ordem real de testes, promoção e rollback?\n"
    )

    estado_md = _frontmatter("ESTADO-PROPOSTO", "estado", projeto, "Proposta de estado atual")
    estado_md += (
        f"# Estado atual — {projeto}\n\n"
        "> **RASCUNHO AUTOMÁTICO.** Confirme antes de mover para `docs/ESTADO.md`.\n\n"
        f"- Branch observada: `{git['branch'] or '(sem git)'}`\n"
        f"- Commit observado: `{git['commit'] or '(sem commit)'}`\n"
        f"- Árvore alterada durante o diagnóstico: `{'sim' if git['alterado'] else 'não'}`\n\n"
        "## Frente ativa\n\n<confirmar>\n\n"
        "## Bloqueio principal\n\n<confirmar>\n\n"
        "## Próximas três ações\n\n1. <confirmar>\n2. <confirmar>\n3. <confirmar>\n"
    )

    aberto_md = _frontmatter("ABERTO-PROPOSTO", "estado", projeto, "Lacunas da análise inicial")
    aberto_md += f"# Lacunas da análise inicial — {projeto}\n\n"
    aberto_md += "> Revise e promova apenas as lacunas reais para `docs/ABERTO.md`.\n\n"
    for i, pergunta in enumerate(a["lacunas_para_confirmar"], 1):
        aberto_md += f"## ABERTO-PROPOSTO-{i:04d}\n\n{pergunta}\n\n"

    glossario_md = _frontmatter("GLOSSARIO-PROPOSTO", "entrada", projeto, "Proposta de glossário")
    glossario_md += (
        f"# Glossário — {projeto}\n\n"
        "> O inventário estrutural não prova o significado de termos do domínio.\n"
        "> Inclua somente termos confirmados durante a análise funcional.\n\n"
        "| Termo | Significado confirmado | Evidência |\n|---|---|---|\n"
        "| <termo> | <significado> | <arquivo, teste ou responsável> |\n"
    )
    return {
        "PROJETO.md": projeto_md,
        "ESTADO.md": estado_md,
        "ABERTO.md": aberto_md,
        "GLOSSARIO.md": glossario_md,
    }


def main(argv: list[str]) -> int:
    if argv:
        print("`memoria propor-documentacao` ainda não aceita opções.")
        return 2
    saida = Path(raiz()) / ".memoria/propostas"
    propostas = _propostas()
    existentes = [nome for nome in propostas if (saida / nome).exists()]
    if existentes:
        print("Não sobrescrevi propostas existentes:")
        for nome in existentes:
            print(f"  = .memoria/propostas/{nome}")
        print("Revise, mova ou remova conscientemente antes de gerar outra vez.")
        return 1

    saida.mkdir(parents=True, exist_ok=True)
    for nome, conteudo in propostas.items():
        (saida / nome).write_text(conteudo, encoding="utf-8")

    titulo("Propostas de documentação criadas")
    for nome in propostas:
        print(f"  .memoria/propostas/{nome}")
    print("\nFluxo legado. `memoria documentar` promove fatos demonstráveis sem revisão humana.")
    return 0
