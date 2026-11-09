import json
import math
import unittest
from pathlib import Path

from hsenv import checks
from hsenv import rewards as R
from hsenv.engine import Protocol
from hsenv.evaldata import EvalData, agent_n, baseline_run, human_effect, human_target, parse_p, simulate

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "studies"   # invented CC0 fixtures; real studies: private suite


def proto(effects, targets=(), exclusions=(), keyed=None):
    """Two arms; one slider (0-100) and one attention choice. keyed: rating by arm."""
    return Protocol({
        "id": "syn", "data": {},
        "arms": [{"id": "a", "n_paper": 60}, {"id": "b", "n_paper": 60}],
        "stages": {"q": {"responses": [
            {"id": "x", "kind": "slider", "range": [0, 100], "prompt": "rate"},
            {"id": "att", "kind": "choice", "prompt": "pick one",
             "options": [{"code": 1, "label": "one"}, {"code": 2, "label": "two"}]}]}},
        "flow": {"stage": "q"},
        "exclusions": list(exclusions),
        "units": {"p": {"per": "session", "fields": {"x": "answer('q.x')", "hi": "answer('q.x') > 50"}}},
        "keyed": {"answers": keyed or {"q.x": "(50 if bernoulli(0.5) else 90) if arm == 'a' else (20 if bernoulli(0.5) else 60)",
                                         "q.att": "1"}},
        "analysis": {"effects": list(effects), "targets": list(targets), "unsupported": []},
    })


def md(id_, reported, role="test", **kw):
    return dict({"id": id_, "unit": "p", "role": role, "contrast": {"kind": "two_groups", "treatment": "a", "reference": "b"},
                 "compute": {"op": "mean_difference", "field": "x", "groupBy": "arm"}, "reported": reported}, **kw)


CELLS = {"cells": {"a": {"mean": 70, "sd": 20, "n": 60}, "b": {"mean": 40, "sd": 20, "n": 60}},
         "test": {"statistic": "t", "value": 8.2, "df": 118, "p": "<.001"}, "cite": {"label": "verbatim"}}


def build(p, policy="keyed", seeds=(1, 2), n=None):
    n = n or agent_n(p)[0]
    runs = [simulate(p, policy, n, s) for s in seeds]
    return EvalData.build(p, runs, baseline=baseline_run(p, n, 0))


class HumanSide(unittest.TestCase):
    def test_cells_give_value_se_p(self):
        h, nc = human_effect(md("e", CELLS))
        self.assertAlmostEqual(h["value"], 30)
        self.assertAlmostEqual(h["se"], math.sqrt(400 / 60 * 2))
        self.assertEqual((h["p"], h["p_relation"]), (0.001, "<"))
        self.assertEqual(h["direction"], 1)
        self.assertEqual(h["n"], 120)
        self.assertEqual(nc, {})

    def test_missing_numbers_are_reasons_not_zeros(self):
        h, nc = human_effect(md("e", {"cite": {}}))
        self.assertIsNone(h["value"])
        self.assertIsNone(h["p"])
        self.assertIn("human_value", nc)
        self.assertIn("human_p", nc)
        self.assertIn("human_n", nc)

    def test_no_uncertainty_and_compare_as(self):
        h, nc = human_effect(md("e", {"value": 3.0, "n": 100, "no_uncertainty": "mixed model"}))
        self.assertEqual(h["value"], 3.0)
        self.assertIsNone(h["se"])
        self.assertTrue(nc["human_se"].startswith("no_uncertainty"))
        e = md("e", {"value": 1.6, "n": 50})
        e["compute"]["compareAs"] = {"metric": "regression_coefficient", "reason": "log-odds"}
        h, nc = human_effect(e)
        self.assertIsNone(h["value"])
        self.assertIn("compareAs", nc["human_value"])
        self.assertEqual(h["direction"], 1)   # the sign is still read (direction_match)

    def test_se_from_t_and_p_from_stat(self):
        h, _ = human_effect(md("e", {"value": 2.0, "n": 100, "test": {"statistic": "t", "value": 4.0, "df": 98}}))
        self.assertAlmostEqual(h["se"], 0.5)
        self.assertTrue(h["p_basis"].startswith("derived"))
        self.assertLess(h["p"], 0.001)

    def test_paired_se_from_paired_t(self):
        e = md("e", {"value": 2.0, "n": 50, "test": {"statistic": "t", "value": 4.0, "df": 49}})
        e["compute"]["op"] = "paired_difference"
        self.assertAlmostEqual(human_effect(e)[0]["se"], 0.5)
        e = md("e", {"value": 2.0, "n": 50, "test": {"statistic": "t", "value": 4.0, "df": 49, "type": "paired"}})
        self.assertIsNone(human_effect(e)[0]["se"])   # a paired t is not the SE of a between difference

    def test_parse_p_and_stars(self):
        self.assertEqual(parse_p("<.001"), (0.001, "<"))
        self.assertEqual(parse_p(".051 (Table 14); '.51' in the text"), (0.051, "="))
        self.assertEqual(parse_p(0.2), (0.2, "="))
        h, _ = human_effect(md("e", {"value": 1.0, "sig": "ns"}))
        self.assertEqual((h["p"], h["p_relation"]), (0.05, ">"))

    def test_review_fixes(self):
        self.assertEqual(parse_p("P < 0.001"), (0.001, "<"))
        self.assertEqual(parse_p("1.2e-5"), (1.2e-5, "="))
        self.assertEqual(parse_p("ns"), (0.05, ">"))
        e = md("e", {"cells": {"a": {"mean": 5, "n": 40}, "b": {"mean": 4, "n": 40}}})
        e["compute"]["op"] = "paired_difference"
        self.assertEqual(human_effect(e)[0]["n"], 40)          # paired: the same people, not 80
        e = md("e", {"test": {"statistic": "chi_square", "value": 9.1, "df": 3}})
        e["compute"] = {"op": "contingency", "field": "x", "groupBy": "arm"}
        h, nc = human_effect(e)
        self.assertIsNone(h["direction"])                        # chi-square has no sign
        h, nc = human_effect(md("e", {"value": 1.0, "n": 50}, direction_claimed=False))
        self.assertIsNone(h["p"])                                # a reading is not a p
        self.assertTrue(h["declared_ns"])
        h, nc = human_effect(md("e", {"value": 2.0, "n": 100, "no_uncertainty": "pooled with other rows",
                                      "test": {"statistic": "t", "value": 4.0, "df": 2000}}))
        self.assertIsNone(h["p"])                                # the test is not this estimand

    def test_declared_basis_is_honoured(self):
        h, _ = human_effect(md("e", {"value": 0.2, "se": 0.05, "n": 300,
                                     "value_note": "derived, not printed: from the printed joint counts",
                                     "se_note": "derived, not printed: from the printed joint counts"}))
        self.assertTrue(h["value_basis"].startswith("derived (derived, not printed"))
        self.assertTrue(h["se_basis"].startswith("derived ("))
        self.assertEqual(h["p_basis"], "derived: z = value / SE (derived SE)")
        h, _ = human_effect(md("e", {"value": 0.2, "se": 0.05, "n": 300, "se_basis": "reported (Table 2)"}))
        self.assertEqual(h["se_basis"], "reported (Table 2)")
        self.assertEqual(h["value_basis"], "printed value")

    def test_target_share_and_mean(self):
        h, nc = human_target({"id": "t", "stat": "share", "human": {"k": 30, "n": 100}})
        self.assertAlmostEqual(h["value"], 0.3)
        h, nc = human_target({"id": "t", "stat": "mean", "human": {"value": 5, "sd": 2, "n": 100}})
        self.assertAlmostEqual(h["se"], 0.2)
        h, nc = human_target({"id": "t", "stat": "median", "human": {"value": 5, "n": 100}})
        self.assertIn("human_se", nc)


