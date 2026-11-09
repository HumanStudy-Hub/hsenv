"""Engine pass 3, review round 2: the reviewer's adversarial fixtures (invented text only) as regression cases, under
the closed note grammar (DESIGN.md §3.5 pass 3). Expected values are the strict outcome. Where the reviewer expected a
confirmation the grammar refuses, the case is listed in GRAMMAR_REFUSES with the reason (maintainers: never loosen
the grammar to save a confirmation)."""
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [_HERE, os.path.dirname(_HERE)]   # importable standalone (S6): the tests folder and the package
from test_engine_pass3 import c, check, proto, rules  # noqa: E402

# reviewer expected a confirmation; the closed grammar refuses it (reason)
GRAMMAR_REFUSES = {
    "1) vs numbered 1.": "'numbered 1.' (trailing period) is not the numbered form",
    "dash served vs note 'en-dash bullet'": "'en dash bullet' is not the bullet form",
    "note 'probably a footnote marker absent'": "'probably' is a doubt word: the line is uncertain",
    "note says 'items 1 or 2 are bold'": "'1 or 2' is a doubt form: the line is uncertain",
    "bulleted, note 'bulleted, italic'": "clauses split on ';' only: 'bulleted, italic' is not one form",
    "bulleted note 'bulleted list, not bold'": "unrecognised clause",
    "bulleted note 'bulleted as the others below'": "unrecognised clause",
    "numbered 'item 2 of a numbered list'": "not the numbered form",
    "numbered 'number 2'": "not the numbered form",
    "note doubt over-block: 'possibly decorative'": "'possibly' is a doubt word: the line is uncertain",
    "two images": "one image item is one picture mark; [image][image] is refused",
    "image (roman ii)": "'image ii' is not the picture form",
    "edge plain remark ok": "'faint print' is a doubt word and an unrecognised clause",
    "note 'not bold' on plain": "v3: an unrecognised note clause makes the line uncertain (round 4)",
    "note 'or' style remark": "v3: an unrecognised note clause makes the line uncertain (round 4)",
    "note 'curly quotes'": "v3: an unrecognised note clause makes the line uncertain (round 4)",
    'plain served, reading 2.': "v3: a leading number is stripped only on option / slider lines or with a bullet / numbered note (round 4 M2)",
    "multiline w/ note line between": "v3: an unrecognised pure note line ('blank gap') ends every join (round 3 M1)",
}

