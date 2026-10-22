"""Validate coded-comment examples against grammar.md (tokenizer-based parser; throwaway tooling)."""

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = ("reference", "docs")
RULES = yaml.safe_load((ROOT / "reference" / "rules" / "core.yaml").read_text(encoding="utf-8"))
TAGS = "|".join(RULES["tags"])
ORDER_WORDS = frozenset(RULES["order_words"])
PREFIX = re.compile(r"(?:^|\s)(?:#\^|//\^|--\^) (?:%s) " % TAGS)
TOKEN = re.compile(r"(?P<q>`[^`\n\r]+`)|(?P<op>=>|<=|>=|!=|<|>|=)|(?P<semi>;)|(?P<sp> )|(?P<w>[^\s;<>=!`]+)")
ISSUE = re.compile(r"^#\d+$")
PATH_EXT = re.compile(r"\.(?:py|js|ts|tsx|jsx|go|rs|cs|java|c|h|cc|cpp|hpp|pas|sh|sql|md|yaml|yml|json|toml|xml|cfg|conf|ini|txt)(?::\S+)?$")
SYMBOL = re.compile(r"_|[a-z][A-Z]|[A-Za-z_]\.[A-Za-z_]|::|\(\)$")
FENCE = re.compile(r"```(coded|bad|judged)\n(.*?)```", re.DOTALL)


def classify(word):
    if "`" in word:
        return "quoted"
    if ISSUE.match(word):
        return "issue"
    if word.startswith("doc:"):
        return "doc"
    if "/" in word or PATH_EXT.search(word):
        return "path"
    return "symbol" if SYMBOL.search(word) else "atom"


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


def parse_clause(tokens):
    ops = [i for i, t in enumerate(tokens) if t[0] == "op"]
    if len(ops) > 1:
        return None
    if not ops:
        words = operand_words(tokens)
        return None if words is None else (False, [words])
    i = ops[0]
    left, right = tokens[:i], tokens[i + 1:]
    if left and left[-1][0] == "sp":
        left = left[:-1]
    if right and right[0][0] == "sp":
        right = right[1:]
    lw, rw = operand_words(left), operand_words(right)
    return None if lw is None or rw is None else (True, [lw, rw])


def valid(line):
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


def check_classes():
    expect = {"foo.bar": "symbol", "a.py:f": "path", "src/x": "path", "#12": "issue", "hot": "atom",
              "`Vec<u8>`.len()": "quoted", "1.10": "atom", "config.json": "path", "Foo::bar": "symbol",
              "load()": "symbol", "doc:x": "doc", "abi_version": "symbol", "idle": "atom"}
    bad = {w: (classify(w), want) for w, want in expect.items() if classify(w) != want}
    for w, (got, want) in bad.items():
        print("FAIL classify(%r) = %s, want %s" % (w, got, want))
    return len(bad)


def check_multiline():
    """A quoted literal may not contain LF or CR (fenced examples are single-line, so test here)."""
    cases = ["//^ invariant `a\nb`<=c", "//^ invariant `a\rb`<=c"]
    bad = [c for c in cases if valid(c)]
    for c in bad:
        print("FAIL multiline quoted literal accepted: %r" % c)
    return len(bad)


def main():
    failures, total = check_classes() + check_multiline(), 0
    for sub in SCAN_DIRS:
        for path in sorted((ROOT / sub).glob("**/*.md")):
            for kind, block in FENCE.findall(path.read_text()):
                for line in block.splitlines():
                    if not line.strip():
                        continue
                    total += 1
                    if valid(line) != (kind in ("coded", "judged")):
                        failures += 1
                        print("FAIL %s [%s] %s" % (path.relative_to(ROOT), kind, line))
    print("%d example lines checked, %d failures" % (total, failures))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
