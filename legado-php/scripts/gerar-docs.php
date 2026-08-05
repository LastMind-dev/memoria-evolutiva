<?php
/**
 * gerar-docs.php — extrai do código o que não deve ser escrito à mão.
 *
 * Uso:  php scripts/gerar-docs.php
 *
 * REGRA DE OURO: a saída precisa ser REPRODUTÍVEL.
 * Rodar duas vezes seguidas tem que produzir bytes idênticos. Se depender da ordem
 * de leitura do sistema de arquivos, de horário ou de caminho absoluto, o diff acusa
 * mudança sem nada ter mudado — e a verificação vira ruído que todo mundo ignora.
 *
 * Por isso: tudo ordenado, nada de timestamp, caminhos sempre relativos.
 *
 * COMO ACRESCENTAR UM EXTRATOR
 * 1. escreva uma função `extrator_<nome>(array $c): array` devolvendo [titulo, corpo]
 * 2. declare o `<nome>` em `padrao.json` → `gerado.extratores`
 *
 * O kit vem com um extrator só — mapa de diretórios — porque é o único universal.
 * Os outros dependem do que seu projeto tem: comandos, rotas, esquema de dados,
 * variáveis de ambiente. Escreva conforme um documento escrito à mão errar sobre o
 * assunto: esse é o sinal de que o assunto deveria ser gerado.
 */

require_once __DIR__ . '/lib-padrao.php';

$c      = config();
$saida  = raiz() . '/' . trim($c['gerado']['diretorio'], '/');
$commit = commitAtual() ?: 'desconhecido';

@mkdir($saida, 0775, true);

/** Cabeçalho padrão de arquivo derivado. */
function cabecalho(string $id, string $titulo, string $projeto, string $commit): string
{
    return "---\n"
         . "id: {$id}\n"
         . "tipo: gerado\n"
         . "projeto: {$projeto}\n"
         . "titulo: {$titulo}\n"
         . "status: verificado\n"
         . "verificado_em: " . date('Y-m-d') . "\n"
         . "verificado_commit: {$commit}\n"
         . "---\n\n"
         . "> ⚠️ **ARQUIVO GERADO AUTOMATICAMENTE.** Não edite à mão — sua alteração será sobrescrita.\n"
         . "> Gerado por `vendor/bin/memoria gerar` em `{$commit}`.\n\n";
}

/**
 * A pasta tem algum arquivo, em qualquer nível?
 *
 * Precisa ser recursivo. Uma pasta que ficou vazia depois de uma troca de branch
 * existe na máquina de quem trabalha e NÃO existe no runner — git não versiona
 * diretório vazio. Sem esta checagem, a saída do gerador diverge entre os dois sem
 * que nada de errado tenha acontecido.
 */
function temAlgumArquivo(string $dir): bool
{
    if (!is_dir($dir)) {
        return false;
    }
    $it = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($dir, FilesystemIterator::SKIP_DOTS));
    foreach ($it as $f) {
        if ($f->isFile()) {
            return true;
        }
    }
    return false;
}

// ═══════════════════════════════════════════════════════════ extratores

/**
 * Mapa de diretórios com contagem de arquivos.
 *
 * É o documento que mais mente quando escrito à mão. Num caso real, o mapa listava
 * duas pastas que não existiam e omitia três que existiam — seis erros em dezesseis
 * linhas, no documento cuja única função era orientar quem não conhece o código.
 */