FOUND = [("LM note 'un-bulleted'", '• Be kind.', 'p1 | 1 | text | Be kind. [note: un-bulleted]', 0),
 ("LM note 'non-bulleted'", '• Be kind.', 'p1 | 1 | text | Be kind. [note: non-bulleted]', 0),
 ("LM note 'unbulleted'", '• Be kind.', 'p1 | 1 | text | Be kind. [note: unbulleted]', 0),
 ("LM note 'bullets omitted here'", '• Be kind.', 'p1 | 1 | text | Be kind. [note: bullets omitted here]', 0),
 ("LM note 'bullet missing'", '• Be kind.', 'p1 | 1 | text | Be kind. [note: bullet missing]', 0),
 ("LM note 'bullet absent'", '• Be kind.', 'p1 | 1 | text | Be kind. [note: bullet absent]', 0),
 ("LM note 'bullet removed'", '• Be kind.', 'p1 | 1 | text | Be kind. [note: bullet removed]', 0),
 ("LM note 'kein bullet'", '• Be kind.', 'p1 | 1 | text | Be kind. [note: kein bullet]', 0),
 ("LM note 'sin bullet'", '• Be kind.', 'p1 | 1 | text | Be kind. [note: sin bullet]', 0),
 ("LM note 'sans bullet'", '• Be kind.', 'p1 | 1 | text | Be kind. [note: sans bullet]', 0),
 ("LM note '没有 bullet'", '• Be kind.', 'p1 | 1 | text | Be kind. [note: 没有 bullet]', 0),
 ("LM note '无 bullet'", '• Be kind.', 'p1 | 1 | text | Be kind. [note: 无 bullet]', 0),
 ("LM note 'pas de bullet'", '• Be kind.', 'p1 | 1 | text | Be kind. [note: pas de bullet]', 0),
 ("LM note 'bullet? unsure'", '• Be kind.', 'p1 | 1 | text | Be kind. [note: bullet? unsure]', 0),
 ("LM note 'lacks a bullet'", '• Be kind.', 'p1 | 1 | text | Be kind. [note: lacks a bullet]', 0),
 ("LM note 'bullet-less'", '• Be kind.', 'p1 | 1 | text | Be kind. [note: bullet-less]', 0),
 ("LM note 'the item after this is bulleted'",
  '• Be kind.',
  'p1 | 1 | text | Be kind. [note: the item after this is bulleted]',
  0),
 ("LM note 'line 3 is bulleted'", '• Be kind.', 'p1 | 1 | text | Be kind. [note: line 3 is bulleted]', 0),
 ("LM note 'bulleted in the original, plain here'",
  '• Be kind.',
  'p1 | 1 | text | Be kind. [note: bulleted in the original, plain here]',
  0),
 ("LM note 'only the heading is bulleted'",
  '• Be kind.',
  'p1 | 1 | text | Be kind. [note: only the heading is bulleted]',
  0),
 ("LM note 'first item bulleted'", '• Be kind.', 'p1 | 1 | text | Be kind. [note: first item bulleted]', 0),
 ("LM note 'bulleted list starts after this'",
  '• Be kind.',
  'p1 | 1 | text | Be kind. [note: bulleted list starts after this]',
  0),
 ("LM note 'bulleted\xa0list'", '• Be kind.', 'p1 | 1 | text | Be kind. [note: bulleted\xa0list]', 1),
 ('10. vs numbered 1', '10. Be kind.', 'p1 | 1 | text | Be kind. [note: numbered 1]', 0),
 ('1. vs numbered 10', '1. Be kind.', 'p1 | 1 | text | Be kind. [note: numbered 10]', 0),
 ('1. vs numbered 01', '1. Be kind.', 'p1 | 1 | text | Be kind. [note: numbered 01]', 0),
 ('1) vs numbered 1.', '1) Be kind.', 'p1 | 1 | text | Be kind. [note: numbered 1.]', 0),
 ("1. vs 'numbered (a)'", '1. Be kind.', 'p1 | 1 | text | Be kind. [note: numbered a]', 0),
 ('fullwidth １. vs numbered 1', '１. Be kind.', 'p1 | 1 | text | Be kind. [note: numbered 1]', 1),
 ('arabic-indic ٣. vs numbered 3', '٣. Be kind.', 'p1 | 1 | text | Be kind. [note: numbered 3]', 0),
 ("1. vs 'numbered 1 (roman i)'", '1. Be kind.', 'p1 | 1 | text | Be kind. [note: numbered i]', 0),
 ("2. vs 'numbered, second of 2'... ", '2. Be kind.', 'p1 | 1 | text | Be kind. [note: numbered, 2nd]', 0),
 ("1. vs 'bullet numbered 1'", '• Be kind.', 'p1 | 1 | text | Be kind. [note: bulleted, numbered 1]', 0),
 ("dash served vs note 'en-dash bullet'", '- Be kind.', 'p1 | 1 | text | Be kind. [note: en dash bullet]', 0),
 ("bullet served, reading has '1.' literal", '• Be kind.', 'p1 | 1 | text | 1. Be kind. [note: bulleted]', 0),
 ('1. served, reading literal 2.', '1. Be kind.', 'p1 | 1 | text | 2. Be kind.', 0),
 ('plain served, reading 2.', 'Be kind.', 'p1 | 1 | text | 2. Be kind.', 0),
 ("glyph '◆' served (not in list)", '◆ Be kind.', 'p1 | 1 | text | Be kind. [note: bulleted]', 0),
 ("'* ' served", '* Be kind.', 'p1 | 1 | text | Be kind. [note: bulleted]', 1),
 ('star nospace', '*Be kind.', 'p1 | 1 | text | Be kind. [note: bulleted]', 0),
 ("doubt 'or 26?'", '20', 'p1 | 1 | text | 20 [note: or 26?]', 0),
 ("doubt '26?'", '20', 'p1 | 1 | text | 20 [note: 26?]', 0),
 ("doubt 'likely 26'", '20', 'p1 | 1 | text | 20 [note: likely 26]', 0),
 ("doubt 'unsure'", '20', 'p1 | 1 | text | 20 [note: unsure]', 0),
 ("doubt 'not sure'", '20', 'p1 | 1 | text | 20 [note: not sure]', 0),
 ("doubt '20 vs 26'", '20', 'p1 | 1 | text | 20 [note: 20 vs 26]', 0),
 ("doubt '20/26'", '20', 'p1 | 1 | text | 20 [note: 20/26]', 0),
 ("doubt 'looks like 20'", '20', 'p1 | 1 | text | 20 [note: looks like 20]', 0),
 ("doubt 'could also read 26'", '20', 'p1 | 1 | text | 20 [note: could also read 26]', 0),
 ("doubt 'may be 26'", '20', 'p1 | 1 | text | 20 [note: may be 26]', 0),
 ("doubt '20 or 26'", '20', 'p1 | 1 | text | 20 [note: 20 or 26]', 0),
 ("doubt 'either 20 or 26'", '20', 'p1 | 1 | text | 20 [note: either 20 or 26]', 0),
 ("doubt 'hard to read'", '20', 'p1 | 1 | text | 20 [note: hard to read]', 0),
 ("doubt 'faint'", '20', 'p1 | 1 | text | 20 [note: faint]', 0),
 ("doubt 'blurry'", '20', 'p1 | 1 | text | 20 [note: blurry]', 0),
 ("doubt 'smudged'", '20', 'p1 | 1 | text | 20 [note: smudged]', 0),
 ('MK notes between that are printed?',
  'Rules:\nBe kind.',
  'p1 | 1 | label | Rules:\np1 | 1 | note | [note: a printed line here: stop]\np1 | 1 | text | Be kind.',
  0),
 ("MK negated same cell 'isn't'",
  'Price\nTen tokens.',
  "p1 | 1 | cell | Price\np1 | 1 | cell | Ten tokens. [note: isn't the same cell]",
  0),
 ("MK 'different from the same cell'",
  'Price\nTen tokens.',
  'p1 | 1 | cell | Price\np1 | 1 | cell | Ten tokens. [note: separate cell, not in same cell]',
  0),
 ("MK 'same cell? unsure'",
  'Price\nTen tokens.',
  'p1 | 1 | cell | Price\np1 | 1 | cell | Ten tokens. [note: same cell? unsure]',
  0),
 ("MK 'unlike the same cell...' ",
  'Price\nTen tokens.',
  'p1 | 1 | cell | Price\np1 | 1 | cell | Ten tokens. [note: in its own box, unlike same cell above]',
  0),
 ("MK 'kein same cell'",
  'Price\nTen tokens.',
  'p1 | 1 | cell | Price\np1 | 1 | cell | Ten tokens. [note: kein same cell]',
  0),
 ('MK cell label: then sentence different cells',
  'Price:\nTen tokens.',
  'p1 | 1 | cell | Price:\np1 | 1 | cell | Ten tokens.',
  1),
 ('MK cells across rows', 'Price:\nTen tokens.', 'p1 | 1 | cell | Price:\np1 | 1 | cell | row 2 | Ten tokens.', 0),
 ('MK heading + text', 'Rules\nBe kind.', 'p1 | 1 | heading | Rules\np1 | 1 | text | Be kind.', 1),
 ('MK nbsp in reading', 'Rules:\nBe kind.', 'p1 | 1 | label | Rules:\np1 | 1 | text | Be\xa0kind.', 1),
 ('MK line with uncertain in middle',
  'A:\nB.\nC.',
  'p1 | 1 | text | A:\np1 | 1 | text | B. [note: maybe]\np1 | 1 | text | C.',
  0),
 ('MK reversed', 'A:\nB.', 'p1 | 1 | text | B.\np1 | 1 | text | A:', 0),
 ('MK option kinds', 'Yes\nNo', 'p1 | 1 | option | Yes\np1 | 1 | option | No', 0),
 ('MK long',
  'Line 0.\n'
  'Line 1.\n'
  'Line 2.\n'
  'Line 3.\n'
  'Line 4.\n'
  'Line 5.\n'
  'Line 6.\n'
  'Line 7.\n'
  'Line 8.\n'
  'Line 9.\n'
  'Line 10.\n'
  'Line 11.\n'
  'Line 12.\n'
  'Line 13.\n'
  'Line 14.\n'
  'Line 15.\n'
  'Line 16.\n'
  'Line 17.\n'
  'Line 18.\n'
  'Line 19.\n'
  'Line 20.\n'
  'Line 21.\n'
  'Line 22.\n'
  'Line 23.\n'
  'Line 24.\n'
  'Line 25.\n'
  'Line 26.\n'
  'Line 27.\n'
  'Line 28.\n'
  'Line 29.',
  'p1 | 1 | text | Line 0.\n'
  'p1 | 1 | text | Line 1.\n'
  'p1 | 1 | text | Line 2.\n'
  'p1 | 1 | text | Line 3.\n'
  'p1 | 1 | text | Line 4.\n'
  'p1 | 1 | text | Line 5.\n'
  'p1 | 1 | text | Line 6.\n'
  'p1 | 1 | text | Line 7.\n'
  'p1 | 1 | text | Line 8.\n'
  'p1 | 1 | text | Line 9.\n'
  'p1 | 1 | text | Line 10.\n'
  'p1 | 1 | text | Line 11.\n'
  'p1 | 1 | text | Line 12.\n'
  'p1 | 1 | text | Line 13.\n'
  'p1 | 1 | text | Line 14.\n'
  'p1 | 1 | text | Line 15.\n'
  'p1 | 1 | text | Line 16.\n'
  'p1 | 1 | text | Line 17.\n'
  'p1 | 1 | text | Line 18.\n'
  'p1 | 1 | text | Line 19.\n'
  'p1 | 1 | text | Line 20.\n'
  'p1 | 1 | text | Line 21.\n'
  'p1 | 1 | text | Line 22.\n'
  'p1 | 1 | text | Line 23.\n'
  'p1 | 1 | text | Line 24.\n'
  'p1 | 1 | text | Line 25.\n'
  'p1 | 1 | text | Line 26.\n'
  'p1 | 1 | text | Line 27.\n'
  'p1 | 1 | text | Line 28.\n'
  'p1 | 1 | text | Line 29.',
  1),
 ('MK long one dropped',
  'Line 0.\n'
  'Line 1.\n'
  'Line 2.\n'
  'Line 3.\n'
  'Line 4.\n'
  'Line 5.\n'
  'Line 6.\n'
  'Line 7.\n'
  'Line 8.\n'
  'Line 9.\n'
  'Line 10.\n'
  'Line 11.\n'
  'Line 12.\n'
  'Line 13.\n'
  'Line 14.\n'
  'Line 15.\n'
  'Line 16.\n'
  'Line 17.\n'
  'Line 18.\n'
  'Line 19.\n'
  'Line 20.\n'
  'Line 21.\n'
  'Line 22.\n'
  'Line 23.\n'
  'Line 24.\n'
  'Line 25.\n'
  'Line 26.\n'
  'Line 27.\n'
  'Line 28.\n'
  'Line 29.',
  'p1 | 1 | text | Line 0.\n'
  'p1 | 1 | text | Line 1.\n'
  'p1 | 1 | text | Line 2.\n'
  'p1 | 1 | text | Line 3.\n'
  'p1 | 1 | text | Line 4.\n'
  'p1 | 1 | text | Line 5.\n'
  'p1 | 1 | text | Line 6.\n'
  'p1 | 1 | text | Line 7.\n'
  'p1 | 1 | text | Line 8.\n'
  'p1 | 1 | text | Line 9.\n'
  'p1 | 1 | text | Line 10.\n'
  'p1 | 1 | text | Line 11.\n'
  'p1 | 1 | text | Line 12.\n'
  'p1 | 1 | text | Line 13.\n'
  'p1 | 1 | text | Line 14.\n'
  'p1 | 1 | text | Line 16.\n'
  'p1 | 1 | text | Line 17.\n'
  'p1 | 1 | text | Line 18.\n'
  'p1 | 1 | text | Line 19.\n'
  'p1 | 1 | text | Line 20.\n'
  'p1 | 1 | text | Line 21.\n'
  'p1 | 1 | text | Line 22.\n'
  'p1 | 1 | text | Line 23.\n'
  'p1 | 1 | text | Line 24.\n'
  'p1 | 1 | text | Line 25.\n'
  'p1 | 1 | text | Line 26.\n'
  'p1 | 1 | text | Line 27.\n'
  'p1 | 1 | text | Line 28.\n'
  'p1 | 1 | text | Line 29.',
  0),
 ('K two elements both line 1',
  'You keep',
  'p1 | 1 | text | line 1 | You keep\np1 | 1 | text | line 2 | the tokens.\np1 | 2 | text | line 1 | You keep',
  0),
 ("K style 'line 1, bold'",
  'You keep',
  'p1 | 1 | text | line 1, bold | You keep\np1 | 1 | text | line 2, bold | the tokens.',
  0),
 ("K style 'bold, line 1'",
  'You keep',
  'p1 | 1 | text | bold, line 1 | You keep\np1 | 1 | text | bold, line 2 | the tokens.',
  0),
 ("K 'first line'",
  'You keep',
  'p1 | 1 | text | first line | You keep\np1 | 1 | text | second line | the tokens.',
  0),
 ("K 'line 1 of 2'",
  'You keep',
  'p1 | 1 | text | line 1 of 2 | You keep\np1 | 1 | text | line 2 of 2 | the tokens.',
  0),
 ("K 'Line 1' caps", 'You keep', 'p1 | 1 | text | Line 1 | You keep\np1 | 1 | text | Line 2 | the tokens.', 0),
 ('K line in kind field', 'You keep', 'p1 | 1 | text, line 1 | You keep\np1 | 1 | text, line 2 | the tokens.', 0),
 ("K 'line 1' as note",
  'You keep',
  'p1 | 1 | text | You keep [note: line 1 of 2]\np1 | 1 | text | the tokens. [note: line 2 of 2]',
  0),
 ("K nbsp 'line\\xa01'",
  'You keep',
  'p1 | 1 | text | line\xa01 | You keep\np1 | 1 | text | line\xa02 | the tokens.',
  0),
 ('K join covers lines 1-2 of 3',
  'You keep the tokens.',
  'p1 | 1 | text | line 1 | You keep\np1 | 1 | text | line 2 | the tokens.\np1 | 1 | text | line 3 | Bonus.',
  0),
 ('K multiline_k lines 1-2 of 3',
  'You keep\nthe tokens.',
  'p1 | 1 | text | line 1 | You keep\np1 | 1 | text | line 2 | the tokens.\np1 | 1 | text | line 3 | Bonus.',
  0),
 ('K label_value on line n', 'Price: 10', 'p1 | 1 | label | line 1 | Price:\np1 | 1 | text | 10', 0),
 ('K page_join line n', 'x', 'p1 | 1 | text | x', 1),
 ('plain sentence with note italic', 'Be kind.', 'p1 | 1 | text | Be kind. [note: italic]', 1),
 ("note 'not bold' on plain", 'Be kind.', 'p1 | 1 | text | Be kind. [note: not bold]', 0),
 ("note 'or' style remark", 'Be kind.', 'p1 | 1 | text | Be kind. [note: italic or slanted]', 0),
 ("note 'curly quotes'", '"Be kind."', 'p1 | 1 | text | "Be kind." [note: curly quotes]', 0),
 ("note 'probably a footnote marker absent'",
  'Be kind.',
  'p1 | 1 | text | Be kind. [note: grey text, probably a hint]',
  0),
 ("printed '5 or 6' in text, note style", 'Pick 5 or 6.', 'p1 | 1 | text | Pick 5 or 6. [note: bold]', 1),
 ("note says 'items 1 or 2 are bold'", 'Be kind.', 'p1 | 1 | text | Be kind. [note: lines 1 or 2 bold]', 0),
 ("bulleted, note 'bulleted, italic'", '• Be kind.', 'p1 | 1 | text | Be kind. [note: bulleted, italic]', 0),
 ("bulleted note 'bullet point'", '• Be kind.', 'p1 | 1 | text | Be kind. [note: bullet point]', 1),
 ("bulleted note 'round bullet'", '• Be kind.', 'p1 | 1 | text | Be kind. [note: round bullet]', 1),
 ("bulleted note 'bulleted list, not bold'",
  '• Be kind.',
  'p1 | 1 | text | Be kind. [note: bulleted list, not bold]',
  0),
 ("bulleted note 'bulleted as the others below'",
  '• Be kind.',
  'p1 | 1 | text | Be kind. [note: bulleted, like the items below]',
  0),
 ("numbered 'numbered list item 2'", '2. Be kind.', 'p1 | 1 | text | Be kind. [note: numbered list item 2]', 1),
 ("numbered 'numbered (2)'", '2. Be kind.', 'p1 | 1 | text | Be kind. [note: numbered (2)]', 1),
 ("numbered 'item 2 of a numbered list'",
  '2. Be kind.',
  'p1 | 1 | text | Be kind. [note: item 2 of a numbered list]',
  0),
 ("numbered 'number 2'", '2. Be kind.', 'p1 | 1 | text | Be kind. [note: number 2]', 0),
 ('multiline k with list glyph',
  'Rules:\n• Be kind.\n• Be brief.',
  'p1 | 1 | label | Rules:\np1 | 1 | text | Be kind. [note: bulleted]\np1 | 1 | text | Be brief. [note: bulleted]',
  1),
 ('multiline two text elements',
  'Welcome.\nPlease read.',
  'p1 | 1 | text | Welcome.\np1 | 1 | text | Please read.',
  1),
 ('multiline with heading', 'Part 1\nPlease read.', 'p1 | 1 | heading | Part 1\np1 | 1 | text | Please read.', 1),
 ('multiline w/ note line between',
  'Welcome.\nPlease read.',
  'p1 | 1 | text | Welcome.\np1 | 1 | note | [note: blank gap]\np1 | 1 | text | Please read.',
  0),
 ('multiline with question kind',
  'Q1.\nHow old are you?',
  'p1 | 1 | question | Q1.\np1 | 1 | question | How old are you?',
  1),
 ("note doubt over-block: 'possibly decorative'",
  'Be kind.',
  'p1 | 1 | text | Be kind. [note: possibly decorative border]',
  0),
 ("k: join lines 1-2 of 3 with ', bold'",
  'You keep the tokens.',
  'p1 | 1 | text | line 1, bold | You keep\n'
  'p1 | 1 | text | line 2, bold | the tokens.\n'
  'p1 | 1 | text | line 3, bold | Bonus.',
  0),
 ('k: join lines 1-2 of 3 plain',
  'You keep the tokens.',
  'p1 | 1 | text | line 1 | You keep\np1 | 1 | text | line 2 | the tokens.\np1 | 1 | text | line 3 | Bonus.',
  0),
 ("k: label_value 'line 1, bold'",
  'Price: 10',
  'p1 | 1 | label | line 1, bold | Price:\np1 | 1 | label | line 2, bold | in tokens\np1 | 1 | text | 10',
  0),
 ("k: 'line 2' alone as last piece of multiline",
  'Rules:\nthe tokens.',
  'p1 | 1 | label | Rules:\np1 | 1 | text | line 1 | You keep\np1 | 1 | text | line 2 | the tokens.',
  0),
 ('k: multiline with line n of different element',
  'Rules:\nYou keep',
  'p1 | 1 | label | Rules:\np1 | 1 | text | bold, line 1 | You keep\np1 | 1 | text | bold, line 2 | the tokens.',
  0),
 ('LM single line + hidden numbering via multiline',
  'Intro:\n3. Be kind.',
  'p1 | 1 | label | Intro:\np1 | 1 | text | Be kind. [note: numbered 3 — no wait, unnumbered]',
  0),
 ("LM numbered, note 'numbered 3, not 1'",
  '3. Be kind.',
  'p1 | 1 | text | Be kind. [note: numbered 3]  [note: no]',
  0),
 ('LM two notes, one vouching one negating',
  '• Be kind.',
  'p1 | 1 | text | Be kind. [note: bulleted] [note: actually not]',
  0),
 ('LM vouching note on another line same element',
  '• Be kind.',
  'p1 | 1 | text | Be kind.\np1 | 1 | note | [note: bulleted]',
  0),
 ("LM note 'bullets' on heading kind line", '• Results', 'p1 | 1 | heading | Results [note: bullets]', 0)]

