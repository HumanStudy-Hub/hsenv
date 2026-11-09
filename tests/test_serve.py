"""The two outside-agent doors (serve_mcp, serve_http): participant mode leaks nothing (DESIGN §2 rule 4)."""
import io
import json
import random
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import unittest.mock
import urllib.error
import urllib.request
from pathlib import Path

from hsenv import checks
from hsenv.engine import Protocol
from hsenv import serve as serve_mod
from hsenv import serve_http, serve_mcp
from hsenv.serve import ServeError, Server, call, study_handle
from hsenv.serve_http import make_handler, make_server
from hsenv.serve_mcp import MCP, respond

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "studies"   # invented CC0 fixtures
MARK = "SECRET"   # every author-written id, condition, key and rule in the synthetic protocol carries it

P = {
    "id": "STUDYSECRET", "meta": {"title": "TITLESECRET: priming raises ratings (hypothesis)"},
    "arms": [{"id": "ARMSECRET_treatment", "n_paper": 5}, {"id": "ARMSECRET_control", "n_paper": 5}],
    "data": {},
    "stages": {
        "STAGESECRET_intro": {"content": [{"id": "ITEMSECRET_welcome", "value": "Welcome. Please read carefully.",
                                           "cite": {"label": "verbatim", "note": "NOTESECRET from the appendix"}}],
                              "responses": [{"id": "RESPSECRET_age", "kind": "number", "prompt": "Your age?",
                                             "range": [18, 99]}]},
        "STAGESECRET_vignette": {
            "content": [{"id": "ITEMSECRET_story", "value": {"expr": "'A short story.' if arm == 'ARMSECRET_treatment' else 'Another story.'"}}],
            "responses": [{"id": "RESPSECRET_pick", "kind": "choice", "prompt": "Did he know?",
                           "options": [{"code": "KEYSECRET_correct", "label": "Yes"},
                                       {"code": "KEYSECRET_wrong", "label": "No"}]},
                          {"id": "RESPSECRET_rate", "kind": "slider", "prompt": "How sure?", "range": [0, 100]}]},
    },
    "flow": {"seq": [
        {"set": {"VARSECRET_cond": {"expr": "choice(['CONDSECRET_hi', 'CONDSECRET_lo'])"}}},
        {"stage": "STAGESECRET_intro"},
        {"for": "LOOPSECRET_v", "in": ["CONDSECRET_a", "CONDSECRET_b"], "do": {"stage": "STAGESECRET_vignette"}},
        {"flag": "FLAGSECRET_fast", "if": "answer('STAGESECRET_intro.RESPSECRET_age') < 20"},
    ]},
    "exclusions": [{"id": "EXCLSECRET_attn", "if": "answer('STAGESECRET_vignette.RESPSECRET_pick') == 'KEYSECRET_wrong'"}],
    "units": {"UNITSECRET": {"per": "session", "fields": {"FIELDSECRET": "answer('STAGESECRET_intro.RESPSECRET_age')"}}},
    "keyed": {"answers": {"STAGESECRET_vignette.RESPSECRET_pick": "KEYSECRET_correct"}},
}


def answer(state, rng, bad=False):
    """A crude participant: valid answers from the State alone (or an invalid one when bad)."""
    out = {}
    for r in state["screen"]["responses"]:
        if r["kind"] == "choice":
            out[r["id"]] = "o99" if bad else rng.choice(r["options"])["code"]
        elif r["kind"] in ("number", "scale", "slider"):
            lo, hi = (r.get("range") or [0, 10])[:2]
            out[r["id"]] = 10 ** 9 if bad else rng.randint(int(lo), int(hi))
        else:
            out[r["id"]] = "ok"
    return out



# a 2-person group with a barrier: each member must see only its own screen
PG = {"id": "GROUPSECRET", "data": {},
      "arms": [{"id": "ARMSECRET_group", "n_paper": 2, "group_size": 2}],
      "stages": {"STAGESECRET_c": {"responses": [{"id": "RESPSECRET_c", "kind": "number", "range": [0, 20],
                                                  "integer": True, "prompt": "How much do you put in?"}]}},
      "flow": {"loop": 2, "as": "r", "do": {"seq": [
          {"stage": "STAGESECRET_c"},
          {"sync": "SYNCSECRET", "compute": {"VARSECRET_total": "sum(group('STAGESECRET_c.RESPSECRET_c'))"},
           "events": [{"expr": "'Group total: %d.' % VARSECRET_total"}]}]}},
      "units": {}, "exclusions": [], "keyed": {"answers": {}}}


def _tmp_studies(*protocols):
    d = Path(tempfile.mkdtemp())
    for p in protocols:
        (d / p["id"]).mkdir()
        (d / p["id"] / "protocol.json").write_text(json.dumps(p))
    return d


def play_single(server, opened, rng):
    """Play one participant session to the end through server calls; -> list of responses."""
    out, o = [opened], opened
    while not o["state"]["done"]:
        o = server.step(opened["session"], answer(o["state"], rng))
        out.append(o)
    return out


