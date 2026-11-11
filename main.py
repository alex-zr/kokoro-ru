"""Озвучка Markdown-файла моделью kokoro-ru.

Примеры:
    python main.py                                  # input/example.md -> output/example.wav
    python main.py input/notes.md --voice dima
    python main.py input/notes.md --clean-only      # только очистка, без модели
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import time
from pathlib import Path

from kokoro_tts.config import VOICES, Settings
from kokoro_tts.markdown_cleaner import clean_markdown

ROOT = Path(__file__).resolve().parent


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Озвучка Markdown русским TTS (kokoro-ru)")
    parser.add_argument(
        "input", nargs="?", default=str(ROOT / "input" / "example.md"), help="путь к .md файлу"
    )
    parser.add_argument("-o", "--output", help="куда сохранить .wav (по умолчанию output/<имя>.wav)")
    parser.add_argument("--voice", choices=list(VOICES), default="dima")
    parser.add_argument("--speed", type=float, default=1.0, help="скорость речи, 1.0 = обычная")
    parser.add_argument("--device", default="cpu", choices=["cpu", "mps"])
    parser.add_argument(
        "--no-mp3", dest="mp3", action="store_false", help="не сохранять mp3 (по умолчанию сохраняется)"
    )
    parser.add_argument(
        "--mp3", dest="mp3", action="store_true", help=argparse.SUPPRESS
    )  # оставлено для совместимости: mp3 теперь по умолчанию
    parser.add_argument("--clean-only", action="store_true", help="только очистить текст и сохранить .txt")
    parser.add_argument("--no-numbers", action="store_true", help="не заменять числа словами")
    parser.add_argument("--revision", help="коммит репозитория модели (для воспроизводимости)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    source = Path(args.input)
    if not source.is_file():
        print(f"Файл не найден: {source}")
        return 1

    wav_path = Path(args.output) if args.output else ROOT / "output" / f"{source.stem}.wav"
    txt_path = wav_path.with_suffix(".txt")

    cleaned = clean_markdown(
        source.read_text(encoding="utf-8"), convert_numbers=not args.no_numbers
    )
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    txt_path.write_text(cleaned, encoding="utf-8")
    print(f"Очищенный текст: {txt_path} ({len(cleaned)} символов)")

    if args.clean_only:
        return 0
    if not cleaned.strip():
        print("После очистки текст пуст, озвучивать нечего.")
        return 1

    # Импорт здесь, чтобы --clean-only работал без torch и kokoro.
    from kokoro_tts.config import SAMPLE_RATE
    from kokoro_tts.synthesizer import RussianSynthesizer, save_wav

    settings = Settings(
        voice=args.voice, speed=args.speed, device=args.device, revision=args.revision
    )
    print("Загружаю модель (при первом запуске скачивается с Hugging Face)...")
    synthesizer = RussianSynthesizer(settings)

    started = time.perf_counter()
    audio, unknown = synthesizer.synthesize(
        cleaned, progress=lambda done, total: print(f"\r[{done}/{total}] предложений", end="")
    )
    print()

    if audio.size == 0:
        print("Аудио получилось пустым.")
        return 1

    save_wav(wav_path, audio)
    elapsed = time.perf_counter() - started
    print(f"Готово: {wav_path} ({audio.size / SAMPLE_RATE:.0f} с аудио за {elapsed:.0f} с)")

    if unknown:
        print("Слова, которых нет в словаре (могут читаться неверно):")
        print("  " + ", ".join(sorted(unknown)))

    if args.mp3:
        if shutil.which("ffmpeg") is None:
            print("ffmpeg не найден: brew install ffmpeg")
        else:
            mp3_path = wav_path.with_suffix(".mp3")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav_path), str(mp3_path)], check=True)
            print(f"mp3: {mp3_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
