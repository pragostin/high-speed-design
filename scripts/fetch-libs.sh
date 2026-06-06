#!/usr/bin/env bash
#
# fetch-libs.sh — download the vendored frontend libraries into site/assets/lib/.
# Run once after cloning, and any time you want to refresh the library versions.
#
#   bash scripts/fetch-libs.sh
#
# Requires: npm (only used to download packages; nothing is installed globally).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LIB="$ROOT/site/assets/lib"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

MARKED_VER="12.0.0"
KATEX_VER="0.16.9"
MERMAID_VER="10.9.0"

echo "Fetching libraries into $LIB ..."
mkdir -p "$LIB/katex/contrib" "$LIB/katex/fonts"

cd "$TMP"
npm pack "marked@$MARKED_VER" "katex@$KATEX_VER" "mermaid@$MERMAID_VER" >/dev/null 2>&1

# marked (UMD global)
tar xzf "marked-$MARKED_VER.tgz"
cp package/lib/marked.umd.js "$LIB/marked.umd.js"
rm -rf package

# katex (js + css + auto-render + fonts)
tar xzf "katex-$KATEX_VER.tgz"
cp package/dist/katex.min.js              "$LIB/katex/katex.min.js"
cp package/dist/katex.min.css             "$LIB/katex/katex.min.css"
cp package/dist/contrib/auto-render.min.js "$LIB/katex/contrib/auto-render.min.js"
cp -r package/dist/fonts/*                "$LIB/katex/fonts/"
rm -rf package

# mermaid (UMD global)
tar xzf "mermaid-$MERMAID_VER.tgz"
cp package/dist/mermaid.min.js "$LIB/mermaid.min.js"
rm -rf package

echo "Done. Libraries vendored:"
echo "  marked  $MARKED_VER"
echo "  katex   $KATEX_VER  (+ $(ls "$LIB/katex/fonts" | wc -l | tr -d ' ') font files)"
echo "  mermaid $MERMAID_VER"
