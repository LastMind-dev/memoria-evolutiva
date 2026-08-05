<?php
/**
 * autoteste.php — os validadores realmente pegam o que prometem?
 *
 * Uso:  php scripts/autoteste.php
 * Saída: 0 se todos os testes passam, 1 se algum falha.
 *
 * POR QUE ISTO EXISTE
 * Verificador que não reprova nada é indistinguível de verificador quebrado — os dois
 * imprimem "tudo certo". E verificador quebra em silêncio: basta um regex que deixou de
 * casar, uma pasta renomeada, um caminho com separador diferente.
 *
 * Num caso real, um contador passou meses devolvendo 73 em vez de 71 porque comparava
 * caminho com `/` numa máquina que devolvia `\`. O script terminava com sucesso. Só foi
 * percebido porque o número certo estava escrito num documento.
 *
 * Este script quebra o projeto DE PROPÓSITO, uma coisa por vez, e confere que o
 * validador certo reclama. É o teste do alarme de incêndio: você aperta o botão.
 *
 * COMO FUNCIONA — e por que é seguro
 * Nada é feito no seu projeto. Tudo acontece numa CÓPIA em pasta temporária, que é
 * apagada no fim. Se o script for interrompido, a cópia fica lá e não afeta nada.
 *
 * Rode depois de:
 *   - instalar o padrão      (confirma que a instalação ficou funcional)
 *   - mexer no padrao.json   (contador novo pega mesmo o que você quer?)
 *   - atualizar o kit
 */

require_once __DIR__ . '/lib-padrao.php';

$origem = raiz();
$tmp    = sys_get_temp_dir() . '/autoteste-padrao-' . getmypid();

/** Cópia recursiva, pulando o que não importa e o que é pesado. */
function copiar(string $de, string $para): void
{
    @mkdir($para, 0775, true);
    foreach (scandir($de) ?: [] as $item) {
        if ($item === '.' || $item === '..' || $item === '.git'
            || $item === 'node_modules' || $item === 'vendor') {
            continue;
        }
        $o = $de . '/' . $item;
        $d = $para . '/' . $item;
        is_dir($o) ? copiar($o, $d) : @copy($o, $d);
    }
}

function apagar(string $caminho): void
{
    if (!is_dir($caminho)) {
        @unlink($caminho);
        return;
    }
    foreach (scandir($caminho) ?: [] as $i) {
        if ($i !== '.' && $i !== '..') {
            apagar($caminho . '/' . $i);
        }
    }
    @rmdir($caminho);
}

/**
 * Escreve um arquivo criando o diretório se preciso.
 *
 * Existe por causa de um bug deste próprio script: ele escrevia direto em
 * `docs/arquitetura/`, que no projeto de origem existia mas num CLONE não — git não
 * versiona diretório vazio. Quatro testes falhavam no CI e passavam na máquina de quem
 * escreveu, com aviso do PHP no meio da saída.
 *
 * É a mesma armadilha que o gerador já tinha caído. Vale para qualquer coisa que
 * escreva em pasta do repositório: **nunca presuma que o diretório existe do outro lado.**
 */
function escrever(string $arquivo, string $conteudo): void
{
    @mkdir(dirname($arquivo), 0775, true);
    file_put_contents($arquivo, $conteudo);
}

/** Frontmatter mínimo e válido, para os testes de cadeia montarem pai e filho. */
function cabecalhoDeTeste(string $id, string $tipo, string $status, array $pais): string
{
    $fm  = "---\nid: {$id}\ntipo: {$tipo}\nprojeto: " . config()['projeto']
         . "\ntitulo: documento de teste do autoteste\nstatus: {$status}\n";
    $fm .= "verificado_em: 2026-01-01\nverificado_commit: 0000000\n";
    if ($pais) {
        $fm .= "deriva_de:\n";
        foreach ($pais as $p) {
            $fm .= "  - {$p}\n";
        }
    }
    return $fm . "---\n\n# documento de teste\n";
}

/** Roda um validador na cópia e devolve [código de saída, saída]. */
function rodar(string $tmp, string $script): array
{
    /*
     * Os scripts rodam DO PACOTE, com o diretório corrente na cópia. Antes o comando
     * era `php $tmp/scripts/<script>` — funcionava quando o kit era copiado para o
     * projeto, e quebraria via Composer, onde a cópia do projeto não tem scripts/
     * (eles moram no vendor, que a cópia pula de propósito).
     */
    $saida = [];
    $rc = 0;
    exec('cd ' . escapeshellarg($tmp) . ' && php ' . escapeshellarg(__DIR__ . '/' . $script) . ' 2>&1', $saida, $rc);
    return [$rc, implode("\n", $saida)];
}

