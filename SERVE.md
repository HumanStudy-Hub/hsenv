# Serving hsenv to outside agents (DESIGN.md §9)

Two thin doors onto the same engine, stdlib only. `hsenv/serve.py` holds the shared core; neither door changes
how a study runs.

| Door | Command |
|---|---|
| MCP (JSON-RPC 2.0 over stdio) | `python3 -m hsenv.serve_mcp [--studies DIR] [--only id1,id2] [--arm study:arm ...] [--seed N] [--operator]` |
| HTTP (JSON) | `python3 -m hsenv.serve_http [--port 8765] [--host 127.0.0.1] [--allow-host NAME] [--studies DIR] [--only ...] [--arm ...] [--seed N]` |

Both also take `--max-sessions N` (default 256, `$HSENV_MAX_SESSIONS`), `--ttl SEC` (default 7200, `$HSENV_TTL`),
`--max-opens N` (sessions per client and study) and `--full-history`; HTTP also takes `--participant-tokens FILE`. Install the package (`pip install git+https://github.com/HumanStudy-Hub/hsenv@v0.8.1`), or run from a clone of this repository. Use Python
3.11 or later, because `score` needs it. Installed from the wheel, the server has no studies of its own: pass
`--studies DIR` (or `HSENV_STUDIES`). A server that finds no studies, or an `--only` id it cannot find, stops
with an error (exit 2) instead of serving an empty list.

## Tools

| Tool | Mode | Returns |
|---|---|---|
| `list_studies` | both | participant: `[{study: "st-xxxxxxxxxxxx"}]` (opaque handles, no arm list); operator: ids, titles, arms, n, which arms the server assigns |
| `open_session(study)` | participant | `{session, state}` (+ `key` on HTTP). The server picks the arm and the seed |
| `open_session(study, arm?, seed?)` | operator | `{session, state, study, arm, spec}`; a group arm gives `{session, participants, pending, states, done, ...}` |
| `get_state(session, history?)` | both | the current State; `history: true` resends everything seen and answered |
| `step(session, answers)` | both | the next State, or the same State with `error` (operator group sessions add `participant`) |
| `get_asset(session, ref)` | both | the image a State references as `asset:<id>` |
| `get_record(session)` | operator | record(s) and SessionSpec |
| `score(study)` | operator | `hsenv.rewards` DEFAULT rewards on every session the server opened for the study, in opening order (participant and operator opens, expired ones included as invalid), up to the planned n of valid units per arm; the baseline is the State-only floor at the planned n. `run` accepts only `"all"`: a chosen subset is never scored. `not_available` if rewards cannot be imported |

`answers` is `{response id: value}` using the State's opaque ids: an option code (`"o2"`), a number in range,
or text. `_elapsed_ms` is optional. Unknown arguments are refused.

HTTP routes are `GET /studies`, `POST /sessions`, `GET /sessions/{id}[?history=1]`, `POST /sessions/{id}/step`,
`GET /sessions/{id}/assets/{ref}`, `GET /sessions/{id}/record`, `POST /score`, and `POST /tools/{name}`
(body `{"arguments": {...}}`). Session calls carry the session's key in the `X-Session-Key` header (or as `key`
in the body or arguments).

## Modes

- **Participant mode** is the default. A response carries the caller's own State and nothing else. Engine errors
  come back as a generic message, and `get_record` and `score` are refused. This follows DESIGN §2 rule 4: the
  SessionSpec is operator-only.
  - **Assignment.** The participant names only a study handle. The server assigns the arm by a balanced draw:
    the allowed arm with the fewest sessions so far, ties broken at random. The operator sets the allowed arms
    with `--arm study:arm` (repeatable; Python: `Server(assign={study: [arms]})`). By default every runnable arm
    is allowed. The session seed is drawn from a hidden base seed. It is random unless the operator sets
    `--seed N`, and with the same base seed and the same sequence of opens, a server run replays exactly. A
    participant cannot pass `arm` or `seed`, and real study or arm ids are refused.
  - **One client, one arm.** A known client always gets the same arm of a study, however often it opens, so
    it cannot open twice to compare conditions. On stdio MCP the client is the one process on the pipe. On HTTP
    it is an operator-issued participant token: start with `--participant-tokens FILE` (one token per line),
    and every open then needs `X-Participant-Token` (401 without one). `--max-opens N` also caps how many
    sessions a client may open per study (429 beyond). Without participant tokens, HTTP clients are anonymous
    and each open is a fresh balanced draw. For a between-subjects run, give each agent its own token, or its
    own stdio server.
  - **Handles.** A handle is `st-` followed by 12 hex characters of sha256(salt | study id). The salt is random
    for each server run. A handle stays the same for the life of one server process and changes on restart, so
    it cannot be computed from a public id. Hand participants the handle from that run's `list_studies`.
  - **Groups.** Each `open_session` on a group arm takes one seat. The first seat starts a new group, and later
    opens of the same study fill that group before a new one starts. Every seat is its own session: it answers
    for its own participant only and sees only its own screen. Members meet at the protocol's `sync` barriers.
    If a seat expires (TTL), the group can never finish: it ends for everyone, and the other seats get
    `done: true` with `ended` (their members are scored as unfinished).
    While a member waits, `step` returns its State with `waiting: true` and an error. Poll `get_state`. One agent
    may hold every seat, but it still sees them one at a time.
  - **Payload.** A State is sent as a diff. `seen` and `answered` hold only the entries that are new since this
    session's last response. `seen_from` and `answered_from` give their index in the whole list, and
    `seen_updates` re-flags an earlier entry whose `reviewable` changed. `get_state(history=true)` resends the
    whole list once. The operator can turn diffs off with `--full-history`. An operator view always gets whole
    States, and looking at them does not move the participant's diff.
