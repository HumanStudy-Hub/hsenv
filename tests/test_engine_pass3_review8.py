"""Engine pass 3, review round 8 (invented fixtures): [partial] is hard in v3 with an explicit page-break continuation
mark for page_join, picture descriptions hold no participle and no 'and', v3 table cells equal the named line's whole
content, spanning heads named by grid catch a lost span, and span limits are shared by engine and checks."""
import os
import sys
import unittest
from types import SimpleNamespace

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [_HERE, os.path.dirname(_HERE)]
from hsenv import checks  # noqa: E402
from hsenv.engine import Env, Protocol  # noqa: E402
from test_engine_pass3 import META, V3, c, check, proto  # noqa: E402
from test_engine_pass3_anchor import run  # noqa: E402
from test_engine_pass3_review2 import gap_prot  # noqa: E402

A1 = 'Your token "'
T = "The tokens are worth two coins."


def tab(rows):
    return proto(data={"t": {"rows": [[dict(x, cite=c()) if isinstance(x, dict) else
                                       ({"text": x, "cite": c()} if x else {"text": ""}) for x in row] for row in rows]}})


class PartialAndContinuation(unittest.TestCase):
    def test_partial_is_hard_in_v3(self):
        for r in ("p1 | 1 | text | The tokens are [partial]\np1 | 1 | text | worth two coins.",
                  "p1 | 1 | text | line 1 | The tokens are [partial]\np1 | 1 | text | line 2 | worth two coins.",
                  "p1 | 1 | text | The tokens [partial] are\np1 | 1 | text | worth two coins.",
                  "p1 | 1 | text | [partial] The tokens are\np1 | 1 | text | worth two coins."):
            self.assertEqual(check(proto(T), r)["found"], 0, r)
        r = "p1 | 1 | text | The tokens are [partial]\np1 | 1 | text | worth two coins."
        self.assertEqual(check(proto(T), r, header="")["found"], 1)   # legacy: unchanged

    def page(self):
        return SimpleNamespace(data={"items": [{"text": T, "cite": dict(c(), page="1-2")}]}, stages={}, raw=META)

    def test_page_join(self):
        for r in ("p1 | 1 | text | The tokens are [partial]\np2 | 1 | text | worth two coins.",
                  "p1 | 1 | text | The tokens are\np2 | 1 | text | [partial] worth two coins.",
                  "p1 | 1 | text | The tokens are [continues on next page] [partial]\np2 | 1 | text | worth two coins.",
                  "p1 | 1 | text | The tokens [continues on next page] are\np2 | 1 | text | worth two coins."):
            self.assertEqual(check(self.page(), r)["found"], 0, r)
        ok = "p1 | 1 | text | The tokens are [continues on next page]\np2 | 1 | text | worth two coins."
        self.assertEqual(check(self.page(), ok)["found"], 1)
        # the continuation mark never lets the line confirm anything alone
        self.assertEqual(check(proto("The tokens are"), "p1 | 1 | text | The tokens are [continues on next page]")
                         ["found"], 0)


class PictureParticiples(unittest.TestCase):
    def test_marks(self):
        v3l = 'p1 | 1 | text | Your token "[image]" is worth 2 coins. [note: picture of a gold coin]'
        dis = 'p1 | 1 | text | Your token "[image]" now is worth 2 coins.'
        for mark in ("[image of a coin reading now]", "[picture of a coin stamped now]", "[image of a coin and now]",
                     "[the image of a sign]", "[callout image of a coin marked now]",
                     "[image of the token bearing now]", "[image showing a coin]"):
            self.assertFalse(checks._anchor_picture(mark), mark)
            leg = 'p1 | 1 | text | Your token "%s" is worth 2 coins.' % mark
            self.assertIn(A1, run(gap_prot(), v3l, (leg, dis))[2], mark)
        self.assertTrue(checks._anchor_picture("[callout die image showing six pips]"))
        self.assertIsNone(checks._note_clause("picture of a coin and now"))   # v3 picture form: no 'and' either


class WholeCells(unittest.TestCase):
    HEADS = "p1 | 1 | label | column head 1 | North\np1 | 1 | label | column head 2 | South\np1 | 1 | label | row label 1 | Me\n"

    def unc(self, rows, r):
        return sorted(k[2] for k in check(tab(rows), r)["image_unconfirmed"])

    def test_v3_cells_whole_content(self):
        rows = [["", "North", "South"], ["Me", "9", "5"]]
        self.assertEqual(self.unc(rows, self.HEADS + "p1 | 1 | cell | row 2 col 2 | 9 / 1\np1 | 1 | cell | row 2 col 3 | "
                                                     "5 / 5"), ["5", "9"])
        self.assertEqual(self.unc(rows, self.HEADS + "p1 | 1 | cell | row Me / column North | 9 / 1\n"
                                                     "p1 | 1 | cell | row Me / column South | 5 / 5"), ["5", "9"])
        rows2 = [["", "North", "South"], ["Me", "Nine coins.", "5"]]
        self.assertEqual(self.unc(rows2, self.HEADS + "p1 | 1 | cell | row 2 col 2 | Nine coins. One coin.\n"
                                                      "p1 | 1 | cell | row 2 col 3 | 5"), ["Nine coins."])

    def test_lost_head_span_caught_by_grid_names(self):
        served = [["", "North", "South"], ["Me", "9", "1", "5", "5"]]   # the print: North and South span 2 columns
        r = ("p1 | 1 | cell | row 1 col 2 | North\np1 | 1 | cell | row 1 col 4 | South\np1 | 1 | label | row label 1 | Me\n"
             "p1 | 1 | cell | row 2 col 2 | 9\np1 | 1 | cell | row 2 col 3 | 1\np1 | 1 | cell | row 2 col 4 | 5\n"
             "p1 | 1 | cell | row 2 col 5 | 5")
        self.assertEqual(self.unc(served, r), ["South"])


class SpanLimits(unittest.TestCase):
    def test_engine_and_checks_share_limits(self):
        rows = [[{"text": "Wide", "colspan": 101}, {"text": "Ok", "colspan": 2}], [{"text": "a"}, {"text": "b"}]]
        prot = {"id": "s", "data": {"t": {"rows": rows}},
                "stages": {"s": {"content": [{"id": "tb", "type": "table", "value": {"expr": "data['t']"}}],
                                 "responses": [{"id": "a", "kind": "number", "range": [0, 9], "prompt": "n"}]}},
                "flow": {"stage": "s"}}
        p = Protocol(prot)
        env = Env(p)
        st = env.open(env.design(n=1, seed=1)[0]).reset()
        cells = next(i for i in st["screen"]["items"] if i.get("type") == "table")["rows"][0]
        self.assertEqual(cells, ["Wide", {"text": "Ok", "colspan": 2}])   # over the limit: served without it
        env2, _, _ = checks.play(p, 2, 1)
        self.assertEqual(checks.table_spans_unserved(p, env2.sessions), ["invalid colspan 101 on cell 'wide'"])


if __name__ == "__main__":
    unittest.main()
