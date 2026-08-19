"""documentar — cria e mantém o núcleo factual sem revisão humana obrigatória."""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

from . import analisar, catraca, diagnosticar, gerar, validar
from .lib import commit_atual, config, morre, raiz, titulo


GERENCIADOR = "memoria-documentar"
NUCLEO = ("PROJETO.md", "ESTADO.md", "ABERTO.md", "GLOSSARIO.md")
INICIO_EVOLUTIVO = "<!-- memoria-evolutiva:inicio -->"
FIM_EVOLUTIVO = "<!-- memoria-evolutiva:fim -->"


def _evolutivo(instrucoes: str) -> str:
    return (
        "\n## Conhecimento evolutivo preservado\n\n"
        f"{instrucoes}\n\n"
        f"{INICIO_EVOLUTIVO}\n"
        "<!-- A IA registra aqui fatos duráveis com âncoras. Este bloco sobrevive a "
        "`memoria documentar`. -->\n"
        f"{FIM_EVOLUTIVO}\n"
    )


def _preservar_evolucao(novo: str, atual: str, migrar_legado: bool) -> str:
    # `read_bytes().decode()` preserva CRLF. Reescrever esse texto com `write_text()` no
    # Windows traduziria o LF novamente e produziria CRCRLF; cada execução dobraria as
    # linhas vazias do conhecimento acumulado.
    atual = atual.replace("\r\n", "\n").replace("\r", "\n")
    if INICIO_EVOLUTIVO not in novo or FIM_EVOLUTIVO not in novo:
        return novo
    preservado = ""
    if INICIO_EVOLUTIVO in atual and FIM_EVOLUTIVO in atual:
        preservado = atual.split(INICIO_EVOLUTIVO, 1)[1].split(FIM_EVOLUTIVO, 1)[0].strip()
    elif migrar_legado and atual.strip():
        preservado = (
            "### Conteúdo anterior migrado automaticamente\n\n"
            "O texto abaixo existia antes da adoção do bloco evolutivo. Revise pelas "
            "âncoras antes de promovê-lo.\n\n"
            + atual.strip()
        )
    if not preservado:
        return novo
    inicio, resto = novo.split(INICIO_EVOLUTIVO, 1)
    _, fim = resto.split(FIM_EVOLUTIVO, 1)
    return f"{inicio}{INICIO_EVOLUTIVO}\n{preservado}\n{FIM_EVOLUTIVO}{fim}"


def _frontmatter(id_: str, tipo: str, projeto: str, titulo_: str,
                 ancoras: list[str]) -> str:
    commit = commit_atual() or "sem-commit"
    texto = (
        "---\n"
        f"id: {id_}\n"
        f"tipo: {tipo}\n"
        f"projeto: {projeto}\n"
        f"titulo: {titulo_}\n"
        "status: verificado\n"
        "classificacao: interno\n"
        f"verificado_em: {date.today().isoformat()}\n"
        f"verificado_commit: {commit}\n"
        f"gerenciado_por: {GERENCIADOR}\n"
    )
    if ancoras:
        texto += "ancoras:\n" + "".join(f"  - {a}\n" for a in ancoras)
    return texto + "---\n\n"


