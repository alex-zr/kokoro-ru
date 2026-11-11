import importlib.util
import unittest

from kokoro_tts.markdown_cleaner import clean_markdown


def clean(text: str, **kwargs) -> str:
    kwargs.setdefault("convert_numbers", False)
    return clean_markdown(text, **kwargs)


class HeadingsAndParagraphsTest(unittest.TestCase):
    def test_heading_gets_period(self):
        self.assertEqual(clean("# Заголовок"), "Заголовок.")

    def test_heading_keeps_existing_punctuation(self):
        self.assertEqual(clean("## Что это?"), "Что это?")

    def test_hard_wrapped_paragraph_is_joined(self):
        self.assertEqual(clean("Первая строка\nвторая строка."), "Первая строка вторая строка.")

    def test_paragraphs_separated_by_blank_line(self):
        self.assertEqual(clean("Один.\n\nДва."), "Один.\n\nДва.")

    def test_front_matter_removed(self):
        self.assertEqual(clean("---\ntitle: X\n---\n\nТекст."), "Текст.")

    def test_horizontal_rule_removed(self):
        self.assertEqual(clean("До.\n\n---\n\nПосле."), "До.\n\nПосле.")


class InlineTest(unittest.TestCase):
    def test_bold_and_italic(self):
        self.assertEqual(clean("Это **важно** и *заметно* и _тоже_."), "Это важно и заметно и тоже.")

    def test_snake_case_is_preserved(self):
        self.assertEqual(clean("Переменная my_var_name."), "Переменная my_var_name.")

    def test_link_keeps_text(self):
        self.assertEqual(clean("Смотри [сюда](https://example.com/a) сейчас."), "Смотри сюда сейчас.")

    def test_image_removed(self):
        self.assertEqual(clean("Текст ![схема](img/a.png) дальше."), "Текст дальше.")

    def test_bare_url_removed(self):
        self.assertEqual(clean("Сайт https://example.com тут."), "Сайт тут.")

    def test_inline_code_keeps_content(self):
        self.assertEqual(clean("Команда `ls` работает."), "Команда ls работает.")

    def test_html_tags_removed(self):
        self.assertEqual(clean("Слово<br>другое <b>жирное</b>."), "Слово другое жирное.")

    def test_footnote_reference_removed(self):
        self.assertEqual(clean("Факт[^1] важен."), "Факт важен.")

    def test_escaped_characters(self):
        self.assertEqual(clean(r"Цена 5 \* 3."), "Цена 5 * 3.")


class BlocksTest(unittest.TestCase):
    def test_list_items_each_end_with_period(self):
        result = clean("- Раз\n- Два\n* Три")
        self.assertEqual(result, "Раз.\nДва.\nТри.")

    def test_numbered_list(self):
        self.assertEqual(clean("1. Первый\n2) Второй"), "Первый.\nВторой.")

    def test_task_list_markers_removed(self):
        self.assertEqual(clean("- [x] Готово\n- [ ] Не готово"), "Готово.\nНе готово.")

    def test_blockquote_marker_removed(self):
        self.assertEqual(clean("> Цитата."), "Цитата.")

    def test_code_block_replaced_with_placeholder(self):
        result = clean("До.\n\n```python\nprint('x')\n```\n\nПосле.")
        self.assertEqual(result, "До.\n\nЗдесь пример кода.\n\nПосле.")

    def test_code_block_can_be_dropped(self):
        result = clean("До.\n\n```\ncode\n```\n\nПосле.", code_placeholder="")
        self.assertEqual(result, "До.\n\nПосле.")

    def test_tilde_fence_with_inner_backticks(self):
        result = clean("~~~\n```\nвнутри\n```\n~~~\n\nПосле.")
        self.assertEqual(result, "Здесь пример кода.\n\nПосле.")

    def test_table_replaced_once(self):
        table = "| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |"
        self.assertEqual(clean(f"До.\n\n{table}\n\nПосле."), "До.\n\nЗдесь таблица.\n\nПосле.")


class NumbersTest(unittest.TestCase):
    def test_numbers_untouched_when_disabled(self):
        self.assertEqual(clean("Версия 3.", convert_numbers=False), "Версия 3.")

    @unittest.skipUnless(importlib.util.find_spec("num2words"), "num2words не установлен")
    def test_integer_converted(self):
        self.assertEqual(clean_markdown("Их 5."), "Их пять.")

    @unittest.skipUnless(importlib.util.find_spec("num2words"), "num2words не установлен")
    def test_date_left_alone(self):
        self.assertIn("11.11.2026", clean_markdown("Дата 11.11.2026 сегодня."))


if __name__ == "__main__":
    unittest.main()
