"""Engine pass 3, review round 6 (invented fixtures): v3-anchor marks must be picture remarks (M1), the anchor is bound
to the gap composition the v3 reading vouched for (S1), row labels / column heads come from the grid squares covering a
cell and spanning ones are ambiguous (S2), and a re-filed reading (same body, new header) is one reader (S3)."""
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [_HERE, os.path.dirname(_HERE)]
from hsenv import checks  # noqa: E402
from hsenv.checks import check_verbatim  # noqa: E402
from test_engine_pass3 import V3, c, check, proto  # noqa: E402
from test_engine_pass3_anchor import LEG_BAD, LEG_CELLS, V3_CELLS, run, table  # noqa: E402
from test_engine_pass3_review2 import gap_prot  # noqa: E402

A1 = 'Your token "'


class AnchorMarks(unittest.TestCase):
    V3L = 'p1 | 1 | text | Your token "[image]" is worth 2 coins. [note: picture of a gold coin]'
    DIS = 'p1 | 1 | text | Your token "[image]" now is worth 2 coins.'

    def test_marks_hiding_text_never_anchor(self):
        for mark in ("[coin icon followed by the word now]", "[image; then printed 'now']", "[text: now]", "[now]",
                     "[note: the word now is printed here]", "[smudge]", "[2]", "[blank]"):
            leg = 'p1 | 1 | text | Your token "%s" is worth 2 coins.' % mark
            v, rules, unc = run(gap_prot(), self.V3L, (leg, self.DIS))
            self.assertIn(A1, unc, mark)
        v, rules, unc = run(gap_prot(), self.V3L, ('p1 | 1 | text | Your token "[image: die]" is worth 2 coins.',
                                                   self.DIS))
        self.assertNotIn(A1, unc)

    def test_edge_marks(self):
        dis = 'p1 | 1 | text | Your token "[image]" is worth 2 coins. Thanks'
        for leg in ('p1 | 1 | text | Your token "[image]" is worth 2 coins. [picture of a coin captioned Thanks]',
                    'p1 | 1 | text | Your token "[image]" is worth 2 coins. [image; followed by the word Thanks]',
                    'p1 | 1 | text | [logo with the word Hello] Your token "[image]" is worth 2 coins.'):
            v, rules, unc = run(gap_prot(), 'p1 | 1 | text | Your token "[image]" is worth 2 coins.', (leg, dis))
            self.assertIn(A1, unc, leg)

    def test_cell_anchor_with_marks(self):
        n = "Plan North:\nYou keep the tokens."
        for rep in ("You keep the tokens. [word 'all' crossed out]", "You keep [all] the tokens.",
                    "You keep the tokens. [callout: also printed: not]", "You keep the tokens. [image of a hand]",
                    "You keep the tokens. [?]"):
            v, rules, unc = run(table(), V3_CELLS, (LEG_CELLS.replace("You keep the tokens.", rep), LEG_BAD))
            self.assertIn(n, unc, rep)


class AnchorComposition(unittest.TestCase):
    def test_bound_to_the_vouched_composition(self):
        p = gap_prot()
        p.stages["show2"] = {"content": [{"id": "u1", "value": {"expr": "data['g']['a1']"}},
                                         {"id": "u2", "type": "image", "value": {"expr": "data['g']['pic']"}},
                                         {"id": "u3", "value": {"expr": "data['g']['a3']"}}]}
        v3 = 'p1 | 1 | text | Your token "[image]" is worth 2 coins.'
        dis = 'p1 | 1 | text | Your token "[image]" now is worth 2 coins.\np1 | 2 | text | Your token "[image]" big coins.'
        leg = 'p1 | 2 | text | Your token "[words: big]coins.'   # the other stage's composition, not vouched by v3
        v, rules, unc = run(p, v3, (leg, dis))
        self.assertIn(A1, unc)


class SpanningHeads(unittest.TestCase):
    def tab(self, rows):
        return proto(data={"t": {"rows": [[dict(x, cite=c()) if isinstance(x, dict) else
                                           ({"text": x, "cite": c()} if x else {"text": ""}) for x in row]
                                          for row in rows]}})

    def test_spanning_head_is_ambiguous(self):
        r = "\n".join(["p1 | 1 | label | column head 1 | Group A", "p1 | 1 | label | column head 2 | B",
                       "p1 | 1 | label | row label 1 | Up", "p1 | 1 | cell | row Up / column Group A | 1",
                       "p1 | 1 | cell | row Up / column Group A | 2", "p1 | 1 | cell | row Up / column B | 3"])
        for body, unc in ((["Up", "1", "2", "3"], ["1", "2"]), (["Up", "1", "3", "2"], ["1", "2", "3"])):
            rows = [["", {"text": "Group A", "colspan": 2}, "B"], body]
            for hdr in (V3, ""):
                v = check(self.tab(rows), r, header=hdr)
                self.assertEqual(sorted(k[2] for k in v["image_unconfirmed"]), unc, (body, bool(hdr)))

    def test_spanning_row_label_is_ambiguous(self):
        r = "\n".join(["p1 | 1 | label | column head 1 | K", "p1 | 1 | label | column head 2 | V",
                       "p1 | 1 | label | row label 1 | Pair", "p1 | 1 | cell | row Pair / column K | x",
                       "p1 | 1 | cell | row Pair / column V | 1", "p1 | 1 | cell | row Pair / column K | y",
                       "p1 | 1 | cell | row Pair / column V | 2"])
        rows = [["", "K", "V"], [{"text": "Pair", "rowspan": 2}, "x", "1"], ["y", "2"]]
        v = check(self.tab(rows), r)
        self.assertEqual(sorted(k[2] for k in v["image_unconfirmed"]), ["1", "2", "x", "y"])


class RefiledReading(unittest.TestCase):
    def test_same_body_new_header_is_one_reader(self):
        texts = {"s#second": "Blind second reading (old)\n" + LEG_CELLS, "s#third": V3 + LEG_CELLS,
                 "s#third-2": LEG_BAD}
        for k in ("s#second", "s#third-2"):
            checks.LEGACY_READINGS.add(checks.reading_sha256(texts[k]))
        v = check_verbatim(table(), texts)
        # without de-duplication the re-filed copy would be a second agreeing vote
        self.assertEqual(len(v["image_unconfirmed"]), 2)


class ColonNumbersV3(unittest.TestCase):
    def test_cases(self):
        f = lambda t, r: check(proto(t), r)["found"]
        self.assertEqual(f("Describe your day.", "p1 | 1 | question | 3: Describe your day."), 0)
        self.assertEqual(f("Describe your day.", "p1 | 1 | question | 3: Describe your day. [note: numbered 3]"), 1)
        self.assertEqual(f("Describe your day.", "p1 | 1 | question | Q3: Describe your day."), 0)
        self.assertEqual(f("Describe your day. Be brief.",
                           "p1 | 1 | question | b) Describe your day.\np1 | 1 | question | Be brief."), 0)
        self.assertEqual(f("Age: 12", "p1 | 1 | label | Age:\np1 | 1 | text | 12"), 1)
        self.assertEqual(f("Agree", "p1 | 1 | option | 3: Agree"), 1)
        self.assertEqual(f("Intro\nDescribe your day.", "p1 | 1 | text | Intro\np1 | 1 | text | 3. Describe your day."), 0)


if __name__ == "__main__":
    unittest.main()
