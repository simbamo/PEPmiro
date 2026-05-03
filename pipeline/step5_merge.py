"""
Step 5: 角色合并 — 跨课文合并同名角色，去重+归类，得到主要人物表（10-15人）。

输入: artifacts/characters_draft.json   (step4 输出)
输出: artifacts/characters_merged.json
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from pipeline import config


def load_draft() -> list[dict]:
    path = config.CHARACTERS_DRAFT
    if not path.exists():
        raise SystemExit(f"not found: {path}, run step4 first")
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_name(name: str) -> str:
    """Normalise name for matching."""
    return name.strip().lower()


def merge_by_name(chars: list[dict]) -> list[dict]:
    """Group by canonical name, merge traits/dialogues across lessons."""
    buckets: dict[str, list[dict]] = defaultdict(list)
    for c in chars:
        buckets[canonical_name(c.get("name", ""))].append(c)

    merged: list[dict] = []
    for name_key, group in buckets.items():
        if not name_key:
            continue
        # Use the longest/most detailed name
        best = max(group, key=lambda c: len(c.get("name", "")))

        traits = []
        interests = []
        relationships = []
        dialogues = []

        for c in group:
            traits.extend(c.get("personality_traits", []) or [])
            interests.extend(c.get("interests", []) or [])
            relationships.extend(c.get("relationships", []) or [])
            dialogues.extend(c.get("dialogues", []) or [])

        # Deduplicate while preserving order
        def dedup(seq):
            seen, out = set(), []
            for x in seq:
                k = x.lower().strip()
                if k and k not in seen:
                    seen.add(k)
                    out.append(x)
            return out

        # Cap total characters per field
        MAX = 5
        traits = dedup(traits)[:MAX]
        interests = dedup(interests)[:MAX]
        relationships = dedup(relationships)[:MAX]
        dialogues = dedup(dialogues)[:6]

        merged.append(
            {
                "name": best.get("name", name_key),
                "personality_traits": traits,
                "interests": interests,
                "relationships": relationships,
                "dialogues": dialogues,
                "source_lessons": list(
                    set(c.get("lesson_idx", "") for c in group if c.get("lesson_idx"))
                ),
            }
        )

    # Sort by number of source lessons (most appearances first)
    merged.sort(key=lambda c: len(c["source_lessons"]), reverse=True)
    return merged


def main() -> None:
    chars = load_draft()
    print(f"[step5] loaded {len(chars)} draft characters")
    merged = merge_by_name(chars)
    print(f"[step5] merged → {len(merged)} unique characters")

    for c in merged:
        print(f"       {c['name']} ({len(c['source_lessons'])} lessons)")

    out = config.CHARACTERS_MERGED
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[step5] → {out}")


if __name__ == "__main__":
    main()