class Rewards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        effects = [md("main", CELLS),
                   md("desc", CELLS, role="descriptive"),
                   md("mismatch", CELLS, reference_mismatch="pooled sample", scoring="direction_only"),
                   md("susp", CELLS, suspect="duplicated column"),
                   md("blank", {"cite": {}})]
        targets = [{"id": "ta", "unit": "p", "field": "x", "stat": "mean", "where": {"arm": "a"}, "effect": "main",
                    "human": {"value": 70, "sd": 20, "n": 60}},
                   {"id": "share_a", "unit": "p", "field": "hi", "stat": "share", "success": True, "where": {"arm": "a"},
                    "human": {"k": 50, "n": 60}}]
        cls.p = proto(effects, targets, exclusions=[{"id": "attention", "if": "answer('q.att') != 1"}])
        cls.keyed = build(cls.p, "keyed")
        cls.random = build(cls.p, "random")

    def test_registry_and_spec(self):
        for rid in R.DEFAULT:
            self.assertIn(rid, R.REGISTRY)
        r = R.score(self.keyed, "significance_match")   # unversioned name resolves to the latest
        self.assertEqual(r.spec["id"], "significance_match-v1")
        self.assertIn("test + paper_claim", r.spec["default_set"])
        with self.assertRaises(Exception):
            r.value = 1   # frozen

    def test_keyed_matches_direction_and_significance(self):
        self.assertEqual(R.score(self.keyed, "significance_match-v1").value, 1.0)
        dm = R.score(self.keyed, "direction_match-v2")
        self.assertEqual(dm.value, 1.0)
        self.assertIn("effect:mismatch", dm.per_effect)          # direction_only counts for direction
        self.assertNotIn("effect:desc", dm.per_effect)           # descriptive: reported only
        self.assertIn("effect:desc", dm.spec["reported_only"])
        self.assertIn("effect:susp", dm.not_computable)          # suspect never scored
        sm = R.score(self.keyed, "significance_match-v1")
        self.assertIn("effect:mismatch", sm.not_computable)      # the printed p is another sample's

    def test_not_computable_is_never_zero(self):
        for rid in ("significance_match-v1", "direction_match-v2", "effect_gap-v1", "human_noise_score-v1"):
            r = R.score(self.keyed, rid)
            self.assertIn("effect:blank", r.not_computable, rid)
            self.assertNotIn("effect:blank", r.per_effect, rid)

    def test_noise_score_keyed_vs_random(self):
        k = R.score(self.keyed, "human_noise_score-v1")
        r = R.score(self.random, "human_noise_score-v1")
        self.assertIsNotNone(k.value)
        self.assertEqual(k.per_effect["effect:main"], 1.0)   # keyed means 70 vs 40, SD 20 = the human cells
        self.assertLess(k.per_effect["target:share_a"], 0.5)   # keyed share ~.5 (50 or 90) vs human 50/60 (logit)
        self.assertLess(k.value, 0.8)   # two effect groups weighted 1 each: (main + ta) and share_a
        self.assertLess(r.value, 0.35)
        self.assertGreater(k.spec["s_null"], 0.5)

    def test_validity_and_loglik(self):
        self.assertEqual(R.score(self.keyed, "validity-v0").value, 1.0)
        v = R.score(self.random, "validity-v0")
        self.assertLess(v.value, 0.8)          # random answers fail the attention check about half the time
        self.assertIn("attention", v.spec["invalid_by_reason"])
        ll = R.score(self.keyed, "loglik-v0")
        self.assertIsNone(ll.value)
        self.assertIn("individual human data", ll.not_computable["*"])

    def test_json_round_trip_and_rescore(self):
        d = json.loads(json.dumps(self.keyed.to_dict(), default=str))
        ev2 = EvalData.from_dict(d)
        self.assertEqual(R.score(ev2, "direction_match-v2").value, R.score(self.keyed, "direction_match-v2").value)

    def test_verifier_and_combined(self):
        v = R.Verifier("direction_match-v2", threshold=0.9).evaluate(self.keyed)
        self.assertTrue(v.passed)
        v = R.Verifier("direction_match-v2", rule="all").evaluate(self.random)
        self.assertIn(v.passed, (True, False))
        c = R.combined(self.keyed, {"id": "mix-v1", "parts": [{"fn": "significance_match", "weight": 0.5},
                                                              {"fn": "direction_match", "weight": 0.5}]})
        self.assertEqual(c.value, 1.0)

    def test_effects_filter(self):
        r = R.score(self.keyed, "direction_match-v2", effects=["main"])
        self.assertEqual(list(r.per_effect), ["effect:main"])