function extrator_mapaDiretorios(array $c): array
{
    $raizCodigo = raiz() . '/' . trim($c['gerado']['raiz'], '/');
    $exts       = $c['gerado']['extensoes'] ?? ['php'];

    if (!is_dir($raizCodigo)) {
        return ['Mapa de diretórios', "Diretório `{$c['gerado']['raiz']}` não existe.\n"];
    }

    $conta = function (string $dir) use ($exts): int {
        $n = 0;
        foreach ($exts as $e) {
            $n += count(arquivosPorExtensao($dir, $e));
        }
        return $n;
    };

    $dirs = glob($raizCodigo . '/*', GLOB_ONLYDIR) ?: [];
    sort($dirs);

    $linhas = [];
    $totalArquivos = 0;

    /*
     * ARQUIVOS SOLTOS NA RAIZ CONTAM.
     *
     * A primeira versão deste extrator só percorria SUBDIRETÓRIOS. Num projeto pequeno,
     * com todos os arquivos direto em `src/`, ele escrevia "Total: 0 arquivos em 0
     * diretórios" — e passava na verificação, porque a verificação só confere se a saída
     * é reprodutível, não se ela é verdadeira.
     *
     * Foi um documento gerado mentindo com carimbo de verificado. Exatamente o que o
     * método existe para impedir, dentro da peça que deveria impedi-lo.
     */
    $naRaiz = 0;
    foreach ($exts as $e) {
        foreach (glob($raizCodigo . '/*.' . $e) ?: [] as $f) {
            if (is_file($f)) {
                $naRaiz++;
            }
        }
    }
    if ($naRaiz > 0) {
        $totalArquivos += $naRaiz;
        $linhas[] = sprintf(
            '| `%s/` *(raiz)* | %d | — |',
            trim($c['gerado']['raiz'], '/'),
            $naRaiz
        );
    }

    foreach ($dirs as $d) {
        if (!temAlgumArquivo($d)) {
            continue;
        }
        $n = $conta($d);
        $totalArquivos += $n;

        $subs = [];
        $filhos = glob($d . '/*', GLOB_ONLYDIR) ?: [];
        sort($filhos);
        foreach ($filhos as $sub) {
            $cn = $conta($sub);
            if ($cn > 0) {
                $subs[] = '`' . basename($sub) . '` (' . $cn . ')';
            }
        }

        $linhas[] = sprintf(
            '| `%s/%s/` | %d | %s |',
            trim($c['gerado']['raiz'], '/'),
            basename($d),
            $n,
            $subs ? implode(' · ', $subs) : '—'
        );
    }

    $corpo  = "Contagem de arquivos por diretório em `" . trim($c['gerado']['raiz'], '/') . "/`.\n";
    $corpo .= 'Extensões consideradas: `' . implode('`, `', $exts) . "`.\n\n";
    $corpo .= "Diretório sem nenhum arquivo é ignorado — git não versiona pasta vazia,\n";
    $corpo .= "então ela existiria só na máquina de quem trabalha.\n\n";
    $corpo .= "| Diretório | Arquivos | Subdiretórios com conteúdo |\n|---|---:|---|\n";
    $corpo .= ($linhas ? implode("\n", $linhas) : '| — | 0 | — |') . "\n\n";
    $n = count($linhas);
    $corpo .= "**Total: {$totalArquivos} " . ($totalArquivos === 1 ? 'arquivo' : 'arquivos')
            . " em {$n} " . ($n === 1 ? 'diretório' : 'diretórios') . ".**\n";

    return ['Mapa de diretórios', $corpo];
}

/**
 * Mapa da cadeia PRD → FDD → HLD → LLD → ADR, extraído do frontmatter.
 *
 * Este NUNCA deve ser escrito à mão, e a razão é diferente da do mapa de diretórios. Lá o
 * problema é que a informação muda; aqui o problema é que ela está espalhada por dezenas
 * de arquivos. Ninguém mantém à mão uma visão que depende de ler o cabeçalho do acervo
 * inteiro — e visão errada da cadeia é pior que nenhuma, porque é o que alguém consulta
 * para decidir o que precisa revisar.
 *
 * É também o antídoto contra a burocracia: se a cadeia render um mapa que ninguém olha,
 * é sinal de que ela virou papel. O mapa é onde isso fica visível.
 */
