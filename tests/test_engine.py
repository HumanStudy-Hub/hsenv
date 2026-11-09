import unittest

from hsenv.engine import Env, Protocol

P = {
    "id": "t", "data": {},
    "stages": {
        "q": {"content": [{"id": "s", "value": {"expr": "'story ' + v"}}],
              "responses": [{"id": "x", "kind": "slider", "range": [0, 100], "prompt": "rate"}]},
        "c": {"responses": [{"id": "pick", "kind": "choice", "prompt": "which",
                             "options": [{"code": "a", "label": "A"}, {"code": "b", "label": "B"}]}]},
    },
    "flow": {"seq": [
        {"for": "v", "in": ["g", "e"], "let": {"k": {"expr": "v_index * 10"}}, "do": {"stage": "q"}},
        {"set": {"g_rating": {"expr": "answer('q.x', v='g')"}}},
        {"stage": "c"},
    ]},
    "units": {"s": {"per": "session", "fields": {"g": "g_rating", "e": "answer('q.x', v='e')"}}},
}


def session():
    env = Env(Protocol(P))
    s = env.open(env.design(n=1, seed=1)[0])
    return env, s


class Engine(unittest.TestCase):
    def test_answer_from_another_iteration_with_explicit_filter(self):
        env, s = session()
        st = s.reset()
        st = s.step({st["screen"]["responses"][0]["id"]: 84})
        st = s.step({st["screen"]["responses"][0]["id"]: 12})
        self.assertEqual(s.vars["g_rating"], 84)
        st = s.step({st["screen"]["responses"][0]["id"]: "o1"})
        self.assertTrue(st["done"])
        self.assertEqual(env.unit_tables()["s"][0], dict(env.unit_tables()["s"][0], g=84, e=12))

    def test_refused_attempts_are_recorded(self):
        _, s = session()
        st = s.reset()
        st = s.step({st["screen"]["responses"][0]["id"]: 1})
        st = s.step({st["screen"]["responses"][0]["id"]: 2})
        rid = st["screen"]["responses"][0]["id"]
        s.step({rid: "zzz"})
        s.step({rid: "o1"})
        self.assertEqual(len(s.refused), 1)
        self.assertEqual(s.record()["refused"][0]["answers"]["pick"], "zzz")
        self.assertEqual(s._funcs({})["refused_errors"]("c"), 1)

    def test_unhashable_answer_is_an_error_state(self):
        _, s = session()
        st = s.reset()
        st = s.step({st["screen"]["responses"][0]["id"]: 1})
        st = s.step({st["screen"]["responses"][0]["id"]: 2})
        rid = st["screen"]["responses"][0]["id"]
        for bad in (["o1"], {"a": 1}, 3, None):
            out = s.step({rid: bad})
            self.assertIn(rid, out["error"])
            self.assertEqual(out["step"], st["step"])

    def test_states_hide_internal_ids_and_keep_seen(self):
        _, s = session()
        st = s.reset()
        self.assertTrue(all(i["id"].startswith("i") for i in st["screen"]["items"]))
        st = s.step({st["screen"]["responses"][0]["id"]: 5})
        self.assertEqual(st["seen"][0]["text"], "story g")
        self.assertFalse(st["seen"][0]["reviewable"])
        self.assertNotIn("v", str(st["screen"]).replace("prompt", "").replace("kind", "").replace("story e", ""))


