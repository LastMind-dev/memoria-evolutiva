# Adaptadores de agentes

`memoria adaptadores` conecta o mesmo gateway de contexto a Codex, Claude, Cursor,
Windsurf e Hermes. Os arquivos por cliente são derivados e guardam somente descoberta,
perfil e limites operacionais; fatos continuam exclusivamente em `docs/`.

## Gerar e verificar

```bash
memoria adaptadores gerar
memoria adaptadores verificar
```

O manifesto neutro fica em `docs/gerado/manifesto-adaptadores-v1.json`. Ele registra
projeto, bank, perfil do canary, schema do gateway, hash do manifesto fragmentado e hash
da parte gerenciada de cada adaptador. Alterações em outros servidores MCP do projeto
são preservadas e não invalidam este adaptador.

| Cliente | Instrução descoberta | Gateway |
|---|---|---|
| Codex | bloco gerenciado em `AGENTS.md` | `.codex/config.toml`, MCP stdio obrigatório e read-only |
| Claude | bloco gerenciado em `CLAUDE.md` | `.mcp.json`, MCP stdio de escopo do projeto |
| Cursor | `.cursor/rules/memoria-evolutiva.mdc` | `.cursor/mcp.json` |
| Windsurf | `.windsurf/rules/memoria-evolutiva.md` | CLI neutra; a configuração MCP do Windsurf é global e não é alterada pelo projeto |
| Hermes | bloco gerenciado em `.hermes.md` | CLI neutra; configuração e memória globais do Hermes não são alteradas |

Codex, Claude e Cursor recebem o mesmo servidor `memoria contexto mcp`. Windsurf e
Hermes descobrem a mesma porta pelo comando `memoria contexto`; isso evita modificar
automaticamente arquivos globais do usuário. Todos chegam a `contexto.construir()` e ao
mesmo envelope v2 com escopo e cobertura explícitos.

## Canary obrigatório

Cada cliente roda, antes da primeira consulta substancial:

```bash
memoria adaptadores canary \
  --plataforma=codex \
  --perfil=engenharia-leitura \
  --json
```

Troque somente o identificador da plataforma. O canary falha se não confirmar:

- adaptador e manifesto atuais;
- projeto e perfil exatos;
- bank configurado, ou opt-out explícito dos bancos;
- frescor dos provedores ativos;
- ao menos uma fonte documental atual;
- commit Git atual; projeto ainda sem commit não passa no canary.

`worktree_sujo` é evidência, não reprovação: uma sessão pode estar trabalhando em uma
mudança local legítima. O campo `acoes_permitidas` permanece vazio.

## Perfis sem escolha ambígua

- leitura, diagnóstico e análise: `engenharia-leitura`;
- criação ou manutenção documental: `engenharia-documentacao`;
- execução automatizada sobre código: `automacao-codigo`;
- `atendimento` e `operacao-assistida`: exigem `produto` e `tenant` explícitos, derivados
  da identidade autenticada da chamada; não reutilizam escopo ou conversa anterior.

O perfil continua obrigatório em cada chamada. O adaptador orienta a seleção objetiva,
mas nunca amplia permissões do gateway.

## Segurança e compatibilidade

O instalador faz merge apenas na entrada MCP `memoria-evolutiva`; servidores alheios são
preservados. Blocos Markdown/TOML usam marcadores próprios. Marcador incompleto,
duplicado, entrada adulterada, schema antigo ou manifesto divergente falha em
`memoria adaptadores verificar` e também em `memoria verificar`.

Clientes ainda podem exigir confiança do workspace antes de iniciar uma configuração MCP
versionada. Essa confirmação é uma barreira de segurança do cliente, não uma revisão
humana do conteúdo da memória. Depois da confiança, o canary decide objetivamente se a
memória pode ser usada.

Referências oficiais: [MCP no Codex](https://learn.chatgpt.com/docs/extend/mcp?surface=cli),
[MCP no Claude Code](https://code.claude.com/docs/en/mcp),
[regras do Cursor](https://docs.cursor.com/context/rules) e
[MCP no Windsurf](https://docs.devin.ai/desktop/cascade/mcp).