def _politica(projeto: str) -> str:
    return _frontmatter(
        "POL-AUTONOMIA", "politica", projeto,
        "Protocolo autônomo de decisão e evidência", ["padrao.json"],
    ) + f"""# Protocolo autônomo — {projeto}

Esta política elimina a revisão humana como etapa obrigatória da documentação. Ela não
autoriza publicação, alteração remota ou ação irreversível: esses limites continuam
dependendo da autorização definida pelo ambiente.

## Ordem de autoridade

A IA decide sempre pela primeira fonte aplicável nesta ordem:

1. comportamento executado, esquema efetivo e contrato de API verificável;
2. testes executáveis que passam no estado analisado;
3. código alcançável pelos fluxos e pontos de entrada;
4. configuração carregada pelo runtime;
5. automação de build, CI, implantação e operação;
6. histórico Git e ADR vigente;
7. documentação canônica ainda compatível com as fontes acima;
8. inferência estrutural.

Fonte inferior nunca corrige fonte superior. Se duas fontes do mesmo nível divergem, a
IA documenta cada comportamento com sua condição de ativação. Se não houver condição
observável que explique a diferença, registra `indeterminado` e não escolhe por gosto.

## Regra de promoção

| Situação | Decisão obrigatória |
|---|---|
| Há fonte primária atual e âncora reproduzível | registrar como fato verificado |
| Há duas fontes concordantes, mas nenhuma execução possível | registrar como inferência corroborada |
| Há apenas nome, comentário ou convenção | registrar como hipótese, nunca como fato |
| Fontes divergem | aplicar a ordem de autoridade e registrar a divergência |
| Não existe evidência suficiente | usar `indeterminado` e continuar sem inventar |
| Ação muda ambiente, dados ou publicação | exigir autorização operacional; não é revisão documental |

## Cobertura obrigatória

`docs/gerado/cobertura-codigo.md` registra todos os arquivos configurados que foram
lidos, com tamanho e SHA-256. Arquivo sem entrada no manifesto está fora da análise.
Mudança de hash invalida a cobertura anterior e exige nova execução de `memoria
documentar`.

## Estrutura padrão

- visão e restrições: `docs/PROJETO.md`;
- fotografia atual: `docs/ESTADO.md`;
- investigações autônomas ainda abertas: `docs/ABERTO.md`;
- linguagem técnica e de domínio: `docs/GLOSSARIO.md`;
- contexto, blocos, runtime, implantação, decisões, riscos e dívida seguem as seções
  equivalentes da estrutura arc42;
- arquitetura usa níveis C4 apenas até o nível sustentado pelas evidências;
- tutoriais, procedimentos, referência e explicação não são misturados no mesmo
  documento.

## Condição de conclusão

A documentação está verificável quando `memoria verificar` e `memoria autoteste` passam.
Essa bateria inclui estrutura, catraca, bancos, adaptadores, skill e avaliação RAG. A
ausência de um fato de negócio não bloqueia a estrutura: fica explícita como
`indeterminado`, com o próximo caminho de investigação definido em `docs/ABERTO.md`.

## Referências do padrão

- arc42: `https://arc42.org/overview`
- C4: `https://c4model.com/abstractions`
- Diátaxis: `https://diataxis.fr/start-here/`
- ADR: `https://docs.arc42.org/section-9/`
"""