GAP = [('baseline [image]', 'Your token "[image]" is worth 2 coins.', {}, True),
 ('lowercase printed in picture note',
  'Your token "[note: picture absent, the word gold printed instead]" is worth 2 coins.',
  {},
  False),
 ('callout lowercase printed', 'Your token "[callout: picture, then printed: gold]" is worth 2 coins.', {}, False),
 ('picture with «gold»', 'Your token "[image labelled «gold»]" is worth 2 coins.', {}, False),
 ('picture with „gold“', 'Your token "[image labelled „gold“]" is worth 2 coins.', {}, False),
 ('picture with `gold`', 'Your token "[image labelled `gold`]" is worth 2 coins.', {}, False),
 ('picture cyrillic', 'Your token "[image: Золото]" is worth 2 coins.', {}, False),
 ('picture CJK', 'Your token "[picture: 金币]" is worth 2 coins.', {}, False),
 ('picture fullwidth caps', 'Your token "[picture: ＧＯＬＤ]" is worth 2 coins.', {}, False),
 ("picture 'without'", 'Your token "[picture, without border; printed word gold]" is worth 2 coins.', {}, False),
 ('picture missing', 'Your token "[picture missing — blank space]" is worth 2 coins.', {}, False),
 ("picture 'isn't'", 'Your token "[picture? isn\'t one, it\'s text gold]" is worth 2 coins.', {}, False),
 ('image of word lowercase', 'Your token "[image of the word gold]" is worth 2 coins.', {}, False),
 ('image, text reads gold', 'Your token "[image, text reads gold]" is worth 2 coins.', {}, False),
 ('image, maybe', 'Your token "[image, maybe]" is worth 2 coins.', {}, False),
 ('image: likely the word', 'Your token "[image: likely a word]" is worth 2 coins.', {}, False),
 ('icon then printed', 'Your token "[icon] gold [icon]" is worth 2 coins.', {}, False),
 ('two images', 'Your token "[image][image]" is worth 2 coins.', {}, False),
 ('nbsp inside mark', 'Your token "[image\xa0of a star]" is worth 2 coins.', {}, True),
 ('figure 1', 'Your token "[figure 1]" is worth 2 coins.', {}, False),
 ('image (roman ii)', 'Your token "[image ii]" is worth 2 coins.', {}, False),
 ('printed text at end edge lowercase note',
  'Your token "[image]" is worth 2 coins. [note: then printed: thanks]',
  {},
  False),
 ('printed text at start edge lowercase',
  '[note: preceded by printed word hello] Your token "[image]" is worth 2 coins.',
  {},
  False),
 ('edge note with fullwidth digit', 'Your token "[image]" is worth 2 coins. [note: ２ more]', {}, False),
 ('picture at start edge with printed',
  '[picture: welcome sign reading hello] Your token "[image]" is worth 2 coins.',
  {},
  False),
 ('nbsp spacing', 'Your\xa0token "[image]" is worth 2 coins.', {}, True),
 ('value fullwidth ２', 'Your token "[image]" is worth ２ coins.', {}, True),
 ('value 02', 'Your token "[image]" is worth 02 coins.', {}, False),
 ('value 4 (not an option)', 'Your token "[image]" is worth 4 coins.', {}, False),
 ('curly quotes', 'Your token “[image]” is worth 2 coins.', {}, True),
 ('empty gap no quotes kept', 'Your token "" is worth 2 coins.', {}, True),
 ('empty gap single quotes in reading', "Your token '' is worth 2 coins.", {}, False),
 ('value via [value A: 2]', 'Your token "[image]" is worth [value A: 2] coins.', {}, True),
 ('value slot as image', 'Your token "[image]" is worth [image] coins.', {}, False),
 ('doubt note at end', 'Your token "[image]" is worth 2 coins. [note: 2?]', {}, False),
 ('uncertain mark', 'Your token "[image]" is worth 2 coins. [uncertain]', {}, False),
 ('partial', 'Your token "[image]" is worth 2 coins. [partial]', {}, False),
 ('non-english mark interior', 'Your token "[non-english]" is worth 2 coins.', {}, False),
 ('value-mark inside quotes gap', 'Your token "[value A: GOLD]" is worth 2 coins.', {}, False),
 ('empty mark interior', 'Your token "[empty]" is worth 2 coins.', {}, False),
 ('dropdown mark interior', 'Your token "[dropdown]" is worth 2 coins.', {}, False),
 ('edge first word eaten: Thanks', 'Your token "[image]" is worth 2 coins. [note: Thanks]', {}, False),
 ('edge first word eaten: 25', 'Your token "[image]" is worth 2 coins. [note: 25 bonus]', {}, False),
 ('edge callout Hello', '[callout: Hello] Your token "[image]" is worth 2 coins.', {}, False),
 ('edge plain remark ok', 'Your token "[image]" is worth 2 coins. [note: faint print]', {}, False)]

