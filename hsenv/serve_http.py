"""HTTP door (DESIGN.md §9): JSON over http.server, stdlib only.

    python -m hsenv.serve_http [--port 8765] [--host 127.0.0.1] [--allow-host NAME ...] [--studies DIR] [--only ...]
                               [--arm study:arm ...] [--seed N] [--max-sessions N] [--ttl SEC]

    GET  /studies                          list_studies
    POST /sessions        {study}          open_session -> {session, key, state}
    GET  /sessions/{id}[?history=1]        get_state        (header X-Session-Key: <key>)
    POST /sessions/{id}/step {answers}     step             (header X-Session-Key, or "key" in the body)
    GET  /sessions/{id}/assets/{asset:..}  image bytes      (header X-Session-Key)
    GET  /sessions/{id}/record             operator only
    POST /score           {study, run?}    operator only
    POST /tools/{name}    {arguments}      any tool by name (same table as MCP; arguments.key)

Every request gets the participant view. Requests carrying `Authorization: Bearer <HSENV_OPERATOR_TOKEN>` get the
operator view of the same sessions (records, scores, arm/seed choice); without the token there is no operator
view at all, and --operator refuses to start without it.

Hardening: binds 127.0.0.1 by default; the Host header must name an allowed host (loopback names plus --allow-host),
which stops DNS rebinding; a request with a foreign Origin or Sec-Fetch-Site: cross-site is refused, and a POST
must be Content-Type: application/json, which stops cross-site form posts; bodies are capped at MAX_BODY bytes.
Put it behind your own TLS and auth before exposing it beyond this machine.
"""
import argparse
import base64
import hmac
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from .serve import ServeError, call
from .serve_mcp import add_server_args, build_server

MAX_BODY = 1024 * 1024
LOOPBACK = ("127.0.0.1", "localhost", "::1", "[::1]")


_HOST = re.compile(r"^(\[[0-9a-f:.]+\]|[a-z0-9.-]+)(?::(\d{1,5}))?$")


def _host_name(h):
    """'Host' header -> lower-case name without port ('[::1]:80' -> '[::1]'); '' if it does not parse."""
    m = _HOST.match((h or "").strip().lower())
    return m.group(1) if m else ""


