"""Catraca agregada reutilizada pela CLI e pelo instalador.

Um projeto só está pronto quando todas as representações derivadas confirmam a
mesma fonte. Manter essa sequência em um módulo evita que ``memoria instalar`` e
``memoria verificar`` prometam fechamentos diferentes.
"""

from __future__ import annotations

from collections.abc import Callable


def executar(*, incluir_bancos: bool = True) -> int:
    from . import adaptadores, avaliacao, bancos, catraca, fragmentos, skill, validar

    etapas: list[Callable[[], int]] = [
        validar.main,
        lambda: catraca.main([]),
        fragmentos.verificar,
    ]
    if incluir_bancos:
        etapas.append(bancos.status)
    etapas.extend((
        adaptadores.verificar,
        avaliacao.verificar,
        lambda: skill.main(["--conferir"]),
    ))

    pior = 0
    for etapa in etapas:
        pior = max(pior, etapa())
    return pior


def main(argv: list[str]) -> int:
    if argv:
        print("`memoria verificar` não aceita opções.")
        return 2
    return executar()