COLUMN_ROWS = [('opts baseline',
  'p1 | grid | option | [note: column 1 of 3] 10\n'
  'p1 | grid | option | 90\n'
  'p1 | grid | option | [note: column 2 of 3] 20\n'
  'p1 | grid | option | 80\n'
  'p1 | grid | option | [note: column 3 of 3] 30\n'
  'p1 | grid | option | 70',
  ['10 20 30', '90 80 70'],
  True),
 ('opts N=2 but 3 pairs (of mismatched per pair)',
  'p1 | grid | option | [note: column 1 of 3] 10\n'
  'p1 | grid | option | 90\n'
  'p1 | grid | option | [note: column 2 of 3] 20\n'
  'p1 | grid | option | 80\n'
  'p1 | grid | option | [note: column 3 of 2] 30\n'
  'p1 | grid | option | 70',
  ['10 20 30', '90 80 70'],
  False),
 ('opts mixed N (of 3, of 3, none)',
  'p1 | grid | option | [note: column 1 of 3] 10\n'
  'p1 | grid | option | 90\n'
  'p1 | grid | option | [note: column 2 of 3] 20\n'
  'p1 | grid | option | 80\n'
  'p1 | grid | option | [note: column 3] 30\n'
  'p1 | grid | option | 70',
  ['10 20 30', '90 80 70'],
  False),
 ("opts no 'of'",
  'p1 | grid | option | [note: column 1] 10\n'
  'p1 | grid | option | 90\n'
  'p1 | grid | option | [note: column 2] 20\n'
  'p1 | grid | option | 80\n'
  'p1 | grid | option | [note: column 3] 30\n'
  'p1 | grid | option | 70',
  ['10 20 30', '90 80 70'],
  True),
 ("opts no 'of' + extra non-option line after",
  'p1 | grid | option | [note: column 1] 10\n'
  'p1 | grid | option | 90\n'
  'p1 | grid | option | [note: column 2] 20\n'
  'p1 | grid | option | 80\n'
  'p1 | grid | option | [note: column 3] 30\n'
  'p1 | grid | option | 70\n'
  'p1 | grid | text | 55',
  ['10 20 30', '90 80 70'],
  True),
 ('opts no-of, 4th pair in next screen',
  'p1 | grid | option | [note: column 1] 10\n'
  'p1 | grid | option | 90\n'
  'p1 | grid | option | [note: column 2] 20\n'
  'p1 | grid | option | 80\n'
  'p1 | grid | option | [note: column 3] 30\n'
  'p1 | grid | option | 70\n'
  'p1 | grid2 | option | [note: column 4] 40\n'
  'p1 | grid2 | option | 60',
  ['10 20 30', '90 80 70'],
  True),
 ('opts fullwidth column １',
  'p1 | grid | option | [note: column １ of 3] 10\n'
  'p1 | grid | option | 90\n'
  'p1 | grid | option | [note: column 2 of 3] 20\n'
  'p1 | grid | option | 80\n'
  'p1 | grid | option | [note: column 3 of 3] 30\n'
  'p1 | grid | option | 70',
  ['10 20 30', '90 80 70'],
  True),
 ("opts 'Column 1 of 3' caps",
  'p1 | grid | option | [note: Column 1 of 3] 10\n'
  'p1 | grid | option | 90\n'
  'p1 | grid | option | [note: Column 2 of 3] 20\n'
  'p1 | grid | option | 80\n'
  'p1 | grid | option | [note: Column 3 of 3] 30\n'
  'p1 | grid | option | 70',
  ['10 20 30', '90 80 70'],
  True),
 ('opts bottom has note doubt',
  'p1 | grid | option | [note: column 1 of 3] 10\n'
  'p1 | grid | option | 90\n'
  'p1 | grid | option | [note: column 2 of 3] 20\n'
  'p1 | grid | option | 80 [note: or 86?]\n'
  'p1 | grid | option | [note: column 3 of 3] 30\n'
  'p1 | grid | option | 70',
  ['10 20 30', '90 80 70'],
  False),
 ('opts bottom has colnote other',
  'p1 | grid | option | [note: column 1 of 3] 10\n'
  'p1 | grid | option | 90\n'
  'p1 | grid | option | [note: column 2 of 3] 20\n'
  'p1 | grid | option | 80 [note: column 2 bottom]\n'
  'p1 | grid | option | [note: column 3 of 3] 30\n'
  'p1 | grid | option | 70',
  ['10 20 30', '90 80 70'],
  False),
 ("opts note 'column 2 of 3, not 3'",
  'p1 | grid | option | [note: column 1 of 3] 10\n'
  'p1 | grid | option | 90\n'
  "p1 | grid | option | [note: column 2 of 3, isn't column 1] 20\n"
  'p1 | grid | option | 80\n'
  'p1 | grid | option | [note: column 3 of 3] 30\n'
  'p1 | grid | option | 70',
  ['10 20 30', '90 80 70'],
  False),
 ("opts note in other lang 'columna 2 de 3'?",
  'p1 | grid | option | [note: column 1 of 3] 10\n'
  'p1 | grid | option | 90\n'
  'p1 | grid | option | [note: column 2 of 3] 20\n'
  'p1 | grid | option | 80\n'
  'p1 | grid | option | [note: column 3 of 3] 30\n'
  'p1 | grid | option | 70',
  ['10 20 30', '90 80 70'],
  True),
 ("opts negated 'not column 1 of 3'",
  'p1 | grid | option | [note: kein column 1 of 3] 10\n'
  'p1 | grid | option | 90\n'
  'p1 | grid | option | [note: column 2 of 3] 20\n'
  'p1 | grid | option | 80\n'
  'p1 | grid | option | [note: column 3 of 3] 30\n'
  'p1 | grid | option | 70',
  ['10 20 30', '90 80 70'],
  False),
 ('opts num with comma 1,0',
  'p1 | grid | option | [note: column 1 of 3] 1,0\n'
  'p1 | grid | option | 90\n'
  'p1 | grid | option | [note: column 2 of 3] 20\n'
  'p1 | grid | option | 80\n'
  'p1 | grid | option | [note: column 3 of 3] 30\n'
  'p1 | grid | option | 70',
  ['1,0 20 30', '90 80 70'],
  False),
 ('opts negative',
  'p1 | grid | option | [note: column 1 of 3] -10\n'
  'p1 | grid | option | 90\n'
  'p1 | grid | option | [note: column 2 of 3] 20\n'
  'p1 | grid | option | 80\n'
  'p1 | grid | option | [note: column 3 of 3] 30\n'
  'p1 | grid | option | 70',
  ['-10 20 30', '90 80 70'],
  True),
 ('opts minus sign U+2212',
  'p1 | grid | option | [note: column 1 of 3] −10\n'
  'p1 | grid | option | 90\n'
  'p1 | grid | option | [note: column 2 of 3] 20\n'
  'p1 | grid | option | 80\n'
  'p1 | grid | option | [note: column 3 of 3] 30\n'
  'p1 | grid | option | 70',
  ['-10 20 30', '90 80 70'],
  True),
 ('opts top/bottom swapped',
  'p1 | grid | option | [note: column 1 of 3] 90\n'
  'p1 | grid | option | 10\n'
  'p1 | grid | option | [note: column 2 of 3] 80\n'
  'p1 | grid | option | 20\n'
  'p1 | grid | option | [note: column 3 of 3] 70\n'
  'p1 | grid | option | 30',
  ['10 20 30', '90 80 70'],
  False),
 ('opts note on bottom instead',
  'p1 | grid | option | 10\n'
  'p1 | grid | option | [note: column 1 of 3] 90\n'
  'p1 | grid | option | 20\n'
  'p1 | grid | option | [note: column 2 of 3] 80\n'
  'p1 | grid | option | 30\n'
  'p1 | grid | option | [note: column 3 of 3] 70',
  ['10 20 30', '90 80 70'],
  False),
 ('opts preceded by stray option',
  'p1 | grid | option | 55\n'
  'p1 | grid | option | [note: column 1 of 3] 10\n'
  'p1 | grid | option | 90\n'
  'p1 | grid | option | [note: column 2 of 3] 20\n'
  'p1 | grid | option | 80\n'
  'p1 | grid | option | [note: column 3 of 3] 30\n'
  'p1 | grid | option | 70',
  ['10 20 30', '90 80 70'],
  False),
 ('pos baseline',
  'p1 | grid column a top | text | 10\n'
  'p1 | grid column a bottom | text | 90\n'
  'p1 | grid column b top | text | 20\n'
  'p1 | grid column b bottom | text | 80\n'
  'p1 | grid column c top | text | 30\n'
  'p1 | grid column c bottom | text | 70',
  ['10 20 30', '90 80 70'],
  True),
 ('pos bottom before top',
  'p1 | grid column a bottom | text | 90\n'
  'p1 | grid column a top | text | 10\n'
  'p1 | grid column b bottom | text | 80\n'
  'p1 | grid column b top | text | 20\n'
  'p1 | grid column c bottom | text | 70\n'
  'p1 | grid column c top | text | 30',
  ['10 20 30', '90 80 70'],
  True),
 ("pos 'column 1 upper/lower'",
  'p1 | grid column 1 upper | text | 10\n'
  'p1 | grid column 1 lower | text | 90\n'
  'p1 | grid column 2 upper | text | 20\n'
  'p1 | grid column 2 lower | text | 80\n'
  'p1 | grid column 3 upper | text | 30\n'
  'p1 | grid column 3 lower | text | 70',
  ['10 20 30', '90 80 70'],
  True),
 ('pos tops all first then bottoms',
  'p1 | grid column a top | text | 10\n'
  'p1 | grid column b top | text | 20\n'
  'p1 | grid column c top | text | 30\n'
  'p1 | grid column a bottom | text | 90\n'
  'p1 | grid column b bottom | text | 80\n'
  'p1 | grid column c bottom | text | 70',
  ['10 20 30', '90 80 70'],
  True),
 ('pos column order c,a,b',
  'p1 | grid column c top | text | 10\n'
  'p1 | grid column c bottom | text | 90\n'
  'p1 | grid column a top | text | 20\n'
  'p1 | grid column a bottom | text | 80\n'
  'p1 | grid column b top | text | 30\n'
  'p1 | grid column b bottom | text | 70',
  ['10 20 30', '90 80 70'],
  True),
 ("pos 'column a top' in kind with different kinds",
  'p1 | grid | column a top | 10\n'
  'p1 | grid | column a bottom | 90\n'
  'p1 | grid | column b top | 20\n'
  'p1 | grid | column b bottom | 80\n'
  'p1 | grid | column c top | 30\n'
  'p1 | grid | column c bottom | 70',
  ['10 20 30', '90 80 70'],
  True),
 ("pos uncertain note doubt variant '20?'",
  'p1 | grid column a top | text | 10\n'
  'p1 | grid column a bottom | text | 90\n'
  'p1 | grid column b top | text | 20 [note: 26?]\n'
  'p1 | grid column b bottom | text | 80\n'
  'p1 | grid column c top | text | 30\n'
  'p1 | grid column c bottom | text | 70',
  ['10 20 30', '90 80 70'],
  False),
 ("pos 'Column A Top' caps",
  'p1 | grid Column A Top | text | 10\n'
  'p1 | grid Column A Bottom | text | 90\n'
  'p1 | grid Column B Top | text | 20\n'
  'p1 | grid Column B Bottom | text | 80\n'
  'p1 | grid Column C Top | text | 30\n'
  'p1 | grid Column C Bottom | text | 70',
  ['10 20 30', '90 80 70'],
  True),
 ('pos interleaved other table',
  'p1 | grid column a top | text | 10\n'
  'p1 | grid column a bottom | text | 90\n'
  'p1 | other column a top | text | 20\n'
  'p1 | other column a bottom | text | 80\n'
  'p1 | grid column b top | text | 30\n'
  'p1 | grid column b bottom | text | 70',
  ['10 30', '90 70'],
  False)]

