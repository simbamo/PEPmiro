"""
Step 3: 视觉角色检测 — mmx vision describe 识别课本插图中的角色。

输入: artifacts/images/<vol_id>/<lesson_idx>/*.png
输出: artifacts/vision_results.jsonl  (每行一个 image → 识别结果)
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from pipeline import config

PROMPT = (
    "Identify all characters, people, or animals in this textbook image. "
    "For each, give: (1) name/description, (2) one-line action/context. "
    "If no characters are identifiable, say 'No identifiable characters'. "
    "Respond in Chinese if possible, English is also fine."
)


def call_vl(image_path: Path) -> str:
    env = {**os.environ, "NO_PROXY": "*"}
    result = subprocess.run(
        [
            "mmx", "vision", "describe",
            "--image", str(image_path),
            "--prompt", PROMPT,
        ],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"mmx failed: {result.stderr.strip()}")
    return result.stdout.strip()


def process_lesson(vol_id: str, lesson_idx: str, images_dir: Path) -> list[dict]:
    results: list[dict] = []
    image_files = sorted(images_dir.glob("*.png"))
    if not image_files:
        return results

    print(f"[step3]   {vol_id}/{lesson_idx}: {len(image_files)} images")
    for img_path in image_files:
        try:
            text = call_vl(img_path)
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
