# hsenv design (engine extract, v0.8)

This is the public, engine-only part of the HumanStudy sandbox design. Section numbers match the references in
the code (`DESIGN §2 rule 2`, `§3.5`, `§8.7`, `§9`, …); sections about how studies are built and reviewed are
left out. Every example here is invented.

**hsenv does not design the participant agent.** A protocol records, for every stage of an experiment, which
material the human participants got and how it was presented. The engine serves that as States, one step at a
time, takes typed answers, and scores the population. How someone turns a State into a prompt, and what memory or
model they use, is up to them and is not part of the engine.

## 1. What the engine is

```
protocol.json  (one per study: declarative, every item cited; no code)
    │  hsenv.engine.make(study_dir)
    ▼
Env ── reset() ──▶ State ──(anyone's agent)──▶ Answers ── step() ──▶ State … ──▶ done
    │                                                     validated against the stage's response spaces
    ▼
records: one answer table (session, participant, stage, response, value, order)
    │  units + measures (declared) ─▶ effects ─▶ §8 evaluation data ─▶ rewards (offline report)
```

There is one engine for every study: a small interpreter of the protocol. Studies differ only in data.

## 2. Rules

1. **The protocol says what humans got, never how a model should be prompted.** Nothing in it is written for an
   AI: no prompt templates, no memory schemes, no "answer format" instructions humans never saw.
2. **Every item is cited** (`verbatim` / `reported` / `derived` / `missing`, with source and page). On-screen
   content must be `verbatim` (or a cited image/table). A stage whose on-screen content is `missing` makes its arm
   **not runnable**; the engine never serves a placeholder.
3. **Answers are typed values in the stage's response spaces** (option code, number in range, text). The engine
   validates them and never parses prose. Free-text answers that the source codes are stored raw and coded by a
   declared `coding` rule.
4. **Hidden from States:** condition labels, hypotheses, keys, which stage is a check, exclusion rules, human
   results, and every author-written id. States carry only opaque per-session ids (`i1`, `r3`, option codes
   `o1…`) and the labels humans saw. A key reaches a State only where the source shows it as feedback. The
   SessionSpec (conditions, orders) is operator-only and never passed to the agent.
5. **Never invent statistics.** Human numbers come from the protocol's `reported` blocks.

## 3. The protocol (`protocol.json`)

The machine-readable contract is `schema/protocol.v1.json` (validated by `hsenv-schema-check`). This section is
the reading guide.

### 3.1 Top level

```
schema_version  "1"
id, meta        citation, licence, sources, sample description, language
roles           who fills each seat in a group study (agent | scripted) and what they were told
arms            [{id, n_paper, n_analysed?, n_recruited?, group_size?, release_hold?, cite}]
conditions      factors, assignment (between | within | fixed), ratio
data            cited texts, tables and images that stages refer to
flow            a tree of nodes (§3.2): the order of stages for one participant (or one group)
stages          {id: Stage} (§3.3)
vars, rules     environment variables, branching, piped values, computed feedback, scripted moves (§3.4)
units           tables built from answers: {name: {per: session | group, fields: {name: expr}}}
exclusions      per-session and population rules, each cited
analysis        targets (levels) and effects (contrasts) with the reported human numbers (§8)
keyed           a key policy for fuzzing (operator-only)
```

### 3.2 Flow nodes

| Node | Meaning | Invented example |
|---|---|---|
| `seq [n…]` | in order | intro → vignettes → demographics |
| `shuffle [n…] pick=k` | random order (or k of them) per participant | 3 vignettes, random order |
| `assign factor` | draw this participant's level (between) or a permutation (within) | condition per vignette, Latin square |
| `branch if <rule> then n else m` | depends on earlier answers | "incorrect, try again" quiz loops |
| `loop k as i {n}` | k repeated rounds; `i` is readable by rules and items | 10 public-goods periods |
| `for x in [..] {n}` | instantiate a template stage per value | one page per scenario |
| `repeat {n} until <rule> max k on_max …` | retry with the source's feedback; `on_max` (continue / flag / end:<status>) is required | comprehension quiz, at most 3 tries |
| `sync role… {n}` | group stage: waits for every member, then shows computed outcomes | round results |
| `end status` | completed / excluded / screened_out | failed eligibility |

### 3.3 Stage (one screen, or one page of a survey)

```
Stage
  id, role
  content    [Item]           text | image | table | piped(answer ref) | computed(rule ref)
                              each: {value | variants by condition, evidence label, source cite}
  responses  [Response]       {id, kind: choice | multi | number | scale | slider | text | rank,
                               options [{code, label}], range, step, anchors, required, min_chars}
  presentation
    page        which page this is on (several stages may share one page)
    advance     self | timed(sec) | after(min_sec)
    back        allowed | not_allowed | unknown
    time_limit  sec | none
```

