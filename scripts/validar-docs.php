<?php
/**
 * validar-docs.php — a documentação canônica não pode mentir sem alguém perceber.
 *
 * Uso:  php scripts/validar-docs.php
 * Saída: 0 se passa, 1 se há erro.
 *
 * FALHA DURA, para todo documento que TEM frontmatter:
 *   1. campos obrigatórios preenchidos
 *   2. `tipo` e `status` dentro do vocabulário
 *   3. `id` não duplicado
 *   4. TODA ÂNCORA APONTA PARA ARQUIVO QUE EXISTE  ← a verificação que mais rende
 *   5. o diretório gerado bate com a saída atual do gerador
 *   6. os ponteiros da raiz continuam ponteiros — não viraram fonte paralela
 *   7. a cadeia PRD → FDD → HLD → LLD está íntegra e não tem filho órfão de pai superado
 *
 * NÃO REPROVA:
 *   - documento legado sem frontmatter nenhum (é dívida, medida pela catraca)
 *   - pastas declaradas em `externos` no padrao.json (outro dono, outro formato)
 *
 * Não sobe framework, não toca banco, não faz rede.
 */

require_once __DIR__ . '/lib-padrao.php';

$c        = config();
$acervo   = acervo();
$externos = $c['externos']['pastas'] ?? [];
/*
 * `_templates/` tem placeholder no lugar de caminho de arquivo — é modelo para copiar,
 * não afirmação sobre o código. Validá-lo quebraria o build no primeiro uso do kit.
 *
 * `_arquivo/` é para documento cujo ASSUNTO deixou de existir: módulo removido,
 * integração desligada. Guardado por histórico, não precisa mais estar correto.
 *
 * CUIDADO COM A CONFUSÃO QUE ISSO CONVIDA: decisão superada NÃO vem para cá. Ela fica
 * onde estava, com `status: superado`. Mover para `_arquivo/` a tira desta verificação —
 * e some justamente a checagem mais valiosa da cadeia, a de filho vivo pendurado em pai
 * morto. Um leitor sem contexto caiu nessa lendo o comentário anterior deste bloco.
 */
$ignorar  = $c['acervos']['ignorar'] ?? ['docs/_templates/', 'docs/_arquivo/'];
$vocab    = $c['vocabulario'];

$erros = $avisos = $legados = $foraDaRegua = [];
$idsVistos = [];
/*
 * Guarda o frontmatter de todo documento válido para a verificação de cadeia, que só
 * pode acontecer depois — ela precisa do conjunto inteiro para resolver `deriva_de`.
 */
$porId = [];

// ------------------------------------------------- 1 a 4: frontmatter e âncoras
$arquivos = markdowns($acervo);

