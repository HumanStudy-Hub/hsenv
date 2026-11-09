# hsenv

hsenv is the protocol engine behind HumanStudy Hub. A behavioural experiment is written down once as a
declarative `protocol.json`: what each participant saw, in what order, what they could answer, and how the
source analysed it, with every item cited. hsenv runs that protocol step by step for any participant (a language
model, a chat, a script, a person), records typed answers, and compares the resulting population with the human
numbers.

- **Gym-style sessions.** `reset()` returns a State (only what was on the participant's screen, with opaque ids);
  `step(answers)` validates typed answers against the stage's response spaces and returns the next State, or the
  same State with an `error`. Conditions, keys, hypotheses and exclusion rules never reach a State.
- **No agent design.** The engine does not prompt anyone. How a State becomes a prompt, and what memory or model
  is used, is the operator's choice and goes into the run's provenance.
- **Checks** (`hsenv-check`): reference integrity, fuzzing for leaks and unreachable stages, verbatim checks of
  served text against source text, coding rules against their cases, paper self-consistency. No model calls.
- **Evaluation as an offline report, not a leaderboard** (`hsenv.evaldata`, `hsenv.rewards`, `hsenv-score`):
  significance and direction match, effect gap, share within the human sampling range, and a human-noise score
  where 1 means "as close as a fresh human sample". Missing human numbers are reported as not computable, never
  scored 0.
- **Serving** to outside agents over MCP (stdio) or HTTP (`hsenv-serve-mcp`, `hsenv-serve-http`), with a
  participant view that leaks nothing and an operator view behind a token. See [SERVE.md](SERVE.md).
- **Schemas** for `protocol.json`, `study.json` and `run.json` (JSON Schema 2020-12, shipped in the package) and a
  stdlib validator (`hsenv-schema-check`).

The runtime uses the Python standard library only. Python 3.11 or later.

This repository holds the engine only. It contains no study protocols; the test fixtures are invented.

## Install

```bash
pip install git+https://github.com/HumanStudy-Hub/hsenv@v0.8.0
```

For development:

```bash
git clone https://github.com/HumanStudy-Hub/hsenv && cd hsenv
pip install -e ".[dev]"
python -m pytest
```

## Usage

A study is a folder holding `protocol.json` (plus any local images it cites). The invented two-arm rating study
in `tests/fixtures/studies/fixture_score` is enough to try everything below.

```python
import random
import hsenv.engine as hs

env = hs.make("tests/fixtures/studies/fixture_score")   # reads protocol.json; no study code runs
rng = random.Random(0)

def my_agent(state):
    """Any participant: a model call, a chat, a person, a script. Here: random valid answers."""
    answers = {}
    for r in state["screen"]["responses"]:
        if r["kind"] == "choice":
            answers[r["id"]] = rng.choice(r["options"])["code"]
        else:
            lo, hi = r["range"]
            answers[r["id"]] = rng.randint(lo, hi)
    return answers

for spec in env.design(n=4, seed=7):       # SessionSpecs: arm and draws per session (operator-only)
    s = env.open(spec)
    state = s.reset()
    while not state["done"]:
        state = s.step(my_agent(state))    # an invalid answer returns the same State with "error"

print(env.unit_tables()["p"][:2])          # the protocol's declared unit: one row per session
```

A State looks like this (ids are opaque per session; option codes are `o1`, `o2`, …):

```json
{"participant": "p1", "done": false, "step": 1, "page": 1,
 "screen": {"items": [{"id": "i1", "type": "text", "text": "How sure are you?"}],
            "responses": [{"id": "r1", "kind": "slider", "prompt": "rate", "required": true,
                           "range": [0, 100], "widget": "hslider"}]},
 "seen": [], "answered": [], "events": [], "timing": {"advance": "self"}, "navigation": {"back": "not_allowed"}}
```

Command line:

```bash
hsenv-schema-check tests/fixtures/studies/fixture_mini/protocol.json   # validate against schema v1
hsenv-check tests/fixtures/studies/fixture_score --public               # mechanical checks, JSON report
hsenv-score tests/fixtures/studies/fixture_score --seeds 3              # simulated run -> offline report
hsenv-score --rescore evaldata.json                                     # re-score a kept run
hsenv-serve-mcp --studies tests/fixtures/studies                        # serve to an outside agent (stdio)
```

`hsenv-score` simulates sessions with a built-in policy; to score your own agent's sessions, build
`hsenv.evaldata.EvalData` from your runs and apply `hsenv.rewards.score(ev, reward_id)`, or use the `score` tool of
an operator server (SERVE.md). Every score carries `report_scope: "offline_report — not a leaderboard"`, says
whether it was run at the official (human analysed) n, and records the protocol and code hashes.

## Documentation

- [DESIGN.md](DESIGN.md): the rules, the protocol format, the State, and the evaluation rules.
- [SERVE.md](SERVE.md): the MCP and HTTP servers.
- `schema/*.v1.json`: the machine-readable contracts.

## Licence

MIT, the same as HumanStudy-Bench. See [LICENSE](LICENSE). Test fixtures are invented and dedicated to the
public domain (CC0-1.0).