function extrator_cadeiaDocumentos(array $c): array
{
    $niveis  = $c['cadeia']['niveis'] ?? [];
    $livres  = $c['cadeia']['livres'] ?? [];
    $acervo  = raiz() . '/' . trim($c['acervos']['canonico'], '/');
    $ignorar = $c['acervos']['ignorar'] ?? [];
    $dirGer  = trim($c['gerado']['diretorio'] ?? 'docs/gerado', '/');

    /*
     * O ADR entra no mapa mesmo sem nível fixo. Ele é parte da cadeia — só não tem altura
     * definida, porque uma decisão pode nascer em qualquer ponto. Deixá-lo de fora
     * produziria um mapa que esconde justamente o documento que explica por que o desenho
     * é aquele.
     */
    $naCadeia = fn (string $t): bool => isset($niveis[$t]) || in_array($t, $livres, true);

    /* Caminho relativo a partir da pasta de derivados, para o link funcionar no GitHub. */
    $subir = str_repeat('../', substr_count($dirGer, '/') + 1);

    $docs = [];
    foreach (markdowns($acervo) as $f) {
        $rel = relativo($f);
        if (comecaCom($rel, $ignorar)) {
            continue;
        }
        $fm = frontmatter((string) file_get_contents($f));
        if ($fm === null || empty($fm['id']) || !$naCadeia($fm['tipo'] ?? '')) {
            continue;
        }
        $docs[$fm['id']] = [
            'tipo'   => $fm['tipo'],
            'titulo' => $fm['titulo'] ?? '(sem título)',
            'status' => $fm['status'] ?? '?',
            'rel'    => $rel,
            'pais'   => array_values(array_filter((array) ($fm['deriva_de'] ?? []), fn ($p) => $p !== '')),
        ];
    }

    if (!$docs) {
        return ['Cadeia de documentos', "Nenhum documento da cadeia (`"
            . implode('`, `', array_merge(array_keys($niveis), $livres)) . "`) foi escrito ainda.\n\n"
            . "Isso é um estado válido — a cadeia serve para o que precisa de rastro entre\n"
            . "requisito e código, e nem todo projeto precisa dos quatro níveis.\n"];
    }

    ksort($docs);

    $filhos = [];
    foreach ($docs as $id => $d) {
        foreach ($d['pais'] as $p) {
            $filhos[$p][] = $id;
        }
    }
    foreach ($filhos as &$lista) {
        sort($lista);
    }
    unset($lista);

    $marca = fn (string $s): string => match ($s) {
        'verificado' => '✅',
        'rascunho'   => '📝',
        'superado'   => '🗑️',
        default      => '❔',
    };

    $corpo  = "Extraído do campo `deriva_de` do frontmatter. **A ordem é do problema para o\n";
    $corpo .= "código:** PRD (por que fazer) → FDD (o que o sistema faz) → HLD (como está\n";
    $corpo .= "organizado) → LLD (como está construído). O ADR atravessa todos.\n\n";
    $corpo .= "Use esta tabela para responder à pergunta que evita documentação podre:\n";
    $corpo .= "**quando este documento mudar, o que mais preciso revisar?** — é a coluna\n";
    $corpo .= "\"quem depende deste\".\n\n";
    $corpo .= "> ⚠️ **Esta coluna só enxerga o que está declarado em `deriva_de`.** Documento\n";
    $corpo .= "> que cita outro apenas em prosa aparece aqui como se ninguém dependesse dele —\n";
    $corpo .= "> e some da revisão exatamente quando mais importa, no dia em que a origem cai.\n\n";
    $corpo .= "| Documento | Tipo | Estado | Depende de | Quem depende deste |\n|---|---|:-:|---|---|\n";

    foreach ($docs as $id => $d) {
        $corpo .= sprintf(
            "| [`%s`](%s) — %s | `%s` | %s | %s | %s |\n",
            $id, $subir . $d['rel'], $d['titulo'], $d['tipo'], $marca($d['status']),
            $d['pais'] ? '`' . implode('`, `', $d['pais']) . '`' : '—',
            isset($filhos[$id]) ? '`' . implode('`, `', $filhos[$id]) . '`' : '—'
        );
    }

    $raizes = array_keys(array_filter($docs, fn ($d) => !$d['pais']));
    if ($raizes) {
        $corpo .= "\n## Árvore\n\n```\n";
        /*
         * O `$vistos` não é otimização: é o que impede o laço infinito.
         *
         * Se dois documentos declararem depender um do outro — direta ou indiretamente —
         * esta recursão nunca termina. Aconteceu: o processo consumiu a memória da máquina
         * e foi morto pelo sistema, sem nenhuma mensagem útil.
         *
         * `validar-docs.php` reprova o ciclo com o caminho completo, que é onde o problema
         * deve ser resolvido. Aqui a árvore só precisa terminar e dizer que cortou.
         */
        $desenhar = function (string $id, string $prefixo, array $vistos) use (&$desenhar, $docs, $filhos, $marca): string {
            if (isset($vistos[$id])) {
                return $prefixo . "↻ {$id} · (ciclo — ver validar-docs.php)\n";
            }
            $vistos[$id] = true;
            $d = $docs[$id];
            $saida = $prefixo . $marca($d['status']) . " {$id} · {$d['titulo']}\n";
            foreach ($filhos[$id] ?? [] as $f) {
                $saida .= $desenhar($f, $prefixo . '    ', $vistos);
            }
            return $saida;
        };
        foreach ($raizes as $r) {
            $corpo .= $desenhar($r, '', []);
        }
        $corpo .= "```\n";
    }

    /*
     * SUPERADO QUE NINGUÉM APONTA É SUSPEITO, NÃO NECESSARIAMENTE ERRADO.
     *
     * Quando uma decisão cai, o normal é que ao menos um documento dependesse dela. Se o
     * mapa mostra "ninguém depende deste", há dois casos: ou a decisão era mesmo isolada,
     * ou — e é o caso comum — os documentos que dependiam dela a citavam só em prosa, e
     * agora estão fora de qualquer revisão.
     *
     * O gerador não decide qual dos dois é. Mas mostra a lista, que é o que faltava no
     * teste em que este método falhou.
     */
    $orfaos = [];
    foreach ($docs as $id => $d) {
        if ($d['status'] === 'superado' && empty($filhos[$id])) {
            $orfaos[] = $id;
        }
    }
    if ($orfaos) {
        $corpo .= "\n## ⚠️ Superados que ninguém declara depender\n\n";
        $corpo .= '`' . implode('`, `', $orfaos) . "`\n\n";
        $corpo .= "Confira se é mesmo isolado. **Se algum documento descrevia o efeito de um\n";
        $corpo .= "destes sem citá-lo em `deriva_de`, ele está agora fora de toda revisão** —\n";
        $corpo .= "afirmando um comportamento que o projeto abandonou, com o build verde.\n\n";
        $corpo .= "Como procurar o que o frontmatter não pega:\n\n";
        $corpo .= "```\ngrep -rn \"" . $orfaos[0] . "\" docs/\n```\n\n";
        $corpo .= "E depois pelo assunto, não pelo id — é assim que estes casos se escondem.\n";
    }

    $porTipo = [];
    foreach ($docs as $d) {
        $porTipo[$d['tipo']] = ($porTipo[$d['tipo']] ?? 0) + 1;
    }
    ksort($porTipo);
    $resumo = [];
    foreach ($porTipo as $t => $n) {
        $resumo[] = "{$n} `{$t}`";
    }

    $corpo .= "\n**Total: " . count($docs) . ' documentos na cadeia — ' . implode(' · ', $resumo) . ".**\n";
    $corpo .= "\nLegenda: ✅ verificado · 📝 rascunho · 🗑️ superado\n";

    return ['Cadeia de documentos', $corpo];
}