TABLES = [('swap baseline',
  [['', 'Left', 'Right'], ['Up', '5', '4'], ['Down', '6', '7']],
  'p1 | 1 | label | column head 1 | Left\n'
  'p1 | 1 | label | column head 2 | Right\n'
  'p1 | 1 | label | row label 1 | Up\n'
  'p1 | 1 | label | row label 2 | Down\n'
  'p1 | 1 | cell | row Up / column Left | 4\n'
  'p1 | 1 | cell | row Up / column Right | 5',
  ['4', '5']),
 ("swap, naming 'row up, column left'",
  [['', 'Left', 'Right'], ['Up', '5', '4'], ['Down', '6', '7']],
  'p1 | 1 | label | column head 1 | Left\n'
  'p1 | 1 | label | column head 2 | Right\n'
  'p1 | 1 | label | row label 1 | Up\n'
  'p1 | 1 | label | row label 2 | Down\n'
  'p1 | 1 | cell | row Up, column Left | 4\n'
  'p1 | 1 | cell | row Up, column Right | 5',
  ['4', '5']),
 ("swap, naming 'Up / Left'",
  [['', 'Left', 'Right'], ['Up', '5', '4'], ['Down', '6', '7']],
  'p1 | 1 | label | column head 1 | Left\n'
  'p1 | 1 | label | column head 2 | Right\n'
  'p1 | 1 | label | row label 1 | Up\n'
  'p1 | 1 | label | row label 2 | Down\n'
  'p1 | 1 | cell | Up / Left | 4\n'
  'p1 | 1 | cell | Up / Right | 5',
  ['4', '5']),
 ("swap, naming 'row 1 / column 1'",
  [['', 'Left', 'Right'], ['Up', '5', '4'], ['Down', '6', '7']],
  'p1 | 1 | label | column head 1 | Left\n'
  'p1 | 1 | label | column head 2 | Right\n'
  'p1 | 1 | label | row label 1 | Up\n'
  'p1 | 1 | label | row label 2 | Down\n'
  'p1 | 1 | cell | row 1 / column 1 | 4\n'
  'p1 | 1 | cell | row 1 / column 2 | 5',
  ['4', '5']),
 ("swap, 'row Up / column Left, underlined'",
  [['', 'Left', 'Right'], ['Up', '5', '4'], ['Down', '6', '7']],
  'p1 | 1 | label | column head 1 | Left\n'
  'p1 | 1 | label | column head 2 | Right\n'
  'p1 | 1 | label | row label 1 | Up\n'
  'p1 | 1 | label | row label 2 | Down\n'
  'p1 | 1 | cell | row Up / column Left, underlined | 4\n'
  'p1 | 1 | cell | row Up / column Right, underlined | 5',
  ['4', '5']),
 ("swap, 'row Up / column Left, line 1 of 1'",
  [['', 'Left', 'Right'], ['Up', '5', '4'], ['Down', '6', '7']],
  'p1 | 1 | label | column head 1 | Left\n'
  'p1 | 1 | label | column head 2 | Right\n'
  'p1 | 1 | label | row label 1 | Up\n'
  'p1 | 1 | label | row label 2 | Down\n'
  'p1 | 1 | cell | row Up / column Left (bold) | 4\n'
  'p1 | 1 | cell | row Up / column Right (bold) | 5',
  ['4', '5']),
 ('swap, naming with nbsp',
  [['', 'Left', 'Right'], ['Up', '5', '4'], ['Down', '6', '7']],
  'p1 | 1 | label | column head 1 | Left\n'
  'p1 | 1 | label | column head 2 | Right\n'
  'p1 | 1 | label | row label 1 | Up\n'
  'p1 | 1 | label | row label 2 | Down\n'
  'p1 | 1 | cell | row\xa0Up / column Left | 4\n'
  'p1 | 1 | cell | row\xa0Up / column Right | 5',
  ['4', '5']),
 ('swap, naming in a note',
  [['', 'Left', 'Right'], ['Up', '5', '4'], ['Down', '6', '7']],
  'p1 | 1 | label | column head 1 | Left\n'
  'p1 | 1 | label | column head 2 | Right\n'
  'p1 | 1 | label | row label 1 | Up\n'
  'p1 | 1 | label | row label 2 | Down\n'
  'p1 | 1 | cell | 4 [note: row Up / column Left]\n'
  'p1 | 1 | cell | 5 [note: row Up / column Right]',
  ['4', '5']),
 ('swap, naming in screen field',
  [['', 'Left', 'Right'], ['Up', '5', '4'], ['Down', '6', '7']],
  'p1 | 1 | label | column head 1 | Left\n'
  'p1 | 1 | label | column head 2 | Right\n'
  'p1 | 1 | label | row label 1 | Up\n'
  'p1 | 1 | label | row label 2 | Down\n'
  'p1 | 1 row Up / column Left | cell | 4\n'
  'p1 | 1 row Up / column Right | cell | 5',
  ['4', '5']),
 ("swap, 'row Up / column Left' + also wrong row in other reading line",
  [['', 'Left', 'Right'], ['Up', '5', '4'], ['Down', '6', '7']],
  'p1 | 1 | label | column head 1 | Left\n'
  'p1 | 1 | label | column head 2 | Right\n'
  'p1 | 1 | label | row label 1 | Up\n'
  'p1 | 1 | label | row label 2 | Down\n'
  'p1 | 1 | cell | row Up / column Left | 4\n'
  'p1 | 1 | cell | row Up / column Right | 5\n'
  'p1 | 1 | cell | 4\n'
  'p1 | 1 | cell | 5',
  ['4', '5']),
 ('heads swapped',
  [['', 'Left', 'Right'], ['Up', '5', '4'], ['Down', '6', '7']],
  'p1 | 1 | label | column head 1 | Right\n'
  'p1 | 1 | label | column head 2 | Left\n'
  'p1 | 1 | label | row label 1 | Up\n'
  'p1 | 1 | label | row label 2 | Down',
  ['Left', 'Right']),
 ("heads swapped, kind 'column head 1'",
  [['', 'Left', 'Right'], ['Up', '5', '4'], ['Down', '6', '7']],
  'p1 | 1 | column head 1 | Right\np1 | 1 | column head 2 | Left',
  ['Left', 'Right']),
 ("heads swapped, 'column heading 1'",
  [['', 'Left', 'Right'], ['Up', '5', '4'], ['Down', '6', '7']],
  'p1 | 1 | label | column heading 1 | Right\np1 | 1 | label | column heading 2 | Left',
  ['Left', 'Right']),
 ("heads swapped, 'header 1'",
  [['', 'Left', 'Right'], ['Up', '5', '4'], ['Down', '6', '7']],
  'p1 | 1 | label | header 1 | Right\np1 | 1 | label | header 2 | Left',
  ['Left', 'Right']),
 ('dup col heads',
  [['', 'X', 'X'], ['Up', '5', '4']],
  'p1 | 1 | label | column head 1 | X\n'
  'p1 | 1 | label | column head 2 | X\n'
  'p1 | 1 | cell | row Up / column X | 4\n'
  'p1 | 1 | cell | row Up / column X | 5',
  ['4', '5']),
 ('value appears unnamed elsewhere on page',
  [['', 'Left', 'Right'], ['Up', '5', '4'], ['Down', '6', '7']],
  'p1 | 1 | label | column head 1 | Left\n'
  'p1 | 1 | label | column head 2 | Right\n'
  'p1 | 1 | label | row label 1 | Up\n'
  'p1 | 1 | label | row label 2 | Down\n'
  'p1 | 1 | cell | row Up / column Left | 4\n'
  'p1 | 1 | cell | row Up / column Right | 5\n'
  'p1 | 1 | text | Score 5 [note: footnote]',
  []),
 ('dup row labels by normalisation',
  [['', 'Left'], ['Up', '5'], ['up ', '4']],
  'p1 | 1 | label | column head 1 | Left\n'
  'p1 | 1 | cell | row Up / column Left | 4\n'
  'p1 | 1 | cell | row Up / column Left | 5',
  ['4', '5']),
 ('named multi-line cell, wrong position',
  [['', 'Left'], ['Up', 'You keep the tokens.'], ['Down', 'Other']],
  'p1 | 1 | cell | row Down / column Left, line 1 | You keep\n'
  'p1 | 1 | cell | row Down / column Left, line 2 | the tokens.',
  ['You keep the tokens.']),
 ('named multi-line cell, right position',
  [['', 'Left'], ['Up', 'You keep the tokens.']],
  'p1 | 1 | cell | row Up / column Left, line 1 | You keep\n'
  'p1 | 1 | cell | row Up / column Left, line 2 | the tokens.',
  []),
 ('served k-line cell, reading names other row',
  [['', 'Left'], ['Up', 'Price:\nTen tokens.'], ['Down', 'x']],
  'p1 | 1 | cell | row Down / column Left, line 1 | Price:\n'
  'p1 | 1 | cell | row Down / column Left, line 2 | Ten tokens.',
  ['Price:\nTen tokens.']),
 ('served k-line cell, unnamed label+sentence cells',
  [['', 'Left'], ['Up', 'Price:\nTen tokens.'], ['Down', 'x']],
  'p1 | 1 | cell | Price:\np1 | 1 | cell | Ten tokens.',
  []),
 ("rule k: 'line 1, bold' documented tail",
  [['', 'Left'], ['Up', 'You keep']],
  'p1 | 1 | label | column head 1 | Left\n'
  'p1 | 1 | label | row label 1 | Up\n'
  'p1 | 1 | cell | row Up / column Left, line 1, bold | You keep\n'
  'p1 | 1 | cell | row Up / column Left, line 2, bold | the tokens.',
  ['You keep'])]