class Degenerate(unittest.TestCase):
    def test_zero_variance_exploit_is_not_rewarded(self):
        """Review 2 M1: every participant of an arm gives the human cell mean (70 / 40): exact direction, exact gap,
        no variance. Before: sig = dir = noise = range = 1. Now an agent-side failure for every reward."""
        p = proto([md("main", CELLS)], keyed={"q.x": "70 if arm == 'a' else 40", "q.att": "1"})
        ev = build(p, "keyed", seeds=(1,))
        side = ev.items[0]["agent"]["per_seed"][0]
        self.assertIsNone(side["p"])
        self.assertIn("zero within-arm variance", side["reason"])
        for rid in ("significance_match", "direction_match", "human_noise_score", "within_human_range"):
            r = R.score(ev, rid)
            self.assertEqual(r.per_effect["effect:main"], 0.0, rid)
            self.assertIn("effect:main", r.spec["agent_side_failed"], rid)
        self.assertIsNone(R.score(ev, "effect_gap").value)


class Floor(unittest.TestCase):
    def test_baseline_uses_no_internals(self):
        """A quiz whose accepted answer is only in the protocol (validate.equals) blocks the State-only floor: the
        baseline is not computable with its completion rate, never an assisted baseline."""
        p = proto([md("main", CELLS)])
        p.stages["q"]["responses"].append({"id": "quiz", "kind": "number", "range": [0, 1000000], "prompt": "type the code",
                                           "integer": True, "validate": {"equals": 737, "message": "wrong"}})
        ev = build(p, "keyed", seeds=(1,), n={"a": 20, "b": 20})
        self.assertEqual(ev.d["baseline"]["policy"], "floor")
        self.assertEqual(ev.d["baseline"]["completed"], 0)
        self.assertIn("baseline_not_computable", ev.items[0]["not_computable"]["baseline"])
        r = R.score(ev, "human_noise_score-v1")
        self.assertIn("baseline_not_computable", r.not_computable["effect:main"])


def fake_ev(human, agent_seeds, baseline=None, plan_factor=1.0, scoring="full", kind="effect"):
    """A one-item EvalData for rule tests (no simulation)."""
    item = {"key": "%s:e" % kind, "id": "e", "kind": kind, "group": "e", "role": "test", "role_declared": True,
            "default_scored": True, "scoring": scoring, "scoring_why": None, "scale": "raw", "op": "mean_difference",
            "human": dict({"value": 1.0, "value_s": 1.0, "se": 0.1, "se_s": 0.1, "n": 100, "p": 0.001,
                           "p_relation": "=", "direction": 1, "direction_na": False, "p_tail": "two-sided"}, **human),
            "direction_claimed": None,
            "agent": {"per_seed": agent_seeds, "pooled": None, "se_a": None}, "baseline": baseline,
            "not_computable": {}}
    return EvalData({"schema": "hsenv-evaldata-1", "study": "fake", "version": "x", "seeds": list(range(len(agent_seeds))),
                     "items": [item], "plan": {"factor": plan_factor, "official": True},
                     "sessions": {"per_seed": [{"seed": i, "run_status": "ok", "rows": []} for i in range(len(agent_seeds))]},
                     "provenance": {"protocol_sha16": "p", "code_sha16": "c"}})


