# Segurança da memória — classificação, escopo e redaction

A versão 4.0 aplica a mesma política antes de indexar, recuperar e entregar contexto.
O modelo não escolhe classificação, perfil, produto ou tenant: esses valores são
entradas explícitas e verificadas pelo motor.

## Frontmatter

```yaml
classificacao: publico
audience:
  - atendimento
produtos:
  - faturamento
tenants:
  - cliente-123
```

Valores de `classificacao`:

- `publico`: pode chegar a atendimento/operação, desde que diretório, audiência e
  escopo também permitam;
- `interno`: somente engenharia e automação de código;
- `restrito`: somente engenharia e automação de código;
- `secreto-nao-indexar`: permanece em `docs/`, mas não entra no manifesto nem no
  Hindsight.

Ausência de classificação significa `interno`. Para tornar algo público é obrigatório
declarar `classificacao: publico`. `audience`, `produtos` e `tenants` são listas de IDs
minúsculos. Lista vazia significa documento global naquele eixo; lista preenchida exige
match exato.

## Escopo de atendimento

`atendimento` e `operacao-assistida` exigem `produto` e `tenant` em toda chamada:

```bash
memoria contexto --pergunta="como acompanhar o pedido?" \
  --perfil=atendimento --produto=pedidos --tenant=cliente-123 --json
```

O gateway filtra classificação, diretório permitido, audiência, produto e tenant antes
de pontuar ou entregar fragmentos. Nenhuma chamada herda escopo de chamada anterior.
Documentos globais continuam disponíveis se forem públicos e estiverem no diretório
permitido. Documento ligado a outro produto ou tenant nunca é retornado.

Perguntas de `atendimento` e `operacao-assistida` não são enviadas ao recall do
Hindsight. Esses perfis usam somente o manifesto local já filtrado, evitando colocar
texto de conversa do cliente no caminho do banco de memória do projeto.

O sistema que chama a memória deve obter `produto` e `tenant` da identidade autenticada;
texto da conversa ou argumento escolhido pela LLM não é fonte confiável de identidade.

## Redaction antes do Hindsight

Antes de cada `retain`, o motor substitui deterministicamente:

- chave privada PEM;
- credencial embutida em URL;
- bearer token;
- segredo configurado em campos como `api_key`, `client_secret`, `password` e `senha`;
- e-mail;
- CPF/CNPJ formatado ou sem pontuação.

O Hindsight recebe somente o texto redigido. Metadados guardam algoritmo, quantidade de
ocorrências e SHA-256 do texto redigido, nunca o valor removido. O marcador local guarda
o fingerprint da política e o total agregado. Mudança da política invalida a prova e
obriga nova sincronização.

Redaction é defesa em profundidade, não autorização para documentar credenciais. Segredo
conhecido deve usar `secreto-nao-indexar` ou ficar fora do repositório conforme a política
do projeto.

## Resposta sem cobertura

O envelope v2 inclui `escopo` e `cobertura`. `cobertura: confirmada` significa que ao
menos uma fonte atual e permitida foi entregue. `cobertura: ausente` vem com fontes
vazias e aviso explícito; o agente deve informar ausência de base documental, nunca
completar a resposta por memória da conversa.

`acoes_permitidas` permanece vazio. Esta biblioteca não substitui autenticação,
autorização, transação, idempotência, rate limit, aprovação ou auditoria do sistema dono.
