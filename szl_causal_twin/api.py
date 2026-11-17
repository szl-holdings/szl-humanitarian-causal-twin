"""Loopback-only synthetic evaluator; no actuator, provider access or background controller."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import socket
from http.server import BaseHTTPRequestHandler, HTTPServer

from .cli import _reject_duplicate_keys
from .core import InvalidEvidence, evaluate

MAX_BODY_BYTES = 128 * 1024


def _response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    # One response per socket: early 413/415 refusals must not parse unread bodies.
    handler.close_connection = True
    data = json.dumps(payload, sort_keys=True, allow_nan=False, separators=(",", ":")).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Connection", "close")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("X-Frame-Options", "DENY")
    handler.end_headers()
    handler.wfile.write(data)


def _static(handler: BaseHTTPRequestHandler, kind: str) -> None:
    allowed = {"ui.html": ("text/html; charset=utf-8", "default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'none'"),
               "ui.js": ("text/javascript; charset=utf-8", "default-src 'none'")}
    if kind not in allowed:
        _response(handler, 404, {"error": "not_found"})
        return
    data = Path(__file__).with_name(kind).read_bytes()
    handler.close_connection = True
    handler.send_response(200)
    handler.send_header("Content-Type", allowed[kind][0])
    handler.send_header("Content-Security-Policy", allowed[kind][1])
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Connection", "close")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("X-Frame-Options", "DENY")
    handler.end_headers()
    handler.wfile.write(data)


class SyntheticHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "SZLSyntheticTwin/0.2"
    sys_version = ""

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(3)

    def log_message(self, fmt: str, *args: object) -> None:
        # No request bodies, source paths, device records, or Authorization headers logged.
        return

    def _is_local_request(self) -> bool:
        hostname = self.headers.get("Host", "")
        expected = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        return self.client_address[0] == "127.0.0.1" and hostname in expected

    def _admit(self) -> bool:
        if not self._is_local_request():
            _response(self, 403, {"error": "loopback_host_required"})
            return False
        return True

    def do_GET(self) -> None:
        if not self._admit():
            return
        if self.path in ("/", "/ui.js"):
            _static(self, "ui.html" if self.path == "/" else "ui.js")
        elif self.path.startswith("/api/causal-twin/v1/examples/"):
            selected = self.path.removeprefix("/api/causal-twin/v1/examples/")
            examples = {"healthy": "healthy-synthetic-water.json", "imbalance": "imbalance-synthetic-water.json",
                        "coverage-loss": "coverage-loss-synthetic-water.json"}
            if selected not in examples:
                _response(self, 404, {"error": "unknown_synthetic_example"})
            else:
                fixture_path = Path(__file__).resolve().parents[1] / "examples" / examples[selected]
                with fixture_path.open("r", encoding="utf-8") as file:
                    _response(self, 200, json.load(file))
        elif self.path == "/healthz":
            _response(self, 200, {"ok": True, "scope": "LOCAL_SYNTHETIC_ONLY", "read_only": True,
                                  "actuation": "DENIED", "field_qualified": False})
        elif self.path == "/readyz":
            _response(self, 503, {"ready": False, "scope": "FIELD_DEPLOYMENT_HOLD",
                                  "requirements": "independent safety review; approved sources and calibration; measured validation"})
        elif self.path == "/api/causal-twin/v1/capabilities":
            _response(self, 200, {"synthetic_only": True, "model_trained": False,
                                  "real_facility_data_admitted": False, "actuation": "DENIED",
                                  "signature": "UNSIGNED", "provider_connector": "NONE"})
        else:
            _response(self, 404, {"error": "not_found"})

    def do_POST(self) -> None:
        if not self._admit():
            return
        if self.path != "/api/causal-twin/v1/evaluate":
            _response(self, 404, {"error": "not_found"})
            return
        if self.headers.get("Transfer-Encoding") is not None:
            _response(self, 400, {"error": "transfer_encoding_not_supported"})
            return
        if self.headers.get("Content-Type", "").lower().split(";", 1)[0].strip() != "application/json":
            _response(self, 415, {"error": "application_json_required"})
            return
        size_header = self.headers.get("Content-Length")
        if size_header is None:
            _response(self, 411, {"error": "content_length_required"})
            return
        try:
            size = int(size_header)
        except ValueError:
            _response(self, 400, {"error": "invalid_content_length"})
            return
        if size <= 0 or size > MAX_BODY_BYTES:
            _response(self, 413, {"error": "body_limit_128_kib"})
            return
        try:
            body = self.rfile.read(size)
            if len(body) != size:
                raise InvalidEvidence("incomplete JSON body")
            obj = json.loads(body.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys,
                             parse_constant=lambda _: (_ for _ in ()).throw(InvalidEvidence("nonfinite JSON constant")))
            answer = evaluate(obj)
        except (InvalidEvidence, ValueError, UnicodeDecodeError, TypeError, json.JSONDecodeError):
            _response(self, 400, {"error": "invalid_or_unadmitted_evidence"})
            return
        _response(self, 200, answer)

    def do_PUT(self) -> None:
        if not self._admit():
            return
        _response(self, 405, {"error": "read_only"})

    def do_DELETE(self) -> None:
        if not self._admit():
            return
        _response(self, 405, {"error": "read_only"})

    def do_PATCH(self) -> None:
        if not self._admit():
            return
        _response(self, 405, {"error": "read_only"})


def make_server(port: int = 18109) -> HTTPServer:
    if type(port) is not int or not (0 <= port <= 65535):
        raise ValueError("invalid port")
    return HTTPServer(("127.0.0.1", port), SyntheticHandler)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="localhost-only synthetic causal-twin HTTP API")
    parser.add_argument("--port", type=int, default=18109)
    args = parser.parse_args(argv)
    with make_server(args.port) as server:
        print(f"LOCAL_SYNTHETIC_ONLY http://127.0.0.1:{server.server_port}", flush=True)
        server.serve_forever(poll_interval=0.3)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