def gap_prot(a1='Your token "', a2='" is worth', a3="coins.", codes="123", free=False):
    data = {"g": {"a1": {"text": a1, "cite": c()}, "a2": {"text": a2, "cite": c()},
                  "a3": {"text": a3, "cite": c()}, "pic": {"src": "pics/star.png"}}}
    tpl = "{'text': data['g']['a2']['text'] + ' ' + str(int(answer('pick.n'))) + ' ' + data['g']['a3']['text']}"
    resp = {"id": "n", "kind": "number"} if free else {"id": "n", "kind": "choice",
                                                       "options": [{"code": k} for k in codes]}
    stages = {"pick": {"responses": [resp]},
              "show": {"content": [{"id": "t1", "value": {"expr": "data['g']['a1']"}},
                                   {"id": "i1", "type": "image", "value": {"expr": "data['g']['pic']"}},
                                   {"id": "t2", "value": {"expr": tpl}}, {"id": "t3", "value": "Next page."}]}}
    return proto(data=data, stages=stages)


class ReviewRound2(unittest.TestCase):
    def test_found(self):
        for name, text, reading, want in FOUND:
            self.assertEqual(check(proto(text), reading)["found"], want, name)

    def test_image_gap(self):
        for name, line, kw, want in GAP:
            v = check(gap_prot(**kw), "p1 | 1 | text | " + line)
            self.assertEqual("image_gap" in set(rules(v).values()), want, name)

    def test_column_rows(self):
        rl = "p1 | grid | label | Mine\np1 | grid | label | Theirs\n"
        for name, r, rows, want in COLUMN_ROWS:
            lines = [{"text": t, "cite": c()} for t in ["Mine", "Theirs"] + rows]
            v = check(proto(data={"img": {"src": "pics/grid.png", "lines": lines}}), rl + r, header="")   # legacy
            self.assertEqual("column_rows" in set(rules(v).values()), want, name)

    def test_named_tables_never_confirm_a_wrong_cell(self):
        for name, rows, reading, bad in TABLES:
            p = proto(data={"t": {"rows": [[{"text": x, "cite": c()} if x else {"text": ""} for x in row]
                                           for row in rows]}})
            unc = {k[2] for k in check(p, reading)["image_unconfirmed"]}
            self.assertEqual([b for b in bad if b not in unc], [], name)


