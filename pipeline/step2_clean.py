"""
Step 2: 文本清洗 — 去掉页眉/页脚/注音/版权页，归一化空白。

输入: artifacts/pages/<vol_id>/*.md
输出: artifacts/pages_clean/<vol_id>/*.md  (同文件名，清洗后内容)
"""
from __future__ import annotations

import re
from pathlib import Path

from pipeline import config

# ---------------------------------------------------------------
# 清洗规则
# ---------------------------------------------------------------

# 页码单独一行的情形：纯数字 / 「第 X 页」 / 「Page X」
PAGE_NUMBER_PAT = re.compile(
    r"(?<!\w)\d{1,3}\s*(?:/\s*\d+)?\s*$|^.{0,5}\s*\d{1,3}\s*/\s*\d{1,3}\s*$",
    re.MULTILINE,
)
PAGE_LABEL_PAT = re.compile(
    r"^\s*(?:第\s*)?\d+\s*(?:页|Page|PAGE)\s*$",
    re.MULTILINE,
)

# 常见页眉页脚关键词（与课文正文无关）
HEADER_FOOTER_KEYWORDS = re.compile(
    r"^(?:PEP|人教|部编|义务教育教科书|外语教学与研究出版社)"
    r"|(?:©\s*[\d,]+\s*(?:人民教育出版社|People's Education Press).*)$",
    re.IGNORECASE | re.MULTILINE,
)

# 版权页特征
COPYRIGHT_PAT = re.compile(
    r"(?:版权归|版权所有|©\s*[\d]{4}\s*)(?:人民教育出版社|People's Education Press|人教).*",
    re.IGNORECASE,
)

# 注音标记（如「你好(nǐ hǎo)」或「ā á ǎ è」）
PINGYIN_PAT = re.compile(r"\([a-zA-Z\s']+\)|[À-ɏ]+")

# 连续空白
MULTI_BLANK = re.compile(r"\n{3,}")


def clean_text(raw: str) -> str:
    lines = raw.splitlines()

    cleaned_lines: list[str] = []
    skip_next = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        # 跳过版权页
        if COPYRIGHT_PAT.search(stripped):
            continue

        # 跳过纯页眉/页脚关键词行
        if HEADER_FOOTER_KEYWORDS.search(stripped) and len(stripped) < 60:
            continue

        # 跳过纯页码行
        if PAGE_NUMBER_PAT.match(stripped) or PAGE_LABEL_PAT.match(stripped):
            continue

        # 去掉行内注音
        stripped = PINGYIN_PAT.sub("", stripped)

        # 去掉行内残留的页码
        stripped = re.sub(r"\s+\d+\s*$", "", stripped)

        if not stripped:
            skip_next = False
            continue

        cleaned_lines.append(stripped)

    text = "\n".join(cleaned_lines)
    text = MULTI_BLANK.sub("\n\n", text)
    return text.strip()


def process_volume(vol_id: str) -> int:
    src_dir = config.PAGES_DIR / vol_id
    dst_dir = config.ARTIFACTS / "pages_clean" / vol_id
    dst_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for md_path in sorted(src_dir.glob("*.md")):
        raw = md_path.read_text(encoding="utf-8")
        cleaned = clean_text(raw)
        dst_path = dst_dir / md_path.name
        dst_path.write_text(cleaned, encoding="utf-8")
        count += 1
        print(f"[step2]   {vol_id}/{md_path.name}  ({len(cleaned)} chars)")

    return count


def main() -> None:
    vol_ids = set(config.VOLUMES.values())
    total = 0
    for vid in sorted(vol_ids):
        print(f"[step2] processing {vid}")
        total += process_volume(vid)
    print(f"[step2] done: {total} files cleaned")


if __name__ == "__main__":
    main()
