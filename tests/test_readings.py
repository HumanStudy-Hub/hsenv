"""Blind readings of image text (skills README Decided 5; review-1 M2, S8; review-2 S3', S5'): a served image-read
text needs a matching line in an independent blind reading (#second, #second-<k>, #third, #third-<k>); lines the
reader marked [uncertain] never count; once a reading of the page disagrees, two blind readings must agree with the
served text (and outnumber the disagreeing ones). Cites must name a meta.sources entry; unchecked texts block."""
import unittest
from types import SimpleNamespace

from hsenv.checks import check_verbatim


_V3 = None


def setUpModule():   # these readings predate the v3 reader prompt: read them as LEGACY (pass 3 format gate)
    global _V3
    import hsenv.checks as hc
    _V3, hc._is_v3 = hc._is_v3, (lambda reading: False)


def tearDownModule():
    import hsenv.checks as hc
    hc._is_v3 = _V3


def proto(*texts, source="s", read="image"):
    cite = {"label": "verbatim", "source": source, "page": 1}
    if read:
        cite["read"] = read
    data = {"items": [{"text": t, "cite": dict(cite)} for t in texts]}
    return SimpleNamespace(data=data, stages={}, raw={"id": "fakestudy",
                                                       "meta": {"sources": {"s": {"file": "s.pdf", "sha256": "x"}}}})


class Readings(unittest.TestCase):
    def test_second_reading_confirms(self):
        v = check_verbatim(proto("Press the green button"), {"s#second": "p1 | screen 1 | text | Press the green button"})
        self.assertEqual((v["found"], v["image_unconfirmed"]), (1, []))

    def test_one_third_reading_does_not_settle_a_real_dispute(self):
        # old rule (any one agreeing reading) let a converter add readers until one agreed (review-2 S5')
        texts = {"s#second": "p1 | screen 1 | text | Press the grey button",
                 "s#third": "p1 | screen 1 | text | Press the green button"}
        v = check_verbatim(proto("Press the green button"), texts)
        self.assertEqual((v["found"], len(v["image_unconfirmed"]), len(v["image_disputed"])), (0, 1, 1))
        v = check_verbatim(proto("Press the green button"), {"s#second": texts["s#second"]})
        self.assertEqual(len(v["image_unconfirmed"]), 1)

    def test_later_round_files(self):
        v = check_verbatim(proto("Next page"), {"s#second-2": "p1 | 1 | button | Next page"})
        self.assertEqual(v["found"], 1)
        v = check_verbatim(proto("Next page"), {"s#first": "p1 | 1 | button | Next page"})   # not a blind reading
        self.assertEqual(v["found"], 0)

    def test_uncertain_line_is_not_agreement(self):
        v = check_verbatim(proto("Merrill Police Department"),
                           {"s#second": "p1 | photo | interface | Merrill Police Department [uncertain: Merritt]"})
        self.assertEqual(v["found"], 0)
        self.assertEqual(len(v["image_unconfirmed"]), 1)
        self.assertEqual(len(v["image_uncertain_only"]), 1)
        v = check_verbatim(proto("Merrill Police Department"),
                           {"s#second": "p1 | photo | interface | Merrill Police Department [uncertain: Merritt]",
                            "s#third": "p1 | photo | interface | Merrill Police Department"})
        self.assertEqual(v["found"], 1)

    def test_note_is_not_screen_text(self):
        v = check_verbatim(proto("Side track"), {"s#second": "p1 | 1 | label | Side track [note: printed on two lines]"})
        self.assertEqual(v["found"], 1)


    def test_dispute_needs_two_agreeing_blind_readings(self):
        g, b = "p1 | 1 | text | Press the green button", "p1 | 1 | text | Press the grey button"
        t = "Press the green button"
        self.assertEqual(len(check_verbatim(proto(t), {"s#second": b, "s#third": g})["image_unconfirmed"]), 1)
        g2 = g + "\np1 | 1 | button | Next"   # an independent reading: same line, read differently elsewhere
        v = check_verbatim(proto(t), {"s#second": b, "s#third": g, "s#third-2": g2})
        self.assertEqual((v["found"], len(v["image_disputed"])), (1, 1))
        # adding readers until enough agree does not outvote more disagreeing readings
        # (independent disagreeing readers; copies differing only in blank lines / header are one reader since pass 3
        # round 6 S3)
        v = check_verbatim(proto(t), {"s#second": b, "s#second-2": b + "\np1 | 1 | button | Go",
                                      "s#second-3": b + "\np1 | 1 | button | Start", "s#third": g, "s#third-2": g2})
        self.assertEqual(v["found"], 0)
        v = check_verbatim(proto(t), {"s#second": b, "s#second-2": b + "\n", "s#second-3": "Blind\n" + b + "\n\n",
                                      "s#third": g, "s#third-2": g2})
        self.assertEqual(v["found"], 1)   # the three b's are one reader: 2 agree vs 1
        # a copied reading file is one reading, not a second vote
        v = check_verbatim(proto(t), {"s#second": b, "s#third": g, "s#third-2": g})
        self.assertEqual(v["found"], 0)
        # a reading that never read page 1 is neither agreement nor dispute
        v = check_verbatim(proto(t), {"s#second": g, "s#second-2": "p2 | 1 | text | other"})
        self.assertEqual((v["found"], v["image_disputed"]), (1, []))

    def test_omission_on_a_read_page_is_a_dispute(self):
        v = check_verbatim(proto("Next"), {"s#second": "p1 | 1 | button | Next", "s#third": "p1 | 1 | text | Hello"})
        self.assertEqual(len(v["image_unconfirmed"]), 1)

    def test_uncertain_second_settled_by_one_third(self):
        v = check_verbatim(proto("Merrill Police Department"),
                           {"s#second": "p1 | 1 | text | Merrill Police Department [uncertain: Merritt]",
                            "s#third": "p1 | 1 | text | Merrill Police Department"})
        self.assertEqual((v["found"], v["image_disputed"]), (1, []))

    def test_label_value_on_two_lines(self):
        r = "p1 | screen 1 | label | [blue bold label] | Sender:\np1 | screen 1 | text | Lab Desk Team"
        self.assertEqual(check_verbatim(proto("Sender: Lab Desk Team"), {"s#second": r})["found"], 1)
        r2 = "p1 | screen 1 | label | Sender:\np1 | screen 2 | text | Lab Desk Team"   # other screen: no join
        self.assertEqual(check_verbatim(proto("Sender: Lab Desk Team"), {"s#second": r2})["found"], 0)
        r3 = "p1 | screen 1 | label | Sender:\np1 | screen 1 | text | Lab Desk Team [uncertain]"
        self.assertEqual(check_verbatim(proto("Sender: Lab Desk Team"), {"s#second": r3})["found"], 0)

    def test_cite_source_must_be_a_meta_source(self):
        r = {"s#second": "p1 | 1 | text | Press the green button", "s": "Press the green button"}
        v = check_verbatim(proto("Press the green button", source="s#second", read=None), r)
        self.assertEqual((v["found"], len(v["bad_source"])), (0, 1))
        v = check_verbatim(proto("Press the green button", source="s#second"), r)   # read:image to a reading
        self.assertEqual((v["found"], len(v["bad_source"])), (0, 1))
        v = check_verbatim(proto("Press the green button", source="other", read=None), {"other": "Press the green button"})
        self.assertEqual(len(v["bad_source"]), 1)
        v = check_verbatim(proto("Press the green button", read=None), r)
        self.assertEqual((v["found"], v["bad_source"]), (1, []))

    def test_unchecked_is_listed(self):
        v = check_verbatim(proto("Hello there", read=None), {})
        self.assertEqual((v["unchecked"], v["unchecked_sources"]), (1, ["s"]))


