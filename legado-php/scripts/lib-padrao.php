<?php
/**
 * lib-padrao.php — o que todos os scripts do padrão compartilham.
 *
 * Não é executável. É incluído pelos outros.
 *
 * Tudo aqui existe porque foi bug em produção pelo menos uma vez. Os comentários
 * dizem qual — apagar o comentário costuma ser o primeiro passo para o bug voltar.
 */

/**
 * Descarte de saída de erro que funciona nos dois mundos.
 *
 * `2>/dev/null` não existe no Windows: o cmd tenta gravar num arquivo `\dev\null`,
 * não acha o caminho, e imprime a mensagem de erro NO MEIO da saída do script.
 * Não quebra nada — só polui, e confunde quem está lendo o resultado.
 */
function silencioso(): string
{
    return stripos(PHP_OS_FAMILY, 'Windows') === 0 ? '2>NUL' : '2>/dev/null';
}

/**
 * Normaliza separador de diretório para barra normal.
 *
 * ESTE É O BUG MAIS PERIGOSO DA FAMÍLIA, porque não dá erro nenhum.
 *
 * No Windows o iterador devolve `C:\projeto\src\Servicos\X.php`. Uma comparação como
 * `str_contains($caminho, '/Servicos/')` simplesmente não casa — o filtro passa
 * batido e a contagem sai errada, em silêncio, com o script terminando com sucesso.
 *
 * Num caso real, isso produziu 73 ocorrências em vez de 71 e 8 em vez de 6. Só foi
 * percebido porque a documentação tinha os números certos escritos.
 *
 * O PHP no Windows aceita barra normal em qualquer caminho. Normalizar na entrada
 * resolve sem exceção.
 */
function barras(string $caminho): string
{
    return str_replace('\\', '/', $caminho);
}

/**
 * Raiz do PROJETO — não do pacote.
 *
 * Quando o kit era copiado para dentro do projeto, `dirname(__DIR__)` bastava: os
 * scripts moravam em `<projeto>/scripts/`. Instalado via Composer, eles moram em
 * `<projeto>/vendor/<fornecedor>/memoria-evolutiva/scripts/` — e `dirname(__DIR__)`
 * passaria a apontar para dentro do vendor, fazendo TODA verificação olhar para o
 * lugar errado com a maior naturalidade.
 *
 * A regra: sobe do diretório corrente até achar `padrao.json`. Funciona chamado da
 * raiz, de um subdiretório, e nas DUAS formas de instalação — via Composer e via
 * cópia direta (o layout antigo continua suportado pelos mesmos arquivos).
 *
 * Sem `padrao.json` em nenhum nível: devolve o cwd. É o caso do instalador rodando
 * num projeto ainda virgem — e é por isso que o instalador deve ser rodado NA RAIZ
 * do projeto novo.
 */
function raiz(): string
{
    static $cache = null;
    if ($cache !== null) {
        return $cache;
    }

    $dir = barras((string) getcwd());
    $sobe = $dir;
    while (true) {
        if (is_file($sobe . '/padrao.json')) {
            return $cache = $sobe;
        }
        $pai = barras(dirname($sobe));
        if ($pai === $sobe) {
            break;
        }
        $sobe = $pai;
    }
    return $cache = $dir;
}

/** Raiz do PACOTE — onde moram scripts/, stubs/ e os documentos do método. */
function pacote(): string
{
    return barras(dirname(__DIR__));
}

/** Lê e valida o padrao.json. Morre com mensagem útil se estiver quebrado. */
function config(): array
{
    static $cache = null;
    if ($cache !== null) {
        return $cache;
    }

    $arquivo = raiz() . '/padrao.json';
    if (!is_file($arquivo)) {
        fwrite(STDERR, "Não encontrei `padrao.json` na raiz do projeto.\n"
            . "Ele é o único arquivo que você edita para adaptar o padrão.\n"
            . "Rode: vendor/bin/memoria instalar\n");
        exit(2);
    }

    $c = json_decode((string) file_get_contents($arquivo), true);
    if (!is_array($c)) {
        fwrite(STDERR, "`padrao.json` não é JSON válido: " . json_last_error_msg() . "\n");
        exit(2);
    }

    foreach (['projeto', 'acervos', 'vocabulario'] as $obrigatorio) {
        if (!isset($c[$obrigatorio])) {
            fwrite(STDERR, "`padrao.json` não tem a chave obrigatória `{$obrigatorio}`.\n");
            exit(2);
        }
    }
    if (empty($c['acervos']['canonico'])) {
        fwrite(STDERR, "`padrao.json`: `acervos.canonico` é obrigatório — é onde a verdade mora.\n");
        exit(2);
    }

    return $cache = $c;
}

/** Caminho absoluto do acervo canônico. */
function acervo(): string
{
    return raiz() . '/' . trim(config()['acervos']['canonico'], '/');
}

