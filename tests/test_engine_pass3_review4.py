"""Engine pass 3, review round 4 (invented fixtures): unrecognised note clauses make a v3 line uncertain, picture
descriptions hold no verb / participle, v3 table cells only from lines naming their exact position, numbers are
stripped only on option / slider lines or under a list note, served images are never merged into one gap, and the
uncertain-only legacy pin never applies to a v3 reading."""
import hashlib
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [_HERE, os.path.dirname(_HERE)]
from hsenv import checks  # noqa: E402
from hsenv.checks import check_verbatim  # noqa: E402
from test_engine_pass3 import V3, c, check, proto, rules  # noqa: E402
from test_engine_pass3_review2 import gap_prot  # noqa: E402


def found(text, r, header=V3):
    return check(proto(text), r, header=header)["found"]


def table(rows):
    return proto(data={"t": {"rows": [[{"text": x, "cite": c()} if x else {"text": ""} for x in row] for row in rows]}})


class UnrecognisedNotes(unittest.TestCase):
    def test_v3_line_uncertain(self):
        for r in ('p1 | 1 | text | You will receive [note: "bonus" in superscript] 5 tokens.',
                  "p1 | 1 | text | You will receive [note: small superscript word bonus] 5 tokens.",
                  "p1 | 1 | text | You will receive 5 tokens. [note: a word after receive is hard to make out]"):
            self.assertEqual(found("You will receive 5 tokens.", r), 0, r)
        for n in ("last digit not legible", "partially hidden", "truncated at right edge", "too small to read",
                  "pixelated", "ambiguous", "difficult to read", "hard to tell"):
            self.assertEqual(found("20", "p1 | 1 | text | 20 [note: %s]" % n), 0, n)
        self.assertEqual(found("20", "p1 | 1 | text | 20 [note: italic]"), 1)


class PictureWords(unittest.TestCase):
    def test_no_verbs_or_participles(self):
        def gap(m):
            v = check(gap_prot(), 'p1 | 1 | text | Your token "%s" is worth 2 coins.' % m)
            return "image_gap" in set(rules(v).values())
        for m in ("[note: picture of a coin stamped gold]", "[note: image of a coin showing gold]",
                  "[note: picture of a banner spelling gold]", "[note: icon of the word gold]",
                  "[note: logo of a coin marked gold]"):
            self.assertFalse(gap(m), m)
        self.assertTrue(gap("[note: picture of a gold coin]"))
        self.assertTrue(gap("[note: die face showing six pips]"))


class NamedCellsOnly(unittest.TestCase):
    SW = [["", "Left", "Right"], ["Up", "5", "4"], ["Down", "1", "2"]]   # print: Up 4 5 / Down 2 1

    def unc(self, rows, r):
        return sorted(k[2] for k in check(table(rows), r)["image_unconfirmed"])

    def test_v3_cells(self):
        allc = ["1", "2", "4", "5", "Down", "Left", "Right", "Up"]
        self.assertEqual(self.unc(self.SW, "p1 | 1 | label | Left\np1 | 1 | label | Right\np1 | 1 | label | Up\n"
                                           "p1 | 1 | cell | 4\np1 | 1 | cell | 5\np1 | 1 | label | Down\n"
                                           "p1 | 1 | cell | 2\np1 | 1 | cell | 1"), allc)
        self.assertEqual(self.unc(self.SW, "p1 | 1 table header | label | Left\np1 | 1 table header | label | Right\n"
                                           "p1 | 1 table row 1 | label | Up\np1 | 1 table row 1 | cell | 4\n"
                                           "p1 | 1 table row 1 | cell | 5\np1 | 1 table row 2 | label | Down\n"
                                           "p1 | 1 table row 2 | cell | 2\np1 | 1 table row 2 | cell | 1"), allc)
        heads = ("p1 | 1 | label | column head 1 | Left\np1 | 1 | label | column head 2 | Right\n"
                 "p1 | 1 | label | row label 1 | Up\np1 | 1 | label | row label 2 | Down\n")
        self.assertEqual(self.unc(self.SW, heads + "p1 | 1 | cell | 4\np1 | 1 | cell | 5\np1 | 1 | cell | 2\n"
                                                   "p1 | 1 | cell | 1"), ["1", "2", "4", "5"])
        self.assertEqual(self.unc(self.SW, heads + "p1 | 1 | cell | row Up / column Left | 4\n"
                                                   "p1 | 1 | cell | row Up / column Right | 5\n"
                                                   "p1 | 1 | cell | row Down / column Left | 2\n"
                                                   "p1 | 1 | cell | row Down / column Right | 1"), ["1", "2", "4", "5"])
        grid = "\n".join("p1 | 1 | cell | row %d col %d | %s" % (r, c_, t) for r, c_, t in (
            (2, 2, "4"), (2, 3, "5"), (3, 2, "2"), (3, 3, "1"), (1, 2, "Left"), (1, 3, "Right"), (2, 1, "Up"),
            (3, 1, "Down")))
        self.assertEqual(self.unc(self.SW, grid), ["1", "2", "4", "5"])
        # row labels swapped while the body cells name the reading's rows: labels unnamed -> never confirmed
        rs = [["", "Left", "Right"], ["Down", "4", "5"], ["Up", "2", "1"]]
        self.assertEqual(self.unc(rs, "p1 | 1 | label | Left\np1 | 1 | label | Right\np1 | 1 | label | Up\n"
                                      "p1 | 1 | cell | row Up / column Left | 4\np1 | 1 | cell | row Up / column Right | 5\n"
                                      "p1 | 1 | label | Down\np1 | 1 | cell | row Down / column Left | 2\n"
                                      "p1 | 1 | cell | row Down / column Right | 1"), allc)