class Review3LabelMatching(unittest.TestCase):
    """skills review-3 M4/S3: whole-field equality after normalisation; join only label+value of one screen on one
    page; unparseable page cites match nothing."""

    def found(self, text, reading, page=1):
        pr = proto(text)
        pr.data["items"][0]["cite"]["page"] = page
        return check_verbatim(pr, {"s#second": reading})["found"]

    def test_word_inside_a_longer_field_never_matches(self):
        for served, read in [("Agree", "Strongly agree"), ("very likely", "Not very likely"),
                             ("true", "Not true at all"), ("Continue", "Continue [unclear]"),
                             ("Yes", "Yes, I agree"), ("Next", "Next page"),
                             ("Answer honestly", "Answer honestly, or you will not be paid."),
                             ("Please answer every question honestly", "Please answer every question honestly, or you will not be paid."),
                             ("the green button", "Press the green button")]:
            self.assertEqual(self.found(served, "p1 | 1 | option | " + read), 0, (served, read))
            self.assertEqual(self.found(served, "p1 | 1 | text | " + read), 0, (served, read))

    def test_whole_units_match(self):
        self.assertEqual(self.found("Agree", "p1 | 1 | option | Agree"), 1)
        self.assertEqual(self.found("Agree", "p1 | 1 | option | AGREE  "), 1)          # case, whitespace
        self.assertEqual(self.found("Agree", "p1 | 1 | option | Strongly agree / Agree / Disagree"), 1)
        self.assertEqual(self.found("The first draws one row.", "p1 | 7 | text | • The first draws one row."), 1)
        self.assertEqual(self.found("How old are you?", "p1 | 2 | text | *How old are you?"), 1)   # required mark
        self.assertEqual(self.found("Example 1", "p1 | 2 | text | Example 1 [note: blue box]"), 1)  # reader remark
        self.assertEqual(self.found("Block 1:", 'p1 | 3 | cell | Block 1: (Task "orange")'), 1)
        self.assertEqual(self.found("Second sentence here.", "p1 | 1 | text | First one. Second sentence here."), 1)
        self.assertEqual(self.found("A | B", "p1 | 1 | headline | bold | A | B"), 1)

    def test_join_only_label_value_on_one_screen_and_page(self):
        lv = "p1 | 1 | label | Sender:\np1 | 1 | text | Lab Desk Team"
        self.assertEqual(self.found("Sender: Lab Desk Team", lv), 1)
        # two options, or an option and a button, are separate elements
        self.assertEqual(self.found("Strongly agree", "p1 | 1 | option | Strongly\np1 | 1 | option | agree"), 0)
        self.assertEqual(self.found("Yes Next", "p1 | 1 | option | Yes\np1 | 1 | button | Next"), 0)
        # engine pass 2 (a quoted question printed on 5 lines): consecutive lines of one element (same page, screen
        # and kind) join as a WHOLE; other screens, kinds or a part of the join never match
        self.assertEqual(self.found("Press the green button", "p1 | 1 | text | Press the\np1 | 1 | text | green button"), 1)
        self.assertEqual(self.found("Press the green button", "p1 | 1 | text | Press the\np1 | 2 | text | green button"), 0)
        self.assertEqual(self.found("Press the green button", "p1 | 1 | text | Press the\np1 | 1 | question | green button"), 0)
        self.assertEqual(self.found("the green", "p1 | 1 | text | Press the\np1 | 1 | text | green button"), 0)
        # same screen label on two pages: never joined across the page change
        pr = proto("Sender: Lab Desk Team")
        pr.data["items"][0]["cite"]["page"] = "3-4"
        r = "p3 | 1 | label | Sender:\np4 | 1 | text | Lab Desk Team"
        self.assertEqual(check_verbatim(pr, {"s#second": r})["found"], 0)

    def test_unparseable_or_wide_page_cites_match_nothing(self):
        for page in (None, "p1", "1-40", "1, 2", "", True):
            pr = proto("Yes")
            if page is None:
                del pr.data["items"][0]["cite"]["page"]
            else:
                pr.data["items"][0]["cite"]["page"] = page
            v = check_verbatim(pr, {"s#second": "p1 | 1 | option | Yes\np37 | 1 | option | Yes"})
            self.assertEqual((v["found"], len(v["image_unconfirmed"])), (0, 1), page)
        self.assertEqual(self.found("Yes", "p2 | 1 | option | Yes", page="1-2"), 1)

    def test_unclear_marks_are_uncertain(self):
        for mark in ("[unclear]", "[illegible]", "[?]", "[guess: Merrill]"):
            self.assertEqual(self.found("Merrill", "p1 | 1 | text | Merrill " + mark), 0, mark)


