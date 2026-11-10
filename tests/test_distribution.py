"""Distribution tiers, release projection and link + hash rehydration (DESIGN §3.6).

Every fixture here is invented (CC0-1.0): made-up materials about cloud watching, no real study, paper or person."""
import copy
import re
import io
import json
import random
import unittest
import zipfile

import hsenv
from hsenv import checks, distribution as D, release
from hsenv.engine import Env, Protocol
from hsenv.schema_check import validate

# ------------------------------------------------------------------------------------------- invented sources
# "materials": a plain-text instrument, publicly reachable, not redistributable (tier link)
MATERIALS = (
    "Cloud Watching Survey, version 2\n"
    "Welcome! In this short survey you will look at the sky\n"
    "and tell us what shapes you see in the clouds today.\n"
    "\n"
    "Q1. How many clouds can you count right now?\n"
    "Q2. Which shape did the largest cloud remind you of?\n"
    "  a) a sleeping “dragon”\n"
    "  b) an over-\n"
    "     turned teacup\n"
    "  c) something else entirely\n"
    "Please write your answer here: ________\n"
    "Thank you for watching the sky with us.\n"
).encode("utf-8")

# "paper": a fake PDF (pages separated by form feeds) with ligatures and a hyphenated line break (tier user)
PAPER = ("%PDF-1.4 invented\f"
         "Method. Participants read the following note before the task:\n"
         "“The sky changes quickly, so ﬁnish each answer within a min-\nute.”\n\f"
         "Results. Most people saw a dragon.\n").encode("utf-8")

MAT_SHA, PAPER_SHA = D.sha256(MATERIALS), D.sha256(PAPER)
URL = "https://example.org/invented/cloud-materials.txt"


def pdf_pages(data):
    """The test's 'PDF library': pages split on form feeds."""
    return data.decode("utf-8").split("\f")


def pdf_pages_other(data):
    """A second 'library' that lays text out differently: line breaks become spaces, ligatures expanded, no curly
    quotes, extra spaces between words."""
    return [p.replace("\n", "  ").replace("ﬁ", "fi").replace("“", '"').replace("”", '"')
            for p in data.decode("utf-8").split("\f")]


pdf_pages.name = "fake-pdf/1"
pdf_pages_other.name = "fake-pdf-other/1"
PDF = {"pdf": pdf_pages}

V = "verbatim"


def project_t(*a, **kw):
    """release.project with the test's fake PDF library allowed (a release requires the pinned pypdfium2)."""
    kw.setdefault("pdf_extractor_family", None)
    return release.project(*a, **kw)


def cite(source, page=None, label=V, **kw):
    c = {"label": label, "source": source}
    if page is not None:
        c["page"] = page
    c.update(kw)
    return c


def protocol():
    return {
        "schema_version": "1", "id": "fixture_clouds",
        "meta": {"citation": "Invented fixture (CC0-1.0): a made-up cloud-watching survey; no real paper.",
                 "licence": {"paper": "CC0-1.0"}, "sample": {"n": 4},
                 "sources": {"materials": {"file": "materials.txt", "sha256": MAT_SHA},
                             "paper": "paper.pdf",
                             "scale": {"file": "scale.txt"},
                             "screens": {"file": "screens.pdf"}},
                 "notes": "the welcome text reads 'In this short survey you will look at the sky and tell us what shapes "
                          "you see' (checked twice)"},
        "arms": [{"id": "main", "n_paper": 4, "cite": cite("paper", 2, "reported",
                                                           evidence="Most people saw a dragon.")}],
        "data": {
            "welcome": {"text": "Welcome! In this short survey you will look at the sky\nand tell us what shapes you "
                                "see in the clouds today.",
                        "spans": [{"start": 0, "end": 8, "style": "bold", "tooltip": "Cloud Watching Survey"}],
                        "cite": cite("materials", 1, evidence="lines 2-3: 'Welcome! In this short survey you will "
                                                              "look at the sky'")},
            "note": {"text": "“The sky changes quickly, so finish each answer within a minute.”",
                     "cite": cite("paper", 1)},
            "shapes": [{"code": "a", "label": "a sleeping “dragon”"},
                       {"code": "b", "label": "an overturned teacup"},
                       {"code": "c", "label": "something else entirely"}],
            "shapes_cite": cite("materials", 1),
            "own_words": {"text": "Look up for a moment.", "cite": cite("materials", 1, "derived")},
            # a text composed from the source: the blank printed longer than in the source
            "blank": {"text": "Please write your answer here: __________", "cite": cite("materials", 1, "derived")},
        },
        "stages": {
            "intro": {"content": [{"id": "w", "value": {"expr": "data['welcome']"}},
                                  {"id": "n", "value": {"expr": "data['note']"}},
                                  {"id": "pic", "value": {"src": "assets/sky.png", "sha256": "ab" * 32,
                                                          "lines": [{"text": "SKY AHEAD", "cite": cite(
                                                              "screens", 1, read="image")}]},
                                   "cite": cite("screens", 1)},
                                  {"id": "own", "value": {"expr": "data['own_words']"}}],
                      "responses": [], "presentation": {"advance": "self", "back": "not_allowed",
                                                        "button": "Thank you for watching the sky with us."},
                      "presentation_cite": cite("materials", 1)},
            "q1": {"content": [{"id": "t", "value": "Q1. How many clouds can you count right now?",
                                "cite": cite("materials", 1)}],
                   "responses": [{"id": "n", "kind": "number", "range": [0, 99], "prompt": "Clouds:",
                                  "prompt_cite": cite("scale", 1), "required": True,
                                  "cite": cite("materials", 1)}],
                   "presentation": {"advance": "self", "back": "not_allowed"}},
            "q2": {"content": [{"id": "t", "value": "Q2. Which shape did the largest cloud remind you of?",
                                "cite": cite("materials", 1)}],
                   "responses": [{"id": "s", "kind": "choice", "prompt": "",
                                  "options": [{"code": "a", "label": "a sleeping “dragon”"},
                                              {"code": "b", "label": "an overturned teacup"},
                                              {"code": "c", "label": "something else entirely"}],
                                  "cite": cite("materials", 1), "required": True},
                                 {"id": "w", "kind": "text", "prompt": {"expr": "data['blank']"},
                                  "required": False, "cite": cite("materials", 1)}],
                   "presentation": {"advance": "self", "back": "not_allowed"}},
            "rate": {"content": [],
                     "responses": [{"id": "r", "kind": "choice", "prompt": "How much do you like clouds?",
                                    "options": [{"code": 1, "label": "Not at all"}, {"code": 2, "label": "Some"},
                                                {"code": 3, "label": "Very much"}],
                                    "cite": cite("scale", 1), "required": True}],
                     "presentation": {"advance": "self", "back": "not_allowed"}},
        },
        "flow": {"seq": [{"stage": "intro"}, {"stage": "q1"}, {"stage": "q2"}, {"stage": "rate"}]},
        "units": {"s": {"per": "session", "fields": {"n": "answer('q1.n')", "r": "answer('rate.r')"}}},
        "exclusions": [],
        "analysis": {"targets": [{"id": "m", "unit": "s", "field": "n", "stat": "mean",
                                  "human": {"value": 7.5, "n": 4, "cite": cite("paper", 2, "reported")}}],
                     "effects": [], "unsupported": []},
        "keyed": {"answers": {"q1.n": "3"}},
    }


TIERS = {"materials": {"tier": "link", "url": URL, "licence": "all rights reserved"},
         "paper": {"tier": "user", "sha256": PAPER_SHA},
         "scale": {"tier": "hosted", "licence": "CC-BY-4.0", "attribution": "Invented Scale Authors (CC-BY-4.0)"},
         "screens": {"tier": "user", "sha256": "cd" * 32}}
SCALE = b"Clouds:\nHow much do you like clouds?\nNot at all\nSome\nVery much\n"   # the hosted (CC-BY) source
SOURCES = {"materials": MATERIALS, "paper": PAPER, "scale": SCALE}
HELD = ["Welcome! In this short survey you will look at the sky\nand tell us what shapes you see in the clouds today.",
        "Cloud Watching Survey",
        "“The sky changes quickly, so finish each answer within a minute.”",
        "a sleeping “dragon”", "an overturned teacup", "something else entirely",
        "Please write your answer here: __________", "SKY AHEAD", "Thank you for watching the sky with us.",
        "Q1. How many clouds can you count right now?", "Q2. Which shape did the largest cloud remind you of?"]


def make():
    return project_t(protocol(), TIERS, sources=SOURCES, extractors=PDF)


def held_by_text(proj, prot):
    return {D._get(prot, h["path"]) if h["kind"] == "text" else None: hid
            for hid, h in proj["distribution"]["held"].items()}


class FakeFetch:
    def __init__(self, table):
        self.table, self.calls = table, []

    def __call__(self, url):
        self.calls.append(url)
        if url not in self.table:
            raise OSError("offline")
        return self.table[url]


# ------------------------------------------------------------------------------------------- canonical form
class TestCanonical(unittest.TestCase):
    def test_restore_round_trip(self):
        for t in ["plain", "a “quoted”  text\nwith\tbreaks", "ﬁne − 3 ½", "___ blank __",
                  "été", " lead and trail ", "­ soft​zero"]:
            c, ops = D.canon(t)
            self.assertEqual(D.restore(c, ops), __import__("unicodedata").normalize("NFC", t))
            self.assertNotRegex(c, r"\s")

    def test_ops_hold_no_words(self):
        c, ops = D.canon("The quick brown fox “jumps” over the lazy dog.")
        self.assertTrue(all(len(s) == 1 or not any(ch.isalpha() for ch in s) for _, _, s in ops))

    def test_text_sha_is_nfc(self):
        self.assertEqual(D.text_sha256("é"), D.text_sha256("é"))


# ------------------------------------------------------------------------------------------- projection
class TestProject(unittest.TestCase):
    def setUp(self):
        self.proj, self.rep = make()
        self.dump = json.dumps(self.proj, ensure_ascii=False)

    def test_no_held_text_in_projection(self):
        for t in HELD:
            self.assertNotIn(t, self.dump, t)
            self.assertNotIn(json.dumps(t, ensure_ascii=False)[1:-1], self.dump, t)
            self.assertNotIn(D.canon_only(t).lower(), D.canon_only(self.dump).lower(), t)
        # an operator note and a cite's evidence quoting held text are withheld, not shipped
        self.assertNotIn("look at the sky", self.dump)
        self.assertTrue(self.proj["meta"]["notes"].startswith(D.WITHHELD))

    def test_hosted_ships_with_attribution(self):
        r = self.proj["stages"]["rate"]["responses"][0]
        self.assertEqual([o["label"] for o in r["options"]], ["Not at all", "Some", "Very much"])
        self.assertEqual(self.proj["stages"]["q1"]["responses"][0]["prompt"], "Clouds:")   # prompt_cite = scale
        self.assertEqual(self.proj["distribution"]["attribution"][0]["source"], "scale")

    def test_structure_ships(self):
        p0 = protocol()
        for key in ("flow", "units", "exclusions", "keyed"):
            self.assertEqual(self.proj[key], p0[key])
        self.assertEqual(self.proj["analysis"]["targets"][0]["human"]["value"], 7.5)
        c = self.proj["arms"][0]["cite"]
        self.assertEqual((c["label"], c["source"], c["page"]), ("reported", "paper", 2))
        self.assertEqual(set(c["evidence"]), {D.PLACEHOLDER})   # quotes the paper: held, restored on rehydration
        r = self.proj["stages"]["q2"]["responses"][0]
        self.assertEqual([o["code"] for o in r["options"]], ["a", "b", "c"])
        self.assertEqual(r["options"][0]["label"], D.PLACEHOLDER * len("a sleeping “dragon”"))

    def test_placeholders_keep_length_and_spans(self):
        w = self.proj["data"]["welcome"]
        self.assertEqual(len(w["text"]), len(HELD[0]))
        self.assertEqual(set(w["text"]), {D.PLACEHOLDER})
        self.assertEqual(w["spans"][0]["start"], 0)
        self.assertEqual(set(w["spans"][0]["tooltip"]), {D.PLACEHOLDER})

    def test_locators(self):
        held = self.proj["distribution"]["held"]
        by_path = {h["path"]: h for h in held.values()}
        note = by_path["/data/note/text"]["locator"]
        self.assertEqual((note["format"], note["extractor"], note["pages"]), ("pdf", "fake-pdf/1", [2, 2]))
        teacup = by_path["/data/shapes/1/label"]["locator"]   # "over-\n turned" in the source
        self.assertEqual(len(teacup["parts"]), 1)
        blank = by_path["/data/blank/text"]["locator"]        # composed: source part + a shorter blank
        self.assertEqual([("literal" in x) for x in blank["parts"]], [False, True])
        self.assertEqual(blank["parts"][1]["literal"], "__")
        self.assertEqual(by_path["/stages/intro/content/2/value/lines/0/text"]["locator"]["format"], "image_reading")
        self.assertEqual(by_path["/stages/intro/content/2/value"]["kind"], "image")
        self.assertEqual(self.rep["withheld_files"], ["assets/sky.png"])
        self.assertEqual(self.rep["derived_shipped"], ["/data/own_words/text"])
        self.assertEqual(self.proj["data"]["own_words"]["text"], "Look up for a moment.")
        self.assertEqual(self.proj["meta"]["sources"]["materials"]["distribution"]["sha256"], MAT_SHA)
        self.assertEqual(self.proj["meta"]["sources"]["paper"]["distribution"]["format"], "pdf")

    def test_projection_runs_in_engine(self):
        env, problems, _ = checks.play(Protocol(copy.deepcopy(self.proj)), 3, 1)
        self.assertEqual(problems, [])
        s = Env(Protocol(copy.deepcopy(self.proj))).open(Env(Protocol(self.proj)).design(n=1, seed=0)[0])
        st = s.reset()
        self.assertTrue(set(st["screen"]["items"][0]["text"]) <= {D.PLACEHOLDER})

    def test_projection_validates(self):
        errs = validate(self.proj, "protocol")
        self.assertEqual(errs.get("errors") if isinstance(errs, dict) else [e for e in errs if e], [])

    def test_tier_rules(self):
        bad = [{"materials": {"tier": "hosted", "licence": "CC-BY-NC-4.0", "attribution": "x"}},
               {"materials": {"tier": "hosted", "licence": "CC-BY-ND-4.0", "attribution": "x"}},
               {"materials": {"tier": "hosted", "licence": "CC-BY-4.0"}},
               {"materials": {"tier": "link", "sha256": MAT_SHA}},
               {"materials": {"tier": "sometimes"}}]
        for t in bad:
            with self.assertRaises(release.ProjectionError, msg=t):
                project_t(protocol(), dict(TIERS, **t), sources=SOURCES, extractors=PDF)
        for lic in ("CC-BY-4.0", "CC0-1.0", "public domain", "CC BY 3.0"):
            self.assertTrue(release.hosted_licence_ok(lic), lic)
        for lic in ("CC-BY-SA-4.0", "CC-BY-NC-SA-4.0", "all rights reserved", None):
            self.assertFalse(release.hosted_licence_ok(lic), lic)

    def test_strict_refusals(self):
        with self.assertRaisesRegex(release.ProjectionError, "cannot be located"):
            project_t(protocol(), TIERS, sources={"materials": MATERIALS}, extractors=PDF)   # no paper file
        p = protocol()
        p["stages"]["q1"]["content"][0]["cite"]["source"] = "nowhere"
        with self.assertRaisesRegex(release.ProjectionError, "missing from meta.sources"):
            project_t(p, TIERS, sources=SOURCES, extractors=PDF)
        p = protocol()   # held text inside an expression cannot be withheld
        p["rules_note"] = {"expr": "'Q1. How many clouds can you count right now?' == ''"}
        p["stages"]["q1"]["content"].append({"id": "x", "value": {"expr": p["rules_note"]["expr"]}})
        with self.assertRaisesRegex(release.ProjectionError, "cannot be withheld"):
            project_t(p, TIERS, sources=SOURCES, extractors=PDF)
        _, rep = project_t(protocol(), TIERS, sources={"materials": MATERIALS}, extractors=PDF, strict=False)
        self.assertTrue(rep["errors"])

    def test_operator_quotes(self):
        p = protocol()
        # a quote outside the screen with a cite: held (restored on rehydration)
        p["meta"]["quote"] = {"text": "Thank you for watching the sky with us.", "cite": cite("materials", 1)}
        # a source sentence in data without any cite: an error (source text that names no source)
        p["data"]["loose"] = "In this short survey you will look at the sky and tell us what shapes you see. Go!"
        with self.assertRaisesRegex(release.ProjectionError, "source text without a cite"):
            project_t(p, TIERS, sources=SOURCES, extractors=PDF)
        del p["data"]["loose"]
        proj, rep = project_t(p, TIERS, sources=SOURCES, extractors=PDF)
        self.assertEqual(set(proj["meta"]["quote"]["text"]), {D.PLACEHOLDER})
        self.assertGreaterEqual(rep["operator_held"], 1)
        out, _ = hsenv.rehydrate(proj, fetch=FakeFetch({URL: MATERIALS}), extractors=PDF)
        self.assertEqual(out["meta"]["quote"]["text"], "Thank you for watching the sky with us.")

    def test_sync_events_are_slots(self):
        p = protocol()
        p["flow"]["seq"].append({"sync": "g", "compute": {}, "events": ["Thank you for watching the sky with us."],
                                 "cite": cite("materials", 1)})
        paths = [path for path, *_ in release._slots(p)]
        self.assertIn(["flow", "seq", 4, "events", 0], paths)

    def test_default_tier_is_user(self):
        proj, rep = project_t(protocol(), {"paper": TIERS["paper"], "screens": TIERS["screens"]},
                                    sources=SOURCES, extractors=PDF, strict=False)
        self.assertEqual(rep["tiers"]["materials"], "user")
        self.assertEqual(rep["tiers"]["scale"], "user")
        self.assertNotIn("Very much", json.dumps(proj))

    def test_distributable_files(self):
        self.assertFalse(release.distributable("sourcetext/materials.txt", self.proj))
        self.assertFalse(release.distributable("sourcetext/materials#second.txt", self.proj))
        self.assertFalse(release.distributable("sourcetext/scale.txt", self.proj))   # held items exist: content needed
        reading = next(k for k, e in self.proj["distribution"]["held"].items()
                       if e["locator"].get("format") == "image_reading")
        kw = dict(sources=dict(SOURCES, screens=b"%PDF-1.4 invented"), extractors=PDF, held_texts={reading: "SKY AHEAD"})
        self.assertTrue(release.distributable("sourcetext/scale.txt", self.proj, content=SCALE, **kw))
        self.assertFalse(release.distributable("sourcetext/scale.txt", self.proj,
                                               content=SCALE + b"an overturned teacup\n", **kw))
        self.assertFalse(release.distributable("artifacts/assets/sky.png", self.proj))
        self.assertFalse(release.distributable("review/fidelity-review-1.md", self.proj))
        self.assertFalse(release.distributable("protocol.json", self.proj))   # only as the projection itself
        self.assertTrue(release.distributable("protocol.json", self.proj, content=json.dumps(self.proj)))
        self.assertFalse(release.distributable("protocol.json", self.proj, content=json.dumps(protocol())))
        self.assertFalse(release.distributable("runs/x.json", self.proj))


