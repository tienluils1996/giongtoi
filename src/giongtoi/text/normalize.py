"""Chuẩn hoá văn bản tiếng Việt trước khi đưa vào TTS.

Thứ tự xử lý:
  từ điển người dùng → viết tắt → từ tiếng Anh (Việt hoá) → số điện thoại → ngày → giờ
  → tiền → % → "thứ N"/"tháng N" → khoảng "a-b" → đơn vị → số → đánh vần viết tắt lạ.
Các cụm đã thay bằng từ điển được "khoá" bằng placeholder để bước sau không xử lý lại.
"""

from __future__ import annotations

import re
from typing import Literal, Mapping

from .lexicon import (
    ABBREVIATIONS,
    CASE_SENSITIVE_ENGLISH,
    ENGLISH,
    LETTER_NAMES,
    UNITS,
)

EnglishMode = Literal["vietnamize", "native"]

DIGITS = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]
MONTHS = {4: "tư"}

_PH_OPEN, _PH_CLOSE = "", ""


# ---------------------------------------------------------------- số → chữ

def _tens_units(t: int, u: int, has_hundreds: bool) -> list[str]:
    if t == 0:
        if u == 0:
            return []
        return (["lẻ"] if has_hundreds else []) + [DIGITS[u]]
    if t == 1:
        words = ["mười"]
        if u:
            words.append("lăm" if u == 5 else DIGITS[u])
        return words
    words = [DIGITS[t], "mươi"]
    if u == 1:
        words.append("mốt")
    elif u == 5:
        words.append("lăm")
    elif u:
        words.append(DIGITS[u])
    return words


def _three(n: int, full: bool) -> list[str]:
    h, rest = divmod(n, 100)
    t, u = divmod(rest, 10)
    words: list[str] = []
    if h or full:
        words += [DIGITS[h], "trăm"]
    words += _tens_units(t, u, has_hundreds=bool(h or full))
    return words


def _below_billion(n: int, full: bool) -> list[str]:
    scales = ["", "nghìn", "triệu"]
    groups = []
    for _ in range(3):
        n, g = divmod(n, 1000)
        groups.append(g)
    words: list[str] = []
    started = full
    for idx in (2, 1, 0):
        g = groups[idx]
        if g == 0:
            continue
        words += _three(g, full=started)
        if scales[idx]:
            words.append(scales[idx])
        started = True
    return words


def _number_words(n: int, full: bool = False) -> list[str]:
    if n >= 1_000_000_000:
        hi, lo = divmod(n, 1_000_000_000)
        words = _number_words(hi) + ["tỷ"]
        if lo:
            words += _below_billion(lo, full=True)
        return words
    return _below_billion(n, full)


def number_to_words(n: int) -> str:
    if n == 0:
        return "không"
    if n < 0:
        return "âm " + number_to_words(-n)
    return " ".join(_number_words(n))


def digits_to_words(s: str) -> str:
    return " ".join(DIGITS[int(c)] for c in s if c.isdigit())


def _decimal_part(s: str) -> str:
    if s.startswith("0"):
        return digits_to_words(s)
    return number_to_words(int(s))


def _month(m: int) -> str:
    return MONTHS.get(m, number_to_words(m))


# ---------------------------------------------------------------- tiện ích

class _Protector:
    """Thay cụm đã xử lý bằng placeholder, khôi phục ở cuối."""

    def __init__(self) -> None:
        self.items: list[str] = []

    def protect(self, text: str) -> str:
        self.items.append(text)
        # chỉ số mã hoá bằng ký tự riêng (không chứa chữ số) để bước đọc số không đụng vào
        return f"{_PH_OPEN}{chr(0xE100 + len(self.items) - 1)}{_PH_CLOSE}"

    def restore(self, text: str) -> str:
        pattern = re.compile(f"{_PH_OPEN}(.){_PH_CLOSE}")
        while pattern.search(text):
            text = pattern.sub(lambda m: self.items[ord(m.group(1)) - 0xE100], text)
        return text


def _word_pattern(keys, flags=0) -> re.Pattern | None:
    keys = sorted({k for k in keys if k}, key=len, reverse=True)
    if not keys:
        return None
    alt = "|".join(re.escape(k) for k in keys)
    return re.compile(rf"(?<![\w{_PH_OPEN}])(?:{alt})(?![\w])", flags)


