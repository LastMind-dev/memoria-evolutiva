<?php
/**
 * iniciar-estrutura.php — instala o padrão num projeto, novo ou existente.
 *
 * Uso:
 *   php scripts/iniciar-estrutura.php --projeto="meu-app" --codigo=src
 *   php scripts/iniciar-estrutura.php --projeto="meu-app" --codigo=app --indice
 *
 * O que faz:
 *   1. cria a árvore de docs/ que ainda não existe
 *   2. escreve o padrao.json com o que você informou
 *   3. troca `<NOME-DO-PROJETO>` pelo nome real nos modelos que vieram no kit
 *   4. renomeia o modelo de cronologia para o mês corrente
 *
 * O que NÃO faz — de propósito:
 *   - não preenche o PROJETO.md por você. As oito decisões da Parte IV do METODO.md
 *     são suas; um PROJETO.md genérico é pior que nenhum, porque parece pronto.
 *   - não roda gerador, não mede catraca, não commita. Isso fica nos próximos passos,
 *     para você ver cada saída antes de congelar qualquer número.
 *
 * É seguro rodar de novo: não sobrescreve arquivo que já existe, e a troca de
 * placeholder é idempotente (na segunda vez não há mais o que trocar).
 */

/*
 * Usa a lib pelos utilitários de caminho — nada aqui chama config(), porque o
 * padrao.json ainda pode não existir quando este script roda.
 */
require_once __DIR__ . '/lib-padrao.php';

/*
 * A raiz do projeto NÃO é a posição deste script. Instalado via Composer, este
 * arquivo mora em vendor/ — e o projeto é onde você está. raiz() sobe do cwd até
 * achar padrao.json; num projeto virgem não acha e devolve o próprio cwd.
 *
 * Consequência prática: RODE O INSTALADOR NA RAIZ DO PROJETO.
 */
$raiz = raiz();

/* Instalado via Composer, ou rodando avulso (kit copiado/baixado)? Muda só as mensagens. */
$viaComposer = str_contains(pacote(), '/vendor/');
$args = [];
foreach ($argv as $a) {
    if (preg_match('/^--([a-z]+)(?:=(.*))?$/', $a, $m)) {
        $args[$m[1]] = $m[2] ?? true;
    }
}

$projeto = $args['projeto'] ?? null;
$codigo  = $args['codigo'] ?? 'src';
$indice  = isset($args['indice']);

if (!$projeto) {
    echo "Faltou --projeto.\n\n";
    echo "  php scripts/iniciar-estrutura.php --projeto=\"meu-app\" --codigo=src\n\n";
    echo "Opções:\n";
    echo "  --projeto=NOME    obrigatório. Vai no frontmatter de todo documento.\n";
    echo "  --codigo=PASTA    onde o código vive (padrão: src). O gerador varre daí.\n";
    echo "  --indice          o projeto usa índice semântico/RAG.\n";
    exit(2);
}

$criados = $existiam = [];

function garante(string $caminho, string $conteudo, array &$criados, array &$existiam): void
{
    if (is_file($caminho)) {
        $existiam[] = $caminho;
        return;
    }
    @mkdir(dirname($caminho), 0775, true);
    file_put_contents($caminho, $conteudo);
    $criados[] = $caminho;
}

// ---------------------------------------------------- publicar os moldes do pacote
/*
 * O pacote traz em stubs/ tudo o que pertence AO PROJETO: a árvore de docs/ com os
 * arquivos de entrada e os moldes, o padrao.json comentado, os ponteiros de raiz
 * (CLAUDE.md, AGENTS.md, .cursor, .windsurfrules) e o workflow de CI.
 *
 * Publicar = copiar SEM SOBRESCREVER. O que já existe no projeto é decisão de alguém
 * e não se toca — a mesma regra do padrao.json, aplicada a tudo.
 */
function publicar(string $de, string $para, array &$criados, array &$existiam): void
{
    if (!is_dir($de)) {
        return;
    }
    foreach (scandir($de) ?: [] as $item) {
        if ($item === '.' || $item === '..') {
            continue;
        }
        $o = $de . '/' . $item;
        $d = $para . '/' . $item;
        if (is_dir($o)) {
            @mkdir($d, 0775, true);
            publicar($o, $d, $criados, $existiam);
        } elseif (is_file($d)) {
            $existiam[] = $d;
        } else {
            @mkdir(dirname($d), 0775, true);
            copy($o, $d);
            $criados[] = $d;
        }
    }
}

publicar(pacote() . '/stubs', $raiz, $criados, $existiam);