# ------------------------------------------------------------------------------------------- rehydration
class TestRehydrate(unittest.TestCase):
    def setUp(self):
        self.proj, _ = make()
        self.orig = protocol()
        self.held = self.proj["distribution"]["held"]

    def hid(self, path):
        return next(h for h, e in self.held.items() if e["path"] == path)

    def full_files(self):
        img = self.hid("/stages/intro/content/2/value")
        return {"paper": PAPER}

    def test_everything_restored(self):
        fetch = FakeFetch({URL: MATERIALS})
        files, items = {"paper": PAPER}, {self.hid("/stages/intro/content/2/value/lines/0/text"): "SKY AHEAD"}
        out, rep = hsenv.rehydrate(self.proj, fetch=fetch, files=files, items=items, extractors=PDF)
        self.assertEqual(fetch.calls, [URL])   # network only through the injected fetch, once per source
        img = self.hid("/stages/intro/content/2/value")
        self.assertEqual(rep["items"][img]["status"], "needs_user_file")
        ok = [h for h, r in rep["items"].items() if r["status"] == "ok"]
        self.assertEqual(len(ok), len(self.held) - 1)
        for h in ok:
            path = self.held[h]["path"]
            self.assertEqual(D._get(out, path), D._get(self.orig, path), path)
        self.assertEqual(list(out["distribution"]["held"]), [img])
        self.assertFalse(rep["complete"])
        # the image file the user supplies is checked against its sha256
        out2, rep2 = hsenv.rehydrate(self.proj, fetch=fetch, files=files, items=dict(items, **{img: b"\x89PNG wrong"}),
                                     extractors=PDF)
        self.assertEqual(rep2["items"][img]["status"], "hash_mismatch")

    def test_complete_round_trip(self):
        p0 = protocol()
        img = p0["stages"]["intro"]["content"][2]["value"]
        pic = b"\x89PNG invented sky"
        img["sha256"] = D.sha256(pic)
        proj, _ = project_t(p0, TIERS, sources=SOURCES, extractors=PDF)
        hid = {e["path"]: h for h, e in proj["distribution"]["held"].items()}
        items = {hid["/stages/intro/content/2/value/lines/0/text"]: "SKY AHEAD", hid["/stages/intro/content/2/value"]: pic}
        out, rep = hsenv.rehydrate(proj, fetch=FakeFetch({URL: MATERIALS}), files={"paper": PAPER}, items=items,
                                   extractors=PDF)
        self.assertTrue(rep["complete"], rep["items"])
        self.assertNotIn("distribution", out)
        img_id = hid["/stages/intro/content/2/value"]
        self.assertEqual(rep["assets"], {img_id: pic})   # keyed by held id; the src is in the item report
        self.assertEqual(rep["items"][img_id]["src"], "assets/sky.png")
        # every participant-facing string is back; the engine serves the same first screen as the original
        for e in proj["distribution"]["held"].values():
            if e["kind"] == "text":
                self.assertEqual(D._get(out, e["path"]), D._get(p0, e["path"]))
        a = Env(Protocol(p0))
        b = Env(Protocol(out))
        sa, sb = a.open(a.design(n=1, seed=3)[0]).reset(), b.open(b.design(n=1, seed=3)[0]).reset()
        self.assertEqual(sa["screen"], sb["screen"])

    def test_other_pdf_library(self):
        # the app must use the extractor named in the locator: another one is refused, never tried
        out, rep = hsenv.rehydrate(self.proj, fetch=FakeFetch({URL: MATERIALS}), files={"paper": PAPER},
                                   extractors={"pdf": pdf_pages_other})
        r = rep["items"][self.hid("/data/note/text")]
        self.assertEqual(r["status"], "source_unavailable")
        self.assertIn("fake-pdf/1", r["detail"])
        # the matcher itself absorbs layout differences (spaces, ligatures, quotes, a hyphen line break)
        loc = self.held[self.hid("/data/note/text")]["locator"]
        self.assertEqual(D.find(D.Scope(pdf_pages_other(PAPER)), loc, D.text_sha256(self.orig["data"]["note"]["text"])),
                         self.orig["data"]["note"]["text"])

    def test_tampered_text_fails_per_item(self):
        # one item's text changed in the downloaded file: that item fails, its neighbours (unchanged) verify
        tampered = MATERIALS.replace(b"teacup", b"teapot")
        out, rep = hsenv.rehydrate(self.proj, fetch=FakeFetch({URL: tampered}), files={"paper": PAPER},
                                   extractors=PDF)
        tea = self.hid("/stages/q2/responses/0/options/1/label")
        self.assertEqual(rep["items"][tea]["status"], "hash_mismatch")
        self.assertTrue(set(D._get(out, self.held[tea]["path"])) <= {D.PLACEHOLDER})
        self.assertNotIn("teapot", json.dumps(out, ensure_ascii=False))
        self.assertEqual(rep["items"][self.hid("/data/welcome/text")]["status"], "ok")
        self.assertFalse(rep["sources"]["materials"]["matches_recorded_sha256"])   # provenance only

    def test_wrong_file_for_user_source(self):
        out, rep = hsenv.rehydrate(self.proj, fetch=FakeFetch({URL: MATERIALS}), files={"paper": MATERIALS},
                                   extractors=PDF)
        self.assertEqual(rep["items"][self.hid("/data/note/text")]["status"], "hash_mismatch")
        self.assertTrue(set(out["data"]["note"]["text"]) <= {D.PLACEHOLDER})

    def test_missing_item(self):
        # the user's extractor loses the text of one item (e.g. a broken text layer): only that item fails
        def lossy(data):
            return [p.replace("quickly", "") for p in pdf_pages(data)]
        lossy.name = pdf_pages.name   # the same named extractor, losing text (e.g. a broken text layer)
        out, rep = hsenv.rehydrate(self.proj, fetch=FakeFetch({URL: MATERIALS}), files={"paper": PAPER},
                                   extractors={"pdf": lossy})
        r = rep["items"][self.hid("/data/note/text")]
        self.assertEqual(r["status"], "hash_mismatch")
        self.assertIn("not found", r["detail"])
        self.assertEqual(rep["items"][self.hid("/data/welcome/text")]["status"], "ok")

    def test_unavailable_and_user_file(self):
        out, rep = hsenv.rehydrate(self.proj, fetch=FakeFetch({}), extractors=PDF)
        self.assertEqual(rep["items"][self.hid("/data/welcome/text")]["status"], "source_unavailable")
        self.assertEqual(rep["items"][self.hid("/data/note/text")]["status"], "needs_user_file")
        out, rep = hsenv.rehydrate(self.proj, extractors=PDF)   # no fetch at all: nothing goes to the network
        self.assertEqual(rep["items"][self.hid("/data/welcome/text")]["status"], "source_unavailable")
        # a link source the user supplies themselves (dead link) passes the same checks
        out, rep = hsenv.rehydrate(self.proj, fetch=FakeFetch({}), files={"materials": MATERIALS}, extractors=PDF)
        self.assertEqual(rep["items"][self.hid("/data/welcome/text")]["status"], "ok")
        # no PDF extractor on the user's machine: the PDF source is unavailable, never guessed
        out, rep = hsenv.rehydrate(self.proj, fetch=FakeFetch({URL: MATERIALS}), files={"paper": PAPER})
        self.assertEqual(rep["items"][self.hid("/data/note/text")]["status"], "source_unavailable")

    def test_image_read_item(self):
        h = self.hid("/stages/intro/content/2/value/lines/0/text")
        _, rep = hsenv.rehydrate(self.proj, fetch=FakeFetch({URL: MATERIALS}), extractors=PDF)
        self.assertEqual(rep["items"][h]["status"], "requires_reading")
        out, rep = hsenv.rehydrate(self.proj, items={h: "SKY AHEAD!"}, extractors=PDF)
        self.assertEqual(rep["items"][h]["status"], "hash_mismatch")
        self.assertTrue(set(D._get(out, self.held[h]["path"])) <= {D.PLACEHOLDER})
        out, rep = hsenv.rehydrate(self.proj, items={h: "SKY AHEAD"}, extractors=PDF)
        self.assertEqual(rep["items"][h]["status"], "ok")

    def test_rehydrated_projection_still_runs(self):
        out, _ = hsenv.rehydrate(self.proj, fetch=FakeFetch({}), extractors=PDF)
        env, problems, _ = checks.play(Protocol(out), 2, 5)
        self.assertEqual(problems, [])


# ------------------------------------------------------------------------------------------- other formats
def docx(paragraphs):
    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    body = "".join("<w:p>%s</w:p>" % "".join("<w:r><w:t xml:space=\"preserve\">%s</w:t></w:r>" % r for r in p)
                   for p in paragraphs)
    xml = '<?xml version="1.0"?><w:document xmlns:w="%s"><w:body>%s</w:body></w:document>' % (w, body)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", xml)
        z.writestr("[Content_Types].xml", "<Types/>")
    return buf.getvalue()


class TestFormats(unittest.TestCase):
    def round_trip(self, data, text, fmt):
        self.assertEqual(D.sniff(data), fmt)
        us = D.units(fmt, data)
        loc = D.make_locator(text, fmt, us)
        self.assertIsNotNone(loc, (fmt, us))
        self.assertEqual(loc["extractor"], D.EXTRACTORS[fmt])
        self.assertEqual(D.find(D.Scope(D.units(fmt, data)), loc, D.text_sha256(text)), text)
        return loc

    def test_docx(self):
        data = docx([["Pick the cloud ", "you liked best."], ["It can be ", "any cloud at all."]])
        loc = self.round_trip(data, "Pick the cloud you liked best.", "docx")
        self.assertEqual(loc["parts"][0]["units"], [0, 0])
        self.round_trip(data, "Pick the cloud you liked best.\nIt can be any cloud at all.", "docx")

    def test_html(self):
        data = (b"<!DOCTYPE html><html><head><title>t</title><script>var x='Rate the cloud';</script></head>"
                b"<body><p>Rate the <b>cloud</b>\n you see.</p><ul><li>Fluffy</li><li>Thin &amp; wispy</li></ul>"
                b"</body></html>")
        self.round_trip(data, "Rate the cloud you see.", "html")
        self.round_trip(data, "Thin & wispy", "html")

    def test_qsf(self):
        qsf = {"SurveyEntry": {}, "SurveyElements": [
            {"Element": "SQ", "PrimaryAttribute": "QID1",
             "Payload": {"QuestionID": "QID1", "QuestionText": "<div>How <i>windy</i> is it today?</div>",
                         "Choices": {"1": {"Display": "Calm"}, "2": {"Display": "Breezy"}},
                         "ChoiceOrder": [2, 1]}}]}
        data = json.dumps(qsf).encode()
        self.round_trip(data, "How windy is it today?", "qsf")
        self.assertEqual(D.units("qsf", data), ["How windy is it today?", "Breezy", "Calm"])

    def test_text_hyphen_and_quotes(self):
        self.round_trip(MATERIALS, "an overturned teacup", "text")
        self.round_trip(MATERIALS, "a sleeping “dragon”", "text")
        self.round_trip(MATERIALS, 'a sleeping "dragon"', "text")   # served straight quotes, source curly

    def test_not_in_source(self):
        self.assertIsNone(D.make_locator("A cloud nobody printed anywhere at all.", "text", D.units("text", MATERIALS)))
        # case differs: never located (the restore ops carry no letters)
        self.assertIsNone(D.make_locator("WELCOME! IN THIS SHORT SURVEY", "text", D.units("text", MATERIALS)))

    def test_random_substrings_round_trip(self):
        rng = random.Random(7)
        src = MATERIALS.decode()
        us = D.units("text", MATERIALS)
        sc = D.Scope(us)
        for _ in range(60):
            a = rng.randrange(0, len(src) - 12)
            t = src[a:a + rng.randrange(8, 60)].strip()
            if len(D.canon_only(t)) < 4:
                continue
            loc = D.make_locator(t, "text", us, scope=sc)
            self.assertIsNotNone(loc, t)
            self.assertEqual(D.find(sc, loc, D.text_sha256(t)), __import__("unicodedata").normalize("NFC", t))


# ------------------------------------------------------------------------------------------- review round 1
class TestReviewRound1(unittest.TestCase):
    """Adversarial review of 0.8.1 (invented fixtures): leaks through uncovered positions, letters in restore ops /
    literals, silent replacement of on-screen text, hosted `derived` exemption, unverified files, crafted input."""

    def proj(self, p, **kw):
        return project_t(p, TIERS, sources=SOURCES, extractors=PDF, **kw)

    def test_more_positions_are_held(self):
        p = protocol()
        r = p["stages"]["q1"]["responses"][0]
        r["columns"] = ["Thank you for watching the sky with us."]
        r["widget_params"] = {"rows": ["something else entirely"]}
        r["button"] = "an overturned teacup"
        q2 = p["stages"]["q2"]["responses"][0]
        q2["options_cite"] = q2.pop("cite")
        p["stages"]["q1"]["content"][0]["cites"] = [p["stages"]["q1"]["content"][0].pop("cite")]
        p["data"]["kinded"] = {"kind": "a sleeping \u201cdragon\u201d", "cite": cite("materials", 1)}
        proj, _ = self.proj(p)
        dump = json.dumps(proj, ensure_ascii=False)
        for t in ("Thank you for watching", "something else entirely", "overturned", "sleeping",
                  "Q1. How many"):
            self.assertNotIn(t, dump)

    def test_hosted_derived_cite_does_not_exempt(self):
        p = protocol()
        p["stages"]["q2"]["responses"][0]["options"][1]["cite"] = [cite("materials", 1),
                                                                   cite("scale", 1, "derived")]
        proj, _ = self.proj(p)
        self.assertNotIn("teacup", json.dumps(proj))

    def test_on_screen_text_containing_held_text_is_an_error(self):
        p = protocol()
        p["data"]["mix"] = {"text": "Pick something else entirely if unsure, please.", "cite": cite("scale", 1)}
        p["data"]["mix2"] = {"text": "Q1. How many clouds can you count right now? Count them.",
                             "cite": cite("scale", 1)}
        with self.assertRaisesRegex(release.ProjectionError, "cannot be withheld"):
            self.proj(p)

    def test_expression_literal_from_source_is_an_error(self):
        p = protocol()
        p["stages"]["q1"]["content"].append(
            {"id": "x", "value": {"expr": "'Thank you for watching the sky with us.' if True else ''"}})
        with self.assertRaisesRegex(release.ProjectionError, "inside expressions"):
            self.proj(p)
        p = protocol()
        p["flow"]["seq"].insert(0, {"for": "w", "in": ["something else entirely"], "do": {"stage": "intro"}})
        _, rep = self.proj(p, strict=False)
        self.assertEqual(rep["literals_in_source"], ["/flow/seq/0/in/0"])

    def test_no_letters_in_ops_or_literals(self):
        for t in ["\uff76\uff9e\uff70\uff83\uff9e\uff9d \uff21\uff22\uff23", "\u2460 \u338f \u216b caf\u00e9"]:
            c, ops = D.canon(t)
            self.assertFalse(any(ch.isalnum() for _, _, s_ in ops for ch in s_), ops)
            self.assertEqual(D.restore(c, ops), __import__("unicodedata").normalize("NFC", t))
        us = D.units("text", MATERIALS)
        # one word changed: never a literal carrying letters
        self.assertIsNone(D.make_locator("Q1. How many clouds can you spot right now?", "text", us))
        self.assertIsNotNone(D.make_locator("ﬁne \u2013 ok", "text", ["a ﬁne - ok b"]))   # ligature, en dash

    def test_file_sha_is_provenance_only(self):
        proj, _ = make()
        del proj["meta"]["sources"]["materials"]["distribution"]["sha256"]
        out, rep = hsenv.rehydrate(proj, fetch=FakeFetch({URL: MATERIALS}), extractors=PDF)
        h = next(k for k, e in proj["distribution"]["held"].items() if e["path"] == "/data/welcome/text")
        self.assertEqual(rep["items"][h]["status"], "ok")   # verified by its own text_sha256
        self.assertIsNone(rep["sources"]["materials"]["matches_recorded_sha256"])

    def test_stamped_download_rehydrates_exactly(self):
        # a publisher PDF stamped per download: other metadata, a watermark line at the top and bottom of every
        # page, and one stamp line the extractor put inside the item. Every item still verifies exactly.
        stamp = "Downloaded by Invented University on 2026-11-09. Not for redistribution."
        pages = pdf_pages(PAPER)
        stamped = ["%PDF-1.7 producer=InventedStamper/2 id=8f2c"] + [
            stamp + "\n" + pg.replace("so ﬁnish each answer", "so ﬁnish\n" + stamp + "\neach answer") + "\n" + stamp
            for pg in pages[1:]]
        data = "\f".join(stamped).encode("utf-8")
        self.assertNotEqual(D.sha256(data), PAPER_SHA)
        proj, _ = make()
        h = next(k for k, e in proj["distribution"]["held"].items() if e["path"] == "/data/note/text")
        out, rep = hsenv.rehydrate(proj, fetch=FakeFetch({URL: MATERIALS}), files={"paper": data},
                                   extractors=PDF)
        self.assertEqual(rep["items"][h]["status"], "ok")
        self.assertEqual(out["data"]["note"]["text"], protocol()["data"]["note"]["text"])
        # the same stamped file with the item's wording altered: that item fails, nothing of it is served
        bad = data.replace("changes quickly".encode(), "changes slowly".encode())
        out, rep = hsenv.rehydrate(proj, fetch=FakeFetch({URL: MATERIALS}), files={"paper": bad},
                                   extractors=PDF)
        self.assertEqual(rep["items"][h]["status"], "hash_mismatch")
        self.assertTrue(set(out["data"]["note"]["text"]) <= {D.PLACEHOLDER})

    def test_crafted_projection_never_crashes_or_overwrites(self):
        proj, _ = make()
        held = proj["distribution"]["held"]
        hs = sorted(held, key=lambda k: int(k[1:]))
        held[hs[0]]["path"] = "/meta/sources/materials/distribution/url"   # not a placeholder: refused
        held[hs[1]]["path"] = "/nowhere/0"
        held[hs[2]]["locator"]["parts"] = [{"units": [0, 10 ** 9], "canon_len": 5, "canon_sha256": "x"}]
        held[hs[3]]["locator"]["parts"] = ["junk"]
        held[hs[4]]["locator"]["restore"] = [[0]]
        held["hx"] = ["not", "a", "dict"]
        out, rep = hsenv.rehydrate(proj, fetch=FakeFetch({URL: MATERIALS}), files={"paper": PAPER}, extractors=PDF)
        self.assertEqual(out["meta"]["sources"]["materials"]["distribution"]["url"], URL)
        for h in hs[:5] + ["hx"]:
            self.assertNotEqual(rep["items"][h]["status"], "ok", h)
        out, rep = hsenv.rehydrate({"id": "x", "distribution": {"held": []}})
        self.assertTrue(rep["complete"])


# -------------------------------------------------------------------------------------------- maintainer decisions
def tiny_pdf(pages):
    """A minimal PDF (Helvetica text, one line per string) written by hand: invented content."""
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", None, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for lines in pages:
        body = "BT /F1 12 Tf 72 720 Td 14 TL " + " ".join("(%s) '" % ln for ln in lines) + " ET"
        objs.append("<< /Length %d >>\nstream\n%s\nendstream" % (len(body), body))
        objs.append("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents %d 0 R "
                    "/Resources << /Font << /F1 3 0 R >> >> >>" % len(objs))
        kids.append(len(objs))
    objs[1] = "<< /Type /Pages /Kids [%s] /Count %d >>" % (" ".join("%d 0 R" % k for k in kids), len(kids))
    out, offs = "%PDF-1.4\n", []
    for i, o in enumerate(objs):
        offs.append(len(out))
        out += "%d 0 obj\n%s\nendobj\n" % (i + 1, o)
    x = len(out)
    out += "xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + "".join("%010d 00000 n \n" % o for o in offs)
    out += "trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, x)
    return out.encode("latin-1")


