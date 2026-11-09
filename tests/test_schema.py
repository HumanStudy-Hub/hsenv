import copy
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from hsenv.engine import Protocol
from hsenv.schema_check import (canonical_sha256, load_schema, main, protocol_sha256, validate,
                                validate_file)

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "studies"
# invented, CC0 fixture protocols only: tests against real study protocols live in the private suite
SCHEMA_FIXTURES = [str(FIXTURES / "fixture_mini" / "protocol.json")]

MINI = {
    "schema_version": "1", "id": "mini",
    "meta": {"citation": "A (2020)", "licence": {"paper": "CC-BY-4.0"}, "sources": {"paper": "paper.pdf"},
             "sample": {"n": 10}},
    "arms": [{"id": "main", "n_paper": 10, "cite": {"label": "reported", "source": "paper", "page": 3}}],
    "data": {"q": {"text": "How sure are you?", "cite": {"label": "verbatim", "source": "paper", "page": 4}}},
    "stages": {"q": {"content": [{"id": "t", "value": {"expr": "data['q']"}}],
                     "responses": [{"id": "x", "kind": "slider", "range": [0, 100], "prompt": "rate", "widget": "hslider",
                                    "cite": {"label": "verbatim", "source": "paper", "page": 4}}],
                     "presentation": {"back": "not_allowed", "advance": "self"}}},
    "flow": {"seq": [{"stage": "q"}, {"repeat": {"stage": "q"}, "until": "True", "max": 2, "on_max": "flag"}]},
    "units": {"s": {"per": "session", "fields": {"x": "answer('q.x')"}}},
    "exclusions": [],
    "analysis": {"targets": [{"id": "m", "unit": "s", "field": "x", "stat": "mean"}], "effects": [], "unsupported": []},
    "keyed": {"answers": {"q.x": "50"}},
}


def errs(r):
    return [p + ": " + m for p, m in r["errors"]]


class TestFixtureStudies(unittest.TestCase):
    def test_fixture_protocol_validates(self):
        self.assertTrue(SCHEMA_FIXTURES)
        for f in SCHEMA_FIXTURES:
            r = validate_file(f)
            self.assertEqual(r["kind"], "protocol")
            self.assertTrue(r["valid"], errs(r)[:5])
            self.assertFalse(r["legacy"])

    def test_sha_matches_engine_version(self):
        f = SCHEMA_FIXTURES[0]
        p = Protocol.load(f)
        self.assertEqual(protocol_sha256(f)[:16], p.version)