class SyntheticStudy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = _tmp_studies(P, PG)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def server(self, **kw):
        kw.setdefault("studies", ["STUDYSECRET"])
        return Server(self.tmp, **kw)

    def handle(self, s, study="STUDYSECRET"):
        return s.handle(study)

    def test_whole_session_over_mcp_stdio_leaks_nothing(self):
        """A real subprocess speaking MCP over stdio: every byte it writes is free of protocol internals, and
        malformed messages never stop it."""
        proc = subprocess.Popen([sys.executable, "-m", "hsenv.serve_mcp", "--studies", str(self.tmp),
                                 "--only", "STUDYSECRET"], cwd=str(ROOT),
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                env={"HSENV_MODE": "participant", "PATH": "/usr/bin:/bin"})
        n = [0]
        raw = []

        def send(line):
            proc.stdin.write(line + "\n")
            proc.stdin.flush()
            out = proc.stdout.readline()
            raw.append(out)
            return json.loads(out)

        def rpc(method, params=None, note=False):
            msg = {"jsonrpc": "2.0", "method": method, "params": params or {}}
            if not note:
                n[0] += 1
                msg["id"] = n[0]
            if note:
                proc.stdin.write(json.dumps(msg) + "\n")
                proc.stdin.flush()
                return None
            resp = send(json.dumps(msg))
            self.assertEqual(resp["id"], n[0])
            return resp

        def tool(name, **args):
            r = rpc("tools/call", {"name": name, "arguments": args})["result"]
            return r, json.loads(r["content"][0]["text"])

        try:
            init = rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                      "clientInfo": {"name": "test", "version": "0"}})
            self.assertEqual(init["result"]["protocolVersion"], "2025-06-18")
            self.assertIn("tools", init["result"]["capabilities"])
            rpc("notifications/initialized", note=True)
            tl = rpc("tools/list")["result"]["tools"]
            self.assertEqual({t["name"] for t in tl}, {"list_studies", "open_session", "get_state", "step", "get_asset"})
            self.assertEqual(set(next(t for t in tl if t["name"] == "open_session")["inputSchema"]["properties"]),
                             {"study"})   # no arm, no seed
            # malformed input: each gets an error and the server keeps going (review 1 A1)
            bad = [
                ('{"jsonrpc":"2.0","id":1,"method":"tools/call","params":"x"}', -32602),
                ('{"jsonrpc":"2.0","id":1,"method":"tools/call","params":5}', -32602),
                ('{"jsonrpc":"2.0","id":1,"method":"initialize","params":[1]}', -32602),
                ('{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"step","arguments":"s"}}', -32602),
                ('{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":["x"],"arguments":{}}}', -32602),
                ('{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_record","arguments":{}}}',
                 -32602),
                ('{"jsonrpc":"2.0","id":{"a":1},"method":"ping"}', -32600),
                ("[" * 200000 + "]" * 200000, -32700),
                ("not json", -32700),
                ("[]", -32600),
                ("5", -32600),
            ]
            for line, code in bad:
                with self.subTest(line=line[:40]):
                    resp = send(line)
                    self.assertEqual(resp["error"]["code"], code, resp)
                    self.assertEqual(rpc("ping")["result"], {})   # still alive
            batch = send(json.dumps([{"jsonrpc": "2.0", "id": 90, "method": "ping"}, 7,
                                     {"jsonrpc": "2.0", "id": 91, "method": "tools/call", "params": "x"}]))
            self.assertEqual([r.get("error", {}).get("code") for r in batch], [None, -32600, -32602])
            _, studies = tool("list_studies")
            h = studies["studies"][0]["study"]
            self.assertEqual(studies["studies"], [{"study": h}])   # no arm count
            self.assertRegex(h, r"^st-[0-9a-f]{12}$")
            for refused in ({"study": "STUDYSECRET"}, {"study": h, "arm": "a1"}, {"study": h, "seed": 5}):
                r, e = tool("open_session", **refused)
                self.assertTrue(r["isError"])
            rng = random.Random(3)
            for _ in range(3):
                _, o = tool("open_session", study=h)
                sid, st = o["session"], o["state"]
                self.assertNotIn("key", o)   # stdio: one client, no keys
                steps = 0
                while not st["done"]:
                    r, badr = tool("step", session=sid, answers=answer(st, rng, bad=True))
                    self.assertIn("error", badr["state"])          # same State + error
                    self.assertEqual(badr["state"]["step"], st["step"])
                    _, nxt = tool("step", session=sid, answers=answer(st, rng))
                    st = nxt["state"]
                    steps += 1
                self.assertEqual(steps, 3)
                tool("get_state", session=sid)
                r, done = tool("step", session=sid, answers={})
                self.assertEqual(done["error"], "session is done")
                for refused in ("get_record", "score"):        # operator tools do not exist here
                    resp = rpc("tools/call", {"name": refused, "arguments": {"session": sid, "study": "STUDYSECRET"}})
                    self.assertEqual(resp["error"]["code"], -32602)
            self.assertIn("error", rpc("no/such"))
        finally:
            proc.stdin.close()
            proc.wait(timeout=10)
            proc.stdout.close()
            proc.stderr.close()
        blob = "".join(raw)
        self.assertGreater(len(raw), 20)
        for badw in (MARK, "hypothesis", "treatment", "control", "excluded", "flags"):
            self.assertNotIn(badw, blob, "participant-mode output contains %r" % badw)

    def test_malformed_in_process(self):
        mcp = MCP(self.server())
        cases = [
            ({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": "x"}, -32602),
            ({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": 3}}, -32602),
            ({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "step", "arguments": [1]}},
             -32602),
            ({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "nope"}}, -32602),
            ({"jsonrpc": "1.0", "id": 1, "method": "ping"}, -32600),
            ({"jsonrpc": "2.0", "id": 1, "method": 5}, -32600),
            ("x", -32600),
        ]
        for msg, code in cases:
            with self.subTest(msg=str(msg)[:60]):
                self.assertEqual(mcp.handle(msg)["error"]["code"], code)
        self.assertEqual(respond(mcp, "{" * 100000)["error"]["code"], -32700)
        self.assertEqual(respond(mcp, "[]")["error"]["code"], -32600)
        # argument types inside a known tool: a tool error, not a crash
        for args in ({"session": ["x"], "answers": {}}, {"session": "s", "answers": "x"},
                     {"session": {"a": 1}}, {"study": 5}):
            r = mcp.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                            "params": {"name": "step" if "answers" in args else "open_session"
                                       if "study" in args else "get_state", "arguments": args}})
            self.assertTrue(r["result"]["isError"], r)
        # an unexpected exception inside a tool becomes an error result; a crash in dispatch becomes -32603
        orig = mcp.server.list_studies
        mcp.server.list_studies = lambda: 1 / 0
        r = mcp.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "list_studies"}})
        self.assertTrue(r["result"]["isError"])
        mcp.server.list_studies = orig
        mcp._dispatch = lambda *a: (_ for _ in ()).throw(RecursionError())
        self.assertEqual(mcp.handle({"jsonrpc": "2.0", "id": 4, "method": "ping"})["error"]["code"], -32603)
        self.assertIsNone(mcp.handle({"jsonrpc": "2.0", "method": "ping"}))   # notification: no reply
        # the stdio loop survives an oversized line
        out = io.StringIO()
        serve_mcp.serve(self.server(), io.StringIO("x" * 500 + "\n" + '{"jsonrpc":"2.0","id":1,"method":"ping"}\n'),
                        out, max_line=60)
        lines = [json.loads(x) for x in out.getvalue().splitlines()]
        self.assertEqual(lines[0]["error"]["code"], -32600)
        self.assertEqual(lines[1]["result"], {})

    def test_session_ids_are_random(self):
        s = self.server()
        h = self.handle(s)
        ids = [s.open_session(h)["session"] for _ in range(6)]
        self.assertEqual(len(set(ids)), 6)
        for i in ids:
            self.assertRegex(i, r"^s-[A-Za-z0-9_-]{20,}$")
        self.assertFalse(any(i in ("s1", "s2", "s6") for i in ids))

    def test_participant_cannot_pick_arm_seed_or_use_real_ids(self):
        s = self.server()
        h = self.handle(s)
        for bad in ({"study": "STUDYSECRET"}, {"study": h, "arm": "ARMSECRET_control"}, {"study": h, "arm": "a1"},
                    {"study": h, "seed": 1}):
            with self.subTest(args=bad):
                with self.assertRaises(ServeError) as cm:
                    call(s, "open_session", bad)
                self.assertNotIn(MARK, str(cm.exception))
        o = s.open_session(h)
        for k in ("arm", "spec", "seed", "study"):
            self.assertNotIn(k, o)
        self.assertNotIn("seed", json.dumps(o))

    def test_balanced_arm_draw_and_operator_assignment(self):
        s = self.server()
        h = self.handle(s)
        op = s.as_operator()
        arms = [op.get_record(s.open_session(h)["session"])["arm"] for _ in range(6)]
        self.assertEqual(sorted(arms), ["ARMSECRET_control"] * 3 + ["ARMSECRET_treatment"] * 3)
        s = self.server(assign={"STUDYSECRET": ["ARMSECRET_control"]})
        op = s.as_operator()
        arms = {op.get_record(s.open_session(self.handle(s))["session"])["arm"] for _ in range(4)}
        self.assertEqual(arms, {"ARMSECRET_control"})

    def test_handles_salted_per_server(self):
        a, b = self.server(), self.server()
        self.assertNotEqual(a.handle("STUDYSECRET"), b.handle("STUDYSECRET"))
        self.assertEqual(a.handle("STUDYSECRET"), a.handle("STUDYSECRET"))
        self.assertEqual(a.list_studies()["studies"][0]["study"], a.handle("STUDYSECRET"))
        self.assertNotEqual(a.handle("STUDYSECRET"), study_handle("STUDYSECRET", ""))
        with self.assertRaises(ServeError):
            a.open_session(b.handle("STUDYSECRET"))

    def test_same_seed_same_states(self):
        a, b = self.server(operator=True), self.server(operator=True)
        rng_a, rng_b = random.Random(1), random.Random(1)
        oa, ob = a.open_session("STUDYSECRET", seed=42), b.open_session("STUDYSECRET", seed=42)
        self.assertEqual(oa["state"], ob["state"])
        self.assertEqual(oa["spec"], ob["spec"])
        sa, sb = oa["state"], ob["state"]
        while not sa["done"]:
            sa = a.step(oa["session"], answer(sa, rng_a))["state"]
            sb = b.step(ob["session"], answer(sb, rng_b))["state"]
            self.assertEqual(sa, sb)

    def test_operator_base_seed_replays_participant_runs(self):
        runs = []
        for _ in range(2):
            s = self.server(base_seed=7)
            h, op = self.handle(s), s.as_operator()
            rs = [op.get_record(s.open_session(h)["session"])["spec"] for _ in range(3)]
            runs.append([(x["arm"], x["seed"]) for x in rs])
        self.assertEqual(runs[0], runs[1])

    def test_state_is_a_diff_unless_asked(self):
        s = self.server()
        h = self.handle(s)
        o = s.open_session(h)
        rng, seen, got = random.Random(0), [], []
        for r in play_single(s, o, rng):
            st = r["state"]
            if "seen" in st:
                self.assertEqual(st["seen_from"], len(got))
                got += st["seen"]
        full = s.as_operator().get_state(o["session"])["state"]   # the operator sees whole States
        self.assertNotIn("seen_from", full)
        o2 = s.open_session(h)
        r = s.step(o2["session"], answer(o2["state"], rng))
        r = s.step(o2["session"], answer(r["state"], rng))
        self.assertGreater(r["state"]["seen_from"], 0)
        whole = s.get_state(o2["session"], history=True)["state"]
        self.assertEqual(whole["seen_from"], 0)
        self.assertEqual(len(whole["seen"]), r["state"]["seen_from"] + len(r["state"]["seen"]))
        again = s.get_state(o2["session"])["state"]
        self.assertEqual(again["seen"], [])   # nothing new since history=true
        fs = self.server(full_history=True)
        o3 = fs.open_session(self.handle(fs))
        r = fs.step(o3["session"], answer(o3["state"], rng))
        r = fs.step(o3["session"], answer(r["state"], rng))
        self.assertEqual(r["state"]["seen_from"], 0)
        self.assertTrue(r["state"]["seen"])

    def test_session_cap_and_idle_expiry(self):
        s = self.server(max_sessions=2, ttl=60)
        h = self.handle(s)
        a = s.open_session(h)["session"]
        s.open_session(h)
        with self.assertRaises(ServeError) as cm:
            s.open_session(h)
        self.assertEqual(cm.exception.code, 503)
        s.sessions[a]["last"] -= 120   # idle past the ttl
        with self.assertRaises(ServeError):
            s.get_state(a)
        env = s._envs["STUDYSECRET"]
        self.assertEqual(len(env.sessions), 1)   # the engine forgot it too
        s.open_session(h)   # room again

    def test_no_studies_is_a_clear_error(self):
        empty = Path(tempfile.mkdtemp())
        try:
            with self.assertRaises(ServeError) as cm:
                Server(empty)
            self.assertIn("--studies", str(cm.exception))
            with self.assertRaises(ServeError):
                Server(empty / "nope")
            with self.assertRaises(ServeError) as cm:
                Server(self.tmp, studies=["nosuch"])
            self.assertIn("nosuch", str(cm.exception))
            with self.assertRaises(SystemExit) as cm:
                with unittest.mock.patch("sys.stderr", io.StringIO()):
                    serve_mcp.main(["--studies", str(empty)])
            self.assertEqual(cm.exception.code, 2)
        finally:
            shutil.rmtree(empty)

    def test_group_member_sees_only_its_own_state(self):
        s = Server(self.tmp, studies=["GROUPSECRET"])
        h = s.handle("GROUPSECRET")
        a, b = s.open_session(h), s.open_session(h)   # two seats of the same group
        self.assertEqual(s.sessions[a["session"]]["grp"], s.sessions[b["session"]]["grp"])
        for o, pid in ((a, "p1"), (b, "p2")):
            self.assertNotIn("states", o)
            self.assertNotIn("participants", o)
            self.assertEqual(o["state"]["participant"], pid)
        rid = a["state"]["screen"]["responses"][0]["id"]
        with self.assertRaises(ServeError):
            s.step(a["session"], {rid: 1}, participant="p2")   # cannot act for someone else
        ra = s.step(a["session"], {rid: 5})
        self.assertTrue(ra["state"]["waiting"])
        self.assertEqual(set(ra), {"session", "state"})
        again = s.step(a["session"], {rid: 5})
        self.assertIn("waiting for the group", again["error"])
        rb = s.step(b["session"], {rid: 7})
        self.assertEqual(rb["state"]["events"], ["Group total: 12."])
        self.assertEqual(s.get_state(a["session"])["state"]["events"], ["Group total: 12."])
        self.assertNotIn(MARK, json.dumps([a, b, ra, rb]))
        c = s.open_session(h)   # the next participant starts a new group
        self.assertEqual(c["state"]["participant"], "p1")
        self.assertNotEqual(s.sessions[c["session"]]["grp"], s.sessions[a["session"]]["grp"])

    def test_operator_mode_records_and_score(self):
        s = self.server(operator=True)
        names = {t["name"] for t in MCP(s).handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["result"]["tools"]}
        self.assertIn("get_record", names)
        o = s.open_session("STUDYSECRET", arm="ARMSECRET_control", seed=1)
        self.assertEqual(o["arm"], "ARMSECRET_control")
        self.assertEqual(o["spec"]["arm"], "ARMSECRET_control")
        st, rng = o["state"], random.Random(0)
        while not st["done"]:
            st = s.step(o["session"], answer(st, rng))["state"]
        rec = s.get_record(o["session"])["records"][0]
        self.assertEqual(rec["status"], "completed")
        self.assertEqual(len([a for a in rec["answers"] if a["response"] == "RESPSECRET_pick"]), 2)
        sc = s.score("STUDYSECRET", [o["session"]])
        self.assertIn(sc["status"], ("ok", "not_available", "error"))

    def test_participant_mode_refuses_operator_calls(self):
        s = self.server()
        o = s.open_session(self.handle(s))
        self.assertNotIn("spec", o)
        self.assertNotIn("arm", o)
        with self.assertRaises(ServeError):
            s.get_record(o["session"])
        with self.assertRaises(ServeError):
            s.score(self.handle(s))

    def test_http(self):
        srv = self.server()
        httpd = make_server(srv, "127.0.0.1", 0, operator_token="tok-1")
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        port = httpd.server_address[1]
        base = "http://127.0.0.1:%d" % port

        def req(method, path, body=None, token=None, key=None, headers=None):
            data = json.dumps(body).encode() if body is not None else None
            hdr = {"Content-Type": "application/json"}
            if token:
                hdr["Authorization"] = "Bearer " + token
            if key:
                hdr["X-Session-Key"] = key
            hdr.update(headers or {})
            r = urllib.request.Request(base + path, data=data, method=method, headers=hdr)
            try:
                with urllib.request.urlopen(r) as f:
                    return f.status, f.read().decode()
            except urllib.error.HTTPError as e:
                return e.code, e.read().decode()

        def raw_http(head, body=b""):
            with socket.create_connection(("127.0.0.1", port), timeout=5) as c:
                c.sendall(head.encode() + b"\r\n\r\n" + body)
                c.shutdown(socket.SHUT_WR)
                data = b""
                while True:
                    x = c.recv(65536)
                    if not x:
                        break
                    data += x
            return int(data.split(b" ")[1])

        try:
            raw = []
            code, body = req("GET", "/studies")
            raw.append(body)
            h = json.loads(body)["studies"][0]["study"]
            code, body = req("POST", "/sessions", {"study": h, "seed": 2})
            self.assertEqual(code, 400)   # seed is the server's
            code, body = req("POST", "/sessions", {"study": "STUDYSECRET"})
            self.assertEqual(code, 404)   # real ids are not accepted
            code, body = req("POST", "/sessions", {"study": h})
            raw.append(body)
            self.assertEqual(code, 200)
            o = json.loads(body)
            sid, key = o["session"], o["key"]
            self.assertEqual(req("GET", "/sessions/%s" % sid)[0], 404)              # no key
            self.assertEqual(req("GET", "/sessions/%s" % sid, key="wrong")[0], 404)  # wrong key
            self.assertEqual(req("GET", "/sessions/%s" % sid, key=key)[0], 200)
            st, rng = o["state"], random.Random(2)
            self.assertEqual(req("POST", "/sessions/%s/step" % sid, {"answers": answer(st, rng)})[0], 404)
            while not st["done"]:
                code, body = req("POST", "/sessions/%s/step" % sid, {"answers": answer(st, rng)}, key=key)
                raw.append(body)
                st = json.loads(body)["state"]
            code, body = req("POST", "/tools/get_state", {"arguments": {"session": sid, "key": key, "history": True}})
            self.assertEqual(code, 200)
            code, body = req("GET", "/sessions/%s/record" % sid)
            raw.append(body)
            self.assertEqual(code, 403)
            code, body = req("POST", "/score", {"study": h})
            self.assertEqual(code, 403)
            code, _ = req("GET", "/sessions/%s/record" % sid, token="wrong")
            self.assertEqual(code, 403)
            code, body = req("GET", "/sessions/%s/record" % sid, token="tok-1")   # operator token
            self.assertEqual(code, 200)
            self.assertEqual(json.loads(body)["records"][0]["status"], "completed")
            code, body = req("GET", "/nope")
            self.assertEqual(code, 404)
            # hardening (review 1 A6)
            self.assertEqual(req("GET", "/studies", headers={"Host": "evil.example"})[0], 421)
            self.assertEqual(req("GET", "/studies", headers={"Host": "localhost:%d" % port})[0], 200)
            self.assertEqual(req("POST", "/sessions", {"study": h}, headers={"Origin": "http://evil.example"})[0], 403)
            self.assertEqual(req("POST", "/sessions", {"study": h}, headers={"Origin": "null"})[0], 403)
            self.assertEqual(req("POST", "/sessions", {"study": h}, headers={"Sec-Fetch-Site": "cross-site"})[0], 403)
            self.assertEqual(req("POST", "/sessions", {"study": h}, headers={"Content-Type": "text/plain"})[0], 415)
            self.assertEqual(req("POST", "/sessions", {"study": h},
                                 headers={"Origin": "http://127.0.0.1:%d" % port})[0], 200)
            hd = "POST /sessions HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Type: application/json\r\nContent-Length: %s"
            self.assertEqual(raw_http(hd % "999999999999"), 413)
            self.assertEqual(raw_http(hd % "-5"), 400)
            self.assertEqual(raw_http(hd % "abc"), 400)
            self.assertEqual(raw_http(hd % "1", b"{"), 400)
            self.assertEqual(req("GET", "/studies")[0], 200)   # still serving
            self.assertNotIn(MARK, "".join(raw))
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_http_operator_needs_token(self):
        with self.assertRaises(ValueError):
            make_handler(self.server(operator=True))
        err = io.StringIO()
        with unittest.mock.patch("sys.stderr", err):
            self.assertEqual(serve_http.main(["--operator", "--studies", str(self.tmp)]), 2)
            self.assertEqual(serve_http.main(["--host", "0.0.0.0", "--studies", str(self.tmp)]), 2)
        self.assertIn("HSENV_OPERATOR_TOKEN", err.getvalue())

    def test_http_no_operator_view_without_token(self):
        httpd = make_server(self.server(), "127.0.0.1", 0)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            r = urllib.request.Request("http://127.0.0.1:%d/score" % httpd.server_address[1],
                                       data=b'{"study": "STUDYSECRET"}', method="POST",
                                       headers={"Content-Type": "application/json", "Authorization": "Bearer "})
            with self.assertRaises(urllib.error.HTTPError) as cm:
                urllib.request.urlopen(r)
            self.assertEqual(cm.exception.code, 403)
        finally:
            httpd.shutdown()
            httpd.server_close()


