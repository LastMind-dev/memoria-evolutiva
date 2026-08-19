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

import contextlib
import io
import re
import tempfile
from pathlib import Path

from . import gerar, seguranca
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

    autonomia = c.get("autonomia", {})
    if autonomia.get("ativo"):
        if autonomia.get("revisao_humana_obrigatoria") is not False:
            erros.append(
                "padrao.json: autonomia ativa exige `revisao_humana_obrigatoria: false`"
            )
        if autonomia.get("sem_evidencia") != "indeterminado":
            erros.append(
                "padrao.json: autonomia ativa exige `sem_evidencia: indeterminado`"
            )
        politica = str(autonomia.get("politica") or "")
        if not politica or not (Path(raiz()) / politica).is_file():
            erros.append(
                "padrao.json: política autônoma ausente; rode `memoria documentar`"
            )
        if "cobertura-codigo" not in c.get("gerado", {}).get("extratores", []):
            erros.append(
                "padrao.json: autonomia exige o extrator `cobertura-codigo`"
            )

    memoria = c.get("memoria", {})
    grafo = c.get("grafo", {})
    if bool(memoria.get("ativo")) != bool(grafo.get("ativo")):
        erros.append("padrao.json: Hindsight e Graphify devem estar ambos ativos ou ambos desativados")
    if memoria.get("ativo"):
        if memoria.get("obrigatorio") is not True:
            erros.append("padrao.json: Hindsight ativo exige `memoria.obrigatorio: true`")
        if memoria.get("ferramenta") != "hindsight" or memoria.get("modo") != "local":
            erros.append("padrao.json: o banco documental padrão é `hindsight` em modo `local`")
        if not memoria.get("endpoint") or not memoria.get("banco"):
            erros.append("padrao.json: Hindsight exige `endpoint` e `banco`")
        if memoria.get("consulta_budget", "mid") not in {"low", "mid", "high"}:
            erros.append("padrao.json: `memoria.consulta_budget` precisa ser low, mid ou high")
        for chave, padrao, minimo, maximo in (
            ("consultas_paralelas", 2, 1, 32),
            ("cache_consulta_ttl_segundos", 30, 0, 3600),
        ):
            valor = memoria.get(chave, padrao)
            if isinstance(valor, bool) or not isinstance(valor, int) or not minimo <= valor <= maximo:
                erros.append(
                    f"padrao.json: `memoria.{chave}` precisa ser inteiro entre "
                    f"{minimo} e {maximo}"
                )
    if grafo.get("ativo"):
        if grafo.get("obrigatorio") is not True:
            erros.append("padrao.json: Graphify ativo exige `grafo.obrigatorio: true`")
        if grafo.get("ferramenta") != "graphify" or grafo.get("modo") != "local":
            erros.append("padrao.json: o grafo de código padrão é `graphify` em modo `local`")
        if not grafo.get("comando") or not grafo.get("arquivo") or not grafo.get("marcador"):
            erros.append("padrao.json: Graphify exige `comando`, `arquivo` e `marcador`")
        literais = grafo.get("extensoes_literais", [".sql"])
        if literais != [".sql"]:
            erros.append(
                "padrao.json: `grafo.extensoes_literais` precisa ser exatamente ['.sql']"
            )

    contexto = c.get("contexto", {})
    if contexto:
        for chave, padrao, minimo, maximo in (
            ("max_tokens", 2048, 64, 32768),
            ("max_fontes", 8, 1, 100),
            ("max_codigo", 5, 0, 100),
            ("http_porta", 8765, 0, 65535),
        ):
            valor = contexto.get(chave, padrao)
            if isinstance(valor, bool) or not isinstance(valor, int) or not minimo <= valor <= maximo:
                erros.append(
                    f"padrao.json: `contexto.{chave}` precisa ser inteiro entre "
                    f"{minimo} e {maximo}"
                )
        if contexto.get("http_host", "127.0.0.1") not in {
            "127.0.0.1", "localhost", "::1",
        }:
            erros.append("padrao.json: `contexto.http_host` aceita somente loopback")

    politica_segura = c.get("seguranca_memoria", {})
    esperado_seguro = {
        "ativo": True,
        "classificacao_padrao": "interno",
        "nao_indexar": ["secreto-nao-indexar"],
        "escopo": "produto-tenant-exato-v1",
        "perfis_com_escopo_obrigatorio": ["atendimento", "operacao-assistida"],
        "redaction_antes_retain": True,
        "redaction_algoritmo": "redaction-deterministica-v1",
    }
    if not isinstance(politica_segura, dict):
        erros.append("padrao.json: `seguranca_memoria` precisa ser objeto")
    else:
        for chave, valor in esperado_seguro.items():
            if politica_segura.get(chave) != valor:
                erros.append(
                    f"padrao.json: `seguranca_memoria.{chave}` precisa ser "
                    f"{valor!r} na Fase 4"
                )

    adaptadores = c.get("adaptadores", {})
    if adaptadores:
        plataformas_validas = {"codex", "claude", "cursor", "windsurf", "hermes"}
        plataformas = adaptadores.get("plataformas")
        if (not isinstance(plataformas, list) or not plataformas
                or any(not isinstance(item, str) for item in plataformas)
                or len(set(plataformas)) != len(plataformas)
                or any(item not in plataformas_validas for item in plataformas)):
            erros.append("padrao.json: `adaptadores.plataformas` precisa listar clientes válidos sem duplicatas")
        perfil = adaptadores.get("perfil_canary")
        from .contexto import PERFIS
        if perfil not in PERFIS:
            erros.append("padrao.json: `adaptadores.perfil_canary` precisa ser perfil válido")
        manifesto_adaptadores = adaptadores.get("manifesto")
        if not isinstance(manifesto_adaptadores, str) or not manifesto_adaptadores.endswith(".json"):
            erros.append("padrao.json: `adaptadores.manifesto` precisa ser caminho JSON")

    ciclo = c.get("ciclo", {})
    contrato_ciclo = {
        "ativo": True,
        "auto_reparar_no_inicio": True,
        "iniciar_hindsight_embed": True,
        "mutacao_externa": "somente-bancos-locais",
        "publicacao_automatica": False,
    }
    if not isinstance(ciclo, dict):
        erros.append("padrao.json: `ciclo` precisa ser objeto")
    else:
        for chave, valor in contrato_ciclo.items():
            if ciclo.get(chave) != valor:
                erros.append(
                    f"padrao.json: `ciclo.{chave}` precisa ser {valor!r} no ciclo autônomo"
                )
        timeout_ciclo = ciclo.get("timeout_inicializacao_segundos", 180)
        if (isinstance(timeout_ciclo, bool) or not isinstance(timeout_ciclo, int)
                or not 10 <= timeout_ciclo <= 600):
            erros.append(
                "padrao.json: `ciclo.timeout_inicializacao_segundos` precisa ser "
                "inteiro entre 10 e 600"
            )

    agendamento = c.get("agendamento", {})
    contrato_agendamento = {
        "ativo": True,
        "registrar_na_instalacao": True,
        "frequencia": "diaria",
        "comando": "memoria-agendador-v1",
        "banco_negocio": "proibido",
        "publicacao_automatica": False,
    }
    if not isinstance(agendamento, dict):
        erros.append("padrao.json: `agendamento` precisa ser objeto")
    else:
        for chave, valor in contrato_agendamento.items():
            if agendamento.get(chave) != valor:
                erros.append(
                    f"padrao.json: `agendamento.{chave}` precisa ser {valor!r} "
                    "na manutenção zero-touch"
                )
        horario = agendamento.get("horario_local", "02:15")
        if not isinstance(horario, str) or not re.fullmatch(
            r"(?:[01]\d|2[0-3]):[0-5]\d", horario
        ):
            erros.append(
                "padrao.json: `agendamento.horario_local` precisa usar HH:MM entre 00:00 e 23:59"
            )

    executor = c.get("executor", {})
    contrato_executor = {
        "ativo": True,
        "estado": ".memoria/executor",
        "isolamento": "git-worktree-branch-v1",
        "mutacao_externa_padrao": "negada",
        "publicacao_automatica": False,
    }
    if not isinstance(executor, dict):
        erros.append("padrao.json: `executor` precisa ser objeto")
    else:
        for chave, valor in contrato_executor.items():
            if executor.get(chave) != valor:
                erros.append(
                    f"padrao.json: `executor.{chave}` precisa ser {valor!r} na Fase 5"
                )
        for chave, padrao, minimo, maximo in (
            ("timeout_global_segundos", 900, 1, 86400),
            ("max_tentativas", 3, 1, 10),
            ("backoff_segundos", 1, 0, 300),
            ("lock_expira_segundos", 1200, 30, 172800),
        ):
            valor = executor.get(chave, padrao)
            if (isinstance(valor, bool) or not isinstance(valor, int)
                    or not minimo <= valor <= maximo):
                erros.append(
                    f"padrao.json: `executor.{chave}` precisa ser inteiro entre "
                    f"{minimo} e {maximo}"
                )
        timeout_executor = executor.get("timeout_global_segundos", 900)
        expira_executor = executor.get("lock_expira_segundos", 1200)
        if (isinstance(timeout_executor, int) and not isinstance(timeout_executor, bool)
                and isinstance(expira_executor, int) and not isinstance(expira_executor, bool)
                and expira_executor <= timeout_executor):
            erros.append(
                "padrao.json: `executor.lock_expira_segundos` precisa superar o timeout global"
            )
        capacidades = executor.get("capacidades_permitidas", [])
        if (not isinstance(capacidades, list)
                or any(not isinstance(item, str) for item in capacidades)
                or len(capacidades) != len(set(capacidades))
                or set(capacidades) - {"sincronizar-bancos"}):
            erros.append(
                "padrao.json: `executor.capacidades_permitidas` aceita somente "
                "`sincronizar-bancos`, sem duplicatas"
            )

    avaliacao = c.get("avaliacao", {})
    contrato_avaliacao = {
        "ativo": True,
        "corpus": "docs/avaliacao/casos-rag-v1.json",
        "baseline": "docs/politicas/baseline-rag-v1.json",
        "relatorio": "docs/gerado/relatorio-avaliacao-rag-v1.json",
        "manifesto": "docs/gerado/manifesto-avaliacao-rag-v1.json",
    }
    if not isinstance(avaliacao, dict):
        erros.append("padrao.json: `avaliacao` precisa ser objeto")
    else:
        for chave, valor in contrato_avaliacao.items():
            if avaliacao.get(chave) != valor:
                erros.append(
                    f"padrao.json: `avaliacao.{chave}` precisa ser {valor!r} na Fase 6"
                )
        for chave, padrao in (
            ("min_hit_1", 0.5), ("min_hit_3", 1.0),
            ("min_cobertura_citacao", 1.0), ("min_cobertura_resposta", 1.0),
            ("max_sem_fonte", 0.0), ("min_negativos_ok", 1.0),
            ("regressao_maxima", 0.0),
        ):
            valor = avaliacao.get(chave, padrao)
            if (isinstance(valor, bool) or not isinstance(valor, (int, float))
                    or not 0 <= float(valor) <= 1):
                erros.append(
                    f"padrao.json: `avaliacao.{chave}` precisa ser número entre 0 e 1"
                )
        usos = avaliacao.get("min_usos_promocao", 2)
        if isinstance(usos, bool) or not isinstance(usos, int) or not 1 <= usos <= 100:
            erros.append(
                "padrao.json: `avaliacao.min_usos_promocao` precisa ser inteiro entre 1 e 100"
            )
        corpus = Path(raiz()) / str(avaliacao.get("corpus") or "")
        if not corpus.is_file():
            erros.append("padrao.json: corpus de avaliação ausente; rode `memoria instalar`")

    for f in arquivos:
        rel = relativo(f)
        if comeca_com(rel, ignorar):
            continue
        if comeca_com(rel, externos):
            fora_da_regua.append(rel)
            continue

        texto_documento = Path(f).read_text(encoding="utf-8")
        fm = frontmatter(texto_documento)

        # DOCUMENTO SEM FRONTMATTER É DÍVIDA, NÃO ERRO — reprovar o passivo deixa o
        # build vermelho desde o dia um, e build que nasce vermelho ninguém olha.
        if fm is None:
            legados.append(rel)
            continue

        nucleo_gerenciado = {
            f"{c['acervos']['canonico'].strip('/')}/{nome}"
            for nome in ("PROJETO.md", "ESTADO.md", "ABERTO.md", "GLOSSARIO.md")
        }
        if fm.get("gerenciado_por") == "memoria-documentar" and rel in nucleo_gerenciado:
            inicio = "<!-- memoria-evolutiva:inicio -->"
            fim = "<!-- memoria-evolutiva:fim -->"
            if (texto_documento.count(inicio) != 1 or texto_documento.count(fim) != 1
                    or texto_documento.index(inicio) > texto_documento.index(fim)):
                erros.append(
                    f"{rel}: bloco evolutivo ausente, duplicado ou invertido. "
                    "Rode `memoria documentar` para reparar sem perder a cópia anterior."
                )

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

        try:
            acesso = seguranca.metadados(fm)
        except seguranca.SegurancaErro as exc:
            erros.append(f"{rel}: política de acesso inválida — {exc}")
            acesso = None
        if (acesso is not None and acesso["classificacao"] == "publico"
                and fm.get("classificacao") != "publico"):
            erros.append(f"{rel}: documento público precisa declarar `classificacao: publico`")

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
        if (autonomia.get("ativo") and fm.get("status") == "verificado"
                and fm.get("tipo") != "gerado" and not ancoras):
            erros.append(
                f"{rel}: documento verificado sem `ancoras` no modo autônomo"
            )

    # ------------------------------------------------------- 5: derivados vivos
    dir_gerado = Path(raiz()) / c["gerado"].get("diretorio", "").strip("/")
    atuais = ({g.name: g.read_text(encoding="utf-8")
               for g in sorted(dir_gerado.glob("*.md"))}
              if dir_gerado.is_dir() else {})

    # Gerar na própria árvore e tentar desfazer deixou duas frestas reais: derivado
    # ausente era criado e aprovado, e arquivo novo produzido antes de uma falha ficava
    # para trás. A saída esperada nasce numa pasta temporária; a árvore validada é
    # somente leitura para o motor embutido.
    with tempfile.TemporaryDirectory(prefix="validar-memoria-") as tmp:
        esperado_dir = Path(tmp) / "gerado"
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stderr(stderr):
                rc_gerar = gerar.main(saida_override=esperado_dir, silencioso=True)
        except SystemExit as e:
            rc_gerar = int(e.code) if isinstance(e.code, int) else 2

        if rc_gerar != 0:
            saida = stderr.getvalue().strip().splitlines()[:3]
            erros.append("o gerador falhou: " + " | ".join(saida or [f"saída {rc_gerar}"]))
        else:
            esperados = {
                g.name: g.read_text(encoding="utf-8")
                for g in sorted(esperado_dir.glob("*.md"))
            }
            faltando = sorted(set(esperados) - set(atuais))
            sobrando = sorted(set(atuais) - set(esperados))

            for nome in faltando:
                erros.append(
                    f"{c['gerado']['diretorio']}/{nome}: derivado ausente. "
                    "Rode `memoria gerar` e commite a saída."
                )
            for nome in sobrando:
                erros.append(
                    f"{c['gerado']['diretorio']}/{nome}: derivado sem extrator declarado. "
                    "Remova-o ou declare o extrator correspondente em `padrao.json`."
                )
            for nome in sorted(set(atuais) & set(esperados)):
                if hash_do_conteudo(atuais[nome]) != hash_do_conteudo(esperados[nome]):
                    erros.append(
                        f"{c['gerado']['diretorio']}/{nome}: desatualizado ou editado à mão. "
                        "Rode `memoria gerar` e commite a saída."
                    )

    if autonomia.get("ativo"):
        # A política de decisão é parte do motor, não uma preferência do projeto. Se ela
        # for alterada à mão, duas IAs podem tomar decisões opostas com build verde.
        from . import documentar
        rel_politica = str(autonomia.get("politica"))
        politica_atual = Path(raiz()) / rel_politica
        politica_esperada = documentar._documentos()["politicas/AUTONOMIA.md"]
        if (politica_atual.is_file()
                and hash_do_conteudo(politica_atual.read_text(encoding="utf-8"))
                != hash_do_conteudo(politica_esperada)):
            erros.append(
                f"{rel_politica}: política autônoma alterada. Rode `memoria documentar`."
            )

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
