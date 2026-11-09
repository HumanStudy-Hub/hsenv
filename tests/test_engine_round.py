"""Engine round of 2026-11-08 (sandbox lesson.md "NEXT ENGINE ROUND" a-i): private config, expression limits,
asset confinement, unresolved expressions in States, cross-page joins, ratio designs, declared reading annotations,
image marks as fragment boundaries, '|' inside reading content."""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from hsenv.checks import check_refs, check_verbatim, play, state_expr_leaks
from hsenv.engine import Env, Protocol, ProtocolError
from hsenv.expr import ExprError, evaluate


_V3 = None


def setUpModule():   # these readings predate the v3 reader prompt: read them as LEGACY (pass 3 format gate)
    global _V3
    import hsenv.checks as hc
    _V3, hc._is_v3 = hc._is_v3, (lambda reading: False)


def tearDownModule():
    import hsenv.checks as hc
    hc._is_v3 = _V3

ROOT = Path(__file__).resolve().parents[1]   # the hsenv project folder


def proto(*texts, page=1, data=None, stages=None, meta=None):
    cite = {"label": "verbatim", "source": "s", "page": page, "read": "image"}
    m = {"sources": {"s": {"file": "s.pdf", "sha256": "x"}}}
    m.update(meta or {})
    return SimpleNamespace(data=data if data is not None else {"items": [{"text": t, "cite": dict(cite)} for t in texts]},
                           stages=stages or {}, raw={"id": "fakestudy", "meta": m})


class A_NoStudyDataInPublicCode(unittest.TestCase):
    # files owned by other agents this round that still name a study; remove an entry once its file is clean
    PENDING_OTHER_OWNERS = set()

    @staticmethod
    def public_files():
        """Engine code, scripts, and everything under tests/ (incl. fixtures) and schema/: all of it is published."""
        files = [f for f in sorted((ROOT / "hsenv").glob("*.py")) if f.name not in A_NoStudyDataInPublicCode.PENDING_OTHER_OWNERS]
        files += sorted((ROOT / "scripts").glob("*.py"))
        for d in ("tests", "schema"):
            files += sorted(f for f in (ROOT / d).rglob("*") if f.is_file() and "__pycache__" not in f.parts)
        return files

    @staticmethod
    def citation_surnames(ids):
        """Every author surname in the studies' meta.citation (APA: 'Surname, I. I., Other, I., & Last, I. (year)')."""
        names = set()
        for i in ids:
            try:
                cit = json.loads((ROOT / "studies" / i / "protocol.json").read_text(encoding="utf-8"))["meta"]["citation"]
            except (OSError, ValueError, KeyError, TypeError):
                continue
            head = re.split(r"\(\d{4}", cit or "")[0]
            names |= {m.group(1) for m in re.finditer(r"([A-Z][\w'-]+(?: [A-Z][\w'-]+)*), [A-Z]\.", head)}
        return names

    def grep(self, rx, files):
        return ["%s:%d" % (f.relative_to(ROOT), k + 1) for f in files
                for k, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines()) if rx.search(line)]

    def test_engine_package_names_no_study(self):
        if not (ROOT / "studies").is_dir():
            self.skipTest("no studies/ folder next to the package (published copy): nothing private to grep for")
        ids = sorted(p.name for p in (ROOT / "studies").iterdir() if p.is_dir())
        self.assertTrue(ids)
        files = self.public_files()
        self.assertTrue(any("fixtures" in f.parts for f in files) and any(f.parent.name == "schema" for f in files))
        rx = re.compile("|".join(map(re.escape, ids)), re.I)
        self.assertEqual(self.grep(rx, files), [], "study ids in public engine files (move them to the private config)")
        # first-author names of the ids too (e.g. a review cited by author name), case-insensitive; names that are
        # English words or too common to grep are skipped here
        common = {"hall", "li", "ross", "wong", "thomas", "davis", "berg"}
        names = sorted({re.match(r"[a-z]+", i).group(0) for i in ids} - common)
        rx2 = re.compile(r"\b(?:%s)\b" % "|".join(names), re.I)
        self.assertEqual(self.grep(rx2, files), [], "study author names in public engine files")
        # every author surname in the studies' citations, as written (capitalised, whole word)
        surnames = self.citation_surnames(ids)
        self.assertGreater(len(surnames), len(ids))
        rx3 = re.compile(r"\b(?:%s)\b" % "|".join(map(re.escape, sorted(surnames, key=len, reverse=True))))
        self.assertEqual(self.grep(rx3, files), [], "citation surnames in public engine files")

    def test_works_without_private_config(self):
        code = ("import hsenv.checks as c; assert c.LEGACY_UNCERTAIN_READINGS == {} and c.LEGACY_CITE_SOURCES == {} "
                "and c.PRIVATE == {}; print('ok')")
        env = dict(os.environ, HSENV_PRIVATE_CONFIG="")
        out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True)
        self.assertEqual(out.stdout.strip(), "ok", out.stderr)

    def test_private_config_from_env(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "cfg.json"
            f.write_text(json.dumps({"legacy_cite_sources": {"x": ["a"]}, "legacy_uncertain_readings": {"ab": "l"}}))
            code = "import hsenv.checks as c; print(sorted(c.LEGACY_CITE_SOURCES['x']), c.LEGACY_UNCERTAIN_READINGS)"
            out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=dict(os.environ, HSENV_PRIVATE_CONFIG=str(f)),
                                 capture_output=True, text=True)
            self.assertEqual(out.stdout.strip(), "['a'] {'ab': 'l'}", out.stderr)


