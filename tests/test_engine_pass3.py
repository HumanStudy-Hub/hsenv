"""Engine pass 3: segmentation rules of the image gate (check_verbatim), each reported as match_rule — (1) k-line
served texts vs k reading lines (label+content cells), (2) texts separated on one stage by images / computed values vs
one reading line, (3) list glyphs vs [note: bulleted] marks, (4) numeric rows given column by column, (j) named cells
confirm only their own position, (k) a line of a multi-line cell never confirms alone. Invented fixtures only."""
import re
import unittest
from types import SimpleNamespace

from hsenv import checks
from hsenv.checks import check_verbatim

CITE = {"label": "verbatim", "source": "s", "page": 1, "read": "image"}
META = {"id": "fakestudy", "meta": {"sources": {"s": {"file": "s.pdf"}}}}


def c():
    return dict(CITE)


def proto(*texts, data=None, stages=None):
    return SimpleNamespace(data=data if data is not None else {"items": [{"text": t, "cite": c()} for t in texts]},
                           stages=stages or {}, raw=META)


V3 = "Blind second reading of s.pdf pp. 1 (independent agent; format v3)\n"


def check_l(p, *readings):
    """Rule-4 fixtures: legacy readings (positions in a screen field such as 'grid column a top'; a v3 reading writes
    the screen field as 'screen k' and positions in the style field)."""
    return check(p, *readings, header="")


def v3_screens(r):
    return re.sub(r"(?m)^(\s*p\d+\s*\|)\s*(\d+)\s*\|", r"\1 screen \2 |", r)


def check(p, *readings, header=V3):
    """Readings are v3 (the full closed note grammar) unless header="": then they are pinned as LEGACY readings, as
    the private config pins the readings collected before the v3 prompt."""
    if header:   # v3 readings write the screen field as 'screen k' (prompts.md §1); fixtures write 'k'
        readings = [v3_screens(r) for r in readings]
    texts = {("s#second", "s#third")[k]: header + r for k, r in enumerate(readings)}
    if not header:
        checks.LEGACY_READINGS.update(checks.reading_sha256(t) for t in texts.values())
    return check_verbatim(p, texts)


def found(text, reading):
    return check(proto(text), reading)["found"]


def rules(v):
    return {m["text"]: m["match_rule"] for m in v["image_matches"]}


class Rule1MultiLine(unittest.TestCase):
    def test_label_and_content_cell(self):
        r = "p1 | 1 | cell | Plan North:\np1 | 1 | cell | You keep the tokens. The group gets nothing."
        v = check(proto("Plan North:\nYou keep the tokens. The group gets nothing."), r)
        self.assertEqual(v["found"], 1)
        self.assertEqual(list(rules(v).values()), ["multiline_k"])

    def test_cell_lines_need_a_label_or_a_same_cell_note(self):
        r = "p1 | 1 | cell | Plan North\np1 | 1 | cell | You keep the tokens."
        self.assertEqual(found("Plan North\nYou keep the tokens.", r), 0)   # two cells side by side
        r2 = r + ' [note: same cell as "Plan North", printed on two lines]'
        self.assertEqual(found("Plan North\nYou keep the tokens.", r2), 1)

    def test_k_lines_in_order_whole_fields(self):
        r = "p1 | 1 | label | Group B:\np1 | 1 | note | [note: small text]\np1 | 1 | cell | Pays ten.\n" \
            "p1 | 1 | cell | Keeps two."
        self.assertEqual(found("Group B:\nPays ten.\nKeeps two.", r.replace("cell", "text")), 1)
        self.assertEqual(found("Group B:\nKeeps two.\nPays ten.", r.replace("cell", "text")), 0)   # reordered
        self.assertEqual(found("Group B:\nPays.\nKeeps two.", r.replace("cell", "text")), 0)       # a word skipped

    def test_other_text_line_between_fails(self):
        r = "p1 | 1 | cell | Plan North:\np1 | 1 | text | Read on.\np1 | 1 | cell | You keep the tokens."
        self.assertEqual(found("Plan North:\nYou keep the tokens.", r), 0)

    def test_reordered_cell_lines_fail(self):
        r = "p1 | 1 | cell | You keep the tokens.\np1 | 1 | cell | Plan North:"
        self.assertEqual(found("Plan North:\nYou keep the tokens.", r), 0)


