from __future__ import annotations

import contextlib
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import test_regressoes as regressoes
from memoria_evolutiva import autoteste


class AutotesteArtefatosGitTest(unittest.TestCase):
    projeto: Path
    # Reusa exclusivamente provedores sintéticos: HTTP em porta efêmera e um
    # fake_graphify.py que gera graph.json; o produto gera os dois marcadores.
    setUp = regressoes.BancosLocaisTest.setUp
    tearDown = regressoes.BancosLocaisTest.tearDown
    cli = regressoes.BancosLocaisTest.cli

    def _preparar_git_com_artefatos_ignorados(self) -> None:
        ignorados = {
            "src/000_ignorado.php": "<?php // fixture ignorada\n",
            ".memoria/executor/estado.json": '{"fixture_runtime": true}\n',
            "graphify-out/cache/estado.json": '{"fixture_cache": true}\n',
            ".env": "FIXTURE_SINTETICA=nao_e_credencial\n",
        }
        for rel, conteudo in ignorados.items():
            arquivo = self.projeto / rel
            arquivo.parent.mkdir(parents=True, exist_ok=True)
            arquivo.write_text(conteudo, encoding="utf-8")
        with (self.projeto / ".gitignore").open("a", encoding="utf-8") as arquivo:
            arquivo.write("\ndocs/\n.memoria/\ngraphify-out/\nsrc/000_ignorado.php\n.env\n")
        for args in (("init", "--quiet"), ("add", ".gitignore", "padrao.json", "src/app.py")):
            subprocess.run(
                ["git", *args], cwd=self.projeto, capture_output=True,
                text=True, check=True, timeout=30,
            )
        preparado = self.cli("documentar")
        self.assertEqual(0, preparado.returncode, preparado.stdout + preparado.stderr)
        marcador = json.loads((self.projeto / ".memoria/bancos/graphify.json").read_text())
        self.assertEqual("fake-graphify 1.0", marcador["versao"])
        self.assertNotIn("src/000_ignorado.php", marcador["arquivos"])
        valido = self.cli("bancos", "status", "--offline")
        self.assertEqual(0, valido.returncode, valido.stdout + valido.stderr)

    def _fotografia(self) -> dict[str, bytes]:
        return {
            arquivo.relative_to(self.projeto).as_posix(): arquivo.read_bytes()
            for arquivo in self.projeto.rglob("*") if arquivo.is_file()
        }

    def test_cli_preserva_artefatos_ignorados_sem_alterar_a_origem(self) -> None:
        self._preparar_git_com_artefatos_ignorados()
        antes = self._fotografia()
        resultado = self.cli("autoteste")
        self.assertEqual(0, resultado.returncode, resultado.stdout + resultado.stderr)
        self.assertIn("0 falharam", resultado.stdout)
        self.assertIn("✔  grafo corrompido reprova mesmo com hashes de fonte iguais", resultado.stdout)
        self.assertEqual(antes, self._fotografia())

    def test_cli_preserva_dependencias_configuradas_fora_do_acervo(self) -> None:
        caminho = self.projeto / "padrao.json"
        cfg = json.loads(caminho.read_text(encoding="utf-8"))
        cfg["memoria"]["marcador"] = ".memoria/bancos/hindsight-local.json"
        cfg["catraca"]["linha_de_base"] = ".memoria/baseline-local.json"
        cfg["rag"]["manifesto"] = ".memoria/fragmentos-local.json"
        cfg["adaptadores"]["manifesto"] = ".memoria/adaptadores-local.json"
        caminho.write_text(json.dumps(cfg, ensure_ascii=False) + "\n", encoding="utf-8")
        self._preparar_git_com_artefatos_ignorados()
        antes = self._fotografia()

        resultado = self.cli("autoteste")

        self.assertEqual(0, resultado.returncode, resultado.stdout + resultado.stderr)
        self.assertIn("0 falharam", resultado.stdout)
        self.assertEqual(antes, self._fotografia())


class AutotesteCoberturaGitTest(unittest.TestCase):
    projeto: Path
    setUp = regressoes.CliEmProjetoTemporario.setUp
    tearDown = regressoes.CliEmProjetoTemporario.tearDown
    cli = regressoes.CliEmProjetoTemporario.cli

    def test_quebra_cobertura_altera_fonte_elegivel_e_nao_primeiro_php(self) -> None:
        # Existe na cópia, mas não no inventário: rglob escolhia este PHP e
        # não disparava o alarme da cobertura de src/exemplo.php.
        isca = self.projeto / "src/.memoria/000_nao_e_fonte.php"
        isca.parent.mkdir(parents=True)
        isca.write_text("<?php // fixture fora do inventario\n", encoding="utf-8")
        subprocess.run(
            ["git", "init", "--quiet"], cwd=self.projeto, capture_output=True,
            text=True, check=True, timeout=30,
        )

        resultado = self.cli("autoteste")

        self.assertEqual(0, resultado.returncode, resultado.stdout + resultado.stderr)
        self.assertIn("✔  fonte mudou sem atualizar a cobertura", resultado.stdout)
        self.assertIn("0 falharam", resultado.stdout)
        self.assertEqual("<?php // fixture fora do inventario\n", isca.read_text())


class CopiaArtefatosSeguraTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="teste-autoteste-selecao-")
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name).resolve()
        self.projeto = self.base / "origem"
        self.projeto.mkdir()

    def escrever(self, nome: str, texto: str = "fixture sintetica\n") -> Path:
        arquivo = self.projeto / nome
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text(texto, encoding="utf-8")
        return arquivo

    def test_preservacao_e_restrita_e_segura_nas_duas_copias(self) -> None:
        permitidos = {
            "docs/PROJETO.md", "docs/evidencia/local.json",
            ".memoria/bancos/local.json", "acervo-local/manifesto.json",
            "src/Fonte.php", ".gitignore",
        }
        bloqueados = {
            "src/000_ignorado.php", "docs/codigo.php", "docs/script.py",
            ".memoria/executor/estado.json", "acervo-local/cache/estado.json",
            ".env", ".env.production", "docs/.env.json",
            "bootstrap/cache/estado.json", "storage/logs/estado.json",
            ".phpunit.cache/estado.json", "docs/vendor/estado.json",
        }
        for rel in permitidos | bloqueados:
            self.escrever(rel)
        self.escrever(
            ".gitignore", "docs/\n.memoria/\nacervo-local/\nsrc/000_ignorado.php\n",
        )
        subprocess.run(
            ["git", "init", "--quiet"], cwd=self.projeto, capture_output=True,
            check=True, timeout=30,
        )
        preservar = tuple(map(Path, (
            "docs", ".memoria/bancos/local.json", "acervo-local/manifesto.json",
            # Nem uma solicitação explícita autoriza segredos ou runtime.
            ".env", ".env.production", "bootstrap/cache/estado.json",
            "storage/logs/estado.json", ".phpunit.cache/estado.json",
        )))
        copia_real = shutil.copy2

        def copiar_seguro(de: Path, para: Path) -> None:
            self.assertNotIn(de.relative_to(self.projeto).as_posix(), bloqueados)
            copia_real(de, para)

        copia_base = self.base / "copia-base"
        with mock.patch.object(autoteste.shutil, "copy2", side_effect=copiar_seguro):
            autoteste._copiar(self.projeto, copia_base, preservar)
        copia_final = self.base / "copia-final"
        autoteste._copiar(copia_base, copia_final, preservar)
        for copia in (copia_base, copia_final):
            with self.subTest(copia=copia.name):
                encontrados = {
                    arquivo.relative_to(copia).as_posix()
                    for arquivo in copia.rglob("*") if arquivo.is_file()
                }
                self.assertEqual(permitidos, encontrados)

    def test_preservacao_nao_segue_links_nem_escapa_da_raiz(self) -> None:
        self.escrever(".gitignore", "docs/\natalho/\n")
        self.escrever("docs/local.md")
        externo = self.base / "externo"
        externo.mkdir()
        (externo / "proibido.md").write_text("fixture externa\n", encoding="utf-8")
        try:
            (self.projeto / "docs/link.md").symlink_to(externo / "proibido.md")
            (self.projeto / "docs/link-dir").symlink_to(externo, target_is_directory=True)
            (self.projeto / "atalho").symlink_to(externo, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"symlink indisponivel: {exc}")
        subprocess.run(
            ["git", "init", "--quiet"], cwd=self.projeto, capture_output=True,
            check=True, timeout=30,
        )

        copia = self.base / "copia"
        autoteste._copiar(self.projeto, copia, (
            Path("docs"), Path("atalho/proibido.md"),
            Path("../externo/proibido.md"), externo / "proibido.md",
        ))

        self.assertEqual(
            {".gitignore", "docs/local.md"},
            {arquivo.relative_to(copia).as_posix() for arquivo in copia.rglob("*")
             if arquivo.is_file() or arquivo.is_symlink()},
        )

    def test_destino_resolvido_externo_e_recusado_mesmo_sem_classificacao_de_link(self) -> None:
        self.escrever(".gitignore", "docs/\n")
        externo = self.base / "externo"
        externo.mkdir()
        (externo / "proibido.md").write_text("fixture externa\n", encoding="utf-8")
        self.escrever("docs/local.md")
        try:
            (self.projeto / "docs/atalho").symlink_to(externo, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"symlink indisponivel: {exc}")
        subprocess.run(["git", "init", "--quiet"], cwd=self.projeto,
                       capture_output=True, check=True, timeout=30)
        copia = self.base / "copia"
        # Simula um redirecionamento não classificado como symlink, como uma junção.
        with mock.patch.object(Path, "is_symlink", return_value=False):
            autoteste._copiar(self.projeto, copia, (Path("docs"),))
        self.assertFalse((copia / "docs/atalho/proibido.md").exists())
        self.assertTrue((copia / "docs/local.md").is_file())

    def test_dependencias_externas_sao_recusadas_antes_de_copiar(self) -> None:
        for secao, campo in (
            ("memoria", "marcador"), ("catraca", "linha_de_base"),
            ("adaptadores", "manifesto"), ("avaliacao", "corpus"),
            ("avaliacao", "baseline"), ("avaliacao", "manifesto"),
        ):
            cfg = {
                "projeto": "fixture", "acervos": {"canonico": "docs"},
                "gerado": {"raiz": "src"}, secao: {campo: "../fora.json"},
            }
            saida = io.StringIO()
            with (
                self.subTest(campo=f"{secao}.{campo}"),
                mock.patch.object(autoteste, "config", return_value=cfg),
                mock.patch.object(autoteste, "raiz", return_value=str(self.projeto)),
                mock.patch.object(autoteste, "_copiar") as copiar,
                contextlib.redirect_stdout(saida),
            ):
                self.assertEqual(1, autoteste.main())
                self.assertIn(f"`{secao}.{campo}` precisa ficar dentro", saida.getvalue())
                copiar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