def make_handler(server, operator_token=None, allowed_hosts=(), timeout=30):
    """server: the shared Server. operator_token: requests with `Authorization: Bearer <token>` get the operator
    view of the same sessions; without a token nobody does. Sessions are bound to a key returned at open."""
    if server.operator and not operator_token:
        raise ValueError("the HTTP door gives an operator view only behind a token: set HSENV_OPERATOR_TOKEN")
    server.require_key = True
    base = server.as_participant()
    op = server.as_operator() if operator_token else None
    hosts = {h.lower() for h in LOOPBACK} | {_host_name(h) for h in allowed_hosts}
    timeout_ = timeout

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"
        timeout = timeout_   # a client that stops sending (slowloris) loses its thread after this many seconds

        def log_message(self, *a):   # quiet by default
            pass

        def _send(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _guard(self, method):
            if _host_name(self.headers.get("Host")) not in hosts:
                raise ServeError("host not allowed", 421)
            origin = self.headers.get("Origin")
            if origin is not None:   # agents send none; a browser page may drive us only from our own origin
                port = self.server.server_address[1]
                ok = {"http://%s:%d" % (h if not (":" in h and not h.startswith("[")) else "[%s]" % h, port)
                      for h in hosts}
                if origin.strip().lower().rstrip("/") not in ok:
                    raise ServeError("cross-origin requests are not allowed", 403)
            if (self.headers.get("Sec-Fetch-Site") or "").lower() == "cross-site":
                raise ServeError("cross-origin requests are not allowed", 403)
            if self.headers.get("Transfer-Encoding"):
                raise ServeError("send a Content-Length, not a chunked body", 411)
            raw = self.headers.get("Content-Length")
            n = 0
            if raw is not None:
                try:
                    n = int(raw.strip())
                except ValueError:
                    raise ServeError("bad Content-Length")
                if n < 0:
                    raise ServeError("bad Content-Length")
                if n > MAX_BODY:
                    raise ServeError("body too large (max %d bytes)" % MAX_BODY, 413)
            if method == "POST":
                ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                if ctype != "application/json":
                    raise ServeError("Content-Type must be application/json", 415)
            return n

        def _body(self, n):
            if not n:
                return {}
            try:
                d = json.loads(self.rfile.read(n))
            except (ValueError, RecursionError):
                raise ServeError("body must be JSON")
            if not isinstance(d, dict):
                raise ServeError("body must be a JSON object")
            return d

        def _server(self):
            auth = self.headers.get("Authorization") or ""
            if op is not None and auth.startswith("Bearer ") and \
                    hmac.compare_digest(auth[7:].encode("utf-8", "replace"), operator_token.encode()):
                return op
            return base

        def _client(self, server):
            """The participant token naming this client (operator-issued, --participant-tokens), or None."""
            if server.operator or not server.participant_tokens:
                return None
            tok = self.headers.get("X-Participant-Token") or ""
            if not any(hmac.compare_digest(tok.encode("utf-8", "replace"), x.encode()) for x in
                       server.participant_tokens):
                raise ServeError("a participant token is required (X-Participant-Token)", 401)
            return tok

        def _route(self, method, n):
            server = self._server()
            url = urlparse(self.path)
            parts = [unquote(x) for x in url.path.strip("/").split("/") if x]
            hkey = self.headers.get("X-Session-Key")

            def keyed(args):
                if hkey is not None and not server.operator:
                    args.setdefault("key", hkey)
                return args

            body = self._body(n) if method == "POST" else {}
            if method == "GET" and parts == ["studies"]:
                return call(server, "list_studies", {})
            if method == "POST" and parts == ["sessions"]:
                return call(server, "open_session", body, client=self._client(server))
            if len(parts) >= 2 and parts[0] == "sessions":
                sid = parts[1]
                if method == "GET" and len(parts) == 2:
                    hist = (parse_qs(url.query).get("history") or ["0"])[0] in ("1", "true", "yes")
                    return call(server, "get_state", keyed({"session": sid, "history": hist}))
                if method == "POST" and parts[2:] == ["step"]:
                    return call(server, "step", keyed(dict(body, session=sid)))
                if method == "GET" and parts[2:] == ["record"]:
                    return call(server, "get_record", {"session": sid})
                if method == "GET" and len(parts) == 4 and parts[2] == "assets":
                    a = call(server, "get_asset", keyed({"session": sid, "ref": parts[3]}))
                    return (base64.b64decode(a["data"]), a["mimeType"])
            if method == "POST" and parts == ["score"]:
                return call(server, "score", body)
            if method == "POST" and len(parts) == 2 and parts[0] == "tools":
                args = body.get("arguments")
                client = self._client(server) if parts[1] == "open_session" else None
                return call(server, parts[1], keyed(args) if isinstance(args, dict) else args, client=client)
            raise ServeError("not found", 404)

        def _do(self, method):
            try:
                n = self._guard(method)
                out = self._route(method, n)
            except ServeError as e:
                if e.code in (411, 413, 400):
                    self.close_connection = True   # the unread body must not be parsed as the next request
                return self._send(e.code, {"error": str(e)})
            except Exception:   # noqa: BLE001 - never echo internals
                return self._send(500, {"error": "internal error"})
            if isinstance(out, tuple):
                return self._send(200, out[0], out[1])
            return self._send(200, out)

        def do_GET(self):
            self._do("GET")

        def do_POST(self):
            self._do("POST")

        def _no(self):
            self._send(405, {"error": "method not allowed"})

        do_PUT = do_DELETE = do_PATCH = do_OPTIONS = _no

    return Handler


def make_server(server, host="127.0.0.1", port=8765, operator_token=None, allowed_hosts=(), timeout=30):
    return ThreadingHTTPServer((host, port), make_handler(server, operator_token, allowed_hosts, timeout))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--host", default="127.0.0.1", help="bind address (default 127.0.0.1)")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--allow-host", action="append", default=[], metavar="NAME",
                    help="extra Host header name to accept (needed when binding beyond loopback)")
    ap.add_argument("--operator", action="store_true",
                    help="accepted only with HSENV_OPERATOR_TOKEN; the operator view is always behind the token")
    ap.add_argument("--participant-tokens", metavar="FILE",
                    help="one token per line; opening a session then needs X-Participant-Token, and each token gets "
                         "one arm per study (and at most --max-opens sessions)")
    add_server_args(ap)
    a = ap.parse_args(argv)
    token = os.environ.get("HSENV_OPERATOR_TOKEN") or None
    ptoks = None
    if a.participant_tokens:
        try:
            ptoks = [x.strip() for x in open(a.participant_tokens, encoding="utf-8") if x.strip()]
        except OSError as e:
            print("hsenv: cannot read --participant-tokens: %s" % e, file=sys.stderr)
            return 2
    if a.operator and not token:
        print("hsenv: --operator needs HSENV_OPERATOR_TOKEN (the operator view is only served behind it)",
              file=sys.stderr)
        return 2
    if a.host not in LOOPBACK:
        if not a.allow_host:
            print("hsenv: binding %s needs --allow-host <the name clients use> (Host allowlist)" % a.host,
                  file=sys.stderr)
            return 2
        print("hsenv: WARNING: serving beyond this machine on %s; put TLS and auth in front" % a.host,
              file=sys.stderr)
    srv = build_server(a, False, participant_tokens=ptoks)
    httpd = make_server(srv, a.host, a.port, token, a.allow_host)
    print("hsenv http on http://%s:%d (participant view%s)" % (a.host, a.port,
                                                               "; operator view behind the token" if token else ""),
          file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