class Rule3ListMarkers(unittest.TestCase):
    R = ("p1 | 1 | label | bold | Rules:\np1 | 1 | text | Be kind. [note: bulleted item]\n"
         'p1 | 1 | text | Be brief. [note: bulleted item; "brief" in bold]')

    def test_glyph_matched_by_bullet_note(self):
        v = check(proto("Rules:\n• Be kind.\n• Be brief."), self.R)
        self.assertEqual(v["found"], 1)
        self.assertEqual(list(rules(v).values()), ["multiline_k+list_marker"])

    def test_missing_bullet_note_fails(self):
        r = self.R.replace(" [note: bulleted item]\n", "\n")
        self.assertEqual(found("Rules:\n• Be kind.\n• Be brief.", r), 0)

    def test_literal_glyph_on_both_sides(self):
        r = "p1 | 1 | label | Rules:\np1 | 1 | text | • Be kind.\np1 | 1 | text | • Be brief."
        v = check(proto("Rules:\n• Be kind.\n• Be brief."), r)
        self.assertEqual(v["found"], 1)

    def test_single_line(self):
        v = check(proto("- Be kind."), "p1 | 1 | text | Be kind. [note: bullet point]")
        self.assertEqual((v["found"], list(rules(v).values())), (1, ["list_marker"]))
        self.assertEqual(found("- Be kind.", "p1 | 1 | text | Be kind."), 0)
        self.assertEqual(found("1. Be kind.", "p1 | 1 | text | Be kind. [note: blue]"), 0)


class Rule2Gaps(unittest.TestCase):
    def prot(self, a1='Your token "', a2='" is worth', a3="coins."):
        data = {"g": {"a1": {"text": a1, "cite": c()}, "a2": {"text": a2, "cite": c()},
                      "a3": {"text": a3, "cite": c()}, "pic": {"src": "pics/star.png"}}}
        tpl = "{'text': data['g']['a2']['text'] + ' ' + str(int(answer('pick.n'))) + ' ' + data['g']['a3']['text']}"
        stages = {"pick": {"responses": [{"id": "n", "kind": "choice", "options": [{"code": k} for k in "123"]}]},
                  "show": {"content": [{"id": "t1", "value": {"expr": "data['g']['a1']"}},
                                       {"id": "i1", "type": "image", "value": {"expr": "data['g']['pic']"}},
                                       {"id": "t2", "value": {"expr": tpl}},
                                       {"id": "t3", "value": "Next page."}]}}
        return proto(data=data, stages=stages)

    def line(self, x):
        return "p1 | 1 | text | " + x

    def test_image_mark_gap(self):
        v = check(self.prot(), self.line('Your token "[callout of a star]" is worth 2 coins.'))
        self.assertEqual(v["found"], 3)
        self.assertEqual(rules(v)['Your token "'], "image_gap")

    def test_empty_gap_between_delimiters(self):
        v = check(self.prot(), self.line('Your token "" is worth 2 coins. [note: picture of a star; between the quotes]'))
        self.assertEqual((v["found"], set(rules(v).values())), (3, {"image_gap"}))

    def test_empty_gap_needs_delimiters(self):
        p = self.prot(a1="Your token", a2="is worth")
        self.assertEqual(check(p, self.line("Your token is worth 2 coins."))["found"], 0)
        self.assertEqual(check(p, self.line("Your token [image] is worth 2 coins."))["found"], 3)

    def test_negatives(self):
        for bad in ('" is worth 2 coins. Your token "[image]',          # fragments reordered
                    'Your token "[image]" worth 2 coins.',              # a word skipped
                    'Your token "[image] gold" is worth 2 coins.',      # extra text in the gap
                    'Your token "[image]" is worth 7 coins.',           # not a rendering of the value (codes 1-3)
                    'Your token "[image]" is worth two coins.',         # not digits
                    'Your token "[image]" is worth 2 coins. Thanks.',   # line not covered
                    'Your token "[uncertain: image]" is worth 2 coins.'):
            v = check(self.prot(), self.line(bad))
            self.assertIn('Your token "', [k[2] for k in v["image_unconfirmed"]], bad)
            # reordered: '" is worth 2 coins.' is still a whole sentence of the line, and the existing template rule
            # (unchanged) takes any short number for a computed value: a2/a3 confirmed there, never a1
            self.assertEqual(v["found"], 2 if bad.startswith('" is') or " 7 " in bad else 0, bad)