- **Operator mode** is turned on with `--operator` or `HSENV_MODE=operator`. It adds real ids, the choice of arm
  and seed, whole-group sessions (`participant` on `step`), the SessionSpec, records and scores. Never give an
  operator server to the agent being studied.

`tests/test_serve.py` plays whole sessions over a real stdio MCP subprocess and over HTTP, and asserts that no id,
condition, key or rule appears in any response. It also plays `mystudy2024` and the group study
`otherstudy2018` (one seat per member), checking every response for author ids and operator-only text.

## Sessions and limits

- Session ids are `s-` + `secrets.token_urlsafe(16)`, so they reveal nothing and cannot be guessed.
- **Binding.** A stdio MCP server has exactly one client, so the pipe binds the sessions to that client. On HTTP,
  `open_session` returns a `key` once, and every later call on that session must carry it. A missing or wrong
  key gets the same 404 as an unknown session.
- At most `--max-sessions` sessions are live at once; beyond that `open_session` answers 503 (HTTP) or an error
  (MCP). A session nobody has touched for `--ttl` seconds is dropped; `get_record` can no longer read it.
  `score` still counts it, because an opening log, which every view of the server shares, keeps one compact
  entry per opened session. That entry holds the arm and the finished members' records; an unfinished member
  becomes a stub that scores as invalid.
- `score` holds the server lock only while it takes a snapshot of the log. Then it computes the rewards with the
  lock released, so participants keep stepping. A session still running at snapshot time scores as unfinished.
  The baseline (the State-only floor) is computed once per study, protocol version and planned n, and is reused.
- A participant server never serves a screen whose item text, prompt or option label is null (a missing gap,
  DESIGN §2 rule 2). The participant gets the generic error instead. `schema_check` and `checks.play` catch
  such a gap earlier, at build time.
- Sessions live in memory and are lost on restart. The same operator seed (and arm) gives the same States.
  Balanced randomisers count across all of a study's sessions on one server, just as they do within one `Env`.

## Robustness and HTTP hardening

- **MCP.** No message can stop the server. A line that is not JSON, or JSON nested too deeply, gets -32700. A
  malformed request, an empty batch or a line over 4 MB gets -32600. Params or arguments that are not objects,
  a tool name that is not a string, or an unknown tool get -32602. Anything unexpected gets -32603. A tool that
  fails returns an `isError` result.
- **HTTP.**
  - It binds `127.0.0.1` by default. Binding anything else requires `--allow-host <name>` and prints a warning.
  - The `Host` header must be a loopback name or an `--allow-host` name; otherwise the request gets 421. This
    stops DNS rebinding.
  - A request with an `Origin` other than this server's own (an allowed host *and* this port), or with
    `Sec-Fetch-Site: cross-site`, gets 403. Agents send no `Origin`.
  - A POST must be `Content-Type: application/json`, or it gets 415. Together with the `Origin` check, this
    stops cross-site form posts.
  - `Content-Length` must be an integer from 0 to 1 MB. A larger value gets 413, and a bad or negative one gets
    400. A chunked body gets 411. A client that stops sending loses its handler thread after 30 s.
  - The operator view is only ever behind `HSENV_OPERATOR_TOKEN`. `--operator` without the token refuses to
    start.

## Claude Code / Claude Desktop config

Claude Code (`.mcp.json` in the project, or `claude mcp add`):

```json
{
  "mcpServers": {
    "hsenv": {
      "command": "python3",
      "args": ["-m", "hsenv.serve_mcp", "--studies", "/path/to/studies", "--only", "mystudy"],
      "env": {"HSENV_MODE": "participant"}
    }
  }
}
```

```bash
claude mcp add hsenv -e HSENV_MODE=participant \
  -- python3 -m hsenv.serve_mcp --studies /path/to/studies --only mystudy
```

Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "hsenv": {
      "command": "python3",
      "args": ["-m", "hsenv.serve_mcp", "--studies", "/path/to/studies", "--only", "mystudy"],
      "env": {"HSENV_MODE": "participant"}
    }
  }
}
```

Sessions are in memory, so `score` and `get_record` only see sessions run on the same server. There are two
ways to read a participant's run:

- **HTTP:** start the server with `HSENV_OPERATOR_TOKEN=<secret>`. Requests carrying
  `Authorization: Bearer <secret>` get the operator view of the same sessions; all other requests get the
  participant view.
- **Python:** `srv = hsenv.serve.Server(studies_dir)`, then pass `srv` to the participant door and use
  `srv.as_operator()` yourself.

A stdio MCP server has a single client, so give it to the participant and never start it with `--operator`.

The provenance of an outside run (model, how States were rendered, retries allowed; DESIGN §9) is the
operator's to record. The server does not guess it.
