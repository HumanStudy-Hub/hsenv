"""Engine pass 3, review round 5 (invented fixtures): every v3 join path strips only what the line's own rules allow
(MF1), inline stage tables are position-checked (MF2), grid names honour colspan, a named multi-line cell printed on
more lines than the served text matches by whole-line runs, style fields are split into clauses, and a leading '3:'
is no colon part of its own in v3."""
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [_HERE, os.path.dirname(_HERE)]
from test_engine_pass3 import CITE, META, V3, c, check, proto, rules  # noqa: E402
from types import SimpleNamespace  # noqa: E402


def found(text, r, header=V3):
    return check(proto(text), r, header=header)["found"]


def cells(rows):
    return [[{"text": x, "cite": c()} if x else {"text": ""} for x in row] for row in rows]


class JoinPaths(unittest.TestCase):
    def test_v3_numbers_never_stripped_by_joins(self):
        for t, r in (("people agreed with you in the last round.",
                      "p1 | 1 | text | line 1 | 12 people agreed with\np1 | 1 | text | line 2 | you in the last round."),
                     ("people agreed with you in the last round.",
                      "p1 | 1 | text | 12 people agreed with\np1 | 1 | text | you in the last round."),
                     ("Describe your day. Be brief.", "p1 | 1 | question | 3. Describe your day.\np1 | 1 | question | Be brief."),
                     ("Describe your day. Be brief.", "p1 | 1 | question | b) Describe your day.\np1 | 1 | question | Be brief."),
                     ("Your age: 25", "p1 | 1 | label | 3. Your age:\np1 | 1 | text | 25"),
                     ("Your age: years", "p1 | 1 | text | 3. Your age:\np1 | 1 | text | years"),
                     ("Read this.\nmore text here\nEnd now.",
                      "p1 | 1 | text | Read this.\np1 | 1 | text | 4 more text here\np1 | 1 | text | End now."),
                     ("agreed with you.\nNext line.", "p1 | 1 | text | 12 agreed with you.\np1 | 1 | text | Next line."),
                     ("Agree", "p1 | 1 | text | 3: Agree")):
            self.assertEqual(found(t, r), 0, r)
        self.assertEqual(found("Your age: 25", "p1 | 1 | label | 3. Your age:\np1 | 1 | text | 25", ""), 1)   # legacy

    def test_page_join_and_image_join(self):
        c2 = dict(CITE, page="1-2")
        for t, r in (("people agreed with you.", "p1 | 1 | text | In the last round\np2 | 1 | text | 12 people agreed with you."),
                     ("people agreed with you in round 3.", "p1 | 1 | text | 12 people agreed with\np2 | 1 | text | you in round 3.")):
            p = SimpleNamespace(data={"items": [{"text": t, "cite": dict(c2)}]}, stages={}, raw=META)
            self.assertEqual(check(p, r)["found"], 0, r)
        d = {"pic": {"src": "x.png", "lines": [{"text": "Strongly", "cite": c()}, {"text": "agree", "cite": c()}]}}
        self.assertEqual(check(proto(data=d), "p1 | 1 | text | I strongly agree with the plan.")["found"], 0)


class InlineTables(unittest.TestCase):
    SW = [["", "Left", "Right"], ["Up", "5", "4"], ["Down", "1", "2"]]   # print: Up 4 5 / Down 2 1
    R = "\n".join(["p1 | 1 | label | column head 1 | Left", "p1 | 1 | label | column head 2 | Right",
                   "p1 | 1 | label | row label 1 | Up", "p1 | 1 | cell | row Up / column Left | 4",
                   "p1 | 1 | cell | row Up / column Right | 5", "p1 | 1 | label | row label 2 | Down",
                   "p1 | 1 | cell | row Down / column Left | 2", "p1 | 1 | cell | row Down / column Right | 1"])

    def test_stage_table_checked_like_a_data_table(self):
        for p in (proto(data={"t": {"rows": cells(self.SW)}}),
                  proto(data={}, stages={"s": {"content": [{"id": "tb", "type": "table",
                                                            "value": {"rows": cells(self.SW)}}]}})):
            v = check(p, self.R)
            self.assertEqual(sorted(k[2] for k in v["image_unconfirmed"]), ["1", "2", "4", "5"])


class SpansAndWraps(unittest.TestCase):
    def table(self, second="Plan South:\nYou lose."):
        rows = cells([["", "Plan North:\nYou keep the tokens and the group gets none.", second],
                      ["Price", "Me", "Group", "Me", "Group"]])
        rows[0][1]["colspan"] = rows[0][2]["colspan"] = 2
        return proto(data={"t": {"rows": rows}})

    R = ("p1 | 1 | cell | row 1 col 2, line 1 | Plan North:\n"
         "p1 | 1 | cell | row 1 col 2, line 2 | You keep the tokens and the\n"
         "p1 | 1 | cell | row 1 col 2, line 3 | group gets none. [note: italic]\n"
         "p1 | 1 | cell | row 1 col 4, line 1 | Plan South:\np1 | 1 | cell | row 1 col 4, line 2 | You lose.\n")

    def unc(self, p, r):
        return sorted(k[2][:12] for k in check(p, r)["image_unconfirmed"])

    def test_colspan_grid_and_wrapped_lines(self):
        v = check(self.table(), self.R)
        self.assertEqual(sorted(rules(v).values()), ["multiline_k", "multiline_k"])
        self.assertIn("Plan South:\nYou lose.", [m["text"] for m in v["image_matches"]])

    def test_wrong_grid_column_or_split_fails(self):
        r = self.R.replace("row 1 col 4", "row 1 col 3")   # ignores the span of the first head
        self.assertIn("Plan South:\n", self.unc(self.table(), r))
        # a served line break that is not a reading line break
        p = self.table(second="Plan South: You\nlose.")
        self.assertIn("Plan South: ", self.unc(p, self.R))
        # part of the element only (line 3 missing)
        r = self.R.replace("p1 | 1 | cell | row 1 col 2, line 3 | group gets none. [note: italic]\n", "")
        self.assertIn("Plan North:\n", self.unc(self.table(), r))


class StyleFieldClauses(unittest.TestCase):
    def test_clauses_in_the_style_field(self):
        line = ('p1 | 1 | text | "50% chance" in bold; wraps onto a second line after "Next, one of you (with a" | '
                "Next, one of you (with a 50% chance).")
        self.assertEqual(found("Next, one of you (with a 50% chance).", line), 1)
        bad = line.replace('after "Next, one of you (with a"', 'after "Never"')   # quote not on the line
        self.assertEqual(found("Next, one of you (with a 50% chance).", bad), 0)


if __name__ == "__main__":
    unittest.main()