class TestProtocolSchema(unittest.TestCase):
    def check(self, mutate):
        d = copy.deepcopy(MINI)
        mutate(d)
        return validate(d, "protocol")

    def test_minimal_v1_valid_not_legacy(self):
        r = validate(MINI, "protocol")
        self.assertTrue(r["valid"], errs(r))
        self.assertFalse(r["legacy"])
        self.assertEqual(r["warnings"], [])

    def test_schema_version_other_than_1_rejected(self):
        r = self.check(lambda d: d.update(schema_version="2"))
        self.assertFalse(r["valid"])

    def test_back_enum(self):
        r = self.check(lambda d: d["stages"]["q"]["presentation"].update(back="maybe"))
        self.assertIn("stages.q.presentation.back", " ".join(errs(r)))

    def test_cite_label_enum(self):
        r = self.check(lambda d: d["data"]["q"]["cite"].update(label="paraphrased"))
        self.assertTrue(any("data.q.cite.label" in e for e in errs(r)), errs(r))   # data is free-form; its cites are not
        d = copy.deepcopy(MINI)
        d["arms"][0]["cite"]["label"] = "paraphrased"
        r = validate(d, "protocol")
        self.assertFalse(r["valid"])
        self.assertTrue(any("arms[0].cite.label" in e for e in errs(r)), errs(r))

    def test_cite_needs_source(self):
        r = self.check(lambda d: d["arms"][0]["cite"].pop("source"))
        self.assertFalse(r["valid"])

    def test_response_kind_enum(self):
        r = self.check(lambda d: d["stages"]["q"]["responses"][0].update(kind="essay"))
        self.assertFalse(r["valid"])

    def test_unknown_flow_node(self):
        r = self.check(lambda d: d["flow"]["seq"].append({"goto": "q"}))
        self.assertFalse(r["valid"])

    def test_repeat_needs_on_max(self):
        r = self.check(lambda d: d["flow"]["seq"][1].pop("on_max"))
        self.assertFalse(r["valid"])

    def test_effect_op_enum(self):
        eff = {"id": "e", "unit": "s", "compute": {"op": "anova", "field": "x"}, "reported": {"value": 1}}
        r = self.check(lambda d: d["analysis"]["effects"].append(eff))
        self.assertFalse(r["valid"])
        eff["compute"]["op"] = "mean_difference"
        r = self.check(lambda d: d["analysis"]["effects"].append(eff))
        self.assertTrue(r["valid"], errs(r))

    def test_missing_required_top(self):
        r = self.check(lambda d: d.pop("keyed"))
        self.assertIn("missing required field 'keyed'", " ".join(errs(r)))

    def test_runnable_arm_needs_cite(self):
        r = self.check(lambda d: d["arms"][0].pop("cite"))
        self.assertFalse(r["valid"])
        r = self.check(lambda d: (d["arms"][0].pop("cite"), d["arms"][0].update(runnable=False)))
        self.assertTrue(r["valid"], errs(r))

    def test_unknown_field_reported_not_rejected(self):
        r = self.check(lambda d: d["stages"]["q"]["responses"][0].update(sparkle=True))
        self.assertTrue(r["valid"])
        self.assertTrue(any("sparkle" in m for _, m in r["warnings"]))

    def test_note_and_cite_suffixes_are_known(self):
        def m(d):
            d["stages"]["q"]["responses"][0]["range_note"] = "as printed"
            d["stages"]["q"]["responses"][0]["range_cite"] = [{"label": "reported", "source": "paper"}]
        r = self.check(m)
        self.assertTrue(r["valid"], errs(r))
        self.assertEqual(r["warnings"], [])

    def test_legacy_value_warns(self):
        r = self.check(lambda d: d["stages"]["q"]["responses"][0].update(widget="text_box"))
        self.assertTrue(r["valid"])
        self.assertTrue(any("legacy value" in m for _, m in r["warnings"]))