**What a State carries** (engine output, the same for every study):

```
State
  participant, step (1-based), page, done
  screen      the Items and Responses on screen now (resolved for this participant's condition and pipes)
  seen        earlier Items no longer on screen: [{stage, item, shown_at_step, reviewable}]
  answered    this participant's own earlier answers
  events      what the environment showed since the last step (feedback, others' moves, payoffs)
  timing      advance / time_limit of this page, as humans had it
  navigation  back allowed or not
  error       only when the last step was refused
```

`seen` and `answered` record facts about what the human experienced. They are not a memory design: whether an
operator passes them to a model, summarises them or drops them is the operator's choice and belongs in the run's
provenance (`schema/run.v1.json`).

The engine has no clock: `advance`, `time_limit` and `min_sec` are shown in `timing` and recorded. Sliders record
their start position; a skipped non-required answer is `null`. Validation errors use the source's own message
where humans saw one.

### 3.4 Rules

`vars` are environment variables with an initial value and an update rule. Rules read `vars`, the loop index,
`attempt`, the participant's own answers and, in group studies, other members' answers.

A small, sandboxed expression language (`hsenv/expr.py`) works over answers and the environment's seeded random
draws: `answer('stage.response')`, comparisons, arithmetic, `count`, `sum`, `mean`, `balanced(...)`, group
aggregates in `sync`. It is used for exclusions, branching, piped text, computed feedback and scripted roles.
Every rule cites where the source states it. **Keys live in rules, never in States** (except as cited feedback).

**Free-text coding** (`coding`): declared kinds only (number normalisation, regex, synonym lists), applied in a
fixed order. Anything uncoded goes to an explicit `uncoded` bucket, never to "other". A reply carrying answer
tokens of two different codes without an explicit answer cue is `needs_coder`: never guessed, held out of shares,
its rate reported. A rule must reproduce its declared `cases`.

### 3.5 Field reference

