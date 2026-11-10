# hsenv design (engine extract, v0.8.1)

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
| meta.sources | `<key>.distribution: {tier: hosted \| link \| user, licence, attribution, url, sha256, format}` | how that source's participant-facing text reaches users (§3.6); absent = `user` |
| projection | `distribution: {format: hsenv-projection/1, placeholder, held: {hN: {path, source, kind, length, text_sha256, locator}}, attribution}` | only in a release projection (`hsenv.release.project`); `hsenv.rehydrate` removes it (§3.6) |

**Checks** (`hsenv-check`, no model calls): cite and reference integrity; fuzzing with random and keyed answers
(unreached stages, unanswerable stages, leaks of operator-only text or expressions into any State); verbatim checks
of served text against supplied source text and blind readings of images; coding rules against their cases; paper
self-consistency (2×2 χ², Welch t from printed cells); every declared effect computable. `--public` runs without any
private configuration and lists texts it cannot verify instead of blocking.

**Private configuration.** Study-specific engine data (pins for legacy readings) lives outside the package in a
JSON file named by `HSENV_PRIVATE_CONFIG`. Unset, the engine runs with none; public engine code names no study.

### 3.6 Distribution tiers and rehydration (hsenv 0.8.1)

In short: a study can be published without republishing anyone's text. Each source gets a tier: *hosted* (the licence allows redistribution, so the text ships), *link* (the package ships the URL plus, per item, a locator and a hash; the user's machine fetches the file and restores each item locally, checking its hash) or *user* (the user supplies the file; same checks). `hsenv.release.project` builds the shareable projection and refuses one that would still contain non-redistributable text; `hsenv.rehydrate` restores it. The rest of this section is the exact rule.

**Structure always ships; only participant-facing content is
tiered.** Every release projection carries, for every study and tier: stages and their order, randomisation and
assignment, conditions, response formats (kinds, ranges, option codes, counts and order, required / validation
rules), timing, piping and visibility, units / recodes / exclusions, effects and targets with the paper's reported
numbers (facts, cited), and every cite's source, page and label. Participant-level data never ships. The text and
images participants saw ship per **source** (a paper's licence is not its instrument's licence):

| tier | when | what ships | on the user's machine |
|---|---|---|---|
| `hosted` | the source's licence allows commercial reuse: CC-BY (any version), CC0, public domain. Never NC or ND; CC-BY-SA is tier `link` (no share-alike on the package) | the text, with `attribution` | nothing to do |
| `link` | reachable by URL or DOI (open, or paywalled when the user has access), not redistributable | no text: the URL / DOI, the builder's file sha256 as provenance, and per item a locator + `text_sha256` | the app downloads the source, extracts each item, checks each item's hash |
| `user` | gone, or not declared (the default) | the same as `link`, without a URL | the user supplies the file; the same checks |

**One verification rule for every source: every item is verified by its own
`text_sha256`; the file sha256 is recorded as provenance only and never gates reading or serving.** Publisher PDFs
are stamped per download (watermark, timestamp, institution, metadata), so two legitimate copies rarely share a
file hash, while the item hash checks exactly what is served. A different or tampered file can only make an item
fail (`hash_mismatch`); it can never put other text on screen. `report.sources[key]` records the file's sha256
and whether it matches the recorded one.