try:
    PDFIUM = D.pdfium_extractor()
except ImportError:
    PDFIUM = None


class TestDecisions(unittest.TestCase):
    def test_release_requires_the_pinned_pdf_extractor(self):
        with self.assertRaisesRegex(release.ProjectionError, "extractor the app ships"):
            release.project(protocol(), TIERS, sources=SOURCES, extractors=PDF)

    @unittest.skipIf(PDFIUM is None, "pypdfium2 not installed (optional)")
    def test_pypdfium2_round_trip(self):
        pdf = tiny_pdf([["Cover page of the invented note."],
                        ["Please look at the sky for one", "minute before you answer."]])
        p = protocol()
        p["data"]["note"]["text"] = "Please look at the sky for one minute before you answer."
        tiers = dict(TIERS, paper={"tier": "user", "sha256": D.sha256(pdf)})
        proj, _ = release.project(p, tiers, sources={"materials": MATERIALS, "paper": pdf, "scale": SCALE},
                                  extractors={"pdf": PDFIUM})   # strict, pinned family
        h = next(k for k, e in proj["distribution"]["held"].items() if e["path"] == "/data/note/text")
        loc = proj["distribution"]["held"][h]["locator"]
        self.assertTrue(loc["extractor"].startswith("pypdfium2/") and "+pdfium/" in loc["extractor"])
        self.assertEqual(loc["pages"], [2, 2])
        items = {next(k for k, e in proj["distribution"]["held"].items()
                      if e["locator"]["format"] == "image_reading"): "SKY AHEAD"}
        out, rep = hsenv.rehydrate(proj, fetch=FakeFetch({URL: MATERIALS}), files={"paper": pdf}, items=items,
                                   extractors={"pdf": PDFIUM})
        self.assertEqual(rep["items"][h]["status"], "ok")
        self.assertEqual(out["data"]["note"]["text"], p["data"]["note"]["text"])
        out, rep = hsenv.rehydrate(proj, files={"paper": pdf}, extractors={"pdf": pdf_pages})
        self.assertEqual(rep["items"][h]["status"], "source_unavailable")

    def region_protocol(self):
        p = protocol()
        img = p["stages"]["intro"]["content"][2]
        img["cite"]["region"] = {"box": [0.1, 0.2, 0.9, 0.5], "dpi": 200}
        img["value"]["lines"][0]["cite"]["region"] = {"box": [0.1, 0.2, 0.9, 0.3], "dpi": 200}
        p["data"]["sign"] = {"text": "CLOUDS ONLY", "cite": cite("screens", 2, read="image",
                                                                region={"box": [0, 0, 0.5, 0.25]})}
        p["stages"]["q2"]["responses"][0]["options"][2] = {"code": "c", "label": "MAYBE RAIN", "cite": cite(
            "screens", 2, read="image", region={"box": [0, 0.5, 0.5, 0.75]})}
        p["data"]["noregion"] = {"text": "NO BOX HERE", "cite": cite("screens", 3, read="image")}
        p["stages"]["intro"]["content"].append({"id": "sg", "value": {"expr": "data['sign']"}})
        return p

    def test_region_items(self):
        # a screenshot PDF whose pages also carry a little text layer (a caption each): those texts verify the pages
        screens = b"%PDF-1.4 Screen one: look at the sky now\fScreen two: watch the clouds now\f"
        tiers = dict(TIERS, screens={"tier": "user"})
        p = self.region_protocol()
        p["data"]["cap1"] = {"text": "Screen one: look at the sky now", "cite": cite("screens", 1)}
        p["data"]["cap2"] = {"text": "Screen two: watch the clouds now", "cite": cite("screens", 2)}
        proj, rep = project_t(p, tiers, sources=dict(SOURCES, screens=screens), extractors=PDF)
        held = proj["distribution"]["held"]
        by = {e["path"]: k for k, e in held.items()}
        img = by["/stages/intro/content/2/value"]
        self.assertEqual(held[img]["locator"], {"format": "region", "source": "screens", "page": 1,
                                                "box": [0.1, 0.2, 0.9, 0.5], "dpi": 200})
        self.assertEqual(held[by["/data/noregion/text"]]["locator"]["format"], "image_reading")
        self.assertIn(by["/data/sign/text"], rep["regions"])
        self.assertNotIn("CLOUDS ONLY", json.dumps(proj))
        # source not supplied: nothing rendered
        out, r = hsenv.rehydrate(proj, fetch=FakeFetch({URL: MATERIALS}), files={"paper": PAPER}, extractors=PDF)
        self.assertEqual(r["items"][img]["status"], "needs_user_file")
        self.assertEqual(r["renders"], {})
        # a wrong file: none of its pages verifies, so no region of it is rendered
        out, r = hsenv.rehydrate(proj, fetch=FakeFetch({URL: MATERIALS}), extractors=PDF,
                                 files={"paper": PAPER, "screens": b"%PDF-1.4 another file\fentirely\f"})
        self.assertEqual(r["items"][img]["status"], "needs_user_file")
        self.assertIn("not trusted", r["items"][img]["detail"])
        self.assertEqual(r["renders"], {})
        # page 2's caption tampered: page 1 still renders, page 2 does not
        out, r = hsenv.rehydrate(proj, fetch=FakeFetch({URL: MATERIALS}), extractors=PDF,
                                 files={"paper": PAPER, "screens": screens.replace(b"watch", b"count")})
        self.assertEqual(r["items"][img]["status"], "ok_image")
        self.assertEqual(r["items"][by["/data/sign/text"]]["status"], "needs_user_file")
        out, r = hsenv.rehydrate(proj, fetch=FakeFetch({URL: MATERIALS}),
                                 files={"paper": PAPER, "screens": screens}, extractors=PDF)
        self.assertEqual(r["items"][img]["status"], "ok_image")
        self.assertEqual(r["renders"][img]["box"], [0.1, 0.2, 0.9, 0.5])
        self.assertEqual(r["renders"][img]["src"], "assets/sky.png")
        line = by["/stages/intro/content/2/value/lines/0/text"]
        self.assertEqual(r["items"][line]["status"], "ok_image")
        sign = by["/data/sign/text"]
        self.assertEqual(r["items"][sign]["status"], "ok_image")
        self.assertEqual(out["data"]["sign"]["src"], "regions/%s.png" % sign)
        self.assertNotIn("text", out["data"]["sign"])
        self.assertEqual(r["renders"][sign]["page"], 2)
        self.assertEqual(r["renders"][sign]["src"], "regions/%s.png" % sign)
        opt = by["/stages/q2/responses/0/options/2/label"]
        self.assertEqual(r["items"][opt]["status"], "requires_reading")   # an option label cannot be an image
        self.assertEqual(r["items"][by["/data/noregion/text"]]["status"], "requires_reading")
        # the rehydrated protocol serves the rendered region as an image item
        env = Env(Protocol(out))
        st = env.open(env.design(n=1, seed=0)[0]).reset()
        kinds = [(it["type"], "src" in it) for it in st["screen"]["items"]]
        self.assertIn(("image", True), kinds)
        # a hash-checked reading still wins and is served as text
        out, r = hsenv.rehydrate(proj, files={"screens": screens}, items={sign: "CLOUDS ONLY"}, extractors=PDF)
        self.assertEqual((r["items"][sign]["status"], out["data"]["sign"]["text"]), ("ok", "CLOUDS ONLY"))

    def test_region_validation(self):
        for bad in ({"box": [0.5, 0, 0.4, 1]}, {"box": [0, 0, 1.2, 1]}, {"box": [0, 0, 1]},
                    {"box": [0, 0, 1, 1], "dpi": 20}, {"box": [0, 0, 1, 1], "page": 0}, "box"):
            self.assertIsNone(D.region_locator("s", 1, bad), bad)
        self.assertEqual(D.region_locator("s", 4, {"box": [0, 0, 1, 1]})["dpi"], 150)

    def test_share_alike_is_not_hosted(self):
        with self.assertRaisesRegex(release.ProjectionError, "CC-BY-SA"):
            project_t(protocol(), dict(TIERS, scale={"tier": "hosted", "licence": "CC-BY-SA-4.0",
                                                     "attribution": "x"}), sources=SOURCES, extractors=PDF)
        proj, _ = project_t(protocol(), dict(TIERS, scale={"tier": "link", "licence": "CC-BY-SA-4.0",
                                                           "url": "https://example.org/scale.txt",
                                                           "sha256": D.sha256(b"Clouds:\nHow much do you like "
                                                                              b"clouds?\nNot at all\nSome\n"
                                                                              b"Very much\n")}),
                            sources=dict(SOURCES, scale=b"Clouds:\nHow much do you like clouds?\nNot at all\n"
                                                        b"Some\nVery much\n"), extractors=PDF)
        self.assertNotIn("Very much", json.dumps(proj))

    def test_coding_cases_tier_with_their_source(self):
        p = protocol()
        p["analysis"]["coding"] = {"shape": {
            "apply": "text", "cite": cite("materials", 1, "reported"),
            "cases": [{"text": "a sleeping \u201cdragon\u201d", "code": "a"},          # quoted from the source
                      {"text": "a cloud like my grandmother's hat", "code": "c"},  # invented: ours
                      {"text": "an overturned teacup", "code": "b", "cite": cite("materials", 1)}]}}
        proj, _ = project_t(p, TIERS, sources=SOURCES, extractors=PDF)
        cases = proj["analysis"]["coding"]["shape"]["cases"]
        self.assertEqual(set(cases[0]["text"]), {D.PLACEHOLDER})
        self.assertEqual(cases[1]["text"], "a cloud like my grandmother's hat")
        self.assertEqual(set(cases[2]["text"]), {D.PLACEHOLDER})
        out, _ = hsenv.rehydrate(proj, fetch=FakeFetch({URL: MATERIALS}), extractors=PDF)
        self.assertEqual([c["text"] for c in out["analysis"]["coding"]["shape"]["cases"]],
                         [c["text"] for c in p["analysis"]["coding"]["shape"]["cases"]])


# ------------------------------------------------------------------------------------------- review round 2
INV = ("Invented Mood Inventory\n"
       "I often feel restless at night.\n"
       "My neighbours rarely greet me.\n"
       "Please answer every statement honestly and quickly before moving to the next page of the booklet.\n"
       "Rate each statement from one to five.\n").encode()
INV_T = {"inv": {"tier": "link", "url": "https://example.org/inv.txt", "sha256": D.sha256(INV)}}
INV_LEAKS = ["restless at night", "rarely greet", "honestly and quickly", "one to five"]


def inv_cite(label="verbatim", **k):
    return dict({"label": label, "source": "inv"}, **k)


def inv_base():
    return {"schema_version": "1", "id": "fx", "meta": {"citation": "invented", "sources": {"inv": {"file": "inv.txt"}}},
            "data": {}, "stages": {"s": {"content": [], "responses": [], "presentation": {"advance": "self"}}},
            "flow": {"seq": [{"stage": "s"}]}, "units": {}, "exclusions": [],
            "analysis": {"targets": [], "effects": [], "unsupported": []}}


class TestReviewRound2(unittest.TestCase):
    """Independent review 2 (probes p1-p6, invented text): every case either holds / withholds the text or refuses."""

    def outcome(self, p, src=INV, tiers=INV_T):
        try:
            proj, rep = project_t(p, tiers, sources={"inv": src})
        except release.ProjectionError:
            return "refused"
        dump = json.dumps(proj, ensure_ascii=False)
        return [t for t in INV_LEAKS if t in dump]

    def test_no_leak_in_any_probe(self):
        cases = []
        for text in ("1. I often feel restless at night.", "I OFTEN FEEL RESTLESS AT NIGHT.",
                     "i often feel restless at night"):
            p = inv_base()
            p["data"]["q1"] = {"text": text, "cite": inv_cite("derived")}
            cases.append(("derived " + text, p))
        r = {"id": "r", "kind": "text", "prompt": "x", "min_chars": 3, "cite": inv_cite(),
             "min_chars_message": "Please answer every statement honestly and quickly"}
        p = inv_base(); p["stages"]["s"]["responses"] = [r]; cases.append(("min_chars_message", p))
        p = inv_base(); p["stages"]["s"]["responses"] = [{"id": "r", "kind": "text", "prompt": "x", "cite": inv_cite(),
            "validate": {"contains": "restless", "message_label": "My neighbours rarely greet me.",
                         "equals": "My neighbours rarely greet me."}}]
        cases.append(("validate", p))
        p = inv_base(); p["stages"]["s"]["content"] = [{"id": "i", "value": "x", "text": "My neighbours rarely greet me.",
                                                         "cite": inv_cite()}]
        cases.append(("content text beside value", p))
        p = inv_base(); p["stages"]["s"]["presentation"]["dialog"] = "My neighbours rarely greet me."
        p["stages"]["s"]["presentation_cite"] = inv_cite(); cases.append(("presentation.dialog", p))
        for where in ("arm", "condition", "omitted", "conflicts", "flow", "coding", "keyed", "run_excluded"):
            p = inv_base()
            q = "My neighbours rarely greet me."
            if where == "arm":
                p["arms"] = [{"id": "a", "label": q, "n_paper": 3}]
            elif where == "condition":
                p["conditions"] = [{"id": "c", "factor": "f", "levels": [q]}]
            elif where == "omitted":
                p["omitted"] = [{"what": q, "why": "x"}]
            elif where == "conflicts":
                p["meta"]["conflicts"] = ["the item reads " + q]
            elif where == "flow":
                p["flow"] = {"seq": [{"stage": "s", "doc": q}]}
            elif where == "coding":
                p["coding"] = {"c": {"rule": "x", "categories": {"a": q}, "cite": inv_cite("reported")}}
            elif where == "keyed":
                p["keyed"] = {"answers": {"s.r": q}}
            else:
                p["run_excluded"] = [{"id": "x", "what": q}]
            cases.append((where, p))
        for name, p in cases:
            self.assertIn(self.outcome(p), ("refused", []), name)

    def test_data_struct_keys_and_notes_are_material(self):
        src = "Inv\nThank you for your time today.\nYour answers are kept private.\n".encode()
        t = {"inv": {"tier": "link", "url": "https://example.org/inv.txt", "sha256": D.sha256(src)}}
        c = inv_cite()
        for data in ({"msg": {"start": "Your answers are kept private.", "end": "Thank you for your time today.",
                              "cite": c}},
                     {"opts": [{"code": "Thank you for your time today.", "label": "Your answers are kept private."}],
                      "opts_cite": c},
                     {"q": {"text": "Your answers are kept private.", "q_note": "Thank you for your time today.",
                            "cite": c}}):
            p = inv_base()
            p["data"] = data
            proj, _ = project_t(p, t, sources={"inv": src})
            self.assertNotIn("Thank you for your time", json.dumps(proj))
        # an id that is not in the source stays an id
        p = inv_base()
        p["data"] = {"q": {"id": "q_rest", "text": "I often feel restless at night.", "cite": c}}
        proj, _ = project_t(p, INV_T, sources={"inv": INV})
        self.assertEqual(proj["data"]["q"]["id"], "q_rest")

    def test_cjk(self):
        long_cjk = ("参加者は次の文章を読んでから質問に答えてください。この調査は約十分で終わりますので最後までよろしく"
                    "お願いします。回答は匿名で処理されます。")
        src = ("調査票\n" + long_cjk + "\n").encode()
        t = {"inv": {"tier": "link", "url": "https://example.org/inv.txt", "sha256": D.sha256(src)}}
        p = inv_base(); p["data"]["x"] = {"text": long_cjk}
        with self.assertRaisesRegex(release.ProjectionError, "without a cite"):
            project_t(p, t, sources={"inv": src})
        p = inv_base(); p["data"]["x"] = {"text": long_cjk, "cite": inv_cite()}
        p["meta"]["conflicts"] = ["原文: " + long_cjk[:30]]
        proj, _ = project_t(p, t, sources={"inv": src})
        self.assertNotIn(long_cjk[5:25], json.dumps(proj, ensure_ascii=False))

    def test_held_fragment_in_operator_text(self):
        L = "Please answer every statement honestly and quickly before moving to the next page of the booklet."
        p = inv_base()
        p["meta"]["conflicts"] = ["the paper prints 'answer every statement honestly and quickly before' here"]
        p["data"]["x"] = {"text": L, "cite": inv_cite()}
        proj, _ = project_t(p, INV_T, sources={"inv": INV})
        self.assertTrue(proj["meta"]["conflicts"][0].startswith(D.WITHHELD))

    def test_distributable_round2(self):
        shots = b"%PDF-1.4 invented shots"
        p = inv_base()
        p["meta"]["sources"]["shots"] = {"file": "s.pdf"}
        p["data"]["q"] = {"text": "My neighbours rarely greet me.", "cite": inv_cite()}
        p["stages"]["s"]["content"] = [{"id": "img", "value": {"src": "./artifacts/shot1.png", "sha256": "cd" * 32},
                                        "cite": inv_cite(source="shots", page=1)}]
        t = dict(INV_T, shots={"tier": "user", "sha256": D.sha256(shots)})
        proj, _ = project_t(p, t, sources={"inv": INV})
        for n in ("review/checks-latest.json", "program.json", "package/materials.json", "artifacts/shot1.png",
                  "artifacts/./shot1.png", "artifacts/Shot1.png", "sourcetext/INV.txt", "sources/open/inv.txt"):
            self.assertFalse(release.distributable(n, proj), n)
        self.assertFalse(release.distributable("effects.json", proj))   # not scanned: refused
        self.assertFalse(release.distributable("effects.json", proj, content=b'{"effects": [{"id": "e1"}]}',
                                               sources={"inv": INV}))   # every non-hosted source must be scanned
        self.assertTrue(release.distributable("effects.json", proj, content=b'{"effects": [{"id": "e1"}]}',
                                              sources={"inv": INV, "shots": shots}, extractors=PDF))
        self.assertFalse(release.distributable("effects.json", proj, sources={"inv": INV},
                                               content=json.dumps({"note": "item: My neighbours rarely greet me."})))

    def test_rehydrate_ids_srcs_and_line_order(self):
        p = inv_base()
        p["meta"]["sources"]["shots"] = {"file": "s.pdf"}
        p["stages"]["s"]["content"] = [{"id": "img", "value": {
            "src": "artifacts/shot1.png", "sha256": "cd" * 32,
            "lines": [{"text": "STOP AND LOOK", "cite": inv_cite(source="shots", page=1, read="image",
                                                                  region={"box": [0, 0, .5, .5]})}]},
            "cite": inv_cite(source="shots", page=1)}]
        shots = b"PDFBYTES"
        t = dict(INV_T, shots={"tier": "user", "sha256": D.sha256(shots)})
        proj, _ = project_t(p, t, sources={"inv": INV})
        held = proj["distribution"]["held"]
        line = next(k for k, v in held.items() if "/lines/" in v["path"])
        # the picture has no region and no file: its line is not replaced by a rendering
        out, r = hsenv.rehydrate(proj, files={"shots": shots})
        self.assertEqual(r["items"][line]["status"], "requires_reading")
        self.assertEqual(r["renders"], {})
        self.assertEqual(len(out["stages"]["s"]["content"][0]["value"]["lines"]), 1)
        # a crafted held id or image src is refused
        cp = copy.deepcopy(proj)
        cp["distribution"]["held"]["../../tmp/evil"] = cp["distribution"]["held"].pop(line)
        _, r = hsenv.rehydrate(cp, files={"shots": shots})
        self.assertEqual(r["renders"], {})
        self.assertEqual(r["items"]["../../tmp/evil"]["status"], "hash_mismatch")
        cp = copy.deepcopy(proj)
        cp["stages"]["s"]["content"][0]["value"]["src"] = "../../../.ssh/authorized_keys"
        img = next(k for k, v in cp["distribution"]["held"].items() if v["kind"] == "image")
        cp["distribution"]["held"][img]["sha256"] = D.sha256(b"ATTACKER")
        _, r = hsenv.rehydrate(cp, items={img: b"ATTACKER"})
        self.assertEqual(r["assets"], {})
        # a source key named like a held id is a source, never an item
        _, r = hsenv.rehydrate(proj, files={line: b"x"}, items={})
        self.assertEqual(r["items"][line]["status"], "requires_reading")

    def test_region_page_checked_and_kept(self):
        p = protocol()
        p["data"]["sign"] = {"text": "CLOUDS ONLY", "cite": cite("paper", 9, read="image",
                                                                region={"box": [0, 0, 0.5, 0.25]})}
        with self.assertRaisesRegex(release.ProjectionError, "the source has 3 pages"):
            project_t(p, TIERS, sources=SOURCES, extractors=PDF)
        p["data"]["sign"]["cite"]["page"] = 2
        proj, _ = project_t(p, TIERS, sources=SOURCES, extractors=PDF)
        self.assertEqual(proj["data"]["sign"]["cite"]["region"], {"box": [0, 0, 0.5, 0.25]})

    def test_hosted_cite_must_be_in_the_hosted_file(self):
        scale = b"Clouds:\nHow much do you like clouds?\nNot at all\nSome\nVery much\n"
        t = dict(TIERS)
        proj, _ = project_t(protocol(), t, sources=dict(SOURCES, scale=scale), extractors=PDF)
        self.assertIn("Very much", json.dumps(proj))
        with self.assertRaisesRegex(release.ProjectionError, "not in the supplied hosted file"):
            project_t(protocol(), t, sources=dict(SOURCES, scale=scale.replace(b"Very much", b"A lot")),
                      extractors=PDF)

    def test_licence_spellings(self):
        for lic in ("CC BY 4.0", "CC-BY-4.0", "cc-by", "CC BY 4.0 International", "CC0 1.0 Universal",
                    "Public Domain", "PDM-1.0", "\uff23\uff23 \uff22\uff39", "CC BY\xa04.0"):
            self.assertTrue(release.hosted_licence_ok(lic), lic)
        for lic in ("CC BY 9", "CC BY \u0664", "CC-BY-3.0-IGO", "CC BY-SA 4.0", "CC BY-NC", "CC BY-ND", "none", ""):
            self.assertFalse(release.hosted_licence_ok(lic), lic)