def _documentos() -> dict[str, str]:
    d = diagnosticar.coletar(incluir_estado_trabalho=False)
    a = analisar.consolidar(d)
    projeto = d["projeto"]
    codigo = d["codigo"]
    repo = d["repositorio"]
    git = d["git"]
    manifestos = list(repo["manifestos"])
    workflows = list(repo["workflows"])
    ancoras_projeto = ["padrao.json", *manifestos]

    projeto_md = _frontmatter(
        "PROJETO", "entrada", projeto, f"Porta de entrada — {projeto}",
        ancoras_projeto,
    ) + f"""# {projeto}

## O que está comprovado

- Código analisado em `{codigo['raiz'] or '.'}`.
- **{codigo['arquivos']} arquivos** nas extensões configuradas.
- Assinatura conjunta da cobertura: `{codigo['cobertura_sha256']}`.
- Manifestos detectados: {', '.join(f'`{m}`' for m in manifestos) or 'nenhum'}.
- Objetivo de negócio: `indeterminado` enquanto não houver evidência executável ou
  documental ancorada no repositório.

## Ordem de leitura

1. `docs/politicas/AUTONOMIA.md` — como decidir sem perguntar por preferência;
2. `docs/ESTADO.md` — fotografia técnica atual;
3. `docs/ABERTO.md` — fila determinística de investigação;
4. `docs/gerado/diagnostico-projeto.md` — estrutura observada;
5. `docs/gerado/cobertura-codigo.md` — prova arquivo a arquivo;
6. documentos de produto, função, arquitetura, decisão e operação alcançados pelas
   âncoras e pela cadeia `deriva_de`;
7. Hindsight para significado documental e Graphify para estrutura, sempre como
   orientação derivada e nunca como autoridade.

## Regra operacional

Documentação não é autoridade sobre comportamento. Em qualquer divergência, aplique a
ordem de `docs/politicas/AUTONOMIA.md`, atualize o documento inferior e prossiga. Não há
aprovação humana obrigatória para promover fatos sustentados por evidência; ação externa
ou irreversível continua fora desta autorização.
""" + _evolutivo(
        "Registre aqui objetivo, restrições e regras de negócio confirmadas que não "
        "cabem em um PRD/FDD/ADR dedicado."
    )

    estado_ancoras = ["padrao.json", *manifestos, *workflows]
    estado_md = _frontmatter(
        "ESTADO", "estado", projeto, f"Estado técnico — {projeto}", estado_ancoras,
    ) + f"""# Estado técnico — {projeto}

| Evidência | Valor |
|---|---|
| Commit analisado | `{git['commit'] or '(sem commit)'}` |
| Raiz de código | `{codigo['raiz'] or '.'}` |
| Arquivos de código lidos | {codigo['arquivos']} |
| Arquivos de teste detectados | {repo['arquivos_de_teste']} |
| Workflows de CI detectados | {len(workflows)} |
| Assinatura da cobertura | `{codigo['cobertura_sha256']}` |

Esta fotografia é derivada do repositório. Estado de negócio, ambiente ativo e trabalho
em andamento permanecem `indeterminado` até aparecerem em fonte de autoridade superior.
Rode `memoria documentar` novamente após mudança relevante.
""" + _evolutivo(
        "Registre aqui fatos atuais de ambiente, entrega e operação, sempre com fonte e "
        "fronteira entre local, commit, publicação e produção."
    )

    aberto_md = _frontmatter(
        "ABERTO", "estado", projeto, "Fila autônoma de investigação", ["padrao.json"],
    ) + f"# Fila autônoma de investigação — {projeto}\n\n"
    aberto_md += (
        "Itens desta fila não pedem uma decisão humana. A IA percorre cada item pela ordem\n"
        "de autoridade, registra a melhor evidência disponível e usa `indeterminado` se o\n"
        "repositório não contiver resposta demonstrável.\n\n"
        "## Em aberto\n\n"
    )
    for i, pergunta in enumerate(a["lacunas_para_confirmar"], 1):
        tarefa = pergunta.rstrip("?").replace("Qual ", "Determinar ", 1)
        aberto_md += (
            f"### ABERTO-AUTO-{i:04d} — {tarefa}\n\n"
            "**tipo:** indefinicao\n\n"
            "**status:** aberto\n\n"
            "**Procedimento:** procurar primeiro em execução/testes, depois em código, "
            "configuração, CI, histórico e documentação. Registrar âncoras; sem prova, "
            "manter `indeterminado`.\n\n"
        )
    aberto_md += _evolutivo(
        "Registre aqui investigações abertas, resolvidas e próximos passos. Não apague "
        "o histórico: marque a resolução e a evidência."
    )

    termos = [
        ("acervo canônico", "Documentação versionada em `docs/`; fonte documental principal."),
        ("âncora", "Caminho verificável que liga uma afirmação ao repositório."),
        ("cobertura", "Lista das fontes lidas, identificadas por SHA-256."),
        ("indeterminado", "Fato não demonstrável pelas fontes disponíveis; não é licença para inferir."),
        ("derivado", "Artefato reproduzível pelo comando `memoria gerar`; nunca editado à mão."),
    ]
    glossario_md = _frontmatter(
        "GLOSSARIO", "entrada", projeto, f"Glossário verificável — {projeto}",
        ["padrao.json"],
    ) + f"# Glossário verificável — {projeto}\n\n"
    glossario_md += "| Termo | Definição sustentada pelo padrão |\n|---|---|\n"
    for termo, definicao in termos:
        glossario_md += f"| {termo} | {definicao} |\n"
    glossario_md += (
        "\nTermo de domínio só entra quando houver uso observável em código, contrato, teste\n"
        "ou esquema. Nome isolado não recebe significado inventado.\n"
    )
    glossario_md += _evolutivo(
        "Registre aqui termos de domínio confirmados no código, contrato, teste ou esquema."
    )

    return {
        "PROJETO.md": projeto_md,
        "ESTADO.md": estado_md,
        "ABERTO.md": aberto_md,
        "GLOSSARIO.md": glossario_md,
        "politicas/AUTONOMIA.md": _politica(projeto),
    }