| Where | Field | Meaning |
|---|---|---|
| data value | `{"text", "spans":[{start,end,style}], "cite"}` | inline emphasis (underline/bold/italic) that can carry a manipulation |
| content item | `style` | whole-item emphasis |
| content item (image) | value `{"src", "lines":[cited text]}`; local files are served as opaque `asset:<sha16>` | the picture and its verified text lines; nothing else reaches a State |
| item / image value | `src` (local) | a regular file inside the study folder: no absolute path, no `..`, no symlink leaving the folder |
| image value | `sha256`, `size: {width, height}` | `--fetch-images` checks every remote src returns these bytes; display size |
| item | value `{"rows": [[cells]]}` | a table as shown; cells may carry integer `colspan` / `rowspan` (≤ 100 / ≤ 1000) and `{"text", "mark"}` |
| item | `reviewable: true` (+ `reviewable_on: [stages]`) | reachable again on later pages |
| stage | `layout: [ids]` (may include `"@button"`) | on-screen order when text and questions interleave |
| stage | `presentation.{back, paging, advance, min_sec, time_limit, button}` | plain values only; evidence in `presentation_cite` |
| stage | `shuffle_responses: true` | questions within a stage in random order; content stays first |
| stage | `single_switch: {responses, from, to, message, enforce}` | price list: rows switch from one option to the other at most once |
| stage | `sum_to: {responses, total, message}` | constant-sum page; the State returns the error and stays |
| stage | `validate_page: [{if_valid, message}]` | rules across a page's answers |
| stage | `required_message_page` | one page-level message when only required answers are missing |
| flow `page` | `shuffle: true` | stages on one page in random order |
| flow | `{"sync": id, "compute": {name: expr}, "events": [texts]}` | group barrier: each member waits; `compute` runs per member (`group(ref)`, `my_index`, `group_size`) |
| flow `end` | `page: <stage>` | a terminal page shown before the session ends |
| response | `range: [min, null]`, `range: {expr}` + `range_visible: false` | open-ended number; an evaluated bound enforced but not shown |
| response | `validate: {min, max, also, contains, pattern, equals, ignore_case, message}` | the survey's own validation; the State returns the error and stays |
| response | `step` (slider), `start`, `start_visible: false` | slider grid; handle position (or `"unknown"`); hidden handle |
| response | `required_message`, `soft_required`, `prefill` | the source's own "please answer" message; a reminder only; a value already in the box |
| response | `widget`, `widget_params`, `columns`, `shows_value`, `gridlines`, `prefix`, `suffix` | how the input looked (plain interface words only) |
| response | `na_option` | a Not Applicable box; answering "NA" stores "NA", distinct from a skipped answer (null) |
| response | `prompt_style`, `instruction` (+ `instruction_cite`) | bold stems; the line between question and input |
| option | `text_entry: true`, `fixed: true` | a text box tied to the option (answer `{"code","text"}`); keeps its place under shuffling |
| rule | `balanced(name, options)` | least-presented-so-far draw across sessions |
| record | `refused` + `refused(stage)`, `refused_errors(stage)` | refused validation attempts (count and values) |
| step | `_elapsed_ms` | optional reserved answer key: time on that screen as the simulator measured it |
| arm | `group_size: k` | a group study: `design(n)` gives n groups of k participants; `open()` returns a GroupSession |
| arm | `n_analysed`, `n_recruited` (`{value, cite}`) | human n after / before exclusions: the planned agent n (§8.2, §8.7) |
| arm | `release_hold: <reason>`, `exclusion_caveat` | runnable privately, never released; exclusions the replay cannot apply |
| conditions | `ratio: {arm: share}` | allocation ratio; `design(n=int)` honours it (largest remainder) |
| roles | `[{member, id, label, shown: {text, cite}}]` | what a participant was told about their own position; only `shown.text` reaches the State |
| unit | `per: group`, `arms: [ids]`, `cites: {field: cite}` | one row per group; built only for those arms; cites of transformed fields |
| unit | `trim: [{id, field, group_by, center, spread, k, fence, keep}]` | row-level trimming on the analysed rows |
| exclusion | `population: {values, rule: mean_plus_k_sd \| iqr_fence, k, group_by, after_exclusions}` | cutoffs computed on the analysed sample |
| exclusion | `applies_to: [ids]`, `pending_if: expr` | exclusion for some analyses only; undecided until resolved |
| coding | `apply`, `cases: [{text, code}]`, `coder: {rubric, input, output, provenance}` | the rule; the cases it must reproduce; the declared coder for `needs_coder` |
| target | `stat: mean \| median \| share …`, `missing_values` | the level and the codes held out of shares |
| target/effect | `role` (test, paper_claim, descriptive, robustness, exploratory, check) | only test / paper_claim are scored by default |
| target/effect | `suspect`, `direction_unresolved` + `readings`, `reference_mismatch` + `scoring` | never scored; scored on neither direction nor level; direction only / not comparable |
| effect | `direction_claimed: true \| false` (+ cite) | the source claims a direction (scored on sign) or reads it as no reliable effect |
| effect op | `mean_difference`, `paired_difference`, `proportion_difference`, `contingency`, `correlation`, `spearman`, `proportion_vs_chance`, `smd`, `interaction`, `rank_sum` | the computation (`hsenv/effects_core.py`) |
| reported | `cells`, `test {statistic, value, df, p}`, `no_uncertainty` | the human numbers as printed |
| analysis | `blocked_arm_effects`, `blocked_arm_targets`, `printed_items` | kept for arms that are not runnable; printed item-level data (report only) |
| meta | `language` (+ `foreign_text_allowed`), `export_tags` | the language participants saw; survey export tags that must never be served |
| cite | `read: "image"` | text read off an image: served only when an independent blind reading of the same page agrees (`hsenv-check --source-text`) |
| expression | limits | integers ≤ 4096 bits; containers ≤ 10⁶ elements; ≤ 2·10⁶ comprehension iterations; `range` ≤ 10⁶; source ≤ 200,000 characters. Over a limit → `ExprError` |
| study.json | `slug`, `paper`, `contributors`, `visibility`, `hsenv`, `fidelity`, `arms`, `release` | release metadata (`schema/study.v1.json`) |
| package | `hsenv.release.PUBLIC_PATHS` / `NEVER` / `is_public` | which files of a study folder may be published |

**Checks** (`hsenv-check`, no model calls): cite and reference integrity; fuzzing with random and keyed answers
(unreached stages, unanswerable stages, leaks of operator-only text or expressions into any State); verbatim checks
of served text against supplied source text and blind readings of images; coding rules against their cases; paper
self-consistency (2×2 χ², Welch t from printed cells); every declared effect computable. `--public` runs without any
private configuration and lists texts it cannot verify instead of blocking.

**Private configuration.** Study-specific engine data (pins for legacy readings) lives outside the package in a
JSON file named by `HSENV_PRIVATE_CONFIG`. Unset, the engine runs with none; public engine code names no study.

## 4. Runtime interface

```python
import hsenv.engine as hs

env = hs.make("path/to/mystudy")                  # loads protocol.json; no study code is run
specs = env.design(n="paper", seed=7)             # [SessionSpec]: condition draws, orders, group membership
s = env.open(specs[0])
state = s.reset()
while not state["done"]:
    answers = my_agent(state)                     # anyone's: one model call, a chat, a human, a script
    state = s.step(answers)                       # {"r1": 80}; an invalid value returns the same State + error
tables = env.unit_tables()                        # the declared units, one row per session (or group)
```

- **Group studies:** `GroupSession.pending()` lists who must act; `step(pid, answers)` per participant; `sync`
  stages release outcomes to everyone at once.