class Features(unittest.TestCase):
    def test_option_text_box_and_spans(self):
        prot = {"id": "f", "data": {"stem": {"text": "Have you seen it before?", "spans": [{"start": 14, "end": 18, "style": "underline"}]}},
                "stages": {"q": {"responses": [{"id": "seen", "kind": "choice", "prompt": {"expr": "data['stem']"},
                                                "options": [{"code": 1, "label": "Yes, where:", "text_entry": True},
                                                            {"code": 2, "label": "No"}]}]}},
                "flow": {"stage": "q"}}
        env = Env(Protocol(prot))
        s = env.open(env.design(n=1, seed=1)[0])
        st = s.reset()
        r = st["screen"]["responses"][0]
        self.assertEqual(r["prompt_spans"][0]["style"], "underline")
        self.assertTrue(r["options"][0]["text_entry"])
        self.assertIn("error", s.step({r["id"]: {"code": "o2", "text": "x"}}))
        st = s.step({r["id"]: {"code": "o1", "text": "on MTurk"}})
        self.assertTrue(st["done"])
        vals = {(a["response"], a["value"]) for a in s.answers}
        self.assertIn(("seen", 1), vals)
        self.assertIn(("seen_text", "on MTurk"), vals)


class ButtonInLayout(unittest.TestCase):
    def test_button_position(self):
        prot = {"id": "b", "data": {},
                "stages": {"intro": {"presentation": {"button": "Start Experiment"},
                                     "layout": ["note", "@button", "legal"],
                                     "content": [{"id": "note", "value": "HIT note"}, {"id": "legal", "value": "Legal text"}]}},
                "flow": {"stage": "intro"}}
        env = Env(Protocol(prot))
        st = env.open(env.design(n=1, seed=1)[0]).reset()
        ids = [i["id"] for i in st["screen"]["items"]]
        self.assertEqual(st["screen"]["order"], [ids[0], "button", ids[1]])
        self.assertEqual(st["screen"]["button"], "Start Experiment")


class PageRequiredMessage(unittest.TestCase):
    def test_one_message_for_missing_answers(self):
        prot = {"id": "pr", "data": {},
                "stages": {"q": {"required_message_page": "Please adjust all sliders.",
                                 "responses": [{"id": "a", "kind": "slider", "range": [0, 1]},
                                               {"id": "b", "kind": "slider", "range": [0, 1]}]}},
                "flow": {"stage": "q"}}
        env = Env(Protocol(prot))
        s = env.open(env.design(n=1, seed=1)[0])
        st = s.reset()
        a, b = [r["id"] for r in st["screen"]["responses"]]
        self.assertEqual(s.step({a: 0.5})["error"], {"page": "Please adjust all sliders."})
        self.assertIn(a, s.step({a: 7, b: 0.5})["error"])   # a wrong value keeps its own message
        self.assertTrue(s.step({a: 0.5, b: 0.5})["done"])


class NumericEqualsAndTrim(unittest.TestCase):
    PROT = {"id": "ne", "data": {"br": [30, 70]},
            "arms": [{"id": "a", "n_paper": 6}],
            "stages": {"show": {"content": [{"id": "t", "value": {"expr": "'%d%%' % data['br'][i]"}}]},
                       "fix": {"responses": [{"id": "c", "kind": "number", "range": [0, 100],
                                              "validate": {"equals": {"expr": "data['br'][i]"}, "message": "wrong"}}]},
                       "rate": {"responses": [{"id": "x", "kind": "number", "range": [0, 1000]}]}},
            "flow": {"loop": 2, "as": "i", "do": {"seq": [{"stage": "show"}, {"stage": "fix"}, {"stage": "rate"}]}},
            "units": {"t": {"per": "session", "rows": "range(2)", "fields": {"i": "row", "x": "answer('rate.x', i=row)"},
                            "trim": [{"id": "out3", "field": "x", "group_by": ["i"], "center": "mean", "spread": "iqr", "k": 1}]}}}

    def test_equals_expression(self):
        env = Env(Protocol(self.PROT))
        s = env.open(env.design(seed=1)[0])
        st = s.reset()
        st = s.step({})
        rid = st["screen"]["responses"][0]["id"]
        self.assertEqual(s.step({rid: 31})["error"], {rid: "wrong"})
        self.assertNotIn("error", s.step({rid: 30}))


