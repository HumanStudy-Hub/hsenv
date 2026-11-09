"""Engine pass 2 (sandbox lesson.md "NEXT ENGINE PASS" and "Engine pass also" items): matcher fixes (review-5 M1/M2,
joins, quotes, cells, marks, normalisation, style report), blocked group arms, hidden expression ranges, per-group
unit arms, roles in States, statistic vocabulary, printed item data, public-package pieces."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from hsenv.checks import check_verbatim, play, printed_item_tests, statistic_vocabulary
from hsenv.engine import Env, Protocol

ROOT = Path(__file__).resolve().parents[1]
_V3 = None


def setUpModule():   # these readings predate the v3 reader prompt: read them as LEGACY (pass 3 format gate)
    global _V3
    import hsenv.checks as hc
    _V3, hc._is_v3 = hc._is_v3, (lambda reading: False)


def tearDownModule():
    import hsenv.checks as hc
    hc._is_v3 = _V3
CITE = {"label": "verbatim", "source": "s", "page": 1, "read": "image"}


def proto(*texts, page=1, data=None, stages=None):
    c = dict(CITE, page=page)
    return SimpleNamespace(data=data if data is not None else {"items": [{"text": t, "cite": dict(c)} for t in texts]},
                           stages=stages or {}, raw={"id": "fakestudy", "meta": {"sources": {"s": {"file": "s.pdf"}}}})


def found(text, reading, page=1):
    return check_verbatim(proto(text, page=page), {"s#second": reading})["found"]


class MatcherM1(unittest.TestCase):
    R = "p1 | 1 | text | Welcome to the study. Please read carefully.\np1 | 1 | text | You will be paid at the end. Thank you."

    def test_pieces_must_touch_the_line_break(self):
        self.assertEqual(found("Welcome to the study.\nThank you.", self.R), 0)   # review-5 M1 attack
        self.assertEqual(found("Please read carefully.\nYou will be paid at the end.", self.R), 1)
        self.assertEqual(found("Welcome to the study. Thank you.", self.R), 0)

    def test_middle_pieces_are_whole_fields(self):
        r = "p1 | 1 | text | A. B.\np1 | 1 | text | C. D.\np1 | 1 | text | E."
        self.assertEqual(found("B.\nC.\nE.", r), 0)
        self.assertEqual(found("B.\nC. D.\nE.", r), 1)


class MatcherM2(unittest.TestCase):
    def prot(self, value_expr, before, after):
        c = dict(CITE)
        data = {"g": {"a": {"text": before, "cite": dict(c)}, "b": {"text": after, "cite": dict(c)}}}
        tpl = "{'text': data['g']['a']['text'] + ' ' + %s + ' ' + data['g']['b']['text']}" % value_expr
        return proto(data=data, stages={"s": {"content": [{"id": "x", "value": {"expr": tpl}}]}})

    def test_values_cannot_absorb_words_or_units(self):
        p = self.prot("str(answer('s.q'))", "You will", "points.")
        self.assertEqual(check_verbatim(p, {"s#second": "p1 | 1 | text | You will earn 5 points."})["found"], 0)
        self.assertEqual(check_verbatim(p, {"s#second": "p1 | 1 | text | You will 5 points."})["found"], 2)
        p = self.prot("str(answer('s.q'))", "A bonus of", "will be added.")
        self.assertEqual(check_verbatim(p, {"s#second": "p1 | 1 | text | A bonus of GBP 3 will be added."})["found"], 0)

    def test_unit_allowed_when_the_expression_renders_it(self):
        p = self.prot("('GBP ' + str(answer('s.q')) if answer('s.q') else '0')", "A bonus of", "will be added.")
        self.assertEqual(check_verbatim(p, {"s#second": "p1 | 1 | text | A bonus of GBP 3 will be added."})["found"], 2)
        self.assertEqual(check_verbatim(p, {"s#second": "p1 | 1 | text | A bonus of EUR 3 will be added."})["found"], 0)


class MatcherJoins(unittest.TestCase):
    def test_question_printed_on_several_lines_with_outer_quotes(self):
        r = ('p1 | 1 | question | “Which one resembles\np1 | 1 | question | most closely (a) ‘quick’?\n'
             'p1 | 1 | question | (b) ‘slow’?”\np1 | 1 | note | [note: italics]')
        self.assertEqual(found("Which one resembles most closely (a) 'quick'? (b) 'slow'?", r), 1)
        self.assertEqual(found("most closely (a) 'quick'? (b) 'slow'?", r), 0)   # a part of the join

    def test_style_change_split(self):
        r = "p1 | 1 | text | You have been asked to take part. For this\np1 | 1 | text | italic | we pay you $3."
        self.assertEqual(found("You have been asked to take part. For this we pay you $3.", r), 1)

    def test_whole_line_quotes(self):
        r = 'p1 | 1 | question | z in italics | “Suppose you ran a study.”'
        self.assertEqual(found("Suppose you ran a study.", r), 1)
        self.assertEqual(found('"Suppose you ran a study."', r), 1)
        self.assertEqual(found("Suppose", 'p1 | 1 | text | "Suppose" he said.'), 0)

    def test_two_line_cells(self):
        r = ("p1 | 1 | cell | row A / column X, line 1 | You: 20\np1 | 1 | cell | row A / column X, line 2 | Other: 20\n"
             "p1 | 1 | cell | row A / column Y, line 1 | You: 5\np1 | 1 | cell | row A / column Y, line 2 | Other: 25")
        self.assertEqual(found("You: 20\nOther: 20", r), 1)
        self.assertEqual(found("You: 5\nOther: 25", r), 1)
        self.assertEqual(found("Other: 20\nYou: 5", r), 0)   # two different cells

    def test_page_join_skips_notes_and_soft_marks(self):
        r = ("p3 | 1 | text | The experiment starts. Only the person [partial]\n"
             "p3 | 1 | note | [note: continues on p. 4]\np4 | 1 | text | [partial] who opened it will know.")
        self.assertEqual(found("The experiment starts. Only the person who opened it will know.", r, page="3-4"), 1)
        self.assertEqual(found("Only the person who opened it will know.", r, page="3-4"), 0)   # whole join only
        self.assertEqual(found("The experiment starts.", r, page=3), 0)   # a [partial] line never confirms alone
        hard = r.replace("[partial] who", "[uncertain: who] who")
        self.assertEqual(found("The experiment starts. Only the person who opened it will know.", hard, page="3-4"), 0)

    def test_two_line_label(self):
        r = "p1 | 2 | label | row label, two lines | Number of persons / Choosing this amount"
        self.assertEqual(found("Number of persons Choosing this amount", r), 1)
        self.assertEqual(found("Yes No", "p1 | 2 | option | Yes / No"), 0)

    def test_underscores_and_minus(self):
        self.assertEqual(found("Identification Number ____A", "p1 | 1 | text | Identification Number _________A"), 1)
        self.assertEqual(found("−3 points", "p1 | 1 | text | -3 points"), 1)

    def test_style_report(self):
        v = check_verbatim(proto("Pay now."), {"s#second": "p1 | 1 | text | italic | Pay now."})
        self.assertEqual(v["found"], 1)
        self.assertEqual([x[-1] for x in v["style_unserved"]], [["italic"]])
        p = proto("Pay now.")
        p.data["items"][0]["spans"] = [{"start": 0, "end": 3, "style": "italic"}]
        self.assertEqual(check_verbatim(p, {"s#second": "p1 | 1 | text | italic | Pay now."})["style_unserved"], [])


class BlockedGroupArmsAndRanges(unittest.TestCase):
    def test_blocked_group_arm_runs_as_group_and_errors_are_reported(self):
        prot = {"id": "g", "data": {},
                "arms": [{"id": "ok", "n_paper": 1, "group_size": 2}, {"id": "two", "group_size": 2, "runnable": False, "why": "t"}],
                "stages": {"q": {"responses": [{"id": "a", "kind": "number", "range": [0, 9], "prompt": "n"}]}},
                "flow": [{"stage": "q"}, {"sync": "s", "compute": {"tot": "sum(group('q.a'))"}}, {"stage": "q"}]}
        _, probs, stats = play(Protocol(prot), 2, 1)
        self.assertEqual((probs, stats["blocked_arm_problems"]), ([], []))
        self.assertNotIn("q", stats["unreached_stages"])
        prot["flow"][1]["compute"] = {"tot": "sum(group('q.a')) / 0"}
        _, _, stats = play(Protocol(prot), 2, 1)
        self.assertTrue(any("blocked arm two" in x for x in stats["blocked_arm_problems"]))

    def test_hidden_expression_range(self):
        prot = {"id": "r", "data": {"hi": 10}, "stages": {"q": {"responses": [
            {"id": "a", "kind": "number", "range": {"expr": "[0, data['hi']]"}, "range_visible": False, "prompt": "n"}]}},
            "flow": {"stage": "q"}}
        env = Env(Protocol(prot))
        s = env.open(env.design(n=1)[0])
        st = s.reset()
        r = st["screen"]["responses"][0]
        self.assertNotIn("range", r)
        self.assertIn("error", s.step({r["id"]: 11}))
        self.assertTrue(s.step({r["id"]: 5}).get("done"))


class GroupUnitArmsAndRoles(unittest.TestCase):
    P = {"id": "u", "data": {},
         "arms": [{"id": "a1", "n_paper": 1, "group_size": 2}, {"id": "a2", "n_paper": 1, "group_size": 2}],
         "roles": [{"member": 1, "id": "room_a", "label": "proposer", "shown": {"text": "Room A", "cite": {"label": "reported"}}},
                   {"member": 2, "id": "room_b", "shown": {"text": "Room B", "cite": {"label": "reported"}}}],
         "stages": {"q": {"responses": [{"id": "a", "kind": "number", "range": [0, 9], "prompt": "n"}]}},
         "flow": [{"stage": "q"}, {"sync": "s"}],
         "units": {"g1": {"per": "group", "arms": ["a1"], "fields": {"m": "mean(group('q.a'))"}}}}

    def run_all(self):
        env = Env(Protocol(self.P))
        states = []
        for spec in env.design(n=1):
            g = env.open(spec)
            st = g.reset()
            states.append(dict(st))
            for pid in ("p1", "p2"):
                st = g.step(pid, {st[pid]["screen"]["responses"][0]["id"]: 3})
                states.append(dict(st))
        return env, states

    def test_group_unit_respects_arms(self):
        env, _ = self.run_all()
        self.assertEqual([r["arm"] for r in env.unit_tables()["g1"]], ["a1"])

    def test_role_in_every_state(self):
        _, states = self.run_all()
        for st in states:
            self.assertEqual(st["p1"]["role"], "Room A")
            self.assertEqual(st["p2"]["role"], "Room B")
        self.assertNotIn("proposer", json.dumps(states))


class ReportsOnEffects(unittest.TestCase):
    def test_statistic_vocabulary_and_printed_items(self):
        eff = {"id": "e", "unit": "s", "contrast": {"treatment": "t", "reference": "c"},
               "compute": {"op": "mean_difference", "field": "x", "groupBy": "arm"},
               "reported": {"value": 1.0, "test": {"statistic": "mann_whitney", "value": 9.9}}}
        rows = [{"arm": "t", "x": v} for v in (2, 3, 4)] + [{"arm": "c", "x": v} for v in (1, 2, 3)]
        p = SimpleNamespace(raw={"analysis": {"effects": [eff], "printed_items": {"s": {"rows": rows, "cite": {}}}}})
        self.assertEqual(statistic_vocabulary(p), [{"effect": "e", "statistic": "mann_whitney"}])
        out = printed_item_tests(p)
        self.assertEqual((out[0]["value_ok"], out[0]["test_ok"]), (True, False))


class PublicPackage(unittest.TestCase):
    def test_release_paths(self):
        from hsenv import release
        self.assertIn("protocol.json", release.PUBLIC_PATHS)
        self.assertTrue(release.is_public("sources/open/a.pdf"))
        self.assertTrue(release.is_public("review/fidelity-review-1.md"))
        for bad in ("sources/private/a.pdf", "runs/x/records.jsonl", "bundle.json", "../protocol.json", "notes.md"):
            self.assertFalse(release.is_public(bad), bad)

    def test_protocol_capabilities(self):
        from hsenv.capabilities import protocol_capabilities
        self.assertEqual(protocol_capabilities({"arms": [{"id": "a", "runnable": False}],
                                                "analysis": {"effects": [{"reported": {"value": 1}}]}}),
                         {"replayable": False, "humanBenchmark": True})
        self.assertEqual(protocol_capabilities({"arms": [{"id": "a", "release_hold": "x"}, {"id": "b"}]}),
                         {"replayable": True, "humanBenchmark": False})

    def test_study_schema_release_fields(self):
        from hsenv.schema_check import validate
        study = {"schema_version": "1", "id": "x1", "title": "t", "authors": ["A"], "year": 2026, "version": "1.0.0",
                 "quality": "high_fidelity", "licence": {"paper": "CC0-1.0", "materials": "CC0-1.0"},
                 "protocol": {"path": "protocol.json", "sha256": "0" * 64, "schema_version": "1"},
                 "contributors": [{"name": "N", "github": "n"}], "visibility": "public",
                 "fidelity": {"verdict": "HIGH FIDELITY", "signed_by": "m"}, "slug": "x1", "hsenv": ">=0.8,<0.9",
                 "arms": [{"id": "main", "runnable": True}]}
        res = validate(study, "study")
        errs = res[0] if isinstance(res, tuple) else res.get("errors")
        self.assertEqual(errs, [])

    def test_report_hash_and_public_mode(self):
        with tempfile.TemporaryDirectory() as d:
            prot = {"id": "pub", "data": {"t": {"text": "Hello", "cite": {"label": "verbatim", "source": "closed"}}},
                    "meta": {"sources": {"closed": {"file": "x.pdf"}}},
                    "arms": [{"id": "main", "n_paper": 1}],
                    "stages": {"s": {"content": [{"id": "i", "value": {"expr": "data['t']"}}],
                                     "responses": [{"id": "a", "kind": "number", "range": [0, 9], "range_visible": True,
                                                    "prompt": "Your number"}]}},
                    "flow": {"stage": "s"}}
            Path(d, "protocol.json").write_text(json.dumps(prot))
            run = lambda *extra: json.loads(subprocess.run([sys.executable, "-m", "hsenv.checks", d, "--sessions", "5", *extra],
                                                          cwd=ROOT, capture_output=True, text=True).stdout)
            r = run()
            from hsenv.schema_check import canonical_sha256
            self.assertEqual(r["protocol_sha256"], canonical_sha256(prot))
            self.assertEqual((r["PASS"], r["verbatim"]["unchecked"]), (False, 1))
            r = run("--public")
            self.assertEqual((r["PASS"], r["verbatim"]["checked_privately"], r["public"]), (True, ["closed"], True))
            prot["arms"][0]["release_hold"] = "licence"
            Path(d, "protocol.json").write_text(json.dumps(prot))
            self.assertFalse(run("--public")["PASS"])

    def test_licence_is_benchs(self):
        self.assertIn('license = { text = "MIT" }', (ROOT / "pyproject.toml").read_text())
        self.assertTrue((ROOT / "LICENSE").read_text().startswith("MIT License"))


if __name__ == "__main__":
    unittest.main()
