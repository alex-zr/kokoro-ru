import unittest

from kokoro_tts.chunking import split_in_half, split_paragraphs, split_sentences


class SplitParagraphsTest(unittest.TestCase):
    def test_splits_on_blank_lines(self):
        self.assertEqual(split_paragraphs("А.\n\n\nБ.\n \nВ."), ["А.", "Б.", "В."])

    def test_empty_text(self):
        self.assertEqual(split_paragraphs("  \n\n "), [])


class SplitSentencesTest(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(
            split_sentences("Привет. Как дела? Отлично!"), ["Привет.", "Как дела?", "Отлично!"]
        )

    def test_newlines_inside_paragraph_are_flattened(self):
        self.assertEqual(split_sentences("Раз.\nДва."), ["Раз.", "Два."])

    def test_decimal_number_not_split(self):
        self.assertEqual(split_sentences("Версия 3.5 вышла."), ["Версия 3.5 вышла."])


class SplitInHalfTest(unittest.TestCase):
    def test_single_word_cannot_be_split(self):
        self.assertIsNone(split_in_half("Слово"))

    def test_halves_rejoin_to_original(self):
        text = "один два три четыре пять шесть семь восемь"
        left, right = split_in_half(text)
        self.assertTrue(left and right)
        self.assertEqual(f"{left} {right}", text)

    def test_prefers_split_after_comma(self):
        text = "очень длинное начало фразы, потом короткий хвост"
        left, _ = split_in_half(text)
        self.assertTrue(left.endswith(","))


if __name__ == "__main__":
    unittest.main()
