from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

PDF_DIR = PROJECT_ROOT / "pdfs"
ARTIFACTS = PROJECT_ROOT / "artifacts"
PAGES_DIR = ARTIFACTS / "pages"
IMAGES_DIR = ARTIFACTS / "images"

VISION_CANDIDATES = ARTIFACTS / "vision_candidates.json"
CHARACTERS_DRAFT = ARTIFACTS / "characters_draft.json"
CHARACTERS_MERGED = ARTIFACTS / "characters_merged.json"
CHARACTERS_FINAL = ARTIFACTS / "characters_final.json"
SEED_MD = ARTIFACTS / "seed.md"

MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_VL_MODEL = os.getenv("MINIMAX_VL_MODEL", "Minimax-VL-01")
MINIMAX_TEXT_MODEL = os.getenv("MINIMAX_TEXT_MODEL", "abab6.5s-chat")
MIROFISH_DIR = os.getenv("MIROFISH_DIR", "")

VOLUMES = {
    "三上": "grade3_vol1",
    "三下": "grade3_vol2",
    "四上": "grade4_vol1",
    "四下": "grade4_vol2",
}

PAGE_DPI = 200
MIN_IMAGE_WIDTH = 200
MIN_IMAGE_HEIGHT = 200
