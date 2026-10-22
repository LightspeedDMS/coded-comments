"""Validate coded-comment examples against grammar.md and reference/rules/core.yaml (throwaway tooling).

Everything rule-shaped (markers, tags, order words, word classes, S7 why form, prose signals, budgets) is read from
core.yaml; nothing is hardcoded here. Results per line: INVALID (grammar or S7), BUDGET (valid but over a budgets
limit) or VALID. Prose signals are a separate judged-PROSE report, never a grammar failure.
"""

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = ("reference", "docs")
RULES = yaml.safe_load((ROOT / "reference" / "rules" / "core.yaml").read_text(encoding="utf-8"))
TAGS = "|".join(RULES["tags"])
MARKERS = "|".join(RULES["markers"].values())
ORDER_WORDS = frozenset(RULES["order_words"])
PREFIX = re.compile(r"(?:^|\s)(?:%s) (?P<tag>%s) " % (MARKERS, TAGS))
WHY_FORM = re.compile(RULES["why_form"])
PROSE_SIGNALS = tuple(RULES["prose_signals"])
CLASS_ORDER = tuple(RULES["word_class_order"])
WORD_CLASS = {name: re.compile(pattern) for name, pattern in RULES["word_class"].items()}
BUDGETS = RULES["budgets"]
TOKEN = re.compile(r"(?P<q>`[^`\n\r]+`)|(?P<op>=>|<=|>=|!=|<|>|=)|(?P<semi>;)|(?P<sp> )|(?P<w>[^\s;<>=!`]+)")
QUOTED = re.compile(r"`[^`\n\r]+`")
FENCE = re.compile(r"```(coded|bad|judged|budget)\n(.*?)```", re.DOTALL)
EXPECTED = {"coded": "VALID", "judged": "VALID", "budget": "BUDGET", "bad": "INVALID"}
_ENCODER = []


def classify(word):
    for name in CLASS_ORDER:
        if WORD_CLASS[name].search(word):
            return name
    return "atom"


def tokenize(body):
    tokens, pos = [], 0
    while pos < len(body):
        m = TOKEN.match(body, pos)
        if not m:
            return None
        tokens.append((m.lastgroup, m.group()))
        pos = m.end()
    return tokens


def operand_words(tokens):
    """Return list of words, or None if the operand is malformed (empty, edge/double spaces)."""
    if not tokens or tokens[0][0] == "sp" or tokens[-1][0] == "sp":
        return None
    words, current = [], ""
    for kind, text in tokens:
        if kind == "sp":
            if not current:
                return None
            words.append(current)
            current = ""
        elif kind in ("q", "w"):
            current += text
        else:
            return None
    words.append(current)
    return words


def split_at(tokens, i):
    """Split around the operator at index i, dropping the one optional space on each side of it."""
    left, right = tokens[:i], tokens[i + 1:]
    if left and left[-1][0] == "sp":
        left = left[:-1]
    if right and right[0][0] == "sp":
        right = right[1:]
    return left, right


def parse_side(tokens):
    """side ::= operand ( SP? cmp SP? operand )?  Returns (has_cmp, operand word lists) or None."""
    cmps = [i for i, t in enumerate(tokens) if t[0] == "op"]
    if len(cmps) > 1:
        return None
    if not cmps:
        words = operand_words(tokens)
        return None if words is None else (False, [words])
    lw, rw = (operand_words(part) for part in split_at(tokens, cmps[0]))
    return None if lw is None or rw is None else (True, [lw, rw])


def parse_clause(tokens):
    """clause ::= side ( SP? '=>' SP? side )?  '=>' binds loosest. Returns (has_op, operand word lists) or None."""
    arrows = [i for i, t in enumerate(tokens) if t == ("op", "=>")]
    if len(arrows) > 1:
        return None
    if not arrows:
        return parse_side(tokens)
    sides = [parse_side(part) for part in split_at(tokens, arrows[0])]
    if any(side is None for side in sides):
        return None
    return True, [operand for _, operands in sides for operand in operands]


def grammar_ok(line):
    """Grammar, S5 and S1 only (marker, tag, clauses with one '=>' per clause and one cmp per side, an anchor or
    operator or order word)."""
    m = PREFIX.search(line)
    if not m:
        return False
    tokens = tokenize(line[m.end():])
    if not tokens:
        return False
    clauses, current, after_semi = [], [], False
    for tok in tokens:
        if tok[0] == "semi":
            clauses.append(current)
            current, after_semi = [], True
        elif after_semi and tok[0] == "sp":
            after_semi = False
        else:
            current.append(tok)
            after_semi = False
    clauses.append(current)
    parsed = [parse_clause(c) for c in clauses]
    if any(p is None for p in parsed):
        return False
    return any(has_op or any(classify(w) != "atom" or w in ORDER_WORDS for op in operands for w in op)
               for has_op, operands in parsed)


def s7_ok(line):
    """S7: the first clause of a why line is '<choice>, not <alternative>' (why_form from core.yaml)."""
    m = PREFIX.search(line)
    if not m or m.group("tag") != "why":
        return True
    return WHY_FORM.search(line[m.start("tag"):]) is not None


def valid(line):
    return grammar_ok(line) and s7_ok(line)


def comment_text(line):
    m = PREFIX.search(line)
    return line[m.start():].strip() if m else line.strip()


def token_count(text):
    if not _ENCODER:
        import tiktoken
        _ENCODER.append(tiktoken.get_encoding("o200k_base"))
    return len(_ENCODER[0].encode(text))


def over_budget(line):
    text = comment_text(line)
    return len(text) > BUDGETS["line_chars"] or token_count(text) > BUDGETS["line_tokens"]


