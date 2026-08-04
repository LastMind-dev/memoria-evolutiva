<?php
/**
 * gerar-skill.php — reconstrói o pacote de skill a partir dos arquivos versionados.
 *
 * Uso:
 *   vendor/bin/memoria skill                    monta em ./skill-memoria-evolutiva/
 *   vendor/bin/memoria skill --saida=/tmp/x     monta em outro lugar
 *   vendor/bin/memoria skill --conferir         só diz se a skill está defasada
 *
 * POR QUE ESTE SCRIPT EXISTE
 *
 * Skill, comando, prompt salvo, regra de editor — cada ferramenta chama de um jeito. Todas
 * têm o mesmo defeito: **o conteúdo mora dentro da ferramenta.** Some quando você troca,
 * não tem diff, não tem revisão, e ninguém percebe quando envelhece.
 *
 * O princípio 1 do método diz que isso é cache, não memória. Aplicado à própria skill: a
 * FONTE do protocolo de sessão é `docs/runbooks/sessao.md`, versionado no repositório. A
 * skill é ARTEFATO DERIVADO — como `docs/gerado/`, só que num formato que a ferramenta lê.
 *
 * Sem este script o laço fica aberto: alguém melhora o runbook, a skill continua ensinando
 * a versão antiga, e passa a existir uma segunda fonte da verdade dentro da peça que
 * deveria impedir exatamente isso.
 *
 * O QUE ELE FAZ, E O QUE NÃO FAZ
 *
 * Ele copia: o kit inteiro para `assets/kit/`, e o runbook de sessão do projeto para
 * `references/`, quando existe. Ele NÃO reescreve a `SKILL.md` — a redação de uma skill é
 * trabalho de escrita, não de template. O que ele faz é CONFERIR se a fonte mudou depois
 * da última geração, e avisar. Aviso, não falha: divergência aqui não quebra o produto,
 * só significa que a skill está velha.
 *
 * ISTO NÃO INSTALA NADA. A saída é uma pasta; instalar é assunto da sua ferramenta.
 */

require_once __DIR__ . '/lib-padrao.php';

$c        = config();
$conferir = in_array('--conferir', $argv, true);
$saida    = raiz() . '/skill-memoria-evolutiva';

foreach ($argv as $a) {
    if (preg_match('/^--saida=(.+)$/', $a, $m)) {
        $saida = barras($m[1]);
    }
}

/** Origem → destino dentro do pacote. Só o que é versionado entra aqui. */
$fontes = [
    'docs/runbooks/sessao.md'   => 'references/sessao-do-projeto.md',
    'docs/runbooks/indexacao.md' => 'references/indexacao-do-projeto.md',
];

$marcador = raiz() . '/docs/.skill-gerada.json';

// ------------------------------------------------------------------- conferir
if ($conferir) {
    if (!is_file($marcador)) {
        echo "Nunca foi gerada. Rode `vendor/bin/memoria skill` quando quiser o pacote.\n";
        exit(0);
    }

    $j    = json_decode((string) file_get_contents($marcador), true);
    $ref  = $j['fontes'] ?? [];
    $vela = [];

    foreach ($fontes as $orig => $_) {
        $abs = raiz() . '/' . $orig;
        if (!is_file($abs)) {
            continue;
        }
        $h = hashDoConteudo((string) file_get_contents($abs));
        if (($ref[$orig] ?? null) !== $h) {
            $vela[] = $orig;
        }
    }

    titulo('Skill derivada — gerada em ' . ($j['gerada_em'] ?? '?'));

    if (!$vela) {
        echo "  Em dia com os arquivos de origem.\n";
        exit(0);
    }

    echo "  Mudaram desde a última geração:\n";
    foreach ($vela as $v) {
        echo "    ~ {$v}\n";
    }
    echo "\n  A skill instalada está ensinando a versão antiga. Rode:\n";
    echo "    vendor/bin/memoria skill\n";
    echo "\n  Aviso, não erro: skill velha não quebra o produto — só faz o agente\n";
    echo "  seguir um procedimento que o projeto já mudou.\n";
    exit(0);
}

// -------------------------------------------------------------------- montar
function copiarArvore(string $de, string $para, array $pular = []): int
{
    if (!is_dir($de)) {
        return 0;
    }
    @mkdir($para, 0775, true);
    $n = 0;
    foreach (scandir($de) ?: [] as $item) {
        if ($item === '.' || $item === '..' || in_array($item, $pular, true)) {
            continue;
        }
        $o = $de . '/' . $item;
        $d = $para . '/' . $item;
        if (is_dir($o)) {
            $n += copiarArvore($o, $d, $pular);
        } elseif (@copy($o, $d)) {
            $n++;
        }
    }
    return $n;
}

@mkdir($saida . '/references', 0775, true);
@mkdir($saida . '/assets', 0775, true);

/*
 * O kit vai inteiro, MENOS o que ele próprio manda não copiar para dentro de um projeto.
 * Aqui é diferente: o pacote da skill é material de referência, então os documentos do
 * método entram — é deles que o agente vai ler o porquê quando precisar.
 */
/*
 * O kit embutido na skill é O PACOTE — scripts, stubs e documentos do método. Nunca o
 * projeto: o projeto entra só pelos runbooks listados em $fontes, que são o que o
 * agente precisa para operar ESTE repositório.
 */
$copiados = copiarArvore(pacote(), $saida . '/assets/kit', [
    '.git', 'node_modules', 'vendor',
]);

$levados = [];
foreach ($fontes as $orig => $dest) {
    $abs = raiz() . '/' . $orig;
    if (!is_file($abs)) {
        continue;
    }
    @mkdir(dirname($saida . '/' . $dest), 0775, true);
    copy($abs, $saida . '/' . $dest);
    $levados[$orig] = hashDoConteudo((string) file_get_contents($abs));
}

file_put_contents($marcador, json_encode([
    'gerada_em' => date('Y-m-d'),
    'commit'    => commitAtual(),
    'nota'      => 'A skill é ARTEFATO DERIVADO. A fonte do protocolo é '
                 . 'docs/runbooks/sessao.md. Editar a skill instalada não muda nada aqui — '
                 . 'edite o runbook e regere.',
    'fontes'    => $levados,
], JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . "\n");

titulo('Pacote da skill montado');
echo '  ' . relativo($saida) . "\n";
echo "  {$copiados} arquivos do kit · " . count($levados) . " runbook(s) do projeto\n";
echo "\n  Falta a SKILL.md: a redação é trabalho de escrita, não de template.\n";
echo "  Se já existe uma, copie-a para dentro e confira se ela ainda bate com o runbook.\n";
echo "\n  A partir de agora, `vendor/bin/memoria skill --conferir` avisa quando o\n";
echo "  runbook mudar e a skill ficar para trás.\n";
exit(0);