def executar(substituir_iniciais: set[str] | None = None,
             sincronizar_bancos: bool = True,
             inicializar_avaliacao: bool = False) -> int:
    """Atualiza o núcleo; conteúdo anterior é arquivado, nunca descartado."""
    diagnosticar._arquivos.cache_clear()
    diagnosticar.inventario_projeto.cache_clear()
    diagnosticar.inventario_codigo.cache_clear()
    substituir_iniciais = substituir_iniciais or set()
    base_raiz = Path(raiz()).resolve()
    base_docs = (base_raiz / config()["acervos"]["canonico"].strip("/")).resolve()
    if not base_docs.is_relative_to(base_raiz):
        morre("`acervos.canonico` precisa ficar dentro da raiz do projeto.\n")
    escritos: list[str] = []
    arquivados: list[str] = []

    for relativo, conteudo in _documentos().items():
        destino = base_docs / relativo
        atual = destino.read_bytes() if destino.is_file() else b""
        gerenciado = f"gerenciado_por: {GERENCIADOR}" in atual.decode(
            "utf-8", errors="replace"
        )
        if atual and not gerenciado and relativo not in substituir_iniciais:
            digest = hashlib.sha256(atual).hexdigest()[:12]
            nome_seguro = relativo.replace("/", "__")
            arquivo = base_raiz / ".memoria/legado-documentacao" / (
                f"{digest}__{nome_seguro}"
            )
            arquivo.parent.mkdir(parents=True, exist_ok=True)
            if not arquivo.is_file():
                arquivo.write_bytes(atual)
            arquivados.append(str(arquivo.relative_to(base_raiz)).replace("\\", "/"))
        destino.parent.mkdir(parents=True, exist_ok=True)
        conteudo = _preservar_evolucao(
            conteudo,
            atual.decode("utf-8", errors="replace"),
            migrar_legado=bool(atual and relativo not in substituir_iniciais),
        )
        destino.write_text(conteudo, encoding="utf-8")
        escritos.append(relativo)

    # Adaptadores carregam a raiz absoluta do projeto. Em worktree isolada eles mudam;
    # as entradas precisam nascer antes da cobertura. O manifesto, porém, referencia o
    # RAG: ele só fecha depois de gerar cobertura e fragmentos, formando um pipeline
    # acíclico em vez de aceitar um artefato velho como bootstrap.
    from . import adaptadores
    rc_preparar_adaptadores = adaptadores.preparar()
    if rc_preparar_adaptadores != 0:
        return rc_preparar_adaptadores
    # `_documentos()` já inventariou o projeto antes de as entradas mudarem. A
    # cobertura precisa reler bytes reais, não reutilizar esse cache pré-adaptador.
    diagnosticar._arquivos.cache_clear()
    diagnosticar.inventario_projeto.cache_clear()
    diagnosticar.inventario_codigo.cache_clear()

    rc_gerar = gerar.main()
    if rc_gerar != 0:
        return rc_gerar

    from . import fragmentos
    rc_fragmentos = fragmentos.gerar()
    if rc_fragmentos != 0:
        return rc_fragmentos

    rc_adaptadores = adaptadores.gerar()
    if rc_adaptadores != 0:
        return rc_adaptadores

    c = config()
    baseline = Path(raiz()) / c.get("catraca", {}).get(
        "linha_de_base", "docs/politicas/baseline.json"
    ).strip("/")
    if not baseline.is_file():
        rc_catraca = catraca.main(["--medir"])
        if rc_catraca != 0:
            return rc_catraca

    rc_validar = validar.main()
    rc_catraca = catraca.main([])
    titulo("Documentação autônoma")
    for caminho in escritos:
        print(f"  ~ docs/{caminho}")
    for caminho in arquivados:
        print(f"  > conteúdo anterior preservado em {caminho}")
    print("\nRevisão humana documental: não obrigatória.")
    print("Fatos sem prova permanecem `indeterminado`; ações externas mantêm suas autorizações.")
    rc = max(rc_validar, rc_catraca)
    if rc == 0 and sincronizar_bancos:
        from . import bancos
        if (c.get("memoria", {}).get("ativo") or c.get("grafo", {}).get("ativo")):
            print("\nSincronizando os bancos derivados obrigatórios...")
            rc = max(rc, bancos.sincronizar())
    if rc == 0:
        from . import avaliacao
        if inicializar_avaliacao and not avaliacao.baseline_path().is_file():
            rc = max(rc, avaliacao.medir())
        else:
            rc = max(rc, avaliacao.gerar())
    return rc


def main(argv: list[str]) -> int:
    if argv:
        print("`memoria documentar` não aceita opções.")
        return 2
    return executar()