def _apply_lexicon(text: str, lexicon: Mapping[str, str], prot: _Protector) -> str:
    """Khoá có chữ hoa → khớp đúng hoa thường; khoá toàn chữ thường → khớp mọi kiểu."""
    sensitive = {k: v for k, v in lexicon.items() if k != k.lower()}
    insensitive = {k.lower(): v for k, v in lexicon.items() if k == k.lower()}
    pat = _word_pattern(sensitive)
    if pat:
        text = pat.sub(lambda m: prot.protect(sensitive[m.group(0)]), text)
    pat = _word_pattern(insensitive, re.IGNORECASE)
    if pat:
        text = pat.sub(lambda m: prot.protect(insensitive[m.group(0).lower()]), text)
    return text


def _apply_english(text: str, prot: _Protector) -> str:
    sensitive = {k.upper(): v for k, v in ENGLISH.items() if k in CASE_SENSITIVE_ENGLISH}
    insensitive = {k: v for k, v in ENGLISH.items() if k not in CASE_SENSITIVE_ENGLISH}
    return _apply_lexicon(_apply_lexicon(text, sensitive, prot), insensitive, prot)


# ---------------------------------------------------------------- các bước

_NUM = r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?"


def _read_number(s: str) -> str:
    """Đọc một chuỗi số theo quy ước Việt: '.' ngăn nghìn, ',' thập phân."""
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", s):
        intpart, _, dec = s.partition(",")
        words = number_to_words(int(intpart.replace(".", "")))
        return words + (f" phẩy {_decimal_part(dec)}" if dec else "")
    if re.fullmatch(r"\d{1,3}(?:,\d{3}){2,}", s):  # 1,000,000 kiểu Anh
        return number_to_words(int(s.replace(",", "")))
    m = re.fullmatch(r"(\d+)[.,](\d+)", s)
    if m:
        return f"{_read_number(m.group(1))} phẩy {_decimal_part(m.group(2))}"
    if len(s) > 1 and s.startswith("0"):
        return digits_to_words(s)
    return number_to_words(int(s))


def _dates(text: str) -> str:
    def full_date(m: re.Match) -> str:
        d, mo, y = int(m.group(2)), int(m.group(3)), int(m.group(4))
        if not (1 <= d <= 31 and 1 <= mo <= 12):
            return m.group(0)
        prefix = m.group(1) or ""
        lead = "" if re.search(r"ngày\s*$", prefix, re.IGNORECASE) else "ngày "
        return f"{prefix}{lead}{number_to_words(d)} tháng {_month(mo)} năm {number_to_words(y)}"

    text = re.sub(r"(\S*\s?)?(?<!\d)(\d{1,2})[/-](\d{1,2})[/-](\d{4})(?!\d)", full_date, text)

    def day_month(m: re.Match) -> str:
        d, mo = int(m.group(2)), int(m.group(3))
        if not (1 <= d <= 31 and 1 <= mo <= 12):
            return m.group(0)
        prefix = m.group(1) or ""
        lead = "" if re.search(r"ngày\s*$", prefix, re.IGNORECASE) else "ngày "
        return f"{prefix}{lead}{number_to_words(d)} tháng {_month(mo)}"

    text = re.sub(r"(\S*\s?)?(?<![\d/])(\d{1,2})/(\d{1,2})(?![\d/])", day_month, text)

    def month_year(m: re.Match) -> str:
        mo, y = int(m.group(1)), int(m.group(2))
        if not 1 <= mo <= 12:
            return m.group(0)
        return f"tháng {_month(mo)} năm {number_to_words(y)}"

    return re.sub(r"(?<![\d/])(\d{1,2})/(\d{4})(?!\d)", month_year, text)


def _times(text: str) -> str:
    def repl(m: re.Match) -> str:
        h, mi = int(m.group(1)), m.group(2)
        if h > 24 or (mi and int(mi) > 59):
            return m.group(0)
        out = f"{number_to_words(h)} giờ"
        if mi and int(mi):
            out += f" {digits_to_words(mi) if mi.startswith('0') else number_to_words(int(mi))} phút"
        return out

    text = re.sub(r"(?<![\d:])(\d{1,2}):(\d{2})(?![\d:])", repl, text)
    return re.sub(r"(?<![\d\w])(\d{1,2})[hg](\d{2})?(?![\w])", repl, text)


