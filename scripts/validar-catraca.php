<?php
/**
 * validar-catraca.php — a dívida existente fica congelada e visível.
 *
 * Uso:
 *   php scripts/validar-catraca.php               verifica contra a linha de base
 *   vendor/bin/memoria catraca --medir       grava a contagem atual como base
 *
 * POR QUE CATRACA E NÃO FALHA DURA
 * Quando a regra nasce depois do código, o passivo já existe. Reprovar tudo trava o
 * time sem consertar nada — e build que nasce vermelho ninguém olha.
 *
 * A catraca mede e falha SÓ SE PIORAR. O passivo fica visível e imóvel; código novo
 * já nasce dentro da regra. Quando um número chega a zero, promova aquela regra a
 * falha dura de verdade.
 *
 * TIPOS DE CONTADOR (declarados em padrao.json):
 *   regex                     conta ocorrências de um padrão em arquivos
 *   arquivo_sem_padrao        conta arquivos que NÃO contêm um padrão exigido
 *   markdown_sem_frontmatter  conta documentos sem bloco de metadados
 *
 * Não sobe framework, não toca banco, não faz rede.
 */

require_once __DIR__ . '/lib-padrao.php';

$c       = config();
$medir   = in_array('--medir', $argv, true);
$base    = raiz() . '/' . trim($c['catraca']['linha_de_base'] ?? 'docs/baseline.json', '/');
$def     = $c['catraca']['contadores'] ?? [];

if (!$def) {
    echo "Nenhum contador declarado em `padrao.json` → `catraca.contadores`.\n";
    echo "A catraca não tem o que medir. Isso é válido — mas veja se não deveria ter.\n";
    exit(0);
}

$atual = $detalhe = $rotulos = [];

foreach ($def as $d) {
    $chave  = $d['chave'];
    $rotulos[$chave] = $d['rotulo'] ?? $chave;
    $onde   = raiz() . '/' . trim($d['onde'] ?? '', '/');
    $excl   = $d['excluir'] ?? [];
    $total  = 0;
    $ondeAchou = [];

    switch ($d['tipo'] ?? 'regex') {

        case 'regex':
            foreach (arquivosPorExtensao($onde, $d['extensao'] ?? 'php') as $f) {
                if (contemAlgum($f, $excl)) {
                    continue;
                }
                $n = preg_match_all($d['padrao'], (string) file_get_contents($f));
                if ($n > 0) {
                    $total += $n;
                    $ondeAchou[relativo($f)] = $n;
                }
            }
            break;

        case 'arquivo_sem_padrao':
            foreach (arquivosPorExtensao($onde, $d['extensao'] ?? 'php') as $f) {
                if (contemAlgum($f, $excl)) {
                    continue;
                }
                if (!preg_match($d['exige'], (string) file_get_contents($f))) {
                    $total++;
                    $ondeAchou[relativo($f)] = 1;
                }
            }
            break;

        case 'markdown_sem_frontmatter':
            foreach (markdowns($onde) as $f) {
                $rel = relativo($f);
                if (contemAlgum($rel, $excl) || comecaCom($rel, $c['externos']['pastas'] ?? [])) {
                    continue;
                }
                if (!str_starts_with((string) file_get_contents($f), "---\n")) {
                    $total++;
                    $ondeAchou[$rel] = 1;
                }
            }
            break;

        default:
            fwrite(STDERR, "Contador `{$chave}`: tipo `{$d['tipo']}` desconhecido.\n");
            exit(2);
    }

    arsort($ondeAchou);
    $atual[$chave]   = $total;
    $detalhe[$chave] = $ondeAchou;
}

// ---------------------------------------------------------------- gravar base
if ($medir) {
    @mkdir(dirname($base), 0775, true);
    file_put_contents($base, json_encode([
        'medido_em' => date('Y-m-d'),
        'commit'    => commitAtual(),
        'nota'      => 'Contagem congelada da dívida existente. A verificação falha se algum '
                     . 'número aumentar. Quando um chegar a zero, promova a regra a falha dura.',
        'contagens' => $atual,
    ], JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . "\n");

    titulo('Linha de base gravada');
    foreach ($atual as $k => $v) {
        printf("  %-52s %d\n", $rotulos[$k], $v);
    }
    echo "\nA partir de agora, qualquer aumento quebra o build.\n";
    exit(0);
}

// ------------------------------------------------------------------ verificar
if (!is_file($base)) {
    echo "Sem linha de base. Meça uma vez:\n\n  vendor/bin/memoria catraca --medir\n";
    exit(1);
}

$json    = json_decode((string) file_get_contents($base), true);
$ref     = $json['contagens'] ?? [];
$quando  = $json['medido_em'] ?? '?';
$piorou  = $melhorou = [];

foreach ($atual as $k => $v) {
    $r = $ref[$k] ?? 0;
    if ($v > $r) {
        $piorou[] = [$k, $r, $v];
    } elseif ($v < $r) {
        $melhorou[] = [$k, $r, $v];
    }
}

titulo("Catraca — linha de base de {$quando}");
foreach ($atual as $k => $v) {
    $r = $ref[$k] ?? 0;
    $sinal = $v > $r ? '↑' : ($v < $r ? '↓' : '=');
    printf("  %s  %-52s %d (base %d)\n", $sinal, $rotulos[$k], $v, $r);
}

if ($melhorou) {
    echo "\nMelhorou — trave o ganho:\n";
    foreach ($melhorou as [$k, $r, $v]) {
        echo "  ↓ {$rotulos[$k]}: {$r} → {$v}\n";
    }
    echo "  vendor/bin/memoria catraca --medir\n";
}

if ($piorou) {
    echo "\nERRO — a dívida aumentou:\n";
    foreach ($piorou as [$k, $r, $v]) {
        echo "\n  x {$rotulos[$k]}: {$r} → {$v}\n";
        foreach (array_slice(array_keys($detalhe[$k]), 0, 8) as $arquivo) {
            echo "      {$arquivo}\n";
        }
    }
    echo "\nO passivo antigo fica congelado, mas não pode crescer.\n";
    echo "Código novo precisa nascer dentro da regra.\n";
    exit(1);
}

echo "\nNada piorou.\n";
exit(0);