// ═══════════════════════════════════════════════════════════ execução

$mapa = [
    'mapa-diretorios'   => ['fn' => 'extrator_mapaDiretorios',   'id' => 'GERADO-MAPA'],
    'cadeia-documentos' => ['fn' => 'extrator_cadeiaDocumentos', 'id' => 'GERADO-CADEIA'],
];

/*
 * EXTRATORES DO PROJETO — a fresta que a migração do primeiro projeto real exigiu.
 *
 * Quando o gerador morava em scripts/ do projeto, acrescentar um extrator era editar o
 * arquivo. Via Composer ele mora no vendor — e vendor não se edita. Sem esta fresta, o
 * primeiro projeto migrado PERDERIA seus quatro extratores próprios (tabelas do banco,
 * comandos artisan, rotas, mapa customizado), e os arquivos gerados ficariam órfãos:
 * passariam na verificação para sempre, envelhecendo em silêncio — a mentira exata que
 * o método existe para impedir.
 *
 * O arquivo declarado em `gerado.extensao_do_projeto` é do PROJETO, versionado nele, e
 * devolve um array no mesmo formato do $mapa acima:
 *
 *     return [
 *         'tabelas' => ['id' => 'GERADO-TABELAS', 'fn' => function (array $c): array {
 *             return ['Tabelas do banco', $corpo];
 *         }],
 *     ];
 *
 * Chave repetida SOBRESCREVE o extrator embutido — é assim que um projeto troca o mapa
 * genérico pelo seu. O nome da chave vira o nome do arquivo: `<chave>.md`.
 */
$extensao = $c['gerado']['extensao_do_projeto'] ?? null;
if ($extensao) {
    $absExt = raiz() . '/' . ltrim($extensao, '/');
    if (!is_file($absExt)) {
        fwrite(STDERR, "`gerado.extensao_do_projeto` aponta para `{$extensao}`, que não existe.\n");
        fwrite(STDERR, "Crie o arquivo ou remova a chave do padrao.json.\n");
        exit(2);
    }
    $extras = require $absExt;
    if (!is_array($extras)) {
        fwrite(STDERR, "`{$extensao}` precisa devolver um array de extratores (return [...];).\n");
        exit(2);
    }
    foreach ($extras as $nome => $def) {
        if (empty($def['id']) || empty($def['fn']) || !is_callable($def['fn'])) {
            fwrite(STDERR, "Extrator `{$nome}` em `{$extensao}`: precisa de `id` e `fn` chamável.\n");
            exit(2);
        }
        $mapa[$nome] = $def;
    }
}

$feitos = [];
foreach ($c['gerado']['extratores'] ?? [] as $nome) {
    if (!isset($mapa[$nome])) {
        fwrite(STDERR, "Extrator `{$nome}` declarado em padrao.json mas não existe neste script.\n");
        fwrite(STDERR, "Escreva a função e registre no array \$mapa, ou remova do padrao.json.\n");
        exit(2);
    }
    [$titulo, $corpo] = call_user_func($mapa[$nome]['fn'], $c);
    $arquivo = $saida . '/' . $nome . '.md';
    file_put_contents(
        $arquivo,
        cabecalho($mapa[$nome]['id'], $titulo, $c['projeto'], $commit) . "# {$titulo}\n\n" . $corpo
    );
    $feitos[] = relativo($arquivo);
}

titulo("Derivados gerados em `{$commit}`");
foreach ($feitos as $f) {
    echo "  {$f}\n";
}
echo "\nNunca edite estes arquivos à mão — `vendor/bin/memoria validar` reprova se você editar.\n";
exit(0);
