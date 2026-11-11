"""Очистка Markdown перед озвучкой.

Убираем разметку, ссылки и код, оставляем текст, который можно читать вслух.
Модуль не зависит от тяжёлых библиотек (torch и т. д.) и легко тестируется.
"""
from __future__ import annotations

import html
import re

DEFAULT_CODE_PLACEHOLDER = "Здесь пример кода."
DEFAULT_TABLE_PLACEHOLDER = "Здесь таблица."

_FRONT_MATTER = re.compile(r"\A---[ \t]*\n.*?\n(?:---|\.\.\.)[ \t]*(?:\n|\Z)", re.S)
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
_FENCE = re.compile(r"^\s*(```+|~~~+)")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)(?:\s+#+)?\s*$")
_RULE = re.compile(r"^\s*(?:([-*_])(?:\s*\1){2,}|=+)\s*$")
_LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$")
_TASK = re.compile(r"^\[[ xX]\]\s+")
_QUOTE = re.compile(r"^\s*(?:>\s?)+")

# Целые числа и десятичные дроби. Даты вида 11.11.2026 намеренно не трогаем.
_NUMBER = re.compile(r"(?<![\d.,])\d+(?:[.,]\d+)?(?!\d|[.,]\d)")


def clean_markdown(
    text: str,
    *,
    code_placeholder: str = DEFAULT_CODE_PLACEHOLDER,
    table_placeholder: str = DEFAULT_TABLE_PLACEHOLDER,
    convert_numbers: bool = True,
) -> str:
    """Превращает Markdown в обычный текст: абзацы разделены пустой строкой.

    code_placeholder / table_placeholder: чем заменить блок кода и таблицу.
    Пустая строка означает «просто пропустить».
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _FRONT_MATTER.sub("", text, count=1)
    text = _HTML_COMMENT.sub("", text)

    paragraphs: list[str] = []
    para_buf: list[str] = []
    list_buf: list[str] = []
    in_code = False
    fence = ""
    in_table = False

    def flush_para() -> None:
        if para_buf:
            paragraphs.append(_ensure_end(" ".join(para_buf)))
            para_buf.clear()

    def flush_list() -> None:
        if list_buf:
            paragraphs.append("\n".join(list_buf))
            list_buf.clear()

    def flush_all() -> None:
        flush_para()
        flush_list()

    for raw in text.split("\n"):
        line = raw.rstrip()
        stripped = line.strip()

        # --- блок кода ---
        if in_code:
            if stripped.startswith(fence):
                in_code = False
            continue
        fence_match = _FENCE.match(line)
        if fence_match:
            flush_all()
            in_code = True
            fence = fence_match.group(1)
            in_table = False
            if code_placeholder:
                paragraphs.append(code_placeholder)
            continue

        line = _QUOTE.sub("", line)
        stripped = line.strip()

        # --- пустая строка ---
        if not stripped:
            flush_all()
            in_table = False
            continue

        # --- таблица: одно замечание на всю таблицу ---
        if stripped.startswith("|"):
            if not in_table:
                flush_all()
                in_table = True
                if table_placeholder:
                    paragraphs.append(table_placeholder)
            continue
        in_table = False

        # --- горизонтальная линия ---
        if _RULE.match(line):
            flush_all()
            continue

        # --- заголовок ---
        heading = _HEADING.match(line)
        if heading:
            flush_all()
            content = _clean_inline(heading.group(1))
            if content:
                paragraphs.append(_ensure_end(content))
            continue

        # --- элемент списка ---
        item = _LIST_ITEM.match(line)
        if item:
            flush_para()
            content = _clean_inline(_TASK.sub("", item.group(1)))
            if content:
                list_buf.append(_ensure_end(content))
            continue

        # --- обычная строка абзаца ---
        flush_list()
        content = _clean_inline(stripped)
        if content:
            para_buf.append(content)

    flush_all()
    result = "\n\n".join(p for p in paragraphs if p.strip())
    if convert_numbers:
        result = numbers_to_words(result)
    return result


def _ensure_end(text: str) -> str:
    """Добавляет точку в конец, чтобы TTS сделал паузу."""
    text = text.strip()
    if text and text[-1] not in ".!?…:;":
        text += "."
    return text


def _clean_inline(s: str) -> str:
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)  # картинки
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)  # [текст](url) -> текст
    s = re.sub(r"\[([^\]]+)\]\[[^\]]*\]", r"\1", s)  # [текст][ref] -> текст
    s = re.sub(r"\[\^[^\]]+\]", "", s)  # сноски [^1]
    s = re.sub(r"<https?://[^>]+>", "", s)  # <http://...>
    s = re.sub(r"(?:https?://|www\.)\S+", "", s)  # голые URL
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.I)  # перенос строки -> пробел
    s = re.sub(r"</?[A-Za-z][^>]*>", "", s)  # остальные HTML-теги
    s = re.sub(r"`([^`]*)`", r"\1", s)  # `код` -> код
    s = re.sub(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1", r"\2", s)  # жирный
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\1", s)  # *курсив*
    s = re.sub(r"(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)", r"\1", s)  # _курсив_
    s = re.sub(r"~~(.+?)~~", r"\1", s)  # зачёркнутый
    s = html.unescape(s).replace("\xa0", " ")
    s = re.sub(r"\\([\\`*_{}\[\]()#+\-.!|>~])", r"\1", s)  # экранирование
    return re.sub(r"\s+", " ", s).strip()


def numbers_to_words(text: str) -> str:
    """Заменяет числа словами (нужен пакет num2words; без него текст не меняется).

    Падежи не согласуются: «в 2026 году» станет «в две тысячи двадцать шесть году».
    """
    try:
        from num2words import num2words
    except ImportError:
        return text

    def repl(match: re.Match[str]) -> str:
        raw = match.group(0)
        try:
            if re.search(r"[.,]", raw):
                return num2words(float(raw.replace(",", ".")), lang="ru")
            return num2words(int(raw), lang="ru")
        except Exception:
            return raw

    return _NUMBER.sub(repl, text)