class FormatGate(unittest.TestCase):
    """Readings without 'format v3' in their header are LEGACY: the old rules behave as before pass 3 round 2 (no
    regression for collected readings); the segmentation rules still need every note clause in the grammar."""

    def test_doubt_note(self):
        self.assertEqual(check(proto("20"), "p1 | 1 | text | 20 [note: 26?]")["found"], 0)
        self.assertEqual(check(proto("20"), "p1 | 1 | text | 20 [note: 26?]", header="")["found"], 0)   # legacy too
        v = check(proto("• Be kind."), "p1 | 1 | text | Be kind. [note: bulleted; maybe]", header="")
        self.assertEqual(v["found"], 0)   # a doubt keeps a legacy line from the segmentation rules

    def test_unparsed_position_names(self):
        rows = [["", "Left", "Right"], ["Up", "5", "4"]]
        p = proto(data={"t": {"rows": [[{"text": x, "cite": c()} if x else {"text": ""} for x in row] for row in rows]}})
        r = "p1 | 1 | cell | row Up, column Left | 4\np1 | 1 | cell | row Up, column Right | 5"
        self.assertTrue({"4", "5"} <= {k[2] for k in check(p, r)["image_unconfirmed"]})
        self.assertFalse({"4", "5"} & {k[2] for k in check(p, r, header="")["image_unconfirmed"]})   # old behaviour

    def test_unrecognised_note_line_between(self):
        r = "p1 | 1 | label | Rules:\np1 | 1 | note | [note: a printed line here: stop]\np1 | 1 | text | Be kind."
        self.assertEqual(check(proto("Rules:\nBe kind."), r)["found"], 0)
        self.assertEqual(rules(check(proto("Rules:\nBe kind."), r, header="")), {"Rules:\nBe kind.": "multiline"})

    def test_rule_k_markers_only(self):
        for hdr in ("", None):
            kw = {} if hdr is None else {"header": hdr}
            # a remark mentioning a line is no rule-k marker (legacy confirms); v3 (S1) never lets such a line
            # confirm alone; 'cropped' in a style field is a doubt in both formats (S2/S3)
            self.assertEqual(check(proto("Be kind."), "p1 | 1 | text | Be kind. [note: at the start of line 3 a dot]",
                                   **kw)["found"], 1 if hdr == "" else 0)
            self.assertEqual(check(proto("Be kind."), "p1 | 1 | label | [photo 1: sign, line 1, cropped] | Be kind.",
                                   **kw)["found"], 0)
            self.assertEqual(check(proto("Be kind."), "p1 | 1 | label | [photo 1: sign, line 1] | Be kind.",
                                   **kw)["found"], 1 if hdr == "" else 0)
            # a marker part of the style field or a whole note clause is
            self.assertEqual(check(proto("You keep"), "p1 | 1 | text | bold, line 1 | You keep\n"
                                                      "p1 | 1 | text | bold, line 2 | the tokens.", **kw)["found"], 0)
            self.assertEqual(check(proto("You keep"), "p1 | 1 | text | You keep [note: line 1 of 2]\n"
                                                      "p1 | 1 | text | the tokens. [note: line 2 of 2]", **kw)["found"], 0)


if __name__ == "__main__":
    unittest.main()