class TestStrictness(unittest.TestCase):
    """Review 1 (2026-11-08) B: the holes the mutation test found."""

    def check(self, mutate):
        d = copy.deepcopy(MINI)
        mutate(d)
        return validate(d, "protocol")

    def resp(self, d):
        return d["stages"]["q"]["responses"][0]

    def test_choice_multi_rank_need_options(self):
        for kind in ("choice", "multi", "rank"):
            with self.subTest(kind=kind):
                r = self.check(lambda d: (self.resp(d).update(kind=kind), self.resp(d).pop("range")))
                self.assertFalse(r["valid"])
                self.assertIn("options", " ".join(errs(r)))
                r = self.check(lambda d: self.resp(d).update(kind=kind, options=[]))
                self.assertFalse(r["valid"])
                r = self.check(lambda d: self.resp(d).update(kind=kind, options=[{"code": "1", "label": "Yes"}]))
                self.assertTrue(r["valid"], errs(r))
                r = self.check(lambda d: self.resp(d).update(kind=kind, options={"expr": "data['opts']"}))
                self.assertTrue(r["valid"], errs(r))

    def test_slider_scale_need_range(self):
        for kind in ("slider", "scale"):
            with self.subTest(kind=kind):
                r = self.check(lambda d: (self.resp(d).update(kind=kind), self.resp(d).pop("range")))
                self.assertFalse(r["valid"])
                self.assertIn("range", " ".join(errs(r)))
        r = self.check(lambda d: (self.resp(d).update(kind="number"), self.resp(d).pop("range")))
        self.assertTrue(r["valid"], errs(r))

    def test_runnable_arm_n_paper_integer(self):
        for bad in ("120", {"n": 120}, 1.5):
            with self.subTest(n=bad):
                self.assertFalse(self.check(lambda d: d["arms"][0].update(n_paper=bad))["valid"])
        self.assertFalse(self.check(lambda d: d["arms"][0].update(n_paper=None))["valid"])
        # n_paper null with n_operator (the operator passes n)
        r = self.check(lambda d: d["arms"][0].update(n_paper=None, n_operator="pass n explicitly"))
        self.assertTrue(r["valid"], errs(r))
        r = self.check(lambda d: d["arms"][0].update(n_paper="about 120", runnable=False))
        self.assertTrue(r["valid"], errs(r))

    def test_runtime_exclusion_applies_to_is_a_list(self):
        ex = {"id": "x", "if": "answer('q.x') > 90", "applies_to": "Study 2"}
        r = self.check(lambda d: d["exclusions"].append(ex))
        self.assertFalse(r["valid"])
        self.assertIn("exclusions[0].applies_to", " ".join(errs(r)))
        r = self.check(lambda d: d["exclusions"].append(dict(ex, applies_to=["m"])))
        self.assertTrue(r["valid"], errs(r))
        # analysis_exclusions are documentation: a prose string is still accepted there (5 legacy studies)
        r = self.check(lambda d: d.update(analysis_exclusions=[dict(ex, what="drop outliers")]))
        self.assertTrue(r["valid"], errs(r))

    def test_literal_on_screen_text_needs_cite(self):
        lit = {"id": "w", "value": "Welcome."}
        r = self.check(lambda d: d["stages"]["q"]["content"].append(lit))
        self.assertFalse(r["valid"])
        self.assertIn("stages.q.content[1]", " ".join(errs(r)))
        cite = {"label": "verbatim", "source": "paper", "page": 2}
        for ok in (dict(lit, cite=cite), {"id": "w", "value": {"text": "Welcome.", "cite": cite}},
                   {"id": "w", "value": {"expr": "data['q']"}}, {"id": "w", "value": "  "}):
            with self.subTest(ok=ok):
                r = self.check(lambda d: d["stages"]["q"]["content"].append(ok))
                self.assertTrue(r["valid"], errs(r))
        r = self.check(lambda d: d["stages"]["q"]["content"].append({"id": "w", "text": "Hello"}))
        self.assertFalse(r["valid"])

    def test_prompt_and_option_label_need_cite(self):
        def uncited(d):
            self.resp(d).update(kind="choice", options=[{"code": "1", "label": "Yes"}], prompt="Did he know?")
            self.resp(d).pop("range")
            self.resp(d).pop("cite", None)
        r = self.check(uncited)
        self.assertFalse(r["valid"])
        self.assertIn("responses[0].prompt", " ".join(errs(r)))
        self.assertIn("responses[0].options[0].label", " ".join(errs(r)))
        r = self.check(lambda d: (uncited(d), self.resp(d).update(cite={"label": "verbatim", "source": "paper"})))
        self.assertTrue(r["valid"], errs(r))
        r = self.check(lambda d: (uncited(d), self.resp(d).update(prompt="")))   # empty prompt: nothing shown
        self.assertEqual([e for e in errs(r) if ".prompt" in e], [])

    def test_unknown_arm_in_where(self):
        t = {"id": "m2", "unit": "s", "field": "x", "stat": "mean", "where": {"arm": "nope"}}
        r = self.check(lambda d: d["analysis"]["targets"].append(t))
        self.assertFalse(r["valid"])
        self.assertIn("analysis.targets[1].where.arm", " ".join(errs(r)))
        r = self.check(lambda d: d["analysis"]["targets"].append(dict(t, where={"arm": "main"})))
        self.assertTrue(r["valid"], errs(r))
        r = self.check(lambda d: d["analysis"]["targets"].append(dict(t, where={"arm": ["main", "ghost"]})))
        self.assertFalse(r["valid"])


