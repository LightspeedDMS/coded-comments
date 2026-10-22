"""Table-driven comment/code line counter for non-Python host syntaxes (analysis tooling only)."""

# line: line-comment openers; blocks: (open, close); quotes: string delimiters;
# multiline: quote chars whose strings may span lines; hash_at_token_start: shell '#' rule.
SPECS = {
    "shell": {"line": ("#",), "blocks": (), "quotes": "'\"", "multiline": "", "hash_at_token_start": True},
    "go": {"line": ("//",), "blocks": (("/*", "*/"),), "quotes": "'\"`", "multiline": "`"},
    "rust": {"line": ("//",), "blocks": (("/*", "*/"),), "quotes": '"', "multiline": ""},
    "csharp": {"line": ("//",), "blocks": (("/*", "*/"),), "quotes": "'\"", "multiline": ""},
    "java": {"line": ("//",), "blocks": (("/*", "*/"),), "quotes": "'\"", "multiline": ""},
    "c": {"line": ("//",), "blocks": (("/*", "*/"),), "quotes": "'\"", "multiline": ""},
    "cpp": {"line": ("//",), "blocks": (("/*", "*/"),), "quotes": "'\"", "multiline": ""},
    "pascal": {"line": ("//",), "blocks": (("{", "}"), ("(*", "*)")), "quotes": "'", "multiline": ""},
    "sql": {"line": ("--",), "blocks": (("/*", "*/"),), "quotes": "'\"", "multiline": ""},
}


def count_lines(text, lang):
    """Return (comment_lines, code_lines); a mixed line counts once in each, blank in neither."""
    spec = SPECS[lang]
    comments = codes = 0
    quote = None
    block_close = None
    for lineno, line in enumerate(text.splitlines()):
        if lang == "shell" and lineno == 0 and line.startswith("#!"):
            continue
        has_comment = has_code = False
        escaped = False
        i = 0
        while i < len(line):
            ch = line[i]
            if block_close:
                has_comment = True
                if line.startswith(block_close, i):
                    i += len(block_close)
                    block_close = None
                else:
                    i += 1
            elif quote:
                has_code = True
                if escaped:
                    escaped = False
                elif ch == "\\" and quote != "`":
                    escaped = True
                elif ch == quote:
                    quote = None
                i += 1
            elif any(line.startswith(op, i) for op in spec["line"]) and (
                not spec.get("hash_at_token_start") or i == 0 or line[i - 1].isspace()
            ):
                has_comment = True
                break
            else:
                opened = next((c for o, c in spec["blocks"] if line.startswith(o, i)), None)
                if opened:
                    has_comment = True
                    block_close = opened
                    i += next(len(o) for o, c in spec["blocks"] if c == opened and line.startswith(o, i))
                elif ch in spec["quotes"]:
                    has_code = True
                    quote = ch
                    i += 1
                else:
                    has_code = has_code or not ch.isspace()
                    i += 1
        if quote and quote not in spec["multiline"]:
            quote = None
        comments += has_comment
        codes += has_code
    return comments, codes