# ------------------------------------------------------------------------------------------- review round 3
INV3 = INV + "Strongly agree\n私は夜によく落ち着かない気持ちになる。\n".encode()
INV3_T = {"inv": {"tier": "link", "url": "https://example.org/inv.txt", "sha256": D.sha256(INV3)}}
LONG = "Please answer every statement honestly and quickly before moving to the next page of the booklet."


class TestReviewRound3(unittest.TestCase):
    """Independent review round 2 of the distribution layer (probes q1-q5, invented text)."""

    def outcome(self, p, tiers=INV3_T, sources=None):
        try:
            proj, rep = project_t(p, tiers, sources=sources or {"inv": INV3})
        except release.ProjectionError as e:
            return "refused"
        body = json.dumps({k: v for k, v in proj.items() if k != "distribution"}, ensure_ascii=False)
        folded = release._fold(body)
        return [t for t in ("restless at night", "rarely greet", "honestly and quickly", "Strongly agree", "落ち着かない")
                if t in body or release._fold(t) in folded]

    def test_probes(self):
        cases = []
        for k in ("start", "id"):
            p = inv_base(); p["data"]["msg"] = {k: LONG, "end": "x"}; cases.append(("uncited data." + k, p))
        p = inv_base(); p["data"]["opts"] = [{"code": LONG, "label": "x"}]; cases.append(("uncited code", p))
        p = inv_base(); p["data"]["q"] = {"text": "I often feel restless at night.", "expr": "1", "cite": inv_cite()}
        cases.append(("data dict with expr", p))
        p = inv_base(); p["data"]["q"] = {"label": "Strongly agree", "expr": "1", "cite": inv_cite()}
        cases.append(("short in dict with expr", p))
        p = inv_base(); p["stages"]["s"]["responses"] = [
            {"id": "r1", "kind": "choice", "prompt": "a", "options": [{"code": 1, "label": "Strongly agree"}],
             "options_cite": inv_cite()},
            {"id": "r2", "kind": "choice", "prompt": "b", "options": [{"code": 1, "label": "Strongly agree"}]}]
        cases.append(("short held repeated uncited", p))
        p = inv_base(); p["stages"]["s"]["content"] = [{"id": "i", "value": "x", "caption": "Strongly agree",
                                                         "cite": inv_cite()}]
        cases.append(("item caption", p))
        p = inv_base(); p["stages"]["s"]["responses"] = [{"id": "r", "kind": "text", "prompt": "x",
                                                           "placeholder": "Strongly agree", "cite": inv_cite()}]
        cases.append(("response placeholder", p))
        p = inv_base(); p["omitted"] = [{"what": "原文「私は夜によく落ち着かない気持ちになる。」", "why": "dropped"}]
        cases.append(("CJK operator quote", p))
        for swaps in ("reads I \u043eften feel restl\u0435ss at night.", "reads I of\u200bten feel rest\u00adless at night."):
            p = inv_base(); p["data"]["q"] = {"text": "I often feel restless at night.", "cite": inv_cite()}
            p["meta"]["conflicts"] = [swaps]; cases.append(("homoglyph / zero-width copy", p))
        p = inv_base(); p["omitted"] = [{"what": "Please answer every statement honestly and quickly b\u0435fore moving "
                                                 "to the n\u0435xt page of the bookl\u0435t.", "why": "x"}]
        cases.append(("homoglyph quote of the source", p))
        for name, p in cases:
            self.assertIn(self.outcome(p), ("refused", []), name)
        # a quote in an undocumented distribution key never ships
        p = inv_base(); p["meta"]["sources"]["inv"]["distribution"] = dict(INV3_T["inv"], note=LONG)
        proj, _ = project_t(p, None, sources={"inv": INV3})
        self.assertNotIn("honestly and quickly", json.dumps(proj))

    def test_hosted_file_required_and_nfc(self):
        p = inv_base(); p["meta"]["sources"]["paper"] = {"file": "p.pdf"}
        p["data"]["q"] = {"text": "Strongly agree", "cite": {"label": "verbatim", "source": "paper"}}
        tiers = dict(INV3_T, paper={"tier": "hosted", "licence": "CC-BY-4.0", "attribution": "x"})
        with self.assertRaisesRegex(release.ProjectionError, "supply the hosted file"):
            project_t(p, tiers, sources={"inv": INV3})
        nfd = __import__("unicodedata").normalize("NFD", "Caf\u00e9 lists: I often feel restless at night.")
        src = ("Header\n" + nfd + "\n").encode()
        p = inv_base(); p["stages"]["s"]["content"] = [{"id": "i", "value": {"text": nfd}, "cite": inv_cite()}]
        with self.assertRaisesRegex(release.ProjectionError, "not NFC"):
            project_t(p, {"inv": {"tier": "link", "url": "https://e.org/x", "sha256": D.sha256(src)}},
                      sources={"inv": src})

    def test_sourcetext_names_exact(self):
        H = {"tier": "hosted", "licence": "CC-BY-4.0", "attribution": "A. Author"}
        for hk, lk in (("paper", "paper.si"), ("si", "SI"), ("SI", "si")):
            p = inv_base(); p["meta"]["sources"] = {hk: {"file": "x"}, lk: {"file": "y"}}
            p["data"]["q"] = {"text": "I often feel restless at night.", "cite": {"label": "verbatim", "source": lk}}
            proj, _ = project_t(p, {hk: H, lk: dict(INV3_T["inv"])}, sources={lk: INV3, hk: b"unrelated hosted"})
            self.assertFalse(release.distributable("sourcetext/%s.txt" % lk, proj))
            self.assertFalse(release.distributable("sourcetext/%s#second.txt" % lk, proj))
            self.assertTrue(release.distributable("sourcetext/%s.txt" % hk, proj, content=b"unrelated hosted",
                                                  sources={lk: INV3, hk: b"unrelated hosted"}))
        for n in ("variants/v1.json", "study.json", "capabilities.json", "sources/SOURCE.json"):
            self.assertFalse(release.distributable(n, proj), n)

    def test_assets_and_renders_keyed_by_held_id(self):
        p = inv_base(); p["meta"]["sources"]["shots"] = {"file": "s"}
        p["stages"]["s"]["content"] = [{"id": "img", "value": {"src": "artifacts/a.png", "sha256": D.sha256(b"IMG")},
                                        "cite": {"label": "verbatim", "source": "shots"}}]
        proj, _ = project_t(p, dict(INV3_T, shots={"tier": "user", "sha256": "ab" * 32}), sources={"inv": INV3})
        cp = copy.deepcopy(proj)
        cp["stages"]["s"]["content"][0]["value"]["src"] = "https://x.org/../../../../etc/passwd"
        _, r = hsenv.rehydrate(cp, items={"h1": b"IMG"})
        self.assertEqual(list(r["assets"]), ["h1"])
        self.assertEqual(r["items"]["h1"]["src"], "https://x.org/../../../../etc/passwd")

    def test_find_cost_capped(self):
        sc = D.Scope(["x" * 30000] * 8)
        loc = {"parts": [{"units": [0, 7], "canon_len": 50000, "canon_sha256": "0" * 64}], "restore": []}
        self.assertIsNone(D.find(sc, loc, "0" * 64))

    def test_lines_only_inside_an_image(self):
        doc = {"data": {"x": {"lines": ["\u2591\u2591"]}}, "stages": {}}
        self.assertIsNone(D._image_position(doc, "/data/x/lines/0"))
        doc["data"]["x"]["src"] = "a.png"
        self.assertEqual(D._image_position(doc, "/data/x/lines/0")[0], "line")

    def test_quote_scan_unchecked_reported(self):
        _, rep = project_t(protocol(), TIERS, sources=SOURCES, extractors=PDF)
        self.assertEqual(rep["quote_scan_unchecked"], ["screens"])


# ------------------------------------------------------------------------------------------- review round 4
def r1_pdf(pages):
    return ("%PDF-1.4\f" + "\f".join(pages)).encode()


R1_STORY = "Method. Each participant first read the cover story about the lighthouse keeper."
R1_CAP = "Figure 2. The invented stimulus shown on every trial of the main task."
R1_BUILDER = r1_pdf([R1_STORY + "\nfiller text one", "header\n" + R1_CAP + "\nStrongly agree\nbody text"])


def r1_extract(data):
    return data.decode().split("\f")[1:]


r1_extract.name = "pypdfium2/fake+pdfium/1"


class TestReviewRound4(unittest.TestCase):
    """Distribution review round 3 (probes r1-r3b, invented text): regions follow the page their anchors matched,
    anchors need >= 16 verified characters and no failed text on the page, dict keys are scanned."""

    def r1_protocol(self, cap=R1_CAP):
        p = inv_base()
        p["meta"]["sources"] = {"paper": {"file": "p.pdf"}}
        c = p["stages"]["s"]["content"]
        c.append({"id": "story", "value": R1_STORY, "cite": {"label": "verbatim", "source": "paper", "page": 1}})
        if cap:
            c.append({"id": "cap", "value": cap, "cite": {"label": "verbatim", "source": "paper", "page": 2}})
        c.append({"id": "pic", "value": {"src": "artifacts/fig2.png", "sha256": "ab" * 32,
                                         "region": {"box": [0.1, 0.2, 0.9, 0.6]}},
                  "cite": {"label": "verbatim", "source": "paper", "page": 2}})
        return p

    def go(self, p, user):
        proj, _ = release.project(p, {"paper": {"tier": "user"}}, sources={"paper": R1_BUILDER},
                                  extractors={"pdf": r1_extract})
        out, r = hsenv.rehydrate(proj, files={"paper": user}, extractors={"pdf": r1_extract})
        pic = next(k for k, e in proj["distribution"]["held"].items() if e["kind"] == "image")
        return r, pic

    def test_region_follows_the_matched_page(self):
        r, pic = self.go(self.r1_protocol(), r1_pdf(["Cover: terms of use. Downloaded 2026.",
                                                       R1_STORY + "\nfiller text one",
                                                       "header\n" + R1_CAP + "\nStrongly agree\nbody text"]))
        self.assertEqual(r["items"][pic]["status"], "ok_image")
        self.assertEqual((r["renders"][pic]["page"], r["renders"][pic]["built_page"]), (3, 2))
        # another edition: the caption is on page 3 but its page reads differently around it (reflowed): refused
        r, pic = self.go(self.r1_protocol(), r1_pdf([R1_STORY + "\nfiller", "Unrelated page of another edition.",
                                                       R1_CAP + "\nnew figure"]))
        self.assertEqual(r["items"][pic]["status"], "needs_user_file")
        self.assertEqual(r["renders"], {})

    def test_short_or_failed_anchor_blocks_the_render(self):
        r, pic = self.go(self.r1_protocol(cap="Strongly agree"),
                         r1_pdf([R1_STORY, "Discussion. People said Strongly agree most often when asked."]))
        self.assertEqual(r["items"][pic]["status"], "needs_user_file")
        self.assertIn("shorter than 16", r["items"][pic]["detail"])
        p = self.r1_protocol()
        p["stages"]["s"]["content"].insert(1, {"id": "lab", "value": "Strongly agree",
                                               "cite": {"label": "verbatim", "source": "paper", "page": 2}})
        r, pic = self.go(p, r1_pdf([R1_STORY, "header\n" + R1_CAP + "\nStrongly disagree\nbody text"]))
        self.assertEqual(r["items"][pic]["status"], "needs_user_file")   # a text on that page failed
        self.assertIn("did not verify", r["items"][pic]["detail"])

    def test_dict_keys_and_structural_values(self):
        for mut in (lambda p: p["data"].__setitem__("fb", {LONG: 1}),
                    lambda p: p["meta"].__setitem__("lookup", {LONG: 1}),
                    lambda p: p["data"].__setitem__("fb", {"Rate each statement from one to five.": "ok"}),
                    lambda p: p["analysis"].__setitem__("effects", [{"id": LONG}]),
                    lambda p: p["stages"]["s"].__setitem__("responses", [{"id": "r", "kind": "text", "prompt": "x",
                                                                          "widget": {"hint": LONG}}])):
            p = inv_base()
            mut(p)
            with self.assertRaises(release.ProjectionError):
                project_t(p, INV3_T, sources={"inv": INV3})
        for mut in (lambda p: p["analysis"].__setitem__("effects", [{"kind": {"why": LONG}}]),
                    lambda p: p["meta"].__setitem__("format", {"note2": LONG})):
            p = inv_base()
            mut(p)
            proj, _ = project_t(p, INV3_T, sources={"inv": INV3})
            self.assertNotIn("honestly and quickly", json.dumps(proj))

    def test_stamp_retry_is_bounded_on_a_wrong_file(self):
        import time
        lines = ["Line %02d of an invented page with some words to make it a realistic length here." % i
                 for i in range(70)]
        page = "\n".join(lines)
        b = r1_pdf([page] * 5)
        p = inv_base()
        p["meta"]["sources"] = {"paper": {"file": "p"}}
        p["data"]["items"] = [{"text": ln, "cite": {"label": "verbatim", "source": "paper", "page": 3}}
                              for ln in lines[:5]]
        proj, _ = release.project(p, {"paper": {"tier": "user"}}, sources={"paper": b},
                                  extractors={"pdf": r1_extract})
        wrong = r1_pdf([page.replace("words", "wordz")] * 5)
        t = time.time()
        _, r = hsenv.rehydrate(proj, files={"paper": wrong}, extractors={"pdf": r1_extract})
        self.assertLess(time.time() - t, 5)
        self.assertEqual(r["counts"]["hash_mismatch"], 5)


# ------------------------------------------------------------------------------------------- review round 5
class TestReviewRound5(unittest.TestCase):
    """Distribution review round 4 (probes a1-a3, invented text): a repeated text cannot anchor a page; distinct
    anchor texts count once; scanned JSON compared with held hashes; bibliographic fields are not quotes."""

    def build(self, p, builder):
        return release.project(p, {"paper": {"tier": "user"}}, sources={"paper": builder},
                               extractors={"pdf": r1_extract})

    def rehy(self, proj, user):
        return hsenv.rehydrate(proj, files={"paper": user}, extractors={"pdf": r1_extract})[1]

    def stimulus_protocol(self, q, pages):
        p = inv_base()
        p["meta"]["sources"] = {"paper": {"file": "p.pdf"}}
        c = p["stages"]["s"]["content"]
        for i in pages:
            c.append({"id": "q%d" % i, "value": q, "cite": {"label": "verbatim", "source": "paper", "page": i}})
            c.append({"id": "f%d" % i, "value": {"src": "artifacts/f%d.png" % i, "sha256": "ab" * 32,
                                                 "region": {"box": [0.1, 0.1, 0.9, 0.5]}},
                      "cite": {"label": "verbatim", "source": "paper", "page": i}})
        return p

    def test_repeated_instruction_cannot_anchor(self):
        q = "How attractive do you find the face shown above on this page?"
        b = r1_pdf(["Stimulus A\n" + q, "Stimulus B\n" + q, "Stimulus C\n" + q])
        proj, _ = self.build(self.stimulus_protocol(q, (1, 2, 3)), b)
        parts = [e["locator"]["parts"][0] for e in proj["distribution"]["held"].values() if e["kind"] == "text"]
        self.assertTrue(all(pt["unique"] is False for pt in parts))
        for user in (b, r1_pdf(["Cover page: terms of use, downloaded 2026.", "Stimulus A\n" + q,
                                "Stimulus B\n" + q, "Stimulus C\n" + q])):
            r = self.rehy(proj, user)
            self.assertEqual(r["renders"], {})
            self.assertTrue(all(it["status"] in ("ok", "needs_user_file") for it in r["items"].values()))
        q = "Rate the picture below from one to seven."
        b = r1_pdf(["Intro page without stimuli.", "Stimulus A\n" + q, "Stimulus B\n" + q])
        proj, _ = self.build(self.stimulus_protocol(q, (2, 3)), b)
        r = self.rehy(proj, r1_pdf(["Stimulus A\n" + q, "Stimulus B\n" + q]))
        self.assertEqual(r["renders"], {})

    def test_distinct_anchor_texts_count_once(self):
        p = inv_base()
        p["meta"]["sources"] = {"paper": {"file": "p.pdf"}}
        p["stages"]["s"]["responses"] = [{"id": "r%d" % i, "kind": "choice", "prompt": "x",
                                          "options": [{"code": 1, "label": "Agree", "cite": {
                                              "label": "verbatim", "source": "paper", "page": 2}}]} for i in range(4)]
        p["stages"]["s"]["content"] = [{"id": "f", "value": {"src": "artifacts/f.png", "sha256": "ab" * 32,
                                                             "region": {"box": [0.1, 0.1, 0.9, 0.5]}},
                                        "cite": {"label": "verbatim", "source": "paper", "page": 2}}]
        proj, _ = self.build(p, r1_pdf(["Methods text here.", "Figure 3 survey\nAgree Agree Agree Agree"]))
        r = self.rehy(proj, r1_pdf(["Methods text here.", "Totally different page; we Agree."]))
        self.assertEqual(r["renders"], {})

    def test_scanned_json_and_bibliography(self):
        p = inv_base(); p["data"]["q"] = {"text": "Strongly agree", "cite": inv_cite()}
        proj, _ = project_t(p, INV3_T, sources={"inv": INV3})
        eff = {"effects": [{"id": "e1", "item": "Strongly agree"}]}
        self.assertFalse(release.distributable("effects.json", proj, json.dumps(eff), sources={"inv": INV3}))
        src2 = INV3.replace(b"Invented Mood Inventory", b"The Invented Mood Inventory and Sleep in Adults")
        st = {"title": "The Invented Mood Inventory and Sleep in Adults", "authors": ["A. Author"]}
        self.assertTrue(release.distributable("study.json", proj, json.dumps(st), sources={"inv": src2}))
        p = inv_base(); p["meta"]["sources"]["inv"]["title"] = "The Invented Mood Inventory and Sleep in Adults"
        proj, rep = project_t(p, {"inv": {"tier": "link", "url": "https://example.org/x"}}, sources={"inv": src2})
        self.assertEqual(proj["meta"]["sources"]["inv"]["title"], "The Invented Mood Inventory and Sleep in Adults")

    def test_total_hash_budget(self):
        sc = D.Scope(["abc " * 2000])
        loc = {"parts": [{"units": [0, 0], "canon_len": 100, "canon_sha256": "0" * 64}], "restore": []}
        t, m = D.find_ex(sc, loc, "0" * 64, total={"left": 10})
        self.assertIsNone(t)


