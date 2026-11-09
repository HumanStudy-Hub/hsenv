"""Engine pass 3, review round 7 (invented fixtures): v3-anchor marks only in the picture form, segmentation rules need
recognised kind / style clauses, row labels / column heads numbered over the grid, and a byte-order mark never makes a
second reader."""
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
V3L = 'p1 | 1 | text | Your token "[image]" is worth 2 coins. [note: picture of a gold coin]'
DIS = 'p1 | 1 | text | Your token "[image]" now is worth 2 coins.'
BODY = 'Your token "[image]" is worth 2 coins.'


class AnchorForms(unittest.TestCase):
    def test_marks(self):
        for mark in ("[image of coin, NOW]", "[logo Hello]", "[image: coin with NOW on it]", "[icon; now]",
                     "[picture of coin and the letter A]", "[image / now]", "[image] now [image]", "[image showing now]",
                     "[figure: Fig. A]", "[photo: coin; also STOP]", "[image: coin above Now]"):
            v, rules, unc = run(gap_prot(), V3L, ('p1 | 1 | text | Your token "%s" is worth 2 coins.' % mark, DIS))
            self.assertIn(A1, unc, mark)
        # '<kw>: one to three lower-case words' is the allowed legacy form (it cannot tell 'now' from a description)
        v, rules, unc = run(gap_prot(), V3L, ('p1 | 1 | text | Your token "[image: gold coin]" is worth 2 coins.', DIS))
        self.assertNotIn(A1, unc)


class NarrowLegacyForms(unittest.TestCase):
    """Coordinator ruling after round 7: an optional article, 'callout' directly before a picture phrase, and the
    die-face phrases (optionally '+ showing <n> pips' and a position clause); nothing broader."""

    def test_marks(self):
        ok = ("[callout die image showing six pips]",
              "[note: an image of a die face showing six pips sits between the two straight double quotes]",
              "[note: the image of a die face showing six pips]",
              "[callout image of a die face showing six pips placed between the two curly single quotes]")
        bad = ("[note: between the two straight double quotes is a picture of a die face showing six pips, no text]",
               "[callout die image with the word six]", "[callout die image showing 6 pips]",
               "[note: a die face showing seven pips]", "[note: an image of a die face showing six pips sits under "
                                                        "the quotes]", "[note: an image of a die face reading six]",
               "[callout die image showing six pips, then Go]",
               "[note: a die face]")   # no picture word: not a picture mark at all (round 6 M1)
        for m in ok:
            self.assertTrue(checks._anchor_picture(m), m)
        for m in bad:
            self.assertFalse(checks._anchor_picture(m), m)

    def test_vote(self):
        leg = 'p1 | 1 | text | Your token "[callout die image showing six pips]" is worth 2 coins.'
        self.assertNotIn(A1, run(gap_prot(), V3L, (leg, DIS))[2])
        leg = 'p1 | 1 | text | Your token "[callout die image with the word six]" is worth 2 coins.'
        self.assertIn(A1, run(gap_prot(), V3L, (leg, DIS))[2])


class V3Screens(unittest.TestCase):
    def test_screen_field_must_be_screen_k(self):
        for screen, gap in (("screen 1", True), ("1", True), ("intro page", False), ("screen 1 (top)", False)):
            r = "p1 | %s | text | %s" % (screen, BODY)   # the helper writes a bare '1' as 'screen 1'
            v = check(gap_prot(), r)
            self.assertEqual(A1 not in [k[2] for k in v["image_unconfirmed"]], gap, screen)
        # legacy screen-field remarks are a known legacy limit (DESIGN.md §3.5): unchanged
        self.assertEqual(check(gap_prot(), "p1 | intro page | text | " + BODY, header="")["found"], 3)