foreach ($arquivos as $f) {
    $rel = relativo($f);

    if (comecaCom($rel, $ignorar)) {
        continue;
    }
    if (comecaCom($rel, $externos)) {
        $foraDaRegua[] = $rel;
        continue;
    }

    $fm = frontmatter((string) file_get_contents($f));

    /*
     * DOCUMENTO SEM FRONTMATTER É DÍVIDA, NÃO ERRO.
     *
     * Em projeto existente, a maioria dos documentos nasceu antes desta estrutura.
     * Reprovar todos deixa o build vermelho desde o primeiro dia — e build que nasce
     * vermelho ninguém olha. O passivo fica congelado pela catraca; documento NOVO
     * sem frontmatter aumenta a conta e quebra.
     */
    if ($fm === null) {
        $legados[] = $rel;
        continue;
    }

    foreach ($vocab['obrigatorios'] as $campo) {
        if (empty($fm[$campo])) {
            $erros[] = "{$rel}: falta o campo obrigatório `{$campo}`";
        }
    }
    /*
     * O NOME DO PROJETO PRECISA BATER COM O padrao.json.
     *
     * Parece burocracia até acontecer: numa instalação real, o `padrao.json` ficou com
     * o nome de exemplo (`meu-projeto`) e TODO derivado saiu carimbado errado, com o
     * build verde. Ninguém percebeu porque nada comparava as duas pontas.
     *
     * Também é o que denuncia documento colado de outro repositório — que vem inteiro,
     * com afirmações que nunca foram verdade aqui.
     */
    if (!empty($fm['projeto']) && $fm['projeto'] !== $c['projeto']) {
        $erros[] = "{$rel}: `projeto: {$fm['projeto']}` não bate com o `padrao.json` "
                 . "(`{$c['projeto']}`). Ou o documento veio de outro repositório, ou a "
                 . 'configuração ficou com o nome de exemplo.';
    }

    if (isset($fm['tipo']) && !in_array($fm['tipo'], $vocab['tipo'], true)) {
        $erros[] = "{$rel}: tipo `{$fm['tipo']}` fora do vocabulário";
    }
    if (isset($fm['status']) && !in_array($fm['status'], $vocab['status'], true)) {
        $erros[] = "{$rel}: status `{$fm['status']}` fora do vocabulário";
    }

    if (!empty($fm['id'])) {
        if (isset($idsVistos[$fm['id']])) {
            $erros[] = "{$rel}: id `{$fm['id']}` duplicado (também em {$idsVistos[$fm['id']]})";
        }
        $idsVistos[$fm['id']] = $rel;
        $porId[$fm['id']] = ['fm' => $fm, 'rel' => $rel];
    }

    /*
     * ÂNCORA QUEBRADA É O CORAÇÃO DESTA VERIFICAÇÃO.
     *
     * Documento que cita caminho morto vira mentira silenciosa, e é o tipo de erro
     * que sobrevive anos. Num caso real, uma nota especificava rota e componente que
     * nunca existiram; o código implementou outros caminhos NO MESMO DIA e ninguém
     * percebeu por mais de um mês.
     */
    foreach ((array) ($fm['ancoras'] ?? []) as $ancora) {
        if ($ancora !== '' && !file_exists(raiz() . '/' . $ancora)) {
            $erros[] = "{$rel}: âncora quebrada — `{$ancora}` não existe";
        }
    }

    if (($fm['status'] ?? '') === 'verificado' && empty($fm['verificado_commit'])) {
        $avisos[] = "{$rel}: `status: verificado` sem `verificado_commit`";
    }
}

// ------------------------------------------------------- 5: derivados vivos
$gerador = __DIR__ . '/gerar-docs.php';
$dirGerado = raiz() . '/' . trim($c['gerado']['diretorio'] ?? '', '/');

if (is_file($gerador) && is_dir($dirGerado)) {
    $antes = [];
    foreach (glob($dirGerado . '/*.md') as $g) {
        $antes[basename($g)] = (string) file_get_contents($g);
    }

    /*
     * O GERADOR ESCREVE. PRECISAMOS DESFAZER ISSO.
     *
     * Reexecutar é a única forma honesta de saber se a saída commitada corresponde ao
     * código de hoje. Mas o gerador SOBRESCREVE os arquivos — e carimba o commit
     * atual, que no CI é sempre diferente do commitado.
     *
     * Se deixarmos assim, a verificação SEGUINTE vê arquivos alterados e reprova. Não
     * porque algo está errado: porque ESTE script acabou de mexer neles.
     *
     * Verificação que altera o que verifica não é verificação.
     */
    @exec('php ' . escapeshellarg($gerador) . ' 2>&1', $saida, $rc);

    if ($rc !== 0) {
        $erros[] = 'scripts/gerar-docs.php falhou: ' . implode(' | ', array_slice($saida, 0, 3));
    } else {
        foreach ($antes as $nome => $conteudo) {
            $agora = (string) @file_get_contents($dirGerado . '/' . $nome);
            if (hashDoConteudo($conteudo) !== hashDoConteudo($agora)) {
                $erros[] = "{$c['gerado']['diretorio']}/{$nome}: desatualizado ou editado à mão. "
                         . 'Rode `vendor/bin/memoria gerar` e commite a saída.';
            }
        }
    }

    // devolve a árvore ao estado em que a encontramos
    foreach ($antes as $nome => $conteudo) {
        file_put_contents($dirGerado . '/' . $nome, $conteudo);
    }
}