class OptionsFixedAndMultiText(unittest.TestCase):
    def test_fixed_last_and_multi_text(self):
        prot = {"id": "mo", "data": {},
                "stages": {"q": {"responses": [{"id": "m", "kind": "multi", "shuffle_options": True, "options": [
                    {"code": 1, "label": "A"}, {"code": 2, "label": "B"}, {"code": 3, "label": "C"},
                    {"code": 9, "label": "Other:", "text_entry": True, "fixed": True}]}]}},
                "flow": {"stage": "q"}}
        env = Env(Protocol(prot))
        for seed in range(6):
            s = env.open(env.design(n=1, seed=seed)[0])
            st = s.reset()
            r = st["screen"]["responses"][0]
            self.assertEqual(r["options"][-1]["label"], "Other:")
        st = s.step({r["id"]: [r["options"][0]["code"], {"code": r["options"][-1]["code"], "text": "Reddit"}]})
        self.assertTrue(st["done"])
        self.assertIn(("m_text_9", "Reddit"), [(a["response"], a["value"]) for a in s.answers])


class PendingExclusion(unittest.TestCase):
    def test_pending_rows_are_not_analysed_silently(self):
        prot = {"id": "pe", "data": {}, "arms": [{"id": "a", "n_paper": 3}],
                "stages": {"q": {"responses": [{"id": "t", "kind": "text"}]}},
                "flow": {"stage": "q"},
                "exclusions": [{"id": "susp", "if": "answer('q.t') == 'yes'", "pending_if": "answer('q.t') not in ('yes', 'idk')"}],
                "units": {"s": {"per": "session", "fields": {"t": "answer('q.t')"}}}}
        env = Env(Protocol(prot))
        for k, txt in enumerate(["yes", "idk", "the puzzles"]):
            s = env.open(env.design(seed=1)[k])
            st = s.reset()
            s.step({st["screen"]["responses"][0]["id"]: txt})
        rows = env.unit_tables()["s"]
        self.assertEqual([r["excluded"] for r in rows], [True, False, False])
        self.assertEqual(rows[2]["pending"], ["susp"])
        from hsenv.checks import _excluded
        self.assertTrue(_excluded(rows[2], ["x", "s"]))
        self.assertFalse(_excluded(rows[1], ["x", "s"]))


class ExprButtonAndChoiceEquals(unittest.TestCase):
    def test_button_and_choice_equals_expr(self):
        prot = {"id": "bc", "data": {"btn": "Weiter", "key": ["e", "i"]},
                "stages": {"t": {"presentation": {"button": {"expr": "data['btn']"}},
                                 "responses": [{"id": "k", "kind": "choice",
                                                "options": [{"code": "e", "label": "E"}, {"code": "i", "label": "I"}],
                                                "validate": {"equals": {"expr": "data['key'][n]"}, "message": "X"}}]}},
                "flow": {"loop": 2, "as": "n", "do": {"stage": "t"}}}
        env = Env(Protocol(prot))
        s = env.open(env.design(n=1, seed=1)[0])
        st = s.reset()
        self.assertEqual(st["screen"]["button"], "Weiter")
        rid = st["screen"]["responses"][0]["id"]
        self.assertEqual(s.step({rid: "o2"})["error"], {rid: "X"})
        st = s.step({rid: "o1"})
        rid = st["screen"]["responses"][0]["id"]
        self.assertEqual(s.step({rid: "o1"})["error"], {rid: "X"})
        self.assertTrue(s.step({rid: "o2"})["done"])


class ExactlyOneOptional(unittest.TestCase):
    def test_fuzz_can_meet_an_exactly_one_rule(self):
        from hsenv.checks import play
        prot = {"id": "x1", "data": {},
                "stages": {"imc": {"validate_page": [{"if_valid": "(answer('imc.title') is not None) + (answer('imc.go') is not None) == 1"}],
                                   "layout": ["title", "t", "go"],
                                   "content": [{"id": "t", "value": "Instructions text"}],
                                   "responses": [{"id": "title", "kind": "choice", "required": False, "options": [{"code": 0, "label": "Instructions"}]},
                                                 {"id": "go", "kind": "choice", "required": False, "options": [{"code": 1, "label": "Continue"}]}]}},
                "flow": {"stage": "imc"}}
        _, probs, stats = play(Protocol(prot), 30, 1)
        self.assertEqual(probs, [])


