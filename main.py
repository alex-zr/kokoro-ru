"""Озвучка Markdown-файла моделью kokoro-ru.

Аргумент один: путь к файлу или к папке. Если это файл, озвучивается он,
если папка — все .md верхнего уровня. С флагом --narration папка обходится
рекурсивно: обрабатываются .md из всех вложенных папок narration.
Результат всегда сохраняется в папке исходника, с тем же именем и расширением
.mp3 (или .wav с --no-mp3).

Примеры:
    python main.py                                  # input/example.md -> input/example.mp3
    python main.py input/notes.md --voice masha
    python main.py input/notes.md --clean-only      # только очистка, без модели
    python main.py input                            # все .md из input/ -> mp3 рядом с ними
    python main.py ~/Books --narration              # все .md из вложенных narration/
    python main.py ~/Books --narration voiceover    # то же, но папки называются voiceover
    python main.py ~/Documents/my notes.md          # пробелы в пути можно не экранировать
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import time
from pathlib import Path

from kokoro_tts.config import NARRATION_DIR_NAME, SAMPLE_RATE, SKIP_DIRS, VOICES, Settings
from kokoro_tts.markdown_cleaner import clean_markdown

ROOT = Path(__file__).resolve().parent

MARKDOWN_SUFFIXES = {".md", ".markdown"}
PROGRESS_WIDTH = 20

DEFAULT_INPUT = ROOT / "input" / "example.md"


def progress_bar(done: int, total: int, width: int = PROGRESS_WIDTH) -> str:
    """Текстовый прогресс-бар без внешних зависимостей."""
    fraction = min(done / total, 1.0) if total > 0 else 0.0
    filled = round(width * fraction)
    return f"{'█' * filled}{'░' * (width - filled)} {done}/{total}"


def input_path(parts: list[str] | None) -> Path:
    """Путь из позиционных аргументов: можно не брать в кавычки, если есть пробелы."""
    if not parts:
        return DEFAULT_INPUT
    return Path(" ".join(parts)).expanduser()


def narration_looks_like_path(value: str) -> bool:
    """True, если --narration, вероятно, случайно получил путь вместо имени папки.

    argparse с nargs="?" съедает следующий аргумент, поэтому
    `main.py --narration ~/Books` воспримет путь как имя папки.
    """
    separators = {os.sep, os.altsep} - {None}
    return any(separator in value for separator in separators) or Path(value).expanduser().exists()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Озвучка Markdown русским TTS (kokoro-ru)")
    parser.add_argument(
        "input",
        nargs="*",
        help="путь к .md файлу или к папке с .md файлами (пробелы можно не экранировать)",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="куда сохранить .wav (по умолчанию рядом с исходником, с тем же именем)",
    )
    parser.add_argument(
        "-b",
        "--batch",
        action="store_true",
        help="устаревший флаг: папка определяется автоматически по аргументу",
    )
    parser.add_argument(
        "--narration",
        nargs="?",
        const=NARRATION_DIR_NAME,
        default=None,
        metavar="NAME",
        help=(
            "рекурсивно найти папки NAME (по умолчанию narration) и озвучить "
            "все .md из них; путь к папке указывайте перед флагом"
        ),
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


def find_narration_dirs(root: Path, name: str = NARRATION_DIR_NAME) -> list[Path]:
    """Все вложенные папки с именем name (без учёта регистра), отсортированные по пути.

    Обход рекурсивный. В скрытые и служебные папки (model, .venv и т. п.)
    не заходим, символические ссылки не разворачиваем.
    """
    target = name.casefold()
    found: list[Path] = []

    for current, dirs, _ in os.walk(root, followlinks=False):
        current_path = Path(current)
        dirs[:] = sorted(
            directory
            for directory in dirs
            if not directory.startswith(".") and directory.casefold() not in SKIP_DIRS
        )
        if current_path.name.casefold() == target:
            found.append(current_path)

    return sorted(found)


def collect_narration_files(root: Path, name: str = NARRATION_DIR_NAME) -> list[Path]:
    """Markdown-файлы верхнего уровня из всех вложенных папок name."""
    return sorted(
        path
        for directory in find_narration_dirs(root, name)
        for path in collect_markdown_files(directory)
    )


def resolve_sources(
    source: Path, batch: bool = False, narration: str | None = None
) -> tuple[list[Path], str | None]:
    """Файлы для обработки и текст ошибки (None, если всё в порядке).

    Файл -> он сам. Папка -> все Markdown-файлы верхнего уровня. С narration
    (имя папки) -> Markdown-файлы из всех вложенных папок с этим именем.
    Флаг --batch оставлен для совместимости и требует именно папку.
    """
    if narration is not None and not source.is_dir():
        if source.is_file():
            return [], f"--narration ожидает папку, а не файл: {source}"
        return [], f"Не найдена папка: {source}"

    if source.is_dir():
        if narration is not None:
            narration_dirs = find_narration_dirs(source, narration)
            if not narration_dirs:
                return [], f"Папки {narration} не найдены: {source}"
            sources = collect_narration_files(source, narration)
            if not sources:
                return [], f"В папках {narration} нет Markdown-файлов: {source}"
            return sources, None

        sources = collect_markdown_files(source)
        if not sources:
            return [], f"В папке нет Markdown-файлов: {source}"
        return sources, None
    if source.is_file():
        if batch:
            return [], f"--batch ожидает папку, а не файл: {source}"
        return [source], None
    if batch:
        return [], f"Не найдена папка: {source}"
    return [], f"Файл не найден: {source}"


def audio_path_for(source: Path, args: argparse.Namespace) -> Path:
    """Куда писать wav: -o или рядом с исходником (имя как у входа)."""
    if args.output:
        return Path(args.output)
    return source.with_suffix(".wav")


def process_file(
    source: Path,
    args: argparse.Namespace,
    synthesizer: object | None,
    file_total: int = 1,
    completed_files: int = 0,
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
            f"\rФайлы [{progress_bar(completed_files, file_total)}] · "
            f"{source.name} [{progress_bar(done, total)}] предложений"
            if args.batch
            else f"\r{source.name} [{progress_bar(done, total)}] предложений",
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
    # Текст нужен был только для проверки/отладки; после успешной озвучки убираем его.
    txt_path.unlink(missing_ok=True)
    print(f"Промежуточный текст удалён: {txt_path}")
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
    source = input_path(args.input)

    if args.narration is not None and narration_looks_like_path(args.narration):
        print(
            "Похоже, --narration получил путь, а не имя папки. "
            "Укажите папку перед флагом: python main.py <папка> --narration [имя]"
        )
        return 1

    sources, error = resolve_sources(source, args.batch, narration=args.narration)
    if error:
        print(error)
        return 1

    # Папка -> пакетный режим: -o запрещён, прогресс печатается с именем файла.
    args.batch = source.is_dir()
    if args.batch and args.output:
        print("-o/--output нельзя использовать для папки: результаты сохраняются рядом с исходниками.")
        return 1

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
    completed = 0
    for index, path in enumerate(sources, 1):
        if args.batch:
            print(
                f"\nФайлы [{progress_bar(completed, len(sources))}] · "
                f"[{index}/{len(sources)}] {path}"
            )
        try:
            code = process_file(
                path,
                args,
                synthesizer,
                file_total=len(sources),
                completed_files=completed,
            )
        except Exception as exc:  # один битый файл не должен ронять всю пачку
            print(f"\nОшибка при обработке {path}: {exc}")
            code = 1
        failed += code != 0
        completed += 1
        if args.batch:
            print(f"\rФайлы [{progress_bar(completed, len(sources))}]", end="\n")

    if args.batch:
        print(f"\nОбработано файлов: {len(sources) - failed} из {len(sources)}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
