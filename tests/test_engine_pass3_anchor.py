"""Engine pass 3, v3 anchor (maintainer ruling after review round 5; invented fixtures): a LEGACY reading line adds an
agreeing vote through multiline_k (served table cell) or image_gap only when a v3 reading confirms the same served
text by that strict rule, and the legacy line's printed content equals the served text under that rule's join."""
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [_HERE, os.path.dirname(_HERE)]
from hsenv import checks  # noqa: E402
from hsenv.checks import check_verbatim  # noqa: E402
from test_engine_pass3 import V3, c, proto, v3_screens  # noqa: E402
from test_engine_pass3_review2 import gap_prot  # noqa: E402


def run(p, v3=None, legacy=()):
    """readings: s#second = the first legacy one, s#third = v3, s#third-2 = the second legacy one."""
    texts = {}
    if legacy:
        texts["s#second"] = legacy[0]
    if v3 is not None:
        texts["s#third"] = V3 + v3_screens(v3)
    if len(legacy) > 1:
        texts["s#third-2"] = legacy[1]
    for k in ("s#second", "s#third-2"):
        if k in texts:
            checks.LEGACY_READINGS.add(checks.reading_sha256(texts[k]))
    v = check_verbatim(p, texts)
    return v, {m["text"]: m["match_rule"] for m in v["image_matches"]}, [k[2] for k in v["image_unconfirmed"]]


def table():
    rows = [[{"text": ""}, {"text": "Plan North:\nYou keep the tokens.", "cite": c()},
             {"text": "Plan South:\nYou give the tokens away.", "cite": c()}]]
    return proto(data={"t": {"rows": rows}})


V3_CELLS = ("p1 | 1 | cell | row 1 col 2, line 1 | Plan North:\np1 | 1 | cell | row 1 col 2, line 2 | You keep the tokens.\n"
            "p1 | 1 | cell | row 1 col 3, line 1 | Plan South:\n"
            "p1 | 1 | cell | row 1 col 3, line 2 | You give the tokens away.")
LEG_CELLS = ("p1 | 1 | cell | Plan North:\np1 | 1 | cell | You keep the tokens.\np1 | 1 | cell | Plan South:\n"
             "p1 | 1 | cell | You give the tokens away.")
LEG_BAD = LEG_CELLS.replace("Plan North:\n", "Plan Alpha:\n").replace("Plan South:\n", "Plan Beta:\n")


class CellAnchor(unittest.TestCase):
    def test_v3_anchor_adds_the_legacy_vote(self):
        v, rules, unc = run(table(), V3_CELLS, (LEG_CELLS, LEG_BAD))   # one legacy reading disagrees
        self.assertEqual(unc, [])
        self.assertEqual(rules["Plan North:\nYou keep the tokens."], "multiline_k+v3_anchor, multiline_k")

    def test_no_anchor_no_vote(self):
        v, rules, unc = run(table(), None, (LEG_CELLS, LEG_BAD))
        self.assertEqual(len(unc), 2)
        # the v3 reading names the cells wrongly (columns swapped): it confirms neither, so no anchor
        swapped = V3_CELLS.replace("col 2", "col X").replace("col 3", "col 2").replace("col X", "col 3")
        v, rules, unc = run(table(), swapped, (LEG_CELLS, LEG_BAD))
        self.assertEqual(len(unc), 2)

    def test_anchor_is_per_served_text(self):
        # the v3 reading confirms only Plan North; Plan South gets no anchor for the legacy vote
        v3 = V3_CELLS.replace("You give the tokens away.", "You give tokens away.")
        v, rules, unc = run(table(), v3, (LEG_CELLS, LEG_BAD))
        self.assertEqual(unc, ["Plan South:\nYou give the tokens away."])

    def test_legacy_extra_word_or_doubt_blocks(self):
        extra = LEG_CELLS.replace("You keep the tokens.", "You keep all the tokens.")
        v, rules, unc = run(table(), V3_CELLS, (extra, LEG_BAD))
        self.assertIn("Plan North:\nYou keep the tokens.", unc)
        doubt = LEG_CELLS.replace("You keep the tokens.", "You keep the tokens. [note: maybe]")
        v, rules, unc = run(table(), V3_CELLS, (doubt, LEG_BAD))
        self.assertIn("Plan North:\nYou keep the tokens.", unc)
        other = LEG_CELLS.replace("You keep the tokens.", "You keep the tokens. [note: blue frame]")
        v, rules, unc = run(table(), V3_CELLS, (other, LEG_BAD))
        self.assertIn("Plan North:\nYou keep the tokens.", unc)   # legacy note content outside the grammar


class GapAnchor(unittest.TestCase):
    V3_LINE = 'p1 | 1 | text | Your token "[image]" is worth 2 coins. [note: picture of a gold coin]'
    LEG_OK = ('p1 | 1 | text | Your token "[image: gold coin]" is worth 2 coins.',
              'p1 | 1 | text | Your token "" is worth 2 coins. [note: image: a coin]')

    def test_anchor(self):
        v, rules, unc = run(gap_prot(), self.V3_LINE, self.LEG_OK)
        self.assertEqual(unc, [])
        self.assertEqual(rules['Your token "'], "image_gap+v3_anchor, image_gap, image_gap+v3_anchor")

    def test_negatives(self):
        a1 = 'Your token "'
        # no v3 anchor
        self.assertIn(a1, run(gap_prot(), None, self.LEG_OK)[2])
        # legacy line with an extra word, a doubt, or an edge note holding printed text
        for bad in ('p1 | 1 | text | Your token "[callout gold coin]" is worth only 2 coins.',
                    'p1 | 1 | text | Your token "[callout gold coin]" is worth 2 coins. [note: maybe 3]',
                    'p1 | 1 | text | Your token "" is worth 2 coins. [note: image; then printed "Thanks"]'):
            v, rules, unc = run(gap_prot(), self.V3_LINE, (bad, self.LEG_OK[1]))
            self.assertNotIn("image_gap+v3_anchor", rules.get(a1, "").split(", ")[0], bad)
        # the v3 reading confirms a different text, not this one: no anchor for a1
        v3 = 'p1 | 1 | text | Your token "[image]" is worth 9 coins.'   # 9 is no rendering: a1 not confirmed
        v, rules, unc = run(gap_prot(), v3, self.LEG_OK)
        self.assertIn(a1, unc)


if __name__ == "__main__":
    unittest.main()
