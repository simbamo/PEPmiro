"""
Step 1: 把 4 册 PDF 拆成「按课文」的文本 + 插图。

输入: pdfs/<册>.pdf  (文件名需与 config.VOLUMES 的 key 对应，如 三上.pdf)
输出:
    artifacts/pages/<vol_id>/<lesson_idx>_<title>.md
    artifacts/images/<vol_id>/<lesson_idx>/<image_id>.png

英文 PEP 课本切分策略:
  1) 扫每页文本，找 "Unit N" 做课文边界
  2) 标题从 "Unit N" 前的非数字行取
  3) 每条边界 → 一篇课文，从该页起到下一边界前一页为止
  4) 课文文本由 page.get_text("text") 拼接，去空白行
  5) 插图 = page.get_images() + 整页渲染图都导出
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import fitz

from pipeline import config


# Patterns for English PEP textbook
# "Unit 1 Making friends" — number + title on same line
UNIT_FULL_PAT = re.compile(r"^\s*Unit\s+(\d+)\s+(.+)\s*$", re.IGNORECASE)
# "Unit 1" alone — look backward for title
UNIT_SINGLE_PAT = re.compile(r"^\s*Unit\s+(\d+)\s*$", re.IGNORECASE)
# Pure number line — skip when searching backward for title
UNIT_NUM_LINE = re.compile(r"^\s*\d+\s*$")


@dataclass
class LessonBoundary:
    vol_id: str
    lesson_idx: int
    title: str
    start_page: int
    end_page: int


def find_unit_boundaries(doc: fitz.Document, vol_id: str) -> list[LessonBoundary]:
    # Parse TOC pages (first 8 pages) to get unit number -> TOC page ref
    PAGE_NUM_PAT = re.compile(r"p\.\s*(\d+)", re.IGNORECASE)
    # Match "N  Title" unit entry in TOC
    UNIT_ENTRY_PAT = re.compile(r"(\d+)\s+([A-Za-z][^\n]{0,40})")

    unit_toc_pages: dict[int, int] = {}  # unit number -> TOC page number
    for pg in range(min(8, len(doc))):
        text = doc[pg].get_text("text")
        # Find unit entries and their following p. ref
        for m in UNIT_ENTRY_PAT.finditer(text):
            num = int(m.group(1))
            if not (1 <= num <= 20):
                continue
            # Look for p. ref after this match (within 200 chars)
            search_region = text[m.end() : m.end() + 200]
            page_m = PAGE_NUM_PAT.search(search_region)
            if page_m:
                toc_page = int(page_m.group(1))
                if num not in unit_toc_pages:
                    unit_toc_pages[num] = toc_page

    # Build unit starts using TOC page numbers
    # Known offset: PDF page = TOC page + 6 (verified from PDF structure)
    OFFSET = 6
    boundaries: list[LessonBoundary] = []
    for unit_num in sorted(unit_toc_pages.keys()):
        toc_pg = unit_toc_pages[unit_num]
        pdf_start = toc_pg + OFFSET
        if pdf_start >= len(doc):
            continue
        # Extract title from the PDF page content
        page_text = doc[pdf_start].get_text("text")
        lines = page_text.splitlines()
        # Title is first substantial non-number, non-"Unit" line
        title = ""
        for j, ln in enumerate(lines[:6]):
            ln_s = ln.strip()
            if not ln_s or len(ln_s) < 3:
                continue
            if UNIT_NUM_LINE.match(ln_s):
                continue
            # Skip standalone "Unit" (no number after)
            if ln_s == "Unit":
                continue
            # Skip "Unit N" (number only, no title on same line)
            if re.match(r"^\s*Unit\s+\d+\s*$", ln_s, re.IGNORECASE):
                continue
            title = ln_s
            break
        if not title:
            title = f"Unit {unit_num}"
        boundaries.append(
            LessonBoundary(
                vol_id=vol_id,
                lesson_idx=unit_num,
                title=title,
                start_page=pdf_start,
                end_page=0,  # filled below
            )
        )

    # Fill end_page = next unit's start - 1
    for i, b in enumerate(boundaries):
        if i + 1 < len(boundaries):
            b.end_page = boundaries[i + 1].start_page - 1
        else:
            b.end_page = len(doc) - 1

    return boundaries


def detect_boundaries(doc: fitz.Document, vol_id: str) -> list[LessonBoundary]:
    boundaries = find_unit_boundaries(doc, vol_id)
    if boundaries:
        return boundaries
    # Fallback: one lesson covering entire doc
    return [
        LessonBoundary(
            vol_id=vol_id,
            lesson_idx=1,
            title="Full Document",
            start_page=0,
            end_page=len(doc) - 1,
        )
    ]


def export_lesson(doc: fitz.Document, b: LessonBoundary) -> dict:
    text_parts: list[str] = []
    image_paths: list[str] = []
    images_out_dir = config.IMAGES_DIR / b.vol_id / f"{b.lesson_idx:02d}"
    images_out_dir.mkdir(parents=True, exist_ok=True)

    img_counter = 0
    for page_no in range(b.start_page, b.end_page + 1):
        page = doc[page_no]
        text_parts.append(page.get_text("text"))

        for xref_info in page.get_images(full=True):
            xref = xref_info[0]
            try:
                pix = fitz.Pixmap(doc, xref)
            except Exception:
                continue
            if pix.width < config.MIN_IMAGE_WIDTH or pix.height < config.MIN_IMAGE_HEIGHT:
                pix = None
                continue
            if pix.n - pix.alpha >= 4:
                pix = fitz.Pixmap(fitz.csRGB, pix)
            out_path = images_out_dir / f"p{page_no:03d}_e{img_counter:02d}.png"
            pix.save(out_path)
            image_paths.append(str(out_path.relative_to(config.PROJECT_ROOT)))
            img_counter += 1
            pix = None

        rendered = page.get_pixmap(dpi=config.PAGE_DPI)
        out_path = images_out_dir / f"page_{page_no:03d}.png"
        rendered.save(out_path)
        image_paths.append(str(out_path.relative_to(config.PROJECT_ROOT)))

    pages_out_dir = config.PAGES_DIR / b.vol_id
    pages_out_dir.mkdir(parents=True, exist_ok=True)
    safe_title = re.sub(r"[\\/<>:\"|?*\s]+", "_", b.title)[:40]
    md_path = pages_out_dir / f"{b.lesson_idx:02d}_{safe_title}.md"
    md = (
        f"# {b.title}\n\n"
        f"- vol: {b.vol_id}\n"
        f"- lesson_idx: {b.lesson_idx}\n"
        f"- pages: {b.start_page}-{b.end_page}\n\n"
        f"---\n\n"
        + "\n\n".join(p.strip() for p in text_parts if p.strip())
    )
    md_path.write_text(md, encoding="utf-8")

    return {
        **asdict(b),
        "md_path": str(md_path.relative_to(config.PROJECT_ROOT)),
        "images": image_paths,
    }


def process_volume(pdf_path: Path) -> list[dict]:
    vol_label = pdf_path.stem
    if vol_label not in config.VOLUMES:
        raise SystemExit(f"unknown volume: {vol_label}, expected one of {list(config.VOLUMES)}")
    vol_id = config.VOLUMES[vol_label]
    print(f"[step1] {vol_label} -> {vol_id}: opening {pdf_path}")
    doc = fitz.open(pdf_path)
    boundaries = detect_boundaries(doc, vol_id)
    print(f"[step1]   detected {len(boundaries)} lessons")

    manifest = []
    for b in boundaries:
        info = export_lesson(doc, b)
        manifest.append(info)
        print(f"[step1]   lesson {b.lesson_idx:02d} {b.title}: pages {b.start_page}-{b.end_page}, images={len(info['images'])}")
    doc.close()
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="only process this volume label, e.g. 三上")
    args = parser.parse_args()

    config.PAGES_DIR.mkdir(parents=True, exist_ok=True)
    config.IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(config.PDF_DIR.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"no PDFs found in {config.PDF_DIR}")

    full_manifest: list[dict] = []
    for pdf in pdfs:
        if args.only and pdf.stem != args.only:
            continue
        full_manifest.extend(process_volume(pdf))

    out = config.ARTIFACTS / "step1_manifest.json"
    out.write_text(json.dumps(full_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[step1] manifest: {out}")


if __name__ == "__main__":
    main()
