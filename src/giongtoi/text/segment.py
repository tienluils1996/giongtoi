"""Chia văn bản dài: chương → đoạn → câu (đoạn đọc được cho TTS)."""

from __future__ import annotations

import re
from dataclasses import dataclass

DEFAULT_MAX_CHARS = 220
DEFAULT_MIN_CHARS = 20

# Từ viết tắt kết thúc bằng dấu chấm nhưng không kết thúc câu
_NO_SPLIT_ABBR = {
    "tp.", "mr.", "mrs.", "ms.", "dr.", "st.", "pgs.", "gs.", "ts.", "ths.", "bs.",
    "q.", "p.", "tt.", "ng.", "vs.", "no.", "pgs.ts.",
}


@dataclass
class Chapter:
    title: str
    body: str


@dataclass
class Segment:
    text: str
    paragraph_end: bool = False


def split_chapters(text: str) -> list[Chapter]:
    text = text.replace("\r\n", "\n").strip()
    if re.search(r"^#{1,6}\s+\S", text, re.MULTILINE):
        chapters: list[Chapter] = []
        title, lines = "Mở đầu", []
        for line in text.split("\n"):
            m = re.match(r"^#{1,6}\s+(.*\S)\s*$", line)
            if m:
                chapters.append(Chapter(title, "\n".join(lines).strip()))
                title, lines = m.group(1), []
            else:
                lines.append(line)
        chapters.append(Chapter(title, "\n".join(lines).strip()))
        return [c for c in chapters if c.body]

    parts = [p.strip() for p in re.split(r"\n[ \t]*\n(?:[ \t]*\n)+", text) if p.strip()]
    if len(parts) <= 1:
        return [Chapter("Toàn văn", text)] if text else []
    return [Chapter(f"Phần {i}", p) for i, p in enumerate(parts, 1)]


def _raw_sentences(paragraph: str) -> list[str]:
    pieces = re.split(r"(?<=[.!?…])([\"”’)\]]*)\s+", paragraph)
    # re.split với nhóm bắt → [câu, đuôi, câu, đuôi, ...]
    sentences: list[str] = []
    for i in range(0, len(pieces), 2):
        s = pieces[i] + (pieces[i + 1] if i + 1 < len(pieces) else "")
        if not s.strip():
            continue
        if sentences and _ends_with_abbr(sentences[-1]):
            sentences[-1] = f"{sentences[-1]} {s}"
        else:
            sentences.append(s)
    return [s.strip() for s in sentences]


def _ends_with_abbr(s: str) -> bool:
    last = s.split()[-1].lower() if s.split() else ""
    if last in _NO_SPLIT_ABBR:
        return True
    return bool(re.fullmatch(r"[a-zà-ỹđ]\.", last))  # chữ cái đầu tên: "Nguyễn A. Bình"


def _pack(pieces: list[str], max_chars: int) -> list[str]:
    out: list[str] = []
    cur = ""
    for p in pieces:
        cand = f"{cur} {p}".strip() if cur else p
        if len(cand) <= max_chars:
            cur = cand
        else:
            if cur:
                out.append(cur)
            cur = p
    if cur:
        out.append(cur)
    return out


def _split_long(sentence: str, max_chars: int) -> list[str]:
    if len(sentence) <= max_chars:
        return [sentence]
    clauses = [c for c in re.split(r"(?<=[,;:])\s+", sentence) if c]
    result: list[str] = []
    for chunk in _pack(clauses, max_chars):
        if len(chunk) <= max_chars:
            result.append(chunk)
        else:
            result.extend(_pack(chunk.split(), max_chars))
    return result


def _merge_short(sentences: list[str], min_chars: int, max_chars: int) -> list[str]:
    out: list[str] = []
    buf = ""
    for s in sentences:
        buf = f"{buf} {s}".strip() if buf else s
        if len(buf) >= min_chars:
            out.append(buf)
            buf = ""
    if buf:
        if out and len(out[-1]) + 1 + len(buf) <= max_chars:
            out[-1] = f"{out[-1]} {buf}"
        else:
            out.append(buf)
    return out


def split_sentences(
    text: str,
    max_chars: int = DEFAULT_MAX_CHARS,
    min_chars: int = DEFAULT_MIN_CHARS,
) -> list[Segment]:
    segments: list[Segment] = []
    for para in re.split(r"\n\s*\n", text.strip()):
        para = re.sub(r"\s+", " ", para).strip()
        if not para:
            continue
        pieces: list[str] = []
        for s in _raw_sentences(para):
            pieces.extend(_split_long(s, max_chars))
        pieces = _merge_short(pieces, min_chars, max_chars)
        for i, p in enumerate(pieces):
            segments.append(Segment(p, paragraph_end=(i == len(pieces) - 1)))
    return segments