- **Invalid answers:** the State comes back with `error`. The engine never guesses. How many retries an operator
  allows is recorded in provenance.
- **Same engine, three faces:** Python, HTTP and MCP (§9, `SERVE.md`).

## 8. Evaluation (offline report)

The v0.8 evaluation layer is an **offline report, not a leaderboard**: every score carries
`report_scope: "offline_report — not a leaderboard"`. In `hsenv.serve` the operator chooses arms and seeds, so the
numbers are not hardened against a strategic operator.

### 8.2 One scoring rule for every target

Each target has a human value `h` from `N_h` analysed participants and an agent value `a` from `n_a` agent
participants.

- `se_h(N)` is the human standard error at sample size N (from the printed SE / CI / SD, or derived from a printed
  test where the estimand matches exactly).
- **Ceiling** `c = 0.674 · sqrt(se_h(N_h)² + se_h(n_a)²)`: the median distance of a fresh human sample.
  **Human range** `m = 1.96 · sqrt(se_h(N_h)² + se_h(n_a)²)`.
- **Baseline** `b`: the State-only random floor (§8.7).
- **Gap** `d = |a − h|`. **Score** `s = (|b − h| − d) / (|b − h| − c)`: 0 = baseline, 1 = as close as a typical fresh
  human sample; aggregated clipped to [0, 1].
- **Status:** `uninformative` when `|b − h| / sqrt(se_h² + se_b²) < 2.8`; `within_human_range` when `d ≤ m`, else
  `outside_human_range`; `no_uncertainty` / `not_computed` otherwise.
- **Reference** `s_null`: the expected score of a run that *is* a fresh human sample of size `n_a`, by simulation,
  published next to every score.
- **Scales:** shares on the empirical-logit scale; Agresti–Caffo / Agresti–Coull SEs at 0% or 100%.

### 8.7 Evaluation data and rewards

`EvalData.build(protocol, runs, baseline)` (`hsenv/evaldata.py`) collects, per effect and target, the human side
(value, SE, n, p, direction, each with its basis: printed or derived) and the agent side (the same op, per seed and
pooled). Rewards (`hsenv/rewards.py`) are pure functions of `EvalData`, registered by versioned id; an `EvalData`
JSON can be re-scored later with `hsenv-score --rescore`.

| id | scope | value |
|---|---|---|
| `significance_match-v1` | population | per effect 1 if (agent p < α) == (human p < α) and, when significant, directions agree |
| `direction_match-v2` | population | sign of the agent contrast equals the human sign (human significant or direction claimed) |
| `effect_gap-v1` | population | −\|effect_agent − effect_human\| in the effect's own metric |
| `within_human_range-v1` | population | share of targets with `d ≤ m` |
| `human_noise_score-v1` | population | the §8.2 score `s` |
| `spread_check-v0` | population | diagnostic only: agent SD per arm against the printed SD; never changes a score |
| `validity-v0` | session | the session completed and no whole-session exclusion removed it |
| `loglik-v0` | step | placeholder: always not computable (needs individual human data) |

Rules every reward follows:

- **Planned n.** The agent n per arm is the human analysed n (`arms[].n_analysed`, else `n_paper`, labelled
  `n_paper_unverified`). Only a run at that n is `official`; any other n is `non_official`: values, no pass/fail.
  A seed whose valid sessions fall below 0.9 × planned in any arm is `underpowered_run`.
- **Not computable is never 0.** A missing human number makes the item `not_computable` and it leaves the
  denominator. An agent-side failure (zero variance, constant answers, empty cell) scores 0 and stays in.
- **Baseline** is the `floor` policy: random answers drawn from the State alone (no keys, no hidden limits), at the
  planned n, seed 0, with the same top-up as agent sessions.
- **Two views.** Rewards are computed on the analysed rows and on all completed rows (intention to treat); the
  lower is kept only when the agent's exclusion rate exceeds the human rate by a two-sample margin. Both are
  reported.
- **Recorded with every score:** reward id and params, the constants, and the protocol and code hashes.

User-defined rewards: a declarative combination (`rewards.combined(ev, config)`) or a Python function with the
`@reward` decorator; a `Verifier(reward, threshold | rule="all")` adds a pass rule.

## 9. Serving

- **Python:** `hsenv.engine.make(study_dir)`; the engine is pure data interpretation and runs in-process.
- **HTTP** (`hsenv-serve-http`) and **MCP over stdio** (`hsenv-serve-mcp`): participants get States only (never
  conditions, rules or scores); an operator token unlocks records and `score`. See `SERVE.md`.
- **Provenance per run:** model, how States were rendered ("screen only", "screen + seen", "one chat"), retries
  allowed (`schema/run.v1.json`). Populations with different renderings are not pooled.
