"""
reader.py — 讀取參考資料（PDF、TXT、DOCX）並回傳純文字
"""
import os
import re
import zipfile
from pathlib import Path


def read_reference_files(file_paths: list) -> str:
    """讀取多個參考資料並合併為純文字。"""
    texts = []
    for path in file_paths:
        ext = Path(path).suffix.lower()
        filename = os.path.basename(path)
        try:
            if ext == ".pdf":
                text = _read_pdf(path)
            elif ext in (".txt", ".md"):
                with open(path, "r", encoding="utf-8-sig") as f:
                    text = f.read()
            elif ext == ".docx":
                text = _read_docx(path)
            else:
                continue

            if text.strip():
                texts.append(f"=== {filename} ===\n{text.strip()}")
            else:
                texts.append(f"=== {filename}（內容為空）===")

        except Exception as e:
            texts.append(f"=== {filename} 讀取失敗：{e} ===")

    return "\n\n".join(texts)


def _read_pdf(path: str) -> str:
    """用 PyMuPDF 擷取 PDF 文字，並清理冗餘內容以節省 token。"""
    import fitz  # PyMuPDF

    doc = fitz.open(path)
    all_lines = []
    for page in doc:
        text = page.get_text()
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            # 過濾純數字行（頁碼）
            if line.isdigit():
                continue
            all_lines.append(line)
    doc.close()

    # 去除連續重複行（頁首頁尾常重複）
    deduped = []
    seen_recently: list[str] = []
    for line in all_lines:
        if line not in seen_recently:
            deduped.append(line)
        seen_recently.append(line)
        if len(seen_recently) > 10:
            seen_recently.pop(0)

    return "\n".join(deduped)


def _read_docx(path: str) -> str:
    """用 zipfile 讀取 DOCX XML 並去除標籤，不需要 python-docx。"""
    try:
        with zipfile.ZipFile(path) as z:
            with z.open("word/document.xml") as f:
                xml = f.read().decode("utf-8")
        text = re.sub(r"<[^>]+>", " ", xml)
        text = re.sub(r"\s+", " ", text).strip()
        return text
    except Exception:
        return ""