class ImageLines(unittest.TestCase):
    def test_line_spans_reach_the_state(self):
        prot = {"id": "im", "data": {},
                "stages": {"q": {"content": [{"id": "box", "value": {"src": "https://example.org/a.png", "lines": [
                    "Plain line", {"text": "Price GBP1.80 today", "spans": [{"start": 6, "end": 13, "style": "bold"}],
                                   "cite": {"label": "verbatim", "read": "image"}}]}}],
                                 "responses": [{"id": "a", "kind": "number", "range": [0, 9]}]}},
                "flow": {"stage": "q"}}
        env = Env(Protocol(prot))
        st = env.open(env.design(n=1, seed=1)[0]).reset()
        ln = st["screen"]["items"][0]["lines"]
        self.assertEqual(ln[0], "Plain line")
        self.assertEqual(ln[1], {"text": "Price GBP1.80 today", "spans": [{"start": 6, "end": 13, "style": "bold"}]})


class NewOps(unittest.TestCase):
    def test_rank_sum_matches_r(self):
        from hsenv.effects_core import op_rank_sum
        rows = [{"condition": "t", "y": v} for v in [3, 5, 7, 9, 9]] + [{"condition": "r", "y": v} for v in [1, 2, 5, 6]]
        out = op_rank_sum(rows, {"contrast": {"treatment": "t", "reference": "r"}, "compute": {"field": "y"}})
        self.assertEqual(out["test"]["value"], 16.5)            # R: W = 16.5
        self.assertAlmostEqual(out["test"]["p"], 0.1383, 3)     # R: p-value = 0.1383 (ties, correct=TRUE)

    def test_rank_sum_exact_without_ties(self):
        from hsenv.effects_core import op_rank_sum
        rows = [{"condition": "t", "y": v} for v in [1.1, 2.2, 3.3, 4.4]] + [{"condition": "r", "y": v} for v in [0.5, 0.6, 0.7, 5]]
        out = op_rank_sum(rows, {"contrast": {"treatment": "t", "reference": "r"}, "compute": {"field": "y"}})
        self.assertEqual(out["test"]["value"], 12)              # R: W = 12
        self.assertAlmostEqual(out["test"]["p"], 0.3429, 4)     # R: p-value = 0.3429 (exact)

    def test_slider_grid_and_hidden_start(self):
        prot = {"id": "sl", "data": {}, "stages": {"q": {"responses": [
            {"id": "x", "kind": "slider", "range": [0, 1], "step": 0.01, "start": 0.5, "start_visible": False}]}},
                "flow": {"stage": "q"}}
        env = Env(Protocol(prot))
        s = env.open(env.design(n=1, seed=1)[0])
        r = s.reset()["screen"]["responses"][0]
        self.assertNotIn("start", r)
        self.assertIn("error", s.step({r["id"]: 0.333}))
        self.assertTrue(s.step({r["id"]: 0.33})["done"])

    def test_validate_also_accepts_extra_codes(self):
        prot = {"id": "al", "data": {}, "stages": {"q": {"responses": [
            {"id": "b", "kind": "number", "range": [0, 20], "validate": {"also": [99]}}]}}, "flow": {"stage": "q"}}
        env = Env(Protocol(prot))
        s = env.open(env.design(n=1, seed=1)[0])
        rid = s.reset()["screen"]["responses"][0]["id"]
        self.assertIn("error", s.step({rid: 50}))
        self.assertTrue(s.step({rid: 99})["done"])


