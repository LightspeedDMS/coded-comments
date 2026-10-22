"""Check reference/rules/core.yaml against the grammar, the reviewer slice and the fenced examples (throwaway)."""

import json
import re
import sys
from pathlib import Path

import tiktoken
import yaml

import grammar_check as gc

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "reference" / "rules" / "core.yaml"
SEMANTIC_ONLY = {
    "#^ invariant This function validates the input thoroughly",
    "//^ see hot loop",
}
EXPECTED_HOSTS = 14
HOST_KEYS = sorted(["marker", "line", "block", "doc", "exported", "pragma", "generated"])
HOST_MAX_TOKENS = 150
PLACEHOLDER = re.compile(r"\{(\w+)\}")


def expand(parts, template, extra):
    values = dict(parts)
    values.update(extra)
    text = template
    for _ in range(len(values) + 1):
        new = PLACEHOLDER.sub(lambda m: values[m.group(1)], text)
        if new == text:
            return text
        text = new
    raise ValueError("placeholder expansion did not converge")


def coded_regexes(rules):
    tags = "|".join(rules["tags"])
    return {name: re.compile(expand(rules["parts"], rules["parts"]["coded"], {"marker": marker, "tags": tags}))
            for name, marker in rules["markers"].items()}


def fenced_lines(kind):
    out = []
    for sub in ("reference", "docs"):
        for path in sorted((ROOT / sub).glob("**/*.md")):
            for k, block in gc.FENCE.findall(path.read_text()):
                if k == kind:
                    out += [line for line in block.splitlines() if line.strip()]
    return out


def must_search(pattern, text, what, errors, flags=0):
    match = re.search(pattern, text, flags)
    if match is None:
        errors.append("%s not found" % what)
    return match


def check_examples(regexes, errors):
    for line in fenced_lines("coded"):
        if not any(rx.search(line) for rx in regexes.values()):
            errors.append("coded line does not match any rule regex: " + line)
    matched_bad = {line for line in fenced_lines("bad") if any(rx.search(line) for rx in regexes.values())}
    if matched_bad != SEMANTIC_ONLY:
        errors.append("bad lines matching the regex differ from the pinned semantic-only set: %s" % sorted(
            matched_bad ^ SEMANTIC_ONLY))
    for line in fenced_lines("judged"):
        if not any(rx.search(line) for rx in regexes.values()):
            errors.append("judged line does not match any rule regex: " + line)
    for line in SEMANTIC_ONLY:
        if gc.valid(line):
            errors.append("semantic-only line is accepted by the full checker: " + line)


def check_against_grammar(rules, errors):
    grammar = (ROOT / "reference" / "grammar.md").read_text()
    tags = must_search(r"tag\s+::= (.+)", grammar, "tag production in grammar.md", errors)
    if tags and re.findall(r'"(\w+)"', tags.group(1)) != rules["tags"]:
        errors.append("tags differ from grammar.md")
    exts = must_search(r"ends in `([^`]+)`", grammar, "known extensions in grammar.md", errors)
    yaml_exts = must_search(r"\(\?:([a-z|]+)\)", rules["word_class"]["path"], "extension list in core.yaml", errors)
    if exts and yaml_exts and exts.group(1).split() != yaml_exts.group(1).split("|"):
        errors.append("known extensions differ from grammar.md")
    if rules["word_class"]["symbol"] != gc.SYMBOL.pattern or rules["word_class"]["issue"] != gc.ISSUE.pattern:
        errors.append("symbol/issue patterns differ from grammar_check")
    decision = json.loads((ROOT / ".analysis" / "marker_decision.json").read_text())
    for host, info in decision["hosts"].items():
        opener = rules["hosts"].get(host)
        if opener is None or rules["markers"][opener].replace("\\", "") != info["marker"]:
            errors.append("host marker differs from marker_decision.json: " + host)
    if len(rules["hosts"]) != EXPECTED_HOSTS:
        errors.append("expected %d hosts, got %d" % (EXPECTED_HOSTS, len(rules["hosts"])))


def check_reviewer(rules, errors):
    text = (ROOT / "reference" / "reviewer.md").read_text()
    rows = re.findall(r"^\| `([A-Z]+)` \| ([HML]) \| (block|warn) \|", text, re.M)
    if [(v["id"], v["sev"], v["act"]) for v in rules["violations"]] != rows:
        errors.append("violation table differs from reviewer.md")
    block = must_search(r"```report\n(.*?)```", text, "report example in reviewer.md", errors, re.DOTALL)
    finding, verdict = re.compile(rules["report"]["finding"]), re.compile(rules["report"]["verdict"])
    for line in (block.group(1).splitlines() if block else []):
        if not (finding.match(line) or verdict.match(line)):
            errors.append("report example line matches neither rule: " + line)


def check_budgets(rules, errors):
    text = (ROOT / "reference" / "how.md").read_text()
    section = must_search(r"## Limits\n(.*)", text, "limits table in how.md", errors, re.DOTALL)
    rows = re.findall(r"^\| `(\w+)` \| ([0-9.]+) \|", section.group(1), re.M) if section else []
    table = {key: float(value) for key, value in rows}
    declared = {key: float(value) for key, value in rules.get("budgets", {}).items()}
    if table != declared:
        errors.append("budget limits differ: how.md %s vs core.yaml %s" % (table, declared))


def check_hosts(rules, errors):
    enc = tiktoken.get_encoding("o200k_base")
    directory = ROOT / "reference" / "hosts"
    found = {p.stem for p in directory.glob("*.yaml")}
    if found != set(rules["hosts"]):
        errors.append("host files differ from core.yaml hosts: %s" % sorted(found ^ set(rules["hosts"])))
    for host in sorted(found & set(rules["hosts"])):
        text = (directory / (host + ".yaml")).read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        if not isinstance(data, dict) or sorted(data) != HOST_KEYS:
            errors.append("%s keys differ or file is not a mapping" % host)
            continue
        marker = rules["markers"][rules["hosts"][host]].replace("\\", "")
        if data["marker"] != marker + " ":
            errors.append("%s marker %r differs from core.yaml %r" % (host, data["marker"], marker))
        if not isinstance(data["line"], str) or data["marker"].rstrip() != data["line"] + "^":
            errors.append("%s line %r does not open the marker" % (host, data["line"]))
        size = len(enc.encode(text))
        if size > HOST_MAX_TOKENS:
            errors.append("%s is %d tokens, limit %d" % (host, size, HOST_MAX_TOKENS))


def main():
    rules = yaml.safe_load(RULES.read_text())
    errors = []
    regexes = coded_regexes(rules)
    check_examples(regexes, errors)
    check_against_grammar(rules, errors)
    check_reviewer(rules, errors)
    check_budgets(rules, errors)
    check_hosts(rules, errors)
    for error in errors:
        print("FAIL", error)
    print("rules check: %d regexes, %d violation classes, %d hosts, %d failures" % (
        len(regexes), len(rules["violations"]), len(rules["hosts"]), len(errors)))
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
