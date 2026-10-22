#!/usr/bin/env bash
# Install (or --uninstall) the coded-comments reference tree under $HOME/.claude/coded-comments.
# Touches only that directory. Never edits CLAUDE.md, settings.json, hooks or pace-maker files.
set -euo pipefail

NAME="coded-comments"

if [ -z "${HOME:-}" ]; then
    echo "error: HOME is not set" >&2
    exit 1
fi

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/reference"
TARGET_ROOT="$HOME/.claude"
DEST="$TARGET_ROOT/$NAME"

if [ "${1:-}" = "--uninstall" ]; then
    if [ -d "$DEST" ]; then
        rm -r -- "$DEST"
        echo "removed $DEST"
    else
        echo "nothing to remove at $DEST"
    fi
    exit 0
fi

if [ -n "${1:-}" ]; then
    echo "usage: install.sh [--uninstall]" >&2
    exit 2
fi

for required in ENTRY.md index.md what.md how.md rules/core.yaml hosts; do
    if [ ! -e "$SRC/$required" ]; then
        echo "error: $SRC/$required is missing" >&2
        exit 1
    fi
done

mkdir -p -- "$TARGET_ROOT"
STAGE="$(mktemp -d "$TARGET_ROOT/.$NAME.stage.XXXXXX")"
trap 'rm -rf -- "$STAGE"' EXIT

cp -R -- "$SRC/." "$STAGE/"
chmod 755 -- "$STAGE"
if [ -d "$DEST" ]; then
    rm -r -- "$DEST"
fi
mv -- "$STAGE" "$DEST"
trap - EXIT

echo "installed $NAME to $DEST ($(find "$DEST" -type f | wc -l | tr -d ' ') files)"
echo
echo "Paste this into ~/.claude/CLAUDE.md (not edited automatically):"
echo
cat -- "$DEST/ENTRY.md"