class Reviewable(unittest.TestCase):
    def test_reviewable_only_on_listed_stages(self):
        prot = {"id": "rv", "data": {},
                "stages": {"instr": {"content": [{"id": "t", "value": "Rules", "reviewable": True, "reviewable_on": ["cmp"]}]},
                           "dec": {"responses": [{"id": "a", "kind": "number", "range": [0, 9]}]},
                           "cmp": {"responses": [{"id": "b", "kind": "number", "range": [0, 9]}]}},
                "flow": {"seq": [{"stage": "instr"}, {"stage": "dec"}, {"stage": "cmp"}]}}
        env = Env(Protocol(prot))
        s = env.open(env.design(n=1, seed=1)[0])
        s.reset()
        st = s.step({})
        self.assertFalse(st["seen"][0]["reviewable"])
        st = s.step({st["screen"]["responses"][0]["id"]: 1})
        self.assertTrue(st["seen"][0]["reviewable"])
        self.assertNotIn("_rev_on", st["seen"][0])


class EndPage(unittest.TestCase):
    def test_end_with_terminal_page(self):
        prot = {"id": "e", "data": {},
                "stages": {"q": {"responses": [{"id": "a", "kind": "number", "range": [0, 9], "prefill": 3}]},
                           "stop": {"content": [{"id": "t", "value": "You cannot continue."}]}},
                "flow": {"seq": [{"stage": "q"}, {"end": "screened_out", "if": "answer('q.a') > 5", "page": "stop"},
                                 {"stage": "q"}]}}
        env = Env(Protocol(prot))
        s = env.open(env.design(n=1, seed=1)[0])
        st = s.reset()
        self.assertEqual(st["screen"]["responses"][0]["prefill"], 3)
        st = s.step({st["screen"]["responses"][0]["id"]: 7})
        self.assertEqual(st["screen"]["items"][0]["text"], "You cannot continue.")
        st = s.step({})
        self.assertTrue(st["done"])
        self.assertEqual(s.status, "screened_out")


class Groups(unittest.TestCase):
    PGG = {"id": "pgg", "data": {},
           "arms": [{"id": "g", "n_paper": 2, "group_size": 4}],
           "stages": {"contrib": {"responses": [{"id": "c", "kind": "number", "range": [0, 20], "integer": True,
                                                 "prompt": {"expr": "'Round %d: how much do you contribute?' % (r + 1)"}}]}},
           "flow": {"loop": 2, "as": "r", "do": {"seq": [
               {"stage": "contrib"},
               {"sync": "round_end",
                "compute": {"total": "sum(group('contrib.c'))",
                            "payoff": "20 - answer('contrib.c') + 1.6 * sum(group('contrib.c')) / group_size"},
                "events": [{"expr": "'Group total: %d. Your payoff: %.2f' % (total, payoff)"}]}]}},
           "units": {"s": {"per": "session", "fields": {"payoff": "vars['payoff']"}},
                     "g": {"per": "group", "fields": {"mean_c": "mean(group('contrib.c'))"}}}}

    def test_public_goods_round(self):
        env = Env(Protocol(self.PGG))
        g = env.open(env.design(seed=1)[0])
        st = g.reset()
        self.assertEqual(sorted(g.pending()), ["p1", "p2", "p3", "p4"])
        for k, pid in enumerate(["p1", "p2", "p3"]):
            st = g.step(pid, {st[pid]["screen"]["responses"][0]["id"]: 5 * k})
            self.assertTrue(st[pid]["waiting"])
        self.assertEqual(g.pending(), ["p4"])
        st = g.step("p4", {st["p4"]["screen"]["responses"][0]["id"]: 20})
        # everyone released into round 2 with the round-1 outcome as an event
        self.assertEqual(sorted(g.pending()), ["p1", "p2", "p3", "p4"])
        self.assertEqual(st["p1"]["events"], ["Group total: 35. Your payoff: 34.00"])
        self.assertEqual(st["p4"]["events"], ["Group total: 35. Your payoff: 14.00"])
        self.assertIn("Round 2", st["p2"]["screen"]["responses"][0]["prompt"])
        for pid in ["p1", "p2", "p3", "p4"]:
            st = g.step(pid, {st[pid]["screen"]["responses"][0]["id"]: 10})
        self.assertTrue(all(st[p]["done"] for p in st))
        self.assertEqual(len(env.unit_tables()["s"]), 4)
        self.assertEqual(env.unit_tables()["s"][0]["payoff"], 20 - 10 + 1.6 * 40 / 4)
        self.assertEqual(env.unit_tables()["g"], [dict(env.unit_tables()["g"][0], mean_c=10.0)])
        self.assertEqual(len(env.unit_tables()["g"]), 1)


