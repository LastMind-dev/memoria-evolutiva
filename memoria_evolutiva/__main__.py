"""memoria — a porta de entrada única dos validadores da memória evolutiva.

Este arquivo não contém lógica: traduz o subcomando para o módulo e repassa argumentos.
A lógica mora nos módulos, onde pode ser lida — e é onde os comentários contam qual bug
de produção gerou cada regra.
"""

from __future__ import annotations

import sys


AJUDA = """memoria — memória evolutiva do projeto

Uso: memoria <comando> [opções]

  instalar   --projeto=NOME --codigo=PASTA [--adiar-bancos|--sem-bancos] [--sem-agendamento]
  diagnosticar [--json]  inventário factual; não escreve no projeto
  analisar    [--json]  consolida evidências e lacunas; não escreve no projeto
  propor-documentacao   legado: cria rascunhos opcionais, sem sobrescrever
  documentar  gera, decide e valida o núcleo factual sem revisão humana obrigatória
  gerar      extrai do código o que não se escreve à mão
  validar    estrutura, âncoras, cadeia, derivados, ponteiros
  catraca    [--medir]   a dívida congelada não pode crescer
  bancos     [status [--offline]|sincronizar|consultar --pergunta=TEXTO]  Hindsight + Graphify
  fragmentos [gerar|verificar|status]  manifesto determinístico do RAG em modo sombra
  contexto   --pergunta=TEXTO --perfil=PERFIL --json | mcp | http
  adaptadores [gerar|verificar|status|canary]  entradas de Codex, Claude, Cursor, Windsurf e Hermes
  ciclo      iniciar|atualizar --plataforma=ID --perfil=PERFIL --json  manutenção zero-touch
  agendador  instalar|status|executar|remover --json  atualização diária sem banco de negócio
  executar   --run-id=ID --acao=documentar|verificar --json  executor isolado e retomável
  avaliar    [medir|gerar|verificar|status] [--json]  métricas e catraca do RAG
  indice     compatibilidade: verifica a cópia documental no Hindsight
  verificar  estrutura + catraca + bancos + adaptadores + avaliação + skill
  autoteste  quebra uma cópia de propósito e confere que os validadores reclamam
  skill      [--conferir] [--saida=DIR]  gera a peça de procedimento a partir do runbook

Rode sempre a partir da raiz do projeto (onde está o padrao.json).
"""


def main() -> int:
    # Saída redirecionada no Windows pode cair em CP1252. Configure antes da primeira
    # mensagem para que caracteres decorativos nunca interrompam uma operação.
    from .lib import preparar_saida
    preparar_saida()

    argv = sys.argv[1:]
    cmd = argv[0] if argv else None
    resto = argv[1:]

    if cmd == "verificar":
        # A bateria de fim de sessão e de CI local — um nome só para lembrar.
        from . import validar, catraca, bancos, skill, adaptadores, avaliacao
        pior = 0
        for fn in (
            lambda: validar.main(),
            lambda: catraca.main([]),
            lambda: bancos.status(),
            lambda: adaptadores.verificar(),
            lambda: avaliacao.verificar(),
            lambda: skill.main(["--conferir"]),
        ):
            rc = fn()
            pior = max(pior, rc)
        return pior

    if cmd == "instalar":
        from . import instalar
        return instalar.main(resto)
    if cmd == "diagnosticar":
        from . import diagnosticar
        return diagnosticar.main(resto)
    if cmd == "analisar":
        from . import analisar
        return analisar.main(resto)
    if cmd == "propor-documentacao":
        from . import propor_documentacao
        return propor_documentacao.main(resto)
    if cmd == "documentar":
        from . import documentar
        return documentar.main(resto)
    if cmd == "gerar":
        from . import gerar
        return gerar.main()
    if cmd == "validar":
        from . import validar
        return validar.main()
    if cmd == "catraca":
        from . import catraca
        return catraca.main(resto)
    if cmd == "indice":
        from . import indice
        return indice.main(resto)
    if cmd == "bancos":
        from . import bancos
        return bancos.main(resto)
    if cmd == "fragmentos":
        from . import fragmentos
        return fragmentos.main(resto)
    if cmd == "contexto":
        from . import contexto
        return contexto.main(resto)
    if cmd == "adaptadores":
        from . import adaptadores
        return adaptadores.main(resto)
    if cmd == "ciclo":
        from . import ciclo
        return ciclo.main(resto)
    if cmd == "agendador":
        from . import agendador
        return agendador.main(resto)
    if cmd == "executar":
        from . import executor
        return executor.main(resto)
    if cmd == "avaliar":
        from . import avaliacao
        return avaliacao.main(resto)
    if cmd == "autoteste":
        from . import autoteste
        return autoteste.main()
    if cmd == "skill":
        from . import skill
        return skill.main(resto)

    sys.stderr.write(AJUDA)
    return 0 if cmd is None else 2


if __name__ == "__main__":
    raise SystemExit(main())
