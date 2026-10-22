"""Formatter definitions (what to run, on which fixtures, with which default-config command line)."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

if "FMT_TOOLS" not in os.environ:
    sys.exit("FMT_TOOLS must point at the tool install dir (venv/, npm/, gobin/)")
TOOLS = Path(os.environ["FMT_TOOLS"])
VENV, NPM, GOBIN = TOOLS / "venv" / "bin", TOOLS / "npm" / "node_modules" / ".bin", TOOLS / "gobin"

BIN = {name: shutil.which(name) for name in ("black", "ruff", "gofmt", "go", "rustfmt", "dotnet")}
BIN.update({"prettier": str(NPM / "prettier"), "clang-format": str(VENV / "clang-format"),
            "shfmt": str(GOBIN / "shfmt"), "sqlfluff": str(VENV / "sqlfluff")})
for _name, _path in BIN.items():
    if not _path or not Path(_path).is_file():
        sys.exit("required tool not found: %s (%s)" % (_name, _path))

POSITIONS = ["top", "pkgdoc", "decl", "field", "body", "trailing", "test"]
CLANG_STYLES = ["LLVM", "Google", "Chromium", "Mozilla", "WebKit", "Microsoft", "GNU"]
SQL_DIALECTS = ["postgres", "tsql", "sqlite", "oracle"]
CLANG_LANGS = {"c": ["fixture.c"], "cpp": ["fixture.cpp"], "java": ["Fixture.java"], "csharp": ["Fixture.cs"]}
PRETTIER_LANGS = {"typescript": "fixture.ts", "javascript": "fixture.js"}
VERSION_ARGV = {"black": ["--version"], "ruff": ["--version"], "go": ["version"], "rustfmt": ["--version"],
                "prettier": ["--version"], "clang-format": ["--version"], "dotnet": ["--version"],
                "shfmt": ["--version"], "sqlfluff": ["--version"]}


def spec(language, formatter, fixtures, argv, mode="inplace", deindent=True, env=None):
    return {"language": language, "formatter": formatter, "fixtures": fixtures, "argv": argv,
            "mode": mode, "deindent": deindent, "env": env or {}}


def build_specs(workroot):
    dotnet_env = {"DOTNET_CLI_HOME": str(workroot / "dotnet_home"), "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
                  "DOTNET_NOLOGO": "1"}
    specs = [
        spec("python", "black", ["python.py"], lambda p: [BIN["black"], str(p)], deindent=False,
             env={"BLACK_CACHE_DIR": str(workroot / "black_cache")}),
        spec("python", "ruff format", ["python.py"], lambda p: [BIN["ruff"], "format", "--isolated", str(p)],
             deindent=False),
        spec("go", "gofmt", ["fixture_test.go", "pkgdoc_spaced.go", "pkgdoc_legacy.go"],
             lambda p: [BIN["gofmt"], str(p)], mode="stdout"),
        spec("rust", "rustfmt", ["fixture.rs"],
             lambda p: [BIN["rustfmt"], "--edition", "2021", "--config-path", str(p.parent), str(p)]),
        spec("csharp", "dotnet format whitespace", ["Fixture.cs"],
             lambda p: [BIN["dotnet"], "format", "whitespace", "--folder", str(p.parent)], env=dotnet_env),
        spec("shell", "shfmt", ["fixture.sh"], lambda p: [BIN["shfmt"], str(p)], mode="stdout"),
    ]
    for lang, fixture in PRETTIER_LANGS.items():
        specs.append(spec(lang, "prettier", [fixture],
                          lambda p: [BIN["prettier"], "--no-config", "--no-editorconfig", "--write", str(p)]))
    for lang, fixtures in CLANG_LANGS.items():
        for style in CLANG_STYLES:
            specs.append(spec(lang, "clang-format[%s]" % style, fixtures,
                              lambda p, s=style: [BIN["clang-format"], "-i", "--style=" + s, str(p)]))
    for dialect in SQL_DIALECTS:
        specs.append(spec("sql", "sqlfluff format[%s]" % dialect, ["fixture.sql"],
                          lambda p, d=dialect: [BIN["sqlfluff"], "format", "--dialect", d, "--nocolor", str(p)]))
    return specs


def tool_versions():
    out = {}
    for name, args in VERSION_ARGV.items():
        proc = subprocess.run([BIN[name]] + args, capture_output=True, text=True, check=False)
        lines = (proc.stdout.strip() or proc.stderr.strip()).splitlines()
        if proc.returncode != 0 or not lines:
            sys.exit("version probe failed for %s: rc=%d %s" % (name, proc.returncode, proc.stderr.strip()))
        out[name] = lines[0]
    out["gofmt"] = "ships with %s (gofmt has no version flag)" % out["go"]
    return out