class ReviewRound1(unittest.TestCase):
    def test_m1_small_run_is_refused_not_easier(self):
        p = proto([md("main", CELLS)])
        runs = [simulate(p, "keyed", {"a": 6, "b": 6}, 1, top_up=False)]
        ev = EvalData.build(p, runs, baseline=baseline_run(p, {"a": 60, "b": 60}, 0), planned={"a": 60, "b": 60})
        for rid in ("human_noise_score", "within_human_range", "significance_match"):
            r = R.score(ev, rid)
            self.assertIsNone(r.value, rid)
            self.assertFalse(r.passed)
            self.assertEqual(r.spec["status"], "underpowered_run")

    def test_m1_planned_n_sets_the_range(self):
        base = {"value_s": 0.0, "se_s": 0.05}
        near = fake_ev({}, [{"value": 1.4, "value_s": 1.4, "n": 4, "p": 0.01, "direction": 1}], base, plan_factor=1.0)
        t, _ = R.noise_terms(near, near.items[0], 0)
        self.assertAlmostEqual(t["se_hn"], 0.1)            # planned n = human n: the observed n = 4 is ignored
        self.assertEqual(t["status"], "outside_human_range")   # d = .4 > m = 1.96 * .1414 (observed n = 4 would give m = .99)

    def test_m2_degenerate_constant_answers_do_not_score_well(self):
        p = proto([md("main", CELLS)], keyed={"q.x": "50", "q.att": "1"})
        ev = build(p, "keyed", seeds=(1,))
        sm = R.score(ev, "significance_match")
        self.assertEqual(sm.value, 0.0)
        self.assertIn("effect:main", sm.spec["agent_side_failed"])
        self.assertNotIn("effect:main", sm.not_computable)
        self.assertEqual(R.score(ev, "direction_match").value, 0.0)
        self.assertLess(R.score(ev, "human_noise_score").value, 0.2)

    def test_m2_agent_failure_stays_in_denominator(self):
        ev = fake_ev({}, [{"value": None, "value_s": None, "n": None, "p": None, "reason": "no variance"}],
                     {"value_s": 0.0, "se_s": 0.05})
        for rid in ("significance_match", "direction_match", "human_noise_score", "within_human_range"):
            r = R.score(ev, rid)
            self.assertEqual(r.value, 0.0, rid)
            self.assertTrue(r.spec["agent_side_failed"], rid)
        g = R.score(ev, "effect_gap")
        self.assertIsNone(g.value)
        self.assertEqual(g.spec["status"], "agent_side_failed")

    def test_m3_unsigned_human_test_both_significant_matches(self):
        ev = fake_ev({"direction": None, "direction_na": True},
                     [{"value": 0.3, "value_s": 0.3, "n": 100, "p": 0.0001, "direction": None}])
        self.assertEqual(R.score(ev, "significance_match").value, 1.0)
        ev = fake_ev({"direction": None, "direction_na": False},
                     [{"value": 0.3, "value_s": 0.3, "n": 100, "p": 0.9, "direction": 1}])
        r = R.score(ev, "significance_match")   # unknown (not unsigned) direction: not computable whatever the agent did
        self.assertIsNone(r.value)
        self.assertIn("direction is unknown", r.not_computable["effect:e"])

    def test_one_sided_p(self):
        h = {"p": 0.03, "p_tail": "one-sided"}
        right = fake_ev(h, [{"value": 0.3, "value_s": 0.3, "n": 100, "p": 0.08, "direction": 1}])
        wrong = fake_ev(h, [{"value": -0.3, "value_s": -0.3, "n": 100, "p": 0.08, "direction": -1}])
        self.assertEqual(R.score(right, "significance_match").value, 1.0)   # one-sided .04 < .05
        self.assertEqual(R.score(wrong, "significance_match").value, 0.0)   # one-sided .96 in the claimed direction
        e = md("e", {"value": 1.0, "n": 50, "test": {"statistic": "t", "value": 2.0, "df": 48, "p": 0.025,
                                                       "tail": "one-sided"}})
        self.assertEqual(human_effect(e)[0]["p_tail"], "one-sided")

    def test_bayesian_gives_no_p_and_no_credible_se(self):
        h, nc = human_effect(md("e", {"value": 0.5, "n": 200, "ci": [0.2, 0.8], "test": {"statistic": "BF10", "value": 30}}))
        self.assertIsNone(h["p"])
        self.assertIn("Bayesian", nc["human_p"])
        self.assertIsNone(h["se"])

    def test_cite_label_derived_is_honoured(self):
        h, _ = human_effect(md("e", {"value": 0.09, "n": 100, "cite": {"label": "derived", "source": "paper"}}))
        self.assertTrue(h["value_basis"].startswith("derived"))

    def test_zero_cell_uses_adjusted_se(self):
        e = md("e", {"cells": {"a": {"k": 0, "n": 50}, "b": {"k": 20, "n": 50}}})
        e["compute"]["op"] = "proportion_difference"
        h, _ = human_effect(e)
        self.assertIn("Agresti-Caffo", h["se_basis"])
        self.assertGreater(h["se"], math.sqrt(0.4 * 0.6 / 50))

    def test_uninformative_reason_when_floor_inside_ceiling(self):
        ev = fake_ev({"se_s": 0.01}, [{"value": 1.0, "value_s": 1.0, "n": 100, "p": 0.001, "direction": 1}],
                     {"value_s": 1.03, "se_s": 0.0001}, plan_factor=0.01)   # z = 3 >= 2.8 but B < c
        t, why = R.noise_terms(ev, ev.items[0], 0)
        self.assertIsNone(t)
        self.assertIn("within the ceiling", why)

    def test_version_order_constants_and_verifier_all(self):
        R.reward("toyreward-v2")(lambda ev: R.Reward(0.2, None, {}, {}))
        R.reward("toyreward-v10")(lambda ev: R.Reward(1.0, None, {}, {}))
        self.assertEqual(R.get("toyreward").id, "toyreward-v10")
        ev = fake_ev({}, [{"value": 1.0, "value_s": 1.0, "n": 100, "p": 0.001, "direction": 1}])
        r = R.score(ev, "direction_match")
        self.assertEqual(r.spec["constants"]["uninformative_z"], 2.8)
        self.assertEqual((r.spec["protocol_sha16"], r.spec["code_sha16"]), ("p", "c"))
        ev2 = fake_ev({"direction": None}, [{"value": 1.0, "value_s": 1.0, "n": 100, "p": 0.001, "direction": 1}])
        ev2.items.append(dict(ev.items[0], key="effect:f", id="f"))
        self.assertFalse(R.Verifier("direction_match", rule="all").evaluate(ev2).passed)
        self.assertTrue(R.Verifier("direction_match", rule="all", allow_not_computable=True).evaluate(ev2).passed)


class ReviewRound2(unittest.TestCase):
    def test_one_sided_only_when_printed(self):
        e = md("e", {"value": 1.0, "n": 50, "test": {"statistic": "t", "value": 2.0, "df": 48, "tail": "one-sided"}})
        self.assertEqual(human_effect(e)[0]["p_tail"], "two-sided")   # the p is derived (two-sided), not printed

    def test_direction_needs_a_significant_or_claimed_human_result(self):
        ev = fake_ev({"p": 0.34}, [{"value": 1.0, "value_s": 1.0, "n": 100, "p": 0.001, "direction": 1}])
        r = R.score(ev, "direction_match")
        self.assertIsNone(r.value)
        self.assertIn("not significant", r.not_computable["effect:e"])
        ev.items[0]["direction_claimed"] = True
        self.assertEqual(R.score(ev, "direction_match").value, 1.0)

    def test_scoped_shortfall_is_an_agent_failure(self):
        ev = fake_ev({}, [{"value": 1.0, "value_s": 1.0, "n": 50, "p": 0.001, "direction": 1}])   # planned 100
        r = R.score(ev, "direction_match")
        self.assertEqual(r.value, 0.0)
        self.assertIn("planned", r.spec["agent_side_failed"]["effect:e"]["0"])

    def test_non_official_has_no_verdict(self):
        ev = fake_ev({}, [{"value": 1.0, "value_s": 1.0, "n": 50, "p": 0.001, "direction": 1}], plan_factor=0.5)
        ev.d["plan"]["official"] = False
        r = R.score(ev, "direction_match")
        self.assertEqual(r.value, 1.0)
        self.assertIsNone(r.passed)
        self.assertIn("non_official", r.spec["label"])
        self.assertIsNone(R.Verifier("direction_match", threshold=0.5).evaluate(ev).passed)

    def test_combined_and_validity_count_failures(self):
        ev = fake_ev({}, [{"value": None, "value_s": None, "n": None, "p": None, "reason": "no variance"}])
        c = R.combined(ev, {"id": "mix", "parts": [{"fn": "effect_gap"}, {"fn": "direction_match"}],
                            "on_not_computable": "skip"})
        self.assertIsNone(c.value)
        self.assertFalse(c.passed)
        ev.d["sessions"]["per_seed"][0]["rows"] = [
            {"session": "a:0", "status": "completed", "excluded": [], "pending": ["coder"]},
            {"session": "a:1", "status": "completed", "excluded": [], "pending": []}]
        v = R.score(ev, "validity")
        self.assertEqual(v.value, 0.5)   # the pending session is counted, not dropped

    def test_planned_n_is_the_analysed_n(self):
        """Review 5: only the structured field counts; prose notes are never parsed."""
        from hsenv.evaldata import analysed_n
        cite = {"label": "reported", "source": "paper"}
        self.assertEqual(analysed_n({"id": "x", "n_paper": 592, "n_analysed": {"value": 247, "cite": cite}}),
                         (247, "n_analysed (cited)"))
        self.assertEqual(analysed_n({"id": "x", "n_paper": 197, "n_note": "derived: USA_1 analysed n 2,360"}),
                         (197, "n_paper_unverified"))   # the old regex planned n = 1 here
        self.assertEqual(analysed_n({"id": "x", "n_paper": 9440, "n_note": "analysed 4,826"}),
                         (9440, "n_paper_unverified"))

    def test_agresti_coull_single_share(self):
        e = md("e", {"cells": {"share": {"k": 0, "n": 46}}})
        e["compute"] = {"op": "proportion_vs_chance", "field": "x", "chance": 0.5}
        h, _ = human_effect(e)
        self.assertIn("Agresti-Coull", h["se_basis"])
        self.assertAlmostEqual(h["se"], math.sqrt((2 / 50) * (48 / 50) / 50))