class B_ExpressionLimits(unittest.TestCase):
    def bad(self, src):
        with self.assertRaises(ExprError) as cm:
            evaluate(src, {})
        return str(cm.exception)

    def test_review_examples(self):
        self.assertIn("limit", self.bad("len([0]*(4*10**8))"))
        self.assertIn("limit", self.bad("10**10**9"))

    def test_sizes_loops_and_formats(self):
        for src in ("'x' * 10**7", "[0] * 10**6 + [1]", "'%0999999999d' % 1", "'%*d' % (5, 1)",
                    "[i for i in range(10**6) for j in range(10**6)]", "sum(range(10**12))",
                    "[[0] * 10**5 for i in range(10**5)]", "str([[0] * 10**5] * 10**5)", "money(1, 10**9)",
                    "join('x' * 1000, range(10**5))", "replace('a' * 10**5, '', 'b' * 100)",
                    "[list(range(10**6)) for i in range(100)]", "2 ** 5000"):
            self.assertIn("limit", self.bad(src), src)

    def test_source_size_and_nesting(self):
        self.assertIn("limit", self.bad("1 + " * 100000 + "1"))
        self.assertRaises(ExprError, evaluate, "(" * 1000 + "1" + ")" * 1000, {})

    def test_ordinary_rules_still_work(self):
        self.assertEqual(evaluate("10**100 // 10**99", {}), 10)
        self.assertEqual(evaluate("sum([x * 2 for x in range(10)])", {}), 90)
        self.assertEqual(evaluate("'%.2f' % 3.14159 + '!'", {}), "3.14!")
        self.assertEqual(evaluate("money(3, 1) + ' ' + str(len([0] * 1000))", {}), "3.0 1000")
        self.assertEqual(evaluate("sorted(list(xs))[-1]", {"xs": [3, 1, 2]}), 3)
        self.assertEqual(evaluate("-2 ** 2 + 7 % 3 - 1", {}), -4)

    def test_guards_cannot_be_named(self):
        self.assertRaises(ExprError, evaluate, "_hs_add(1, 2)", {})


