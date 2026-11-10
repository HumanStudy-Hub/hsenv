# Changelog

## 0.8.1 (2026-11-10)

### Added

- **Distribution layer** (`hsenv.distribution`, `hsenv.release`; DESIGN §3.6). Structure always ships; the
  participant-facing text of each source ships by tier: `hosted` (CC-BY, CC0, public domain: the text with its
  attribution), `link` (a URL or DOI) or `user` (the user supplies the file).
  - `hsenv.release.project(protocol, tiers, sources=…, extractors=…)` writes a release projection. Held text is
    replaced by a same-length placeholder and listed under `distribution.held` with its JSON pointer, length,
    `text_sha256` and a locator that works across extractors. `strict=True` refuses anything it cannot place
    safely.
  - `hsenv.rehydrate(projection, fetch=…, files=…, items=…, extractors=…)` rebuilds the protocol on the user's
    machine. It serves nothing unless the item's own hash verifies. A file's sha256 is recorded as provenance only.
  - One rule for held text (`release.HeldIndex`) and one rule for quoted runs (`release.SourceRuns`), with a shared
    CJK window. One `release._forms` helper supplies the inputs to every leak comparison.
  - `release.COMPUTED`, a registry of every protocol position the engine evaluates. Source text at a computed
    position is a strict error. A drift test parses `engine.py` and `checks.py` to keep the registry complete.
  - Region locators for text read off an image and for pictures, rendered from the user's verified copy.
  - `hsenv.release.distributable(name, projection)` extends `is_public` with the per-file rules of a release.
  - PDF locators use one pinned extractor, `hsenv.distribution.pdfium_extractor()` (pypdfium2, an optional
    extra: `pip install "hsenv[pdf]"`). Every other format is read with the standard library.
- `hsenv.rehydrate` is exported at the package top level.
- Schema (`protocol.v1.json`): a top-level `distribution` block (present only in a projection), `distribution`
  on each `meta.sources` entry (`sourceDistribution`), the `heldItem` definition, and `region` on cites.
- `tests/test_distribution.py`, with invented fixtures only.

### Changed

- The engine never shows a cite or a note. Every value it passes through to a State (spans, prefix / suffix,
  na_option, anchors, columns, widget_params, prefill, image-line and table-cell spans) goes through
  `engine._shown`, which drops cite and note keys recursively.
- `release.NEVER` drops an entry that `PUBLIC_PATHS` could never match. `is_public` gives the same results.

## 0.8.0 (2026-11-09)

First public release: engine, checks, evaluation data, rewards and score (an offline report, not a leaderboard),
MCP and HTTP servers, v1 schemas, and the test suite with invented fixtures.