# ------------------------------------------------------------------------------------------- review round 6
class TestReviewRound6(unittest.TestCase):
    """Distribution review round 5 (probes b1, r1, r2, invented text)."""

    Q1 = "I worry about my health"
    Q2 = "How attractive do you find the face shown above on this page?"

    def proj(self):
        b = r1_pdf(["Methods. Participants rated items.", "Scale\n1. I worry about my health.\n2. " + self.Q2 + "\nEnd."])
        p = inv_base()
        p["meta"]["sources"] = {"paper": {"file": "p.pdf"}}
        for i, q in enumerate((self.Q1, self.Q2)):
            p["stages"]["s"]["content"].append({"id": "q%d" % i, "value": q,
                                                "cite": {"label": "verbatim", "source": "paper", "page": 2}})
        proj, _ = release.project(p, {"paper": {"tier": "user"}}, sources={"paper": b}, extractors={"pdf": r1_extract})
        return proj, b

    def test_scanned_json_held_text_rule(self):
        proj, b = self.proj()

        def dist(doc):
            return release.distributable("effects.json", proj, json.dumps(doc), sources={"paper": b},
                                         extractors={"pdf": r1_extract})
        for doc in ({"effects": [{"id": "e1", "label": "Mean agreement with 'I worry about my health' by condition"}]},
                    {"effects": [{"id": "e1", "title": self.Q2}]}, {"effects": [{"id": "e1", "paper": self.Q2}]},
                    {"hypotheses": [{"id": "h1", "pages": [self.Q2]}]}, {"effects": [{"id": "e1", "label": self.Q2}]},
                    {"effects": [{"id": "e1", "label": self.Q1.lower()}]}, {"title": self.Q2}):
            self.assertFalse(dist(doc), doc)
        self.assertTrue(dist({"title": "An invented paper about faces", "effects": [{"id": "e1"}]}))
        # the held text cannot be recovered from what was supplied: refused
        self.assertFalse(release.distributable("effects.json", proj, json.dumps({"effects": []}),
                                               sources={"paper": r1_pdf(["x", "y"])}, extractors={"pdf": r1_extract}))

    def test_bibliographic_fields_still_held_checked(self):
        b = r1_pdf(["Methods.", "Scale\n" + self.Q2 + "\nEnd."])
        p = inv_base()
        p["meta"]["sources"] = {"paper": {"file": "p.pdf", "title": self.Q2}}
        p["meta"]["citation"] = "X (2020). " + self.Q2
        p["stages"]["s"]["content"].append({"id": "q", "value": self.Q2,
                                            "cite": {"label": "verbatim", "source": "paper", "page": 2}})
        proj, _ = release.project(p, {"paper": {"tier": "user"}}, sources={"paper": b}, extractors={"pdf": r1_extract})
        self.assertNotIn("attractive", json.dumps(proj))

    def test_reflowed_edition_and_legacy_projection(self):
        qa = "Look at the photograph of Person K and decide whether you trust them."
        p = inv_base()
        p["meta"]["sources"] = {"paper": {"file": "p.pdf"}}
        p["stages"]["s"]["content"] = [
            {"id": "t", "value": qa, "cite": {"label": "verbatim", "source": "paper", "page": 3}},
            {"id": "fig", "value": {"src": "artifacts/fig.png", "sha256": "ab" * 32,
                                    "region": {"box": [0.1, 0.5, 0.9, 0.9]}},
             "cite": {"label": "verbatim", "source": "paper", "page": 3}}]
        b = r1_pdf(["Intro text.", "Method text, long discussion of procedure.", qa + "\n[stimulus photo K]\nFigure 2."])
        proj, _ = release.project(p, {"paper": {"tier": "user"}}, sources={"paper": b}, extractors={"pdf": r1_extract})
        reflow = r1_pdf(["Intro text.", "Method text, long discussion of procedure.\n" + qa,
                         "[stimulus photo K]\nFigure 2."])
        _, r = hsenv.rehydrate(proj, files={"paper": reflow}, extractors={"pdf": r1_extract})
        self.assertEqual(r["renders"], {})
        stamped = r1_pdf(["Intro text.", "Method text, long discussion of procedure.",
                          "Downloaded by Invented University\n" + qa + "\n[stimulus photo K]\nFigure 2."])
        _, r = hsenv.rehydrate(proj, files={"paper": stamped}, extractors={"pdf": r1_extract})
        self.assertEqual(len(r["renders"]), 1)   # a stamp line above the anchor is tolerated
        legacy = copy.deepcopy(proj)   # a locator without `unique` never anchors
        for e in legacy["distribution"]["held"].values():
            for pt in e["locator"].get("parts", []):
                pt.pop("unique", None)
        _, r = hsenv.rehydrate(legacy, files={"paper": b}, extractors={"pdf": r1_extract})
        self.assertEqual(r["renders"], {})


# ------------------------------------------------------------------------------------------- review round 7
class TestReviewRound7(unittest.TestCase):
    """Distribution review round 6 (probes p1, p2, invented text): image-read texts in scanned JSON, the citation,
    JSON keys, SOURCE.json entries."""

    Q = "I often feel lonely even when other people are around me"
    CAP = "Methods. Participants completed the scale shown in Figure 1."
    T3 = "Loneliness and social connection in a large invented sample of adults"

    def setUp(self):
        self.b = r1_pdf([self.CAP, "Figure 1.\n[scanned scale image]"])
        p = inv_base()
        p["meta"]["sources"] = {"paper": {"file": "p.pdf"}}
        p["stages"]["s"]["content"] = [
            {"id": "cap", "value": self.CAP, "cite": {"label": "verbatim", "source": "paper", "page": 1}},
            {"id": "q", "value": self.Q, "cite": {"label": "verbatim", "source": "paper", "page": 2, "read": "image",
                                                  "region": {"box": [0.1, 0.2, 0.9, 0.4]}}}]
        self.proj, _ = release.project(p, {"paper": {"tier": "user"}}, sources={"paper": self.b},
                                       extractors={"pdf": r1_extract})
        self.hid = next(k for k, e in self.proj["distribution"]["held"].items() if e["locator"]["format"] == "region")

    def dist(self, doc, held_texts=None, name="effects.json"):
        return release.distributable(name, self.proj, json.dumps(doc), sources={"paper": self.b},
                                     extractors={"pdf": r1_extract}, held_texts=held_texts)

    def test_parts_less_held_texts_must_be_supplied(self):
        clean = {"effects": [{"id": "e1", "label": "Agreement by condition"}]}
        self.assertFalse(self.dist(clean))                                     # not supplied: refused
        self.assertFalse(self.dist(clean, {self.hid: self.Q + "!"}))           # fails its hash: refused
        self.assertTrue(self.dist(clean, {self.hid: self.Q}))
        for label in ("Agreement with '%s' by condition" % self.Q, self.Q.lower()):
            self.assertFalse(self.dist({"effects": [{"id": "e1", "label": label}]}, {self.hid: self.Q}), label)

    def test_citation_kept_and_keys_checked(self):
        b3 = r1_pdf([self.T3 + "\nJ. Doe\nAbstract.", "Scale\nHow lonely do you feel today on a scale from one to seven?"])
        p = inv_base()
        p["meta"]["sources"] = {"paper": {"file": "p.pdf", "title": self.T3}}
        p["meta"]["citation"] = "Doe, J. (2020). " + self.T3 + ". Invented Journal, 1, 1-10."
        p["stages"]["s"]["content"] = [{"id": "q", "value": "How lonely do you feel today on a scale from one to seven?",
                                        "cite": {"label": "verbatim", "source": "paper", "page": 2}}]
        proj, _ = release.project(p, {"paper": {"tier": "user"}}, sources={"paper": b3}, extractors={"pdf": r1_extract})
        self.assertEqual(proj["meta"]["citation"], p["meta"]["citation"])
        kw = dict(sources={"paper": b3}, extractors={"pdf": r1_extract})
        self.assertTrue(release.distributable("effects.json", proj, json.dumps({"title": self.T3, "effects": []}), **kw))
        self.assertFalse(release.distributable("effects.json", proj, json.dumps({"effects": {self.T3: {"id": "e"}}}),
                                               **kw))
        # SOURCE.json: the exemption covers a declared source's own entry only
        self.assertTrue(release.distributable("sources/SOURCE.json", proj, json.dumps({"paper": {"title": self.T3}}),
                                              **kw))
        self.assertFalse(release.distributable("sources/SOURCE.json", proj,
                                               json.dumps({"notes": {"title": self.T3}}), **kw))


# ------------------------------------------------------------------------------------------- review round 8
class TestReviewRound8(unittest.TestCase):
    """Distribution review round 7 (probes a, s, invented text)."""

    def test_hosted_sourcetext_reprinting_held_text(self):
        item = "I often feel lonely even when other people are around me"
        paper = ("Introduction. We study loneliness.\nAppendix A. Items of the Invented Loneliness Scale.\n1. "
                 + item + "\n").encode()
        scale = ("Invented Loneliness Scale manual\n1. " + item + "\n").encode()
        p = inv_base()
        p["meta"]["sources"] = {"paper": {"file": "p.txt"}, "scale": {"file": "manual.txt"}}
        p["stages"]["s"]["content"] = [{"id": "q", "value": item, "cite": {"label": "verbatim", "source": "scale"}}]
        t = {"paper": {"tier": "hosted", "licence": "CC-BY-4.0", "attribution": "Doe 2020, CC BY 4.0"},
             "scale": {"tier": "link", "url": "https://example.org/manual"}}
        proj, _ = project_t(p, t, sources={"paper": paper, "scale": scale})
        self.assertFalse(release.distributable("sourcetext/paper.txt", proj))
        self.assertFalse(release.distributable("sourcetext/paper.txt", proj, content=paper,
                                               sources={"paper": paper, "scale": scale}))
        clean = b"Introduction. We study loneliness.\n"
        self.assertTrue(release.distributable("sourcetext/paper.txt", proj, content=clean,
                                              sources={"paper": paper, "scale": scale}))
        self.assertFalse(release.distributable("sourcetext/paper.txt", proj, content=clean, sources={"paper": paper}))
        self.assertFalse(release.distributable("sources/open/paper.txt", proj))

    def test_cjk_with_slash_is_not_a_token(self):
        cjk = "请根据您最近一周的实际情况/真实感受回答以下所有问题并选择最符合的选项"
        src = ("说明\n" + cjk + "\n").encode()
        t = {"inv": {"tier": "link", "url": "https://e.org/x"}}
        p = inv_base(); p["stages"]["s"]["content"] = [{"id": "intro", "value": cjk}]
        with self.assertRaisesRegex(release.ProjectionError, "without a cite"):
            project_t(p, t, sources={"inv": src})
        p = inv_base(); p["analysis"]["effects"] = [{"id": "e1", "label": cjk}]
        proj, _ = project_t(p, t, sources={"inv": src})
        self.assertNotIn(cjk, json.dumps(proj, ensure_ascii=False))

    def test_meta_source_src_is_not_a_shipped_image(self):
        p = inv_base(); p["data"]["q"] = {"text": "I often feel restless at night.", "cite": inv_cite()}
        p["meta"]["sources"]["inv"]["src"] = "artifacts/paper.pdf"
        proj, _ = project_t(p, INV3_T, sources={"inv": INV3})
        self.assertFalse(release.distributable("artifacts/paper.pdf", proj))


# ------------------------------------------------------------------------------------------- review round 9
HOST_T = {"tier": "hosted", "licence": "CC-BY-4.0", "attribution": "Doe 2020, CC BY 4.0"}
LINK_T = {"tier": "link", "url": "https://example.org/manual"}


class TestReviewRound9(unittest.TestCase):
    """Distribution review round 8 (probes c8, p1-p9, invented text): one shared held-text rule (HeldIndex)."""

    def hosted_case(self, items, scale_bytes):
        p = inv_base()
        p["meta"]["sources"] = {"paper": {"file": "p.txt"}, "scale": {"file": "m.txt"}}
        p["stages"]["s"]["content"] = [{"id": "q%d" % i, "value": t, "cite": {"label": "verbatim", "source": "scale"}}
                                       for i, t in enumerate(items)]
        srcs = {"paper": b"Intro.\n", "scale": scale_bytes}
        proj, _ = project_t(p, {"paper": HOST_T, "scale": LINK_T}, sources=srcs)
        return proj, srcs

    def test_sourcetext_reprints(self):
        item = "I feel isolated from others"
        proj, srcs = self.hosted_case([item], ("Manual\n1. " + item + "\n").encode())
        for st in ("Appendix. Items: (1) I feel iso-\nlated from others. (2) ...\n",
                   "Appendix. Items: (1) I feel isolated from others.\n"):
            self.assertFalse(release.distributable("sourcetext/paper.txt", proj, content=st, sources=srcs), st)
        self.assertFalse(release.distributable("sourcetext/paper.txt", proj, sources=srcs,
                                               content=("Appendix: " + item).encode("utf-16")))   # strict UTF-8
        items = ["我经常感到孤独即使身边有人", "我觉得自己与他人疏远", "我很难找到可以交谈的人"]
        proj, srcs = self.hosted_case(items, ("孤独量表手册\n" + "\n".join(
            "%d. %s" % (i + 1, t) for i, t in enumerate(items)) + "\n").encode())
        for st in ("附录 量表条目\n" + "\n".join("%d. %s" % (i + 1, t) for i, t in enumerate(items)) + "\n",
                   "被试回答了“%s”、“%s”和“%s”等条目。\n" % tuple(items)):
            self.assertFalse(release.distributable("sourcetext/paper.txt", proj, content=st.encode(), sources=srcs))
        eff = json.dumps({"effects": [{"id": "e", "outcome": "条目：" + items[0]}]}, ensure_ascii=False)
        self.assertFalse(release.distributable("effects.json", proj, content=eff, sources=srcs))

    def test_missing_extractor_refuses(self):
        item = "I often feel lonely even when other people are around me"
        scale = ("%PDF-1.4\fManual\n1. " + item + "\n").encode()
        p = inv_base()
        p["meta"]["sources"] = {"paper": {"file": "p.txt"}, "scale": {"file": "m.pdf"}}
        p["stages"]["s"]["content"] = [{"id": "q", "value": item,
                                        "cite": {"label": "verbatim", "source": "scale", "page": 1}}]
        srcs = {"paper": b"Intro.\n", "scale": scale}
        proj, _ = project_t(p, {"paper": HOST_T, "scale": LINK_T}, sources=srcs, extractors={"pdf": r1_extract})
        self.assertFalse(release.distributable("sourcetext/paper.txt", proj, content="clean", sources=srcs))
        self.assertFalse(release.distributable("effects.json", proj, content="{}", sources=srcs))
        # a non-strict projection never ships as protocol.json
        p["stages"]["s"]["content"].append({"id": "intro", "value": "Note: " + item})
        proj3, _ = project_t(p, {"paper": HOST_T, "scale": LINK_T}, sources=srcs, extractors={"pdf": r1_extract},
                             strict=False)
        self.assertFalse(release.distributable("protocol.json", proj3, content=json.dumps(proj3)))
        self.assertTrue(release.distributable("protocol.json", proj, content=json.dumps(proj)))

    def test_on_screen_fragment_and_uncited_image(self):
        vig = "Imagine you find a wallet with two hundred dollars on a park bench near your home"
        p = inv_base()
        p["meta"]["sources"] = {"paper": {"file": "p.pdf"}}
        p["data"]["stim"] = {"src": "artifacts/stim.png", "lines": [vig], "region": {"box": [0.1, 0.1, 0.9, 0.5]},
                             "cite": {"label": "verbatim", "source": "paper", "page": 3, "read": "image"}}
        p["stages"]["s"]["content"] = [{"id": "q", "value": "Remember: you find a wallet with two hundred dollars "
                                                             "on a park bench."}]
        with self.assertRaisesRegex(release.ProjectionError, "cannot be withheld"):
            project_t(p, {"paper": {"tier": "user"}})
        p = inv_base()
        p["data"]["q"] = {"text": "I often feel restless at night.", "cite": inv_cite()}
        p["data"]["fig"] = {"src": "artifacts/scale_page.png"}
        with self.assertRaisesRegex(release.ProjectionError, "image\\(s\\) without a cite"):
            project_t(p, INV3_T, sources={"inv": INV3})
        p["data"]["fig"]["cite"] = {"label": "missing", "source": "inv"}
        project_t(p, INV3_T, sources={"inv": INV3})

    def test_slash_joined_text_is_not_a_path(self):
        scale = b"Manual\nResponse scale: never/rarely/sometimes/often/always-or-nearly-always\n"
        p = inv_base()
        p["meta"]["sources"] = {"scale": {"file": "m.txt"}}
        p["stages"]["s"]["content"] = [{"id": "a", "value": "never/rarely/sometimes/often/always-or-nearly-always"}]
        with self.assertRaisesRegex(release.ProjectionError, "without a cite"):
            project_t(p, {"scale": LINK_T}, sources={"scale": scale})
        self.assertTrue(release._TOKEN.fullmatch("artifacts/fig2.png") and release._TOKEN.fullmatch("./x/y"))