class TestRound2(unittest.TestCase):
    """Review 2 (2026-11-08)."""

    def check(self, mutate):
        d = copy.deepcopy(MINI)
        mutate(d)
        return validate(d, "protocol")

    def resp(self, d):
        return d["stages"]["q"]["responses"][0]

    def test_data_is_optional(self):
        r = self.check(lambda d: d.pop("data") and d["stages"]["q"].update(content=[]))
        self.assertTrue(r["valid"], errs(r))

    def test_duplicate_response_id(self):
        r = self.check(lambda d: d["stages"]["q"]["responses"].append(copy.deepcopy(self.resp(d))))
        self.assertIn("duplicate response id 'x'", " ".join(errs(r)))

    def test_duplicate_option_code_warns(self):
        cite = {"label": "verbatim", "source": "paper"}
        r = self.check(lambda d: (self.resp(d).update(kind="choice", options=[
            {"code": 0, "label": "False", "cite": cite}, {"code": 0, "label": "Don't know", "cite": cite}]),
            self.resp(d).pop("range")))
        self.assertTrue(r["valid"], errs(r))
        self.assertTrue(any("duplicate option code 0" in m for _, m in r["warnings"]))

    def test_reversed_range(self):
        r = self.check(lambda d: self.resp(d).update(range=[100, 0]))
        self.assertIn("reversed range", " ".join(errs(r)))

    def test_unknown_target_unit(self):
        r = self.check(lambda d: d["analysis"]["targets"][0].update(unit="nope"))
        self.assertIn("analysis.targets[0].unit", " ".join(errs(r)))

    def test_nested_meta_cites(self):
        r = self.check(lambda d: d["meta"].update(conflicts=[{"what": "x", "cite": {"label": "quoted", "source": "p"}}]))
        self.assertIn("meta.conflicts[0].cite", " ".join(errs(r)))
        r = self.check(lambda d: d["meta"].update(conflicts=[{"what": "x", "cite": {"label": "reported", "source": "p"}}]))
        self.assertTrue(r["valid"], errs(r))

    def test_missing_gap_on_screen(self):
        gap = {"id": "g", "value": {"text": None, "cite": {"label": "missing", "source": "paper", "note": "not printed"}}}
        r = self.check(lambda d: (d["stages"]["q"]["content"].append(gap), d["arms"][0].update(runnable=False)))
        self.assertTrue(r["valid"], errs(r))
        bad = copy.deepcopy(gap)
        bad["value"]["cite"]["label"] = "reported"
        r = self.check(lambda d: (d["stages"]["q"]["content"].append(bad), d["arms"][0].update(runnable=False)))
        self.assertFalse(r["valid"])


class TestRule2(unittest.TestCase):
    """Review 3 S1: DESIGN §2 rule 2 statically — a runnable arm never reaches an on-screen missing gap."""
    GAP = {"text": None, "cite": {"label": "missing", "source": "paper", "note": "not printed"}}

    def proto(self, runnable=True, gate=None, item_if=None, value=None):
        d = copy.deepcopy(MINI)
        d["arms"].append({"id": "other", "n_paper": 5, "cite": {"label": "reported", "source": "paper"}})
        if not runnable:
            d["arms"][0]["runnable"] = False
        item = {"id": "g", "value": value if value is not None else copy.deepcopy(self.GAP)}
        if item_if:
            item["if"] = item_if
        d["stages"]["gap"] = {"content": [item]}
        node = {"stage": "gap"}
        if gate:
            node["if"] = gate
        d["flow"]["seq"].insert(0, node)
        return validate(d, "protocol")

    def rule2(self, r):
        return [e for e in errs(r) if "rule 2" in e]

    def test_runnable_arm_reaching_a_gap_is_an_error(self):
        self.assertTrue(self.rule2(self.proto()))
        self.assertTrue(self.rule2(self.proto(value={"expr": "data['missing']['x']"})))

    def test_gap_only_for_non_runnable_arms_is_fine(self):
        self.assertTrue(self.rule2(self.proto(gate="arm == 'other'")))   # 'other' is runnable too
        # gate it to an arm that is not runnable
        d = copy.deepcopy(MINI)
        d["arms"].append({"id": "blocked", "n_paper": 5, "runnable": False})
        d["stages"]["gap"] = {"content": [{"id": "g", "value": copy.deepcopy(self.GAP)}]}
        d["flow"]["seq"].insert(0, {"stage": "gap", "if": "arm in ('blocked',)"})
        self.assertEqual(self.rule2(validate(d, "protocol")), [])
        d["flow"]["seq"][0] = {"if": "arm == 'blocked'", "then": {"stage": "gap"}}
        self.assertEqual(self.rule2(validate(d, "protocol")), [])
        d["flow"]["seq"][0] = {"if": "arm != 'blocked'", "then": {"stage": "gap"}}
        self.assertTrue(self.rule2(validate(d, "protocol")))
        d["flow"]["seq"][0] = {"stage": "gap", "if": "answer('q.x') > 3"}   # unknown condition: reachable
        self.assertTrue(self.rule2(validate(d, "protocol")))
        d["flow"]["seq"][0] = {"stage": "gap"}
        d["stages"]["gap"]["content"][0]["if"] = "arm == 'blocked'"   # the item itself is gated
        self.assertEqual(self.rule2(validate(d, "protocol")), [])

    def test_response_cite_missing_is_not_a_gap(self):
        r = validate(MINI, "protocol")
        d = copy.deepcopy(MINI)
        d["stages"]["q"]["responses"][0]["required_cite"] = {"label": "missing", "source": "paper"}
        d["stages"]["q"]["responses"][0]["cite"] = {"label": "missing", "source": "paper", "note": "required?"}
        self.assertEqual(self.rule2(validate(d, "protocol")), [])
        self.assertEqual(self.rule2(r), [])