// ------------------------------------------------------------------- árvore
/*
 * GIT NÃO VERSIONA DIRETÓRIO VAZIO — e por isso cada pasta ganha um `.gitkeep`.
 *
 * Sem ele, a árvore que você acabou de criar existe na sua máquina e **desaparece no
 * clone**. Aí a tabela "onde encontrar cada coisa" do `PROJETO.md` aponta para pastas
 * que, para quem clonou, não existem — e a primeira impressão de quem chega é a de um
 * documento que já mente na terceira seção.
 *
 * O `.gitkeep` também é o que diz "este assunto tem lugar, ainda não tem conteúdo",
 * que é informação diferente de "este assunto não existe aqui".
 */
foreach ([
    'docs/cronologia', 'docs/produto', 'docs/funcional', 'docs/arquitetura',
    'docs/decisoes', 'docs/runbooks', 'docs/evidencia', 'docs/politicas',
    'docs/gerado', 'docs/_templates', 'docs/_arquivo',
] as $d) {
    @mkdir($raiz . '/' . $d, 0775, true);
    $guarda = $raiz . '/' . $d . '/.gitkeep';
    if (!is_file($guarda)) {
        file_put_contents($guarda,
            "Marcador para o git preservar esta pasta enquanto ela estiver vazia.\n"
          . "Pode apagar quando houver conteúdo aqui.\n");
    }
}

// ------------------------------------------------------------- padrao.json
$config = [
    'projeto'  => $projeto,
    'acervos'  => [
        'canonico'   => 'docs',
        'exploracao' => null,
        'indice'     => $indice ? 'externo' : null,
        'ignorar'    => ['docs/_templates/', 'docs/_arquivo/'],
    ],
    'vocabulario' => [
        'tipo' => ['entrada', 'estado', 'cronologia', 'prd', 'fdd', 'hld', 'lld',
                   'adr', 'runbook', 'politica', 'evidencia', 'gerado'],
        'status' => ['rascunho', 'verificado', 'superado'],
        'obrigatorios' => ['id', 'tipo', 'projeto', 'titulo', 'status'],
    ],
    'cadeia' => [
        'niveis'        => ['prd' => 0, 'fdd' => 1, 'hld' => 2, 'lld' => 3],
        'livres'        => ['adr'],
        'exige_origem'  => ['fdd', 'hld', 'lld'],
    ],
    'externos' => ['pastas' => []],
    /*
     * Só entram na lista os ponteiros que EXISTEM. Declarar um arquivo ausente vira
     * aviso a cada execução, e aviso permanente é ruído que treina todo mundo a não
     * ler a saída.
     */
    'ponteiros' => [
        'limite_de_linhas' => 40,
        'arquivos' => array_values(array_filter(
            ['CLAUDE.md', 'AGENTS.md', '.cursor/rules/projeto.mdc', '.windsurfrules'],
            fn (string $p): bool => is_file($raiz . '/' . $p)
        )),
    ],
    'gerado'   => [
        'diretorio'  => 'docs/gerado',
        'raiz'       => $codigo,
        'extensoes'  => ['php'],
        'extratores' => ['mapa-diretorios', 'cadeia-documentos'],
    ],
    'catraca'  => [
        'linha_de_base' => 'docs/politicas/baseline.json',
        'contadores'    => [[
            'chave'  => 'docs_sem_frontmatter',
            'rotulo' => 'estrutura · documento sem frontmatter',
            'tipo'   => 'markdown_sem_frontmatter',
            'onde'   => 'docs',
            'excluir'=> ['docs/_arquivo/', 'docs/_templates/'],
        ]],
    ],
    'memoria'  => [
        'ativo'    => $indice,
        'marcador' => 'docs/.indexado.json',
        'nucleo'   => ['docs/PROJETO.md', 'docs/ESTADO.md', 'docs/ABERTO.md',
                       'docs/GLOSSARIO.md', 'docs/cronologia/', 'docs/produto/',
                       'docs/funcional/', 'docs/arquitetura/', 'docs/decisoes/',
                       'docs/politicas/', 'docs/runbooks/', 'docs/evidencia/',
                       'docs/gerado/'],
        'ignorar'  => ['docs/_arquivo/', 'docs/_templates/'],
    ],
];