class ReviewRound3(unittest.TestCase):
    """The review-3 attacks; DESIGN §8.7 keeps them as the leaderboard acceptance tests."""

    def test_a1_near_constant_policy_fails_spread(self):
        p = proto([md("main", CELLS)], keyed={"q.x": "(70 if bernoulli(0.97) else 71) if arm == 'a' else "
                                                       "(40 if bernoulli(0.97) else 41)", "q.att": "1"})
        ev = build(p, "keyed", seeds=(1,))
        sc = R.score(ev, "spread_check")   # review 4: spread is a diagnostic; it does not change the noise score
        self.assertEqual(sc.per_effect["effect:main"], 0.0)
        self.assertFalse(sc.spec["details"]["effect:main"][0]["arms"][0]["ok"])
        self.assertEqual(R.score(ev, "human_noise_score").per_effect["effect:main"], 1.0)

    def test_f_paired_difference_spread(self):
        h = {"arm_sd": {"difference": [2.0, 100.0]}}
        ok = fake_ev(h, [{"value": 1.0, "value_s": 1.0, "n": 100, "p": 0.001, "direction": 1,
                          "arm_sd": {"difference": [2.1, 100]}}], {"value_s": 0.0, "se_s": 0.05})
        tight = fake_ev(h, [{"value": 1.0, "value_s": 1.0, "n": 100, "p": 0.001, "direction": 1,
                             "arm_sd": {"difference": [0.3, 100]}}], {"value_s": 0.0, "se_s": 0.05})
        self.assertEqual(R.score(ok, "spread_check").value, 1.0)
        self.assertEqual(R.score(tight, "spread_check").value, 0.0)
        self.assertEqual(R.score(tight, "human_noise_score").value, 1.0)   # diagnostic only (review 4 M1)

    def test_d_strategic_exclusion_takes_the_lower_view(self):
        good = {"value": 1.0, "value_s": 1.0, "n": 100, "p": 0.001, "direction": 1}
        bad = {"value": 3.0, "value_s": 3.0, "n": 110, "p": 0.001, "direction": 1}
        ev = fake_ev({}, [good], {"value_s": 0.0, "se_s": 0.05})
        ev.items[0]["agent"]["per_seed_itt"] = [bad]
        ev.d["plan"].update(per_arm={"a": 100}, human_per_arm={"a": 100}, recruited_per_arm={"a": 110},
                            analysed_structured={"a": True})
        rows = [{"session": "a:%d" % i, "arm": "a", "status": "completed", "pending": [],
                 "excluded": ["attention"] if i < 40 else []} for i in range(140)]
        ev.d["sessions"]["per_seed"][0]["rows"] = rows   # agent excludes 29% against a human 9%
        r = R.score(ev, "within_human_range")
        self.assertTrue(r.spec["itt_applies"])
        self.assertEqual(r.value, 0.0)
        self.assertEqual(r.spec["view"], "intention_to_treat")
        self.assertEqual((r.spec["value_analysed"], r.spec["value_itt"]), (1.0, 0.0))
        for row in rows[:30]:
            row["excluded"] = []   # 10 of 110: the human rate
        r = R.score(ev, "within_human_range")
        self.assertFalse(r.spec["itt_applies"])
        self.assertEqual((r.value, r.spec["view"], r.spec["value_itt"]), (1.0, "analysed", 0.0))

    def test_e_range_without_a_floor(self):
        agent = [{"value": 0.1, "value_s": 0.1, "n": 100, "p": 0.3, "direction": 1}]
        weak = fake_ev({"value": 0.1, "value_s": 0.1, "se_s": 0.1}, agent, None)
        r = R.score(weak, "within_human_range")
        self.assertIsNone(r.value)
        self.assertIn("uninformative without a floor", r.not_computable["effect:e"])
        strong = fake_ev({}, [dict(agent[0], value=1.0, value_s=1.0)], None)   # |h| / se = 10: informative
        self.assertEqual(R.score(strong, "within_human_range").value, 1.0)
        self.assertIsNone(R.score(strong, "human_noise_score").value)   # the noise score always needs the floor
        lvl = fake_ev({}, [dict(agent[0], value=1.0, value_s=1.0)], None, kind="target")
        self.assertIsNone(R.score(lvl, "within_human_range").value)

    def test_h_over_n_is_truncated_to_the_plan(self):
        from hsenv.evaldata import run_from_env
        p = proto([md("main", CELLS)])
        env, _, _ = checks.play(p, 30, 1, "keyed")
        run = run_from_env(env, 1, "keyed", planned={"a": 10, "b": 10})
        self.assertEqual(run["truncated_sessions"], 40)
        self.assertEqual(len(run["sessions"]), 20)

    def test_m4_expired_sessions_still_count(self):
        import tempfile
        import time
        from hsenv.serve import Server
        p = proto([md("main", CELLS)])
        p.raw["arms"] = [{"id": "a", "n_paper": 3}, {"id": "b", "n_paper": 3}]
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "syn").mkdir()
            (Path(d) / "syn" / "protocol.json").write_text(json.dumps(p.raw))
            s = Server(studies_dir=d, operator=True, ttl=0.05)
            for i in range(4):   # abandoned: left to expire
                s.open_session("syn", arm="a", seed=100 + i)
            time.sleep(0.1)
            with s.lock:
                s._gc()   # the server's own TTL sweep (runs on every call)
            self.assertEqual(len(s.sessions), 0)
            s.ttl = 3600
            for i in range(6):
                arm = "ab"[i % 2]
                o = s.open_session("syn", arm=arm, seed=i)
                st = o["state"]
                ids = {r["kind"]: r["id"] for r in st["screen"]["responses"]}
                code = [r for r in st["screen"]["responses"] if r["kind"] == "choice"][0]["options"][0]["code"]
                s.step(o["session"], {ids["slider"]: 70 if arm == "a" else 40, ids["choice"]: code})
            sc = s.score("syn")
            self.assertEqual(sc["expired_by_ttl"], 4)
            self.assertEqual(sc["opened_per_arm"]["a"], 7)
            self.assertEqual(sc["scored_per_arm"]["a"], 7)   # 4 expired (invalid) + 3 valid
            rates = sc["rewards"]["direction_match-v2"]["spec"]["exclusion_rates"]
            self.assertEqual(rates["agent_dropouts"], 4)   # review 5: dropouts are reported, not exclusions
            self.assertTrue(rates["itt_not_applicable"])   # no whole-session exclusion in this protocol (review 6)
            self.assertEqual(rates["agent_opened"], 10)
            self.assertEqual(sc["report_scope"], R.REPORT_SCOPE)

    def test_labels_hashes_and_combined_meta(self):
        from hsenv.evaldata import CODE_FILES
        self.assertTrue({"serve.py", "score.py"} <= set(CODE_FILES))
        ev = fake_ev({}, [{"value": 1.0, "value_s": 1.0, "n": 100, "p": 0.001, "direction": 1}])
        r = R.score(ev, "direction_match")
        self.assertEqual(r.spec["report_scope"], "offline_report — not a leaderboard")
        c = R.combined(ev, {"id": "mix", "parts": [{"fn": "direction_match"}, {"fn": "significance_match"}]})
        for k in ("official", "constants", "protocol_sha16", "code_sha16", "report_scope"):
            self.assertIn(k, c.spec, k)


