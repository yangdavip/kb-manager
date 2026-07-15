"""文件解析器 — 从不同格式文件中提取纯文本"""
import hashlib
import os
from pathlib import Path

import pypdf
import docx
import markdown
from bs4 import BeautifulSoup


def compute_hash(file_path: str) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_file(file_path: str) -> str:
    """根据文件扩展名自动选择解析器，返回纯文本"""
    ext = Path(file_path).suffix.lower()
    parser = _PARSERS.get(ext)
    if parser is None:
        raise ValueError(f"不支持的文件格式: {ext}")
    return parser(file_path)


def _parse_txt(path: str) -> str:
    for encoding in ("utf-8", "gbk", "gb2312", "latin-1"):
        try:
            with open(path, "r", encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    raise ValueError(f"无法解码文件: {path}")


def _parse_md(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _parse_pdf(path: str) -> str:
    reader = pypdf.PdfReader(path)
    parts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def _parse_docx(path: str) -> str:
    doc = docx.Document(path)
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _parse_csv(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _parse_json(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _parse_html(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()
    soup = BeautifulSoup(html, "html.parser")
    # 移除 script/style
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


_PARSERS = {
    ".txt": _parse_txt,
    ".md": _parse_md,
    ".markdown": _parse_txt,
    ".pdf": _parse_pdf,
    ".docx": _parse_docx,
    ".csv": _parse_csv,
    ".json": _parse_json,
    ".html": _parse_html,
    ".htm": _parse_html,
}