/*
 * O KIT JÁ VEM COM UM padrao.json — E ISSO QUASE VIROU O PIOR BUG DA FAMÍLIA.
 *
 * A instalação manda copiar o kit inteiro para a raiz. Quando este script chegava
 * aqui, o arquivo já existia, e a regra "não sobrescrevo o que existe" o preservava
 * inteiro — com `"projeto": "meu-projeto"` dentro. O instalador imprimia sucesso, o
 * build ficava verde, e TODO documento gerado saía carimbado com o nome errado.
 *
 * Configuração mentindo com carimbo de verificada, dentro da ferramenta que existe
 * para impedir exatamente isso.
 *
 * A regra correta não é "nunca sobrescreva": é "nunca sobrescreva DECISÃO DE ALGUÉM".
 * Placeholder não é decisão de ninguém. Então: se o valor ainda é o do modelo, este
 * script preenche e diz que preencheu. Se já foi mudado, não encosta.
 */
$arqConfig  = $raiz . '/padrao.json';
$ajustados  = [];

if (!is_file($arqConfig)) {
    garante($arqConfig,
        json_encode($config, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . "\n",
        $criados, $existiam);
} else {
    $atual = json_decode((string) file_get_contents($arqConfig), true);

    if (!is_array($atual)) {
        fwrite(STDERR, "`padrao.json` existe mas não é JSON válido: " . json_last_error_msg() . "\n");
        fwrite(STDERR, "Conserte ou apague o arquivo e rode de novo.\n");
        exit(2);
    }

    $placeholders = ['', 'meu-projeto', '<NOME-DO-PROJETO>', 'nome-do-projeto'];

    if (in_array((string) ($atual['projeto'] ?? ''), $placeholders, true)) {
        $atual['projeto'] = $projeto;
        $ajustados[] = "projeto → {$projeto}";
    } elseif ($atual['projeto'] !== $projeto) {
        $ajustados[] = "projeto MANTIDO como `{$atual['projeto']}` (já estava preenchido; "
                     . "você pediu `{$projeto}` — se quis mesmo trocar, edite à mão)";
    }

    if (in_array((string) ($atual['gerado']['raiz'] ?? ''), ['', 'src'], true) && $codigo !== 'src') {
        $atual['gerado']['raiz'] = $codigo;
        $ajustados[] = "gerado.raiz → {$codigo}";
    }

    if ($indice && empty($atual['memoria']['ativo'])) {
        $atual['memoria']['ativo'] = true;
        $ajustados[] = 'memoria.ativo → true';
    }

    if (!isset($atual['ponteiros'])) {
        $atual['ponteiros'] = $config['ponteiros'];
        $ajustados[] = 'ponteiros → ' . implode(', ', $config['ponteiros']['arquivos']);
    } else {
        $atual['ponteiros']['arquivos'] = array_values(array_filter(
            $atual['ponteiros']['arquivos'] ?? [],
            fn (string $p): bool => is_file($raiz . '/' . $p)
        ));
    }

    if ($ajustados) {
        file_put_contents($arqConfig,
            json_encode($atual, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . "\n");
    } else {
        $existiam[] = $arqConfig;
    }
}

// ---------------------------------------------- modelo de cronologia → mês real
/*
 * O kit traz `docs/cronologia/AAAA-MM.md` como modelo. Um arquivo com nome de
 * placeholder no acervo canônico é exatamente o tipo de coisa que sobrevive por anos
 * e confunde quem chega — então ele vira o mês corrente na instalação, ou some.
 */
$mes      = date('Y-m');
$modeloCr = $raiz . '/docs/cronologia/AAAA-MM.md';
$mesCr    = $raiz . "/docs/cronologia/{$mes}.md";

if (is_file($modeloCr) && !is_file($mesCr)) {
    $texto = (string) file_get_contents($modeloCr);
    $texto = str_replace(['AAAA-MM', '<mês> de <ano>'], [$mes, $mes], $texto);
    file_put_contents($mesCr, $texto);
    @unlink($modeloCr);
    $criados[] = $mesCr;
}

if (!is_file($mesCr)) {
    garante($mesCr,
        "---\nid: CRONOLOGIA-{$mes}\ntipo: cronologia\nprojeto: {$projeto}\n"
      . "titulo: Cronologia — {$mes}\nstatus: rascunho\n---\n\n"
      . "# Cronologia — {$mes}\n\n"
      . "> **Append-only.** Entradas antigas não são editadas — correção entra como entrada\n"
      . "> nova referenciando a anterior. Mais recente no topo.\n\n---\n\n",
        $criados, $existiam);
}

// ------------------------------------- placeholder → nome real nos modelos do kit
/*
 * IDEMPOTENTE de propósito. Rodar de novo não estraga nada: na segunda vez não há
 * mais `<NOME-DO-PROJETO>` para trocar. Isso importa porque instalar o padrão num
 * projeto existente costuma ser feito em duas ou três tentativas.
 */
$trocados = [];
foreach (markdowns($raiz . '/docs') as $md) {
    $texto = (string) file_get_contents($md);
    if (!str_contains($texto, '<NOME-DO-PROJETO>')) {
        continue;
    }
    file_put_contents($md, str_replace('<NOME-DO-PROJETO>', $projeto, $texto));
    $trocados[] = str_replace($raiz . '/', '', str_replace('\\', '/', $md));
}

$faltando = [];
foreach (['PROJETO', 'ESTADO', 'ABERTO', 'GLOSSARIO'] as $entrada) {
    if (!is_file($raiz . "/docs/{$entrada}.md")) {
        $faltando[] = "docs/{$entrada}.md";
    }
}

// ------------------------------------------------------------------- relatório
echo "\nEstrutura do padrão — {$projeto}\n";
echo str_repeat('─', 60) . "\n";

if ($criados) {
    echo "\nCriados:\n";
    foreach ($criados as $c) {
        echo '  + ' . str_replace($raiz . '/', '', $c) . "\n";
    }
}
if ($existiam) {
    echo "\nJá existiam, não toquei:\n";
    foreach ($existiam as $c) {
        echo '  = ' . str_replace($raiz . '/', '', $c) . "\n";
    }
}
if ($ajustados) {
    echo "\nAjustado no padrao.json que já existia:\n";
    foreach ($ajustados as $a) {
        echo "  ~ {$a}\n";
    }
}
if ($trocados) {
    echo "\nNome do projeto preenchido em:\n";
    foreach ($trocados as $t) {
        echo "  ~ {$t}\n";
    }
}
if ($faltando) {
    echo "\nATENÇÃO — faltam arquivos de entrada:\n";
    foreach ($faltando as $f) {
        echo "  ! {$f}\n";
    }
    echo "  Eles vêm no kit, em docs/. Copie o kit inteiro para a raiz do projeto\n";
    echo "  e rode este script de novo — sem eles o padrão não tem porta de entrada.\n";
}

echo "\n" . str_repeat('─', 60) . "\n";
echo "PRÓXIMOS PASSOS, nesta ordem:\n\n";
echo "  1. Preencha, nesta ordem, os arquivos de entrada que já estão em docs/:\n";
echo "       docs/PROJETO.md    ← as OITO DECISÕES. Sem elas nada funciona.\n";
echo "       docs/ESTADO.md     ← onde o projeto está hoje\n";
echo "       docs/ABERTO.md     ← comece vazio; ele enche sozinho\n";
echo "       docs/GLOSSARIO.md  ← os termos que você já explicou duas vezes\n";
echo "     Documento novo? copie o molde de docs/_templates/.\n\n";
$cmd = $viaComposer
    ? fn (string $c): string => "vendor/bin/memoria {$c}"
    : fn (string $c): string => 'php ' . pacote() . "/scripts/" . [
        'gerar' => 'gerar-docs.php', 'catraca --medir' => 'validar-catraca.php --medir',
        'validar' => 'validar-docs.php', 'indice --marcar' => 'validar-indice.php --marcar',
        'autoteste' => 'autoteste.php',
      ][$c];
echo '  2. ' . $cmd('gerar') . "\n";
echo '  3. ' . $cmd('catraca --medir') . str_repeat(' ', max(1, 40 - strlen($cmd('catraca --medir')))) . "← congela a dívida atual\n";
echo '  4. ' . $cmd('validar') . str_repeat(' ', max(1, 40 - strlen($cmd('validar')))) . "← precisa passar\n";
echo '  5. ' . $cmd('autoteste') . str_repeat(' ', max(1, 40 - strlen($cmd('autoteste')))) . "← o alarme de incêndio\n";
if ($indice) {
    echo '  6. indexe o núcleo e rode: ' . $cmd('indice --marcar') . "\n";
}
if (!$viaComposer) {
    echo "\n  NOTA — você está rodando o kit avulso, sem Composer. Os documentos\n";
    echo "  publicados e o workflow de CI assumem `vendor/bin/memoria`; prefira\n";
    echo "  instalar via Composer (composer require --dev) para tudo casar.\n";
}
echo "\n  Por último — e é o critério de aceitação de verdade:\n";
echo "  abra uma sessão nova, num modelo que nunca viu o projeto, e mande:\n";
echo "  \"leia docs/PROJETO.md e me diga onde o projeto está e o que eu não posso fazer\".\n\n";
echo "  Leia a parte que ele errar com mais atenção do que a que ele acertar.\n";
exit(0);
