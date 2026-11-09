"""Engine pass 3, review round 3 (invented fixtures): picture form, closed style tails, quoted style clauses, v3 join
barriers, position words on cell / option / label lines, the LEGACY pin set, line / part words (S1), doubt in kind /
style fields and zero-width characters (S2, S3), same-cell quotes (M5), legacy table cells (S4)."""
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [_HERE, os.path.dirname(_HERE)]
from hsenv import checks  # noqa: E402
from test_engine_pass3 import V3, c, check, proto, rules  # noqa: E402
from test_engine_pass3_review2 import gap_prot  # noqa: E402


def found(text, r, header=V3):
    return check(proto(text), r, header=header)["found"]


def table(rows):
    return proto(data={"t": {"rows": [[{"text": x, "cite": c()} if x else {"text": ""} for x in row] for row in rows]}})


class PictureForm(unittest.TestCase):
    def gap(self, line, hdr=V3):
        return "image_gap" in set(rules(check(gap_prot(), "p1 | 1 | text | " + line, header=hdr)).values())

    def test_marks(self):
        self.assertTrue(self.gap('Your token "[image]" is worth 2 coins.'))
        self.assertTrue(self.gap('Your token "[note: die face showing six pips]" is worth 2 coins.'))
        self.assertTrue(self.gap('Your token "[note: picture of a gold coin]" is worth 2 coins.'))
        for mark in ("[note: picture of a sign saying gold]", "[note: picture of a banner with caption gold]",
                     "[note: image with lettering gold]", "[note: image of the heading gold]",
                     "[note: image showing the caption gold coins]", "[image of a coin inscribed gold]",
                     "[note: picture of a coin; progress bar then printed word gold]",
                     "[note: picture of a big round gold coin]"):
            line = 'Your token "%s" is worth 2 coins.' % mark
            self.assertFalse(self.gap(line), mark)
            self.assertFalse(self.gap(line, ""), mark)


class StyleTails(unittest.TestCase):
    def test_pure_note_between_text_lines(self):
        for note, want in (("progress bar", 1), ("small", 1),
                           ("progress bar, then the sentence please wait here is printed below it", 0),
                           ("row label, the words never lie are printed between", 0),
                           ("salmon-shaded header spanning the words total score", 0),
                           ('"Never lie." in bold', 0), ('wraps onto a second line after "Never lie"', 0)):
            r = "p1 | 1 | text | Welcome.\np1 | 1 | note | [note: %s]\np1 | 1 | text | Please read." % note
            self.assertEqual(found("Welcome.\nPlease read.", r), want, note)
            # round 9 S2: v3 never joins two unmarked lines into one element
            self.assertEqual(found("Welcome. Please read.", r), 0, note)

    def test_label_and_text_across_a_note_line(self):
        for note, v3, legacy in (("a printed line here: stop", 0, 1), ("progress bar", 1, 1),
                                 ("progress bar, then the sentence please wait here is printed below it", 0, 1),
                                 ("salmon-shaded header spanning the words total score", 0, 1)):
            r = "p1 | 1 | label | Rules:\np1 | 1 | note | [note: %s]\np1 | 1 | text | Be kind." % note
            self.assertEqual(found("Rules:\nBe kind.", r), v3, note)
            self.assertEqual(found("Rules:\nBe kind.", r, ""), legacy, note)   # legacy: the old multiline rule

    def test_quoted_style_needs_the_quote_in_the_line(self):
        self.assertEqual(found("• Be kind.", 'p1 | 1 | text | Be kind. [note: bulleted; "kind" in bold]'), 1)
        self.assertEqual(found("• Be kind.", 'p1 | 1 | text | Be kind. [note: bulleted; "Always" in bold]'), 0)


class PositionWords(unittest.TestCase):
    SW = [["", "Left", "Right"], ["Up", "5", "4"]]   # served Up row swapped against the readings

    def run_t(self, r):
        out = {}
        for hdr in (V3, ""):
            v = check(table(self.SW), r, header=hdr)
            out[bool(hdr)] = sorted(k[2] for k in v["image_unconfirmed"])
        return out

    def test_v3_refuses_cells_and_heads_with_position_words(self):
        heads = "p1 | 1 | label | Left\np1 | 1 | label | Right\np1 | 1 | label | Up\n"
        cases = (heads + "p1 | 1 | cell | 4 [note: column 1 of 2]\np1 | 1 | cell | 5 [note: column 2 of 2]",
                 heads + "p1 | 1 | cell | column 1 | 4\np1 | 1 | cell | column 2 | 5",
                 "p1 | 1 | label | Left\np1 | 1 | label | Right\np1 | 1 | label | Up [note: row label]\n"
                 "p1 | 1 | cell | 4 [note: row label up, left column]\np1 | 1 | cell | 5 [note: row label up, right column]")
        for r in cases:
            self.assertTrue({"4", "5"} <= set(self.run_t(r)[True]), r)
        r = ("p1 | 1 | label | Right [note: column 1]\np1 | 1 | label | Left [note: column 2]\np1 | 1 | label | Up\n"
             "p1 | 1 | cell | 5\np1 | 1 | cell | 4")
        self.assertTrue({"Left", "Right"} <= set(self.run_t(r)[True]))
        # round 4 M1: in v3 an unnamed cell never confirms a served table cell (legacy: fields only)
        r = ("p1 | 1 | label | Left [note: salmon-shaded header spanning column 1]\n"
             "p1 | 1 | label | Right [note: salmon-shaded header spanning column 2]\np1 | 1 | label | Up\n"
             "p1 | 1 | cell | 4\np1 | 1 | cell | 5")
        self.assertEqual(self.run_t(r), {True: ["4", "5", "Left", "Right", "Up"], False: []})