class LeakCheck(unittest.TestCase):
    def test_cite_note_in_a_state_is_a_leak(self):
        from hsenv.checks import play
        note = "the items were trick questions according to the authors"
        prot = {"id": "l", "data": {},
                "stages": {"q": {"presentation": {"paging": note},
                                 "content": [{"id": "t", "value": "Question text", "cite": {"label": "verbatim", "note": note}}],
                                 "responses": [{"id": "a", "kind": "number", "range": [0, 9]}]}},
                "flow": {"stage": "q"}}
        _, _, stats = play(Protocol(prot), 3, 1)
        self.assertTrue(stats["leaks"])


class ResponseTimesAndIQR(unittest.TestCase):
    PROT = {"id": "rt", "data": {},
            "arms": [{"id": "a", "n_paper": 6}],
            "stages": {"q": {"responses": [{"id": "x", "kind": "number", "range": [0, 1000]}]}},
            "flow": {"loop": 2, "as": "i", "do": {"stage": "q"}},
            "exclusions": [{"id": "fast", "if": "any(t is not None and t < 1000 for t in elapsed_all('q.x'))"},
                           {"id": "out", "population": {"values": "answers('q.x')", "rule": "iqr_fence", "k": 1.5,
                                                         "per_position": True}}],
            "units": {"s": {"per": "session", "fields": {"x": "mean(answers('q.x'))"}}}}

    def test_population_rule_after_earlier_exclusions(self):
        prot = dict(self.PROT, exclusions=[
            {"id": "big", "if": "answer('q.x', i=0) > 500"},
            {"id": "out", "population": {"values": "answers('q.x')", "rule": "iqr_fence", "k": 1.5,
                                          "per_position": True, "after_exclusions": ["big"]}}])
        env = Env(Protocol(prot))
        vals = [10, 11, 12, 13, 30, 900]   # with 900 removed first, 30 is outside the fence on item 1
        for k, v in enumerate(vals):
            s = env.open(env.design(seed=1)[k])
            st = s.reset()
            st = s.step({st["screen"]["responses"][0]["id"]: v})
            s.step({st["screen"]["responses"][0]["id"]: 500})
        self.assertEqual(sorted(env.population_exclusions(env.sessions)), ["a:4"])

    def test_elapsed_and_iqr_fence(self):
        env = Env(Protocol(self.PROT))
        vals = [(10, 500), (11, 500), (12, 500), (13, 500), (14, 500), (90, 500)]
        for k, (v1, v2) in enumerate(vals):
            s = env.open(env.design(seed=1)[k])
            st = s.reset()
            st = s.step({st["screen"]["responses"][0]["id"]: v1, "_elapsed_ms": 500 if k == 0 else 4000})
            st = s.step({st["screen"]["responses"][0]["id"]: v2, "_elapsed_ms": 3000})
            self.assertTrue(st["done"])
            self.assertEqual(s._funcs({})["elapsed"]("q.x"), 3000)
        recs = env.records()
        self.assertTrue(recs[0]["excluded"])            # first screen under 1 s
        self.assertFalse(recs[1]["excluded"])
        pop = env.population_exclusions(env.sessions)
        self.assertEqual(sorted(pop), ["a:5"])            # 90 is outside Q3 + 1.5 IQR on item 1 only
        s = env.open(env.design(seed=2)[0])
        st = s.reset()
        self.assertIn("_elapsed_ms", s.step({st["screen"]["responses"][0]["id"]: 1, "_elapsed_ms": -5})["error"])


if __name__ == "__main__":
    unittest.main()