class ReviewRound4(unittest.TestCase):
    """Honest runs must not be penalised (hsenv/review-rewards-4.md)."""

    def test_honest_exclusion_at_the_human_rate_keeps_the_analysed_view(self):
        p = proto([md("main", CELLS)], exclusions=[{"id": "attention", "if": "answer('q.att') != 1"}],
                  keyed={"q.x": "(50 if bernoulli(0.5) else 90) if arm == 'a' else (20 if bernoulli(0.5) else 60)",
                         "q.att": "1 if bernoulli(0.85) else 2"})
        p.raw["arms"] = p.arms = [{"id": "a", "n_paper": 60, "n_analysed": 50},
                                  {"id": "b", "n_paper": 60, "n_analysed": 50}]   # human exclusion rate 1/6
        ev = build(p, "keyed", seeds=(1, 2))
        r = R.score(ev, "direction_match")
        self.assertFalse(r.spec["itt_applies"], r.spec["exclusion_rates"])
        self.assertEqual(r.spec["view"], "analysed")
        self.assertIsNotNone(r.spec["value_itt"])   # both views are always reported

    def test_skewed_or_ceiling_spread_does_not_change_the_score(self):
        """Honest log-normal money or ceiling Likert data fail the normal-theory SD check 10-29% of the time per arm
        (review 4); the check is a diagnostic and the noise score / range stay as they are."""
        for agent_sd in (3.1, 0.9):   # heavy right tail; compressed at the ceiling (human SD 2.0)
            ev = fake_ev({"arm_sd": {"a": [2.0, 131.0]}},
                         [{"value": 1.0, "value_s": 1.0, "n": 100, "p": 0.001, "direction": 1,
                           "arm_sd": {"a": [agent_sd, 131]}}], {"value_s": 0.0, "se_s": 0.05})
            self.assertEqual(R.score(ev, "spread_check").value, 0.0)
            self.assertEqual(R.score(ev, "human_noise_score").value, 1.0)
            self.assertEqual(R.score(ev, "within_human_range").value, 1.0)

    def test_spread_skipped_for_rating_level_rows(self):
        ev = fake_ev({"arm_sd": {"a": [2.0, 131.0]}},
                     [{"value": 1.0, "value_s": 1.0, "n": 100, "p": 0.001, "direction": 1, "rows_per_session": 30,
                       "arm_sd": {"a": [9.0, 3000]}}])
        r = R.score(ev, "spread_check")
        self.assertIsNone(r.value)
        self.assertIn("rows per participant", r.not_computable["effect:e"])

    def test_combined_non_official_has_no_verdict(self):
        ev = fake_ev({}, [{"value": None, "value_s": None, "n": None, "p": None, "reason": "no variance"}])
        ev.d["plan"]["official"] = False
        c = R.combined(ev, {"id": "mix", "parts": [{"fn": "effect_gap"}]})
        self.assertIsNone(c.value)
        self.assertIsNone(c.passed)


