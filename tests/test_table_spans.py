"""Table cells keep their colspan / rowspan in the served State (engine), and checks block a protocol table whose
spanning cell is rendered without its span (invented table)."""
import unittest
from types import SimpleNamespace

from hsenv.checks import play, sample_sessions, table_spans_unserved
from hsenv.engine import Env, Protocol


def prot():
    rows = [[{"text": ""}, {"text": "Plan North", "colspan": 2}, {"text": "Plan South", "colspan": 2}],
            [{"text": "Price", "rowspan": 1}, {"text": "Me"}, {"text": "Group"}, {"text": "Me"}, {"text": "Group"}],
            [{"text": "p = 4"}, {"text": "9"}, {"text": "1"}, {"text": "5"}, {"text": "5"}]]
    return {"id": "spans", "data": {"t": {"rows": rows}},
            "stages": {"s": {"content": [{"id": "tb", "type": "table", "value": {"expr": "data['t']"}}],
                             "responses": [{"id": "a", "kind": "number", "range": [0, 9], "prompt": "n"}]}},
            "flow": {"stage": "s"}}


class TableSpans(unittest.TestCase):
    def test_spans_served_only_when_present(self):
        env = Env(Protocol(prot()))
        st = env.open(env.design(n=1, seed=1)[0]).reset()
        rows = next(i for i in st["screen"]["items"] if i.get("type") == "table")["rows"]
        self.assertEqual(rows[0][1], {"text": "Plan North", "colspan": 2})
        self.assertEqual(rows[1][0], {"text": "Price", "rowspan": 1})   # present (>= 1): served as given
        self.assertEqual(rows[1][1], "Me")   # no span: a plain string as before

    def test_check_blocks_a_lost_span(self):
        p = Protocol(prot())
        env, probs, stats = play(p, 3, 1)
        self.assertEqual(table_spans_unserved(p, env.sessions), [])
        lost = [[{"text": ""}, "Plan North", "Plan South"], ["Price", "Me", "Group", "Me", "Group"],
                ["p = 4", "9", "1", "5", "5"]]
        fake = SimpleNamespace(pages=[{"stages": [("s", None)], "shown": [{"type": "table", "rows": lost}]}])
        self.assertEqual(table_spans_unserved(p, [fake]), ["s"])


if __name__ == "__main__":
    unittest.main()


class SampledChecksSeeEveryArm(unittest.TestCase):
    def test_stage_only_in_the_last_arm(self):
        """Arm-ordered designs: the first 50 sessions may all be one arm; the sampled page checks see every arm."""
        pr = prot()
        pr["arms"] = [{"id": "a", "n_paper": 60}, {"id": "b", "n_paper": 5}]
        pr["stages"]["q"] = {"responses": [{"id": "x", "kind": "number", "range": [0, 9], "prompt": "n"}]}
        pr["flow"] = {"seq": [{"stage": "q"}, {"if": "arm == 'b'", "then": {"stage": "s"}}]}
        p = Protocol(pr)
        env, probs, stats = play(p, 60, 1)
        self.assertTrue(all(s.spec["arm"] == "a" for s in env.sessions[:50]))
        lost = [[{"text": ""}, "Plan North", "Plan South"], ["Price", "Me", "Group", "Me", "Group"],
                ["p = 4", "9", "1", "5", "5"]]
        for s in env.sessions:   # serve the table without its spans, as the old engine did
            for pg in s.pages:
                for it in pg.get("shown") or []:
                    if it.get("rows"):
                        it["rows"] = lost
        self.assertEqual(table_spans_unserved(p, env.sessions[:50]), [])          # the old sample misses arm b
        self.assertEqual(table_spans_unserved(p, sample_sessions(env.sessions)), ["s"])
