# Ciclo zero-touch dos agentes

O projeto é preparado uma vez. Depois disso, Codex, Claude, Cursor, Windsurf e Hermes
recebem o mesmo contrato gerado, sem manter cópias dos fatos fora de `docs/`.

## Instalação única

O extra `local` instala as duas dependências derivadas suportadas: `graphifyy` e
`hindsight-embed`. Com `pipx`, `--include-deps` também expõe seus executáveis:

```bash
pipx install --include-deps "memoria-evolutiva[local] @ git+https://github.com/LastMind-dev/memoria-evolutiva.git@main"
cd meu-projeto
memoria instalar --projeto="meu-projeto" --codigo=src
```

O Hindsight continua independente do modelo. Seu perfil global ou as variáveis
`HINDSIGHT_API_LLM_*` definem o provedor; segredo e escolha de modelo não entram no
repositório. Se o endpoint local padrão estiver parado e `hindsight-embed` já estiver
configurado, o instalador inicia o daemon sob demanda. Graphify é descoberto no PATH,
no ambiente do pacote ou no diretório de ferramentas do `uv`.

## Início de qualquer agente

```bash
memoria ciclo iniciar --plataforma=codex --perfil=engenharia-leitura --json
```

O comando confirma os provedores e o canary. Se detectar estado velho, roda
`memoria documentar` e repete a prova. Com tudo fresco, não reescreve documentação.

## Depois de mudar código ou documentação

```bash
memoria ciclo atualizar --plataforma=codex --perfil=engenharia-leitura --json
```

Esse caminho relê as fontes, atualiza o núcleo gerenciado, regenera derivados, valida,
sincroniza Hindsight+Graphify e termina com novo canary. Os blocos gerenciados de cada
cliente já contêm os comandos com sua própria identidade de plataforma.

## Manutenção diária sem operador

A instalação completa registra uma execução diária às 02:15 no Agendador de Tarefas
do Windows ou no crontab do usuário. O job chama um comando fechado, sem aceitar shell,
SQL, conexão ou credencial da aplicação:

```bash
memoria agendador status --json
memoria agendador executar --json
```

Scripts e logs ficam em `.memoria/agendador/`, fora do Git. A instalação é idempotente:
rodar novamente substitui somente a tarefa identificada por este projeto. Use
`--sem-agendamento` apenas quando o ambiente não permitir registrar tarefas do usuário.

## Fronteiras

O ciclo pode escrever documentação do projeto e os dois bancos locais configurados.
Ele nunca cria commit, não faz push, não abre PR, não publica, não faz deploy e não toca
o banco de negócio. A atualização agendada compartilha o mesmo lock do executor para
impedir duas escritas concorrentes e devolve explicitamente `banco_negocio: nao_acessado`.
O executor isolado continua disponível para produzir patches retomáveis. A memória
evolui sem revisão humana de conteúdo, mas uma instalação não ganha autorização
operacional que não recebeu.
