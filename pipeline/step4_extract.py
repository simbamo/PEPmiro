"""
Step 4: 角色抽取 — MiniMax abab6.5s-chat 从课文文本+插图描述中抽取角色 persona。

输入:
  - artifacts/pages_clean/<vol_id>/*.md  (清洗后课文)
  - artifacts/vision_results.jsonl        (step3 视觉结果)
输出: artifacts/characters_draft.json  (角色草稿列表)
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from pipeline import config

MINIMAX_BASE = "https://api.minimaxi.com/v1"


def call_text(messages: list[dict]) -> str:
    url = f"{MINIMAX_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.MINIMAX_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.MINIMAX_TEXT_MODEL,
        "messages": messages,
        "temperature": 0.3,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    if "error" in data:
        raise RuntimeError(f"MiniMax API error: {data['error']}")

    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError(f"No choices in response: {data}")

    return choices[0]["message"]["content"]


SYSTEM_PROMPT = """You are a helpful assistant that extracts character personas from English textbook content.
Your task is to identify named characters, people, or animals that appear in the text or images,
and for each character extract:
- name (or description if unnamed)
- personality traits (brief, 2-4 adjectives)
- interests / hobbies
- relationships (family, friends, classmates)
- 2-3 example dialogues or catchphrases from the text

Return a JSON array of character objects with these fields.
If multiple characters share the same name across lessons, merge their info.
Only include characters that have a named identity (e.g., "Amy", "Bob the cat"), not generic "children" or "students".
"""


def load_vision_results() -> dict[tuple[str, str], str]:
    results: dict[tuple[str, str], str] = {}
    path = config.ARTIFACTS / "vision_results.jsonl"
    if not path.exists():
        return results
    with path.open(encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            key = (obj["vol_id"], obj["lesson_idx"])
            results[key] = results.get(key, "") + "\n" + obj.get("vision_result", "")
    return results


def extract_for_lesson(
    vol_id: str,
    lesson_idx: str,
    text_content: str,
    vision_content: str,
) -> list[dict]:
    user_msg = f"""Lesson {lesson_idx} from {vol_id}:

=== TEXT CONTENT ===
{text_content[:3000]}

=== IMAGE DESCRIPTIONS ===
{vision_content[:1500]}
"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]

    raw = None
    try:
        raw = call_text(messages)
        # Try to extract JSON array from response
        raw = re.sub(r"^```json\s*", "", raw.strip())
        raw = re.sub(r"\s*```$", "", raw)
        chars = json.loads(raw)
        if isinstance(chars, list):
            for c in chars:
                c["vol_id"] = vol_id
                c["lesson_idx"] = lesson_idx
            return chars
    except Exception as exc:
        print(f"[step4]   {vol_id}/{lesson_idx}: error {exc}, raw: {(raw or '')[:200]}")

    return []


def main() -> None:
    vision_by_lesson = load_vision_results()
    all_chars: list[dict] = []

    for vol_id in sorted(config.VOLUMES.values()):
        clean_dir = config.ARTIFACTS / "pages_clean" / vol_id
        if not clean_dir.exists():
            print(f"[step4]   {vol_id}: no cleaned pages, skipping")
            continue

        for md_path in sorted(clean_dir.glob("*.md")):
            lesson_idx = md_path.stem.split("_")[0]
            text = md_path.read_text(encoding="utf-8")
            vision = vision_by_lesson.get((vol_id, lesson_idx), "")

            print(f"[step4]   {vol_id}/{lesson_idx}: extracting characters...")
            chars = extract_for_lesson(vol_id, lesson_idx, text, vision)
            all_chars.extend(chars)
            print(f"[step4]     found {len(chars)} characters")
            time.sleep(0.3)

    out_path = config.CHARACTERS_DRAFT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(all_chars, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[step4] done: {len(all_chars)} characters → {out_path}")


if __name__ == "__main__":
    main()