class Review4Matcher(unittest.TestCase):
    """skills review-4 M6 (bracketed text, [partial]) and the review-4 matcher rules: (a) printed lines of one image item
    joined, and a multi-line served element read as consecutive lines; (b) static fragments of one composed
    template around short rendered values. None of them may confirm wrong text."""

    def found(self, text, reading):
        return check_verbatim(proto(text), {"s#second": reading})["found"]

    def test_bracketed_words_are_text(self):
        for served, read in [("I agree", "I [do not] agree"), ("I agree", "I [not] agree"), ("No", "No [smudged]"),
                             ("Agree", "Agree [partial]"), ("Strongly agree", "Strongly [partial] agree"),
                             ("Example 1", "Example 1 [blue box]"), ("Yes", "Yes [partial: cut off]")]:
            self.assertEqual(self.found(served, "p1 | 1 | text | " + read), 0, (served, read))
        self.assertEqual(self.found("I [do not] agree", "p1 | 1 | text | I [do not] agree"), 1)   # printed brackets
        for read in ("Agree [note: blue box]", "Agree [radio, not selected]", "Agree [A selected]", "Agree [checked]",
                     "Agree [empty input]", "[dropdown] Agree", "Agree [info icon]", "Agree [non-english]"):
            self.assertEqual(self.found("Agree", "p1 | 1 | option | " + read), 1, read)
        # a widget-mark word followed by other words is not a mark
        self.assertEqual(self.found("Agree", "p1 | 1 | option | Agree [radio station]"), 0)

    def item(self, lines, page=1):
        c = {"label": "verbatim", "source": "s", "page": page, "read": "image"}
        data = {"img": {"src": "x.png", "lines": [{"text": t, "cite": dict(c)} for t in lines]}}
        return SimpleNamespace(data=data, stages={}, raw={"id": "fakestudy",
                                                          "meta": {"sources": {"s": {"file": "s.pdf"}}}})

    def test_a_printed_lines_join(self):
        r = "p1 | 1 | text | 50% of materials are plant based and fully recyclable\np1 | 1 | text | high-quality goods"
        v = check_verbatim(self.item(["50% of materials are plant based and", "fully recyclable", "high-", "quality goods"]),
                           {"s#second": r})
        self.assertEqual((v["found"], v["image_unconfirmed"]), (4, []))
        for lines in (["50% of materials are plant baked and", "fully recyclable"],          # one wrong letter
                      ["fully recyclable", "50% of materials are plant based and"],         # wrong order
                      ["50% of materials are plant based", "fully recyclable"]):            # word missing
            v = check_verbatim(self.item(lines), {"s#second": r})
            self.assertEqual(v["found"], 0, lines)
        # the join must be a whole unit: a longer reading line does not confirm
        v = check_verbatim(self.item(["50% of materials", "are plant based"]), {"s#second": r})
        self.assertEqual(v["found"], 0)
        # lines cited on another page are barriers
        it = self.item(["50% of materials are plant based and", "fully recyclable"])
        it.data["img"]["lines"][1]["cite"]["page"] = 2
        self.assertEqual(check_verbatim(it, {"s#second": r + "\np2 | 1 | text | fully recyclable"})["found"], 1)

    def test_a_multiline_element_read_as_consecutive_lines(self):
        r = "p1 | 1 | text | Option PURCHASE:\np1 | 1 | text | Player A buys the product."
        self.assertEqual(self.found("Option PURCHASE:\nPlayer A buys the product.", r), 1)
        self.assertEqual(self.found("Option PURCHASE:\nPlayer B buys the product.", r), 0)
        self.assertEqual(self.found("Option PURCHASE:\nPlayer A buys the product.",
                                    "p1 | 1 | text | Option PURCHASE:\np1 | 1 | text | x\np1 | 1 | text | Player A buys the product."), 0)
        self.assertEqual(self.found("Yes\nNo", "p1 | 1 | option | Yes\np1 | 1 | option | No"), 0)   # two options

    def tpl(self, expr, a="If your ticket is drawn, a prize of", b="will be paid out with your fee."):
        c = {"label": "verbatim", "source": "s", "page": 1, "read": "image"}
        data = {"T": {"a": {"text": a, "cite": dict(c)}, "b": {"text": b, "cite": dict(c)}}}
        stages = {"p6": {"content": [{"id": "t", "value": {"expr": expr}}]}}
        return SimpleNamespace(data=data, stages=stages, raw={"id": "fakestudy",
                                                               "meta": {"sources": {"s": {"file": "s.pdf"}}}})

    def test_b_fragment_template(self):
        e = "{'text': data['T']['a']['text'] + ' ' + ('GBP ' + str(answer('p4.roll'))) + ' ' + data['T']['b']['text']}"
        ok = "p1 | 1 | text | If your ticket is drawn, a prize of GBP 3 will be paid out with your fee."
        self.assertEqual(check_verbatim(self.tpl(e), {"s#second": ok})["found"], 2)
        self.assertEqual(check_verbatim(self.tpl(e), {"s#second": ok.replace("GBP 3", "GBP 0.5")})["found"], 2)
        # a string constant of the template is static text too: "GBP" must be printed
        self.assertEqual(check_verbatim(self.tpl(e), {"s#second": ok.replace("GBP 3", "£3")})["found"], 0)
        for bad in ("If your ticket is drawn, a prize of GBP 3 will not be paid out with your fee.",
                    "If your ticket is drawn, a prize of nothing at all will be paid out with your fee.",
                    "If your ticket is drawn, a prize of  will be paid out with your fee.",
                    "If your ticket is drawn, a prize of GBP 3. Something else will be paid out with your fee.",
                    "Only if your ticket is drawn, a prize of GBP 3 will be paid out with your fee."):
            self.assertEqual(check_verbatim(self.tpl(e), {"s#second": "p1 | 1 | text | " + bad})["found"], 0, bad)
        # no template in the protocol (neighbouring keys only): never composed
        self.assertEqual(check_verbatim(self.tpl("data['T']['a']"), {"s#second": ok})["found"], 0)
        # fragments cited on different pages are not one element
        pr = self.tpl(e)
        pr.data["T"]["b"]["cite"]["page"] = 2
        self.assertEqual(check_verbatim(pr, {"s#second": ok})["found"], 0)


if __name__ == "__main__":
    unittest.main()
