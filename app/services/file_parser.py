"""文件解析器 — 从不同格式文件中提取纯文本

PDF 解析优先使用 MinerU（深度文档理解），不可用时降级到 pypdf。
MinerU 集成方式：subprocess 调用 mineru CLI，解析输出 Markdown 文件。
"""
import hashlib
import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pypdf
import docx
import markdown
from bs4 import BeautifulSoup

logger = logging.getLogger("kb-manager.file_parser")

# MinerU 可执行文件路径（优先用环境变量指定）
MINERU_BIN = os.environ.get("MINERU_BIN", "mineru")


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
    """PDF 解析：优先 MinerU，降级 pypdf"""
    try:
        text = _parse_pdf_with_mineru(path)
        if text and text.strip():
            logger.info(f"MinerU 解析成功: {path} ({len(text)} chars)")
            return text
        logger.warning(f"MinerU 返回空内容，降级到 pypdf: {path}")
    except FileNotFoundError:
        logger.info("MinerU 未安装，使用 pypdf 解析 PDF")
    except subprocess.TimeoutExpired:
        logger.warning("MinerU 解析超时（5分钟），降级到 pypdf")
    except Exception as e:
        logger.warning(f"MinerU 解析失败: {e}，降级到 pypdf")

    return _parse_pdf_with_pypdf(path)


def _parse_pdf_with_mineru(path: str) -> str:
    """
    使用 MinerU CLI 解析 PDF → Markdown → 纯文本

    MinerU 输出目录结构:
        output/
        └── <filename>/
            ├── <filename>.md      ← 主 Markdown 文件
            ├── images/            ← 提取的图片
            └── ...

    返回 Markdown 文本的纯文本内容。
    """
    with tempfile.TemporaryDirectory(prefix="mineru_") as tmpdir:
        # 调用 mineru CLI
        cmd = [
            MINERU_BIN,
            "-p", path,
            "-o", tmpdir,
            "--task", "doc",
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 分钟超时
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"MinerU 退出码 {result.returncode}: {result.stderr[:500]}"
            )

        # 查找输出的 Markdown 文件
        md_files = list(Path(tmpdir).rglob("*.md"))
        if not md_files:
            raise RuntimeError("MinerU 未生成 Markdown 文件")

        # 合并所有 Markdown 文件内容
        parts = []
        for md_file in sorted(md_files):
            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if content:
                parts.append(content)

        if not parts:
            raise RuntimeError("MinerU 生成的 Markdown 文件为空")

        # 将 Markdown 转为纯文本（保留段落结构）
        raw_md = "\n\n".join(parts)
        return _markdown_to_text(raw_md)


def _markdown_to_text(md: str) -> str:
    """将 Markdown 转为纯文本，去除标记语法但保留文本结构"""
    # 去除图片引用 ![alt](url)
    md = re.sub(r"!\[.*?\]\(.*?\)", "", md)
    # 去除链接 [text](url) → text
    md = re.sub(r"\[(.+?)\]\(.*?\)", r"\1", md)
    # 去除标题标记 #
    md = re.sub(r"^#{1,6}\s+", "", md, flags=re.MULTILINE)
    # 去除加粗/斜体标记
    md = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", md)
    # 去除代码块标记```...```
    md = re.sub(r"```[\s\S]*?```", "", md)
    # 去除行内代码 `code`
    md = re.sub(r"`([^`]+)`", r"\1", md)
    # 去除表格分隔行 |---|
    md = re.sub(r"^\|[-:\s|]+\|$", "", md, flags=re.MULTILINE)
    # 去除表格管道符 | → 空格
    md = re.sub(r"\|", " ", md)
    # 压缩多余空行
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip()


def _parse_pdf_with_pypdf(path: str) -> str:
    """pypdf 降级解析：提取纯文本，丢失版面/表格信息"""
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