// ------------------------------------------------------- 7: cadeia de origem
/*
 * A CADEIA É O QUE TORNA A DOCUMENTAÇÃO EVOLUTIVA EM VEZ DE ESCRITA-UMA-VEZ.
 *
 * Cada documento de engenharia declara de quais outros ele DEPENDE:
 *
 *     PRD  (por que fazer)  →  FDD (o que faz)  →  HLD (como é)  →  LLD (como está feito)
 *     e todo ADR que restringe o que o documento afirma
 *
 * Leia `deriva_de` como "se algum destes cair, eu preciso ser revisto". Sem esse campo,
 * ninguém responde à pergunta que causa metade da documentação podre: **quando isto
 * mudar, o que mais preciso revisar?**
 *
 * Severidades, deliberadamente diferentes:
 *
 *   ERRO   aponta para id que não existe. Mesma família da âncora quebrada.
 *   ERRO   direção invertida. A cadeia deixou de dizer o que dizia.
 *   ERRO   documento `verificado` pendurado em pai `superado`. O mais valioso: a origem
 *          caiu e o detalhamento continuou de pé, afirmando o que o projeto abandonou.
 *   AVISO  pai reverificado depois do filho. Não quer dizer errado — quer dizer que
 *          ninguém olhou. Como falha dura encheria o build por mudança de vírgula.
 */
$cadeia  = $c['cadeia'] ?? [];
$niveis  = $cadeia['niveis'] ?? [];
$exigem  = $cadeia['exige_origem'] ?? [];

foreach ($porId as $id => $d) {
    $fm   = $d['fm'];
    $rel  = $d['rel'];
    $tipo = $fm['tipo'] ?? '';
    $pais = array_values(array_filter((array) ($fm['deriva_de'] ?? []), fn ($p) => $p !== ''));

    if (!$pais && in_array($tipo, $exigem, true) && ($fm['status'] ?? '') !== 'superado') {
        $avisos[] = "{$rel}: `{$tipo}` sem `deriva_de`. De qual documento este veio? "
                  . 'Um detalhamento sem origem declarada é um detalhamento que ninguém '
                  . 'conferiu contra requisito nenhum.';
    }

    foreach ($pais as $paiId) {
        if ($paiId === $id) {
            $erros[] = "{$rel}: `deriva_de` aponta para si mesmo";
            continue;
        }
        if (!isset($porId[$paiId])) {
            $erros[] = "{$rel}: `deriva_de: {$paiId}` — não existe documento com esse id";
            continue;
        }

        $pai = $porId[$paiId]['fm'];

        if (isset($niveis[$tipo], $niveis[$pai['tipo'] ?? '']) && $niveis[$pai['tipo']] > $niveis[$tipo]) {
            $erros[] = "{$rel}: cadeia invertida — `{$tipo}` não pode derivar de "
                     . "`{$pai['tipo']}` ({$paiId}). A origem tem que estar mais perto do "
                     . 'problema, não mais perto do código.';
        }

        if (($pai['status'] ?? '') === 'superado' && ($fm['status'] ?? '') === 'verificado') {
            $erros[] = "{$rel}: está `verificado`, mas deriva de `{$paiId}`, que está "
                     . '`superado`. Revise e marque como `superado` também, ou reaponte '
                     . 'para o documento que substituiu o pai.';
        }

        $vf = $fm['verificado_em'] ?? '';
        $vp = $pai['verificado_em'] ?? '';
        if ($vf !== '' && $vp !== '' && $vp > $vf) {
            $avisos[] = "{$rel}: o pai `{$paiId}` foi reverificado em {$vp}, depois deste "
                      . "({$vf}). Pode estar em dia — mas ninguém olhou desde então.";
        }
    }
}

/*
 * CICLO NA CADEIA — o erro que aparece assim que os ADRs entram.
 *
 * É fácil de cometer sem perceber: o FDD declara depender do ADR que decidiu uma regra,
 * o ADR declara depender do HLD que motivou a decisão, e o HLD depende do FDD. Cada uma
 * das três linhas parece certa isolada; juntas afirmam que os três dependem de si
 * mesmos, e "revise quem depende deste" deixa de ter resposta.
 *
 * Custou uma travada de verdade: a primeira versão do gerador desenhava a árvore
 * recursivamente e entrou em laço infinito até o processo ser morto pelo sistema.
 *
 * A regra que desfaz: entre dois documentos, a seta aponta uma vez só, e aponta para
 * quem levanta a pergunta que o outro responde.
 */
$estado = [];   // 0 = não visitado, 1 = na pilha, 2 = fechado
$pilha  = [];
$ciclos = [];