// ══════════════════════════════════════════════════════════════ os testes
/*
 * Cada teste: um nome, uma função que estraga a cópia, o validador que DEVE reclamar,
 * e um trecho que precisa aparecer na saída.
 *
 * `esperado` = 1 significa "tem que reprovar". `esperado` = 0 significa "NÃO pode
 * reprovar" — esses são tão importantes quanto os outros, porque validador que reprova
 * demais é abandonado tão rápido quanto validador que não reprova nada.
 */
$testes = [
    [
        'nome'     => 'âncora apontando para arquivo inexistente',
        'quebra'   => fn (string $t) => escrever($t . '/docs/arquitetura/_teste.md',
            "---\nid: TESTE-ANCORA\ntipo: hld\nprojeto: " . config()['projeto']
            . "\ntitulo: t\nstatus: rascunho\nancoras:\n  - caminho/que/nao/existe.php\n---\n# t\n"),
        'script'   => 'validar-docs.php',
        'esperado' => 1,
        'contem'   => 'âncora quebrada',
    ],
    [
        'nome'     => 'tipo fora do vocabulário',
        'quebra'   => fn (string $t) => escrever($t . '/docs/arquitetura/_teste.md',
            "---\nid: TESTE-VOCAB\ntipo: inventado\nprojeto: " . config()['projeto']
            . "\ntitulo: t\nstatus: rascunho\n---\n# t\n"),
        'script'   => 'validar-docs.php',
        'esperado' => 1,
        'contem'   => 'fora do vocabulário',
    ],
    [
        'nome'     => 'nome de projeto divergente do padrao.json',
        'quebra'   => fn (string $t) => escrever($t . '/docs/arquitetura/_teste.md',
            "---\nid: TESTE-PROJ\ntipo: hld\nprojeto: outro-repositorio\n"
            . "titulo: t\nstatus: rascunho\n---\n# t\n"),
        'script'   => 'validar-docs.php',
        'esperado' => 1,
        'contem'   => 'não bate com o',
    ],
    [
        'nome'     => 'id duplicado',
        'quebra'   => function (string $t) {
            $fm = "---\nid: TESTE-DUP\ntipo: hld\nprojeto: " . config()['projeto']
                . "\ntitulo: t\nstatus: rascunho\n---\n# t\n";
            escrever($t . '/docs/arquitetura/_a.md', $fm);
            escrever($t . '/docs/arquitetura/_b.md', $fm);
        },
        'script'   => 'validar-docs.php',
        'esperado' => 1,
        'contem'   => 'duplicado',
    ],
    [
        'nome'     => 'arquivo derivado editado à mão',
        'quebra'   => function (string $t) {
            $dir = $t . '/' . trim(config()['gerado']['diretorio'], '/');
            foreach (glob($dir . '/*.md') ?: [] as $g) {
                file_put_contents($g, file_get_contents($g) . "\nlinha intrusa\n");
                return;
            }
        },
        'script'   => 'validar-docs.php',
        'esperado' => 1,
        'contem'   => 'editado à mão',
    ],
    [
        'nome'     => 'ponteiro da raiz virou fonte paralela',
        'quebra'   => function (string $t) {
            $ps = config()['ponteiros']['arquivos'] ?? [];
            file_put_contents($t . '/' . $ps[0],
                file_get_contents($t . '/' . $ps[0]) . str_repeat("linha extra\n", 60));
        },
        'script'   => 'validar-docs.php',
        'esperado' => 1,
        'contem'   => 'fonte paralela',
        /*
         * Nem todo teste se aplica a todo projeto. `aplica` é conferido ANTES de rodar.
         *
         * A primeira versão deste arquivo tentava detectar isso pelo retorno da função
         * de quebra — que era null sempre, porque `file_put_contents` no fim do corpo
         * sem `return` devolve null. Resultado: o teste dos ponteiros era pulado em
         * TODO projeto, e o autoteste imprimia sucesso sem nunca ter testado aquilo.
         *
         * Um teste que se pula sozinho em silêncio é pior que um teste ausente.
         */
        'aplica'   => fn (): bool => !empty(config()['ponteiros']['arquivos']),
    ],
    /*
     * ─── cadeia ────────────────────────────────────────────────────────────────
     * Estes testes montam pai e filho do zero, em vez de mexer no que o projeto já tem.
     * Assim funcionam em projeto que ainda não escreveu nenhum PRD — que é o estado de
     * todo projeto no dia da instalação, e justamente quando o autoteste mais precisa
     * funcionar.
     */
    [
        'nome'     => 'deriva_de apontando para documento inexistente',
        'quebra'   => fn (string $t) => escrever($t . '/docs/funcional/_teste.md',
            cabecalhoDeTeste('FDD-TESTE', 'fdd', 'rascunho', ['PRD-QUE-NAO-EXISTE'])),
        'script'   => 'validar-docs.php',
        'esperado' => 1,
        'contem'   => 'não existe documento com esse id',
        'aplica'   => fn (): bool => !empty(config()['cadeia']['niveis']),
    ],
    [
        'nome'     => 'cadeia invertida — requisito derivando de detalhe',
        'quebra'   => function (string $t) {
            escrever($t . '/docs/arquitetura/_pai.md',
                cabecalhoDeTeste('LLD-TESTE', 'lld', 'rascunho', []));
            escrever($t . '/docs/produto/_filho.md',
                cabecalhoDeTeste('PRD-TESTE', 'prd', 'rascunho', ['LLD-TESTE']));
        },
        'script'   => 'validar-docs.php',
        'esperado' => 1,
        'contem'   => 'cadeia invertida',
        'aplica'   => fn (): bool => count(config()['cadeia']['niveis'] ?? []) > 1,
    ],
    [
        'nome'     => 'documento vivo pendurado em pai superado',
        'quebra'   => function (string $t) {
            escrever($t . '/docs/produto/_pai.md',
                cabecalhoDeTeste('PRD-TESTE', 'prd', 'superado', []));
            escrever($t . '/docs/funcional/_filho.md',
                cabecalhoDeTeste('FDD-TESTE', 'fdd', 'verificado', ['PRD-TESTE']));
        },
        'script'   => 'validar-docs.php',
        'esperado' => 1,
        'contem'   => 'superado',
        'aplica'   => fn (): bool => count(config()['cadeia']['niveis'] ?? []) > 1,
    ],
    [
        'nome'     => 'cadeia circular',
        'quebra'   => function (string $t) {
            escrever($t . '/docs/funcional/_a.md',
                cabecalhoDeTeste('FDD-TESTE', 'fdd', 'rascunho', ['ADR-TESTE']));
            escrever($t . '/docs/decisoes/_b.md',
                cabecalhoDeTeste('ADR-TESTE', 'adr', 'rascunho', ['HLD-TESTE']));
            escrever($t . '/docs/arquitetura/_c.md',
                cabecalhoDeTeste('HLD-TESTE', 'hld', 'rascunho', ['FDD-TESTE']));
        },
        'script'   => 'validar-docs.php',
        'esperado' => 1,
        'contem'   => 'cadeia circular',
        'aplica'   => fn (): bool => count(config()['cadeia']['niveis'] ?? []) > 1,
    ],
    [
        'nome'     => 'ciclo não trava o gerador',
        /*
         * Este teste existe porque o laço infinito aconteceu de verdade: o gerador
         * desenhava a árvore recursivamente, encontrou um ciclo, e o processo foi morto
         * pelo sistema depois de consumir a memória da máquina. Sem mensagem, sem pista.
         *
         * Travamento não devolve código de saída útil — então o que se mede aqui é que o
         * processo TERMINA.
         */
        'quebra'   => function (string $t) {
            escrever($t . '/docs/funcional/_a.md',
                cabecalhoDeTeste('FDD-TESTE', 'fdd', 'rascunho', ['ADR-TESTE']));
            escrever($t . '/docs/decisoes/_b.md',
                cabecalhoDeTeste('ADR-TESTE', 'adr', 'rascunho', ['HLD-TESTE']));
            escrever($t . '/docs/arquitetura/_c.md',
                cabecalhoDeTeste('HLD-TESTE', 'hld', 'rascunho', ['FDD-TESTE']));
        },
        'script'   => 'gerar-docs.php',
        'esperado' => 0,
        'contem'   => null,
        'aplica'   => fn (): bool => count(config()['cadeia']['niveis'] ?? []) > 1,
    ],
    [
        'nome'     => 'cadeia bem formada NÃO reprova',
        'quebra'   => function (string $t) {
            escrever($t . '/docs/produto/_pai.md',
                cabecalhoDeTeste('PRD-TESTE', 'prd', 'verificado', []));
            escrever($t . '/docs/funcional/_filho.md',
                cabecalhoDeTeste('FDD-TESTE', 'fdd', 'verificado', ['PRD-TESTE']));
            /*
             * O mapa da cadeia é derivado: acrescentar documento o desatualiza, e o
             * validador reprovaria por isso — não pela cadeia. Regerar antes é o que
             * mantém este teste medindo o que ele diz que mede.
             */
            @exec('cd ' . escapeshellarg($t) . ' && php ' . escapeshellarg(__DIR__ . '/gerar-docs.php') . ' 2>&1');
        },
        'script'   => 'validar-docs.php',
        'esperado' => 0,
        'contem'   => null,
        'aplica'   => fn (): bool => count(config()['cadeia']['niveis'] ?? []) > 1,
    ],
    [
        'nome'     => 'documento novo sem frontmatter aumenta a dívida',
        'quebra'   => fn (string $t) => escrever(
            $t . '/' . trim(config()['acervos']['canonico'], '/') . '/_teste_legado.md',
            "# sem frontmatter\n"),
        'script'   => 'validar-catraca.php',
        'esperado' => 1,
        'contem'   => 'dívida aumentou',
    ],
    [
        'nome'     => 'documento sem frontmatter NÃO é erro de estrutura',
        'quebra'   => fn (string $t) => escrever(
            $t . '/' . trim(config()['acervos']['canonico'], '/') . '/_teste_legado.md',
            "# sem frontmatter\n"),
        'script'   => 'validar-docs.php',
        'esperado' => 0,
        'contem'   => null,
    ],
    [
        'nome'     => 'projeto intacto passa nas três verificações',
        'quebra'   => fn (string $t) => null,
        'script'   => null, // roda as três
        'esperado' => 0,
        'contem'   => null,
    ],
];

