"""Engine pass 3, review round 10 (invented fixtures): in v3 the fourth field is a style field only when it is a
recognised one (else it is printed content), the enumerator test runs after the glyph is stripped and a dash before a
digit is a minus sign, marked elements are invalid when the next line breaks the marker run, and v3 cells match
templates whole."""
import os
import sys
import unittest
from types import SimpleNamespace

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [_HERE, os.path.dirname(_HERE)]
from test_engine_pass3 import META, V3, c, check, proto  # noqa: E402


def found(text, r, header=V3):
    return check(proto(text), r, header=header)["found"]


class StyleFieldOrContent(unittest.TestCase):
    def test_pipes(self):
        for t, r in (("About", "p1 | 1 | text | Home | About"), ("2", "p1 | 1 | text | Page 1 | 2"),
                     ("No", "p1 | 1 | option | Yes | No"), ("Instructions", "p1 | 1 | heading | Part 1 | Instructions"),
                     ("Part 1", "p1 | 1 | heading | Part 1 | Instructions")):
            self.assertEqual(found(t, r), 0, r)
        self.assertEqual(found("Home | About", "p1 | 1 | text | Home | About"), 1)
        self.assertEqual(found("Home | About", "p1 | 1 | text | bold | Home | About"), 1)
        self.assertEqual(found("Part 1 | Instructions", "p1 | 1 | heading | Part 1 | Instructions"), 1)

    def test_cell_with_pipe(self):
        rows = [["", "North", "South"], ["Me", "9", "5"]]
        p = proto(data={"t": {"rows": [[{"text": x, "cite": c()} if x else {"text": ""} for x in r] for r in rows]}})
        r = ("p1 | 1 | label | column head 1 | North\np1 | 1 | label | column head 2 | South\n"
             "p1 | 1 | label | row label 1 | Me\np1 | 1 | cell | row 2 col 2 | 1 | 9\np1 | 1 | cell | row 2 col 3 | 5")
        self.assertEqual([k[2] for k in check(p, r)["image_unconfirmed"]], ["9"])


class GlyphsAndNumbers(unittest.TestCase):
    def test_cases(self):
        for t, r in (("Be kind", "p1 | 1 | text | • 3. Be kind [note: bullet]"),
                     ("Be kind", "p1 | 1 | text | • 3. Be kind"), ("Be kind", "p1 | 1 | text | - 3. Be kind [note: bullet]"),
                     ("Be kind", "p1 | 1 | text | (3) Be kind [note: numbered 3]"),
                     ("5 points", "p1 | 1 | text | – 5 points"), ("5 points lost", "p1 | 1 | text | – 5 points lost")):
            self.assertEqual(found(t, r), 0, r)
        self.assertEqual(found("Be kind.", "p1 | 1 | text | 3) Be kind. Now. [note: numbered 3]"), 1)
        self.assertEqual(found("people agree", "p1 | 1 | option | 12 people agree"), 1)
        self.assertEqual(found("5 points", "p1 | 1 | text | – 5 points [note: bullet]"), 1)
        self.assertEqual(found("5 points", "p1 | 1 | text | – 5 points", ""), 1)   # legacy: unchanged


class MarkedElements(unittest.TestCase):
    def test_element_edges(self):
        t = "Nine coins for you"
        for r in ("p1 | 1 | text | line 1 | Nine coins\np1 | 1 | text | line 2 | for you\np1 | 1 | text | line 2 | today",
                  "p1 | 1 | text | line 1 | Nine coins\np1 | 1 | text | line 2 | for you\np1 | 1 | text | today",
                  "p1 | 1 | text | line 1 | Nine coins\np1 | 1 | text | line 2 | for you\np1 | 1 | text | line 3 | today",
                  "p1 | 1 | text | line 1 of 3 | Nine coins\np1 | 1 | text | line 2 of 3 | for you"):
            self.assertEqual(found(t, r), 0, r)
        r = "p1 | 1 | text | line 1 | Nine coins\np1 | 1 | text | line 2 | for you"
        self.assertEqual(found(t, r), 1)
        self.assertEqual(found(t, r + "\np1 | 1 | text | Next paragraph."), 1)   # a new element starts: fine
        for t2 in ("for you", "Nine coins\nfor", "coins\nfor"):
            self.assertEqual(found(t2, r), 0, t2)
        r2 = "p1 | 1 | text | line 1 | Nine coins.\np1 | 1 | text | line 2 | For you."
        self.assertEqual(found("For you.", r2), 0)
        self.assertEqual(found("Nine coins. For", "p1 | 1 | text | line 1 | Nine coins. For\np1 | 1 | text | line 2 | you."), 0)
        self.assertEqual(found(t, "p1 | 1 | text | Nine coins [note: line 1]\np1 | 1 | text | for you [note: line 2]"), 1)

    def page(self, t):
        return SimpleNamespace(data={"items": [{"text": t, "cite": dict(c(), page="1-2")}]}, stages={}, raw=META)

    def test_page_join_edges(self):
        cont = "p1 | 1 | text | The tokens are [continues on next page]\n"
        self.assertEqual(check(self.page("The tokens are Yes"), cont + "p2 | 1 | option | Yes")["found"], 0)
        self.assertEqual(check(self.page("The tokens are worth two coins."),
                               cont + "p2 | 1 | text | - worth two coins.")["found"], 0)
        self.assertEqual(check(self.page("The tokens are"), cont + "p2 | 1 | text | worth two coins.")["found"], 0)


if __name__ == "__main__":
    unittest.main()
