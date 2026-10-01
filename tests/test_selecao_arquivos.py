from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from memoria_evolutiva import diagnosticar, lib


class SelecaoArquivosTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="teste-selecao-arquivos-")
        self.addCleanup(self._tmp.cleanup)
        self.projeto = Path(self._tmp.name).resolve()
        self.escrever("padrao.json", json.dumps({
            "projeto": "fixture-selecao",
            "acervos": {"canonico": "docs"},
            "vocabulario": {},
            "gerado": {"raiz": "app", "extensoes": ["php"]},
        }))
        self.escrever("app/Servico.php", "<?php class Servico {}\n")
        self.escrever(".gitignore", "cache/\n")
        self.ambiente = mock.patch.dict(
            os.environ, {"MEMORIA_PROJETO_RAIZ": str(self.projeto)},
        )
        self.ambiente.start()
        self.addCleanup(self.ambiente.stop)
        self.limpar_caches()
        self.addCleanup(self.limpar_caches)

    @staticmethod
    def limpar_caches() -> None:
        lib.raiz.cache_clear()
        lib.config.cache_clear()
        diagnosticar._arquivos.cache_clear()
        diagnosticar.inventario_projeto.cache_clear()
        diagnosticar.inventario_codigo.cache_clear()

    def escrever(self, nome: str, texto: str) -> Path:
        arquivo = self.projeto / nome
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text(texto, encoding="utf-8")
        return arquivo

    def git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args], cwd=self.projeto, capture_output=True,
            text=True, encoding="utf-8", check=True, timeout=30,
        )

    def test_arquivo_ignorado_nao_altera_o_inventario(self) -> None:
        self.git("init", "--quiet")
        self.git("add", "--", ".gitignore", "padrao.json", "app/Servico.php")
        antes = diagnosticar.inventario_projeto()
        self.escrever("cache/compilado.php", "<?php // cache sintetico de teste\n")
        self.limpar_caches()

        self.assertEqual(antes, diagnosticar.inventario_projeto())

    def test_ignorado_nao_altera_as_fontes_do_grafo(self) -> None:
        from memoria_evolutiva import grafo

        self.git("init", "--quiet")
        antes = grafo._arquivos()
        self.escrever("cache/compilado.php", "<?php // cache sintetico de teste\n")

        self.assertEqual(antes, grafo._arquivos())

    def test_alias_da_raiz_preserva_caminhos_para_os_consumidores(self) -> None:
        from memoria_evolutiva import gerar, grafo, instalar

        alias_tmp = tempfile.TemporaryDirectory(prefix="teste-raiz-alias-")
        self.addCleanup(alias_tmp.cleanup)
        alias = Path(alias_tmp.name) / "projeto"
        try:
            alias.symlink_to(self.projeto, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"symlink indisponivel: {exc}")

        leitores = {
            "inventario": diagnosticar.inventario_projeto,
            "codigo": diagnosticar.inventario_codigo,
            "grafo": grafo._arquivos,
            "mapa": lambda: gerar.extrator_mapa_diretorios(lib.config()),
            "deteccao": lambda: instalar._fontes_de_codigo(lib.raiz()),
        }
        for com_git in (False, True):
            if com_git:
                self.git("init", "--quiet")
            self.limpar_caches()
            esperados = {nome: ler() for nome, ler in leitores.items()}
            self.assertIn("app/Servico.php", esperados["grafo"])
            # No POSIX getcwd resolve symlinks; simula a raiz lexical retornada
            # pelo Windows (ex.: RUNNER~1), mantendo a seleção e leitura reais.
            with (
                mock.patch.dict(os.environ, {"MEMORIA_PROJETO_RAIZ": ""}),
                mock.patch("memoria_evolutiva.lib.os.getcwd", return_value=str(alias)),
            ):
                self.limpar_caches()
                self.assertEqual(alias, Path(lib.raiz()))
                for nome, ler in leitores.items():
                    with self.subTest(com_git=com_git, leitor=nome):
                        self.assertEqual(esperados[nome], ler())

    def test_env_e_bloqueado_antes_da_leitura_mesmo_versionado(self) -> None:
        bloqueados = {
            self.escrever(nome, "VALOR_SINTETICO=nao_e_credencial\n")
            for nome in (".env", ".env.production", "config/.env", ".env.php")
        }
        exemplos = {".env.example", ".env.sample", ".env.template", ".env.dist"}
        for nome in exemplos:
            self.escrever(nome, "EXEMPLO=valor-ilustrativo\n")
        leitura_real = Path.read_bytes

        def ler(arquivo: Path) -> bytes:
            self.assertNotIn(arquivo, bloqueados, "Tentativa de ler arquivo de ambiente")
            return leitura_real(arquivo)

        for com_git in (False, True):
            with self.subTest(com_git=com_git):
                if com_git:
                    self.git("init", "--quiet")
                    self.git("add", "--force", "--", ".env", ".env.production", "config/.env", ".env.php")
                self.limpar_caches()
                with mock.patch.object(Path, "read_bytes", ler):
                    caminhos = {item["arquivo"] for item in diagnosticar.inventario_projeto()}
                self.assertTrue(exemplos <= caminhos)

    def test_runtime_sem_git_nao_altera_cobertura(self) -> None:
        antes = diagnosticar.inventario_projeto()
        for nome in (
            ".phpunit.cache/test-results", "bootstrap/cache/packages.php",
            "storage/framework/cache/data/fixture", "storage/framework/sessions/fixture",
            "storage/framework/views/compilado.php", "storage/logs/aplicacao.log",
        ):
            self.escrever(nome, "artefato sintetico de runtime\n")
        self.limpar_caches()

        self.assertEqual(antes, diagnosticar.inventario_projeto())

    def test_falha_de_git_nao_vira_varredura_permissiva(self) -> None:
        self.git("init", "--quiet")
        falhas = (
            FileNotFoundError("git indisponivel"),
            subprocess.TimeoutExpired("git", 30),
            subprocess.CompletedProcess(
                ["git"], 128, stdout=b"", stderr=b"fatal: index corrupt\n",
            ),
        )
        for falha in falhas:
            with self.subTest(falha=falha):
                self.limpar_caches()
                with mock.patch(
                    "memoria_evolutiva.fontes.subprocess.run",
                    side_effect=falha if isinstance(falha, Exception) else None,
                    return_value=falha,
                ):
                    with self.assertRaisesRegex(OSError, "Git"):
                        diagnosticar.inventario_projeto()

    def test_diretorio_versionado_substituido_por_link_nao_e_lido(self) -> None:
        self.git("init", "--quiet")
        fonte = self.escrever("app/atalho/Fonte.php", "<?php // fonte local\n")
        self.git("add", "--", "app/atalho/Fonte.php")
        externo_tmp = tempfile.TemporaryDirectory(prefix="teste-fonte-externa-")
        self.addCleanup(externo_tmp.cleanup)
        externo = Path(externo_tmp.name)
        (externo / "Fonte.php").write_text("<?php // fixture externa\n", encoding="utf-8")
        fonte.unlink()
        fonte.parent.rmdir()
        try:
            fonte.parent.symlink_to(externo, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"symlink indisponivel: {exc}")

        caminhos = {item["arquivo"] for item in diagnosticar.inventario_projeto()}
        self.assertNotIn("app/atalho/Fonte.php", caminhos)

    def test_mapa_e_deteccao_usam_a_mesma_selecao(self) -> None:
        from memoria_evolutiva import gerar, instalar

        self.git("init", "--quiet")
        leitores = {
            "mapa": lambda: gerar.extrator_mapa_diretorios(lib.config()),
            "deteccao": lambda: instalar._fontes_de_codigo(str(self.projeto)),
        }
        antes = {nome: ler() for nome, ler in leitores.items()}
        self.escrever("app/cache/Compilado.php", "<?php // fixture ignorada\n")
        self.limpar_caches()
        for nome, ler in leitores.items():
            with self.subTest(leitor=nome):
                self.assertEqual(antes[nome], ler())

    def test_copia_autoteste_nao_reintroduz_ignorados_ou_env(self) -> None:
        from memoria_evolutiva import autoteste

        self.git("init", "--quiet")
        self.escrever("cache/compilado.php", "<?php // fixture ignorada\n")
        self.escrever(".env", "VALOR_SINTETICO=nao_e_credencial\n")
        copia_tmp = tempfile.TemporaryDirectory(prefix="teste-copia-selecao-")
        self.addCleanup(copia_tmp.cleanup)
        copia = Path(copia_tmp.name) / "projeto"
        autoteste._copiar(self.projeto, copia)

        self.assertFalse((copia / "cache/compilado.php").exists())
        self.assertFalse((copia / ".env").exists())
        self.assertTrue((copia / "app/Servico.php").is_file())

    def test_falha_de_selecao_impede_executar_graphify(self) -> None:
        from memoria_evolutiva import grafo

        with (
            mock.patch.object(grafo, "_arquivos", side_effect=OSError("Git falhou")),
            mock.patch.object(grafo, "_comando", side_effect=AssertionError(
                "Graphify consultado antes de validar as fontes"
            )),
        ):
            with self.assertRaisesRegex(grafo.GrafoErro, "fontes"):
                grafo.sincronizar()

    def preparar_grafo_sintetico(self) -> tuple[Path, Path]:
        from memoria_evolutiva import grafo

        fontes = grafo._arquivos()
        conteudo = {"nodes": [{"id": "fixture", "source_file": "app/Servico.php"}]}
        arquivo = self.escrever("graphify-out/graph.json", json.dumps(conteudo))
        estado = {
            "schema": 2, "provedor": "graphify", "arquivos": fontes,
            "grafo_sha256": lib.sha256_canonico(arquivo.read_bytes()),
            **grafo._validar_conteudo_grafo(conteudo, fontes),
        }
        marcador = self.escrever(".memoria/bancos/graphify.json", json.dumps(estado))
        return arquivo, marcador

    def test_verificacao_do_grafo_reprova_selecao_falha_sem_excecao(self) -> None:
        from memoria_evolutiva import grafo

        self.preparar_grafo_sintetico()
        with (
            mock.patch.object(grafo, "_cfg", return_value={"ativo": True}),
            mock.patch.object(grafo, "_arquivos", side_effect=OSError("Git falhou")),
        ):
            try:
                resultado = grafo.verificar(silencioso=True)
            except OSError as exc:
                self.fail(f"verificar deveria retornar falha controlada: {exc}")
        self.assertEqual(1, resultado)

    def test_falha_de_selecao_apos_graphify_restaura_artefato(self) -> None:
        from memoria_evolutiva import grafo

        arquivo, marcador = self.preparar_grafo_sintetico()
        antes = (arquivo.read_bytes(), marcador.read_bytes())

        def extrair(*args: object, **kwargs: object) -> subprocess.CompletedProcess:
            arquivo.write_text('{"nodes": []}', encoding="utf-8")
            return subprocess.CompletedProcess(["graphify-fixture"], 0, stdout="", stderr="")

        with (
            mock.patch.object(grafo, "_arquivos", side_effect=[{}, OSError("Git falhou")]),
            mock.patch.object(grafo, "_comando", return_value=["graphify-fixture"]),
            mock.patch.object(grafo, "_versao_comando", return_value="fixture"),
            mock.patch.object(grafo.subprocess, "run", side_effect=extrair),
        ):
            with self.assertRaises((grafo.GrafoErro, OSError)):
                grafo.sincronizar()
        self.assertEqual(antes, (arquivo.read_bytes(), marcador.read_bytes()))

    def test_cli_reporta_git_corrompido_sem_traceback(self) -> None:
        import sys

        self.git("init", "--quiet")
        self.escrever(".git/index", "indice sintetico invalido\n")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
        env["PYTHONUTF8"] = "1"
        resultado = subprocess.run(
            [sys.executable, "-m", "memoria_evolutiva", "diagnosticar", "--json"],
            cwd=self.projeto, env=env, capture_output=True, text=True,
            encoding="utf-8", timeout=30,
        )
        self.assertIn("Git recusou", resultado.stderr)
        self.assertNotIn("Traceback", resultado.stderr)
        self.assertEqual(2, resultado.returncode)

    def test_versionado_ignorado_e_fonte_nova_usam_working_tree(self) -> None:
        self.git("init", "--quiet")
        fonte = self.escrever("cache/versionado.php", "<?php // antes\n")
        self.git("add", "--force", "cache/versionado.php")
        fonte.write_text("<?php // depois\n", encoding="utf-8")
        self.escrever("app/Olá mundo.php", "<?php // novo\n")
        self.escrever("cache/ignorado.php", "<?php // ignorado\n")
        itens = {str(item["arquivo"]): item for item in diagnosticar.inventario_projeto()}
        self.assertIn("cache/versionado.php", itens)
        self.assertIn("app/Olá mundo.php", itens)
        self.assertNotIn("cache/ignorado.php", itens)
        self.assertEqual(lib.sha256_canonico(fonte.read_bytes()), itens["cache/versionado.php"]["sha256"])

    def test_subdiretorio_de_monorepo_nao_inclui_irmaos(self) -> None:
        from memoria_evolutiva import fontes

        self.git("init", "--quiet")
        self.escrever("modulo/app/Fonte.php", "<?php // modulo\n")
        self.escrever("modulo/cache/ignorado.php", "<?php // ignorado\n")
        modulo = self.projeto / "modulo"
        selecionados = fontes.arquivos(modulo, {".git"})
        self.assertEqual(["app/Fonte.php"], [p.relative_to(modulo).as_posix() for p in selecionados])

    def test_worktree_com_git_arquivo_respeita_ignorados(self) -> None:
        from memoria_evolutiva import fontes

        self.git("init", "--quiet")
        self.git("add", ".gitignore", "padrao.json", "app/Servico.php")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "--quiet", "-m", "fixture")
        copia_tmp = tempfile.TemporaryDirectory(prefix="teste-worktree-selecao-")
        self.addCleanup(copia_tmp.cleanup)
        copia = Path(copia_tmp.name).resolve() / "worktree"
        self.git("worktree", "add", "--detach", str(copia))
        (copia / "cache").mkdir()
        (copia / "cache/ignorado.php").write_text("<?php // fixture\n", encoding="utf-8")
        self.assertTrue((copia / ".git").is_file())
        arquivos = {p.relative_to(copia).as_posix() for p in fontes.arquivos(copia, {".git"})}
        self.assertIn("app/Servico.php", arquivos)
        self.assertNotIn("cache/ignorado.php", arquivos)

    def test_arvore_sem_git_funciona_sem_executavel_git(self) -> None:
        with mock.patch("memoria_evolutiva.fontes.subprocess.run", side_effect=FileNotFoundError):
            arquivos = {item["arquivo"] for item in diagnosticar.inventario_projeto()}
        self.assertIn("app/Servico.php", arquivos)

    def test_git_sem_candidatos_nao_aciona_fallback(self) -> None:
        from memoria_evolutiva import fontes

        self.git("init", "--quiet")
        processo = subprocess.CompletedProcess(["git"], 0, stdout=b"", stderr=b"")
        with mock.patch("memoria_evolutiva.fontes.subprocess.run", return_value=processo):
            self.assertEqual([], fontes.arquivos(self.projeto, {".git"}))

    def test_mapa_nao_conta_alias_de_diretorio_duas_vezes(self) -> None:
        from memoria_evolutiva import gerar

        self.escrever("app/Services/Fonte.php", "<?php // fixture\n")
        antes = gerar.extrator_mapa_diretorios(lib.config())
        try:
            (self.projeto / "app/Alias").symlink_to(
                self.projeto / "app/Services", target_is_directory=True,
            )
        except OSError as exc:
            self.skipTest(f"symlink indisponivel: {exc}")
        self.limpar_caches()
        self.assertEqual(antes, gerar.extrator_mapa_diretorios(lib.config()))


if __name__ == "__main__":
    unittest.main()