**Projection** (`hsenv.release.project(protocol, tiers, sources=…, extractors=…)` → `(projection, report)`).
Every participant-facing string (item values, data texts, option labels, anchors, prompts, instructions, prefixes,
messages (`*_message`, every `validate` message, `min_chars_message`), buttons, prefills, columns, widget_params,
span tooltips, image lines, table cells, role texts, sync events, content `text` beside `value`; cited by
`<key>_cite`, `cite` or `cites`, nearest first) whose cites (any label but `missing`) are not
backed by a `verbatim` / `reported` cite of a hosted source is replaced by a **placeholder of the same length** (U+2591 per character) and listed in
`distribution.held` with its JSON pointer, source, length, `text_sha256` (sha256 of the NFC-normalised exact served
text) and locator. Images of non-hosted sources keep their `src` and `sha256`; the file itself is not distributable.
Lengths ship (span offsets stay valid; a length reveals less than the hash of a short text already does). Because
only strings change, **the projection runs in the engine as it is**: structure-level previews and fuzz work without
the text, and a placeholder is visibly marked. Strings under keys that are usually structural — data `id` / `code` / `start` / `end` /
`style` / `size` / `read` (unless the dict is a span or a table cell), data `*_note`, `validate` `equals` /
`contains` / `pattern`, unknown presentation keys, unknown item / response keys (caption, placeholder …), text beside
an `expr` in a data dict — are held when they locate in their source and ship otherwise. A held text must be NFC
(the projection refuses otherwise).
A hosted `verbatim` / `reported` cite exempts a text only if the text is in the hosted file, which a strict
projection requires the builder to supply. A `derived` text ships as our own wording (`report.derived_shipped`) only when it shares no run of
min(length, 16) case-folded canonical characters with any supplied non-hosted source; otherwise it must locate
(held) or the projection refuses. Operator-side quotes of a non-hosted source — `{text, cite}` outside the
screen, cite fields other than label / source / page / read / file / qid / block / part / table / licence / region
(evidence and notes quote sources), and any string sharing a run of ≥ 23 case-folded canonical characters with a
supplied non-hosted source, or 8 wide (CJK) characters (no whitespace needed; under data every key but src /
sha256 / if / expr is read; elsewhere a structural key exempts only its own token-shaped value — an ASCII id, code or
format without spaces — never a sentence and never a subtree; URLs, DOIs, hashes and paths — ASCII only, a path starting with `/` `./` `../` or ending in a file extension;
"never/rarely/often" is text — are not quotes) —
are held the same way when they locate (rehydration restores them) and otherwise replaced by
`withheld:<sha16>`; on screen (data / stages / roles / flow) such a string without a cite is an error, and so is
source text in any dict key or structural value anywhere (neither can be withheld). Coding `cases` quoted from a
source (the paper's coded examples) are that source's text: a case is held when it carries its own verbatim /
reported cite of a non-hosted source, or when it locates in the coding rule's cite source; invented cases (ours)
ship. Participant data never ships. **One held-text rule** (`hsenv.release.HeldIndex`, the only implementation; the projection scan, scanned JSON
files and hosted sourcetext all call it), on the **alphanumeric skeleton** — folded (canonical, then full NFKC so fullwidth / halfwidth digits and Latin
are one, case-folded, Cyrillic / Greek confusables mapped to Latin; comparison forms only, never served and never
in a locator), then only letters, digits and CJK kept, so punctuation, quotes,
spacing, symbols, HTML entities and HTML tags never hide a copy. **One helper, `release._forms(s)`, gives every
leak comparison its inputs** — the string as it is, HTML-unescaped repeatedly until stable (capped at 8 rounds), and
each of those with single-line tags `<[A-Za-z/!][^<>\n]*>` replaced by a space; the strongest result counts, and
angle-bracket text such as "Press <Enter>" stays text. `HeldIndex.hit`, `HeldIndex.shares` (leak vs screen
fragment), the uncited-source-quote net (`found_in` in the projection, `quote()` for scanned JSON) and `_literals`
all call it, and none normalises on its own (a table-driven test feeds the same escaped / tagged / fullwidth variants
to every entry point and checks each calls `_forms`). **Computed positions** are one registry,
`release.COMPUTED` (every position engine.py or checks.py evaluates: vars, any `expr`, `if` / `until`, `pending_if`,
`if_valid`, `coding/<rule>/apply`, flow `in` lists, `let`, `set`, `loop` and sync `compute`, unit `fields`,
`population.values` / `group_by`, `keyed.answers`), matched only under the parts the engine reads (vars, flow, stages,
units, exclusions, analysis, keyed, coding, roles — never under `data`, which is read only through expressions) and
never inside a cite or a note (operator text, held or withheld as usual even under a computed ancestor). One path
classifier knows which segments are **author-chosen names** — children of vars / let / set / compute / fields, and
stage, unit and coding ids: a name is never matched against reserved words or against the cite / note key patterns
(`vars.bonus_note` is a computed var, a stage called `apply` / `if` / `expr` is an ordinary stage, `coding/open_note/
apply` is a coding rule, `keyed.answers["s.r_note"]` is a keyed answer); whether a key is a cite is decided by its
value (a cite dict, a list of them or a map of them), never by its name (`fields.n_cites` holding an expression is a
field; `vars.tbl.cite` holding a string is part of a var; `vars.k_cite` holding a cite dict is a cite). The rule: a string
at a computed position is never held and never withheld; that string, each string literal of it when it parses as
an expression (a bare string constant, implicit adjacent literals included, yields its value), and the operands that
actually concatenate (`+` chains, `%` formatting, the engine's `join(sep, [...])` — never if-expression branches,
comparisons or lists) are a strict error when they quote a non-hosted source by **the one run / whole rule** (`release.SourceRuns`,
the same rule the quote net, scanned JSON and keys use): on the alphanumeric skeleton of any `_forms`, the text shares
a run of ≥ 23 characters holding at least one letter (digits alone — a printed 1–20 scale — are not a quote) with a
source, or a CJK window (`_cjk_windows`, which HeldIndex uses too: 8 skeleton characters with at least 5 CJK characters,
or 7 skeleton units holding an ASCII run, each maximal ASCII run counting once, with at least 6 CJK units (5 when
the window holds Latin letters: 次Q音乐App听歌) — so a
fullwidth comma, a digit or a Latin word inside a Chinese item, 我使用ChatGPT写作业, never break it, while digits and
Latin never count toward the CJK share: 过去12个月里, 在0到100之间, 每天使用TikTok are our own wording); every
source holding a window is checked for the run (a window shared by two sources never hides one; each (source, run)
is checked at most once per text, so a run shared by 100 sources stays fast), or its whole skeleton appears in a source (≥ 6 characters when it contains CJK, everywhere; for Latin text ≥ 12
characters, at computed positions and in keys only — on operator and uncited screen text a short Latin phrase such as
a country, a citation label or "ground squirrel" is a fact, and the run rule covers longer Latin text; never a single
ASCII token such as an id or a ref). **One function decides operator text vs material** (`_operator`, used by the quote net): inside a cite — decided
by value — it is operator text; under data and vars a note-named string is material (the engine may display
`data['panel_note']`), so it is held or refused like any text, never withheld; on stages, roles, flow and elsewhere a
note key that is not an author-chosen name is operator text. On screen parts (data, stages, roles, flow) a dict
counts as a cite by value only under a cite-named key or when it has no keys beyond a cite's own (CITE_KEEP plus
quote / evidence / note / where), so a stimulus shaped like a cite (`{headline, source, label}`) stays material. The
derived-text and "maybe" checks use the same `SourceRuns` (no other comparison path remains besides HeldIndex for
held texts); a `derived` text that quotes its source but cannot be located gets that error. Invariant test: whatever
the engine displays (random sessions in every arm over the rehydrated protocol, and every display slot) never reads
`withheld:`. The engine itself never shows a cite or a note: every value it passes through to a State (spans,
prefix / suffix, na_option, anchors, columns, widget_params, prefill, image-line and table-cell spans) goes through
one helper, `engine._shown`, which drops cite and note keys recursively. A button is cited by
`presentation_cite`, `presentation.cite` or the stage's cite.
Checked on the original protocol before anything is rewritten. Display strings are never parsed as Python (an item `"…" (R)` is text). Held text at a
computed position is an error too (the scan); a dict key anywhere that quotes a source — whole (≥ 12, not a single ASCII
token: `comprehension`, `presentation` are names) or by the run rule — is an error (keys cannot be withheld); an image dict at a computed position is an error (a picture there is
never held). Tests: every registry entry, with the exact text, a prefix, a suffix, an added comma, an 80-character
fragment and a held item, raises, and so do CJK items (numbered, with a reverse marker, a 9-character fragment); a
non-source string ships unchanged; both directions of the name classifier are tested; and the drift test parses
engine.py and checks.py — `.ev(X["k"])` (the only sites a display spec — value, text, prefill, options, button,
equals, label, instruction, events — may exempt), raw `{"expr": X["k"]}` / `evaluate(X["k"])`, dict specs iterated
into an evaluation, single-variable comprehensions, indirect assignments evaluated within ten lines, keyed answers —
and checks each site's protocol path (not its key name) with `_computed`; it is itself tested on hypothetical new
engine lines. It cannot see evaluation through a helper that takes a protocol node, or a name that reaches `ev` over
more than a few lines; such a change must extend the parser. In any of its forms, a
string is held text if its skeleton — also with a leading
enumerator (`1.` `1)` `(1)` `1、` `（1）` `①` `1.1` `i.` `(ii)` `a)` `一、` `Item 1:` `Q1a.` `質問1：` `문항 1.`, item
codes `A1.` `PHQ1.` `No. 1`, nested `1. (a)`, bullets and check boxes `□ ☐ ○ [ ]`), a trailing marker (a short
parenthetical or bracket such as "(R)", "[R]", "(reverse scored)", "（反向）", `*` `†`), tab-separated cells or a trailing response
scale (digits, or "N/A" after a separator: "1 2 3 4 5 N/A") removed — equals a held text's of 6–15 characters, contains a whole held text (a held text
of ≥ 6 characters with any character of a script written without spaces — CJK, Thai, Lao, Khmer, Myanmar — counts
inside a sentence, those scripts having no word boundaries), or hashes to a held text / part (`whole`); or shares a 16-character
skeleton fragment, or an 8-character CJK skeleton run, with one (`fragment`). Held texts under 6 skeleton
characters are not checked (guessable anyway), and a single ASCII token (an id, a code, a layout entry, a key) is
not held to the short-text rule (`gender` is not the label "Gender:") — in the projection scan and in scanned
JSON alike. Only an exact `withheld:<16 hex>` marker is exempt from the scans. JSON strings are also checked
HTML-unescaped. Text files are decoded strictly as UTF-8
(anything else refuses), each line then checked in all its forms (escaped / unescaped, with / without tags), line-end hyphenation joined and digit-only lines dropped first (kept when a held text is itself all digits),
then the whole document and each line are checked. Every shipped string of the projection is checked: outside the screen a hit is
withheld; in an expression, id or key it is an error; on screen (data, stages, roles, flow) a `whole` hit or a
shared run of ≥ 23 characters is an error (a marker would be served as text), a shorter fragment is reported
(`screen_fragments`). While any source is not hosted, every image needs a cite (or a `missing` label). String literals inside expressions, flow `for … in` lists and `vars` cannot be held (the engine
computes with them): a literal of ≥ 12 canonical characters found in a supplied non-hosted source is an error (move
the text into data with a cite); without sources they are only counted (`report.literals_unchecked`). `strict=True` (every release) raises on any error: an unlocatable
verbatim / reported text, a source without the fields its tier needs (hosted: an accepted licence and attribution;
link: an http(s) URL or a DOI), a cite
naming an undeclared source, a PDF locator from another extractor than the pinned one. Strict failures are fixed in
the protocol, never by loosening the engine. `hsenv.release.distributable(name, projection)` extends `is_public` (names normalised and
case-folded): `sourcetext/<key>.txt` and `sourcetext/<key>#…` ship only when `<key>` is exactly a declared hosted
source key (keys may contain dots) holding nothing, and — while anything at all is held (a CC-BY paper may reprint a
proprietary scale held for another source) — only with its `content` supplied together with every non-hosted source
(and `held_texts`) and free of held text by the same rule as scanned JSON (16-character case-folded fragments
anywhere, a line equal to a 6–15-character held text, a line hashing to a held text or part); `protocol.json` ships
only when its `content` is the projection itself and the projection was made strict (`distribution.strict: true`);
a scan that cannot read a supplied source (no extractor) refuses, never raises; held image
files never; while any source is non-hosted or anything is held, `review/**` (fidelity notes and check reports
quote materials; there is no scrub step), `program.json`, `package/**` and `sources/open/**` are refused
and `artifacts/**` ships only where an image object under data / stages / roles still references the file and it
was not held;
`variants/**` is refused (a variant needs its own projection); `effects.json`, `study.json`, `capabilities.json`
and `sources/SOURCE.json` ship only when their content is passed together with every declared non-hosted source and
is free of held text: every held text with a locator is recovered from the supplied sources (as rehydration does;
one that cannot be recovered refuses the file), every held text without one (an image reading or region text) must
be supplied by the builder (`held_texts={held id: text}`, checked against its `text_sha256`; missing or wrong
refuses the file), pictures are checked by hash only, and every string and key is checked by the projection's rule — 16-character
case-folded fragments, whole-string equality for 6–15 characters, and the held hashes — without exception. The
quote-run check against the sources applies to every key, and to every string value except at bibliographic
positions: a top-level
title / authors / journal / doi / year …, a string directly under a top-level `paper` or `citation` object, a
declared source's own entry field in `sources/SOURCE.json`, and in a projection `meta.sources.<key>` string fields and
`meta.citation`; the held-text check applies there too. Only the documented keys of a `distribution` entry ship. A cite without a source fails closed.
`report.quote_scan_unchecked` lists the non-hosted sources whose files were not supplied (the quote net did not
run for them).

