"""
Step 1: 把 4 册 PDF 拆成「按课文」的文本 + 插图。

输入: pdfs/<册>.pdf  (文件名需与 config.VOLUMES 的 key 对应，如 三上.pdf)
输出:
    artifacts/pages/<vol_id>/<lesson_idx>_<title>.md
    artifacts/images/<vol_id>/<lesson_idx>/<image_id>.png

切分策略 (启发式):
  1) 扫一遍每页文本，找形如「\\d+ 标题」「第 \\d+ 课 标题」「目录中列出的标题」的行做边界
  2) 每条边界 → 一篇课文，从该页起到下一边界前一页为止
  3) 课文文本由 page.get_text("text") 拼接，去空白行
  4) 插图 = page.get_images() 嵌入图 + 整页渲染图都导出，过滤掉太小的装饰图

切分一定会有错（人教版排版每年微调）。脚本会同时输出 manifest.json 列出所有切边界，
跑完后人工浏览 artifacts/pages/<vol_id>/ 一眼能看出对不对，错了改 manifest 再 --redo 重出。
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import fitz

from pipeline import config


LESSON_HEADER_PATTERNS = [
    re.compile(r"^\s*第\s*([一二三四五六七八九十百千\d]+)\s*课\s+(.+)$"),
    re.compile(r"^\s*(\d{1,2})\s+([一-鿿《].+)$"),
    re.compile(r"^\s*(\d{1,2})\.\s+(.+)$"),
]


@dataclass
class LessonBoundary:
    vol_id: str
    lesson_idx: int
    title: str
    start_page: int
    end_page: int


def detect_boundaries(doc: fitz.Document, vol_id: str) -> list[LessonBoundary]:
    raw: list[tuple[int, int, str]] = []
    for page_no in range(len(doc)):
        text = doc[page_no].get_text("text")
        for line in text.splitlines():
            line = line.strip()
            if not line or len(line) > 40:
                continue
            for pat in LESSON_HEADER_PATTERNS:
                m = pat.match(line)
                if not m:
                    continue
                idx_token, title = m.group(1), m.group(2).strip()
                idx = _parse_idx(idx_token)
                if idx is None or not title:
                    continue
                raw.append((page_no, idx, title))
                break

    by_idx: dict[int, tuple[int, int, str]] = {}
    for page_no, idx, title in raw:
        prev = by_idx.get(idx)
        if prev is None or page_no > prev[0]:
            by_idx[idx] = (page_no, idx, title)
    cleaned = sorted(by_idx.values(), key=lambda x: x[1])

    boundaries: list[LessonBoundary] = []
    for i, (page_no, idx, title) in enumerate(cleaned):
        end = cleaned[i + 1][0] - 1 if i + 1 < len(cleaned) else len(doc) - 1
        boundaries.append(
            LessonBoundary(
                vol_id=vol_id,
                lesson_idx=idx,
                title=title,
                start_page=page_no,
                end_page=end,
            )
        )
    return boundaries


def _parse_idx(token: str) -> int | None:
    if token.isdigit():
        return int(token)
    cn = "零一二三四五六七八九十"
    if all(c in cn for c in token):
        if token == "十":
            return 10
        if token.startswith("十"):
            return 10 + cn.index(token[1])
        if token.endswith("十"):
            return cn.index(token[0]) * 10
        if "十" in token:
            a, b = token.split("十")
            return cn.index(a) * 10 + cn.index(b)
        return cn.index(token)
    return None


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
