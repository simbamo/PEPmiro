"""
Step 3: 视觉角色检测 — MiniMax-VL-01 识别课本插图中的角色。

输入: artifacts/images/<vol_id>/<lesson_idx>/*.png
输出: artifacts/vision_results.jsonl  (每行一个 image → 识别结果)
"""
from __future__ import annotations

import base64
import json
import re
import time
from pathlib import Path

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from pipeline import config

MINIMAX_BASE = "https://api.minimaxi.com/v1"


def image_to_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def build_vl_payload(image_path: Path, prompt: str) -> dict:
    img_b64 = image_to_base64(image_path)
    return {
        "model": config.MINIMAX_VL_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                    },
                ],
            }
        ],
        "temperature": 0.1,
    }


SYSTEM_PROMPT = (
    "You are an image understanding assistant for an English textbook. "
    "Look at the image carefully and identify all named characters, people, "
    "or animals that appear. For each one, return: name/description, and "
    "briefly what they are doing. Be specific about names if text is visible."
)

USER_PROMPT = (
    "Identify all characters, people, or animals in this textbook image. "
    "For each, give: (1) name/description, (2) one-line action/context. "
    "If no characters are identifiable, say 'No identifiable characters'. "
    "Respond in Chinese if possible, English is also fine."
)


@retry(wait=wait_exponential(min=2, max=10), stop=stop_after_attempt(3))
def call_vl(image_path: Path) -> dict:
    url = f"{MINIMAX_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.MINIMAX_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = build_vl_payload(image_path, USER_PROMPT)

    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    print(f"[step3]   HTTP {resp.status_code}: {resp.text[:300]}")
    resp.raise_for_status()
    data = resp.json()

    # MiniMax error shape
    if "error" in data:
        raise RuntimeError(f"MiniMax API error: {data['error']}")

    # Parse choice
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError(f"No choices in response: {data}")

    message = choices[0].get("message", {})
    content = message.get("content", "")
    if isinstance(content, list):
        content = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
    return {"raw": content, "image": str(image_path)}


def process_lesson(vol_id: str, lesson_idx: str, images_dir: Path) -> list[dict]:
    results: list[dict] = []
    image_files = sorted(images_dir.glob("*.png"))
    if not image_files:
        return results

    print(f"[step3]   {vol_id}/{lesson_idx}: {len(image_files)} images")
    for img_path in image_files:
        try:
            result = call_vl(img_path)
            results.append(
                {
                    "vol_id": vol_id,
                    "lesson_idx": lesson_idx,
                    "image": str(img_path.relative_to(config.PROJECT_ROOT)),
                    "vision_result": result["raw"],
                }
            )
            print(f"[step3]     {img_path.name}: OK")
        except Exception as exc:
            print(f"[step3]     {img_path.name}: ERROR {exc}")
            results.append(
                {
                    "vol_id": vol_id,
                    "lesson_idx": lesson_idx,
                    "image": str(img_path.relative_to(config.PROJECT_ROOT)),
                    "vision_result": f"ERROR: {exc}",
                }
            )
        time.sleep(0.3)  # gentle rate limit

    return results


def main() -> None:
    out_path = config.ARTIFACTS / "vision_results.jsonl"
    all_results: list[dict] = []

    for vol_id in sorted(config.VOLUMES.values()):
        lesson_dirs = sorted((config.IMAGES_DIR / vol_id).glob("*"))
        for lesson_dir in lesson_dirs:
            if not lesson_dir.is_dir():
                continue
            lesson_idx = lesson_dir.name
            results = process_lesson(vol_id, lesson_idx, lesson_dir)
            all_results.extend(results)

    with out_path.open("w", encoding="utf-8") as f:
        for r in all_results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"[step3] done: {len(all_results)} images processed → {out_path}")


if __name__ == "__main__":
    main()