# ------------------------------------------------------------------------------------------- review round 10
class TestReviewRound10(unittest.TestCase):
    """Distribution review round 9 (probes q1-q3, invented text): the held-text check on an alphanumeric skeleton."""

    def case(self, items, scale):
        p = inv_base()
        p["meta"]["sources"] = {"paper": {"file": "p.txt"}, "scale": {"file": "m.txt"}}
        p["stages"]["s"]["content"] = [{"id": "q%d" % i, "value": t, "cite": {"label": "verbatim", "source": "scale"}}
                                       for i, t in enumerate(items)]
        srcs = {"paper": b"Intro.\n", "scale": scale.encode()}
        proj, _ = project_t(p, {"paper": HOST_T, "scale": LINK_T}, sources=srcs)
        return proj, srcs

    def test_numbered_and_punctuated_reprints(self):
        items = ["我感到情绪低落", "我常常感到孤独", "我觉得很疲倦"]
        proj, srcs = self.case(items, "量表\n" + "\n".join(items) + "\n")
        for fmt in ("%d.%s", "（%d）%s", "%d、%s", "%d. %s"):
            st = "\n".join(fmt % (i + 1, t) for i, t in enumerate(items))
            self.assertFalse(release.distributable("sourcetext/paper.txt", proj, content=st.encode(), sources=srcs), st)
        st = "\n".join("%s。" % t for t in items)
        self.assertFalse(release.distributable("sourcetext/paper.txt", proj, content=st.encode(), sources=srcs))
        items = ["I feel sad", "I sleep badly", "I feel lonely"]
        proj, srcs = self.case(items, "Scale\n" + "\n".join(items) + "\n")
        for fmt in ("%d. %s.", "%d. \u201c%s\u201d", "%d) %s 1 2 3 4", "%d.%s", "Item %d: %s", "- %s", "\u2022 %s",
                    "%d. %s&#46;&nbsp;"):
            st = "\n".join((fmt % (i + 1, t)) if "%d" in fmt else (fmt % t) for i, t in enumerate(items))
            self.assertFalse(release.distributable("sourcetext/paper.txt", proj, content=st.encode(), sources=srcs), st)
        for item_fmt in ("%s.", "\u201c%s\u201d"):
            eff = json.dumps({"effects": [{"id": "e", "items": [item_fmt % t for t in items]}]})
            self.assertFalse(release.distributable("effects.json", proj, content=eff, sources=srcs))
        # unrelated text still ships
        self.assertTrue(release.distributable("sourcetext/paper.txt", proj, sources=srcs,
                                              content=b"Introduction. We measured mood in an invented sample.\n"))

    def test_on_screen_and_operator_copies(self):
        p = inv_base()
        p["meta"]["sources"] = {"scale": {"file": "m.txt"}}
        p["stages"]["s"]["content"] = [{"id": "q", "value": "I feel lonely", "cite": {"label": "verbatim", "source": "scale"}},
                                       {"id": "r", "value": "I feel lonely."}]
        with self.assertRaisesRegex(release.ProjectionError, "cannot be withheld"):
            project_t(p, {"scale": LINK_T}, sources={"scale": b"Scale\nI feel lonely\n"})
        p = inv_base()
        p["meta"]["sources"] = {"scale": {"file": "m.txt"}}
        p["stages"]["s"]["content"] = [{"id": "q", "value": "我常常感到孤独", "cite": {"label": "verbatim", "source": "scale"}}]
        p["meta"]["notes"] = "条目“我常常感到孤独。”取自量表"
        p["analysis"]["effects"] = [{"id": "e", "label": "我常常感到孤独。"}]
        proj, _ = project_t(p, {"scale": LINK_T}, sources={"scale": "量表\n我常常感到孤独\n".encode()})
        self.assertNotIn("孤独", json.dumps({k: v for k, v in proj.items() if k != "distribution"}, ensure_ascii=False))

    def test_single_token_ids_are_not_short_copies(self):
        # over-blocking guard (real-data run): an id / key / layout entry equal to a short held label is not a leak
        p = inv_base()
        p["meta"]["sources"] = {"scale": {"file": "m.txt"}}
        p["stages"]["s"]["content"] = [{"id": "gender", "value": "Gender:", "cite": {"label": "verbatim", "source": "scale"}}]
        p["stages"]["s"]["layout"] = ["gender"]
        p["data"]["opts"] = {"gender": [1, 2]}
        proj, _ = project_t(p, {"scale": LINK_T}, sources={"scale": b"Form\nGender:\n"})
        self.assertEqual(proj["stages"]["s"]["layout"], ["gender"])

    def test_punctuation_changed_long_item(self):
        proj, srcs = self.case(["I feel lonely, even with others"], "Scale\nI feel lonely, even with others\n")
        for st in ("Appendix. 1. I feel lonely even with others.", "Appendix. 1. I feel lonely; even with others."):
            self.assertFalse(release.distributable("sourcetext/paper.txt", proj, content=st.encode(), sources=srcs))


# ------------------------------------------------------------------------------------------- review round 11
class TestReviewRound11(unittest.TestCase):
    """Distribution review round 10 (probes r1-r3, invented text)."""

    def test_markers_and_cjk_with_digits(self):
        ix = release.HeldIndex(["过去7天我睡得不好", "I feel sad", "私は悲しいと感じる", "나는 슬프다고 느낀다"])
        for probe in ("1.过去7天我睡得不好（反向）", "量表包括“过去7天我睡得不好”等条目", "①过去7天我睡得不好",
                      "一、过去7天我睡得不好", "1. I feel sad (R)", "<b>I feel sad</b>", "<td>I feel sad</td><td>1</td>",
                      "I feel sad*", "I feel sad†", "a. I feel sad", "ii. I feel sad", "(i) I feel sad", "Q1a. I feel sad",
                      "1.1 I feel sad", "① I feel sad", "I feel sad  1 2 3 4 5 N/A", "質問1：私は悲しいと感じる（逆転項目）",
                      "문항 1. 나는 슬프다고 느낀다 (역)"):
            self.assertEqual(ix.hit(probe), "whole", probe)
            self.assertFalse(ix.text_file(probe.encode()), probe)
        for probe in ("I feel sadness", "I feel sad today", "gender"):
            self.assertIsNone(ix.hit(probe), probe)
        self.assertFalse(release.HeldIndex(["I feel sad & lonely"]).text_file("I feel sad &amp; lonely".encode()))

    def test_withheld_prefix_is_not_exempt(self):
        long_item = "I feel lonely, even with others"
        p = inv_base()
        p["meta"]["sources"] = {"scale": {"file": "m.txt"}}
        p["stages"]["s"]["content"] = [{"id": "q", "value": long_item, "cite": {"label": "verbatim", "source": "scale"}}]
        p["meta"]["notes"] = "withheld: " + long_item
        proj, _ = project_t(p, {"scale": LINK_T}, sources={"scale": ("Scale\n" + long_item + "\n").encode()})
        self.assertNotIn("lonely", json.dumps({k: v for k, v in proj.items() if k != "distribution"}))
        p["stages"]["s"]["content"].append({"id": "r", "value": "withheld:" + long_item})
        with self.assertRaises(release.ProjectionError):
            project_t(p, {"scale": LINK_T}, sources={"scale": ("Scale\n" + long_item + "\n").encode()})

    def test_cjk_digit_item_in_operator_note_and_on_screen(self):
        item = "过去7天我睡得不好"
        src = ("量表\n" + item + "\n").encode()
        p = inv_base()
        p["meta"]["sources"] = {"scale": {"file": "m.txt"}}
        p["stages"]["s"]["content"] = [{"id": "q", "value": item, "cite": {"label": "verbatim", "source": "scale"}}]
        p["meta"]["notes"] = "条目“过去7天我睡得不好”（反向）取自量表"
        proj, _ = project_t(p, {"scale": LINK_T}, sources={"scale": src})
        self.assertTrue(proj["meta"]["notes"].startswith(D.WITHHELD))
        p["stages"]["s"]["content"].append({"id": "r", "value": "1. 过去7天我睡得不好（反向）"})
        with self.assertRaises(release.ProjectionError):
            project_t(p, {"scale": LINK_T}, sources={"scale": src})

    def test_json_entities_and_tokens(self):
        p = inv_base()
        p["meta"]["sources"] = {"scale": {"file": "m.txt"}}
        p["stages"]["s"]["content"] = [{"id": "gender", "value": "Gender:", "cite": {"label": "verbatim", "source": "scale"}},
                                       {"id": "q", "value": "I feel sad & lonely", "cite": {"label": "verbatim",
                                                                                         "source": "scale"}}]
        src = b"Form\nGender:\nI feel sad & lonely\n"
        proj, _ = project_t(p, {"scale": LINK_T}, sources={"scale": src})
        kw = dict(sources={"scale": src})
        self.assertFalse(release.distributable("effects.json", proj, json.dumps({"e": "I feel sad &amp; lonely"}), **kw))
        self.assertTrue(release.distributable("effects.json", proj, json.dumps({"by": "gender"}), **kw))


# ------------------------------------------------------------------------------------------- review round 12
class TestReviewRound12(unittest.TestCase):
    """Distribution review round 11 (probes q1-q3, invented text): NFKC comparison form, item codes, long tags,
    unspaced scripts."""

    def test_fullwidth_and_markers(self):
        cases = [(["过去7天我睡得不好"], ["过去７天我睡得不好", "注：过去７天我睡得不好（反向）"]),
                 (["过去７天我睡得不好"], ["过去7天我睡得不好", "条目“过去7天我睡得不好”"]),
                 (["最近２週間で疲れた"], ["最近2週間で疲れた"]),
                 (["ฉันรู้สึกเศร้า"], ["ข้อ 1 ฉันรู้สึกเศร้า (R)", "ตัวอย่างข้อคำถาม ฉันรู้สึกเศร้า ในแบบวัด"]),
                 (["I feel sad"], ["\uff29 \uff46\uff45\uff45\uff4c \uff53\uff41\uff44",
                                   '<span style="font-size: 14px; font-family: arial, helvetica, sans-serif; color: '
                                   'rgb(0, 0, 0);">I feel sad</span>', "A1. I feel sad", "D3) I feel sad",
                                   "No. 1 I feel sad", "PHQ1. I feel sad", "1. (a) I feel sad", "I feel sad [R]",
                                   "I feel sad (reverse scored)", "I feel sad (reverse-coded)", "1\tI feel sad\tR",
                                   "\u25a1 I feel sad", "\u2610 I feel sad", "\u25cb I feel sad", "[ ] I feel sad"])]
        for items, probes in cases:
            ix = release.HeldIndex(items)
            for probe in probes:
                self.assertEqual(ix.hit(probe), "whole", probe)
                self.assertFalse(ix.text_file(probe.encode()), probe)
        self.assertIsNone(release.HeldIndex(["I feel sad"]).hit("I feel sadness"))

    def test_fullwidth_copies_in_projection_and_files(self):
        item = "过去7天我睡得不好"
        src = ("量表\n" + item + "\n").encode()
        p = inv_base()
        p["meta"]["sources"] = {"scale": {"file": "m.txt"}}
        p["stages"]["s"]["content"] = [{"id": "q", "value": item, "cite": {"label": "verbatim", "source": "scale"}}]
        p["meta"]["notes"] = "条目“过去７天我睡得不好”（反向）取自量表"
        proj, _ = project_t(p, {"scale": LINK_T}, sources={"scale": src})
        self.assertNotIn("睡得不好", json.dumps({k: v for k, v in proj.items() if k != "distribution"},
                                                ensure_ascii=False))
        p["stages"]["s"]["content"].append({"id": "r", "value": "1. 过去７天我睡得不好"})
        with self.assertRaises(release.ProjectionError):
            project_t(p, {"scale": LINK_T}, sources={"scale": src})
        p = inv_base()
        p["meta"]["sources"] = {"paper": {"file": "p.txt"}, "scale": {"file": "m.txt"}}
        p["stages"]["s"]["content"] = [{"id": "q", "value": item, "cite": {"label": "verbatim", "source": "scale"}}]
        srcs = {"paper": "引言。量表条目如“过去７天我睡得不好”。\n".encode(), "scale": src}
        proj, _ = project_t(p, {"paper": HOST_T, "scale": LINK_T}, sources=srcs)
        self.assertFalse(release.distributable("sourcetext/paper.txt", proj, srcs["paper"], sources=srcs))
        self.assertFalse(release.distributable("effects.json", proj, json.dumps({"note": "条目：过去７天我睡得不好"},
                                                                               ensure_ascii=False), sources=srcs))

    def test_fullwidth_item_rehydrates_exactly(self):
        item = "过去７天我睡得不好（Ａ）"
        p = inv_base()
        p["meta"]["sources"] = {"scale": {"file": "m.txt"}}
        p["stages"]["s"]["content"] = [{"id": "q", "value": item, "cite": {"label": "verbatim", "source": "scale"}}]
        proj, _ = project_t(p, {"scale": LINK_T}, sources={"scale": ("量表\n" + item + "\n").encode()})
        out, rep = hsenv.rehydrate(proj, files={"scale": ("封面 2026\n量表\n" + item + "\n").encode()})
        self.assertEqual(out["stages"]["s"]["content"][0]["value"], item)   # comparison forms never reach the text


# ------------------------------------------------------------------------------------------- review round 13
class TestReviewRound13(unittest.TestCase):
    """Distribution review round 12 (probe p1, invented text): angle-bracket text is text, a tag hides nothing."""

    def test_angle_bracket_texts(self):
        for item, probes in [("Press <Enter> to continue", ["Press <Enter> to continue", "Note: Press <Enter> to continue"]),
                             ("Press <Enter>", ["Press <Enter>"]),
                             ("Dear <name>, thank you for taking part", ["Dear <name>, thank you for taking part"]),
                             ("I feel lonely even with others", ["Item <I feel lonely even with others> reversed",
                                                                 "<b>I feel lonely even with others</b>"])]:
            ix = release.HeldIndex([item], [D.text_sha256(item)])
            for probe in probes:
                self.assertEqual(ix.hit(probe), "whole", probe)
                self.assertFalse(ix.text_file(probe.encode()), probe)
        ix = release.HeldIndex(["I feel lonely even with others"])
        doc = ("Results: Group A<Group B in all blocks.\nAppendix item: I feel lonely even with others\n"
               "and Group B>Group A later.")
        self.assertFalse(ix.text_file(doc.encode()))   # a "tag" spanning lines never swallows the item
        self.assertIsNone(release.HeldIndex(["I like bananas"]).hit("I like bana"))   # word-final "na" kept

    def test_angle_bracket_item_everywhere(self):
        item = "Press <Enter> to continue"
        src = ("Instructions\n" + item + "\n").encode()
        p = inv_base()
        p["meta"]["sources"] = {"task": {"file": "t.txt"}}
        p["stages"]["s"]["content"] = [{"id": "q", "value": item, "cite": {"label": "verbatim", "source": "task"}}]
        p["meta"]["notes"] = item
        proj, _ = project_t(p, {"task": LINK_T}, sources={"task": src})
        n = proj["meta"]["notes"]
        self.assertTrue(n.startswith(D.WITHHELD) or set(n) == {D.PLACEHOLDER})   # held (restorable) or withheld
        p["stages"]["s"]["content"].append({"id": "r", "value": item})
        with self.assertRaises(release.ProjectionError):
            project_t(p, {"task": LINK_T}, sources={"task": src})
        p = inv_base()
        p["meta"]["sources"] = {"paper": {"file": "p.txt"}, "task": {"file": "t.txt"}}
        p["stages"]["s"]["content"] = [{"id": "q", "value": item, "cite": {"label": "verbatim", "source": "task"}}]
        srcs = {"paper": ("Method. Participants read: " + item + "\n").encode(), "task": src}
        proj, _ = project_t(p, {"paper": HOST_T, "task": LINK_T}, sources=srcs)
        self.assertFalse(release.distributable("sourcetext/paper.txt", proj, srcs["paper"], sources=srcs))
        self.assertFalse(release.distributable("effects.json", proj, json.dumps({"n": item}), sources=srcs))


# ------------------------------------------------------------------------------------------- review round 14
class TestReviewRound14(unittest.TestCase):
    """Distribution review round 13 (probes p1-p3, invented text): HTML entities are unescaped inside HeldIndex.hit."""

    CASES = [("Click \"Next\" when you're ready", "Click &quot;Next&quot; when you&#39;re ready"),
             ("Press <Enter> to continue", "Press &lt;Enter&gt; to continue"),
             ("Tom & Jerry fight", "Tom &amp;amp; Jerry fight")]

    def project(self, item, extra):
        p = inv_base()
        p["meta"]["sources"] = {"task": {"file": "t.txt"}}
        p["stages"]["s"]["content"] = [{"id": "q", "value": item, "cite": {"label": "verbatim", "source": "task"}}]
        extra(p)
        return project_t(p, {"task": LINK_T}, sources={"task": ("Instructions\n" + item + "\n").encode()})

    def test_escaped_copies(self):
        for item, escaped in self.CASES:
            ix = release.HeldIndex([item])
            self.assertEqual(ix.hit(escaped), "whole", escaped)
            self.assertFalse(ix.text_file(escaped.encode()), escaped)
            with self.assertRaises(release.ProjectionError, msg=escaped):   # uncited on screen
                self.project(item, lambda p, e=escaped: p["stages"]["s"]["content"].append({"id": "r", "value": e}))
            proj, _ = self.project(item, lambda p, e=escaped: p["meta"].__setitem__("notes", e))
            self.assertTrue(proj["meta"]["notes"].startswith(D.WITHHELD), escaped)
            src = ("Instructions\n" + item + "\n").encode()
            self.assertFalse(release.distributable("effects.json", proj, json.dumps({"n": escaped}),
                                                   sources={"task": src}), escaped)

    def test_all_digit_held_text_in_text_file(self):
        ix = release.HeldIndex(["2468 1357 9024"])
        self.assertFalse(ix.text_file(b"Appendix\n2468 1357 9024\n"))
        self.assertTrue(release.HeldIndex(["I feel sad"]).text_file(b"Appendix\n2468 1357 9024\n"))


