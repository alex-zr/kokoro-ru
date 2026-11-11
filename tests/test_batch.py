import argparse
import tempfile
import unittest
from pathlib import Path

from main import audio_path_for, collect_markdown_files


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


class AudioPathTest(unittest.TestCase):
    def test_batch_keeps_audio_next_to_source(self):
        args = argparse.Namespace(batch=True, output=None)
        source = Path("/tmp/notes/example.md")
        self.assertEqual(audio_path_for(source, args), Path("/tmp/notes/example.wav"))

    def test_single_file_saves_next_to_source_by_default(self):
        args = argparse.Namespace(batch=False, output=None)
        path = audio_path_for(Path("/tmp/notes/example.md"), args)
        self.assertEqual(path, Path("/tmp/notes/example.wav"))

    def test_single_markdown_gets_audio_extension(self):
        args = argparse.Namespace(batch=False, output=None)
        path = audio_path_for(Path("/tmp/notes/example.markdown"), args)
        self.assertEqual(path, Path("/tmp/notes/example.wav"))

    def test_single_file_respects_output(self):
        args = argparse.Namespace(batch=False, output="/tmp/custom.wav")
        self.assertEqual(audio_path_for(Path("example.md"), args), Path("/tmp/custom.wav"))


if __name__ == "__main__":
    unittest.main()
