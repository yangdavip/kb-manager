"""文本分段引擎"""
from dataclasses import dataclass


@dataclass
class ChunkResult:
    content: str
    char_offset: int
    char_count: int


def chunk_text(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    strategy: str = "fixed",
) -> list[ChunkResult]:
    """将文本按指定策略切分为片段

    Args:
        text: 原始文本
        chunk_size: 每段最大字符数
        chunk_overlap: 相邻段重叠字符数
        strategy: 分段策略 (fixed / paragraph / recursive)
    """
    if not text.strip():
        return []

    if strategy == "paragraph":
        return _chunk_by_paragraph(text, chunk_size, chunk_overlap)
    elif strategy == "recursive":
        return _chunk_recursive(text, chunk_size, chunk_overlap)
    else:
        return _chunk_fixed(text, chunk_size, chunk_overlap)


def _chunk_fixed(text: str, size: int, overlap: int) -> list[ChunkResult]:
    """固定长度滑动窗口分段"""
    chunks = []
    start = 0
    step = max(size - overlap, 1)
    while start < len(text):
        end = min(start + size, len(text))
        content = text[start:end].strip()
        if content:
            chunks.append(ChunkResult(
                content=content,
                char_offset=start,
                char_count=len(content),
            ))
        if end >= len(text):
            break
        start += step
    return chunks


def _chunk_by_paragraph(text: str, size: int, overlap: int) -> list[ChunkResult]:
    """按段落分段（双换行符），超长段落再走固定切分"""
    chunks = []
    paragraphs = text.split("\n\n")
    current = ""
    current_start = 0
    offset = 0

    for para in paragraphs:
        para_text = para.strip()
        if not para_text:
            offset += len(para) + 2
            continue

        if len(current) + len(para_text) + 2 <= size:
            if current:
                current += "\n\n" + para_text
            else:
                current = para_text
                current_start = offset
        else:
            if current:
                chunks.append(ChunkResult(
                    content=current,
                    char_offset=current_start,
                    char_count=len(current),
                ))
            # 超长段落走固定切分
            if len(para_text) > size:
                sub_chunks = _chunk_fixed(para_text, size, overlap)
                for sc in sub_chunks:
                    sc.char_offset += offset
                    chunks.append(sc)
                current = ""
            else:
                current = para_text
                current_start = offset
        offset += len(para) + 2

    if current:
        chunks.append(ChunkResult(
            content=current,
            char_offset=current_start,
            char_count=len(current),
        ))
    return chunks


def _chunk_recursive(text: str, size: int, overlap: int) -> list[ChunkResult]:
    """递归字符分段 — 按 [\n\n, \n, 。, ., , ,  ] 依次尝试切分"""
    separators = ["\n\n", "\n", "。", ".", "！", "!", "？", "?", "；", ";", "，", ",", " ", ""]
    chunks = []

    def _split(t: str, start_offset: int):
        if len(t) <= size:
            if t.strip():
                chunks.append(ChunkResult(
                    content=t.strip(),
                    char_offset=start_offset,
                    char_count=len(t.strip()),
                ))
            return

        # 找一个能在 size 范围内切分的分隔符
        for sep in separators:
            if sep == "":
                # 最终回退到固定切分
                sub = _chunk_fixed(t, size, overlap)
                for sc in sub:
                    sc.char_offset += start_offset
                    chunks.append(sc)
                return

            idx = t.rfind(sep, 0, size)
            if idx > 0:
                part = t[:idx + len(sep)]
                rest = t[idx + len(sep):]
                if part.strip():
                    chunks.append(ChunkResult(
                        content=part.strip(),
                        char_offset=start_offset,
                        char_count=len(part.strip()),
                    ))
                _split(rest, start_offset + idx + len(sep))
                return

    _split(text, 0)
    return chunks
