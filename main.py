"""Озвучка Markdown-файла моделью kokoro-ru.

Примеры:
    python main.py                                  # input/example.md -> output/example.mp3
    python main.py input/notes.md --voice masha
    python main.py input/notes.md --clean-only      # только очистка, без модели
    python main.py input --batch                    # все .md из input/ -> mp3 рядом с ними
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import time
from pathlib import Path

from kokoro_tts.config import SAMPLE_RATE, VOICES, Settings
from kokoro_tts.markdown_cleaner import clean_markdown

ROOT = Path(__file__).resolve().parent

MARKDOWN_SUFFIXES = {".md", ".markdown"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Озвучка Markdown русским TTS (kokoro-ru)")
    parser.add_argument(
        "input",
        nargs="?",
        default=str(ROOT / "input" / "example.md"),
        help="путь к .md файлу или папке (вместе с --batch)",
    )
    parser.add_argument("-o", "--output", help="куда сохранить .wav (по умолчанию output/<имя>.wav)")
    parser.add_argument(
        "-b",
        "--batch",
        action="store_true",
        help="обработать все .md файлы из указанной папки, сохраняя результаты рядом с исходниками",
    )
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


def collect_markdown_files(directory: Path) -> list[Path]:
    """Все Markdown-файлы верхнего уровня указанной папки, отсортированные по имени."""
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in MARKDOWN_SUFFIXES
    )


def audio_path_for(source: Path, args: argparse.Namespace) -> Path:
    if args.batch:
        # В пакетном режиме результаты лежат рядом с исходным .md.
        return source.with_suffix(".wav")
    if args.output:
        return Path(args.output)
    return ROOT / "output" / f"{source.stem}.wav"


def process_file(
    source: Path,
    args: argparse.Namespace,
    synthesizer: object | None,
) -> int:
    """Озвучивает один файл. Возвращает 0 при успехе, 1 при ошибке."""
    wav_path = audio_path_for(source, args)
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
    if synthesizer is None:
        raise RuntimeError("Синтезатор не загружен")

    from kokoro_tts.synthesizer import save_wav

    started = time.perf_counter()
    audio, unknown = synthesizer.synthesize(
        cleaned,
        progress=lambda done, total: print(
            f"\r{source.name}: [{done}/{total}] предложений" if args.batch
            else f"\r[{done}/{total}] предложений",
            end="",
        ),
    )
    print()

    if audio.size == 0:
        print("Аудио получилось пустым.")
        return 1

    save_wav(wav_path, audio)
    elapsed = time.perf_counter() - started
    duration = f"{audio.size / SAMPLE_RATE:.0f} с аудио за {elapsed:.0f} с"

    if unknown:
        print("Слова, которых нет в словаре (могут читаться неверно):")
        print("  " + ", ".join(sorted(unknown)))

    save_mp3_or_keep_wav(wav_path, args, duration)
    return 0


def save_mp3_or_keep_wav(wav_path: Path, args: argparse.Namespace, duration: str) -> None:
    if args.mp3:
        if shutil.which("ffmpeg") is None:
            print("ffmpeg не найден: brew install ffmpeg — оставляю только wav")
        else:
            mp3_path = wav_path.with_suffix(".mp3")
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav_path), str(mp3_path)],
                check=True,
            )
            # mp3 уже готов, промежуточный wav больше не нужен.
            wav_path.unlink(missing_ok=True)
            print(f"Готово: {mp3_path} ({duration}, wav удалён)")
            return
    print(f"Готово: {wav_path} ({duration})")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source = Path(args.input)

    if args.batch:
        if args.output:
            print("-o/--output нельзя использовать вместе с --batch: результаты сохраняются рядом с исходниками.")
            return 1
        if not source.is_dir():
            print(f"Не найдена папка: {source}")
            return 1
        sources = collect_markdown_files(source)
        if not sources:
            print(f"В папке нет Markdown-файлов: {source}")
            return 1
    else:
        if not source.is_file():
            print(f"Файл не найден: {source}")
            return 1
        sources = [source]

    synthesizer = None
    if not args.clean_only:
        # Импорт здесь, чтобы --clean-only работал без torch и kokoro.
        from kokoro_tts.synthesizer import RussianSynthesizer

        settings = Settings(
            voice=args.voice, speed=args.speed, device=args.device, revision=args.revision
        )
        print("Загружаю модель (при первом запуске скачивается с Hugging Face)...")
        synthesizer = RussianSynthesizer(settings)

    failed = 0
    for index, path in enumerate(sources, 1):
        if args.batch:
            print(f"\n[{index}/{len(sources)}] {path}")
        try:
            code = process_file(path, args, synthesizer)
        except Exception as exc:  # один битый файл не должен ронять всю пачку
            print(f"Ошибка при обработке {path}: {exc}")
            code = 1
        failed += code != 0

    if args.batch:
        print(f"\nОбработано файлов: {len(sources) - failed} из {len(sources)}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