# ------------------------------------------------------------------------------------------- review round 15
class TestReviewRound15(unittest.TestCase):
    """Distribution review round 14 (probes q1, q2, invented text): every comparison goes through release._forms."""

    PARA = ("Imagine that you are walking home late at night when a stranger asks you for directions to the "
            "station.")
    ITEM = "I feel lonely even with others around me"

    @classmethod
    def variants(cls, text):
        return {"plain": text, "nbsp": text.replace(" ", "&nbsp;"), "br": text.replace(" ", "<br>"),
                "numeric": text.replace(" ", "&#32;"), "double": text.replace(" ", "&amp;nbsp;"),
                "deep": text.replace(" ", "&amp;amp;amp;amp;amp;nbsp;"),
                "span": '<span style="color: red">' + text + "</span>",
                "fullwidth": "".join(chr(ord(c) + 0xFEE0) if "!" <= c <= "~" else c for c in text)}

    def src(self):
        return ("Instructions\n" + self.ITEM + "\n" + self.PARA + "\n").encode()

    def base(self):
        p = inv_base()
        p["meta"]["sources"] = {"task": {"file": "t.txt"}}
        p["stages"]["s"]["content"] = [{"id": "q", "value": self.ITEM,
                                        "cite": {"label": "verbatim", "source": "task"}}]
        return p

    def entry_points(self):
        """name -> fn(text) -> True when the text is caught. One per comparison entry point."""
        ix = release.HeldIndex([self.ITEM])
        proj, _ = project_t(self.base(), {"task": LINK_T}, sources={"task": self.src()})

        def screen(t):
            p = self.base()
            p["data"] = {"v": {"text": t}}
            try:
                project_t(p, {"task": LINK_T}, sources={"task": self.src()})
            except release.ProjectionError:
                return True
            return False

        def note(t):
            p = self.base()
            p["meta"]["notes"] = t
            pr, _ = project_t(p, {"task": LINK_T}, sources={"task": self.src()})
            return pr["meta"]["notes"] != t

        def literal(t):
            p = self.base()
            p["vars"] = {"x": t}
            try:
                project_t(p, {"task": LINK_T}, sources={"task": self.src()})
            except release.ProjectionError:
                return True
            return False
        def flow_in(t):
            p = self.base()
            p["flow"]["seq"].append({"for": "w", "in": [t], "do": {"stage": "s"}})
            try:
                project_t(p, {"task": LINK_T}, sources={"task": self.src()})
            except release.ProjectionError:
                return True
            return False

        def expr_lit(t):
            p = self.base()
            p["stages"]["s"]["content"].append({"id": "e", "value": {"expr": "'x' if True else " + json.dumps(t)}})
            try:
                project_t(p, {"task": LINK_T}, sources={"task": self.src()})
            except release.ProjectionError:
                return True
            return False
        return {
            "_literals: flow in": flow_in,
            "_literals: expr": expr_lit,
            "hit (held item)": lambda t: ix.hit(t) is not None,
            "shares (held item)": lambda t: ix.shares(t, 23),
            "text_file (held item)": lambda t: not ix.text_file(t.encode()),
            "found_in: uncited on screen": screen,
            "found_in: operator note": note,
            "quote(): scanned JSON": lambda t: not release.distributable("effects.json", proj, json.dumps({"n": t}),
                                                                         sources={"task": self.src()}),
            "_literals: vars": literal,
        }

    def test_every_entry_point_catches_every_variant(self):
        for name, caught in self.entry_points().items():
            text = self.ITEM if "held item" in name else self.PARA
            for vname, v in self.variants(text).items():
                self.assertTrue(caught(v), "%s missed the %s variant" % (name, vname))

    def test_every_entry_point_goes_through_forms(self):
        calls = []
        real = release._forms

        def counting(s):
            calls.append(s)
            return real(s)
        release._forms = counting
        try:
            for name, caught in self.entry_points().items():
                text = self.ITEM if "held item" in name else self.PARA
                del calls[:]
                caught(self.variants(text)["nbsp"])
                self.assertTrue(calls, "%s did not call release._forms" % name)
        finally:
            release._forms = real

    def test_forms_unescape_until_stable(self):
        forms = release._forms("a&amp;amp;amp;amp;amp;nbsp;b")   # five rounds of escaping
        self.assertEqual(forms[-1], "a\xa0b")                       # unescaped until stable
        self.assertEqual(len(forms), 7)                               # raw + 6 unescape rounds
        self.assertEqual(release._forms("&amp;" * 1 + "lt;"), ["&amp;lt;", "&lt;", "<"])
        deep = "a" + "&amp;" + "amp;" * 12 + "lt;b"               # deeper than the cap: stops at 8 rounds
        self.assertEqual(len(release._forms(deep)), 9)
        self.assertEqual(release._forms("x <br> y"), ["x <br> y", "x   y"])   # a tag becomes a space

    def test_held_text_in_engine_computed_strings_is_an_error(self):
        p = self.base()
        p["vars"] = {"x": self.ITEM}
        with self.assertRaises(release.ProjectionError):
            project_t(p, {"task": LINK_T}, sources={"task": self.src()})

    def test_partial_copy_on_screen(self):
        item = "I don't think it's fair that they're paid more than we're paid for the same work"
        for part in ("I don't think it's fair that they're paid more",
                     "I don&#39;t think it&#39;s fair that they&#39;re paid more"):
            p = inv_base()
            p["meta"]["sources"] = {"task": {"file": "t.txt"}}
            p["stages"]["s"]["content"] = [{"id": "q", "value": item, "cite": {"label": "verbatim", "source": "task"}},
                                           {"id": "r", "value": part}]
            with self.assertRaises(release.ProjectionError, msg=part):
                project_t(p, {"task": LINK_T}, sources={"task": ("Instructions\n" + item + "\n").encode()})


# ------------------------------------------------------------------------------------------- review round 16
class TestComputedRegistry(unittest.TestCase):
    """Distribution review round 15 (probes mf1, r1-r3, invented text): one registry of computed positions
    (release.COMPUTED). Every entry: raw source text there is a strict error, a non-source string ships unchanged."""

    ITEM = "I feel lonely even with others around me"
    PARA = ("Each participant received an endowment of twelve tokens and decided privately how many of them to "
            "keep for themselves this round")
    OTHER = "Another made-up phrase entirely"

    def src(self):
        return ("Instructions\n" + self.ITEM + "\n" + self.PARA + "\nOther line here.\n").encode()

    def near_copies(self):
        w = self.PARA.split(" ", 1)
        return {"exact": self.PARA, "prefix": "Scenario: " + self.PARA, "suffix": self.PARA + " (paraphrase)",
                "comma": w[0] + ", " + w[1], "fragment80": self.PARA[:80] + " xyz"}

    def base(self):
        p = inv_base()
        p["meta"]["sources"] = {"task": {"file": "t.txt"}}
        p["stages"]["s"]["content"] = [{"id": "q", "value": self.ITEM,
                                        "cite": {"label": "verbatim", "source": "task"}}]
        return p

    @staticmethod
    def expr(t):
        return "answer('s.q') == %s" % json.dumps(t)

    # one concrete position per registry entry: (pattern, setter(protocol, text) -> JSON pointer of the string)
    def positions(self):
        E = self.expr

        def at(path, value):
            def setter(p, t):
                node = p
                for k in path[:-1]:
                    node = node.setdefault(k, {}) if isinstance(k, str) else node[k]
                node[path[-1]] = value(t)
                return path
            return setter

        def flow(node_of):
            def setter(p, t):
                node, ptr = node_of(t)
                p["flow"]["seq"].append(node)
                return ["flow", "seq", len(p["flow"]["seq"]) - 1] + ptr
            return setter
        return [
            (("vars", "**"), at(["vars", "x"], lambda t: t)),
            (("**", "expr"), lambda p, t: (p["stages"]["s"]["content"].append({"id": "e", "value": {"expr": E(t)}}),
                                          ["stages", "s", "content", 1, "value", "expr"])[1]),
            (("**", "if"), lambda p, t: (p["stages"]["s"]["content"][0].__setitem__("if", E(t)),
                                        ["stages", "s", "content", 0, "if"])[1]),
            (("**", "until"), flow(lambda t: ({"repeat": {"stage": "s"}, "until": E(t), "max": 2, "on_max": "flag"},
                                              ["until"]))),
            (("**", "pending_if"), lambda p, t: (p.__setitem__("exclusions", [{"id": "x", "if": "False",
                                                                                 "pending_if": E(t)}]),
                                                ["exclusions", 0, "pending_if"])[1]),
            (("**", "if_valid"), lambda p, t: (p["stages"]["s"].__setitem__("validate_page", [{"if_valid": E(t)}]),
                                              ["stages", "s", "validate_page", 0, "if_valid"])[1]),
            (("coding", "*", "apply"), at(["coding", "rule", "apply"], E)),
            (("flow", "**", "in", "**"), flow(lambda t: ({"for": "w", "in": [t], "do": {"stage": "s"}}, ["in", 0]))),
            (("flow", "**", "let", "*"), flow(lambda t: ({"for": "w", "in": [1], "let": {"z": t},
                                                          "do": {"stage": "s"}}, ["let", "z"]))),
            (("flow", "**", "set", "*"), flow(lambda t: ({"set": {"z": t}}, ["set", "z"]))),
            (("flow", "**", "loop"), flow(lambda t: ({"loop": E(t), "do": {"stage": "s"}}, ["loop"]))),
            (("flow", "**", "compute", "*"), flow(lambda t: ({"sync": "g", "compute": {"v": E(t)}}, ["compute", "v"]))),
            (("units", "*", "fields", "*"), at(["units", "u", "fields", "f"], E)),
            (("keyed", "answers", "*"), lambda p, t: (p.__setitem__("keyed", {"answers": {"s.q": E(t)}}),
                                                      ["keyed", "answers", "s.q"])[1]),
            (("**", "population", "values"),
             lambda p, t: (p.__setitem__("exclusions", [{"id": "x", "population": {"values": E(t), "rule": "iqr_fence",
                                                                                 "after_exclusions": []}}]),
                           ["exclusions", 0, "population", "values"])[1]),
            (("**", "population", "group_by"),
             lambda p, t: (p["analysis"]["effects"].append({"id": "e", "population": {"group_by": E(t)}}),
                           ["analysis", "effects", 0, "population", "group_by"])[1]),
        ]

    def test_non_computed_neighbours_are_not_computed(self):
        # a data key called "while", population ids, a cite note: not evaluated, so not in the registry
        self.assertFalse(release._computed(["data", "while", "text"]))
        self.assertFalse(release._computed(["exclusions", 0, "population", "after_exclusions", 0]))
        self.assertTrue(release._computed(["analysis", "effects", 0, "population", "group_by"]))

    def test_every_registry_entry_has_a_position(self):
        self.assertEqual(sorted(pat for pat, _ in self.positions()), sorted(release.COMPUTED))

    def test_source_text_errors_and_other_text_ships(self):
        for pattern, setter in self.positions():
            for name, text in dict(self.near_copies(), held_item=self.ITEM).items():
                p = self.base()
                path = setter(p, text)
                self.assertTrue(release._computed(path), (pattern, path))
                with self.assertRaises(release.ProjectionError, msg="%s / %s" % (pattern, name)):
                    project_t(p, {"task": LINK_T}, sources={"task": self.src()})
            p = self.base()
            path = setter(p, self.OTHER)
            proj, _ = project_t(p, {"task": LINK_T}, sources={"task": self.src()})
            got, want = proj, p
            for k in path:
                got, want = got[k], want[k]
            self.assertEqual(got, want, pattern)   # never held, never withheld

    def test_computed_position_never_held_even_when_cited(self):
        p = self.base()   # a cited dict under vars and a data `if` string are computed: errors, not placeholders
        p["vars"] = {"x": {"text": self.ITEM, "cite": {"label": "verbatim", "source": "task"}}}
        with self.assertRaises(release.ProjectionError):
            project_t(p, {"task": LINK_T}, sources={"task": self.src()})
        p = self.base()
        p["data"]["d"] = {"text": "Other line here.", "if": "True",
                          "cite": {"label": "verbatim", "source": "task"}}
        proj, _ = project_t(p, {"task": LINK_T}, sources={"task": self.src()})
        self.assertEqual(proj["data"]["d"]["if"], "True")

    def test_cites_under_computed_positions_are_operator_text(self):
        p = self.base()   # a cite's quote under vars is held / withheld like any cite, never refused
        p["vars"] = {"endowment": 12, "endowment_cite": {"label": "reported", "source": "task",
                                                         "quote": self.PARA}}
        proj, _ = project_t(p, {"task": LINK_T}, sources={"task": self.src()})
        self.assertNotIn("endowment of twelve", json.dumps(proj["vars"]))
        self.assertEqual(proj["vars"]["endowment"], 12)

    def test_keys_and_images_at_computed_positions(self):
        p = self.base()
        p["vars"] = {self.PARA: 1}
        with self.assertRaisesRegex(release.ProjectionError, "dict key"):
            project_t(p, {"task": LINK_T}, sources={"task": self.src()})
        p = self.base()
        p["vars"] = {"the partner's choice": 1}   # a key wholly in the source (>= 12 characters)
        with self.assertRaisesRegex(release.ProjectionError, "dict key"):
            project_t(p, {"task": LINK_T}, sources={"task": self.src() + b"Then the partner's choice was shown.\n"})
        p = self.base()
        p["flow"]["seq"].append({"for": "f", "in": [{"src": "artifacts/face1.png",
                                                    "cite": {"label": "verbatim", "source": "task"}}],
                                 "do": {"stage": "s"}})
        with self.assertRaisesRegex(release.ProjectionError, "image"):
            project_t(p, {"task": LINK_T}, sources={"task": self.src()})

    def test_data_is_never_computed(self):
        for key in ("if", "until", "apply", "while"):
            self.assertFalse(release._computed(["data", "frames", key]), key)
        self.assertFalse(release._computed(["data", "demog", "population", "values"]))
        p = self.base()
        p["data"]["frames"] = {"if": {"text": "Other line here.", "cite": {"label": "verbatim", "source": "task"}}}
        proj, _ = project_t(p, {"task": LINK_T}, sources={"task": self.src()})
        self.assertEqual(set(proj["data"]["frames"]["if"]["text"]), {D.PLACEHOLDER})   # held as data text

    def test_author_chosen_names(self):
        # names are neither keywords nor cite / note keys, in both directions
        for path in (["vars", "bonus_note"], ["units", "u", "fields", "score_note"], ["coding", "open_note", "apply"],
                     ["flow", "seq", 0, "let", "trial_note"], ["flow", "seq", 0, "set", "n_notes"]):
            self.assertTrue(release._computed(path), path)
        for path in (["stages", "apply", "content", 0, "value"], ["stages", "if", "content", 0, "value"],
                     ["stages", "expr", "content", 0, "value"], ["units", "apply", "per"], ["coding", "if", "cases"],
                     ["analysis", "effects", 0, "apply"]):
            self.assertFalse(release._computed(path), path)
        self.assertFalse(release._computed(["vars", "endowment_cite", "quote"]))   # the `<name>_cite` convention
        p = self.base()
        p["vars"] = {"bonus_note": self.PARA}
        with self.assertRaises(release.ProjectionError):
            project_t(p, {"task": LINK_T}, sources={"task": self.src()})
        p = self.base()
        p["coding"] = {"open_note": {"apply": "'job' if %s in text else 'other'" % json.dumps("Hint: " + self.PARA)}}
        with self.assertRaises(release.ProjectionError):
            project_t(p, {"task": LINK_T}, sources={"task": self.src()})
        p = self.base()
        p["stages"]["apply"] = {"content": [{"id": "q", "value": self.PARA, "cite": {"label": "verbatim",
                                                                                     "source": "task"}}],
                                "responses": [], "presentation": {"advance": "self"}}
        proj, _ = project_t(p, {"task": LINK_T}, sources={"task": self.src()})
        self.assertEqual(set(proj["stages"]["apply"]["content"][0]["value"]), {D.PLACEHOLDER})

    def test_display_text_is_never_parsed_as_python(self):
        for item in ('"I feel lonely even with others around me" (R)', '"I feel lonely even with others around me" [R]',
                     '"I feel lonely even with others around me" - Anon', '"I feel lonely even with others around me" (1)'):
            p = self.base()
            p["stages"]["s"]["content"][0]["value"] = item
            proj, _ = project_t(p, {"task": LINK_T}, sources={"task": ("Instructions\n" + item + "\n").encode()})
            self.assertEqual(len(proj["distribution"]["held"]), 1, item)

    def test_cjk_near_copies_at_computed_positions(self):
        items = ["我经常感到孤独即使身边有人", "我觉得自己与他人疏远了", "我很难找到可以交谈的人"]
        src = ("量表\n" + "\n".join(items) + "\n").encode()
        for variant in (items, ["1. " + items[0]], [items[0] + "（反向）"], [items[1][:9]]):
            p = self.base()
            p["flow"]["seq"].append({"for": "item", "in": list(variant), "do": {"stage": "s"}})
            with self.assertRaises(release.ProjectionError, msg=str(variant)):
                project_t(p, {"task": LINK_T}, sources={"task": self.src() + src})
        p = self.base()
        p["vars"] = {"x": "".join(chr(0x4e00 + i) for i in range(7))}   # unrelated CJK: ships
        project_t(p, {"task": LINK_T}, sources={"task": self.src() + src})

    def test_joined_literal_pieces(self):
        pieces = [self.PARA[i:i + 10] for i in range(0, 60, 10)]
        p = self.base()
        p["vars"] = {"x": {"expr": " + ".join(json.dumps(x) for x in pieces)}}
        with self.assertRaises(release.ProjectionError):
            project_t(p, {"task": LINK_T}, sources={"task": self.src()})

    # display specs: evaluated only through `.ev(X["k"])`, which evaluates nothing but an {"expr"} dict (covered by
    # **/expr) and shows a literal as it is. A raw `{"expr": X["k"]}` / `evaluate(X["k"])` site gets no exemption.
    DISPLAY = {"value", "text", "prefill", "options", "button", "equals", "label", "instruction", "events"}
    # where each engine / checks variable sits in a protocol (coverage is checked on this path, not on key names)
    CONTEXT = {"node": ["flow", "seq", 0], "it": ["stages", "s", "content", 0], "r": ["stages", "s", "responses", 0],
               "pres": ["stages", "s", "presentation"], "v": ["stages", "s", "validate_page", 0],
               "acc": ["stages", "s", "responses", 0, "validate"], "ex": ["exclusions", 0],
               "spec": ["exclusions", 0, "population"], "u": ["units", "u"], "c": ["coding", "rule"],
               "keyed": ["keyed", "answers"]}

    @classmethod
    def evaluated_sites(cls, src):
        """(kind, variable, key) of every evaluation site in a source text:
          ev        `.ev(X["k"])` / `.ev(X.get("k"))`                     (a display spec may be exempt)
          raw       `{"expr": X["k"]}`, `evaluate(X["k"])`                 (must be COMPUTED)
          iter      `for n, spec in X["k"].items()` … ev(spec) / {"expr": spec}   (children must be COMPUTED)
          list      `… for c in X["k"]` … ev({"expr": c}) / evaluate(c)  (items must be COMPUTED)
          indirect  `c = X.get("k")` … ev({"expr": c}) / evaluate(c)      (must be COMPUTED)
          keyed     `ev({"expr": keyed[...]})`                             (keyed answers)
        Not seen (documented): evaluation through a helper function taking the protocol node, or through names that
        reach `ev` across more than a few lines."""
        sites = set()
        for v, k in re.findall(r'\.ev\((\w+)(?:\[|\.get\()"(\w+)"', src):
            sites.add(("ev", v, k))
        for v, k in re.findall(r'\{"expr": (\w+)(?:\[|\.get\()"(\w+)"', src) + \
                re.findall(r'evaluate\((\w+)(?:\[|\.get\()"(\w+)"', src):
            sites.add(("raw", v, k))
        lines = src.splitlines()
        for i, line in enumerate(lines):
            window = "\n".join(lines[i:i + 4])
            m = re.search(r'for \w+, (\w+) in \(?(\w+)(?:\[|\.get\()"(\w+)"', line)
            if m and re.search(r'(?:ev\((?:\{"expr": )?|evaluate\()%s\b' % m.group(1), window):
                sites.add(("iter", m.group(2), m.group(3)))
            m = re.search(r'for (\w+) in \(?(\w+)(?:\[|\.get\()"(\w+)"', line)
            if m and re.search(r'(?:\{"expr": |evaluate\()%s\b(?!\[)' % m.group(1), window):
                sites.add(("list", m.group(2), m.group(3)))
            m = re.search(r'(\w+) = (\w+)(?:\[|\.get\()"(\w+)"', line)
            if m and re.search(r'(?:\{"expr": |evaluate\()%s\b(?!\[)' % m.group(1), "\n".join(lines[i:i + 10])):
                sites.add(("indirect", m.group(2), m.group(3)))
        if re.search(r'\{"expr": keyed\[', src):
            sites.add(("keyed", "keyed", "*"))
        return sites

    @classmethod
    def uncovered(cls, sites):
        out = []
        for kind, var, key in sorted(sites):
            if key == "expr" or (kind == "ev" and key in cls.DISPLAY):
                continue
            ctx = cls.CONTEXT.get(var)
            if ctx is None:
                out.append((kind, var, key, "unknown variable: add it to CONTEXT"))
                continue
            path = ctx + {"iter": [key, "x"], "list": [key, 0], "keyed": ["x"]}.get(kind, [key])
            if not release._computed(path):
                out.append((kind, var, key, "/".join(map(str, path))))
        return out

    def engine_sources(self):
        import pathlib
        here = pathlib.Path(release.__file__).parent
        return {n: (here / n).read_text(encoding="utf-8") for n in ("engine.py", "checks.py")}

    def test_registry_matches_engine(self):
        sites = set()
        for src in self.engine_sources().values():
            sites |= self.evaluated_sites(src)
        keys = {k for _, _, k in sites}
        self.assertTrue({"if", "until", "if_valid", "pending_if", "values", "group_by", "fields", "compute", "in",
                         "loop", "let", "set", "apply", "*"} <= keys, keys)   # the parser finds today's sites
        self.assertEqual(self.uncovered(sites), [], "engine / checks evaluate positions COMPUTED does not cover")

    def test_drift_parser_sees_new_sites(self):
        # hypothetical future engine lines: each must be reported, by path, not by key name
        for snippet in ('if self.ev({"expr": it["label"]}, b):',
                        'ok = all(self.ev({"expr": c}, b) for c in node["checks"])',
                        'cond = node.get("while")\n            if self.ev({"expr": cond}, b):',
                        'v = evaluate(r["text"], names)',
                        'n = self.ev({"expr": it["values"]}, b)',
                        'x = self.ev(node["times"], b)'):
            self.assertTrue(self.uncovered(self.evaluated_sites(snippet)), snippet)