class KindAndStyleClauses(unittest.TestCase):
    CASES = ("p1 | 1 | text | followed by the word now | " + BODY, "p1 | 1 | text | word now after the coin | " + BODY,
             "p1 | 1 | text [coin then now] | " + BODY, "p1 | 1 | text, now printed after picture | " + BODY)

    def test_no_anchor_and_no_v3_rule(self):
        for leg in self.CASES:
            self.assertIn(A1, run(gap_prot(), V3L, (leg, DIS))[2], leg)   # legacy line: no anchored vote
            self.assertIn(A1, run(gap_prot(), leg, ())[2], leg)           # v3 line: no image_gap
            self.assertIn(A1, run(gap_prot(), None, (leg,))[2], leg)      # legacy line: no image_gap
        ok = "p1 | 1 | text | bold | " + BODY
        self.assertNotIn(A1, run(gap_prot(), ok, ())[2])


class GridLabels(unittest.TestCase):
    def tab(self, rows):
        return proto(data={"t": {"rows": [[dict(x, cite=c()) if isinstance(x, dict) else
                                           ({"text": x, "cite": c()} if x else {"text": ""}) for x in row]
                                          for row in rows]}})

    def unc(self, rows, r, hdr=V3):
        return sorted(k[2] for k in check(self.tab(rows), r, header=hdr)["image_unconfirmed"])

    def test_row_label_must_be_in_grid_column_0(self):
        rows = [["", "K", "V"], [{"text": "Pair", "rowspan": 2}, "x", "1"], ["y", "2"]]
        r = "\n".join(["p1 | 1 | label | column head 1 | K", "p1 | 1 | label | column head 2 | V",
                       "p1 | 1 | label | row label 1 | Pair", "p1 | 1 | label | row label 2 | y",
                       "p1 | 1 | cell | row 2 col 2 | x", "p1 | 1 | cell | row 3 col 3 | 2"])
        for hdr in (V3, ""):
            self.assertEqual(self.unc(rows, r, hdr), ["1", "y"])
        r2 = r.replace("p1 | 1 | label | row label 2 | y", "p1 | 1 | cell | row 3 col 2 | y")
        self.assertEqual(self.unc(rows, r2), ["1"])

    def test_two_row_head(self):
        rows = [[{"text": "Item", "rowspan": 2}, {"text": "Score", "colspan": 2}], ["a", "b"], ["Q1", "3", "4"]]
        r = "\n".join(["p1 | 1 | label | column head 1 | Score", "p1 | 1 | label | row label 1 | a",
                       "p1 | 1 | label | row label 2 | Q1", "p1 | 1 | cell | row 3 col 2 | 3",
                       "p1 | 1 | cell | row 3 col 3 | 4", "p1 | 1 | label | row 1 col 1 | Item",
                       "p1 | 1 | cell | row 2 col 3 | b"])
        self.assertEqual(self.unc(rows, r), ["Q1", "a"])   # 'a' is no row label; Q1 is row label 1, not 2


class SlashPieces(unittest.TestCase):
    def test_pieces_never_whole_lines(self):
        t = "Plan North:\nYou keep the tokens."
        for r in ("p1 | 1 | text | Plan North: / Stop\np1 | 1 | text | You keep the tokens.",
                  "p1 | 1 | text | Plan North:\np1 | 1 | text | Go / You keep the tokens.",
                  "p1 | 1 | heading | Plan North: | Stop\np1 | 1 | text | You keep the tokens."):
            for hdr in (V3, ""):
                self.assertEqual(check(proto(t), r, header=hdr)["found"], 0, r)
        leg = LEG_CELLS.replace("p1 | 1 | cell | You keep the tokens.", "p1 | 1 | cell | You keep the tokens. / Not")
        self.assertIn(t, run(table(), V3_CELLS, (leg, LEG_BAD))[2])


class ByteOrderMark(unittest.TestCase):
    def test_bom_copy_is_one_reader(self):
        texts = {"s#second": LEG_CELLS, "s#third": "﻿" + LEG_CELLS, "s#third-2": LEG_BAD}
        for k in texts:
            checks.LEGACY_READINGS.add(checks.reading_sha256(texts[k]))
        v = check_verbatim(table(), texts)
        # without the BOM fold the copy would be a second reading; LEGACY readings never confirm table cells alone
        self.assertEqual(len(v["image_unconfirmed"]), 2)
        self.assertEqual(checks._reading_body_key("﻿Blind (format v3)\np1 | 1 | text | A"),
                         checks._reading_body_key("Other header\np1 | 1 | text | A"))


if __name__ == "__main__":
    unittest.main()