class TestStudyAndRun(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        (self.dir / "protocol.json").write_text(json.dumps(MINI))
        self.study = {"schema_version": "1", "id": "mini", "title": "Mini", "authors": ["A. Author"], "year": 2020,
                      "doi": "10.1234/abc.5", "version": "1.0.0", "quality": "checked",
                      "licence": {"paper": "CC-BY-4.0", "materials": "CC-BY-4.0"}, "release_hold": None,
                      "protocol": {"path": "protocol.json", "sha256": canonical_sha256(MINI), "schema_version": "1"}}
        self.run = {"schema_version": "1", "study": {"id": "mini", "version": "1.0.0"},
                    "protocol": {"schema_version": "1", "sha256": canonical_sha256(MINI)},
                    "model": {"id": "anthropic/claude-haiku", "provider": "openrouter", "params": {"temperature": 1}},
                    "persona": {"kind": "preset", "preset": "v2_human"},
                    "prompt": {"rendering": "hsenv.render.text_v1", "answer_format": "json", "per": "page"},
                    "memory": {"policy": "full", "includes": ["seen", "answered"]},
                    "retries": {"max": 2, "on": ["invalid_answer"], "on_exhausted": "null", "feedback": "state_error"},
                    "seeds": [1, 2], "n": "paper"}

    def tearDown(self):
        self.tmp.cleanup()

    def test_study_valid_and_sha_verified(self):
        p = self.dir / "study.json"
        p.write_text(json.dumps(self.study))
        r = validate_file(p, verify_sha=True)
        self.assertTrue(r["valid"], errs(r))
        self.study["protocol"]["sha256"] = "0" * 64
        p.write_text(json.dumps(self.study))
        r = validate_file(p, verify_sha=True)
        self.assertFalse(r["valid"])

    def test_study_quality_enum_and_strict(self):
        s = dict(self.study, quality="gold")
        self.assertFalse(validate(s, "study")["valid"])
        s = dict(self.study, extra=1)
        self.assertFalse(validate(s, "study")["valid"])

    def test_run_valid(self):
        r = validate(self.run, "run")
        self.assertTrue(r["valid"], errs(r))

    def test_run_requires_memory_and_seeds(self):
        for k in ("memory", "seeds", "retries", "persona"):
            d = {x: v for x, v in self.run.items() if x != k}
            self.assertFalse(validate(d, "run")["valid"], k)

    def test_cli_exit_codes(self):
        good = self.dir / "run.json"
        good.write_text(json.dumps(self.run))
        bad = self.dir / "bad.run.json"
        bad.write_text(json.dumps(dict(self.run, n=0)))
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(main([str(good)]), 0)
            self.assertEqual(main([str(bad)]), 1)
            self.assertEqual(main([str(self.dir / "nope.json")]), 2)
            self.assertEqual(main(["--json", str(good)]), 0)


class TestSchemasAreDraft202012(unittest.TestCase):
    def test_meta(self):
        for k in ("protocol", "study", "run"):
            s = load_schema(k)
            self.assertEqual(s["$schema"], "https://json-schema.org/draft/2020-12/schema")

    @unittest.skipUnless(os.environ.get("HSENV_JSONSCHEMA"), "set HSENV_JSONSCHEMA=1 with jsonschema installed")
    def test_independent_validator_agrees(self):
        import jsonschema
        for k in ("protocol", "study", "run"):
            jsonschema.Draft202012Validator.check_schema(load_schema(k))
        v = jsonschema.Draft202012Validator(load_schema("protocol"))
        for f in SCHEMA_FIXTURES:
            with self.subTest(study=Path(f).parent.name):
                self.assertEqual(list(v.iter_errors(json.loads(Path(f).read_text()))), [])
        for mutate in (lambda d: d["stages"]["q"]["responses"][0].pop("range"),
                       lambda d: d["arms"][0].update(n_paper="10"),
                       lambda d: d["exclusions"].append({"id": "x", "applies_to": "Study 2"})):
            d = copy.deepcopy(MINI)
            mutate(d)
            self.assertTrue(list(v.iter_errors(d)))


if __name__ == "__main__":
    unittest.main()
