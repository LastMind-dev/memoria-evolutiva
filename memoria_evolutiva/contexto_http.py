"""Transportes HTTP locais para o mesmo gateway de contexto e para MCP stateless."""

from __future__ import annotations

import json
import hmac
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer

from . import contexto


LOCAIS = {"127.0.0.1", "localhost", "::1"}


class ContextoHTTPError(RuntimeError):
    pass


class _Handler(BaseHTTPRequestHandler):
    server_version = "memoria-evolutiva"

    def _json(self, status: int, payload: object) -> None:
        corpo = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("MCP-Protocol-Version", contexto.MCP_PROTOCOL)
        self.end_headers()
        self.wfile.write(corpo)

    def _local(self) -> bool:
        try:
            host = urllib.parse.urlsplit("//" + self.headers.get("Host", "")).hostname
        except ValueError:
            return False
        if host not in LOCAIS:
            return False
        origem = self.headers.get("Origin")
        if origem:
            partes = urllib.parse.urlsplit(origem)
            if partes.scheme not in {"http", "https"} or partes.hostname not in LOCAIS:
                return False
        token = os.environ.get("MEMORIA_CONTEXTO_TOKEN")
        recebido = self.headers.get("Authorization", "")
        return not token or hmac.compare_digest(recebido, f"Bearer {token}")

    def do_GET(self) -> None:  # noqa: N802 - contrato de BaseHTTPRequestHandler
        if not self._local():
            self._json(403, {"erro": "origem, host ou credencial recusados"})
            return
        if self.path == "/health":
            self._json(200, {"status": "ok", "schema": contexto.SCHEMA})
            return
        self._json(405 if self.path == "/mcp" else 404, {"erro": "rota não disponível"})

    def do_POST(self) -> None:  # noqa: N802 - contrato de BaseHTTPRequestHandler
        if not self._local():
            self._json(403, {"erro": "origem, host ou credencial recusados"})
            return
        if self.path not in {"/contexto", "/mcp"}:
            self._json(404, {"erro": "rota não disponível"})
            return
        versao_mcp = self.headers.get("MCP-Protocol-Version")
        if self.path == "/mcp" and versao_mcp not in {None, contexto.MCP_PROTOCOL}:
            self._json(400, {
                "jsonrpc": "2.0", "id": None,
                "error": {"code": -32600, "message": "Unsupported protocol version"},
            })
            return
        if self.headers.get_content_type() != "application/json":
            self._json(415, {"erro": "Content-Type precisa ser application/json"})
            return
        try:
            tamanho = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            tamanho = -1
        if tamanho < 0 or tamanho > 1_048_576:
            self._json(413, {"erro": "corpo excede 1 MiB"})
            return
        try:
            payload = json.loads(self.rfile.read(tamanho))
        except json.JSONDecodeError:
            self._json(400, {"erro": "JSON inválido"})
            return
        if self.path == "/mcp":
            resposta = contexto.processar_mcp(payload)
            if resposta is None:
                self.send_response(202)
                self.send_header("Content-Length", "0")
                self.end_headers()
            else:
                self._json(200, resposta)
            return
        if not isinstance(payload, dict):
            self._json(400, {"erro": "corpo precisa ser objeto"})
            return
        try:
            pergunta, perfil, max_tokens, produto, tenant = contexto._argumentos_contexto(payload)
            envelope = contexto.construir(pergunta, perfil, max_tokens, produto, tenant)
        except (contexto.ContextoErro, SystemExit) as exc:
            detalhe = str(exc) if isinstance(exc, contexto.ContextoErro) else "configuração do projeto inválida"
            self._json(422, {"erro": detalhe})
            return
        self._json(200, envelope)

    def log_message(self, format: str, *args: object) -> None:
        return


def criar_servidor(host: str = "127.0.0.1", porta: int = 8765,
                   concorrente: bool = True) -> HTTPServer:
    if host not in LOCAIS:
        raise ContextoHTTPError("o servidor de contexto aceita somente loopback")
    if isinstance(porta, bool) or not isinstance(porta, int) or not 0 <= porta <= 65535:
        raise ContextoHTTPError("a porta precisa ser inteira entre 0 e 65535")
    classe = ThreadingHTTPServer if concorrente else HTTPServer
    return classe((host, porta), _Handler)


def main(argv: list[str]) -> int:
    try:
        configuracao = contexto._cfg()
    except contexto.ContextoErro as exc:
        print(f"ERRO — servidor HTTP não iniciou: {exc}", file=sys.stderr)
        return 1
    host = str(configuracao.get("http_host", "127.0.0.1"))
    porta = configuracao.get("http_porta", 8765)
    uma = False
    for argumento in argv:
        if argumento == "--uma-requisicao":
            uma = True
        elif argumento.startswith("--porta="):
            try:
                porta = int(argumento.split("=", 1)[1])
            except ValueError:
                print("`--porta` precisa ser inteira.", file=sys.stderr)
                return 2
        elif argumento.startswith("--host="):
            host = argumento.split("=", 1)[1]
        else:
            print(f"Opção desconhecida: {argumento}", file=sys.stderr)
            return 2
    try:
        servidor = criar_servidor(host, porta, concorrente=not uma)
    except (ContextoHTTPError, OSError) as exc:
        print(f"ERRO — servidor HTTP não iniciou: {exc}", file=sys.stderr)
        return 1
    endereco, porta_real = servidor.server_address[:2]
    print(f"Contexto HTTP em http://{endereco}:{porta_real}", file=sys.stderr, flush=True)
    try:
        servidor.handle_request() if uma else servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()
    return 0