// ══════════════════════════════════════════════════════════════ execução
$c = config();
titulo("Autoteste do padrão — {$c['projeto']}");
echo "  cópia de trabalho: {$tmp}\n";
echo "  nada é alterado no seu projeto\n\n";

$passou = $falhou = 0;
$relatos = [];

$pulados = 0;

foreach ($testes as $t) {
    if (isset($t['aplica']) && !($t['aplica'])()) {
        $pulados++;
        $relatos[] = ['·', $t['nome'], 'não se aplica a este projeto (nada configurado para testar)'];
        continue;
    }

    apagar($tmp);
    copiar($origem, $tmp);
    ($t['quebra'])($tmp);

    $scripts = $t['script'] === null
        ? ['validar-docs.php', 'validar-catraca.php', 'validar-indice.php']
        : [$t['script']];

    $rcFinal = 0;
    $saidaFinal = '';
    foreach ($scripts as $s) {
        [$rc, $saida] = rodar($tmp, $s);
        $saidaFinal .= $saida . "\n";
        if ($rc !== 0) {
            $rcFinal = $rc;
        }
    }

    $okCodigo = ($t['esperado'] === 1) ? ($rcFinal !== 0) : ($rcFinal === 0);
    $okTexto  = $t['contem'] === null || str_contains($saidaFinal, $t['contem']);

    if ($okCodigo && $okTexto) {
        $passou++;
        $relatos[] = ['✔', $t['nome'], ''];
    } else {
        $falhou++;
        $motivo = !$okCodigo
            ? ($t['esperado'] === 1 ? 'deveria reprovar e não reprovou' : "reprovou e não deveria (saída {$rcFinal})")
            : "reprovou, mas a mensagem não menciona `{$t['contem']}`";
        $relatos[] = ['✘', $t['nome'], $motivo];
    }
}

apagar($tmp);

foreach ($relatos as [$sinal, $nome, $obs]) {
    printf("  %s  %s%s\n", $sinal, $nome, $obs !== '' ? "\n        → {$obs}" : '');
}

echo "\n" . str_repeat('─', 60) . "\n";
printf("%d passaram · %d falharam%s\n", $passou, $falhou,
    $pulados > 0 ? " · {$pulados} não se aplicam" : '');

if ($falhou > 0) {
    echo "\nUm validador que não reprova o que deveria é pior que nenhum: dá confiança\n";
    echo "falsa. Conserte antes de confiar no build verde.\n";
    exit(1);
}

echo "\nOs validadores pegam o que prometem.\n";
exit(0);
