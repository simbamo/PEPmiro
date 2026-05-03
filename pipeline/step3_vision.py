"""
Step 3: 视觉角色检测 — MiniMax M2.7 识别课本插图中的角色。

输入: artifacts/images/<vol_id>/<lesson_idx>/*.png
输出: artifacts/vision_results.jsonl  (每行一个 image → 识别结果)
"""
from __future__ import annotations

import base64
import json
import time
from pathlib import Path

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from pipeline import config

# MiniMax supports Anthropic-compatible API at this base URL
MINIMAX_BASE_URL = "https://api.minimaxi.com/v1"

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


def make_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(
        api_key=config.MINIMAX_API_KEY,
        base_url=MINIMAX_BASE_URL,
    )


@retry(wait=wait_exponential(min=2, max=10), stop=stop_after_attempt(3))
def call_vl(client: anthropic.Anthropic, image_path: Path) -> str:
    img_b64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")

    response = client.messages.create(
        model=config.MINIMAX_VL_MODEL,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": USER_PROMPT},
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": img_b64,
                        },
                    },
                ],
            }
        ],
    )

    return response.content[0].text


def process_lesson(
    client: anthropic.Anthropic,
    vol_id: str,
    lesson_idx: str,
    images_dir: Path,
) -> list[dict]:
    results: list[dict] = []
    image_files = sorted(images_dir.glob("*.png"))
    if not image_files:
        return results

    print(f"[step3]   {vol_id}/{lesson_idx}: {len(image_files)} images")
    for img_path in image_files:
        try:
            text = call_vl(client, img_path)
            results.append(
                {
                    "vol_id": vol_id,
                    "lesson_idx": lesson_idx,
                    "image": str(img_path.relative_to(config.PROJECT_ROOT)),
                    "vision_result": text,
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
        time.sleep(0.3)

    return results


def main() -> None:
    client = make_client()
    out_path = config.ARTIFACTS / "vision_results.jsonl"
    all_results: list[dict] = []

    for vol_id in sorted(config.VOLUMES.values()):
        lesson_dirs = sorted((config.IMAGES_DIR / vol_id).glob("*"))
        for lesson_dir in lesson_dirs:
            if not lesson_dir.is_dir():
                continue
            lesson_idx = lesson_dir.name
            results = process_lesson(client, vol_id, lesson_idx, lesson_dir)
            all_results.extend(results)

    with out_path.open("w", encoding="utf-8") as f:
        for r in all_results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"[step3] done: {len(all_results)} images processed → {out_path}")


if __name__ == "__main__":
    main()
