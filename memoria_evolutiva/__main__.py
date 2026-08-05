"""memoria — a porta de entrada única dos validadores da memória evolutiva.

Este arquivo não contém lógica: traduz o subcomando para o módulo e repassa argumentos.
A lógica mora nos módulos, onde pode ser lida — e é onde os comentários contam qual bug
de produção gerou cada regra.
"""

from __future__ import annotations

import sys


AJUDA = """memoria — memória evolutiva do projeto

Uso: memoria <comando> [opções]

  instalar   --projeto=NOME --codigo=PASTA [--indice[=FERRAMENTA]] [--grafo=NOME]
  gerar      extrai do código o que não se escreve à mão
  validar    estrutura, âncoras, cadeia, derivados, ponteiros
  catraca    [--medir]   a dívida congelada não pode crescer
  indice     [--marcar]  o índice semântico está em dia?
  verificar  validar + catraca + indice, devolvendo o pior resultado
  autoteste  quebra uma cópia de propósito e confere que os validadores reclamam
  skill      [--conferir] [--saida=DIR]  gera a peça de procedimento a partir do runbook

Rode sempre a partir da raiz do projeto (onde está o padrao.json).
"""


def main() -> int:
    argv = sys.argv[1:]
    cmd = argv[0] if argv else None
    resto = argv[1:]

    if cmd == "verificar":
        # A bateria de fim de sessão e de CI local — um nome só para lembrar.
        from . import validar, catraca, indice
        pior = 0
        for fn in (lambda: validar.main(), lambda: catraca.main([]), lambda: indice.main([])):
            rc = fn()
            pior = max(pior, rc)
        return pior

    if cmd == "instalar":
        from . import instalar
        return instalar.main(resto)
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
