from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from memoria_evolutiva.fragmentos import _cabecalhos, _partir_texto, consultaveis
from memoria_evolutiva.lib import hash_do_conteudo
from memoria_evolutiva import contexto, executor, seguranca


REPOSITORIO = Path(__file__).resolve().parents[1]


class CliEmProjetoTemporario(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="teste-memoria-")
        self.projeto = Path(self._tmp.name) / "projeto"
        (self.projeto / "src").mkdir(parents=True)
        (self.projeto / "src/exemplo.php").write_text("<?php echo 'ok';\n", encoding="utf-8")
        (self.projeto / ".gitignore").write_text("privado/\n", encoding="utf-8")

        for args in (
            ["instalar", "--projeto=fixture", "--codigo=src", "--sem-bancos"],
            ["gerar"],
            ["catraca", "--medir"],
        ):
            r = self.cli(*args)
            self.assertEqual(0, r.returncode, r.stdout + r.stderr)
            if args[0] == "instalar":
                self.saida_instalacao = r.stdout

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def cli(self, *args: str, ambiente: dict[str, str] | None = None,
            texto: bool = True) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPOSITORIO) + os.pathsep + env.get("PYTHONPATH", "")
        env["PYTHONUTF8"] = "1"
        if ambiente:
            env.update(ambiente)
        return subprocess.run(
            [sys.executable, "-m", "memoria_evolutiva", *args],
            cwd=self.projeto,
            env=env,
            capture_output=True,
            text=texto,
            encoding="utf-8" if texto else None,
            # Em Windows, criação e remoção de muitas árvores temporárias pode ser
            # atrasada por antivírus/indexador. O produto tem time-outs próprios; este
            # limite serve apenas para impedir travamento da suíte.
            timeout=120,
        )

    def preparar_git(self) -> str:
        for comando in (
            ["git", "init"],
            ["git", "config", "user.email", "teste@example.invalid"],
            ["git", "config", "user.name", "Teste"],
            ["git", "add", "."],
            ["git", "commit", "-m", "fixture"],
        ):
            resultado = subprocess.run(
                comando, cwd=self.projeto, capture_output=True, text=True,
                encoding="utf-8", timeout=30,
            )
            self.assertEqual(0, resultado.returncode, resultado.stdout + resultado.stderr)
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.projeto, capture_output=True,
            text=True, encoding="utf-8", check=True, timeout=30,
        ).stdout.strip()

    def test_validar_reprova_derivado_ausente_sem_recria_lo(self) -> None:
        derivado = self.projeto / "docs/gerado/cadeia-documentos.md"
        derivado.unlink()

        r = self.cli("validar")

        self.assertEqual(1, r.returncode, r.stdout + r.stderr)
        self.assertIn("derivado ausente", r.stdout)
        self.assertFalse(derivado.exists(), "validar não pode recriar o que verifica")

    def test_validar_reprova_derivado_extra_sem_remove_lo(self) -> None:
        extra = self.projeto / "docs/gerado/obsoleto.md"
        extra.write_text("# derivado sem dono\n", encoding="utf-8")

        r = self.cli("validar")

        self.assertEqual(1, r.returncode, r.stdout + r.stderr)
        self.assertIn("sem extrator declarado", r.stdout)
        self.assertTrue(extra.exists(), "validar não pode remover o que verifica")

    def test_validar_reprova_edicao_sem_desfaze_la(self) -> None:
        derivado = self.projeto / "docs/gerado/mapa-diretorios.md"
        alterado = derivado.read_text(encoding="utf-8") + "\nlinha intrusa\n"
        derivado.write_text(alterado, encoding="utf-8")

        r = self.cli("validar")

        self.assertEqual(1, r.returncode, r.stdout + r.stderr)
        self.assertIn("editado à mão", r.stdout)
        self.assertEqual(alterado, derivado.read_text(encoding="utf-8"))

    def test_cli_nao_quebra_quando_saida_cp1252_nao_representa_unicode(self) -> None:
        r = self.cli(
            "validar",
            ambiente={"PYTHONUTF8": "0", "PYTHONIOENCODING": "cp1252:strict"},
            texto=False,
        )

        saida = r.stdout + r.stderr
        self.assertEqual(0, r.returncode, saida.decode("cp1252", errors="replace"))
        self.assertNotIn(b"UnicodeEncodeError", saida)

    def test_instalar_padrao_exige_hindsight_e_graphify(self) -> None:
        r = self.cli("instalar", "--projeto=fixture", "--codigo=src", "--adiar-bancos")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)

        configuracao = json.loads((self.projeto / "padrao.json").read_text(encoding="utf-8"))
        self.assertEqual("externo", configuracao["acervos"]["indice"])
        self.assertTrue(configuracao["memoria"]["ativo"])
        self.assertTrue(configuracao["memoria"]["obrigatorio"])
        self.assertEqual("hindsight", configuracao["memoria"]["ferramenta"])
        self.assertTrue(configuracao["grafo"]["ativo"])
        self.assertTrue(configuracao["grafo"]["obrigatorio"])
        self.assertEqual("graphify", configuracao["grafo"]["ferramenta"])
        self.assertEqual("127.0.0.1", configuracao["contexto"]["http_host"])
        self.assertEqual([], json.loads(self.cli(
            "contexto", "--pergunta=inexistentezz", "--perfil=atendimento",
            "--produto=produto-a", "--tenant=tenant-a", "--json"
        ).stdout)["acoes_permitidas"])
        self.assertEqual(
            ["docs/_arquivo/", "docs/_templates/"],
            configuracao["catraca"]["contadores"][0]["excluir"],
        )
        gitignore = (self.projeto / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("privado/", gitignore)
        self.assertIn("graphify-out/cache/", gitignore)
        self.assertIn(".memoria/executor/", gitignore)
        self.assertTrue(configuracao["executor"]["ativo"])
        self.assertEqual([], configuracao["executor"]["capacidades_permitidas"])
        self.assertFalse(configuracao["executor"]["publicacao_automatica"])
        self.assertTrue(configuracao["avaliacao"]["ativo"])
        for caminho in (
            "docs/avaliacao/casos-rag-v1.json",
            "docs/politicas/baseline-rag-v1.json",
            "docs/gerado/relatorio-avaliacao-rag-v1.json",
            "docs/gerado/manifesto-avaliacao-rag-v1.json",
        ):
            self.assertTrue((self.projeto / caminho).is_file(), caminho)

    def test_avaliacao_mede_perfis_bloqueia_adulteracao_e_registra_drift(self) -> None:
        verificada = self.cli("avaliar", "verificar", "--json")
        payload = json.loads(verificada.stdout)
        self.assertEqual(0, verificada.returncode, verificada.stdout + verificada.stderr)
        relatorio = payload["relatorio"]
        self.assertTrue(relatorio["gate"]["aprovado"])
        self.assertEqual(1.0, relatorio["metricas"]["global"]["hit_3"])
        self.assertEqual(1.0, relatorio["metricas"]["global"]["cobertura_citacao"])
        self.assertEqual(0.0, relatorio["metricas"]["global"]["sem_fonte"])
        self.assertEqual(
            {"atendimento", "automacao", "engenharia"},
            set(relatorio["metricas"]["por_categoria"]),
        )

        caminho_relatorio = self.projeto / "docs/gerado/relatorio-avaliacao-rag-v1.json"
        original = caminho_relatorio.read_bytes()
        caminho_relatorio.write_bytes(original + b"\n")
        adulterada = self.cli("avaliar", "verificar", "--json")
        self.assertEqual(1, adulterada.returncode, adulterada.stdout + adulterada.stderr)
        self.assertEqual(original + b"\n", caminho_relatorio.read_bytes())

        self.assertEqual(0, self.cli("avaliar", "gerar").returncode)
        configuracao_path = self.projeto / "padrao.json"
        configuracao = json.loads(configuracao_path.read_text(encoding="utf-8"))
        configuracao["rag"]["embedding_modelo"] = "modelo-local-v2"
        configuracao_path.write_text(
            json.dumps(configuracao, ensure_ascii=False, indent=4) + "\n", encoding="utf-8"
        )
        self.assertEqual(0, self.cli("fragmentos", "gerar").returncode)
        drift = self.cli("avaliar", "gerar", "--json")
        drift_payload = json.loads(drift.stdout)
        self.assertEqual(0, drift.returncode, drift.stdout + drift.stderr)
        self.assertTrue(drift_payload["relatorio"]["drift"]["perfil_rag_alterado"])
        self.assertEqual(0.0, drift_payload["relatorio"]["drift"]["global"]["hit_3"])
        self.assertTrue(
            drift_payload["relatorio"]["drift"]["componentes_rag"]
            ["embedding_modelo"]["alterado"]
        )

        baseline = self.projeto / "docs/politicas/baseline-rag-v1.json"
        baseline_antes = baseline.read_bytes()
        baseline_ambigua = json.loads(baseline_antes.decode("utf-8"))
        baseline_ambigua["campo_ambiguo"] = True
        sem_assinatura = {
            chave: valor for chave, valor in baseline_ambigua.items()
            if chave != "assinatura"
        }
        baseline_ambigua["assinatura"] = hashlib.sha256(json.dumps(
            sem_assinatura, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest()
        baseline.write_text(
            json.dumps(baseline_ambigua, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.assertEqual(1, self.cli("avaliar", "verificar").returncode)
        baseline.write_bytes(baseline_antes)

        corpus = self.projeto / "docs/avaliacao/casos-rag-v1.json"
        casos = json.loads(corpus.read_text(encoding="utf-8"))
        casos["casos"][0]["pergunta"] += " alterada"
        corpus.write_text(
            json.dumps(casos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        bloqueada = self.cli("avaliar", "gerar", "--json")
        self.assertEqual(1, bloqueada.returncode, bloqueada.stdout + bloqueada.stderr)
        self.assertEqual(baseline_antes, baseline.read_bytes())
        casos["casos"][0]["fontes_esperadas"] = ["docs/INEXISTENTE.md"]
        corpus.write_text(
            json.dumps(casos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        remedicao_ruim = self.cli("avaliar", "medir", "--json")
        self.assertEqual(1, remedicao_ruim.returncode, remedicao_ruim.stdout + remedicao_ruim.stderr)
        self.assertIn("não é permitido medir baseline reprovado", remedicao_ruim.stdout)
        self.assertEqual(baseline_antes, baseline.read_bytes())

        for caso in casos["casos"]:
            caso["fontes_esperadas"] = []
            caso["termos_esperados"] = []
            caso["espera_sem_fonte"] = True
        corpus.write_text(
            json.dumps(casos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        sem_positivos = self.cli("avaliar", "medir", "--json")
        self.assertEqual(1, sem_positivos.returncode, sem_positivos.stdout)
        self.assertIn("caso positivo de engenharia e de automacao", sem_positivos.stdout)
        self.assertEqual(baseline_antes, baseline.read_bytes())

    def test_executor_documenta_em_worktree_retorna_e_nao_duplica_run(self) -> None:
        base = self.preparar_git()
        ambiente_interrompido = {
            "MEMORIA_EXECUTOR_INTERROMPER_APOS": "executar-acao",
        }

        primeira = self.cli(
            "executar", "--run-id=cron-doc-001", "--acao=documentar", "--json",
            ambiente=ambiente_interrompido,
        )
        payload_primeiro = json.loads(primeira.stdout)
        self.assertEqual(75, primeira.returncode, primeira.stdout + primeira.stderr)
        self.assertEqual("interrompido", payload_primeiro["status"])
        checkpoint = payload_primeiro["checkpoints"]["executar-acao"]["concluido_em"]

        retomada = self.cli(
            "executar", "--run-id=cron-doc-001", "--acao=documentar", "--json",
        )
        payload = json.loads(retomada.stdout)
        self.assertEqual(0, retomada.returncode, retomada.stdout + retomada.stderr)
        self.assertTrue(payload["ok"])
        self.assertEqual("concluido", payload["status"])
        self.assertEqual(checkpoint, payload["checkpoints"]["executar-acao"]["concluido_em"])
        self.assertEqual("git-worktree-branch-v1", payload["isolamento"])
        self.assertTrue(payload["branch"].startswith("memoria/run-"))
        self.assertTrue(Path(payload["worktree"]).is_dir())
        self.assertTrue(Path(payload["diff"]["patch"]).is_file())
        self.assertTrue(payload["diff"]["arquivos"])
        self.assertFalse(payload["publicado"])
        self.assertFalse(payload["commit_criado"])
        self.assertEqual([], payload["mutacoes_externas"])
        self.assertEqual(base, subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.projeto, capture_output=True,
            text=True, encoding="utf-8", check=True, timeout=30,
        ).stdout.strip())
        self.assertEqual("", subprocess.run(
            ["git", "status", "--porcelain"], cwd=self.projeto, capture_output=True,
            text=True, encoding="utf-8", check=True, timeout=30,
        ).stdout.strip())

        estado = self.projeto / ".memoria/executor/runs/cron-doc-001.json"
        antes = estado.read_bytes()
        repetida = self.cli(
            "executar", "--run-id=cron-doc-001", "--acao=documentar", "--json",
        )
        replay = json.loads(repetida.stdout)
        self.assertEqual(0, repetida.returncode, repetida.stdout + repetida.stderr)
        self.assertTrue(replay["replay"])
        self.assertEqual(antes, estado.read_bytes())
        self.assertEqual(payload["diff"]["patch_sha256"], replay["diff"]["patch_sha256"])

    def test_executor_verifica_read_only_e_lock_bloqueia_concorrencia(self) -> None:
        self.preparar_git()
        resultado = self.cli(
            "executar", "--run-id=cron-check-001", "--acao=verificar", "--json",
        )
        payload = json.loads(resultado.stdout)
        self.assertEqual(0, resultado.returncode, resultado.stdout + resultado.stderr)
        self.assertEqual("raiz-somente-leitura", payload["isolamento"])
        self.assertIsNone(payload["branch"])
        self.assertIsNone(payload["diff"])

        lock = self.projeto / ".memoria/executor/lock.json"
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(json.dumps({
            "schema": 1,
            "run_id": "outro-run",
            "pid": os.getpid(),
            "host": socket.gethostname(),
            "token": "ocupado",
            "timestamp": time.time(),
        }), encoding="utf-8")
        concorrente = self.cli(
            "executar", "--run-id=cron-check-002", "--acao=verificar", "--json",
        )
        bloqueio = json.loads(concorrente.stdout)
        self.assertEqual(73, concorrente.returncode, concorrente.stdout + concorrente.stderr)
        self.assertEqual("recusado", bloqueio["status"])
        self.assertIn("execução concorrente", bloqueio["erro"])
        self.assertTrue(lock.is_file())

    def test_executor_nega_capacidade_nao_preconcedida_sem_efeito(self) -> None:
        self.preparar_git()
        resultado = self.cli(
            "executar", "--run-id=cron-cap-001", "--acao=documentar",
            "--capacidades=sincronizar-bancos", "--json",
        )
        payload = json.loads(resultado.stdout)
        self.assertEqual(3, resultado.returncode, resultado.stdout + resultado.stderr)
        self.assertFalse(payload["ok"])
        self.assertEqual([], payload["mutacoes_externas"])
        self.assertFalse((self.projeto / ".memoria/executor/runs/cron-cap-001.json").exists())
        branches = subprocess.run(
            ["git", "branch", "--list", "memoria/run-*"], cwd=self.projeto,
            capture_output=True, text=True, encoding="utf-8", check=True, timeout=30,
        ).stdout.strip()
        self.assertEqual("", branches)

    def test_executor_recusa_estado_adulterado_sem_escapar_do_worktree(self) -> None:
        self.preparar_git()
        interrompida = self.cli(
            "executar", "--run-id=cron-adulterado-001", "--acao=documentar", "--json",
            ambiente={"MEMORIA_EXECUTOR_INTERROMPER_APOS": "preparar-worktree"},
        )
        self.assertEqual(75, interrompida.returncode, interrompida.stdout + interrompida.stderr)
        estado_path = self.projeto / ".memoria/executor/runs/cron-adulterado-001.json"
        estado = json.loads(estado_path.read_text(encoding="utf-8"))
        estado["worktree"] = str(self.projeto)
        estado["plano"] = ["executar-acao"]
        estado["checkpoints"] = {}
        estado_path.write_text(
            json.dumps(estado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        antes = subprocess.run(
            ["git", "status", "--porcelain"], cwd=self.projeto, capture_output=True,
            text=True, encoding="utf-8", check=True, timeout=30,
        ).stdout

        retomada = self.cli(
            "executar", "--run-id=cron-adulterado-001", "--acao=documentar", "--json",
        )
        payload = json.loads(retomada.stdout)

        self.assertEqual(3, retomada.returncode, retomada.stdout + retomada.stderr)
        self.assertEqual("recusado", payload["status"])
        self.assertIn("invariantes", payload["erro"])
        depois = subprocess.run(
            ["git", "status", "--porcelain"], cwd=self.projeto, capture_output=True,
            text=True, encoding="utf-8", check=True, timeout=30,
        ).stdout
        self.assertEqual(antes, depois)

    def test_executor_retoma_depois_de_cada_checkpoint_de_escrita(self) -> None:
        self.preparar_git()
        for numero, checkpoint in enumerate((
            "preparar-worktree", "executar-acao", "validar", "registrar-diff"
        ), 1):
            with self.subTest(checkpoint=checkpoint):
                run_id = f"retomada-{numero:02d}"
                interrompida = self.cli(
                    "executar", f"--run-id={run_id}", "--acao=documentar", "--json",
                    ambiente={"MEMORIA_EXECUTOR_INTERROMPER_APOS": checkpoint},
                )
                antes = json.loads(interrompida.stdout)
                self.assertEqual(75, interrompida.returncode, interrompida.stdout + interrompida.stderr)
                self.assertIn(checkpoint, antes["checkpoints"])
                carimbo = antes["checkpoints"][checkpoint]["concluido_em"]

                retomada = self.cli(
                    "executar", f"--run-id={run_id}", "--acao=documentar", "--json",
                )
                depois = json.loads(retomada.stdout)
                self.assertEqual(0, retomada.returncode, retomada.stdout + retomada.stderr)
                self.assertEqual("concluido", depois["status"])
                self.assertEqual(carimbo, depois["checkpoints"][checkpoint]["concluido_em"])

    def test_fluxo_completo_e_autoteste_nao_alteram_projeto(self) -> None:
        vendor = self.projeto / "vendor"
        vendor.mkdir()
        (vendor / "dependencia.php").write_text("<?php return true;\n", encoding="utf-8")
        self.preparar_git()
        documentar = self.cli("documentar")
        self.assertEqual(0, documentar.returncode, documentar.stdout + documentar.stderr)

        def fotografia() -> dict[str, bytes]:
            return {
                str(arquivo.relative_to(self.projeto)): arquivo.read_bytes()
                for arquivo in self.projeto.rglob("*")
                if arquivo.is_file()
            }

        antes = fotografia()
        verificar = self.cli("verificar")
        autoteste = self.cli("autoteste")
        depois = fotografia()

        self.assertEqual(0, verificar.returncode, verificar.stdout + verificar.stderr)
        self.assertEqual(0, autoteste.returncode, autoteste.stdout + autoteste.stderr)
        self.assertIn("22 passaram", autoteste.stdout)
        self.assertEqual(antes, depois)

    def test_consulta_conjunta_recusa_opt_out_sem_tentar_provedores(self) -> None:
        r = self.cli("bancos", "consultar", "--pergunta=teste")

        self.assertEqual(2, r.returncode, r.stdout + r.stderr)
        self.assertIn("exige Hindsight e Graphify ativos", r.stdout)

    def test_extrator_nao_pode_escrever_fora_do_diretorio_gerado(self) -> None:
        scripts = self.projeto / "scripts"
        scripts.mkdir()
        extrator = scripts / "extrator.py"
        extrator.write_text(
            "import json\n"
            "print(json.dumps([{'nome': '../../fora', 'id': 'X', "
            "'titulo': 'X', 'corpo': 'X'}]))\n",
            encoding="utf-8",
        )
        arq_config = self.projeto / "padrao.json"
        configuracao = json.loads(arq_config.read_text(encoding="utf-8"))
        configuracao["gerado"]["extensao_do_projeto"] = "scripts/extrator.py"
        configuracao["gerado"]["extratores"] = ["../../fora"]
        arq_config.write_text(
            json.dumps(configuracao, ensure_ascii=False, indent=4) + "\n",
            encoding="utf-8",
        )

        r = self.cli("gerar")

        self.assertEqual(2, r.returncode, r.stdout + r.stderr)
        self.assertIn("nome inseguro", r.stderr)
        self.assertFalse((self.projeto / "fora.md").exists())

    def test_diagnosticar_e_analisar_sao_deterministicos_e_sem_escrita(self) -> None:
        def fotografia() -> dict[str, bytes]:
            return {
                str(arquivo.relative_to(self.projeto)): arquivo.read_bytes()
                for arquivo in self.projeto.rglob("*")
                if arquivo.is_file()
            }

        antes = fotografia()
        diagnostico_1 = self.cli("diagnosticar", "--json")
        diagnostico_2 = self.cli("diagnosticar", "--json")
        analise = self.cli("analisar", "--json")
        depois = fotografia()

        self.assertEqual(0, diagnostico_1.returncode, diagnostico_1.stdout + diagnostico_1.stderr)
        self.assertEqual(diagnostico_1.stdout, diagnostico_2.stdout)
        dados = json.loads(diagnostico_1.stdout)
        self.assertEqual(1, dados["codigo"]["arquivos"])
        self.assertEqual({".php": 1}, dados["codigo"]["por_extensao"])
        self.assertTrue(json.loads(analise.stdout)["lacunas_para_confirmar"])
        self.assertEqual(antes, depois)

    def test_diagnostico_com_raiz_ponto_nao_conta_o_proprio_acervo(self) -> None:
        (self.projeto / "README.md").write_text("# Fonte observável\n", encoding="utf-8")
        arq_config = self.projeto / "padrao.json"
        configuracao = json.loads(arq_config.read_text(encoding="utf-8"))
        configuracao["gerado"]["raiz"] = "."
        configuracao["gerado"]["extensoes"] = ["md"]
        arq_config.write_text(
            json.dumps(configuracao, ensure_ascii=False, indent=4) + "\n",
            encoding="utf-8",
        )

        antes = self.cli("diagnosticar", "--json")
        (self.projeto / "docs/gerado/intruso.md").write_text(
            "# Não pode entrar no inventário\n", encoding="utf-8"
        )
        depois = self.cli("diagnosticar", "--json")

        self.assertEqual(0, antes.returncode, antes.stdout + antes.stderr)
        self.assertEqual(0, depois.returncode, depois.stdout + depois.stderr)
        contagem_antes = json.loads(antes.stdout)["codigo"]
        contagem_depois = json.loads(depois.stdout)["codigo"]
        self.assertGreaterEqual(contagem_antes["arquivos"], 1)
        self.assertEqual(contagem_antes, contagem_depois)

    def test_propor_documentacao_escreve_fora_do_canonico_e_nao_sobrescreve(self) -> None:
        canonicos = {
            nome: (self.projeto / f"docs/{nome}").read_bytes()
            for nome in ("PROJETO.md", "ESTADO.md", "ABERTO.md", "GLOSSARIO.md")
        }

        primeira = self.cli("propor-documentacao")
        proposta = self.projeto / ".memoria/propostas/PROJETO.md"
        conteudo_inicial = proposta.read_text(encoding="utf-8")
        segunda = self.cli("propor-documentacao")

        self.assertEqual(0, primeira.returncode, primeira.stdout + primeira.stderr)
        self.assertIn("RASCUNHO AUTOMÁTICO", conteudo_inicial)
        self.assertEqual(1, segunda.returncode)
        self.assertEqual(conteudo_inicial, proposta.read_text(encoding="utf-8"))
        self.assertEqual(
            canonicos,
            {
                nome: (self.projeto / f"docs/{nome}").read_bytes()
                for nome in canonicos
            },
        )

    def test_instalacao_entrega_nucleo_autonomo_e_validado(self) -> None:
        configuracao = json.loads(
            (self.projeto / "padrao.json").read_text(encoding="utf-8")
        )

        self.assertTrue(configuracao["autonomia"]["ativo"])
        self.assertFalse(configuracao["autonomia"]["revisao_humana_obrigatoria"])
        self.assertEqual("indeterminado", configuracao["autonomia"]["sem_evidencia"])
        self.assertNotIn("+ docs/cronologia/AAAA-MM.md", self.saida_instalacao)
        for nome in ("PROJETO.md", "ESTADO.md", "ABERTO.md", "GLOSSARIO.md"):
            conteudo = (self.projeto / "docs" / nome).read_text(encoding="utf-8")
            self.assertIn("gerenciado_por: memoria-documentar", conteudo)
        self.assertTrue((self.projeto / "docs/politicas/AUTONOMIA.md").is_file())
        workflow = (self.projeto / ".github/workflows/documentacao.yml").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("<MEMORIA_EVOLUTIVA_ORIGEM_IMUTAVEL>", workflow)
        self.assertNotIn("memoria-evolutiva.git@main", workflow)
        self.assertTrue(
            "memoria-evolutiva==6.0.0" in workflow
            or re.search(r"memoria-evolutiva\.git@[0-9a-f]{40}", workflow)
        )
        cobertura = self.projeto / "docs/gerado/cobertura-codigo.md"
        self.assertIn("src/exemplo.php", cobertura.read_text(encoding="utf-8"))
        validar = self.cli("validar")
        self.assertEqual(0, validar.returncode, validar.stdout + validar.stderr)

    def test_documentar_atualiza_cobertura_e_reprova_politica_adulterada(self) -> None:
        fonte = self.projeto / "src/novo.php"
        fonte.write_text("<?php function novo() { return 1; }\n", encoding="utf-8")

        defasado = self.cli("validar")
        documentar = self.cli("documentar")
        atualizado = self.cli("validar")

        self.assertEqual(1, defasado.returncode, defasado.stdout + defasado.stderr)
        self.assertEqual(0, documentar.returncode, documentar.stdout + documentar.stderr)
        self.assertEqual(0, atualizado.returncode, atualizado.stdout + atualizado.stderr)
        cobertura = (self.projeto / "docs/gerado/cobertura-codigo.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("src/novo.php", cobertura)

        politica = self.projeto / "docs/politicas/AUTONOMIA.md"
        politica.write_text(
            politica.read_text(encoding="utf-8").replace(
                "comportamento executado", "preferência do agente"
            ),
            encoding="utf-8",
        )
        adulterado = self.cli("validar")
        self.assertEqual(1, adulterado.returncode, adulterado.stdout + adulterado.stderr)
        self.assertIn("política autônoma alterada", adulterado.stdout)

    def test_documentar_arquiva_nucleo_anterior_sem_pedir_arbitragem(self) -> None:
        projeto_md = self.projeto / "docs/PROJETO.md"
        legado = "# Conhecimento anterior\n\nRegra e ação do sistema legado.\n".encode(
            "cp1252"
        )
        projeto_md.write_bytes(legado)

        r = self.cli("documentar")

        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("gerenciado_por: memoria-documentar", projeto_md.read_text(encoding="utf-8"))
        arquivos = list((self.projeto / ".memoria/legado-documentacao").glob("*PROJETO.md"))
        self.assertEqual(1, len(arquivos))
        self.assertEqual(legado, arquivos[0].read_bytes())

    def test_documentar_preserva_conhecimento_evolutivo_entre_execucoes(self) -> None:
        projeto_md = self.projeto / "docs/PROJETO.md"
        atual = projeto_md.read_text(encoding="utf-8")
        fato = (
            "### Regra confirmada\n\n"
            "O processamento é idempotente. Âncora: `src/exemplo.php`.\n"
        )
        atual = atual.replace(
            "<!-- memoria-evolutiva:fim -->",
            fato + "<!-- memoria-evolutiva:fim -->",
            1,
        )
        projeto_md.write_text(atual, encoding="utf-8")

        primeira = self.cli("documentar")
        segunda = self.cli("documentar")
        final = projeto_md.read_text(encoding="utf-8")

        self.assertEqual(0, primeira.returncode, primeira.stdout + primeira.stderr)
        self.assertEqual(0, segunda.returncode, segunda.stdout + segunda.stderr)
        self.assertEqual(1, final.count(fato.strip()))

    def test_validar_reprova_bloco_evolutivo_duplicado(self) -> None:
        projeto_md = self.projeto / "docs/PROJETO.md"
        texto = projeto_md.read_text(encoding="utf-8")
        projeto_md.write_text(
            texto + "\n<!-- memoria-evolutiva:inicio -->\nextra\n"
            "<!-- memoria-evolutiva:fim -->\n",
            encoding="utf-8",
        )

        resultado = self.cli("validar")

        self.assertEqual(1, resultado.returncode, resultado.stdout + resultado.stderr)
        self.assertIn("bloco evolutivo ausente, duplicado ou invertido", resultado.stdout)

    def test_documentar_recusa_acervo_fora_do_repositorio(self) -> None:
        arq_config = self.projeto / "padrao.json"
        configuracao = json.loads(arq_config.read_text(encoding="utf-8"))
        configuracao["acervos"]["canonico"] = "../fora"
        arq_config.write_text(
            json.dumps(configuracao, ensure_ascii=False, indent=4) + "\n",
            encoding="utf-8",
        )

        r = self.cli("documentar")

        self.assertEqual(2, r.returncode, r.stdout + r.stderr)
        self.assertIn("dentro da raiz", r.stderr)
        self.assertFalse((self.projeto.parent / "fora/PROJETO.md").exists())

    def test_documentar_executa_catraca_existente(self) -> None:
        (self.projeto / "docs/legado-sem-frontmatter.md").write_text(
            "# Dívida nova\n", encoding="utf-8"
        )

        r = self.cli("documentar")

        self.assertEqual(1, r.returncode, r.stdout + r.stderr)
        self.assertIn("a dívida aumentou", r.stdout)

    def test_fragmentos_sao_deterministicos_e_perfil_forca_reconstrucao(self) -> None:
        manifesto = self.projeto / "docs/gerado/manifesto-fragmentos-v2.json"
        primeira = self.cli("fragmentos", "gerar")
        bytes_1 = manifesto.read_bytes()
        dados_1 = json.loads(bytes_1)
        segunda = self.cli("fragmentos", "gerar")
        bytes_2 = manifesto.read_bytes()

        self.assertEqual(0, primeira.returncode, primeira.stdout + primeira.stderr)
        self.assertEqual(0, segunda.returncode, segunda.stdout + segunda.stderr)
        self.assertEqual(bytes_1, bytes_2)
        self.assertEqual(64, len(dados_1["assinatura"]))
        self.assertEqual(64, len(dados_1["perfil_fingerprint"]))

        arq_config = self.projeto / "padrao.json"
        configuracao = json.loads(arq_config.read_text(encoding="utf-8"))
        configuracao["rag"]["max_palavras"] = 120
        arq_config.write_text(
            json.dumps(configuracao, ensure_ascii=False, indent=4) + "\n",
            encoding="utf-8",
        )
        defasado = self.cli("fragmentos", "verificar")
        regerado = self.cli("fragmentos", "gerar")
        dados_2 = json.loads(manifesto.read_text(encoding="utf-8"))

        self.assertEqual(1, defasado.returncode, defasado.stdout + defasado.stderr)
        self.assertIn("algoritmo ou do perfil", defasado.stdout)
        self.assertEqual(0, regerado.returncode, regerado.stdout + regerado.stderr)
        self.assertNotEqual(dados_1["perfil_fingerprint"], dados_2["perfil_fingerprint"])

    def test_fragmentos_recusam_limite_nao_inteiro_sem_truncar_perfil(self) -> None:
        arq_config = self.projeto / "padrao.json"
        configuracao = json.loads(arq_config.read_text(encoding="utf-8"))
        configuracao["rag"]["max_palavras"] = 120.5
        arq_config.write_text(
            json.dumps(configuracao, ensure_ascii=False, indent=4) + "\n",
            encoding="utf-8",
        )

        resultado = self.cli("fragmentos", "gerar")

        self.assertEqual(1, resultado.returncode, resultado.stdout + resultado.stderr)
        self.assertIn("precisam ser números inteiros", resultado.stdout)
        self.assertNotIn("Traceback", resultado.stdout + resultado.stderr)

    def test_contexto_json_rele_fontes_e_respeita_orcamento(self) -> None:
        resultado = self.cli(
            "contexto", "--pergunta=documentação do projeto",
            "--perfil=engenharia-leitura", "--max-tokens=96", "--json",
        )

        self.assertEqual(0, resultado.returncode, resultado.stdout + resultado.stderr)
        envelope = json.loads(resultado.stdout)
        self.assertEqual(2, envelope["schema"])
        self.assertEqual("fixture", envelope["projeto"])
        self.assertEqual("confirmado", envelope["frescor"])
        self.assertLessEqual(envelope["tokens_estimados"], 96)
        self.assertTrue(envelope["fontes"])
        self.assertEqual([], envelope["acoes_permitidas"])
        self.assertFalse(envelope["comparacao_sombra"]["migracao_hindsight_liberada"])
        self.assertTrue(any("Hindsight desativado" in a for a in envelope["avisos"]))
        for fonte in envelope["fontes"]:
            rel, ancora = fonte["source_uri"].split("#", 1)
            self.assertTrue((self.projeto / rel).is_file())
            self.assertTrue(ancora)
            self.assertEqual(64, len(fonte["source_sha256"]))

    def test_contexto_atendimento_enxerga_somente_documento_publico_permitido(self) -> None:
        publico = self.projeto / "docs/funcional/FDD-PUBLICO.md"
        publico.write_text(
            "---\nid: FDD-PUBLICO\ntipo: fdd\nprojeto: fixture\n"
            "titulo: Atendimento público\nstatus: verificado\nclassificacao: publico\n---\n\n"
            "# Atendimento público\n\n## Rastreamento\n\nCódigo sabiá identifica a entrega.\n",
            encoding="utf-8",
        )
        interno = self.projeto / "docs/funcional/FDD-INTERNO.md"
        interno.write_text(
            "---\nid: FDD-INTERNO\ntipo: fdd\nprojeto: fixture\n"
            "titulo: Atendimento interno\nstatus: verificado\nclassificacao: interno\n---\n\n"
            "# Atendimento interno\n\n## Segredo\n\nCódigo sabiá é interno.\n",
            encoding="utf-8",
        )
        self.assertEqual(0, self.cli("fragmentos", "gerar").returncode)

        resultado = self.cli(
            "contexto", "--pergunta=código sabiá", "--perfil=atendimento",
            "--produto=produto-a", "--tenant=tenant-a", "--json"
        )
        envelope = json.loads(resultado.stdout)

        self.assertEqual(0, resultado.returncode, resultado.stdout + resultado.stderr)
        self.assertTrue(envelope["fontes"])
        self.assertTrue(all("FDD-PUBLICO" in f["fragment_id"] for f in envelope["fontes"]))
        self.assertEqual([], envelope["codigo"])

    def test_atendimento_exige_escopo_explicito_e_nao_herda_contexto(self) -> None:
        sem_escopo = self.cli(
            "contexto", "--pergunta=projeto", "--perfil=atendimento", "--json"
        )
        parcial = self.cli(
            "contexto", "--pergunta=projeto", "--perfil=atendimento",
            "--produto=produto-a", "--json",
        )

        self.assertEqual(1, sem_escopo.returncode)
        self.assertEqual("", sem_escopo.stdout)
        self.assertIn("exige `produto` e `tenant`", sem_escopo.stderr)
        self.assertEqual(1, parcial.returncode)
        self.assertIn("exige `produto` e `tenant`", parcial.stderr)

    def test_escopo_isola_tenant_produto_e_audiencia_por_match_exato(self) -> None:
        documentos = {
            "FDD-TENANT-A.md": (
                "FDD-TENANT-A", "tenant-a", "atendimento", "Resposta azaleia do tenant A."
            ),
            "FDD-TENANT-B.md": (
                "FDD-TENANT-B", "tenant-b", "atendimento", "Resposta azaleia do tenant B."
            ),
            "FDD-OPERACAO.md": (
                "FDD-OPERACAO", "tenant-a", "operacao-assistida",
                "Resposta azaleia exclusiva da operação."
            ),
        }
        for nome, (id_, tenant, audiencia, corpo) in documentos.items():
            (self.projeto / "docs/funcional" / nome).write_text(
                "---\n"
                f"id: {id_}\ntipo: fdd\nprojeto: fixture\ntitulo: {id_}\n"
                "status: verificado\nclassificacao: publico\n"
                f"audience:\n  - {audiencia}\nprodutos:\n  - produto-a\n"
                f"tenants:\n  - {tenant}\n---\n\n# {id_}\n\n## Resposta\n\n{corpo}\n",
                encoding="utf-8",
            )
        self.assertEqual(0, self.cli("fragmentos", "gerar").returncode)

        resultado = self.cli(
            "contexto", "--pergunta=resposta azaleia", "--perfil=atendimento",
            "--produto=produto-a", "--tenant=tenant-a", "--json",
        )
        outro_produto = self.cli(
            "contexto", "--pergunta=resposta azaleia", "--perfil=atendimento",
            "--produto=produto-b", "--tenant=tenant-a", "--json",
        )
        envelope = json.loads(resultado.stdout)
        fontes = "\n".join(f["source_uri"] for f in envelope["fontes"])

        self.assertEqual(0, resultado.returncode, resultado.stdout + resultado.stderr)
        self.assertIn("FDD-TENANT-A.md", fontes)
        self.assertNotIn("FDD-TENANT-B.md", fontes)
        self.assertNotIn("FDD-OPERACAO.md", fontes)
        self.assertEqual({"produto": "produto-a", "tenant": "tenant-a"}, envelope["escopo"])
        self.assertEqual("confirmada", envelope["cobertura"])
        envelope_outro = json.loads(outro_produto.stdout)
        self.assertEqual("ausente", envelope_outro["cobertura"])
        self.assertEqual([], envelope_outro["fontes"])
        self.assertTrue(any("Cobertura ausente" in aviso for aviso in envelope_outro["avisos"]))

    def test_documento_secreto_nao_entra_no_manifesto_nem_na_consulta(self) -> None:
        secreto = self.projeto / "docs/funcional/FDD-SEGREDO.md"
        secreto.write_text(
            "---\nid: FDD-SEGREDO\ntipo: fdd\nprojeto: fixture\n"
            "titulo: Segredo\nstatus: verificado\nclassificacao: secreto-nao-indexar\n"
            "---\n\n# Segredo\n\n## Conteúdo\n\nFrase ultravioleta confidencial.\n",
            encoding="utf-8",
        )
        legado = self.projeto / "docs/gerado/manifesto-fragmentos-v1.json"
        legado.write_text('{"texto": "Frase ultravioleta confidencial."}\n', encoding="utf-8")

        gerar = self.cli("fragmentos", "gerar")
        manifesto = json.loads((
            self.projeto / "docs/gerado/manifesto-fragmentos-v2.json"
        ).read_text(encoding="utf-8"))
        consulta = self.cli(
            "contexto", "--pergunta=ultravioleta", "--perfil=engenharia-leitura", "--json"
        )

        self.assertEqual(0, gerar.returncode, gerar.stdout + gerar.stderr)
        serializado = json.dumps(manifesto, ensure_ascii=False)
        self.assertNotIn("FDD-SEGREDO", serializado)
        self.assertNotIn("ultravioleta", serializado)
        self.assertFalse(legado.exists(), "manifesto legado não pode preservar corpus secreto")
        envelope = json.loads(consulta.stdout)
        self.assertEqual("ausente", envelope["cobertura"])
        self.assertEqual([], envelope["fontes"])

    def test_politica_de_acesso_invalida_falha_sem_traceback(self) -> None:
        invalido = self.projeto / "docs/funcional/FDD-ACL-INVALIDA.md"
        invalido.write_text(
            "---\nid: FDD-ACL-INVALIDA\ntipo: fdd\nprojeto: fixture\n"
            "titulo: ACL inválida\nstatus: verificado\nclassificacao: publico\n"
            "audience:\n  - administrador-total\n---\n\n# ACL inválida\n",
            encoding="utf-8",
        )

        validar = self.cli("validar")
        fragmentos = self.cli("fragmentos", "gerar")
        gate = self.cli("verificar")

        self.assertEqual(1, validar.returncode, validar.stdout + validar.stderr)
        self.assertIn("audience", validar.stdout)
        self.assertEqual(1, fragmentos.returncode, fragmentos.stdout + fragmentos.stderr)
        self.assertIn("perfil desconhecido", fragmentos.stdout)
        self.assertEqual(1, gate.returncode, gate.stdout + gate.stderr)
        self.assertNotIn("Traceback", gate.stdout + gate.stderr)

    def test_contexto_recusa_manifesto_defasado_sem_poluir_stdout_json(self) -> None:
        projeto = self.projeto / "docs/PROJETO.md"
        projeto.write_text(
            projeto.read_text(encoding="utf-8") + "\nMudança sem regenerar.\n", encoding="utf-8"
        )

        resultado = self.cli(
            "contexto", "--pergunta=projeto", "--perfil=engenharia-leitura", "--json"
        )

        self.assertEqual(1, resultado.returncode, resultado.stdout + resultado.stderr)
        self.assertEqual("", resultado.stdout)
        self.assertIn("manifesto de fragmentos", resultado.stderr)

    def test_contexto_http_recusa_bind_externo(self) -> None:
        resultado = self.cli("contexto", "http", "--host=0.0.0.0", "--porta=0")

        self.assertEqual(1, resultado.returncode, resultado.stdout + resultado.stderr)
        self.assertIn("somente loopback", resultado.stderr)

    def test_adaptadores_sao_deterministicos_e_canary_descobre_cinco_clientes(self) -> None:
        manifesto_path = self.projeto / "docs/gerado/manifesto-adaptadores-v1.json"
        primeiro = manifesto_path.read_bytes()
        regerado = self.cli("adaptadores", "gerar")
        segundo = manifesto_path.read_bytes()

        self.assertEqual(0, regerado.returncode, regerado.stdout + regerado.stderr)
        self.assertEqual(primeiro, segundo)
        manifesto = json.loads(segundo)
        self.assertEqual(
            ["codex", "claude", "cursor", "windsurf", "hermes"],
            manifesto["plataformas"],
        )
        self.assertEqual(["memoria", "contexto", "mcp"], manifesto["gateway"]["comando"])
        self.assertTrue((self.projeto / ".codex/config.toml").is_file())
        self.assertTrue((self.projeto / ".mcp.json").is_file())
        self.assertTrue((self.projeto / ".cursor/mcp.json").is_file())
        self.assertTrue((self.projeto / ".windsurf/rules/memoria-evolutiva.md").is_file())
        self.assertTrue((self.projeto / ".hermes.md").is_file())

        for comando in (
            ["git", "init"],
            ["git", "config", "user.email", "teste@example.invalid"],
            ["git", "config", "user.name", "Teste"],
            ["git", "add", "."],
            ["git", "commit", "-m", "fixture"],
        ):
            git = subprocess.run(
                comando, cwd=self.projeto, capture_output=True, text=True, encoding="utf-8"
            )
            self.assertEqual(0, git.returncode, git.stdout + git.stderr)

        for plataforma in manifesto["plataformas"]:
            resultado = self.cli(
                "adaptadores", "canary", f"--plataforma={plataforma}",
                "--perfil=engenharia-leitura", "--json",
            )
            canary = json.loads(resultado.stdout)
            self.assertEqual(0, resultado.returncode, resultado.stdout + resultado.stderr)
            self.assertTrue(canary["ok"])
            self.assertEqual("fixture", canary["projeto"])
            self.assertEqual("desativado-explicitamente", canary["banco_estado"])
            self.assertEqual("confirmado", canary["frescor"])
            self.assertGreater(canary["fontes_confirmadas"], 0)
            self.assertEqual([], canary["acoes_permitidas"])
        self.assertEqual(0, self.cli("adaptadores").returncode)

        perfil_divergente = self.cli(
            "adaptadores", "canary", "--plataforma=codex",
            "--perfil=engenharia-documentacao", "--json",
        )
        self.assertEqual(1, perfil_divergente.returncode)
        self.assertIn("perfil do canary diverge", perfil_divergente.stdout)

    def test_adaptador_adulterado_bloqueia_gate_e_merge_preserva_outro_mcp(self) -> None:
        claude = self.projeto / ".mcp.json"
        configuracao = json.loads(claude.read_text(encoding="utf-8"))
        configuracao["mcpServers"]["outro-servidor"] = {
            "command": "exemplo", "args": ["--seguro"]
        }
        claude.write_text(json.dumps(configuracao, indent=2) + "\n", encoding="utf-8")

        regerado = self.cli("adaptadores", "gerar")
        preservado = json.loads(claude.read_text(encoding="utf-8"))
        self.assertEqual(0, regerado.returncode, regerado.stdout + regerado.stderr)
        self.assertIn("outro-servidor", preservado["mcpServers"])
        self.assertEqual(0, self.cli("adaptadores", "verificar").returncode)

        cursor = self.projeto / ".cursor/rules/memoria-evolutiva.mdc"
        cursor.write_text(
            cursor.read_text(encoding="utf-8").replace(
                "Gateway read-only", "Gateway read-write"
            ),
            encoding="utf-8",
        )
        verificado = self.cli("adaptadores", "verificar")
        gate = self.cli("verificar")
        self.assertEqual(1, verificado.returncode, verificado.stdout + verificado.stderr)
        self.assertIn("adaptador", verificado.stdout)
        self.assertEqual(1, gate.returncode, gate.stdout + gate.stderr)

    def test_adaptadores_prevalidam_tudo_antes_de_reparar_arquivo(self) -> None:
        agents = self.projeto / "AGENTS.md"
        alterado = agents.read_text(encoding="utf-8").replace(
            "Gateway read-only", "Gateway temporariamente alterado"
        )
        agents.write_text(alterado, encoding="utf-8")
        (self.projeto / ".mcp.json").write_text("{invalido", encoding="utf-8")

        resultado = self.cli("adaptadores", "gerar")

        self.assertEqual(1, resultado.returncode, resultado.stdout + resultado.stderr)
        self.assertIn("não é JSON válido", resultado.stdout)
        self.assertEqual(alterado, agents.read_text(encoding="utf-8"))

    def test_adaptadores_derivam_o_perfil_canary_da_configuracao(self) -> None:
        padrao = self.projeto / "padrao.json"
        configuracao = json.loads(padrao.read_text(encoding="utf-8"))
        configuracao["adaptadores"]["perfil_canary"] = "engenharia-documentacao"
        padrao.write_text(
            json.dumps(configuracao, ensure_ascii=False, indent=4) + "\n",
            encoding="utf-8",
        )

        resultado = self.cli("adaptadores", "gerar")

        self.assertEqual(0, resultado.returncode, resultado.stdout + resultado.stderr)
        for caminho in (
            "AGENTS.md", "CLAUDE.md", ".cursor/rules/memoria-evolutiva.mdc",
            ".windsurf/rules/memoria-evolutiva.md", ".hermes.md",
        ):
            texto = (self.projeto / caminho).read_text(encoding="utf-8")
            self.assertIn("--perfil=engenharia-documentacao", texto)
        manifesto = json.loads(
            (self.projeto / "docs/gerado/manifesto-adaptadores-v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual("engenharia-documentacao", manifesto["perfil_canary"])

    def test_verificador_recusa_manifesto_malformado_sem_traceback(self) -> None:
        manifesto = self.projeto / "docs/gerado/manifesto-adaptadores-v1.json"
        manifesto.write_text('{"schema": 1, "artefatos": null}\n', encoding="utf-8")

        resultado = self.cli("adaptadores", "verificar")

        self.assertEqual(1, resultado.returncode, resultado.stdout + resultado.stderr)
        self.assertIn("manifesto de adaptadores diverge", resultado.stdout)
        self.assertNotIn("Traceback", resultado.stdout + resultado.stderr)

    def test_canary_recusa_projeto_sem_commit_git(self) -> None:
        resultado = self.cli(
            "adaptadores", "canary", "--plataforma=codex",
            "--perfil=engenharia-leitura", "--json",
        )

        payload = json.loads(resultado.stdout)
        self.assertEqual(1, resultado.returncode, resultado.stdout + resultado.stderr)
        self.assertFalse(payload["ok"])
        self.assertIsNone(payload["commit"])
        self.assertTrue(any("commit Git" in falha for falha in payload["falhas"]))

    def test_mcp_resolve_raiz_declarada_fora_do_diretorio_corrente(self) -> None:
        with tempfile.TemporaryDirectory(prefix="cliente-limpo-") as cwd:
            env = {
                "MEMORIA_PROJETO_RAIZ": str(self.projeto),
            }
            ambiente = os.environ.copy()
            ambiente["PYTHONPATH"] = str(REPOSITORIO) + os.pathsep + ambiente.get("PYTHONPATH", "")
            ambiente["PYTHONUTF8"] = "1"
            ambiente.update(env)
            requisicao = {
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {
                    "name": "memoria_contexto",
                    "arguments": {
                        "pergunta": "objetivo", "perfil": "engenharia-leitura"
                    },
                },
            }
            resultado = subprocess.run(
                [sys.executable, "-m", "memoria_evolutiva", "contexto", "mcp"],
                cwd=cwd, env=ambiente, input=json.dumps(requisicao) + "\n",
                capture_output=True, text=True, encoding="utf-8", timeout=120,
            )
        envelope = json.loads(resultado.stdout)["result"]["structuredContent"]
        self.assertEqual(0, resultado.returncode, resultado.stdout + resultado.stderr)
        self.assertEqual("fixture", envelope["projeto"])
        self.assertTrue(envelope["fontes"])

    def test_validar_recusa_configuracao_insegura_do_contexto(self) -> None:
        caminho = self.projeto / "padrao.json"
        configuracao = json.loads(caminho.read_text(encoding="utf-8"))
        configuracao["contexto"]["http_host"] = "0.0.0.0"
        configuracao["contexto"]["max_tokens"] = True
        caminho.write_text(
            json.dumps(configuracao, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        resultado = self.cli("validar")

        self.assertEqual(1, resultado.returncode, resultado.stdout + resultado.stderr)
        self.assertIn("contexto.max_tokens", resultado.stdout)
        self.assertIn("somente loopback", resultado.stdout)

    def test_validar_recusa_relaxamento_invalido_da_catraca_rag(self) -> None:
        caminho = self.projeto / "padrao.json"
        configuracao = json.loads(caminho.read_text(encoding="utf-8"))
        configuracao["avaliacao"]["regressao_maxima"] = 1.5
        configuracao["avaliacao"]["min_usos_promocao"] = True
        caminho.write_text(
            json.dumps(configuracao, ensure_ascii=False, indent=4) + "\n", encoding="utf-8"
        )

        resultado = self.cli("validar")

        self.assertEqual(1, resultado.returncode, resultado.stdout + resultado.stderr)
        self.assertIn("avaliacao.regressao_maxima", resultado.stdout)
        self.assertIn("avaliacao.min_usos_promocao", resultado.stdout)

    def test_avaliacao_recusa_redirecionar_derivado_para_documento_canonico(self) -> None:
        configuracao_path = self.projeto / "padrao.json"
        configuracao = json.loads(configuracao_path.read_text(encoding="utf-8"))
        configuracao["avaliacao"]["relatorio"] = "docs/PROJETO.md"
        configuracao_path.write_text(
            json.dumps(configuracao, ensure_ascii=False, indent=4) + "\n", encoding="utf-8"
        )
        canonico = self.projeto / "docs/PROJETO.md"
        antes = canonico.read_bytes()

        resultado = self.cli("avaliar", "gerar", "--json")

        self.assertEqual(1, resultado.returncode, resultado.stdout + resultado.stderr)
        self.assertIn("avaliacao.relatorio", resultado.stdout)
        self.assertEqual(antes, canonico.read_bytes())

    def test_fragmentos_especiais_ignoram_codigo_cercado_e_preservam_ancoras(self) -> None:
        (self.projeto / "docs/ABERTO.md").write_text(
            "---\nid: ABERTO\ntipo: estado\nprojeto: fixture\n"
            "titulo: Aberto\nstatus: rascunho\n---\n\n# Aberto\n\n"
            "```markdown\n### ABERTO-FAKE — exemplo\n```\n\n"
            "<!--\n### ABERTO-COMENTADO — não é item\n-->\n\n"
            "## Em aberto\n\n### ABERTO-0001 — Falha concreta\n\n"
            "**impacto:** teste determinístico\n",
            encoding="utf-8",
        )
        (self.projeto / "docs/GLOSSARIO.md").write_text(
            "---\nid: GLOSSARIO\ntipo: entrada\nprojeto: fixture\n"
            "titulo: Glossário\nstatus: verificado\n---\n\n# Glossário\n\n"
            "## Fiscal\n\n| Termo | Significado |\n|---|---|\n"
            "| **Competência** | Período de apuração. |\n",
            encoding="utf-8",
        )
        cronologias = list((self.projeto / "docs/cronologia").glob("*.md"))
        self.assertEqual(1, len(cronologias), cronologias)
        cronologia = cronologias[0]
        cronologia.write_bytes(
            (
                "---\nid: CRONOLOGIA-2026-08\ntipo: cronologia\nprojeto: fixture\n"
                "titulo: Cronologia\nstatus: verificado\n---\n\n# Cronologia\n\n"
                "## 2026-08-13 — Evolução\n\nManifesto determinístico criado.\n"
            ).replace("\n", "\r\n").encode("utf-8")
        )
        self.assertIn("id: CRONOLOGIA-2026-08", cronologia.read_text(encoding="utf-8"))

        gerado = self.cli("fragmentos", "gerar")
        dados = json.loads((
            self.projeto / "docs/gerado/manifesto-fragmentos-v2.json"
        ).read_text(encoding="utf-8"))
        ids = {item["fragment_id"] for item in dados["fragmentos"]}
        cronologia_rel = str(cronologia.relative_to(self.projeto)).replace("\\", "/")

        self.assertEqual(0, gerado.returncode, gerado.stdout + gerado.stderr)
        self.assertTrue(any(":item:aberto-0001:parte-" in id_ for id_ in ids))
        self.assertFalse(any("aberto-fake" in id_ for id_ in ids))
        self.assertFalse(any("aberto-comentado" in id_ for id_ in ids))
        self.assertTrue(any(":termo:competência" in id_ for id_ in ids))
        self.assertEqual(
            "CRONOLOGIA-2026-08", dados["documentos"][cronologia_rel]["doc_id"]
        )
        self.assertTrue(
            any(":entrada:2026-08-13-evolução" in id_ for id_ in ids), ids
        )
        for item in dados["fragmentos"]:
            caminho, separador, ancora = item["source_uri"].partition("#")
            self.assertEqual("#", separador)
            self.assertTrue(ancora)
            self.assertTrue((self.projeto / caminho).is_file())
            self.assertEqual(64, len(item["source_sha256"]))
            self.assertEqual(64, len(item["conteudo_sha256"]))
            self.assertTrue(item["texto"].startswith("# "))

    def test_documentar_gera_aberto_no_contrato_fragmentavel(self) -> None:
        documentado = self.cli("documentar")
        manifesto = json.loads((
            self.projeto / "docs/gerado/manifesto-fragmentos-v2.json"
        ).read_text(encoding="utf-8"))
        aberto = (self.projeto / "docs/ABERTO.md").read_text(encoding="utf-8")
        itens = [
            fragmento for fragmento in manifesto["fragmentos"]
            if fragmento["doc_id"] == "ABERTO"
            and ":item:aberto-auto-" in fragmento["fragment_id"]
        ]

        self.assertEqual(0, documentado.returncode, documentado.stdout + documentado.stderr)
        self.assertIn("### ABERTO-AUTO-0001", aberto)
        self.assertTrue(itens, manifesto["fragmentos"])

        id_antes = itens[0]["fragment_id"]
        aberto_path = self.projeto / "docs/ABERTO.md"
        aberto_path.write_text(
            aberto.replace("— Determinar", "— Esclarecer", 1), encoding="utf-8"
        )
        self.assertEqual(0, self.cli("fragmentos", "gerar").returncode)
        atualizado = json.loads((
            self.projeto / "docs/gerado/manifesto-fragmentos-v2.json"
        ).read_text(encoding="utf-8"))
        ids_atualizados = {f["fragment_id"] for f in atualizado["fragmentos"]}
        self.assertIn(id_antes, ids_atualizados)

    def test_fragmentos_mudanca_minima_e_remocao_sem_residuo(self) -> None:
        documento = self.projeto / "docs/funcional/FDD-9000.md"
        documento.write_text(
            "---\nid: FDD-9000\ntipo: fdd\nprojeto: fixture\n"
            "titulo: Teste\nstatus: verificado\n---\n\n# Teste\n\n"
            "## Primeira\n\nConteúdo original.\n\n## Segunda\n\nConteúdo estável.\n",
            encoding="utf-8",
        )
        self.assertEqual(0, self.cli("fragmentos", "gerar").returncode)
        caminho = self.projeto / "docs/gerado/manifesto-fragmentos-v2.json"
        antes = json.loads(caminho.read_text(encoding="utf-8"))
        fragmentos_antes = {
            f["fragment_id"]: f for f in antes["fragmentos"] if f["doc_id"] == "FDD-9000"
        }
        self.assertFalse(any(":secao:teste:parte-" in id_ for id_ in fragmentos_antes))

        documento.write_text(
            documento.read_text(encoding="utf-8").replace(
                "Conteúdo original.", "Conteúdo original alterado."
            ),
            encoding="utf-8",
        )
        self.assertEqual(0, self.cli("fragmentos", "gerar").returncode)
        depois = json.loads(caminho.read_text(encoding="utf-8"))
        fragmentos_depois = {
            f["fragment_id"]: f for f in depois["fragmentos"] if f["doc_id"] == "FDD-9000"
        }
        segunda = next(id_ for id_ in fragmentos_antes if ":secao:segunda:" in id_)
        primeira = next(id_ for id_ in fragmentos_antes if ":secao:primeira:" in id_)
        self.assertEqual(set(fragmentos_antes), set(fragmentos_depois))
        self.assertEqual(
            fragmentos_antes[segunda]["conteudo_sha256"],
            fragmentos_depois[segunda]["conteudo_sha256"],
        )
        self.assertNotEqual(
            fragmentos_antes[primeira]["conteudo_sha256"],
            fragmentos_depois[primeira]["conteudo_sha256"],
        )

        documento.unlink()
        self.assertEqual(0, self.cli("fragmentos", "gerar").returncode)
        final = json.loads(caminho.read_text(encoding="utf-8"))
        self.assertNotIn("docs/funcional/FDD-9000.md", final["documentos"])
        self.assertFalse(any(f["doc_id"] == "FDD-9000" for f in final["fragmentos"]))

    def test_skill_nasce_pronta_com_protocolo_autonomo(self) -> None:
        r = self.cli("skill")

        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        skill = (self.projeto / "skill-memoria-evolutiva/SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Não peça aprovação documental", skill)
        self.assertIn("cobertura-codigo.md", skill)
        metadata = self.projeto / "skill-memoria-evolutiva/agents/openai.yaml"
        self.assertTrue(metadata.is_file())
        self.assertIn("$memoria-evolutiva-projeto", metadata.read_text(encoding="utf-8"))
        self.assertNotIn("Falta a SKILL.md", r.stdout)
        conferir = self.cli("skill", "--conferir")
        self.assertEqual(0, conferir.returncode, conferir.stdout + conferir.stderr)

    def test_skill_desatualizada_ou_adulterada_falha_duro(self) -> None:
        gerada = self.cli("skill")
        self.assertEqual(0, gerada.returncode, gerada.stdout + gerada.stderr)
        runbook = self.projeto / "docs/runbooks/sessao.md"
        runbook.write_text(
            runbook.read_text(encoding="utf-8") + "\nRegra nova.\n", encoding="utf-8"
        )

        fonte_velha = self.cli("skill", "--conferir")
        gate_completo = self.cli("verificar")
        self.assertEqual(1, fonte_velha.returncode, fonte_velha.stdout + fonte_velha.stderr)
        self.assertIn("FALHA", fonte_velha.stdout)
        self.assertIn("runbooks de origem mudaram", fonte_velha.stdout)
        self.assertEqual(1, gate_completo.returncode, gate_completo.stdout + gate_completo.stderr)
        self.assertIn("a skill derivada não representa", gate_completo.stdout)

        regerada = self.cli("skill")
        self.assertEqual(0, regerada.returncode, regerada.stdout + regerada.stderr)
        skill = self.projeto / "skill-memoria-evolutiva/SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8") + "\nInstrução intrusa.\n", encoding="utf-8")
        adulterada = self.cli("skill", "--conferir")
        self.assertEqual(1, adulterada.returncode, adulterada.stdout + adulterada.stderr)
        self.assertIn("artefato alterado", adulterada.stdout)

    def test_regenerar_skill_remove_artefato_obsoleto_do_kit(self) -> None:
        gerada = self.cli("skill")
        self.assertEqual(0, gerada.returncode, gerada.stdout + gerada.stderr)
        obsoleto = self.projeto / "skill-memoria-evolutiva/assets/kit/obsoleto.py"
        obsoleto.write_text("# removido do pacote-fonte\n", encoding="utf-8")

        regerada = self.cli("skill")
        conferir = self.cli("skill", "--conferir")

        self.assertEqual(0, regerada.returncode, regerada.stdout + regerada.stderr)
        self.assertFalse(obsoleto.exists())
        self.assertEqual(0, conferir.returncode, conferir.stdout + conferir.stderr)

    def test_skill_nao_invalida_mapa_quando_raiz_do_codigo_e_projeto(self) -> None:
        arq_config = self.projeto / "padrao.json"
        configuracao = json.loads(arq_config.read_text(encoding="utf-8"))
        configuracao["gerado"]["raiz"] = "."
        arq_config.write_text(
            json.dumps(configuracao, ensure_ascii=False, indent=4) + "\n",
            encoding="utf-8",
        )
        gerado = self.cli("gerar")
        self.assertEqual(0, gerado.returncode, gerado.stdout + gerado.stderr)

        skill = self.cli("skill")
        verificar = self.cli("verificar")

        self.assertEqual(0, skill.returncode, skill.stdout + skill.stderr)
        self.assertEqual(0, verificar.returncode, verificar.stdout + verificar.stderr)

    def test_skill_recusa_saida_sobreposta_ao_projeto(self) -> None:
        resultado = self.cli("skill", "--saida=.")

        self.assertEqual(2, resultado.returncode, resultado.stdout + resultado.stderr)
        self.assertIn("saída insegura", resultado.stdout)

    def test_skill_recusa_geracao_sem_runbook_obrigatorio(self) -> None:
        (self.projeto / "docs/runbooks/documentacao-autonoma.md").unlink()

        resultado = self.cli("skill")

        self.assertEqual(1, resultado.returncode, resultado.stdout + resultado.stderr)
        self.assertIn("faltam runbooks obrigatórios", resultado.stdout)
        self.assertFalse((self.projeto / "docs/.skill-gerada.json").exists())

    def test_skill_marcador_corrompido_falha_sem_traceback(self) -> None:
        marcador = self.projeto / "docs/.skill-gerada.json"
        marcador.write_text("{invalido", encoding="utf-8")

        resultado = self.cli("skill", "--conferir")

        self.assertEqual(1, resultado.returncode, resultado.stdout + resultado.stderr)
        self.assertIn("marcador da skill inválido", resultado.stdout)
        self.assertNotIn("Traceback", resultado.stdout + resultado.stderr)


class HashDoConteudoTest(unittest.TestCase):
    def test_fragmentacao_reconhece_titulos_setext(self) -> None:
        cabecalhos = _cabecalhos(
            "Título (teste)\n==============\n\n[Seção](https://exemplo.test)\n------\n\nCorpo.\n"
        )

        self.assertEqual(["título-teste", "seção"], [c["ancora"] for c in cabecalhos])
        self.assertEqual([1, 2], [c["nivel"] for c in cabecalhos])
        self.assertEqual([2, 5], [c["inicio"] for c in cabecalhos])

    def test_fragmentacao_nunca_corta_bloco_de_codigo_ou_tabela(self) -> None:
        codigo = "```python\n" + " ".join(f"valor{i}" for i in range(20)) + "\n```"
        tabela = "| Coluna | Valor |\n|---|---|\n| A | " + " ".join(
            f"dado{i}" for i in range(20)
        ) + " |"
        tabela_sem_bordas = "Coluna | Valor\n---|---\nA | " + " ".join(
            f"item{i}" for i in range(20)
        )
        codigo_indentado = "    " + " ".join(f"linha{i}" for i in range(20))

        partes_codigo = _partir_texto("Código", codigo, maximo=8, minimo=0)
        partes_tabela = _partir_texto("Tabela", tabela, maximo=8, minimo=0)
        partes_tabela_sem_bordas = _partir_texto(
            "Tabela", tabela_sem_bordas, maximo=8, minimo=0
        )
        partes_codigo_indentado = _partir_texto(
            "Código", codigo_indentado, maximo=8, minimo=0
        )

        self.assertEqual(1, len(partes_codigo))
        self.assertIn(codigo, partes_codigo[0])
        self.assertEqual(1, len(partes_tabela))
        self.assertIn(tabela, partes_tabela[0])
        self.assertEqual(1, len(partes_tabela_sem_bordas))
        self.assertIn(tabela_sem_bordas, partes_tabela_sem_bordas[0])
        self.assertEqual(1, len(partes_codigo_indentado))
        self.assertIn(codigo_indentado, partes_codigo_indentado[0])

    def test_consulta_normal_exclui_fragmento_superado_sem_apagar_historico(self) -> None:
        vigente = {"fragment_id": "A", "doc_status": "verificado"}
        superado = {"fragment_id": "B", "doc_status": "superado"}
        manifesto = {"fragmentos": [vigente, superado]}

        self.assertEqual([vigente], consultaveis(manifesto))
        self.assertEqual([vigente, superado], manifesto["fragmentos"])

    def test_mudanca_de_ambiente_no_corpo_altera_hash(self) -> None:
        producao = "# Corpo\nExecuta em `producao`.\n"
        homologacao = "# Corpo\nExecuta em `homologacao`.\n"

        self.assertNotEqual(hash_do_conteudo(producao), hash_do_conteudo(homologacao))

    def test_carimbo_exato_do_gerador_nao_altera_hash(self) -> None:
        antigo = "> Gerado por `memoria gerar` em `abc1234`.\n"
        novo = "> Gerado por `memoria gerar` em `def5678`.\n"

        # O estreitamento da regex não pode invalidar marcadores já gravados para a
        # linha que o algoritmo PHP normalizava corretamente.
        normalizado_legado = re.sub(r"em `[^`]*`\.$", "em `X`.", antigo, flags=re.M)
        hash_legado = hashlib.sha256(normalizado_legado.encode("utf-8")).hexdigest()[:16]

        self.assertEqual(hash_do_conteudo(antigo), hash_do_conteudo(novo))
        self.assertEqual(hash_legado, hash_do_conteudo(antigo))


class SegurancaMemoriaTest(unittest.TestCase):
    def test_redaction_deterministica_cobre_todas_as_regras_sem_reter_valores(self) -> None:
        original = (
            "-----BEGIN PRIVATE KEY-----\nABCDEF123456\n-----END PRIVATE KEY-----\n"
            "URL=https://usuario:senha-secreta@exemplo.invalid/api\n"
            "Authorization: Bearer abcdefghijklmnop\n"
            "client_secret=segredo-super-seguro\n"
            "Contato: pessoa@example.com\n"
            "CPF: 123.456.789-00\n"
        )
        with mock.patch.object(
            seguranca, "_cfg", return_value={"redaction_antes_retain": True}
        ):
            primeiro, auditoria_1 = seguranca.redigir(original)
            segundo, auditoria_2 = seguranca.redigir(original)

        self.assertEqual(primeiro, segundo)
        self.assertEqual(auditoria_1, auditoria_2)
        for segredo in (
            "ABCDEF123456", "usuario", "senha-secreta", "abcdefghijklmnop",
            "segredo-super-seguro", "pessoa@example.com", "123.456.789-00",
        ):
            self.assertNotIn(segredo, primeiro)
        self.assertEqual(6, auditoria_1["ocorrencias"])
        self.assertEqual(64, len(auditoria_1["conteudo_sha256"]))

    def test_redaction_nao_confunde_hash_com_cpf_ou_cnpj(self) -> None:
        digest = "10499995858cdb36f23f733434d2fdeaeacd6818d8ea1e17192d51b28f3abda0"
        with mock.patch.object(
            seguranca, "_cfg", return_value={"redaction_antes_retain": True}
        ):
            redigido, auditoria = seguranca.redigir(f"perfil: {digest}")

        self.assertEqual(f"perfil: {digest}", redigido)
        self.assertEqual(0, auditoria["ocorrencias"])

    def test_executor_retry_e_timeout_tem_limites_deterministicos(self) -> None:
        with self.assertRaises(executor.ExecutorEtapaErro) as falha:
            executor._rodar_com_retry(
                [sys.executable, "-c", "raise SystemExit(9)"],
                REPOSITORIO, time.monotonic() + 5, max_tentativas=2, backoff=0,
            )
        self.assertEqual(2, falha.exception.resultado["tentativas"])
        self.assertEqual(9, falha.exception.resultado["exit_code"])

        with self.assertRaises(executor.ExecutorTimeout):
            executor._rodar_com_retry(
                [sys.executable, "-c", "import time; time.sleep(2)"],
                REPOSITORIO, time.monotonic() + 0.1, max_tentativas=1, backoff=0,
            )
        with self.assertRaises(executor.ExecutorTimeout):
            executor._git_ate(REPOSITORIO, time.monotonic() - 1, "status")


class BancosLocaisTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="teste-bancos-")
        self.projeto = Path(self._tmp.name) / "projeto"
        (self.projeto / "src").mkdir(parents=True)
        (self.projeto / "src/app.py").write_text("def executar():\n    return 1\n", encoding="utf-8")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPOSITORIO) + os.pathsep + env.get("PYTHONPATH", "")
        env["PYTHONUTF8"] = "1"
        self.env = env
        instalado = self.cli(
            "instalar", "--projeto=banco-fixture", "--codigo=src", "--sem-bancos"
        )
        self.assertEqual(0, instalado.returncode, instalado.stdout + instalado.stderr)

        self.requisicoes: list[tuple[str, dict]] = []
        requisicoes = self.requisicoes
        persistido: dict[str, str] = {}
        self.estado_hindsight = {"memory_unit_count": 1}
        estado_hindsight = self.estado_hindsight
        self.texto_recall = "memória encontrada"
        teste = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802 - contrato de BaseHTTPRequestHandler
                tamanho = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(tamanho) or b"{}")
                requisicoes.append((self.path, payload))
                if not self.path.endswith("/recall"):
                    for item in payload["items"]:
                        persistido[item["document_id"]] = item["content"]
                corpo = (
                    {"results": [{
                        "text": teste.texto_recall,
                        "metadata": {"source_uri": "docs/PROJETO.md"},
                        "document_id": "memoria-evolutiva:banco-fixture:docs/PROJETO.md",
                    }]}
                    if self.path.endswith("/recall") else {
                        "success": True,
                        "items": len(payload.get("items", [])),
                        **({"operation_id": payload["operation_id"]}
                           if payload.get("async") else {}),
                    }
                )
                dados = json.dumps(corpo).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(dados)))
                self.end_headers()
                self.wfile.write(dados)

            def do_GET(self) -> None:  # noqa: N802 - contrato de BaseHTTPRequestHandler
                from urllib.parse import unquote
                if "/operations/" in self.path:
                    dados = b'{"status": "completed"}'
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(dados)))
                    self.end_headers()
                    self.wfile.write(dados)
                    return
                doc_id = unquote(self.path.rsplit("/", 1)[-1])
                if doc_id not in persistido:
                    self.send_response(404)
                    self.end_headers()
                    return
                dados = json.dumps({
                    "id": doc_id,
                    "original_text": persistido.get(doc_id),
                    "memory_unit_count": estado_hindsight["memory_unit_count"],
                    "content_hash": "fake",
                }).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(dados)))
                self.end_headers()
                self.wfile.write(dados)

            def do_DELETE(self) -> None:  # noqa: N802 - contrato de BaseHTTPRequestHandler
                from urllib.parse import unquote
                persistido.pop(unquote(self.path.rsplit("/", 1)[-1]), None)
                dados = b'{"success": true}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(dados)))
                self.end_headers()
                self.wfile.write(dados)

            def log_message(self, format: str, *args: object) -> None:
                return

        self.servidor = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.servidor.serve_forever, daemon=True)
        self.thread.start()

        falso = self.projeto / "fake_graphify.py"
        falso.write_text(
            "import json, sys\n"
            "from pathlib import Path\n"
            "if sys.argv[1] == '--version':\n"
            "    versao = Path('.fake_graphify_version')\n"
            "    print(versao.read_text().strip() if versao.exists() else 'fake-graphify 1.0')\n"
            "elif sys.argv[1] in ('extract', 'update'):\n"
            "    if Path('.fake_graphify_fail').exists():\n"
            "        print('Nothing to update or rebuild failed - check output above')\n"
            "        raise SystemExit(0)\n"
            "    out = Path('graphify-out'); out.mkdir(exist_ok=True)\n"
            "    fontes = ['src/app.py', 'fake_graphify.py']\n"
            "    quantidade = 2 if Path('.fake_graphify_shrink').exists() else 10\n"
            "    nodes = [{'id': f'n{i}', 'name': 'executar' if i == 0 else f'no{i}', "
            "'source_file': fontes[i % 2], 'start_line': 1} for i in range(quantidade)]\n"
            "    (out / 'graph.json').write_text(json.dumps({'nodes': nodes, 'links': []}), encoding='utf-8')\n"
            "    (out / 'GRAPH_REPORT.md').write_text('# Grafo\\n', encoding='utf-8')\n"
            "elif sys.argv[1] == 'query':\n"
            "    print('executar -> retorno')\n"
            "else:\n"
            "    raise SystemExit(2)\n",
            encoding="utf-8",
        )
        cfg_path = self.projeto / "padrao.json"
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        cfg["acervos"]["indice"] = "externo"
        cfg["memoria"].update({
            "ativo": True,
            "obrigatorio": True,
            "ferramenta": "hindsight",
            "endpoint": f"http://127.0.0.1:{self.servidor.server_port}",
            "banco": "banco-fixture",
            "marcador": "docs/.hindsight-indexado.json",
        })
        cfg["grafo"].update({
            "ativo": True,
            "obrigatorio": True,
            "ferramenta": "graphify",
            "comando": [sys.executable, str(falso)],
            "arquivo": "graphify-out/graph.json",
            "marcador": ".memoria/bancos/graphify.json",
        })
        cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.servidor.shutdown()
        self.servidor.server_close()
        self.thread.join(timeout=5)
        self._tmp.cleanup()

    def cli(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "memoria_evolutiva", *args],
            cwd=self.projeto, env=self.env, capture_output=True, text=True,
            encoding="utf-8", timeout=120,
        )

    def test_sincroniza_valida_e_consulta_os_dois_bancos(self) -> None:
        sincronizar = self.cli("bancos", "sincronizar")
        self.assertEqual(0, sincronizar.returncode, sincronizar.stdout + sincronizar.stderr)
        self.assertTrue((self.projeto / "docs/.hindsight-indexado.json").is_file())
        self.assertTrue((self.projeto / "graphify-out/graph.json").is_file())
        self.assertTrue((self.projeto / ".memoria/bancos/graphify.json").is_file())

        caminho, payload = self.requisicoes[0]
        self.assertEqual("/v1/default/banks/banco-fixture/memories", caminho)
        self.assertEqual("replace", payload["items"][0]["update_mode"])
        self.assertTrue(payload["items"][0]["document_id"].startswith(
            "memoria-evolutiva:banco-fixture:docs/"
        ))
        self.assertIn("source_uri", payload["items"][0]["metadata"])
        projeto_item = next(
            item for _, req in self.requisicoes for item in req.get("items", [])
            if item["metadata"].get("source_uri") == "docs/PROJETO.md"
        )
        self.assertEqual("verificado", projeto_item["metadata"]["doc_status"])
        self.assertIn("vigente", projeto_item["tags"])
        consulta = self.cli("bancos", "consultar", "--pergunta=como executar?")
        self.assertEqual(0, consulta.returncode, consulta.stdout + consulta.stderr)
        self.assertEqual("all_strict", self.requisicoes[-1][1]["tags_match"])
        self.assertIn("vigente", self.requisicoes[-1][1]["tags"])
        self.assertIn("memória encontrada", consulta.stdout)
        self.assertIn("executar -> retorno", consulta.stdout)

    def test_sinal_semantico_generico_nao_expulsa_match_literal_exato(self) -> None:
        sincronizar = self.cli("bancos", "sincronizar")
        self.texto_recall = (self.projeto / "docs/PROJETO.md").read_text(encoding="utf-8")
        contexto_cli = self.cli(
            "contexto",
            "--pergunta=como a execução por cron isola a documentação com checkpoints e worktree?",
            "--perfil=automacao-codigo",
            "--json",
        )

        self.assertEqual(0, sincronizar.returncode, sincronizar.stdout + sincronizar.stderr)
        self.assertEqual(0, contexto_cli.returncode, contexto_cli.stdout + contexto_cli.stderr)
        envelope = json.loads(contexto_cli.stdout)
        self.assertTrue(envelope["fontes"])
        self.assertTrue(envelope["fontes"][0]["source_uri"].startswith(
            "docs/runbooks/documentacao-autonoma.md#execução-por-cron"
        ))
        self.assertIn("literal", envelope["fontes"][0]["estrategias"])

    def test_retain_redige_dados_e_exclui_documento_secreto_antes_do_envio(self) -> None:
        (self.projeto / "docs/funcional/FDD-DADOS.md").write_text(
            "---\nid: FDD-DADOS\ntipo: fdd\nprojeto: banco-fixture\n"
            "titulo: Dados operacionais\nstatus: verificado\nclassificacao: restrito\n"
            "produtos:\n  - produto-a\ntenants:\n  - tenant-a\n---\n\n"
            "# Dados\n\n## Exemplo\n\nContato joao@example.com, CPF 123.456.789-00 "
            "e api_key=abc123456789.\n",
            encoding="utf-8",
        )
        (self.projeto / "docs/funcional/FDD-NAO-INDEXAR.md").write_text(
            "---\nid: FDD-NAO-INDEXAR\ntipo: fdd\nprojeto: banco-fixture\n"
            "titulo: Nunca indexar\nstatus: verificado\n"
            "classificacao: secreto-nao-indexar\n---\n\n"
            "# Nunca indexar\n\n## Segredo\n\nSENTINELA-NAO-PODE-SAIR.\n",
            encoding="utf-8",
        )

        sincronizar = self.cli("bancos", "sincronizar")
        itens = [item for _, req in self.requisicoes for item in req.get("items", [])]
        enviado = "\n".join(item["content"] for item in itens)
        dados = next(
            item for item in itens
            if item["metadata"].get("source_uri") == "docs/funcional/FDD-DADOS.md"
        )
        marcador = json.loads((
            self.projeto / "docs/.hindsight-indexado.json"
        ).read_text(encoding="utf-8"))

        self.assertEqual(0, sincronizar.returncode, sincronizar.stdout + sincronizar.stderr)
        self.assertNotIn("joao@example.com", enviado)
        self.assertNotIn("123.456.789-00", enviado)
        self.assertNotIn("abc123456789", enviado)
        self.assertNotIn("SENTINELA-NAO-PODE-SAIR", enviado)
        self.assertIn("[DADO-REMOVIDO:email]", dados["content"])
        self.assertIn("[DADO-REMOVIDO:cpf-cnpj]", dados["content"])
        self.assertIn("[DADO-REMOVIDO:segredo-configuracao]", dados["content"])
        self.assertEqual("restrito", dados["metadata"]["classificacao"])
        self.assertEqual(["produto-a"], json.loads(dados["metadata"]["produtos"]))
        self.assertEqual(["tenant-a"], json.loads(dados["metadata"]["tenants"]))
        self.assertGreaterEqual(int(dados["metadata"]["redaction_ocorrencias"]), 3)
        self.assertTrue(all(
            isinstance(valor, str) for valor in dados["metadata"].values()
        ), "a API oficial do Hindsight aceita somente metadata textual")
        prova = marcador["prova_do_provedor"]
        self.assertEqual("redaction-deterministica-v1", prova["redaction"]["algoritmo"])
        self.assertGreaterEqual(prova["redaction"]["ocorrencias"], 3)
        self.assertEqual(64, len(prova["seguranca_fingerprint"]))

    def test_canary_confirma_bank_ativo_perfil_e_frescor(self) -> None:
        sincronizar = self.cli("bancos", "sincronizar")
        adaptadores = self.cli("adaptadores", "gerar")
        for comando in (
            ["git", "init"],
            ["git", "config", "user.email", "teste@example.invalid"],
            ["git", "config", "user.name", "Teste"],
            ["git", "add", "."],
            ["git", "commit", "-m", "fixture"],
        ):
            git = subprocess.run(
                comando, cwd=self.projeto, capture_output=True, text=True, encoding="utf-8"
            )
            self.assertEqual(0, git.returncode, git.stdout + git.stderr)
        canary = self.cli(
            "adaptadores", "canary", "--plataforma=hermes",
            "--perfil=engenharia-leitura", "--json",
        )

        self.assertEqual(0, sincronizar.returncode, sincronizar.stdout + sincronizar.stderr)
        self.assertEqual(0, adaptadores.returncode, adaptadores.stdout + adaptadores.stderr)
        self.assertEqual(0, canary.returncode, canary.stdout + canary.stderr)
        payload = json.loads(canary.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual("banco-fixture", payload["projeto"])
        self.assertEqual("banco-fixture", payload["banco"])
        self.assertEqual("confirmado", payload["banco_estado"])
        self.assertEqual("engenharia-leitura", payload["perfil"])
        self.assertEqual("confirmado", payload["frescor"])
        self.assertGreater(payload["fontes_confirmadas"], 0)
        self.assertRegex(payload["commit"], r"^[0-9a-f]{40}$")

    def test_contexto_cli_mcp_e_http_devolvem_o_mesmo_envelope(self) -> None:
        sincronizar = self.cli("bancos", "sincronizar")
        self.assertEqual(0, sincronizar.returncode, sincronizar.stdout + sincronizar.stderr)

        cli = self.cli(
            "contexto", "--pergunta=como executar", "--perfil=engenharia-leitura", "--json"
        )
        self.assertEqual(0, cli.returncode, cli.stdout + cli.stderr)
        esperado = json.loads(cli.stdout)
        self.assertIn("semantica", esperado["estrategias"])
        self.assertIn("estrutural", esperado["estrategias"])
        self.assertTrue(esperado["fontes"])
        self.assertTrue(esperado["codigo"])
        self.assertGreater(esperado["comparacao_sombra"]["documentos_semanticos"], 0)

        requisicao_mcp = {
            "jsonrpc": "2.0", "id": 7, "method": "tools/call",
            "params": {
                "name": "memoria_contexto",
                "arguments": {
                    "pergunta": "como executar", "perfil": "engenharia-leitura"
                },
            },
        }
        mcp = subprocess.run(
            [sys.executable, "-m", "memoria_evolutiva", "contexto", "mcp"],
            cwd=self.projeto, env=self.env, input=json.dumps(requisicao_mcp) + "\n",
            capture_output=True, text=True, encoding="utf-8", timeout=120,
        )
        self.assertEqual(0, mcp.returncode, mcp.stdout + mcp.stderr)
        resposta_mcp = json.loads(mcp.stdout)
        self.assertEqual(esperado, resposta_mcp["result"]["structuredContent"])
        self.assertFalse(resposta_mcp["result"]["isError"])

        invalida = dict(requisicao_mcp)
        invalida["params"] = {
            "name": "memoria_contexto",
            "arguments": {"pergunta": {"objeto": True}, "perfil": "engenharia-leitura"},
        }
        mcp_invalido = subprocess.run(
            [sys.executable, "-m", "memoria_evolutiva", "contexto", "mcp"],
            cwd=self.projeto, env=self.env, input=json.dumps(invalida) + "\n",
            capture_output=True, text=True, encoding="utf-8", timeout=120,
        )
        self.assertTrue(json.loads(mcp_invalido.stdout)["result"]["isError"])

        sem_perfil = dict(requisicao_mcp)
        sem_perfil["params"] = {
            "name": "memoria_contexto", "arguments": {"pergunta": "como executar"}
        }
        mcp_sem_perfil = subprocess.run(
            [sys.executable, "-m", "memoria_evolutiva", "contexto", "mcp"],
            cwd=self.projeto, env=self.env, input=json.dumps(sem_perfil) + "\n",
            capture_output=True, text=True, encoding="utf-8", timeout=120,
        )
        self.assertTrue(json.loads(mcp_sem_perfil.stdout)["result"]["isError"])

        contrato_invalido = dict(requisicao_mcp)
        contrato_invalido["params"] = {
            "name": "memoria_contexto",
            "arguments": {
                "pergunta": "como executar", "perfil": "engenharia-leitura",
                "max_tokens": None, "campo_inventado": True,
            },
        }
        mcp_contrato_invalido = subprocess.run(
            [sys.executable, "-m", "memoria_evolutiva", "contexto", "mcp"],
            cwd=self.projeto, env=self.env, input=json.dumps(contrato_invalido) + "\n",
            capture_output=True, text=True, encoding="utf-8", timeout=120,
        )
        self.assertTrue(json.loads(mcp_contrato_invalido.stdout)["result"]["isError"])
        self.assertIn("campo_inventado", mcp_contrato_invalido.stdout)

        max_tokens_nulo = dict(requisicao_mcp)
        max_tokens_nulo["params"] = {
            "name": "memoria_contexto",
            "arguments": {
                "pergunta": "como executar", "perfil": "engenharia-leitura",
                "max_tokens": None,
            },
        }
        mcp_max_tokens_nulo = subprocess.run(
            [sys.executable, "-m", "memoria_evolutiva", "contexto", "mcp"],
            cwd=self.projeto, env=self.env, input=json.dumps(max_tokens_nulo) + "\n",
            capture_output=True, text=True, encoding="utf-8", timeout=120,
        )
        self.assertTrue(json.loads(mcp_max_tokens_nulo.stdout)["result"]["isError"])
        self.assertIn("max_tokens", mcp_max_tokens_nulo.stdout)

        servidor = subprocess.Popen(
            [sys.executable, "-m", "memoria_evolutiva", "contexto", "http",
             "--porta=0", "--uma-requisicao"],
            cwd=self.projeto, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8",
        )
        try:
            pronto = servidor.stderr.readline().strip()
            match = re.search(r"http://127\.0\.0\.1:(\d+)", pronto)
            self.assertIsNotNone(match, pronto)
            payload = json.dumps({
                "pergunta": "como executar", "perfil": "engenharia-leitura"
            }).encode("utf-8")
            from urllib import request
            resposta = request.urlopen(request.Request(
                f"http://127.0.0.1:{match.group(1)}/contexto",
                data=payload, headers={"Content-Type": "application/json"}, method="POST",
            ), timeout=120)
            envelope_http = json.loads(resposta.read().decode("utf-8"))
            self.assertEqual(esperado, envelope_http)

            recalls_antes = sum(
                1 for caminho, _ in self.requisicoes if caminho.endswith("/recall")
            )
            restrito = self.cli(
                "contexto", "--pergunta=memória encontrada",
                "--perfil=atendimento", "--produto=produto-a", "--tenant=tenant-a",
                "--json",
            )
            envelope_restrito = json.loads(restrito.stdout)
            self.assertEqual(0, restrito.returncode, restrito.stdout + restrito.stderr)
            self.assertEqual(0, envelope_restrito["comparacao_sombra"]["documentos_semanticos"])
            self.assertNotIn("semantica", envelope_restrito["estrategias"])
            self.assertEqual(
                recalls_antes,
                sum(1 for caminho, _ in self.requisicoes if caminho.endswith("/recall")),
                "pergunta de cliente não pode entrar no recall do banco do projeto",
            )
        finally:
            servidor.wait(timeout=120)
            if servidor.poll() is None:
                servidor.terminate()
            if servidor.stdout:
                servidor.stdout.close()
            if servidor.stderr:
                servidor.stderr.close()

        (self.projeto / "src/app.py").write_text("def executar():\n    return 2\n", encoding="utf-8")
        stale = self.cli("bancos", "status")
        bloqueada = self.cli("bancos", "consultar", "--pergunta=como executar?")
        self.assertEqual(1, stale.returncode)
        self.assertIn("MUDARAM", stale.stdout)
        self.assertEqual(1, bloqueada.returncode)
        self.assertIn("bloqueada", bloqueada.stdout)

    def test_status_ao_vivo_reprova_banco_apagado_mesmo_com_marcador_verde(self) -> None:
        primeira = self.cli("bancos", "sincronizar")
        self.assertEqual(0, primeira.returncode, primeira.stdout + primeira.stderr)
        # Simula limpeza do Hindsight local sem tocar nos hashes versionados.
        self.requisicoes.clear()
        # O dicionário vive no closure do handler; DELETE cada documento pela API falsa.
        from urllib import parse, request
        marcador = json.loads(
            (self.projeto / "docs/.hindsight-indexado.json").read_text(encoding="utf-8")
        )
        for doc_id in marcador["prova_do_provedor"]["document_ids"].values():
            request.urlopen(request.Request(
                f"http://127.0.0.1:{self.servidor.server_port}/v1/default/banks/banco-fixture/documents/"
                + parse.quote(doc_id, safe=""), method="DELETE"
            )).read()

        status = self.cli("bancos", "status")
        reparado = self.cli("bancos", "sincronizar")

        self.assertEqual(1, status.returncode, status.stdout + status.stderr)
        self.assertIn("Hindsight ao vivo", status.stdout)
        self.assertEqual(0, reparado.returncode, reparado.stdout + reparado.stderr)

    def test_status_reprova_graph_json_corrompido_mesmo_com_hashes_de_fontes_iguais(self) -> None:
        primeira = self.cli("bancos", "sincronizar")
        self.assertEqual(0, primeira.returncode, primeira.stdout + primeira.stderr)
        (self.projeto / "graphify-out/graph.json").write_text("{corrompido", encoding="utf-8")

        status = self.cli("bancos", "status", "--offline")

        self.assertEqual(1, status.returncode, status.stdout + status.stderr)
        self.assertIn("marcador do Graphify inválido", status.stdout)

    def test_sincronizar_reconstroi_grafo_quando_versao_muda(self) -> None:
        primeira = self.cli("bancos", "sincronizar")
        self.assertEqual(0, primeira.returncode, primeira.stdout + primeira.stderr)
        (self.projeto / ".fake_graphify_version").write_text(
            "fake-graphify 2.0\n", encoding="utf-8"
        )

        defasado = self.cli("bancos", "status")
        reparado = self.cli("bancos", "sincronizar")

        self.assertEqual(1, defasado.returncode, defasado.stdout + defasado.stderr)
        self.assertIn("versão do Graphify mudou", defasado.stdout)
        self.assertEqual(0, reparado.returncode, reparado.stdout + reparado.stderr)
        marcador = json.loads(
            (self.projeto / ".memoria/bancos/graphify.json").read_text(encoding="utf-8")
        )
        self.assertEqual("fake-graphify 2.0", marcador["versao"])

    def test_hindsight_grande_usa_operacao_assincrona_e_confirma_documentos(self) -> None:
        cfg_path = self.projeto / "padrao.json"
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        cfg["memoria"]["assincrono_acima_de_bytes"] = 1
        cfg["memoria"]["intervalo_poll_segundos"] = 0.01
        cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

        sincronizar = self.cli("bancos", "sincronizar")

        self.assertEqual(0, sincronizar.returncode, sincronizar.stdout + sincronizar.stderr)
        retains = [payload for caminho, payload in self.requisicoes
                   if caminho.endswith("/memories")]
        self.assertTrue(retains)
        self.assertTrue(retains[0]["async"])
        self.assertIn("operation_id", retains[0])

    def test_nao_marca_hindsight_sem_memoria_persistida(self) -> None:
        self.estado_hindsight["memory_unit_count"] = 0

        sincronizar = self.cli("bancos", "sincronizar")

        self.assertEqual(1, sincronizar.returncode, sincronizar.stdout + sincronizar.stderr)
        self.assertIn("não encontrou memórias", sincronizar.stdout)
        self.assertFalse((self.projeto / "docs/.hindsight-indexado.json").exists())
        self.assertTrue((self.projeto / "graphify-out/graph.json").exists())

    def test_nao_marca_graphify_quando_reconstrucao_e_recusada(self) -> None:
        primeira = self.cli("bancos", "sincronizar")
        self.assertEqual(0, primeira.returncode, primeira.stdout + primeira.stderr)
        marcador = self.projeto / ".memoria/bancos/graphify.json"
        estado_anterior = marcador.read_bytes()
        (self.projeto / "src/app.py").write_text("def executar():\n    return 3\n", encoding="utf-8")
        (self.projeto / ".fake_graphify_fail").write_text("1\n", encoding="utf-8")

        segunda = self.cli("bancos", "sincronizar")

        self.assertEqual(1, segunda.returncode, segunda.stdout + segunda.stderr)
        self.assertIn("recusou a reconstrução", segunda.stdout)
        self.assertEqual(estado_anterior, marcador.read_bytes())

    def test_graphify_nao_substitui_grafo_por_colapso_anormal(self) -> None:
        primeira = self.cli("bancos", "sincronizar")
        self.assertEqual(0, primeira.returncode, primeira.stdout + primeira.stderr)
        marcador = self.projeto / ".memoria/bancos/graphify.json"
        grafo = self.projeto / "graphify-out/graph.json"
        estado_anterior = marcador.read_bytes()
        grafo_anterior = grafo.read_bytes()
        (self.projeto / "src/app.py").write_text("def executar():\n    return 9\n", encoding="utf-8")
        (self.projeto / ".fake_graphify_shrink").write_text("1\n", encoding="utf-8")

        segunda = self.cli("bancos", "sincronizar")

        self.assertEqual(1, segunda.returncode, segunda.stdout + segunda.stderr)
        self.assertIn("redução residual", segunda.stdout)
        self.assertEqual(estado_anterior, marcador.read_bytes())
        self.assertEqual(grafo_anterior, grafo.read_bytes())

    def test_status_reprova_marcador_graphify_corrompido_sem_traceback(self) -> None:
        primeira = self.cli("bancos", "sincronizar")
        self.assertEqual(0, primeira.returncode, primeira.stdout + primeira.stderr)
        marcador = self.projeto / ".memoria/bancos/graphify.json"
        marcador.write_text('{"schema": 1, "provedor": "graphify", "arquivos": []}\n', encoding="utf-8")

        status = self.cli("bancos", "status")

        self.assertEqual(1, status.returncode, status.stdout + status.stderr)
        self.assertIn("marcador do Graphify inválido", status.stdout)
        self.assertNotIn("Traceback", status.stdout + status.stderr)


class ArtefatosDistribuidosTest(unittest.TestCase):
    def test_schema_do_manifesto_de_adaptadores_e_versionado(self) -> None:
        schema = json.loads((
            REPOSITORIO
            / "memoria_evolutiva/schemas/manifesto-adaptadores-v1.schema.json"
        ).read_text(encoding="utf-8"))

        self.assertEqual(1, schema["properties"]["schema"]["const"])
        self.assertIn("gateway", schema["required"])
        self.assertIn("artefatos", schema["required"])
        self.assertEqual(
            ["memoria", "contexto", "mcp"],
            schema["properties"]["gateway"]["properties"]["comando"]["const"],
        )
        self.assertEqual(
            2, schema["properties"]["gateway"]["properties"]["contexto_schema"]["const"]
        )

    def test_schema_do_manifesto_de_fragmentos_e_versionado(self) -> None:
        schema = json.loads((
            REPOSITORIO
            / "memoria_evolutiva/schemas/manifesto-fragmentos-v2.schema.json"
        ).read_text(encoding="utf-8"))

        self.assertEqual(2, schema["properties"]["schema"]["const"])
        self.assertIn("fragment_id", schema["$defs"]["fragmento"]["required"])
        self.assertIn("source_uri", schema["$defs"]["fragmento"]["required"])
        self.assertIn("conteudo_sha256", schema["$defs"]["fragmento"]["required"])
        self.assertIn("perfil_fingerprint", schema["required"])
        self.assertIn("hindsight", schema["properties"]["perfil_indice"]["required"])
        self.assertIn("seguranca", schema["properties"]["perfil_indice"]["required"])
        self.assertIn("tenants", schema["$defs"]["fragmento"]["required"])

    def test_schema_do_gateway_de_contexto_e_versionado(self) -> None:
        schema = json.loads((
            REPOSITORIO / "memoria_evolutiva/schemas/contexto-v2.schema.json"
        ).read_text(encoding="utf-8"))

        self.assertEqual(2, schema["properties"]["schema"]["const"])
        self.assertIn("acoes_permitidas", schema["required"])
        self.assertIn("comparacao_sombra", schema["required"])
        self.assertEqual(0, schema["properties"]["acoes_permitidas"]["maxItems"])
        self.assertIn("source_sha256", schema["$defs"]["fonte"]["required"])
        self.assertIn("escopo", schema["required"])
        self.assertIn("cobertura", schema["required"])
        contrato_externo = schema["allOf"][0]
        self.assertEqual(
            ["atendimento", "operacao-assistida"],
            contrato_externo["if"]["properties"]["perfil"]["enum"],
        )
        escopo_externo = contrato_externo["then"]["properties"]["escopo"]["properties"]
        self.assertEqual("string", escopo_externo["produto"]["type"])
        self.assertEqual("string", escopo_externo["tenant"]["type"])
        entrada = contexto._ferramenta_mcp()["inputSchema"]
        self.assertEqual(
            ["produto", "tenant"], entrada["allOf"][0]["then"]["required"]
        )

    def test_schema_do_executor_e_versionado(self) -> None:
        schema = json.loads((
            REPOSITORIO / "memoria_evolutiva/schemas/executor-run-v1.schema.json"
        ).read_text(encoding="utf-8"))

        self.assertEqual(1, schema["properties"]["schema"]["const"])
        self.assertEqual(False, schema["properties"]["publicado"]["const"])
        self.assertEqual(False, schema["properties"]["commit_criado"]["const"])
        self.assertEqual(
            ["sincronizar-bancos"],
            [schema["properties"]["mutacoes_externas"]["items"]["const"]],
        )
        self.assertIn("preparar-worktree", schema["$defs"]["etapa_nome"]["enum"])
        self.assertIn("registrar-diff", schema["$defs"]["etapa_nome"]["enum"])
        self.assertIn("avaliar-pos-sincronizacao", schema["$defs"]["etapa_nome"]["enum"])
        self.assertEqual(
            [
                "preparar-worktree", "executar-acao", "validar", "registrar-diff",
                "sincronizar-bancos", "avaliar-pos-sincronizacao", "registrar-diff-final",
            ],
            executor._plano("documentar", ["sincronizar-bancos"]),
        )

    def test_schemas_da_avaliacao_rag_sao_versionados(self) -> None:
        for nome in (
            "corpus-avaliacao-rag-v1.schema.json",
            "baseline-avaliacao-rag-v1.schema.json",
            "relatorio-avaliacao-rag-v1.schema.json",
            "manifesto-avaliacao-rag-v1.schema.json",
        ):
            schema = json.loads(
                (REPOSITORIO / "memoria_evolutiva/schemas" / nome).read_text(encoding="utf-8")
            )
            self.assertEqual(1, schema["properties"]["schema"]["const"], nome)

    def test_instalador_detecta_linguagens_sem_decisao_manual(self) -> None:
        with tempfile.TemporaryDirectory(prefix="teste-linguagens-") as tmp:
            projeto = Path(tmp)
            (projeto / "app").mkdir()
            (projeto / "web").mkdir()
            (projeto / "infra").mkdir()
            (projeto / "app/main.py").write_text("print('ok')\n", encoding="utf-8")
            (projeto / "web/app.ts").write_text("export const ok = true;\n", encoding="utf-8")
            (projeto / "infra/Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
            env = os.environ.copy()
            env["PYTHONPATH"] = str(REPOSITORIO) + os.pathsep + env.get("PYTHONPATH", "")
            env["PYTHONUTF8"] = "1"

            r = subprocess.run(
                [sys.executable, "-m", "memoria_evolutiva", "instalar",
                 "--projeto=multistack", "--codigo=.", "--sem-bancos"],
                cwd=projeto, env=env, capture_output=True, text=True,
                encoding="utf-8", timeout=120,
            )

            self.assertEqual(0, r.returncode, r.stdout + r.stderr)
            configuracao = json.loads((projeto / "padrao.json").read_text(encoding="utf-8"))
            self.assertEqual(["py", "ts"], configuracao["gerado"]["extensoes"])
            cobertura = (projeto / "docs/gerado/cobertura-codigo.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("app/main.py", cobertura)
            self.assertIn("web/app.ts", cobertura)
            self.assertIn("infra/Dockerfile", cobertura)

    def test_runbooks_python_nao_mandam_usar_vendor_bin(self) -> None:
        stubs = REPOSITORIO / "memoria_evolutiva/stubs"
        ocorrencias = []
        for arquivo in stubs.rglob("*"):
            if arquivo.is_file():
                texto = arquivo.read_text(encoding="utf-8")
                if "vendor/bin/memoria" in texto:
                    ocorrencias.append(str(arquivo.relative_to(stubs)))

        self.assertEqual([], ocorrencias)

    def test_workflow_distribuido_exige_origem_imutavel(self) -> None:
        workflow = (
            REPOSITORIO / "memoria_evolutiva/stubs/.github/workflows/documentacao.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("<MEMORIA_EVOLUTIVA_ORIGEM_IMUTAVEL>", workflow)
        self.assertIn("memoria bancos status --offline", workflow)
        self.assertIn("memoria skill --conferir", workflow)
        self.assertIn("memoria avaliar verificar", workflow)
        self.assertNotIn("memoria-evolutiva.git@main", workflow)

    def test_workflow_instalado_migra_pin_da_versao_anterior(self) -> None:
        from memoria_evolutiva import instalar

        with tempfile.TemporaryDirectory(prefix="teste-workflow-pin-") as tmp:
            workflow = Path(tmp) / ".github/workflows/documentacao.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text(
                "steps:\n  - name: pacote\n    run: pip install memoria-evolutiva==5.0.0\n",
                encoding="utf-8",
            )
            ajustados: list[str] = []
            with mock.patch.object(
                instalar, "_origem_imutavel_ci", return_value="memoria-evolutiva==6.0.0"
            ):
                instalar._fixar_workflow(tmp, ajustados)

            texto = workflow.read_text(encoding="utf-8")
            self.assertIn("run: pip install memoria-evolutiva==6.0.0", texto)
            self.assertNotIn("==5.0.0", texto)
            self.assertTrue(ajustados)

    def test_workflow_instalado_atualiza_pin_oficial_para_o_commit_atual(self) -> None:
        from memoria_evolutiva import instalar

        with tempfile.TemporaryDirectory(prefix="teste-workflow-sha-") as tmp:
            workflow = Path(tmp) / ".github/workflows/documentacao.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text(
                "steps:\n  - name: pacote\n    run: pip install "
                "git+https://github.com/LastMind-dev/memoria-evolutiva.git@"
                + "a" * 40 + "\n",
                encoding="utf-8",
            )
            origem = (
                "git+https://github.com/LastMind-dev/memoria-evolutiva.git@" + "b" * 40
            )
            ajustados: list[str] = []
            with mock.patch.object(instalar, "_origem_imutavel_ci", return_value=origem):
                instalar._fixar_workflow(tmp, ajustados)

            texto = workflow.read_text(encoding="utf-8")
            self.assertIn("run: pip install " + origem, texto)
            self.assertNotIn("@" + "a" * 40, texto)
            self.assertTrue(ajustados)

    def test_origem_ci_nao_propaga_credencial_embutida(self) -> None:
        from memoria_evolutiva import instalar

        class DistribuicaoFalsa:
            @staticmethod
            def read_text(nome: str) -> str:
                self.assertEqual("direct_url.json", nome)
                return json.dumps({
                    "url": "https://usuario:senha@github.com/exemplo/projeto.git",
                    "vcs_info": {"commit_id": "a" * 40},
                })

        with mock.patch.object(
            instalar.metadata, "distribution", return_value=DistribuicaoFalsa()
        ):
            self.assertEqual(
                "memoria-evolutiva==6.0.0", instalar._origem_imutavel_ci()
            )

    def test_origem_ci_nao_injeta_metacaractere_no_workflow(self) -> None:
        from memoria_evolutiva import instalar

        class DistribuicaoFalsa:
            @staticmethod
            def read_text(_: str) -> str:
                return json.dumps({
                    "url": "https://github.com/exemplo/projeto.git;comando",
                    "vcs_info": {"commit_id": "b" * 40},
                })

        with mock.patch.object(
            instalar.metadata, "distribution", return_value=DistribuicaoFalsa()
        ):
            self.assertEqual(
                "memoria-evolutiva==6.0.0", instalar._origem_imutavel_ci()
            )


if __name__ == "__main__":
    unittest.main()
