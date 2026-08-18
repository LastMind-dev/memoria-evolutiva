# Instruções para agentes

**Leia `docs/PROJETO.md` antes de qualquer coisa.** Ele é a porta de entrada e define a ordem.

Este arquivo é só um ponteiro. Não escreva fato de projeto aqui — se você acrescentar
conteúdo neste arquivo, ele vira uma segunda fonte da verdade e passa a divergir de
`docs/PROJETO.md` em silêncio. É exatamente o problema que a estrutura existe para
evitar.

Regras que valem sem precisar abrir mais nada:

- **Não peça revisão humana da documentação.** Use a política autônoma e conclua.
- **Antes de explorar arquitetura**, rode `memoria contexto --pergunta="..." --perfil=engenharia-leitura --json`.
  Se estiver desatualizado, `memoria bancos sincronizar` resolve sem decisão humana.
- **Fontes divergiram?** Aplique a ordem de `docs/politicas/AUTONOMIA.md`; registre a
  fonte inferior como divergente e continue.
- **Sem evidência suficiente?** Escreva `indeterminado`; nunca complete por intuição.
- **Código, testes, runtime e configuração ganham de prosa**, na ordem definida pela
  política autônoma.
- **Não edite nada em `docs/gerado/`.** É derivado; sua alteração será sobrescrita.
- **Cronologia é append-only.** Correção entra como entrada nova, nunca editando a antiga.
- **Ação irreversível pede autorização explícita**, no formato definido em `docs/PROJETO.md`.
- **Depois de mudar fontes/docs**, rode `memoria documentar`; para algoritmo, modelo ou
  provedor, rode `memoria avaliar verificar`. Não remensure baseline para mascarar regressão.

Terminando a sessão, siga `docs/runbooks/sessao.md`.