class Round2(unittest.TestCase):
    """Review 2 (2026-11-08): scoring log shared by views, per-client arms, group expiry, HTTP plumbing."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = _tmp_studies(P, PG)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def server(self, **kw):
        kw.setdefault("studies", ["STUDYSECRET"])
        return Server(self.tmp, **kw)

    def serve(self, srv, **kw):
        httpd = make_server(srv, "127.0.0.1", 0, **kw)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        port = httpd.server_address[1]

        def req(method, path, body=None, headers=None):
            hdr = dict({"Content-Type": "application/json"}, **(headers or {}))
            r = urllib.request.Request("http://127.0.0.1:%d%s" % (port, path),
                                       data=json.dumps(body).encode() if body is not None else None,
                                       method=method, headers=hdr)
            try:
                with urllib.request.urlopen(r) as f:
                    return f.status, json.loads(f.read().decode())
            except urllib.error.HTTPError as e:
                return e.code, json.loads(e.read().decode() or "{}")
        return req, port

    def test_http_score_counts_participant_operator_and_expired_sessions(self):
        srv = self.server()
        req, _ = self.serve(srv, operator_token="tok")
        op = {"Authorization": "Bearer tok"}
        h = req("GET", "/studies")[1]["studies"][0]["study"]
        rng = random.Random(4)
        played = []
        for _ in range(2):   # two participants finish
            code, o = req("POST", "/sessions", {"study": h})
            self.assertEqual(code, 200)
            st = o["state"]
            while not st["done"]:
                st = req("POST", "/sessions/%s/step" % o["session"], {"answers": answer(st, rng)},
                         {"X-Session-Key": o["key"]})[1]["state"]
            played.append(o["session"])
        code, quit_ = req("POST", "/sessions", {"study": h})   # a third participant leaves after one screen
        code, o = req("POST", "/sessions", {"study": "STUDYSECRET", "arm": "ARMSECRET_control", "seed": 3},
                      headers=op)   # the operator opens one too
        self.assertEqual(code, 200)
        srv.sessions[quit_["session"]]["last"] -= 10 ** 6   # idle past the TTL
        code, sc = req("POST", "/score", {"study": h}, headers=op)
        self.assertEqual(code, 200, sc)
        self.assertEqual(sc["status"], "ok", sc)
        self.assertEqual(sum(sc["opened_per_arm"].values()), 4)
        self.assertEqual(sc["expired_by_ttl"], 1)
        self.assertNotIn(quit_["session"], srv.sessions)
        self.assertIsInstance(srv._opened[2]["members"][0], serve_mod._Gone)   # compact after expiry
        self.assertEqual(req("POST", "/score", {"study": h, "run": ["x"]}, headers=op)[1]["status"], "error")

    def test_views_share_one_opening_log(self):
        s = self.server()
        a, b = s.as_participant(), s.as_operator()
        a.open_session(a.handle("STUDYSECRET"))
        b.open_session("STUDYSECRET")
        self.assertIs(a._opened, b._opened)
        self.assertEqual(len(s._opened), 2)

    def test_one_client_one_arm(self):
        s = self.server()
        mcp = MCP(s)   # the stdio client
        h = s.handle("STUDYSECRET")
        sids = [mcp.handle({"jsonrpc": "2.0", "id": k, "method": "tools/call",
                            "params": {"name": "open_session", "arguments": {"study": h}}})
                ["result"]["structuredContent"]["session"] for k in range(4)]
        self.assertEqual(len({s.sessions[x]["arm"] for x in sids}), 1)
        s = self.server()
        h = s.handle("STUDYSECRET")
        anon = {s.sessions[s.open_session(h)["session"]]["arm"] for _ in range(4)}   # no client: balanced
        self.assertEqual(len(anon), 2)
        capped = self.server(opens_per_client=1)
        capped.open_session(capped.handle("STUDYSECRET"), client="c1")
        with self.assertRaises(ServeError) as cm:
            capped.open_session(capped.handle("STUDYSECRET"), client="c1")
        self.assertEqual(cm.exception.code, 429)
        capped.open_session(capped.handle("STUDYSECRET"), client="c2")

    def test_http_participant_tokens(self):
        srv = self.server(participant_tokens=["pA", "pB"])
        req, _ = self.serve(srv)
        h = req("GET", "/studies")[1]["studies"][0]["study"]
        self.assertEqual(req("POST", "/sessions", {"study": h})[0], 401)
        self.assertEqual(req("POST", "/sessions", {"study": h}, {"X-Participant-Token": "nope"})[0], 401)
        arms = {}
        for tok in ("pA", "pA", "pA", "pB", "pB"):
            code, o = req("POST", "/sessions", {"study": h}, {"X-Participant-Token": tok})
            self.assertEqual(code, 200)
            arms.setdefault(tok, set()).add(srv.sessions[o["session"]]["arm"])
        self.assertEqual([len(v) for v in arms.values()], [1, 1])
        self.assertNotEqual(arms["pA"], arms["pB"])   # balanced across clients

    def test_expired_seat_ends_the_group(self):
        s = Server(self.tmp, studies=["GROUPSECRET"])
        h = s.handle("GROUPSECRET")
        a, b = s.open_session(h), s.open_session(h)
        rid = a["state"]["screen"]["responses"][0]["id"]
        self.assertTrue(s.step(a["session"], {rid: 5})["state"]["waiting"])
        s.sessions[b["session"]]["last"] -= 10 ** 6
        st = s.get_state(a["session"])["state"]
        self.assertTrue(st["done"])
        self.assertIn("ended", st)
        self.assertEqual(s.step(a["session"], {rid: 5})["error"], "session is done")
        c = s.open_session(h)   # a new group, not the dead one
        self.assertNotEqual(s.sessions[c["session"]]["grp"], s.sessions[a["session"]]["grp"])
        self.assertEqual(len({r["gid"] for r in s._opened[:2]}), 1)   # the two seats count as one group

    def test_list_studies_takes_the_lock(self):
        s = self.server()
        got = []
        with s.lock:
            th = threading.Thread(target=lambda: got.append(s.list_studies()))
            th.start()
            th.join(0.3)
            self.assertEqual(got, [])
        th.join(5)
        self.assertEqual(len(got), 1)

    def test_score_tool_offers_all_only(self):
        sc = next(t for t in serve_mod.tools(True) if t["name"] == "score")
        self.assertEqual(sc["inputSchema"]["properties"]["run"]["enum"], ["all"])
        self.assertNotIn("session ids", (ROOT / "SERVE.md").read_text())

    def test_origin_port_and_host_parsing(self):
        req, port = self.serve(self.server())
        h = req("GET", "/studies")[1]["studies"][0]["study"]
        self.assertEqual(req("POST", "/sessions", {"study": h}, {"Origin": "http://localhost:9999"})[0], 403)
        self.assertEqual(req("POST", "/sessions", {"study": h}, {"Origin": "http://localhost:%d" % port})[0], 200)
        for bad in ("[::1]evil:80", "127.0.0.1.evil.com", "localhost.", "", "a:b:c"):
            self.assertEqual(req("GET", "/studies", headers={"Host": bad})[0], 421, bad)
        self.assertEqual(serve_http._host_name("[::1]:8080"), "[::1]")

    def test_slow_client_times_out(self):
        httpd = make_server(self.server(), "127.0.0.1", 0, timeout=1)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        t0 = time.monotonic()
        with socket.create_connection(("127.0.0.1", httpd.server_address[1]), timeout=10) as c:
            c.sendall(b"POST /sessions HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Type: application/json\r\n"
                      b"Content-Length: 100\r\n\r\n{")
            while c.recv(65536):   # the server gives up and closes
                pass
        self.assertLess(time.monotonic() - t0, 5)


class Round3(unittest.TestCase):
    """Review 3 (2026-11-08): no null text is ever served; score runs outside the lock with a cached baseline."""

    def test_participant_server_refuses_a_null_text_screen(self):
        gap = {"id": "GAPSECRET", "data": {"missing": {"t": {"text": None, "cite": {"label": "missing", "source": "p"}}}},
               "arms": [{"id": "ARMSECRET_a", "n_paper": 2}],
               "stages": {"STAGESECRET_s": {"content": [{"id": "i", "value": {"expr": "data['missing']['t']"}}],
                                            "responses": [{"id": "r", "kind": "number", "prompt": "Age?"}]}},
               "flow": {"seq": [{"stage": "STAGESECRET_s"}]}, "units": {}, "exclusions": [], "keyed": {"answers": {}}}
        d = _tmp_studies(gap)
        self.addCleanup(shutil.rmtree, d)
        s = Server(d)
        with self.assertRaises(ServeError) as cm:
            s.open_session(s.handle("GAPSECRET"))
        self.assertEqual(str(cm.exception), serve_mod.GENERIC_ERROR)
        o = s.as_operator().open_session("GAPSECRET")   # the operator may look at it
        self.assertIsNone(o["state"]["screen"]["items"][0]["text"])
        self.assertTrue(serve_mod._null_text(o["state"]))
        self.assertFalse(serve_mod._null_text({"screen": {"items": [{"type": "text", "text": "Hi"}],
                                                          "responses": [{"prompt": "", "options": [{"label": "a"}]}]}}))

    def test_score_runs_outside_the_lock_and_caches_the_baseline(self):
        from hsenv import evaldata
        d = _tmp_studies(P)
        self.addCleanup(shutil.rmtree, d)
        s = Server(d, operator=True)
        rng = random.Random(1)
        for arm in ("ARMSECRET_treatment", "ARMSECRET_control"):
            o = s.open_session("STUDYSECRET", arm=arm, seed=2)
            st = o["state"]
            while not st["done"]:
                st = s.step(o["session"], answer(st, rng))["state"]
        live = s.open_session("STUDYSECRET", arm="ARMSECRET_control", seed=3)   # still running while we score
        calls, free = [], []
        real = evaldata.baseline_run

        def spy(*a, **k):
            calls.append(1)
            got = []
            th = threading.Thread(target=lambda: got.append(s.lock.acquire(timeout=2) and (s.lock.release() or True)))
            th.start()
            th.join()
            free.append(got == [True])
            # a participant steps the live session while rewards are being computed
            s.step(live["session"], answer(live["state"], rng))
            return real(*a, **k)
        with unittest.mock.patch.object(evaldata, "baseline_run", spy):
            a = s.score("STUDYSECRET")
            b = s.score("STUDYSECRET")
        self.assertEqual(free, [True])        # another thread could take the lock during the computation
        self.assertEqual(len(calls), 1)       # the second score reused the cached baseline
        self.assertEqual(a["status"], "ok", a)
        self.assertEqual(b["status"], "ok", b)
        self.assertEqual(a["opened_per_arm"], b["opened_per_arm"])


def _forbidden_tokens(p):
    """Author-written ids and conditions of a real protocol that are not themselves screen text."""
    ids = {p.id} | {a["id"] for a in p.arms} | set(p.stages) | {x["id"] for x in p.exclusions} | set(p.units)
    for st in p.stages.values():
        ids |= {c["id"] for c in st.get("content", []) if "id" in c}
        for r in st.get("responses", []):
            ids.add(r["id"])
            if isinstance(r.get("options"), list):
                ids |= {str(o["code"]) for o in r["options"] if isinstance(o, dict) and "code" in o}
    ids |= set(p.vars) | set((p.raw.get("keyed") or {}).get("answers", {}))
    screen = set(checks.screen_strings(p))
    return {x for x in ids if isinstance(x, str) and len(x) >= 3 and x not in screen}


def _strings(o, vals=None, keys=None):
    """(string values, dict keys) anywhere in o."""
    vals, keys = (set(), set()) if vals is None else (vals, keys)
    if isinstance(o, dict):
        for k, v in o.items():
            keys.add(k)
            _strings(v, vals, keys)
    elif isinstance(o, list):
        for v in o:
            _strings(v, vals, keys)
    elif isinstance(o, str):
        vals.add(o)
    return vals, keys


# keys the code itself writes (State / response schema): a stage that happens to be named "responses" is not a leak
CODE_KEYS = set(re.findall(r'"([A-Za-z_]+)"', (ROOT / "hsenv" / "engine.py").read_text() +
                           (ROOT / "hsenv" / "serve.py").read_text() + (ROOT / "hsenv" / "serve_mcp.py").read_text()))


def _accepted(server, session, rid, fallback):
    """Operator-side helper for the test player only: the value a quiz response accepts (validate.equals)."""
    e = server.sessions[session]
    sess = e["member"] if e.get("grp") is not None else e["obj"]
    for r in sess._page["responses"]:
        if r["view"]["id"] == rid:
            v = r["def"].get("validate") or {}
            if v.get("equals") is not None:
                return sess.ev(v["equals"], r["bindings"])
            if "min" in v:
                return v["min"]
    return fallback


class StudyPlayer:
    """Whole sessions of a protocol over MCP (in-process): no author id appears as any key or value, and no
    operator-only text (cite notes, evidence, conflicts, rules) appears anywhere. A mixin: the private suite
    (kept outside this package) plays real studies with it."""

    STUDIES = FIXTURES

    def play(self, study, sessions=2):
        root = Path(self.STUDIES)
        if not (root / study / "protocol.json").is_file():
            self.skipTest("%s not present" % study)
        p = Protocol.load(root / study)
        server = Server(root, operator=False, studies=[study])
        mcp = MCP(server)
        forbidden, secret = _forbidden_tokens(p), checks.operator_strings(p)
        n = [0]

        def tool(name, **args):
            n[0] += 1
            resp = mcp.handle({"jsonrpc": "2.0", "id": n[0], "method": "tools/call",
                               "params": {"name": name, "arguments": args}})
            text = json.dumps(resp, ensure_ascii=False)
            vals, keys = _strings(resp)
            hits = (forbidden & vals) | ((forbidden - CODE_KEYS) & keys)
            self.assertFalse(hits, "%s: author ids in a participant response: %s" % (study, sorted(hits)[:5]))
            for s in secret:
                self.assertNotIn(s, text)
            return resp["result"].get("structuredContent")

        h = tool("list_studies")["studies"][0]["study"]
        rng, pool = random.Random(0), checks.text_pool(p)
        for _ in range(sessions):
            first = tool("open_session", study=h)
            seats = {first["session"]: first["state"]}
            g = server.sessions[first["session"]].get("grp")
            for _ in range(len(g["free"]) if g else 0):   # fill the group: one seat per participant
                o = tool("open_session", study=h)
                seats[o["session"]] = o["state"]
            last, tries = {}, {}
            for _ in range(20000):
                live = [k for k, st in seats.items() if not st.get("done")]
                if not live:
                    break
                moved = False
                for sid in live:
                    st = seats[sid]
                    if st.get("waiting"):
                        seats[sid] = tool("get_state", session=sid)["state"]
                        continue
                    ans = checks.random_answers(st, rng, pool=pool)
                    err = st.get("error")
                    if isinstance(err, dict) and last.get(sid):   # refused: keep accepted answers, walk the rest
                        t = tries.setdefault(sid, {})
                        for r in st["screen"]["responses"]:
                            if r["id"] not in err and r["id"] in last[sid]:
                                ans[r["id"]] = last[sid][r["id"]]
                            elif r["id"] in err and r.get("options"):
                                k = t[r["id"]] = t.get(r["id"], -1) + 1
                                ans[r["id"]] = r["options"][k % len(r["options"])]["code"]
                            elif r["id"] in err:   # a computed quiz answer: the test reads it on the operator side
                                ans[r["id"]] = _accepted(server, sid, r["id"], ans[r["id"]])
                    else:
                        tries[sid] = {}
                    last[sid] = ans
                    o = tool("step", session=sid, answers=ans)
                    seats[sid] = o["state"]
                    moved = True
                if not moved:   # everyone waits: a barrier that never releases
                    self.fail("%s: every live participant is waiting" % study)
            else:
                self.fail("%s: session did not finish" % study)



class FixtureStudies(StudyPlayer, unittest.TestCase):
    """The player over invented protocols: the synthetic SECRET study, the 2-person group and the CC0 fixture."""

    @classmethod
    def setUpClass(cls):
        cls.STUDIES = _tmp_studies(P, PG)
        shutil.copytree(FIXTURES / "fixture_mini", cls.STUDIES / "fixture_mini")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.STUDIES, ignore_errors=True)

    def test_synthetic_study(self):
        self.play("STUDYSECRET")

    def test_group_study(self):
        self.play("GROUPSECRET", sessions=1)

    def test_fixture_study(self):
        self.play("fixture_mini")


if __name__ == "__main__":
    unittest.main()