class Rule4ColumnRows(unittest.TestCase):
    def prot(self):
        lines = [{"text": t, "cite": c()} for t in ("Mine", "Theirs", "10 20 30", "90 80 70")]
        return proto(data={"img": {"src": "pics/grid.png", "lines": lines}})

    def topbottom(self, cols):
        return "\n".join("p1 | grid column %s %s | text | %s" % (k, pos, v)
                         for k, t, b in cols for pos, v in (("top", t), ("bottom", b)))

    R_LABELS = "p1 | grid | label | Mine\np1 | grid | label | Theirs\n"

    def test_top_bottom_columns(self):
        v = check_l(self.prot(), self.R_LABELS + self.topbottom([("a", 10, 90), ("b", 20, 80), ("c", 30, 70)]))
        self.assertEqual(v["found"], 4)
        self.assertEqual(rules(v), {"10 20 30": "column_rows", "90 80 70": "column_rows"})

    def test_wrong_column_order_fails(self):
        v = check_l(self.prot(), self.R_LABELS + self.topbottom([("b", 20, 80), ("a", 10, 90), ("c", 30, 70)]))
        self.assertEqual(v["found"], 2)

    def test_companion_row_must_match(self):
        v = check_l(self.prot(), self.R_LABELS + self.topbottom([("a", 10, 90), ("b", 20, 81), ("c", 30, 70)]))
        self.assertEqual(v["found"], 2)

    def test_option_pairs(self):
        r = self.R_LABELS + "\n".join("p1 | grid | option | [radio] [note: column %d of 3] %s\np1 | grid | option | %s"
                                      % (k + 1, t, b) for k, (t, b) in enumerate(((10, 90), (20, 80), (30, 70))))
        self.assertEqual(check_l(self.prot(), r)["found"], 4)
        self.assertEqual(check_l(self.prot(), r.replace("column 2 of 3", "second"))["found"], 2)   # pairs unmarked
        r_empty = r.replace("[note: column 1 of 3] 10", "[note: column 1 of 3]")
        self.assertEqual(check_l(self.prot(), r_empty)["found"], 2)


class Rule4V3(unittest.TestCase):
    def test_v3_positions_in_the_style_field_only(self):
        p = Rule4ColumnRows().prot()
        cols = (("a", 10, 90), ("b", 20, 80), ("c", 30, 70))
        style = "p1 | 1 | label | Mine\np1 | 1 | label | Theirs\n" + "\n".join(
            "p1 | 1 | text | column %s %s | %s" % (k, pos, v) for k, t, b in cols for pos, v in (("top", t), ("bottom", b)))
        self.assertEqual(check(p, style)["found"], 4)
        screen = "\n".join("p1 | grid column %s %s | text | %s" % (k, pos, v)
                           for k, t, b in cols for pos, v in (("top", t), ("bottom", b)))
        self.assertEqual(check(p, "p1 | 1 | label | Mine\np1 | 1 | label | Theirs\n" + screen)["found"], 2)


class RuleJNamedCells(unittest.TestCase):
    def table(self, rows):
        return proto(data={"t": {"rows": [[{"text": x, "cite": c()} if x else {"text": ""} for x in row]
                                          for row in rows]}})

    R = ("p1 | 1 | label | column head 1 | Left\np1 | 1 | label | column head 2 | Right\n"
         "p1 | 1 | label | row label 1 | Up\np1 | 1 | label | row label 2 | Down\n"
         "p1 | 1 | cell | row Up / column Left | 4\np1 | 1 | cell | row Up / column Right | 5\n"
         "p1 | 1 | cell | row Down / column Left | 6\np1 | 1 | cell | row Down / column Right | 7")
    GOOD = [["", "Left", "Right"], ["Up", "4", "5"], ["Down", "6", "7"]]

    def test_right_cells(self):
        v = check(self.table(self.GOOD), self.R)
        self.assertEqual((v["found"], v["image_unconfirmed"]), (8, []))

    def test_swapped_cells_heads_and_row_labels_fail(self):
        for rows, n in (([["", "Left", "Right"], ["Up", "5", "4"], ["Down", "6", "7"]], 2),
                        ([["", "Right", "Left"], ["Up", "4", "5"], ["Down", "6", "7"]], 6),
                        ([["", "Left", "Right"], ["Down", "4", "5"], ["Up", "6", "7"]], 6)):
            v = check(self.table(rows), self.R)
            self.assertEqual(len(v["image_unconfirmed"]), n, rows)