def classify_line(line):
    if not valid(line):
        return "INVALID"
    return "BUDGET" if over_budget(line) else "VALID"


def prose_signals(line):
    """Judgment-assist signals found in a coded line outside backtick literals; not a grammar failure."""
    m = PREFIX.search(line)
    if not m:
        return []
    body = " " + QUOTED.sub("", line[m.start("tag"):]) + " "
    return [signal.strip() or signal for signal in PROSE_SIGNALS if signal in body]


def check_classes():
    expect = {"foo.bar": "symbol", "a.py:f": "path", "src/x": "path", "#12": "issue", "hot": "atom",
              "`Vec<u8>`.len()": "quoted", "1.10": "atom", "config.json": "path", "Foo::bar": "symbol",
              "load()": "symbol", "doc:x": "doc", "abi_version": "symbol", "idle": "atom",
              "test:TestFoo": "test", "test:": "atom", "x/test:Y": "path"}
    bad = {w: (classify(w), want) for w, want in expect.items() if classify(w) != want}
    for w, (got, want) in bad.items():
        print("FAIL classify(%r) = %s, want %s" % (w, got, want))
    return len(bad)


def check_multiline():
    """A quoted literal may not contain LF or CR (fenced examples are single-line, so test here)."""
    cases = ["// ^ invariant `a\nb`<=c", "// ^ invariant `a\rb`<=c"]
    bad = [c for c in cases if valid(c)]
    for c in bad:
        print("FAIL multiline quoted literal accepted: %r" % c)
    return len(bad)


def check_markers():
    """Spaced and legacy unspaced markers are both accepted; anything else is not."""
    accepted = ["# ^ hazard a => b", "#^ hazard a => b", "// ^ hazard a => b", "//^ hazard a => b",
                "-- ^ hazard a => b", "--^ hazard a => b", "x = 1  # ^ hazard a => b"]
    rejected = ["#  ^ hazard a => b", "// ^hazard a => b", "/* ^ hazard a => b */", "; ^ hazard a => b"]
    bad = ["accepted marker rejected: " + c for c in accepted if not valid(c)]
    bad += ["rejected marker accepted: " + c for c in rejected if valid(c)]
    for message in bad:
        print("FAIL", message)
    return len(bad)


CLAUSE_ACCEPTED = (
    "# ^ hazard removing X => ints > 4300 digits raise",
    "# ^ hazard removing set_int_max_str_digits(0) => printing ints > 4300 digits raises ValueError",
    "// ^ hazard attempt > 0 => delay <= maxBackoff",
    "// ^ hazard x > 0 => y",
    "// ^ hazard a=>b",
    "// ^ hazard a<b=>c>=d",
    "// ^ hazard float->Duration conversion => negative RetryAfter",
    "// ^ invariant a <= b; c => d = e",
)
CLAUSE_REJECTED = (
    "# ^ coupled a => b => c",
    "# ^ coupled a=>b=>c",
    "// ^ invariant a < b < c",
    "// ^ invariant a<=b<=c",
    "// ^ invariant x >= 1 >= 2",
    "# ^ invariant a < b = c",
    "// ^ hazard a < b < c => d",
    "// ^ hazard a => b < c < d",
    "// ^ hazard a < b => c => d",
    "// ^ hazard removing this => ValueError printing results >4300 digits on CPython (int->str cap)",
    "// ^ hazard a =>",
    "// ^ hazard => a",
    "// ^ hazard a < => b",
)


def check_clauses():
    """S5: '=>' binds loosest. A clause is 'side => side'; each side holds at most one cmp."""
    bad = ["valid clause rejected: " + c for c in CLAUSE_ACCEPTED if not valid(c)]
    bad += ["invalid clause accepted: " + c for c in CLAUSE_REJECTED if valid(c)]
    for message in bad:
        print("FAIL", message)
    return len(bad)


def check_prose_signals():
    """The three real S7 lines carry these signals; a clean line carries none."""
    expect = {
        "//^ why PRAGMAs never read the file, so reading the schema is what rejects a non-database file": ["so"],
        "//^ why double cast: RETURNING always yields a row, but node:sqlite types get() as Record|undefined":
            [":", "but"],
        "//^ why re-check under the write lock: a concurrent migrator may have applied it since the pending scan":
            [":"],
        "// ^ hazard a => b; test:TestX": [],
    }
    bad = {line: (prose_signals(line), want) for line, want in expect.items() if prose_signals(line) != want}
    for line, (got, want) in bad.items():
        print("FAIL prose_signals(%r) = %s, want %s" % (line, got, want))
    return len(bad)


def main():
    failures = check_classes() + check_multiline() + check_markers() + check_clauses() + check_prose_signals()
    total, judged = 0, []
    for sub in SCAN_DIRS:
        for path in sorted((ROOT / sub).glob("**/*.md")):
            for kind, block in FENCE.findall(path.read_text(encoding="utf-8")):
                for line in block.splitlines():
                    if not line.strip():
                        continue
                    total += 1
                    got = classify_line(line)
                    if got != EXPECTED[kind]:
                        failures += 1
                        print("FAIL %s [%s] got %s: %s" % (path.relative_to(ROOT), kind, got, line))
                    signals = prose_signals(line)
                    if signals:
                        judged.append((path.relative_to(ROOT), kind, signals, line))
    for path, kind, signals, line in judged:
        print("judged PROSE %s [%s] signals %s: %s" % (path, kind, signals, line))
    print("%d example lines checked, %d failures; judged PROSE (separate, not failures): %d lines" % (
        total, failures, len(judged)))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