class ReviewRound5(unittest.TestCase):
    def test_unknown_human_rate_never_triggers_itt(self):
        ev = fake_ev({}, [{"value": 1.0, "value_s": 1.0, "n": 100, "p": 0.001, "direction": 1}],
                     {"value_s": 0.0, "se_s": 0.05})
        ev.items[0]["agent"]["per_seed_itt"] = [{"value": 3.0, "value_s": 3.0, "n": 150, "p": 0.001, "direction": 1}]
        ev.d["plan"].update(per_arm={"a": 100}, human_per_arm={"a": 100}, recruited_per_arm={"a": None})
        ev.d["sessions"]["per_seed"][0]["rows"] = [
            {"session": "a:%d" % i, "arm": "a", "status": "completed", "pending": [],
             "excluded": ["comprehension"] if i < 49 else []} for i in range(100)]   # 49%, human rate not printed
        r = R.score(ev, "within_human_range")
        self.assertEqual((r.value, r.spec["view"]), (1.0, "analysed"))
        self.assertTrue(r.spec["itt_unchecked"])
        self.assertEqual(r.spec["exclusion_rates"]["human_rate"], "unknown")

    def test_honest_rate_with_structured_counts_keeps_analysed(self):
        ev = fake_ev({}, [{"value": 1.0, "value_s": 1.0, "n": 100, "p": 0.001, "direction": 1}],
                     {"value_s": 0.0, "se_s": 0.05})
        ev.items[0]["agent"]["per_seed_itt"] = [{"value": 3.0, "value_s": 3.0, "n": 196, "p": 0.001, "direction": 1}]
        ev.d["plan"].update(per_arm={"a": 100}, human_per_arm={"a": 4826}, recruited_per_arm={"a": 9440},
                            analysed_structured={"a": True})
        ev.d["sessions"]["per_seed"][0]["rows"] = [
            {"session": "a:%d" % i, "arm": "a", "status": "completed", "pending": [],
             "excluded": ["comprehension"] if i < 96 else []} for i in range(196)]   # 49% = the human rate
        r = R.score(ev, "within_human_range")
        self.assertFalse(r.spec["itt_applies"], r.spec["exclusion_rates"])
        self.assertEqual(r.value, 1.0)

    def test_incomplete_sessions_are_dropouts_not_exclusions(self):
        ev = fake_ev({}, [{"value": 1.0, "value_s": 1.0, "n": 100, "p": 0.001, "direction": 1}])
        ev.d["plan"].update(per_arm={"a": 10}, human_per_arm={"a": 10}, recruited_per_arm={"a": 10},
                            analysed_structured={"a": True})
        ev.d["sessions"]["per_seed"][0]["rows"] = (
            [{"session": "a:%d" % i, "arm": "a", "status": "completed", "pending": [], "excluded": []} for i in range(10)]
            + [{"session": "b:%d" % i, "arm": "a", "status": "incomplete", "pending": [], "excluded": []} for i in range(5)])
        applies, det = R.exclusion_rates(ev)
        self.assertEqual((det["agent_rate"], det["agent_dropouts"], applies), (0.0, 5, False))

    def test_printed_100_percent_target_without_k(self):
        """A paper prints value 1.0, n 86 and no k: an honest agent at 100% is not a zero-variance failure."""
        from hsenv.evaldata import _agent_target_side
        t = {"id": "p4", "stat": "share", "human": {"value": 1.0, "n": 86}}
        side = _agent_target_side({"agent": 1.0, "n_agent": 86, "k_agent": 86}, t)
        self.assertEqual(side["status"], "computed")
        self.assertIsNotNone(side["value_s"])
        t2 = {"id": "p4", "stat": "share", "human": {"value": 0.7, "n": 86}}
        self.assertEqual(_agent_target_side({"agent": 1.0, "n_agent": 86, "k_agent": 86}, t2)["status"], "zero_variance")


class ArmCountSchema(unittest.TestCase):
    def test_structured_counts_validate(self):
        import copy
        from hsenv.schema_check import validate
        from tests.test_schema import MINI
        c = {"label": "reported", "source": "paper", "page": 3}
        good = copy.deepcopy(MINI)
        good["arms"][0].update(n_analysed={"value": 8, "cite": c}, n_recruited={"value": 10, "cite": c})
        self.assertTrue(validate(good, "protocol")["valid"], validate(good, "protocol")["errors"])
        for bad in ({"value": -1, "cite": c}, {"value": 8}, {"value": "8", "cite": c}, "8"):
            b = copy.deepcopy(MINI)
            b["arms"][0]["n_analysed"] = bad
            self.assertFalse(validate(b, "protocol")["valid"], bad)


class ReviewRound6(unittest.TestCase):
    """Caller plans (skills/review-run-explore-2 Must 1) and label visibility (review rewards-6)."""

    def _proto(self):
        c = {"label": "reported", "source": "paper"}
        p = proto([md("main", CELLS)])
        p.raw["arms"] = p.arms = [{"id": a, "n_paper": 60, "n_analysed": {"value": 60, "cite": c},
                                   "n_recruited": {"value": 60, "cite": c}} for a in "ab"]
        return p

    def test_smaller_caller_plan_is_non_official_not_underpowered(self):
        p = self._proto()
        plan = {"a": 20, "b": 20}
        ev = EvalData.build(p, [simulate(p, "keyed", plan, 1)], baseline=baseline_run(p, plan, 0), planned=plan)
        r = R.score(ev, "direction_match")
        self.assertEqual(r.spec["status"], "scored")
        self.assertFalse(r.spec["official"])
        self.assertIsNone(r.passed)
        self.assertEqual(r.value, 1.0)

    def test_subset_of_arms_is_non_official_and_other_arms_not_failures(self):
        p = self._proto()
        p.raw["analysis"]["targets"] = [{"id": "tb", "unit": "p", "field": "x", "stat": "mean", "where": {"arm": "b"},
                                         "human": {"value": 40, "sd": 20, "n": 60}}]
        plan = {"a": 60}
        ev = EvalData.build(p, [simulate(p, "keyed", plan, 1)], baseline=baseline_run(p, plan, 0), planned=plan)
        self.assertEqual(ev.d["plan"]["subset_of_arms"], ["b"])
        r = R.score(ev, "direction_match")   # the a-vs-b contrast needs arm b
        self.assertFalse(r.spec["official"])
        self.assertIn("not in this run's plan", r.not_computable["effect:main"])
        self.assertFalse(r.spec["agent_side_failed"])
        self.assertIn("not in this run's plan", R.score(ev, "within_human_range").not_computable["target:tb"])

    def test_short_of_its_own_plan_is_underpowered(self):
        p = self._proto()
        runs = [simulate(p, "keyed", {"a": 5, "b": 5}, 1, top_up=False)]
        ev = EvalData.build(p, runs, baseline=baseline_run(p, {"a": 20, "b": 20}, 0), planned={"a": 20, "b": 20})
        self.assertEqual(R.score(ev, "direction_match").spec["status"], "underpowered_run")

    def test_bare_integer_counts(self):
        from hsenv.evaldata import analysed_n, arm_count, plan_of
        arm = {"id": "a", "n_paper": 120, "n_analysed": 100, "n_recruited": 120}
        self.assertEqual(analysed_n(arm), (100, "n_analysed (legacy bare count, no cite)"))
        self.assertEqual(arm_count(arm, "n_recruited")[0], 120)
        p = proto([md("main", CELLS)])
        p.raw["arms"] = p.arms = [dict(arm, id="a"), dict(arm, id="b")]
        plan = plan_of(p, [], None)
        self.assertEqual(plan["per_arm"], {"a": 100, "b": 100})
        self.assertEqual(plan["recruited_per_arm"], {"a": 120, "b": 120})
        self.assertEqual(plan["official_n_basis"], "verified")

    def test_cli_shows_unverified_n_and_itt_labels(self):
        import contextlib
        import io
        from hsenv import score as S
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            S.main([str(FIXTURES / "fixture_score"), "--seeds", "1", "--rewards", "direction_match"])
        out = buf.getvalue()
        self.assertIn("n_paper_unverified", out)
        self.assertIn("passed=True(UNVERIFIED n)", out)
        self.assertNotIn("passed=True ", out)
        self.assertIn("itt not applicable", out)


