---
id: POL-00XX
tipo: politica
projeto: <nome>
titulo: <área que esta política governa>
status: verificado
verificado_em: AAAA-MM-DD
verificado_commit: <sha>
implementada_em: []
---

# <título>

> **`implementada_em` vazio significa que esta política ainda é só texto.**
> Isso é informação, não vergonha — mas trava é código, não prompt. Enquanto o campo
> estiver vazio, nada impede que a regra seja violada em silêncio.

## Regra

> <A regra em uma frase, imperativa.>

## Detalhamento

### 1. <subtema>

<Regras específicas. Prefira "nunca X porque Y" a "evite X".>

---

## Conformidade medida em <data>

<**Meça contra o código antes de publicar a política.** O resultado costuma
surpreender, e o número medido é o que permite a catraca existir.>

| Regra | Estado | Evidência |
|---|---|---|
| <regra> | ❌ N ocorrências | <onde> |
| <regra> | ✅ | <como foi conferido> |
| <regra> | ❓ não verificável | <por quê> |

## Como verificar que está valendo

<Comando ou contador da catraca. Se não houver, diga — e isso vira candidato
a item da fila de arbitragem.>

## Estado

```
documental        ← só texto, nada verifica
piloto-catraca    ← medido e congelado, falha se piorar
piloto-aviso      ← reporta, não quebra
enforcement       ← falha dura
```

<Marque onde esta política está. O padrão fica mais rígido com o tempo, nunca menos.>