class C_AssetConfinement(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "study"
        (self.root / "assets").mkdir(parents=True)
        (self.root / "assets" / "ok.png").write_bytes(b"\x89PNG fake")
        (Path(self.tmp.name) / "outside.txt").write_text("secret")
        os.symlink(Path(self.tmp.name) / "outside.txt", self.root / "assets" / "link.png")
        os.symlink(self.root / "assets" / "ok.png", self.root / "assets" / "inside_link.png")

    def tearDown(self):
        self.tmp.cleanup()

    def prot(self, src):
        return Protocol({"id": "a", "data": {"img": {"src": src}},
                         "stages": {"s": {"content": [{"id": "i", "value": {"expr": "data['img']"}}]}},
                         "flow": {"stage": "s"}}, self.root)

    def test_refused_sources(self):
        for src in ("/dev/zero", "/etc/hosts", "../outside.txt", "assets/../../outside.txt", "assets/link.png",
                    "assets", "C:\\\\x.png", "~/x.png"):
            p = self.prot(src)
            with self.assertRaises(ProtocolError, msg=src):
                p.asset_ref(src)
            self.assertTrue(check_refs(p), src)   # static check names it too
            env = Env(p)
            s = env.open(env.design(n=1)[0])
            self.assertRaises(ProtocolError, s.reset)

    def test_allowed_sources(self):
        for src in ("assets/ok.png", "assets/inside_link.png", "assets/missing.png"):
            p = self.prot(src)
            self.assertTrue(p.asset_ref(src).startswith("asset:"))
            self.assertEqual([x for x in check_refs(p) if "asset src" in x], [])


class D_UnresolvedExpressionsInStates(unittest.TestCase):
    def test_nested_expr_in_anchors_fails_the_fuzz(self):
        prot = {"id": "d", "data": {"left": {"text": "Strongly disagree"}},
                "stages": {"q": {"responses": [{"id": "a", "kind": "scale", "range": [1, 7], "prompt": "Rate",
                                                "anchors": {"left": {"expr": "data['left']['text']"}}}]}},
                "flow": {"stage": "q"}}
        _, _, stats = play(Protocol(prot), 3, 1)
        self.assertTrue(stats["state_expr_leaks"])
        prot["stages"]["q"]["responses"][0]["anchors"] = {"left": "Strongly disagree"}
        _, _, stats = play(Protocol(prot), 3, 1)
        self.assertEqual(stats["state_expr_leaks"], [])

    def test_scanner(self):
        self.assertTrue(state_expr_leaks({"screen": {"items": [{"text": "x data['a'] y"}]}}))
        self.assertTrue(state_expr_leaks({"screen": {"responses": [{"prompt": "answer('s.q') + 1"}]}}))
        self.assertTrue(state_expr_leaks({"screen": {"items": [{"z": {"expr": "1"}}]}}))
        self.assertEqual(state_expr_leaks({"screen": {"items": [{"text": "Your answer(s) below"}]},
                                           "answered": [{"prompt": "p", "value": "data['x'] typed by the person"}]}), [])


class E_CrossPageJoin(unittest.TestCase):
    TEXT = "The first half of the paragraph. It ends on the next page."

    def found(self, reading, page="3-4"):
        return check_verbatim(proto(self.TEXT, page=page), {"s#second": reading})["found"]

    def test_last_line_of_p_and_first_of_q(self):
        r = ("p3 | 1 | text | Something else.\np3 | 1 | text | The first half of the paragraph. It ends\n"
             "p4 | 1 | text | on the next page.\np4 | 1 | text | More text.")
        self.assertEqual(self.found(r), 1)
        hy = "p3 | 1 | text | A well-\np4 | 1 | text | known fact."   # a hyphenated word at the page end
        self.assertEqual(check_verbatim(proto("A well-known fact.", page="3-4"), {"s#second": hy})["found"], 1)

    def test_only_for_two_page_cites_and_page_edges(self):
        r = "p3 | 1 | text | The first half of the paragraph. It ends\np4 | 1 | text | on the next page."
        self.assertEqual(self.found(r, page=3), 0)
        self.assertEqual(self.found(r.replace("p4", "p5"), page="3-5"), 0)
        not_last = r.replace("\np4", "\np3 | 1 | text | A footer\np4")
        self.assertEqual(self.found(not_last), 0)
        unsure = r.replace("on the next page.", "on the next page. [uncertain: next]")
        self.assertEqual(self.found(unsure), 0)
        self.assertEqual(self.found(r.replace("p4 | 1 | text", "p4 | 1 | option")), 0)


class F_RatioDesign(unittest.TestCase):
    def env(self, ratio, runnable=True):
        arms = [{"id": "c", "n_paper": 10}, {"id": "t1", "n_paper": 5}, {"id": "t2", "n_paper": 5, "runnable": runnable},
                {"id": "other", "n_paper": 3}]
        return Env(Protocol({"id": "r", "data": {}, "stages": {"s": {}}, "flow": {"stage": "s"}, "arms": arms,
                             "conditions": [{"id": "cond", "ratio": ratio}]}))

    def counts(self, env, n, **kw):
        return dict(Counter(s["arm"] for s in env.design(n=n, **kw)))

    def test_ratio_largest_remainder(self):
        e = self.env({"c": 0.5, "t1": 0.25, "t2": 0.25})
        self.assertEqual(self.counts(e, 1000), {"c": 1500, "t1": 750, "t2": 750, "other": 1000})
        self.assertEqual(self.counts(e, 1), {"c": 1, "t1": 1, "t2": 1, "other": 1})
        self.assertEqual(self.counts(e, 2), {"c": 3, "t1": 2, "t2": 1, "other": 2})
        self.assertEqual(self.counts(e, "paper"), {"c": 10, "t1": 5, "t2": 5, "other": 3})
        self.assertEqual(self.counts(e, {"c": 2}), {"c": 2})
        self.assertEqual(self.counts(e, 100, arms=["c", "t1"]), {"c": 133, "t1": 67})

    def test_blocked_arm_leaves_the_ratio(self):
        self.assertEqual(self.counts(self.env({"c": 2, "t1": 1, "t2": 1}, runnable=False), 30),
                         {"c": 40, "t1": 20, "other": 30})

    def test_bad_ratio(self):
        self.assertRaises(ProtocolError, self.env({"c": 0, "t1": 1}).design, 10)
        self.assertRaises(ProtocolError, self.env({"zz": 1}).design, 10)


class G_ReadingAnnotations(unittest.TestCase):
    R = "p1 | 1 | option | B. a blue mug and a red pen [22 percent]"

    def test_declared_pattern_strips_that_source_only(self):
        meta = {"image_read": {"reading_annotations": [{"source": "s", "pattern": r"\s*\[\d+ percent\]$",
                                                         "why": "result shares printed after options"}]}}
        self.assertEqual(check_verbatim(proto("B. a blue mug and a red pen"), {"s#second": self.R})["found"], 0)
        v = check_verbatim(proto("B. a blue mug and a red pen", meta=meta), {"s#second": self.R})
        self.assertEqual(v["found"], 1)
        self.assertEqual(v["reading_annotations"], [{"source": "s", "pattern": r"\s*\[\d+ percent\]$",
                                                     "lines_changed": 1}])
        other = {"image_read": {"reading_annotations": [{"source": "t", "pattern": r"\s*\[\d+ percent\]$"}]}}
        self.assertEqual(check_verbatim(proto("B. a blue mug and a red pen", meta=other), {"s#second": self.R})["found"], 0)

    def test_plain_strings_with_one_source_and_bad_declarations(self):
        meta = {"image_read": {"source": "s", "reading_annotations": [r"\s*\[\d+ percent\]$"]}}
        self.assertEqual(check_verbatim(proto("B. a blue mug and a red pen", meta=meta), {"s#second": self.R})["found"], 1)
        bad = {"image_read": {"reading_annotations": [{"source": "s", "pattern": "("}, "x"]}}
        v = check_verbatim(proto("B. a blue mug and a red pen", meta=bad), {"s#second": self.R})
        self.assertEqual([("error" in a) for a in v["reading_annotations"]], [True, True])
        self.assertEqual(v["found"], 0)


class H_ImageMarkFragments(unittest.TestCase):
    def prot(self):
        c = {"label": "verbatim", "source": "s", "page": 1, "read": "image"}
        data = {"g": {"a2": {"text": "\" results in", "cite": dict(c)}, "a3": {"text": "points.", "cite": dict(c)}}}
        tpl = "{'text': data['g']['a2']['text'] + ' ' + str(answer('s.roll')) + ' ' + data['g']['a3']['text']}"
        stages = {"s": {"content": [{"id": "x", "value": {"expr": tpl}}]}}
        return proto(data=data, stages=stages)

    def test_image_mark_splits_fragments_for_templates(self):
        r = 'p1 | 1 | text | Your roll outcome "[callout die image showing six pips]" results in 6 points.'
        self.assertEqual(check_verbatim(self.prot(), {"s#second": r})["found"], 2)
        r2 = 'p1 | 1 | text | Your roll outcome "[note: picture of a die]" results in 6 points.'
        self.assertEqual(check_verbatim(self.prot(), {"s#second": r2})["found"], 2)

    def test_other_marks_are_no_boundary(self):
        r = 'p1 | 1 | text | Your roll outcome "[note: blue box]" results in 6 points.'
        self.assertEqual(check_verbatim(self.prot(), {"s#second": r})["found"], 0)
        # a fragment is used only by the template rule, never as a whole unit for a plain served text
        r3 = 'p1 | 1 | text | Your roll outcome "[image]" results in 6 points.'
        self.assertEqual(check_verbatim(proto('" results in 6 points.'), {"s#second": r3})["found"], 0)


class KeyedSign(unittest.TestCase):
    def test_zero_is_no_sign(self):   # LESSONS 301
        from hsenv.checks import same_sign
        self.assertFalse(same_sign(0, -0.3))
        self.assertFalse(same_sign(0.0, 0.3))
        self.assertTrue(same_sign(-0.1, -0.3))
        self.assertTrue(same_sign(2, 0.3))
        self.assertTrue(same_sign(0, 0))
        self.assertFalse(same_sign(float("nan"), 1))


class I_PipeInContent(unittest.TestCase):
    def found(self, text, reading):
        return check_verbatim(proto(text), {"s#second": reading})["found"]

    def test_content_after_fixed_fields_keeps_pipes(self):
        r = "p1 | screen 1 | label | small grey caps | SITE.COM | BY A WRITER"
        self.assertEqual(self.found("SITE.COM | BY A WRITER", r), 1)
        self.assertEqual(self.found("SITE.COM", r), 1)
        self.assertEqual(self.found("BY A WRITER", r), 1)
        self.assertEqual(self.found("A WRITER", r), 0)   # never a phrase inside a piece
        r4 = "p1 | screen 1 | text | Left | Right"
        self.assertEqual(self.found("Left | Right", r4), 1)
        self.assertEqual(self.found("Right", r4), 1)


if __name__ == "__main__":
    unittest.main()
