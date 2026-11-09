"""MCP door (DESIGN.md §9): JSON-RPC 2.0 over stdio, newline-delimited, stdlib only.

    python -m hsenv.serve_mcp [--studies DIR] [--only id1,id2] [--arm study:arm ...] [--seed N] [--operator]
    HSENV_MODE=operator python -m hsenv.serve_mcp

Methods: initialize, notifications/initialized, ping, tools/list, tools/call. Tools: see serve.tools().
Participant mode (default) returns the caller's own State only; see hsenv/serve.py and SERVE.md. A stdio server
has exactly one client, so its sessions are bound to that client by the pipe itself (no session keys).

Robustness: no message can stop the server. A line that is not JSON (or nested too deeply) gets -32700, a
malformed request -32600, bad params or an unknown tool -32602, and anything unexpected -32603.
"""
import argparse
import json
import sys

from .serve import ServeError, Server, call, tools

PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
SERVER_INFO = {"name": "hsenv", "version": "0.1"}
MAX_LINE = 4 * 1024 * 1024   # one JSON-RPC message, bytes (answers are small; this only stops abuse)


class MCP:
    def __init__(self, server, client="stdio"):
        """client: the one client of this door. It gets one arm per study however often it opens (Server)."""
        self.server = server
        self.client = client

    def handle(self, msg):
        """One JSON-RPC message (any JSON value) -> response dict, or None for notifications. Never raises."""
        try:
            return self._handle(msg)
        except Exception:   # noqa: BLE001 - the last line of defence: the server keeps running
            mid = msg.get("id") if isinstance(msg, dict) and _valid_id(msg.get("id")) else None
            return None if isinstance(msg, dict) and "id" not in msg else _err(mid, -32603, "internal error")

    def _handle(self, msg):
        if not isinstance(msg, dict):
            return _err(None, -32600, "invalid request")
        mid = msg.get("id")
        if not _valid_id(mid):
            return _err(None, -32600, "invalid request: id must be a string, number or null")
        if msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
            return _err(mid, -32600, "invalid request")
        is_note = "id" not in msg
        params = msg.get("params")
        if params is None:
            params = {}
        try:
            if not isinstance(params, dict):
                raise _RpcError(-32602, "params must be an object")
            result = self._dispatch(msg["method"], params)
        except _RpcError as e:
            return None if is_note else _err(mid, e.code, str(e))
        if is_note:
            return None
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    def _dispatch(self, method, params):
        if method == "initialize":
            want = params.get("protocolVersion")
            return {"protocolVersion": want if isinstance(want, str) and want in PROTOCOL_VERSIONS
                    else PROTOCOL_VERSIONS[0],
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": SERVER_INFO}
        if method.startswith("notifications/"):
            return {}
        if method == "ping":
            return {}
        if method == "tools/list":
            return {"tools": tools(self.server.operator, keyed=self.server.require_key)}
        if method == "tools/call":
            name, args = params.get("name"), params.get("arguments")
            if not isinstance(name, str):
                raise _RpcError(-32602, "params.name must be a string")
            if args is None:
                args = {}
            if not isinstance(args, dict):
                raise _RpcError(-32602, "params.arguments must be an object")
            if name not in {t["name"] for t in tools(self.server.operator, keyed=self.server.require_key)}:
                raise _RpcError(-32602, "unknown tool: %s" % name[:60])
            try:
                out = call(self.server, name, args, client=self.client)
            except ServeError as e:
                return {"content": [{"type": "text", "text": json.dumps({"error": str(e)})}], "isError": True}
            except Exception:   # noqa: BLE001 - a tool failure is the caller's result, not a dead server
                return {"content": [{"type": "text", "text": json.dumps({"error": "internal error"})}],
                        "isError": True}
            if name == "get_asset" and out.get("mimeType", "").startswith("image/"):
                return {"content": [{"type": "image", "data": out["data"], "mimeType": out["mimeType"]}],
                        "isError": False}
            return {"content": [{"type": "text", "text": json.dumps(out, ensure_ascii=False)}],
                    "structuredContent": out, "isError": False}
        raise _RpcError(-32601, "method not found: %s" % method[:60])


class _RpcError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _valid_id(mid):
    return mid is None or isinstance(mid, str) or (isinstance(mid, (int, float)) and not isinstance(mid, bool))


def _err(mid, code, message):
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def respond(mcp, line):
    """One input line -> the response to write (dict, list, or None). Never raises."""
    try:
        msg = json.loads(line)
    except (ValueError, RecursionError):
        return _err(None, -32700, "parse error")
    if isinstance(msg, list):   # a batch (2025-03-26)
        if not msg:
            return _err(None, -32600, "invalid request: empty batch")
        return [r for r in (mcp.handle(m) for m in msg) if r is not None] or None
    return mcp.handle(msg)


def _encode(resp):
    try:
        return json.dumps(resp, ensure_ascii=False)
    except (TypeError, ValueError, RecursionError):
        return json.dumps(_err(None, -32603, "internal error"))


def serve(server, stdin=sys.stdin, stdout=sys.stdout, max_line=MAX_LINE):
    mcp = MCP(server)
    while True:
        line = stdin.readline(max_line + 1)
        if not line:
            break
        if len(line) > max_line and not line.endswith("\n"):
            while True:   # drop the rest of the oversized line
                rest = stdin.readline(max_line)
                if not rest or rest.endswith("\n"):
                    break
            resp = _err(None, -32600, "message too large")
        else:
            line = line.strip()
            if not line:
                continue
            resp = respond(mcp, line)
        if resp is not None:
            try:
                stdout.write(_encode(resp) + "\n")
                stdout.flush()
            except (BrokenPipeError, ValueError):   # the client went away
                break


def parse_assign(items):
    """["study:arm", ...] -> {study: [arms]}"""
    out = {}
    for x in items or []:
        if ":" not in x:
            raise SystemExit("--arm takes study:arm, got %r" % x)
        s, a = x.split(":", 1)
        out.setdefault(s, []).append(a)
    return out


def add_server_args(ap):
    ap.add_argument("--studies", help="studies directory (required when installed from a wheel; or $HSENV_STUDIES)")
    ap.add_argument("--only", help="comma-separated study ids to serve (default: all, or $HSENV_ONLY)")
    ap.add_argument("--arm", action="append", metavar="STUDY:ARM",
                    help="arms the server may assign for a study (repeatable; default: every runnable arm)")
    ap.add_argument("--seed", type=int, help="base seed for participant sessions (default: random, never shown)")
    ap.add_argument("--max-sessions", type=int, help="cap on live sessions (default 256 or $HSENV_MAX_SESSIONS)")
    ap.add_argument("--ttl", type=int, help="drop a session idle this many seconds (default 7200 or $HSENV_TTL)")
    ap.add_argument("--max-opens", type=int, metavar="N",
                    help="cap on sessions one client may open per study (default: no cap; the arm is fixed per "
                         "client either way)")
    ap.add_argument("--full-history", action="store_true",
                    help="send whole States (seen/answered) on every response instead of diffs")


def build_server(a, operator, require_key=False, participant_tokens=None):
    only = [x for x in a.only.split(",") if x] if a.only else None
    try:
        return Server(a.studies, operator, only, assign=parse_assign(a.arm), base_seed=a.seed,
                      max_sessions=a.max_sessions, ttl=a.ttl, full_history=a.full_history, require_key=require_key,
                      opens_per_client=a.max_opens, participant_tokens=participant_tokens)
    except ServeError as e:
        print("hsenv: %s" % e, file=sys.stderr)
        raise SystemExit(2)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--operator", action="store_true", help="operator mode (records, specs, scores)")
    add_server_args(ap)
    a = ap.parse_args(argv)
    serve(build_server(a, True if a.operator else None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
