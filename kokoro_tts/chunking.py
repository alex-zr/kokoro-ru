"""Разбиение текста на абзацы, предложения и более короткие куски."""
from __future__ import annotations

import re

_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")
_SOFT_BREAK_CHARS = ",;:—–"


def split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def split_sentences(paragraph: str) -> list[str]:
    """Режет абзац по . ! ? … (сокращения вроде «т. е.» могут разрезаться)."""
    flat = " ".join(paragraph.split())
    return [s.strip() for s in _SENTENCE_END.split(flat) if s.strip()]


def split_in_half(text: str) -> tuple[str, str] | None:
    """Делит текст по границе слов ближе к середине.

    Предпочитает разрез после запятой, точки с запятой, двоеточия или тире.
    Возвращает None, если разрезать нечего (одно слово).
    """
    words = text.split()
    if len(words) < 2:
        return None

    middle = len(" ".join(words)) / 2
    bonus = len(text) * 0.15
    best_index = 0
    best_score = float("inf")
    end = 0
    for i, word in enumerate(words[:-1]):
        end += len(word) + (1 if i else 0)
        score = abs(end - middle)
        if word[-1] in _SOFT_BREAK_CHARS:
            score -= bonus
        if score < best_score:
            best_score = score
            best_index = i

    left = " ".join(words[: best_index + 1])
    right = " ".join(words[best_index + 1 :])
    return left, right