$visita = function (string $id) use (&$visita, &$estado, &$pilha, &$ciclos, $porId): void {
    $estado[$id] = 1;
    $pilha[] = $id;

    foreach ((array) ($porId[$id]['fm']['deriva_de'] ?? []) as $paiId) {
        if ($paiId === '' || !isset($porId[$paiId])) {
            continue;
        }
        if (($estado[$paiId] ?? 0) === 1) {
            $corte = array_slice($pilha, array_search($paiId, $pilha, true));
            $ciclos[] = implode(' → ', $corte) . ' → ' . $paiId;
        } elseif (($estado[$paiId] ?? 0) === 0) {
            $visita($paiId);
        }
    }

    array_pop($pilha);
    $estado[$id] = 2;
};

foreach (array_keys($porId) as $id) {
    if (($estado[$id] ?? 0) === 0) {
        $visita($id);
    }
}

foreach (array_unique($ciclos) as $ciclo) {
    $erros[] = "cadeia circular: {$ciclo}\n"
             . "      Entre dois documentos a dependência aponta UMA vez só. Decida qual dos\n"
             . "      dois levanta a pergunta que o outro responde — esse é o pai — e apague\n"
             . "      a seta de volta. ADR costuma depender do documento que motivou a\n"
             . "      decisão; quem implementa a decisão é que depende do ADR, nunca os dois.";
}

// ------------------------------------------------------ 6: ponteiros da raiz
/*
 * CLAUDE.md, AGENTS.md, .cursor/rules/ e similares existem porque cada ferramenta
 * procura o seu. São ATALHOS para `docs/PROJETO.md` — nada mais.
 *
 * O modo como isso apodrece é sempre o mesmo: alguém acrescenta "só uma observação"
 * no CLAUDE.md, depois outra, e em três meses ele contradiz o PROJETO.md. Aí existem
 * duas portas de entrada dizendo coisas diferentes, e qual delas o agente lê depende
 * de qual ferramenta ele está usando. É a bifurcação, na porta da frente.
 *
 * A régua é grosseira de propósito: precisa citar a entrada canônica, e precisa caber
 * num limite de linhas. Ponteiro que cresce parou de ser ponteiro.
 */
$pont = $c['ponteiros'] ?? [];
$limite = (int) ($pont['limite_de_linhas'] ?? 40);
$entrada = trim($c['acervos']['canonico'], '/') . '/PROJETO.md';

foreach ($pont['arquivos'] ?? [] as $p) {
    $abs = raiz() . '/' . $p;
    if (!is_file($abs)) {
        $avisos[] = "{$p}: declarado em `ponteiros.arquivos` mas não existe";
        continue;
    }
    $texto = (string) file_get_contents($abs);
    $linhas = substr_count(rtrim($texto), "\n") + 1;

    if (!str_contains($texto, $entrada) && !str_contains($texto, 'AGENTS.md')) {
        $erros[] = "{$p}: é ponteiro, mas não cita `{$entrada}` nem `AGENTS.md`. "
                 . 'Um agente que só lê este arquivo nunca chega à porta de entrada.';
    }
    if ($linhas > $limite) {
        $erros[] = "{$p}: {$linhas} linhas (limite {$limite}). Ponteiro que cresce virou "
                 . "fonte paralela — mova o conteúdo para `{$entrada}` ou para o documento "
                 . 'de assunto e deixe só o apontamento.';
    }
}

// ---------------------------------------------------------------------- saída
$ignorados = 0;
foreach ($arquivos as $f) {
    if (comecaCom(relativo($f), $ignorar)) {
        $ignorados++;
    }
}
$verificados = count($arquivos) - count($legados) - count($foraDaRegua) - $ignorados;

titulo("Estrutura da documentação — {$c['projeto']}");
echo "  documentos verificados: {$verificados}\n";
if ($legados) {
    echo '  legados sem frontmatter (medidos pela catraca): ' . count($legados) . "\n";
}
if ($foraDaRegua) {
    echo '  fora da régua por convenção de outra ferramenta: ' . count($foraDaRegua)
       . ' (' . implode(', ', $externos) . ")\n";
}

if ($avisos) {
    echo "\nAVISOS (" . count($avisos) . "):\n";
    foreach ($avisos as $a) {
        echo "  ~ {$a}\n";
    }
}

if ($erros) {
    echo "\nERROS (" . count($erros) . "):\n";
    foreach ($erros as $e) {
        echo "  x {$e}\n";
    }
    echo "\nFalhou.\n";
    exit(1);
}

echo "\nTudo certo.\n";
exit(0);