/** Todos os arquivos de uma extensão dentro de um diretório, recursivo e ordenado. */
function arquivosPorExtensao(string $dir, string $ext): array
{
    if (!is_dir($dir)) {
        return [];
    }
    $out = [];
    $it = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($dir, FilesystemIterator::SKIP_DOTS));
    foreach ($it as $f) {
        if ($f->isFile() && strtolower($f->getExtension()) === strtolower($ext)) {
            $out[] = barras($f->getPathname());
        }
    }
    sort($out);
    return $out;
}

/** Todo markdown de um diretório. */
function markdowns(string $dir): array
{
    return arquivosPorExtensao($dir, 'md');
}

/** Caminho relativo à raiz, com barra normal. */
function relativo(string $absoluto): string
{
    return str_replace(raiz() . '/', '', barras($absoluto));
}

/** O caminho começa com algum dos prefixos? */
function comecaCom(string $caminho, array $prefixos): bool
{
    $caminho = barras($caminho);
    foreach ($prefixos as $p) {
        if ($p === '') {
            continue;
        }
        if (str_starts_with($caminho, rtrim($p, '/') . '/') || $caminho === rtrim($p, '/')) {
            return true;
        }
    }
    return false;
}

/** O caminho contém algum dos trechos? Usado pelas exclusões dos contadores. */
function contemAlgum(string $caminho, array $trechos): bool
{
    $caminho = barras($caminho);
    foreach ($trechos as $t) {
        if ($t !== '' && str_contains($caminho, $t)) {
            return true;
        }
    }
    return false;
}

/**
 * Frontmatter YAML simples — `chave: valor`, listas com `- ` e blocos `>-`.
 *
 * Devolve null se não houver frontmatter. Deliberadamente não usa parser YAML
 * completo: o padrão só precisa de chave/valor e lista, e uma dependência externa
 * aqui tornaria o kit mais difícil de instalar do que o problema que ele resolve.
 */
function frontmatter(string $conteudo): ?array
{
    if (!str_starts_with($conteudo, "---\n")) {
        return null;
    }
    $fim = strpos($conteudo, "\n---", 4);
    if ($fim === false) {
        return null;
    }
    $bloco = substr($conteudo, 4, $fim - 4);

    $dados = [];
    $chave = null;
    $dobra = false;

    foreach (explode("\n", $bloco) as $linha) {
        if ($dobra) {
            if (preg_match('/^\s+\S/', $linha)) {
                $dados[$chave] = trim($dados[$chave] . ' ' . trim($linha));
                continue;
            }
            $dobra = false;
        }
        if (preg_match('/^([a-z_]+):\s*>-?\s*$/', $linha, $m)) {
            $chave = $m[1];
            $dados[$chave] = '';
            $dobra = true;
            continue;
        }
        if (preg_match('/^\s+-\s+(.+)$/', $linha, $m) && $chave !== null && is_array($dados[$chave] ?? null)) {
            $dados[$chave][] = trim($m[1], " \"'");
            continue;
        }
        if (preg_match('/^([a-z_]+):\s*(.*)$/', $linha, $m)) {
            $chave = $m[1];
            $valor = trim($m[2]);
            if ($valor === '') {
                $dados[$chave] = [];
            } elseif ($valor === '[]') {
                $dados[$chave] = [];
                $chave = null;
            } else {
                $dados[$chave] = trim($valor, " \"'");
                $chave = null;
            }
        }
    }
    return $dados;
}

/**
 * Hash do conteúdo ignorando o carimbo de geração.
 *
 * `verificado_em`, `verificado_commit` e a linha "Gerado ... em `sha`" mudam a cada
 * commit, mesmo quando o conteúdo substantivo é idêntico. Sem esta normalização, os
 * arquivos derivados ficariam permanentemente "desatualizados" para o verificador de
 * índice, e o CI viveria vermelho por causa de um carimbo.
 *
 * O índice precisa ser refeito quando o FATO muda, não quando o commit muda.
 */
function hashDoConteudo(string $conteudo): string
{
    $limpo = preg_replace(
        ['/^verificado_(em|commit): .*$/m', '/em `[^`]*`\.$/m'],
        ['X', 'em `X`.'],
        $conteudo
    );
    return substr(hash('sha256', (string) $limpo), 0, 16);
}

/** Sha curto do commit atual, ou string vazia se não houver git. */
function commitAtual(): string
{
    return trim((string) @shell_exec(
        'git -C ' . escapeshellarg(raiz()) . ' rev-parse --short HEAD ' . silencioso()
    ));
}

/** Título de seção na saída do terminal. */
function titulo(string $texto): void
{
    echo "\n{$texto}\n" . str_repeat('─', min(strlen($texto), 72)) . "\n";
}
