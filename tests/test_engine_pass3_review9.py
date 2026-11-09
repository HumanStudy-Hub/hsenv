"""Engine pass 3, review round 9 (invented fixtures): in v3 ' / ', '|' and style text are printed text (no pieces),
list notes strip only the glyph / exact number, joins only within marked elements and over a page break only after the
continuation mark, a continuation line is a disagreement elsewhere, marked elements are contiguous runs, and picture
descriptions hold no capitalised word."""
import os
import sys
import unittest
from types import SimpleNamespace

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [_HERE, os.path.dirname(_HERE)]
from hsenv import checks  # noqa: E402
from test_engine_pass3 import META, V3, c, check, proto  # noqa: E402


def found(text, r, header=V3):
    return check(proto(text), r, header=header)["found"]


def tab(rows):
    return proto(data={"t": {"rows": [[dict(x, cite=c()) if isinstance(x, dict) else
                                       ({"text": x, "cite": c()} if x else {"text": ""}) for x in row] for row in rows]}})


class NoPiecesInV3(unittest.TestCase):
    def test_pieces(self):
        for t, r in (("Score: 7", "p1 | 1 | text | Score: 7 / 10"), ("Yes", "p1 | 1 | option | Yes / Oui"),
                     ("Page 1", "p1 | 1 | text | Page 1 / 3"), ("Home", "p1 | 1 | text | Home | About"),
                     ("bold", "p1 | 1 | heading | bold | Welcome")):
            self.assertEqual(found(t, r), 0, r)
            self.assertEqual(found(t, r, ""), 1, r)   # legacy: unchanged
        self.assertEqual(found("Yes. No.", "p1 | 1 | option | Yes. No."), 1)
        self.assertEqual(found("Yes.", "p1 | 1 | text | Yes. No."), 1)   # sentence units stay (Decided 5)


class ListNotes(unittest.TestCase):
    def test_strip_only_glyph_or_exact_number(self):
        for t, r in (("people agree", "p1 | 1 | text | 12 people agree [note: bullet]"),
                     ("points lost", "p1 | 1 | text | -5 points lost [note: bullet]"),
                     ("people agree", "p1 | 1 | text | 12 people agree"),
                     ("people", "p1 | 1 | text | 3. 12 people [note: numbered 3]"),
                     ("people agree", "p1 | 1 | text | 12 people agree [note: numbered 3]")):
            self.assertEqual(found(t, r), 0, r)
        self.assertEqual(found("12 people", "p1 | 1 | text | 3. 12 people [note: numbered 3]"), 1)
        self.assertEqual(found("Be kind.", "p1 | 1 | text | • Be kind. [note: bullet]"), 1)


class Joins(unittest.TestCase):
    def test_element_join_only_within_marked_elements(self):
        self.assertEqual(found("Thank you. Please continue.",
                               "p1 | 1 | text | Thank you.\np1 | 1 | text | Please continue."), 0)
        r = ("p1 | 1 | text | line 1 | The tokens are\np1 | 1 | text | line 2 | worth two coins.\n"
             "p1 | 1 | text | line 1 | Please press\np1 | 1 | text | line 2 | the button.")
        v = check(proto("The tokens are worth two coins.", "Please press the button."), r)
        self.assertEqual((v["found"], v["image_unconfirmed"]), (2, []))   # two contiguous marked elements

    def page(self, t):
        return SimpleNamespace(data={"items": [{"text": t, "cite": dict(c(), page="1-2")}]}, stages={}, raw=META)

    def test_page_join_needs_the_mark(self):
        t = "The tokens are worth two coins."
        for r in ("p1 | 1 | text | Hello. The tokens are\np2 | 1 | text | worth two coins. Bye.",
                  "p1 | 1 | text | The tokens are\np2 | 1 | text | worth two coins.",
                  "p1 | 1 | text | Hello. The tokens are [continues on next page]\np2 | 1 | text | worth two coins. Bye.",
                  "p1 | 1 | text | The tokens are [continues on next page] [note: bullet]\np2 | 1 | text | worth two coins.",
                  "p1 | 1 | text | The tokens are\np2 | 1 | text | worth two coins. [continues on next page]"):
            self.assertEqual(check(self.page(t), r)["found"], 0, r)
        self.assertEqual(check(self.page("Instructions Please read."),
                               "p1 | 1 | text | Instructions\np2 | 1 | text | Please read.")["found"], 0)
        for r in ("p1 | 1 | text | The tokens are [ Continues on next page ]  \np2 | 1 | text | worth two coins.",
                  "p1 | 1 | text | The tokens are [continues on next page]\np1 | 1 | note | [note: progress bar]\n"
                  "p2 | 1 | text | worth two coins."):
            self.assertEqual(check(self.page(t), r)["found"], 1, r)

    def test_continuation_line_disagrees_elsewhere(self):
        a = "p1 | 1 | text | The tokens are [continues on next page]\np2 | 1 | text | worth two coins."
        b = "p1 | 1 | text | The tokens are\np2 | 1 | text | worth two coins."
        v = check(proto("The tokens are"), a, b)
        self.assertEqual((v["found"], len(v["image_disputed"])), (0, 1))
        v = check(proto("The tokens are"), a)
        self.assertEqual((v["found"], v["image_uncertain_only"]), (0, []))