# ------------------------------------------------------------------------------------------- review round 18
class TestCJKRuns(unittest.TestCase):
    """Distribution review round 18 (probes rev18/p1-p5, invented text): one run / whole rule on the skeleton
    (release.SourceRuns, release._cjk_window) for every entry point; cites by value; concatenations only."""

    ITEMS = {"comma": "我常担心，别人怎么看我", "comma2": "有时，我觉得很无助。", "digit": "过去7天我睡得不好。",
             "latin": "我用AI写过作业。", "digit2": "我在第3题犹豫了。", "fullwidth": "过去７天我睡得不好。",
             "question": "你是否感到紧张？"}

    def src(self):
        return ("量表\n" + "\n".join(self.ITEMS.values()) + "\n").encode()

    def base(self):
        p = inv_base()
        p["meta"]["sources"] = {"task": {"file": "t.txt"}}
        return p

    def refused(self, p):
        try:
            project_t(p, {"task": LINK_T}, sources={"task": self.src()})
        except release.ProjectionError:
            return True
        return False

    def test_every_entry_point_every_variant(self):
        for name, item in self.ITEMS.items():
            variants = {"as printed": item, "no final mark": item.rstrip("。？"), "trailing 。": item.rstrip("。？") + "。"}
            for vname, v in variants.items():
                tag = "%s / %s" % (name, vname)
                for where, put in (("vars", lambda p, t: p.__setitem__("vars", {"x": t})),
                                   ("flow in", lambda p, t: p["flow"]["seq"].append(
                                       {"for": "i", "in": [t], "do": {"stage": "s"}})),
                                   ("expr", lambda p, t: p["stages"]["s"]["content"].append(
                                       {"id": "e", "value": {"expr": "'x' if True else " + json.dumps(t)}})),
                                   ("units field", lambda p, t: p.__setitem__(
                                       "units", {"u": {"per": "session", "fields": {"f": "answer('s.q') == %s"
                                                                                       % json.dumps(t)}}})),
                                   ("dict key", lambda p, t: p.__setitem__("vars", {t: 1})),
                                   ("uncited data", lambda p, t: p["data"].__setitem__("d", {"text": t}))):
                    p = self.base()
                    put(p, v)
                    self.assertTrue(self.refused(p), "%s at %s shipped" % (tag, where))
                if vname == "as printed":   # cited on screen: held (a variant is not the printed text to locate)
                    p = self.base()
                    p["stages"]["s"]["content"] = [{"id": "q", "value": v,
                                                    "cite": {"label": "verbatim", "source": "task"}}]
                    proj, _ = project_t(p, {"task": LINK_T}, sources={"task": self.src()})
                    self.assertEqual(set(proj["stages"]["s"]["content"][0]["value"]), {D.PLACEHOLDER}, tag)
                p = self.base()   # an operator note embedding it: withheld or held (8+ CJK skeleton characters)
                p["meta"]["notes"] = "条目：" + v
                proj, _ = project_t(p, {"task": LINK_T}, sources={"task": self.src()})
                if len(release._skel(v)) >= 8:
                    self.assertNotEqual(proj["meta"]["notes"], "条目：" + v, tag)
                self.assertFalse(release.distributable("effects.json", proj, json.dumps({"n": v}, ensure_ascii=False),
                                                       sources={"task": self.src()}), tag)
                ix = release.HeldIndex([item])
                self.assertEqual(ix.hit(v), "whole", tag)
                self.assertFalse(ix.text_file(("附录：" + v).encode()), tag)

    def test_unrelated_cjk_ships(self):
        p = self.base()
        p["vars"] = {"x": "完全无关的另一句话在这里"}
        self.assertFalse(self.refused(p))

    def test_cites_by_value_and_keyed_names(self):
        para = "Each participant received an endowment of twelve tokens and kept some"
        src = ("Instructions\n" + para + "\n").encode()
        expr = "answer('s.q') == %s" % json.dumps("Note: " + para)
        for put in (lambda p: p.__setitem__("units", {"u": {"per": "session", "fields": {"n_cites": expr}}}),
                    lambda p: p.__setitem__("coding", {"source_cite": {"apply": expr}}),
                    lambda p: p.__setitem__("keyed", {"answers": {"s.r_note": expr}}),
                    lambda p: p.__setitem__("vars", {"tbl": {"cite": para}})):
            p = self.base()
            put(p)
            with self.assertRaises(release.ProjectionError):
                project_t(p, {"task": LINK_T}, sources={"task": src})
        p = self.base()   # a real cite (by value) under vars stays operator text
        p["vars"] = {"k": 3, "k_cite": {"label": "verbatim", "source": "task", "quote": para}}
        proj, _ = project_t(p, {"task": LINK_T}, sources={"task": src})
        self.assertNotIn("endowment", json.dumps(proj["vars"]))

    def test_only_concatenations_are_joined(self):
        src = b"Scale\nNot at all      Very much\n"
        for expr in ("'Not at all' if i < 4 else 'Very much'", "['Not at all', 'Very much'][i]"):
            p = self.base()
            p["flow"]["seq"].append({"for": "i", "in": [1, 5], "let": {"lab": {"expr": expr}}, "do": {"stage": "s"}})
            project_t(p, {"task": LINK_T}, sources={"task": src})   # ships: no concatenation
        for expr in ("'Not at all' + 'Very much'", "join(' ', ['Not at all', 'Very much'])"):
            p = self.base()
            p["vars"] = {"x": {"expr": expr}}
            with self.assertRaises(release.ProjectionError, msg=expr):
                project_t(p, {"task": LINK_T}, sources={"task": src})

    def test_bare_constant_expression(self):
        item = "I worry about my future."
        for expr in (json.dumps(item), '"I " "worry " "about " "my " "future."'):
            p = self.base()
            p["flow"]["seq"].append({"for": "i", "in": [1], "let": {"t": {"expr": expr}}, "do": {"stage": "s"}})
            with self.assertRaises(release.ProjectionError, msg=expr):
                project_t(p, {"task": LINK_T}, sources={"task": ("Q\n" + item + "\n").encode()})


# ------------------------------------------------------------------------------------------- review round 19
def displayed_states(prot, n=4, seed=0):
    """Every State the engine shows for n random sessions per arm (JSON text): what participants would see."""
    import random as _random
    env = Env(Protocol(copy.deepcopy(prot)))
    out, rng = [], _random.Random(seed)
    for spec in env.design(n=n, seed=seed):   # every arm
        s = env.open(spec)
        st = s.reset()
        for _ in range(200):
            if not isinstance(st, dict) or st.get("done"):
                break
            out.append(json.dumps(st, ensure_ascii=False, default=str))
            try:
                st = s.step(checks.random_answers(st, rng))
            except Exception:   # noqa: BLE001 - a fixture that cannot be stepped: what was shown is enough
                break
    return out


class TestNoWithheldOnScreen(unittest.TestCase):
    """The invariant behind round 19's M1: whatever the engine displays never rehydrates to `withheld:` — a string
    that would be shown is held (restorable) or refused, never withheld."""

    S1 = "(This screen is shown only to online panel members, not to students.)"

    def cases(self):
        src = ("Procedure\n" + self.S1 + "\n").encode()
        near = self.S1.replace("students", "pupils")
        out = []
        for key in ("panel_note", "panel_msg"):   # round 19 B: a note-named data string the screen shows
            p = inv_base()
            p["meta"]["sources"] = {"task": {"file": "t.txt"}}
            p["stages"]["s"]["content"] = [{"id": "n", "value": {"expr": "data['%s']" % key}}]
            p["data"][key] = near
            out.append(("data %s near-copy" % key, p, {"task": LINK_T}, {"task": src}, {}, {}))
        p = inv_base()
        p["meta"]["sources"] = {"task": {"file": "t.txt"}}
        p["stages"]["s"]["content"] = [{"id": "n", "value": {"expr": "data['stim']['note']"}}]
        p["data"]["stim"] = {"note": near}
        out.append(("data stim.note", p, {"task": LINK_T}, {"task": src}, {}, {}))
        p = inv_base()
        p["meta"]["sources"] = {"task": {"file": "t.txt"}}
        p["stages"]["s"]["content"] = [{"id": "n", "value": {"expr": "data['cn_note']"}}]
        p["data"]["cn_note"] = "注：本页仅向线上样本显示，学生看不到。"
        out.append(("data cn_note", p, {"task": LINK_T},
                    {"task": "说明\n注：本页仅向在线样本显示，学生看不到。\n".encode()}, {}, {}))
        p = inv_base()   # a news stimulus shaped like a cite (round 19 S2)
        p["meta"]["sources"] = {"task": {"file": "t.txt"}}
        p["stages"]["s"]["content"] = [{"id": "n", "value": {"expr": "data['news']['headline']"}}]
        p["data"]["news"] = {"headline": near, "source": "citynews.example", "label": "reported"}
        out.append(("data cite-shaped stimulus", p, {"task": LINK_T}, {"task": src}, {}, {}))
        # pass-through shapes the engine shows (round 20 S1): notes / cites inside spans, widget_params, columns,
        # anchors, rich-text suffix / na_option
        r = {"id": "r", "kind": "scale", "prompt": "Rate it", "required": False,
             "options": [{"code": 1, "label": "1"}, {"code": 2, "label": "2"}],
             "widget_params": {"help_note": near, "rows": 3}, "columns": [{"label": "A", "note": near}],
             "anchors": {"left": "low", "right": "high", "note": near},
             "suffix": {"text": "dollars", "cite": {"label": "reported", "source": "task", "quote": near}},
             "na_option": {"text": "n/a", "note": near}}
        p = inv_base()
        p["meta"]["sources"] = {"task": {"file": "t.txt"}}
        p["stages"]["s"]["content"] = [{"id": "t", "value": {"text": "Please rate the panel.",
                                                             "spans": [{"start": 0, "end": 6, "note": near}]}}]
        p["stages"]["s"]["responses"] = [r]
        out.append(("pass-through dicts", p, {"task": LINK_T}, {"task": src}, {}, {}))
        out.append(("main fixture", protocol(), TIERS, SOURCES, PDF, None))
        return out

    def test_displayed_text_never_withheld(self):
        for name, p, tiers, srcs, ex, items in self.cases():
            try:
                proj, _ = project_t(p, tiers, sources=srcs, extractors=ex or {})
            except release.ProjectionError:
                continue   # refused: nothing ships
            if items is None:   # the main fixture: supply the image reading
                items = {k: "SKY AHEAD" for k, e in proj["distribution"]["held"].items()
                         if e.get("locator", {}).get("format") == "image_reading"}
            out, _ = hsenv.rehydrate(proj, fetch=FakeFetch({URL: MATERIALS}), files=dict(srcs), items=items,
                                     extractors=ex or {})
            for st in displayed_states(out):
                self.assertNotIn(D.WITHHELD, st, name)
            for path, cont, key, cf, kind in release._slots(out):
                if kind != "image":
                    self.assertFalse(str(cont[key]).startswith(D.WITHHELD), (name, path))

    def test_engine_never_shows_cites_or_notes(self):
        # even before any projection, a State never carries a cite or a note key
        p = self.cases()[-2][1]
        for st in displayed_states(p):
            for bad in ('"note"', '"help_note"', '"cite"', '"quote"'):
                self.assertNotIn(bad, st)

    def test_note_named_data_is_material(self):
        src = ("Procedure\n" + self.S1 + "\n").encode()
        near = self.S1.replace("students", "pupils")
        for data in ({"panel_note": near}, {"stim": {"note": near}}):
            p = inv_base()
            p["meta"]["sources"] = {"task": {"file": "t.txt"}}
            p["data"] = data
            with self.assertRaisesRegex(release.ProjectionError, "without a cite"):
                project_t(p, {"task": LINK_T}, sources={"task": src})
        self.assertFalse(release._operator(["data", "panel_note"], frozenset()))
        self.assertFalse(release._operator(["vars", "bonus_note"], frozenset()))
        self.assertTrue(release._operator(["stages", "s", "presentation", "note"], frozenset()))
        self.assertTrue(release._operator(["flow", "seq", 0, "note"], frozenset()))

    def test_cjk_with_a_latin_word_and_digit_scales(self):
        item = "我使用ChatGPT写作业"
        src = ("量表\n" + item + "\n").encode()
        for put in (lambda p: p["flow"]["seq"].append({"for": "i", "in": [item + "（反向计分）"], "do": {"stage": "s"}}),
                    lambda p: p["data"].__setitem__("d", {"text": "第3题：" + item})):
            p = inv_base()
            p["meta"]["sources"] = {"task": {"file": "t.txt"}}
            put(p)
            with self.assertRaises(release.ProjectionError):
                project_t(p, {"task": LINK_T}, sources={"task": src})
        scale = (" ".join(str(i) for i in range(1, 21)) + "\n").encode()
        for put in (lambda p: p.__setitem__("exclusions", [{"id": "x", "if": "answer('s.q') in [%s]" %
                                                            ", ".join(str(i) for i in range(1, 18))}]),
                    lambda p: p.__setitem__("vars", {"x": " ".join(str(i) for i in range(1, 17))})):
            p = inv_base()
            p["meta"]["sources"] = {"task": {"file": "t.txt"}}
            put(p)
            project_t(p, {"task": LINK_T}, sources={"task": scale})   # digits alone are not a quote


# ------------------------------------------------------------------------------------------- review round 20
class TestReviewRound20(unittest.TestCase):
    """Distribution review round 20 (READY; should-fixes, invented text)."""

    def test_every_source_is_confirmed(self):
        # a window shared by two sources: the run is confirmed against each (source b holds the item)
        item = "nobody around me really understands me at all"
        sk = release._skel(item)
        srcs = {"a": (sk[10:30] + "\n").encode(), "b": (item + "\n").encode()}
        p = inv_base()
        p["meta"]["sources"] = {"a": {"file": "a.txt"}, "b": {"file": "b.txt"}}
        p["data"]["d"] = {"text": "Our own preface words: " + item[8:]}
        with self.assertRaises(release.ProjectionError):
            project_t(p, {"a": LINK_T, "b": LINK_T}, sources=srcs)
        runs = release.SourceRuns([("a", sk[10:30]), ("b", item)])
        self.assertEqual(runs.found("Our own preface words: " + item[8:]), "b")

    def test_common_cjk_phrases_ship_and_near_copies_refuse(self):
        src = ["在过去12个月里，你在网上购物的次数是多少？", "你每天使用TikTok的时间大约有多长？", "请用1-10分评价你对AI的信任程度。",
               "我觉得使用ChatGPT写作业是作弊。", "你是否在2020年以后使用过VPN软件？", "请根据你的真实情况在0到100之间打分。"]
        data = ("问卷\n" + "\n".join(src) + "\n").encode()
        for ours in ("被试报告过去12个月里网购次数的中位数", "每天使用TikTok时长（分钟）", "信任AI的程度用1-10分测量",
                     "使用ChatGPT写作业的比例", "在2020年以后注册的用户", "在0到100之间的整数"):
            p = inv_base()
            p["meta"]["sources"] = {"task": {"file": "t.txt"}}
            p["vars"] = {"x": ours}
            project_t(p, {"task": LINK_T}, sources={"task": data})   # ships: our own wording
        for near in ("你每天使用TikTok的时间大概有多长", "我认为使用ChatGPT写作业是作弊"):
            p = inv_base()
            p["meta"]["sources"] = {"task": {"file": "t.txt"}}
            p["vars"] = {"x": near}
            with self.assertRaises(release.ProjectionError, msg=near):
                project_t(p, {"task": LINK_T}, sources={"task": data})

    def test_run_shared_by_many_sources_is_fast(self):
        import random as _random
        import time
        rng = _random.Random(1)
        words = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho".split()
        common = "pleaseanswerallquestions"[:21]   # a 21-character run in every source

        def para(n):
            return " ".join(rng.choice(words) + str(rng.randint(0, 999)) for _ in range(n))
        runs = release.SourceRuns([("s%d" % i, (para(600) + " " + common + " ") * 3) for i in range(40)])
        text = " | ".join("qq" + common + "zzz%d" % i for i in range(150))
        t = time.time()
        self.assertIsNone(runs.found(text))   # 21 < 23: no quote, and found() stays fast
        self.assertLess(time.time() - t, 2.0)

    def test_run_found_through_a_digit_only_piece(self):
        # the only indexed 20-character piece of this lettered run is all digits; it must still be found
        runs = release.SourceRuns([("s", "wxyz12345678901234567890 mmmm thequickbrownfoxjump kkkk")])
        self.assertEqual(runs.found("xyz12345678901234567890 | AAthequickbrownfoxjumpBB"), "s")
        self.assertEqual(runs.found("12345678901234567890123 alone"), None)   # digits only: not a quote

    def test_cjk_with_latin_letters_five_cjk(self):
        src = "问卷\n我每周至少用3次Q音乐App听歌。\n你更喜欢今天得到50元还是30天后得到80元？\n".encode()
        p = inv_base()
        p["meta"]["sources"] = {"task": {"file": "t.txt"}}
        p["vars"] = {"x": "我每周至少用4次Q音乐App听歌"}
        with self.assertRaises(release.ProjectionError):
            project_t(p, {"task": LINK_T}, sources={"task": src})
        for ours in ("选择今天得到50元的比例", "在0到100之间", "过去12个月里"):
            p = inv_base()
            p["meta"]["sources"] = {"task": {"file": "t.txt"}}
            p["vars"] = {"x": ours}
            project_t(p, {"task": LINK_T}, sources={"task": src})

    def test_presentation_cite(self):
        p = inv_base()
        p["meta"]["sources"] = {"task": {"file": "t.txt"}}
        p["stages"]["s"]["presentation"] = {"advance": "self", "button": "Continue to the next page",
                                            "cite": {"label": "verbatim", "source": "task"}}
        proj, _ = project_t(p, {"task": LINK_T}, sources={"task": b"Footer\nContinue to the next page\n"})
        self.assertEqual(set(proj["stages"]["s"]["presentation"]["button"]), {D.PLACEHOLDER})


if __name__ == "__main__":
    unittest.main()