class LegacyPins(unittest.TestCase):
    def test_pin_set_decides_the_format(self):
        r = "p1 | 1 | text | 20 [note: column 1 of 2]"
        self.assertTrue(checks._is_v3(r))   # not pinned: v3, whatever its header
        checks.LEGACY_READINGS.add(checks.reading_sha256(r))
        try:
            self.assertFalse(checks._is_v3(r))
        finally:
            checks.LEGACY_READINGS.discard(checks.reading_sha256(r))

    def test_header_token(self):
        for h, ok in (("Blind second reading (format v3)", True), ("Blind second reading (format: v3)", True),
                      ("Blind second reading (format v3)", True), ("Blind second reading (FORMAT V3)", True),
                      ("Blind second reading (v3 format)", False), ("Blind second reading\n(format v3)", False)):
            self.assertEqual(checks.reading_header_v3(h + "\np1 | 1 | text | x"), ok, h)


class LinesAndParts(unittest.TestCase):
    def test_style_markers(self):
        for a, b, legacy in (("line 1", "line 2", 0), ("line 1/2", "line 2/2", 0), ("line one", "line two", 1),
                             ("1st line", "2nd line", 1), ("line 1 (of 2)", "line 2 (of 2)", 1),
                             ("top line", "bottom line", 1), ("bold line 1", "bold line 2", 1),
                             ("line 1 of two", "line 2 of two", 1), ("part 1", "part 2", 1),
                             ("line 1; bold", "line 2; bold", 1), ("line 1 [note: x]", "line 2 [note: x]", 1),
                             ("line １", "line ２", 0), ("line-1", "line-2", 1), ("ln 1", "ln 2", 1),
                             ("first of two lines", "second of two lines", 1),
                             ("continues on next line", "continued", 1)):
            r = "p1 | 1 | text | %s | You keep\np1 | 1 | text | %s | the tokens." % (a, b)
            self.assertEqual(found("You keep", r), 0, a)
            self.assertEqual(found("You keep", r, ""), legacy, a)
        r = "p1 | 1, line 1 | text | You keep\np1 | 1, line 2 | text | the tokens."
        self.assertEqual((found("You keep", r), found("You keep", r, "")), (0, 1))

    def test_note_markers(self):
        for n1, n2, legacy in (("line 1 of 2", "line 2 of 2", 0), ("first line of 2", "second line", 1),
                               ("line 1, bold", "line 2, bold", 1), ("bold; line 1", "bold; line 2", 0),
                               ("line 1 of the cell", "line 2 of the cell", 1), ("Line 1", "Line 2", 0)):
            r = "p1 | 1 | text | You keep [note: %s]\np1 | 1 | text | the tokens. [note: %s]" % (n1, n2)
            self.assertEqual(found("You keep", r), 0, n1)
            self.assertEqual(found("You keep", r, ""), legacy, n1)


class Doubt(unittest.TestCase):
    def test_notes_and_fields(self):
        for note in ("may​be 26", "cut off at right edge", "cropped", "seems to be 26", "partly obscured",
                     "low resolution", "I think", "26 perhaps", "２６？", "possibly", "6 or 8 pips"):
            self.assertEqual(found("20", "p1 | 1 | text | 20 [note: %s]" % note), 0, note)
            self.assertEqual(found("20", "p1 | 1 | text | 20 [note: %s]" % note, ""), 0, note)
        self.assertEqual(found("20", "p1 | 1 | text | maybe 26 | 20"), 0)
        self.assertEqual(found("20", "p1 | 1 | text | 20? | 20"), 0)


class SameCell(unittest.TestCase):
    def test_quote_must_be_the_previous_line(self):
        for note, want in (('same cell as "Price"', 1), ('same cell as "Cost"', 0),
                           ('same cell as "Ten tokens. Not this."', 0), ("same cell", 0)):
            r = "p1 | 1 | cell | Price\np1 | 1 | cell | Ten tokens. [note: %s]" % note
            self.assertEqual(found("Price\nTen tokens.", r), want, note)
        r = 'p1 | 1 | cell | Price\np1 | 1 | cell | Cost\np1 | 1 | cell | Ten tokens. [note: same cell as "Price"]'
        self.assertEqual(found("Cost\nTen tokens.", r), 0)

    def test_quoted_clauses_on_pure_note_lines_are_barriers(self):
        for note in ('"Never lie." in bold', 'wraps onto a second line after "Never lie. Always"'):
            r = "p1 | 1 | label | Rules:\np1 | 1 | note | [note: %s]\np1 | 1 | text | Be kind." % note
            self.assertEqual(found("Rules:\nBe kind.", r), 0, note)


class LegacyTableCells(unittest.TestCase):
    def test_unnamed_cells_never_confirm_a_named_table_cell(self):
        rows = [["", "Left", "Right"], ["Up", "Price:\nTen tokens.", "4"], ["Down", "5", "6"]]
        r = ("p1 | 1 | label | column head 1 | Left\np1 | 1 | label | column head 2 | Right\n"
             "p1 | 1 | label | row label 1 | Up\np1 | 1 | label | row label 2 | Down\n"
             "p1 | 1 | cell | row Up / column Right | 4\np1 | 1 | cell | row Down / column Left | 5\n"
             "p1 | 1 | cell | row Down / column Right | 6\np1 | 1 | cell | Price:\np1 | 1 | cell | Ten tokens.")
        for hdr in (V3, ""):
            v = check(table(rows), r, header=hdr)
            self.assertEqual([k[2] for k in v["image_unconfirmed"]], ["Price:\nTen tokens."], bool(hdr))


if __name__ == "__main__":
    unittest.main()