**Locator** — deterministic without offsets into an extractor's output:

```
{format: pdf|docx|html|qsf|text, extractor: "<name/version>",
 parts: [{units: [a, b], canon_len, canon_sha256} | {literal}], restore: [[i, n, s] …], pages: [p, q] (pdf)}
```

*Units* are what every extractor agrees on: PDF pages, docx paragraphs (`w:p`, document order, text boxes before
their host, tracked deletions skipped), HTML text blocks (block elements; script / style / head skipped), QSF
question fields (QuestionText, then each Choice and Answer `Display` in ChoiceOrder / AnswerOrder; HTML reduced to
text), text lines. *Canonical form*: NFC; curly quotes, U+02BC, hyphen and dash variants folded; NFKC only for
punctuation, symbols and typographic ligatures (letters, digits and marks are never folded, so restore ops cannot
carry a text's letters); every whitespace, soft hyphen and zero-width character removed (case kept). Two canonical streams per unit window
are searched: as extracted, and with a hyphen + white space between letters removed (hyphenated line breaks). So
extractors that differ in spacing, line breaks, ligatures, quote forms or hyphenation give the same stream. A part
is found by sliding a window of `canon_len` over its unit window (then ±1 unit) and comparing sha256 values; the
joined parts are turned back into the exact served text by `restore` (insertions of the whitespace and replacements
of the folded characters — never a run of letters); the result counts only if its NFC sha256 is `text_sha256`. A
plain verbatim text is one part. A text composed from the source (cut, joined, a blank printed at another length)
is several parts of ≥ 8 canonical characters with short literals between them (≤ 20 % of the text, punctuation
and blanks only — a literal never carries a letter or digit); anything further from the source is not located. The builder's run of `project` self-tests every locator through the same
`find` the user's machine runs. Every format but PDF is extracted by hsenv itself (stdlib, versioned
`hsenv-<format>/1`; a version's behaviour never changes). PDF: the app ships one fixed
extractor, pypdfium2's text page per page (`hsenv.distribution.pdfium_extractor()`, an optional dependency), named
`pypdfium2/<version>+pdfium/<build>`; builders self-test with exactly that extractor (`project` refuses PDF
locators from any other family), the name is part of every locator, and **rehydration refuses a locator whose
extractor differs from the app's** (`source_unavailable`), for every format.

**Rehydration** (`hsenv.rehydrate(projection, fetch=callable, files={source: bytes}, items={held id: bytes |
str}, extractors={})` → `(protocol, report)`; source files and per-item supplies are separate namespaces).
Network access only through the injected `fetch(url) -> bytes`. Per source: a user file in `files[key]`, else (link)
the download; the file is read whatever its sha256 (provenance only, reported), and **nothing is served unless the
item's own text hash verifies**. *Stamp-robust locators*: a PDF part never spans a page (a text over a page break
is two parts), so stamp lines between pages cannot break it; within a page the part is a sliding canonical window,
so stamp lines above or below it do not matter; if a stamp line lands inside the item, `find` retries that page
with each block of 1–3 consecutive lines removed (pages ≤ 80 lines) — the hash still decides. The retry runs after
every item had its plain search, only for sources where some item matched plainly (a wrong file has none, and
neither does a source with a single held item: a stamp inside the only item of a source is a known limit), within
a budget per rehydration (4·10⁸ hashed characters); all searches together are bounded too (4·10⁹). A held
entry may only fill the placeholder it names (same length, all U+2591) or an image object; a malformed or crafted
entry is reported per item, never raised; held ids must be `h<number>`, image `src`s an http(s) URL or a
relative path inside the study (no `..`, absolute path or other scheme); part windows (≤ 8 units), part counts,
`canon_len` (≤ 100,000), the hashing work per part (≤ 2·10⁸ characters) and op shapes are bounded. An image's text line is replaced by its rendered picture only
once that picture itself resolved. A region's page is checked against the builder's PDF when supplied. Per item: `ok` (restored), `hash_mismatch` (the item not found / not hashing in its
window), `source_unavailable` (download failed, no fetch, no PDF extractor),
`needs_user_file` (user tier without a file; a picture without a region or its file), `ok_image` and
`requires_reading` (see below).
Unresolved items keep their placeholders and stay in `distribution.held`, so the result still runs as a preview;
the block is removed when every item is restored. Verified image files come back in `report.assets` and region renders in `report.renders`, both keyed by held id
(the image's `src` is in the item report / the render entry), so no URL or path is ever a key.

**Text read off an image** (`cite.read = image`, blind-reading-confirmed) has no deterministic extraction on the
user's machine (OCR is neither stable nor exact). Such an item, and a picture of a non-hosted
source, carries a **region** locator when its cite (or the image value / the image's cite, for its lines) gives
`region: {box: [x0, y0, x1, y1], dpi?, page?}` — page-relative units, origin top left, dpi 72–600 (default 150):
`{format: region, source, page, box, dpi}`. *Region rule (one rule)*: the region's **anchors** are the held texts of
the same source located on the region's page at build time whose text occurs on no neighbouring page (marked
`unique: true` in the locator; a locator without it never anchors) and is at least 12 canonical characters long.
The region is rendered only if (a) no held text located on that page failed in this copy, (b) the verified anchors
total ≥ 16 canonical characters with at least one anchor of ≥ 16, each distinct text counted once (by
`canon_sha256`), (c) every anchor matched on exactly one candidate page (the recorded page or a neighbour; a text
matching on two is ambiguous and counts as unmatched) and all on the same one, and (d) each anchor sits where it
sat on the builder's page: the locator records the canonical characters before and after it on its page, and in
this copy neither may be fewer (beyond 8) or more than stamp lines can add (400) — a reflowed edition fails — and it is rendered from **that** page (a cover page
or another edition shifts it), not from the build-time number. A repeated instruction ("Rate the picture below")
therefore never anchors a stimulus page; authors anchor such pages on their own captions or labels. Then the item is `ok_image`: the app renders that region of the user's own copy and serves it to the model
as an image (`report.renders`: {held id: {source, page (this copy), built_page, box, dpi, src}}). Otherwise it is
`needs_user_file` (no anchor, an anchor failed, anchors too short, or anchors on different pages). Protocol authors give image-only pages a verifiable anchor by citing the page's own
printed text (a caption, header or footer) as a held item; a page with no text layer at all cannot be trusted for
a render (open question: an embedded-image fingerprint per page). A picture keeps its `src`; an image's text line is dropped (the rendered picture carries
it); a `{text}` data value or a stage item's literal value becomes `{"src": "regions/<held id>.png"}`; other
positions (option labels, prompts) cannot show an image and stay `requires_reading`. A reading supplied in
`items[<held id>]` that hashes to `text_sha256` still wins and is served as text (the hash-checked description).
`requires_reading` remains only where no region is known; a picture without a region is `needs_user_file`
(`items[<held id>]` with the file's sha256).

Known limits. (1) A PDF text layer is deterministic per library, not across libraries: the canonical form absorbs
spacing, line-break, ligature, quote and hyphenation differences, but not reading order (multi-column pages, text
boxes, tables extracted row- vs column-wise), missing ToUnicode maps, or a page split differently; such an item
fails as `hash_mismatch`, never as wrong text. Hence the single pinned extractor; a pypdfium2 / PDFium upgrade in
the app invalidates existing PDF locators until releases are rebuilt with it (the app should keep the pinned
version, or ship the old one alongside). A region is rendered by the app's renderer: pixels are not hash-checked. The text extractor gives no character
boxes, so an anchor's position on the page is not compared with the region's box: the anchors prove the page,
not the spot on it. The before / after guard catches reflow, not a different page that happens to print the same
anchors with a similar amount of text around them (e.g. the same Likert scale on an appendix page). (2) `text_sha256` / `canon_sha256` of a short text ("Yes", "Strongly agree") are guessable by
dictionary: short texts are effectively disclosed (they are rarely protectable). Accepted as a known limit. (3) A text whose case differs from
the source is not located (restore ops never carry letters). (4) Operator text that paraphrases a source is not
detected; review notes are therefore not distributable while a source is non-hosted. (5) Quote detection needs the
builder to pass every non-hosted source to `project`; without it only cited quotes and held texts are caught.
(6) Held text the engine uses as a lookup key or compares with (`data['fb'][data['pick']['text']]`) breaks the
preview of the projection (not the rehydrated protocol); strict cannot see it. (7) Latin literals (and keys) at computed positions
shorter than 12 skeleton characters that share no 23-character run with a source, and fragments shorter than 16 of
a held text, are not checked (CJK is checked whole from 6 skeleton characters and inside longer text from an
8-character CJK window, so a 6–7-character CJK item embedded in a longer operator string is not caught); a common phrase of 12+ characters that also appears
in the source ("control group") is refused at a computed position. (8) Rehydrated text is NFC; an original stored decomposed comes back composed. (9) Restore ops place every white space, so a held item's word lengths are visible; with `length` and the hash this eases guessing short items. (10) A short Latin held text (6–15 characters) printed inside a longer line with other words ("I feel sad
sometimes", "Item: I feel sad — reverse scored") is not caught: its skeleton equals nothing and it has no
16-character fragment; CJK held texts are caught inside sentences. (11) A tag broken across lines (`<span\nstyle=…>`) is not removed by `_forms` (single-line tags only, so that
"A<B … B>A" across lines never swallows text); its letters stay in the skeleton and could split a copy only if such
broken tags were inserted at least every 16 characters.
Validated before release on a set of real protocols, with plain-text renderings of their sources as text-format
link sources: every located item rehydrated to its exact original (0 wrong); unlocated items were image readings
or sources without a text rendering.

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
