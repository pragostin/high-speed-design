#!/usr/bin/env python3
"""
build_index.py — scan cards/*.md, parse YAML frontmatter, emit site/cards.json.

Run from project root:  python3 scripts/build_index.py
The site reads cards.json for the searchable card list (metadata + body),
sorted newest-first by `date`.
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CARDS_DIR = ROOT / "cards"
OUT = ROOT / "site" / "cards.json"

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def parse_scalar(v: str):
    v = v.strip()
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        if not inner:
            return []
        return [x.strip().strip('"').strip("'") for x in inner.split(",")]
    return v.strip('"').strip("'")


def parse_frontmatter(text: str):
    """Minimal YAML: flat key: value, with [a, b] lists. No nesting needed."""
    meta = {}
    for line in text.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_]+)\s*:\s*(.*)$", line)
        if m:
            meta[m.group(1)] = parse_scalar(m.group(2))
    return meta


def main():
    if not CARDS_DIR.exists():
        print(f"No cards dir at {CARDS_DIR}", file=sys.stderr)
        sys.exit(1)

    cards = []
    for path in sorted(CARDS_DIR.rglob("*.md")):
        raw = path.read_text(encoding="utf-8")
        m = FRONTMATTER_RE.match(raw)
        if not m:
            print(f"  skip (no frontmatter): {path.name}", file=sys.stderr)
            continue
        meta = parse_frontmatter(m.group(1))
        body = m.group(2).strip()

        topics = meta.get("topics", [])
        if isinstance(topics, str):
            topics = [topics] if topics else []
        keywords = meta.get("keywords", [])
        if isinstance(keywords, str):
            keywords = [keywords] if keywords else []

        cards.append({
            "id": path.stem,
            "title": meta.get("title", path.stem),
            "topics": topics,
            "keywords": keywords,
            "date": meta.get("date", "1970-01-01"),
            "summary": meta.get("summary", ""),
            "material": meta.get("material", []),
            "body": body,
        })

    # newest first
    cards.sort(key=lambda c: str(c["date"]), reverse=True)

    # collect the union of topics for the filter chips, by frequency
    topic_counts = {}
    for c in cards:
        for t in c["topics"]:
            topic_counts[t] = topic_counts.get(t, 0) + 1
    topics_sorted = sorted(topic_counts, key=lambda t: (-topic_counts[t], t))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "generated": date.today().isoformat(),
        "count": len(cards),
        "topics": topics_sorted,
        "cards": cards,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(cards)} cards, {len(topics_sorted)} topics -> {OUT}")


if __name__ == "__main__":
    main()