class Integration1(unittest.TestCase):
    """skills/review-run-score-integration-1.md: underpowered labels; one definition of valid incl. population cuts."""

    def test_underpowered_non_official_keeps_labels_and_gives_no_verdict(self):
        p = proto([md("main", CELLS)])
        runs = [simulate(p, "keyed", {"a": 5, "b": 5}, 1, top_up=False)]
        ev = EvalData.build(p, runs, baseline=baseline_run(p, {"a": 20, "b": 20}, 0), planned={"a": 20, "b": 20})
        r = R.score(ev, "direction_match")
        self.assertEqual(r.spec["status"], "underpowered_run")
        self.assertIsNone(r.passed)
        self.assertFalse(r.spec["official"])
        self.assertEqual(r.spec["report_scope"], R.REPORT_SCOPE)
        self.assertIn("non_official", r.spec["label"])


class Integration2(unittest.TestCase):
    def test_official_underpowered_keeps_unverified_label(self):
        p = proto([md("main", CELLS)])   # arms carry n_paper only: unverified
        runs = [simulate(p, "keyed", {"a": 5, "b": 5}, 1, top_up=False)]
        ev = EvalData.build(p, runs, baseline=baseline_run(p, {"a": 60, "b": 60}, 0), planned={"a": 60, "b": 60})
        r = R.score(ev, "direction_match")
        self.assertEqual(r.spec["status"], "underpowered_run")
        self.assertTrue(r.spec["official"])
        self.assertFalse(r.passed)
        self.assertTrue(r.spec["verdict_on_unverified_n"])
        self.assertIn("unverified", r.spec["label"])

    def test_validity_reports_the_run_official_flag(self):
        p = proto([md("main", CELLS)])
        plan = {"a": 10, "b": 10}
        ev = EvalData.build(p, [simulate(p, "keyed", plan, 1)], planned=plan)
        v = R.score(ev, "validity")
        self.assertFalse(v.spec["official"])
        self.assertIsNone(v.passed)
        self.assertIn("non_official", v.spec["label"])


class ServeScoring(unittest.TestCase):
    def test_best_subset_exploit_is_refused(self):
        """Review 2 M2: an operator runs 2 x N sessions and submits the best N. The server scores the first planned
        n of valid sessions per arm in opening order; the attention-failing first sessions are scored as invalid,
        so the exclusion rate (50% against a human 0%) switches on the intention-to-treat view."""
        import tempfile
        from hsenv.serve import Server
        p = proto([md("main", CELLS)], exclusions=[{"id": "attention", "if": "answer('q.att') != 1"}])
        c = {"label": "reported", "source": "paper"}
        p.raw["arms"] = [{"id": a, "n_paper": 5, "n_analysed": {"value": 5, "cite": c},
                          "n_recruited": {"value": 5, "cite": c}} for a in "ab"]   # the humans excluded nobody
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "syn").mkdir()
            (Path(d) / "syn" / "protocol.json").write_text(json.dumps(p.raw))
            s = Server(studies_dir=d, operator=True)
            good = []
            for i in range(20):
                arm = "ab"[i % 2]
                o = s.open_session("syn", arm=arm, seed=i)
                st = o["state"]
                ids = {r["kind"]: r["id"] for r in st["screen"]["responses"]}
                att = "o2" if i < 10 else "o1"   # the first 10 fail the attention check
                opts = [r for r in st["screen"]["responses"] if r["kind"] == "choice"][0]["options"]
                code = opts[1]["code"] if i < 10 else opts[0]["code"]
                s.step(o["session"], {ids["slider"]: (60 + i) if arm == "a" else (30 + i), ids["choice"]: code})
                if i >= 10:
                    good.append(o["session"])
            self.assertEqual(s.score("syn", good)["status"], "error")   # no caller-chosen subsets
            sc = s.score("syn")
            self.assertEqual(sc["scored_per_arm"], {"a": 10, "b": 10})
            self.assertEqual(sc["opened_per_arm"], {"a": 10, "b": 10})
            r = sc["rewards"]["direction_match-v2"]
            self.assertTrue(r["spec"]["itt_applies"])
            self.assertAlmostEqual(r["spec"]["exclusion_rates"]["agent_rate"], 0.5)
            for k in ("official_n_basis", "human_n_basis", "itt_unchecked", "itt_not_applicable", "dropouts"):
                self.assertIn(k, sc)   # labels at the top level (review 6 S1)


if __name__ == "__main__":
    unittest.main()
