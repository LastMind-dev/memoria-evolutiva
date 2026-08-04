<?php
/**
 * validar-indice.php — impede o índice semântico de apodrecer em silêncio.
 *
 * Uso:
 *   php scripts/validar-indice.php            o índice está em dia?
 *   vendor/bin/memoria indice --marcar   grava o estado atual como indexado
 *
 * O PROBLEMA
 * O índice é derivado: cada registro aponta para um documento de origem. Quando o
 * documento muda e ninguém reindexa, o índice continua devolvendo o fato antigo com
 * a MESMA CONFIANÇA de um fato correto. Erra em silêncio — o pior modo de errar,
 * porque não há sinal.
 *
 * POR QUE NÃO REINDEXA SOZINHO
 * O índice costuma ser alcançado por ferramenta que roda na máquina de quem trabalha,
 * não no runner do CI. Então este script NÃO reindexa: ele torna visível que precisa,
 * e falha até alguém fazer. Mesma filosofia da catraca — a ferramenta não conserta,
 * mas impede que o problema cresça sem ninguém ver.
 *
 * DOIS NÍVEIS, DE PROPÓSITO
 * NÚCLEO   o que qualquer agente lê para saber onde o projeto está. Falha dura.
 * O RESTO  medido e visível, sem bloquear. Indexar tudo é caro; fazer disso uma
 *          falha deixaria o build vermelho sem consertar nada.
 *
 * Se o projeto não tem índice, ponha `memoria.ativo: false` no padrao.json — o resto
 * do padrão funciona sem.
 */

require_once __DIR__ . '/lib-padrao.php';

$c = config();
$m = $c['memoria'] ?? [];

if (empty($m['ativo'])) {
    echo "Índice semântico desativado em `padrao.json` → `memoria.ativo`.\n";
    echo "Nada a verificar. O resto do padrão funciona sem.\n";
    exit(0);
}

$marcar   = in_array('--marcar', $argv, true);
$marcador = raiz() . '/' . trim($m['marcador'] ?? 'docs/.indexado.json', '/');
$nucleoDef = $m['nucleo'] ?? [];
$ignorar   = $m['ignorar'] ?? [];

/** O documento pertence ao núcleo? */
function ehNucleo(string $rel, array $def): bool
{
    foreach ($def as $n) {
        if ($rel === $n || (str_ends_with($n, '/') && str_starts_with($rel, $n))) {
            return true;
        }
    }
    return false;
}

$nucleo = $resto = [];
foreach (markdowns(acervo()) as $f) {
    $rel = relativo($f);
    if (comecaCom($rel, $ignorar)) {
        continue;
    }
    $h = hashDoConteudo((string) file_get_contents($f));
    if (ehNucleo($rel, $nucleoDef)) {
        $nucleo[$rel] = $h;
    } else {
        $resto[$rel] = $h;
    }
}
ksort($nucleo);
ksort($resto);

// --------------------------------------------------------------------- marcar
if ($marcar) {
    file_put_contents($marcador, json_encode([
        'indexado_em'     => date('Y-m-d'),
        'commit'          => commitAtual(),
        'nota'            => 'Estado do NÚCLEO na última indexação. Rode --marcar DEPOIS de '
                           . 'indexar de verdade, nunca antes: marcar sem indexar transforma '
                           . 'esta verificação em teatro.',
        'fora_do_nucleo'  => count($resto),
        'documentos'      => $nucleo,
    ], JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . "\n");

    printf("Marcador gravado: %d documentos do núcleo em %s.\n", count($nucleo), commitAtual() ?: '(sem git)');
    printf("Fora do núcleo, não indexados: %d.\n", count($resto));
    exit(0);
}

// ------------------------------------------------------------------ verificar
if (!is_file($marcador)) {
    echo "ERRO — não existe `" . relativo($marcador) . "`.\n\n";
    echo "Sem ele não dá para saber se o índice está velho. Indexe os documentos do\n";
    echo "núcleo e rode:\n\n  vendor/bin/memoria indice --marcar\n";
    exit(1);
}

$j       = json_decode((string) file_get_contents($marcador), true);
$ref     = $j['documentos'] ?? [];
$quando  = $j['indexado_em'] ?? '?';
$ondeSha = $j['commit'] ?? '?';

$mudou = $novo = $sumiu = [];
foreach ($nucleo as $rel => $h) {
    if (!array_key_exists($rel, $ref)) {
        $novo[] = $rel;
    } elseif ($ref[$rel] !== $h) {
        $mudou[] = $rel;
    }
}
foreach ($ref as $rel => $_) {
    if (!array_key_exists($rel, $nucleo)) {
        $sumiu[] = $rel;
    }
}

titulo("Índice — última indexação em {$quando}, commit {$ondeSha}");
printf("  núcleo: %d documentos · indexados: %d\n", count($nucleo), count($ref));
printf("  fora do núcleo, não indexados: %d (medido, não bloqueia)\n", count($resto));

if (!$mudou && !$novo && !$sumiu) {
    echo "\nO núcleo está em dia com os documentos.\n";
    if ($resto) {
        echo "\nDívida visível: " . count($resto) . " documentos fora do índice.\n";
        echo "Quando um deles for indexado, acrescente ao `memoria.nucleo` do padrao.json.\n";
    }
    exit(0);
}

if ($mudou) {
    echo "\nMUDARAM desde a indexação (" . count($mudou) . ") — o índice devolve o texto antigo:\n";
    foreach ($mudou as $r) {
        echo "  ~ {$r}\n";
    }
}
if ($novo) {
    echo "\nNUNCA INDEXADOS (" . count($novo) . ") — invisíveis para a busca:\n";
    foreach ($novo as $r) {
        echo "  + {$r}\n";
    }
}
if ($sumiu) {
    echo "\nSUMIRAM (" . count($sumiu) . ") — o índice guarda fato de documento que não existe mais:\n";
    foreach ($sumiu as $r) {
        echo "  - {$r}\n";
    }
}

echo "\nComo resolver:\n";
echo "  1. reindexe estes documentos, com origem e versão em cada registro\n";
echo "  2. vendor/bin/memoria indice --marcar\n\n";
echo "Registro sem proveniência é purgado, não corrigido.\n";
exit(1);