class MarkedCells(unittest.TestCase):
    H = "p1 | 1 | label | column head 1 | North\np1 | 1 | label | column head 2 | South\np1 | 1 | label | row label 1 | Me\n"

    def unc(self, rows, r):
        return sorted(k[2] for k in check(tab(rows), r)["image_unconfirmed"])

    def test_wrapped_single_line_cell(self):
        rows = [["", "North", "South"], ["Me", "Nine coins for you", "5"]]
        for name in ("row 2 col 2", "row Me / column North"):
            r = self.H + ("p1 | 1 | cell | %s, line 1 | Nine coins\np1 | 1 | cell | %s, line 2 | for you\n"
                          "p1 | 1 | cell | row 2 col 3 | 5" % (name, name))
            self.assertEqual(self.unc(rows, r), [], name)

    def test_other_cell_joins_refused(self):
        rows = [["", "North", "South"], ["Me", "Total: 9", "5"]]
        r = self.H + "p1 | 1 | label | row 2 col 2 | Total:\np1 | 1 | text | row 2 col 2 | 9\np1 | 1 | cell | row 2 col 3 | 5"
        self.assertEqual(self.unc(rows, r), ["Total: 9"])
        rows = [["", "North", "South"], ["Me", "people", "5"]]
        for line in ("3. 12 people [note: numbered 3]", "12 people [note: bullet]"):
            self.assertEqual(self.unc(rows, self.H + "p1 | 1 | cell | row 2 col 2 | %s\np1 | 1 | cell | row 2 col 3 | 5"
                                      % line), ["people"], line)
        rows = [["", "North", "South"], ["Me", "yes", "5"]]
        self.assertEqual(self.unc(rows, self.H + 'p1 | 1 | cell | row 2 col 2 | "yes"\np1 | 1 | cell | row 2 col 3 | 5'),
                         ["yes"])
        r = ("p1 | 1 | label | column head 1 | North. Big\np1 | 1 | label | column head 2 | South\n"
             "p1 | 1 | label | row label 1 | Me\np1 | 1 | cell | row 2 col 2 | 1\np1 | 1 | cell | row 2 col 3 | 5")
        self.assertEqual(self.unc([["", "North.", "South"], ["Me", "1", "5"]], r), ["North."])


class PictureCase(unittest.TestCase):
    def test_upper_case_word_refused(self):
        self.assertIsNone(checks._note_clause("picture of a GOLD coin"))
        self.assertEqual(checks._note_clause("Picture of a gold coin")[0], "picture")
        # documented: any lower-case noun is accepted (the form cannot tell a description from a printed word)
        self.assertEqual(checks._note_clause("picture of a coin now")[0], "picture")


if __name__ == "__main__":
    unittest.main()