class RuleKCellLines(unittest.TestCase):
    R = ("p1 | 1 | cell | row Up / column Left, line 1 | You: 4\np1 | 1 | cell | row Up / column Left, line 2 | "
         "Other: 6")

    def test_truncated_cell_fails(self):
        self.assertEqual(found("You: 4", self.R), 0)
        self.assertEqual(found("Other: 6", self.R), 0)
        self.assertEqual(found("You: 4\nOther: 6", self.R), 1)

    def test_part_of_a_longer_cell_fails(self):
        r = self.R + "\np1 | 1 | cell | row Up / column Left, line 3 | Bonus: 1"
        self.assertEqual(found("You: 4\nOther: 6", r), 0)
        self.assertEqual(found("You: 4\nOther: 6\nBonus: 1", r), 1)

    def test_table_cell_truncated(self):
        rows = [["", "Left"], ["Up", "You: 4"]]
        p = proto(data={"t": {"rows": [[{"text": x, "cite": c()} if x else {"text": ""} for x in row] for row in rows]}})
        v = check(p, "p1 | 1 | label | column head 1 | Left\np1 | 1 | label | row label 1 | Up\n" + self.R)
        self.assertEqual(v["found"], 2)   # the heads; the truncated cell stays unconfirmed
        self.assertEqual([k[2] for k in v["image_unconfirmed"]], ["You: 4"])


class Disputes(unittest.TestCase):
    def test_two_readings_needed_after_a_disagreement(self):
        good = "p1 | 1 | cell | Plan North:\np1 | 1 | cell | You keep the tokens."
        bad = "p1 | 1 | cell | Plan South:\np1 | 1 | cell | You keep the tokens."
        p = proto("Plan North:\nYou keep the tokens.")
        self.assertEqual(check(p, good, bad)["found"], 0)
        self.assertEqual(check(p, good, good + "\n")["found"], 1)