class Numbers(unittest.TestCase):
    def test_v3_leading_numbers(self):
        for served, line in (("years old", "18 years old"), ("tokens each.", "10 tokens each."), ("points", "-5 points"),
                             ("tokens go to the group.", "You get 5 tokens. 10 tokens go to the group."),
                             ("people agreed with you.", "12 people agreed with you."), ("e. Agree", "Agree"),
                             ("Agree", "e. Agree"), ("minutes left", "+3 minutes left")):
            self.assertEqual(found(served, "p1 | 1 | text | " + line), 0, line)
        self.assertEqual(found("Agree", "p1 | 1 | option | 3 Agree"), 1)
        self.assertEqual(found("Be kind.", "p1 | 1 | text | 2. Be kind. [note: numbered 2]"), 1)
        self.assertEqual(found("years old", "p1 | 1 | text | 18 years old", ""), 1)   # legacy: unchanged

    def test_list_glyphs(self):
        self.assertEqual(found("1. Agree", "p1 | 1 | text | Agree [note: numbered 1]"), 1)
        self.assertEqual(found("1) Agree", "p1 | 1 | text | Agree [note: numbered 1]"), 1)
        self.assertEqual(found("- Be kind.", "p1 | 1 | text | Be kind. [note: round bullet]"), 1)


class ServedImages(unittest.TestCase):
    def prot(self, n, cond=False):
        data = {"g": {"a1": {"text": "Pick", "cite": c()}, "a2": {"text": "or stop.", "cite": c()},
                      "pic": {"src": "x.png"}}}
        content = [{"id": "t1", "value": {"expr": "data['g']['a1']"}}]
        for k in range(n):
            it = {"id": "i%d" % k, "type": "image", "value": {"expr": "data['g']['pic']"}}
            if cond:
                it["if"] = "answer('q.n') == '%d'" % (k + 1)
            content.append(it)
        content.append({"id": "t2", "value": {"expr": "data['g']['a2']"}})
        stages = {"q": {"responses": [{"id": "n", "kind": "choice", "required": True,
                                       "options": [{"code": str(k + 1)} for k in range(n)]}]}, "s": {"content": content}}
        return proto(data=data, stages=stages)

    def test_never_merged(self):
        one, two = "p1 | 1 | text | Pick [image] or stop.", "p1 | 1 | text | Pick [image] [image] or stop."
        self.assertEqual(check(self.prot(1), one)["found"], 2)
        self.assertEqual(check(self.prot(1), two)["found"], 0)
        self.assertEqual(check(self.prot(2), one)["found"], 0)
        self.assertEqual(check(self.prot(2), two)["found"], 2)
        # alternatives: one image per option code of one required choice -> exactly one picture
        self.assertEqual(check(self.prot(3, cond=True), one)["found"], 2)
        self.assertEqual(check(self.prot(3, cond=True), two)["found"], 0)


class LegacyUncertainPin(unittest.TestCase):
    def test_never_for_v3(self):
        r = V3 + "p1 | 1 | text | 20 [uncertain: 20 or 26]"
        h = hashlib.sha256(r.encode()).hexdigest()
        checks.LEGACY_UNCERTAIN_READINGS[h] = "test"
        try:
            v = check_verbatim(proto("20"), {"s#second": r})
            self.assertEqual((v["found"], v["image_uncertain_legacy"]), (0, []))
        finally:
            checks.LEGACY_UNCERTAIN_READINGS.pop(h, None)


if __name__ == "__main__":
    unittest.main()