def _currency(text: str) -> str:
    text = re.sub(rf"\$\s?({_NUM})", lambda m: f"{_read_number(m.group(1))} đô la", text)
    text = re.sub(
        rf"({_NUM})\s?(?:USD|usd)(?![\w])", lambda m: f"{_read_number(m.group(1))} đô la", text
    )
    text = re.sub(
        rf"({_NUM})\s?(?:đ|₫|VNĐ|VND|vnđ|vnd)(?![\w])",
        lambda m: f"{_read_number(m.group(1))} đồng",
        text,
    )
    return re.sub(rf"({_NUM})\s?[kK](?![\w])", lambda m: f"{_read_number(m.group(1))} nghìn", text)


def _ordinals(text: str) -> str:
    def thu(m: re.Match) -> str:
        n = int(m.group(2))
        word = {1: "nhất", 4: "tư"}.get(n, number_to_words(n))
        return f"{m.group(1)} {word}"

    text = re.sub(r"(?<!\w)([Tt]hứ)\s+(\d{1,2})(?!\d)", thu, text)
    return re.sub(
        r"(?<!\w)([Tt]háng)\s+(\d{1,2})(?![\d/])",
        lambda m: f"{m.group(1)} {_month(int(m.group(2)))}" if 1 <= int(m.group(2)) <= 12 else m.group(0),
        text,
    )


def _units(text: str) -> str:
    keys = sorted(UNITS, key=len, reverse=True)
    alt = "|".join(re.escape(k) for k in keys)
    pat = re.compile(rf"({_NUM})\s?({alt})(?![\w])")
    return pat.sub(lambda m: f"{_read_number(m.group(1))} {UNITS[m.group(2)]}", text)


def _acronyms(text: str) -> str:
    tokens = re.split(r"(\s+)", text)
    words_idx = [i for i, t in enumerate(tokens) if t and not t.isspace()]

    def is_caps(tok: str) -> bool:
        core = tok.strip(".,!?;:\"'()[]…")
        return len(core) >= 2 and core.isupper() and core.isalpha()

    for pos, i in enumerate(words_idx):
        tok = tokens[i]
        m = re.fullmatch(r"([\"'(\[]*)([A-ZĐ]{2,5})([.,!?;:\"')\]…]*)", tok)
        if not m:
            continue
        neighbours = [tokens[words_idx[p]] for p in (pos - 1, pos + 1) if 0 <= p < len(words_idx)]
        if any(is_caps(n) for n in neighbours):
            continue  # đoạn viết hoa toàn bộ → không đánh vần
        spelled = " ".join(LETTER_NAMES[c] for c in m.group(2))
        tokens[i] = f"{m.group(1)}{spelled}{m.group(3)}"
    return "".join(tokens)


def normalize(
    text: str,
    english_mode: EnglishMode = "vietnamize",
    user_lexicon: Mapping[str, str] | None = None,
) -> str:
    prot = _Protector()
    if user_lexicon:
        text = _apply_lexicon(text, user_lexicon, prot)
    text = _apply_lexicon(text, ABBREVIATIONS, prot)
    if english_mode == "vietnamize":
        text = _apply_english(text, prot)

    text = re.sub(r"(?<!\d)0\d{8,10}(?!\d)", lambda m: digits_to_words(m.group(0)), text)
    text = _dates(text)
    text = _times(text)
    text = _currency(text)
    text = re.sub(rf"({_NUM})\s?%", lambda m: f"{_read_number(m.group(1))} phần trăm", text)
    text = _ordinals(text)
    text = re.sub(
        r"(?<![\d\w])(\d+)\s?[-–]\s?(\d+)(?![\d\w])",
        lambda m: f"{_read_number(m.group(1))} đến {_read_number(m.group(2))}",
        text,
    )
    text = _units(text)
    text = re.sub(_NUM, lambda m: _read_number(m.group(0)), text)
    if english_mode == "vietnamize":
        text = _acronyms(text)

    text = prot.restore(text)
    return re.sub(r"\s+", " ", text).strip()