class ReviewPass3(unittest.TestCase):
    """The independent review of pass 3 (adversarial fixtures), one assertion per fixture."""

    def unc(self, v):
        return [k[2] for k in v["image_unconfirmed"]]

    def test_list_marker_attacks(self):
        for text, line in (("• Be kind.", "Be kind. [note: not bulleted]"),
                           ("3. Be kind.", "Be kind. [note: numbered item 1]"),
                           ("- Be kind.", "Be kind. [note: numbered]"),
                           ("• Be kind.", "Be kind. [note: the next line is bulleted]"),
                           ("• Be kind.", "Be kind. [partial] [note: bulleted]")):
            self.assertEqual(found(text, "p1 | 1 | text | " + line), 0, (text, line))
        self.assertEqual(found("1. Results", "p1 | 1 | heading | Results [note: bullets follow below]"), 0)
        self.assertEqual(found("3. Be kind.", "p1 | 1 | text | Be kind. [note: numbered item 3]"), 1)
        r = "p1 | 1 | label | Rules:\np1 | 1 | text | Be kind. [note: numbered]\np1 | 1 | text | Be brief. [note: numbered]"
        self.assertEqual(found("Rules:\n2. Be kind.\n1. Be brief.", r), 0)

    def test_multiline_attacks(self):
        cases = (("Choose one:\nYes", "p1 | 1 | text | Choose one: / Cancel\np1 | 1 | text | Yes / No"),
                 ("No\nMaybe", "p1 | 1 | text | Yes / No\np1 | 1 | text | Maybe / Never"),
                 ("Rules:\nbold", "p1 | 1 | label | Rules:\np1 | 1 | text | bold | Be kind."),
                 ("Plan North:\nYou keep.", "p1 | 1 | text | Plan North:\np1 | 2 | text | You keep."),
                 ("Plan North:\nYou keep.",
                  "p1 | 1 | text | Plan North:\np1 | 1 | note | * not for group B\np1 | 1 | text | You keep."),
                 ("Plan North:\nYou keep.", "p1 | 1 | text | Plan North:\np1 | 1 | text | You keep. [partial]"),
                 ("Price:\n10", "p1 | 1 | cell | Price:\np1 | 1 | cell | 10"),
                 ("You: 4\nOther: 6.", "p1 | 1 | cell | row Up / column Left, line 1 | Total: You: 4\n"
                                       "p1 | 1 | cell | row Up / column Left, line 2 | Other: 6. Bonus: 1"),
                 ("Plan North\nYou keep the tokens.", "p1 | 1 | cell | Plan North\np1 | 1 | cell | You keep the tokens. "
                                                      "[note: not the same cell as Plan North]"))
        for text, r in cases:
            self.assertEqual(found(text, r), 0, text)
        # rule e (page join): legacy joins the last line of p1 and the first of p2; v3 only after the continuation mark
        p = SimpleNamespace(data={"i": [{"text": "A:\nB.", "cite": dict(CITE, page="1-2")}]}, stages={}, raw=META)
        self.assertEqual(check(p, "p1 | 1 | text | A:\np2 | 1 | text | B.", header="")["found"], 1)
        self.assertEqual(check(p, "p1 | 1 | text | A:\np2 | 1 | text | B.")["found"], 0)
        self.assertEqual(check(p, "p1 | 1 | text | A: [continues on next page]\np2 | 1 | text | B.")["found"], 1)

    def test_lines_n_any_kind(self):
        self.assertEqual(found("You keep", "p1 | 1 | text | line 1 | You keep\np1 | 1 | text | line 2 | the tokens."), 0)
        self.assertEqual(found("You keep the tokens.",
                               "p1 | 1 | text | line 1 | You keep\np1 | 1 | text | line 2 | the tokens."), 1)
        self.assertEqual(found("You: 4", "p1 | 1 | option | line 1 | You: 4\np1 | 1 | option | line 2 | Other: 6"), 0)

    def test_named_cells(self):
        rows = [["", "Left", "Right"], ["Up", "5", "4"], ["Down", "6", "7"]]   # the Up row swapped
        tab = proto(data={"t": {"rows": [[{"text": x, "cite": c()} if x else {"text": ""} for x in row]
                                         for row in rows]}})
        heads = ("p1 | 1 | label | column head 1 | Left\np1 | 1 | label | column head 2 | Right\n"
                 "p1 | 1 | label | row label 1 | Up\np1 | 1 | label | row label 2 | Down\n")
        for r in ("p1 | 1 | cell | row Up / column Left, bold | 4\np1 | 1 | cell | row Up / column Right, bold | 5",
                  "p1 | 1 | row Up / column Left | 4\np1 | 1 | row Up / column Right | 5"):
            v = check(tab, heads + r)
            self.assertEqual(v["found"], 4)
            self.assertTrue({"5", "4"} <= set(self.unc(v)))
        dup = proto(data={"t": {"rows": [[{"text": ""}, {"text": "Left", "cite": c()}],
                                         [{"text": "Up", "cite": c()}, {"text": "5", "cite": c()}],
                                         [{"text": "Up", "cite": c()}, {"text": "4", "cite": c()}]]}})
        v = check(dup, "p1 | 1 | label | column head 1 | Left\np1 | 1 | cell | row Up / column Left | 4\n"
                       "p1 | 1 | cell | row Up / column Left | 5")
        self.assertTrue({"5", "4"} <= set(self.unc(v)))   # ambiguous position: refused
        # a served text outside any table has no position to check (kept for the plain-item two-line cells)
        self.assertEqual(found("4", "p1 | 1 | cell | row Up / column Left | 4"), 1)

    def test_empty_readings(self):
        self.assertEqual(found("Hello", ""), 0)
        self.assertEqual(found("Hello", "p1 | 1 | note | [note: blank]"), 0)

    def gap_prot(self, a1='Your token "', a2='" is worth', free=False):
        data = {"g": {"a1": {"text": a1, "cite": c()}, "a2": {"text": a2, "cite": c()},
                      "a3": {"text": "coins.", "cite": c()}, "pic": {"src": "pics/star.png"}}}
        tpl = "{'text': data['g']['a2']['text'] + ' ' + str(int(answer('pick.n'))) + ' ' + data['g']['a3']['text']}"
        resp = {"id": "n", "kind": "number"} if free else {"id": "n", "kind": "choice",
                                                           "options": [{"code": k} for k in "123"]}
        stages = {"pick": {"responses": [resp]},
                  "show": {"content": [{"id": "t1", "value": {"expr": "data['g']['a1']"}},
                                       {"id": "i1", "type": "image", "value": {"expr": "data['g']['pic']"}},
                                       {"id": "t2", "value": {"expr": tpl}}, {"id": "t3", "value": "Next page."}]}}
        return proto(data=data, stages=stages)

    def test_gap_attacks(self):
        for line in ('Your token "[note: the word GOLD here, not an image]" is worth 2 coins.',
                     'Your token "[callout: box with the word GOLD, beside a picture]" is worth 2 coins.',
                     'Your token "[note: picture; below it: Do not share your token.]" is worth 2 coins.',
                     'Your token "[image]" is worth2coins.',
                     'Your token "[note: smudge, maybe a picture]" is worth 2 coins.',
                     'Your token "[image]" is worth 1990 coins.',
                     'Your token "[image]" is worth 2 coins. [note: then: Thanks!]'):
            v = check(self.gap_prot(), "p1 | 1 | text | " + line)
            self.assertIn('Your token "', self.unc(v), line)
            self.assertNotIn("image_gap", set(rules(v).values()), line)
        # a computed value whose renderings cannot be told (free number, no range): no gap rule
        v = check(self.gap_prot(free=True), 'p1 | 1 | text | Your token "[image]" is worth 1990 coins.')
        self.assertIn('Your token "', self.unc(v))
        # an empty gap between the served texts' own quotes stays allowed (rule 2 as specified)
        v = check(self.gap_prot(), 'p1 | 1 | text | Your token "" is worth 2 coins.')
        self.assertEqual((v["found"], set(rules(v).values())), (3, {"image_gap"}))
        # a picture mark holding printed digits is no gap ('Total:' is still a whole unit of the line)
        v = check(self.gap_prot(a1="Total:", a2="is"), "p1 | 1 | text | Total: [image: 25 tokens] is 2 coins.")
        self.assertNotIn("image_gap", set(rules(v).values()))

    def cprot(self, rows=("10 20 30", "90 80 70")):
        lines = [{"text": t, "cite": c()} for t in ("Mine", "Theirs") + tuple(rows)]
        return proto(data={"img": {"src": "pics/grid.png", "lines": lines}})

    def test_column_row_attacks(self):
        rl = "p1 | grid | label | Mine\np1 | grid | label | Theirs\n"

        def tb(cols):
            return "\n".join("p1 | grid column %s %s | text | %s" % (k, pos, v)
                             for k, t, b in cols for pos, v in (("top", t), ("bottom", b)))
        two = self.cprot(("10 20", "90 80"))
        self.assertEqual(check_l(two, rl + "p1 | grid column a top | text | 10\np1 | grid column a bottom | text | 90\n"
                                         "p1 | grid column a top | text | 20\np1 | grid column a bottom | text | 80")
                         ["found"], 2)
        for cols in ([("a", 90, 10), ("b", 80, 20), ("c", 70, 30)],
                     [("a", 10, 90), ("b", "20 [note: could be 26]", 80), ("c", 30, 70)],
                     [("a", 10, 90), ("b", "20 [uncertain]", 80), ("c", 30, 70)],
                     [("a", "10%", 90), ("b", 20, 80), ("c", 30, 70)],
                     [("a", 10, 90), ("b", 20, 80)]):
            self.assertEqual(check_l(self.cprot(), rl + tb(cols))["found"], 2, cols)
        style = rl + ("p1 | grid | text | column a top | 10\np1 | grid | text | column a bottom | 90\n"
                      "p1 | grid | text | column b top | 20\np1 | grid | text | column b bottom | 80")
        self.assertEqual(check_l(two, style)["found"], 4)   # positions in the style field: one table, in order
        pg = SimpleNamespace(data={"img": {"src": "x.png", "lines": [{"text": t, "cite": dict(CITE, page="1-2")}
                                                                      for t in ("10 20", "90 80")]}}, stages={}, raw=META)
        self.assertEqual(check_verbatim(pg, {"s#second": "p1 | grid column a top | text | 10\np1 | grid column a bottom "
                                                         "| text | 90\np2 | grid column b top | text | 20\np2 | grid "
                                                         "column b bottom | text | 80"})["found"], 0)
        r = rl + "\n".join("p1 | grid | option | [note: column %d of 3] %s\np1 | grid | option | %s" % (k + 1, t, b)
                           for k, (t, b) in enumerate(((10, 90), (20, 80), (30, 70))))
        self.assertEqual(check_l(self.cprot(), r)["found"], 4)
        r2 = r.replace("[note: column 2 of 3] 20", "[note: column 2 of 3; the next option is in column 3] 20")
        self.assertEqual(check_l(self.cprot(), r2)["found"], 2)
        self.assertEqual(check_l(self.cprot(), r + "\np1 | grid | option | 55")["found"], 2)   # trailing option
        self.assertEqual(check_l(self.cprot(), r.replace(" of 3]", " of 4]"))["found"], 2)      # 'of N' honoured


if __name__ == "__main__":
    unittest.main()
