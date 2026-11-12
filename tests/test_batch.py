import argparse
import tempfile
import unittest
from pathlib import Path

from main import (
    DEFAULT_INPUT,
    audio_path_for,
    collect_markdown_files,
    input_path,
    resolve_sources,
)


class InputPathTest(unittest.TestCase):
    def test_no_arguments_uses_default(self):
        self.assertEqual(input_path([]), DEFAULT_INPUT)
        self.assertEqual(input_path(None), DEFAULT_INPUT)

    def test_unquoted_path_with_spaces_is_joined(self):
        parts = ["~/Dropbox/job/intellias/preparation/Interview", "Cheatsheet", "2.0_algo_lecture.md"]
        expected = Path("~/Dropbox/job/intellias/preparation/Interview Cheatsheet 2.0_algo_lecture.md").expanduser()
        self.assertEqual(input_path(parts), expected)

    def test_plain_path_is_kept(self):
        self.assertEqual(input_path(["input/example.md"]), Path("input/example.md"))


class CollectMarkdownFilesTest(unittest.TestCase):
    def test_collects_only_markdown_from_top_level(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("b.md", "a.md", "C.MD", "d.markdown", "note.txt"):
                (root / name).write_text("текст", encoding="utf-8")
            (root / "sub").mkdir()
            (root / "sub" / "nested.md").write_text("текст", encoding="utf-8")

            found = [path.name for path in collect_markdown_files(root)]

            self.assertEqual(found, ["C.MD", "a.md", "b.md", "d.markdown"])

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(collect_markdown_files(Path(tmp)), [])


class ResolveSourcesTest(unittest.TestCase):
    def test_single_file_needs_no_batch_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "notes.md"
            source.write_text("текст", encoding="utf-8")

            sources, error = resolve_sources(source)

            self.assertIsNone(error)
            self.assertEqual(sources, [source])

    def test_directory_is_detected_automatically(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "a.md"
            second = root / "b.md"
            for path in (first, second):
                path.write_text("текст", encoding="utf-8")

            sources, error = resolve_sources(root)

            self.assertIsNone(error)
            self.assertEqual(sources, [first, second])

    def test_empty_directory_reports_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            sources, error = resolve_sources(Path(tmp))

            self.assertEqual(sources, [])
            self.assertIn("нет Markdown-файлов", error)

    def test_missing_path_reports_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            sources, error = resolve_sources(Path(tmp) / "missing.md")

            self.assertEqual(sources, [])
            self.assertIn("не найден", error)

    def test_batch_flag_rejects_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "notes.md"
            source.write_text("текст", encoding="utf-8")

            sources, error = resolve_sources(source, batch=True)

            self.assertEqual(sources, [])
            self.assertIn("ожидает папку", error)


class AudioPathTest(unittest.TestCase):
    def test_batch_keeps_audio_next_to_source(self):
        args = argparse.Namespace(output=None)
        source = Path("/tmp/notes/example.md")
        self.assertEqual(audio_path_for(source, args), Path("/tmp/notes/example.wav"))

    def test_single_file_saves_next_to_source_by_default(self):
        args = argparse.Namespace(output=None)
        path = audio_path_for(Path("/tmp/notes/example.md"), args)
        self.assertEqual(path, Path("/tmp/notes/example.wav"))

    def test_single_markdown_gets_audio_extension(self):
        args = argparse.Namespace(output=None)
        path = audio_path_for(Path("/tmp/notes/example.markdown"), args)
        self.assertEqual(path, Path("/tmp/notes/example.wav"))

    def test_single_file_respects_output(self):
        args = argparse.Namespace(output="/tmp/custom.wav")
        self.assertEqual(audio_path_for(Path("example.md"), args), Path("/tmp/custom.wav"))


if __name__ == "__main__":
    unittest.main()
