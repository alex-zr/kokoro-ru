"""Обёртка над kokoro-ru: текст -> аудио.

Тяжёлые библиотеки (torch, kokoro) импортируются внутри _load(), поэтому
модуль можно импортировать без них, например в тестах.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Callable

import numpy as np

from .chunking import split_in_half, split_paragraphs, split_sentences
from .config import MAX_PHONEMES, SAMPLE_RATE, VOICES, Settings

ProgressCallback = Callable[[int, int], None]


class RussianSynthesizer:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        if self.settings.voice not in VOICES:
            raise ValueError(
                f"Неизвестный голос {self.settings.voice!r}. Доступны: {', '.join(VOICES)}"
            )
        self._load()

    # ------------------------------------------------------------------ загрузка
    def _load(self) -> None:
        import torch
        from huggingface_hub import snapshot_download
        from kokoro import KModel

        s = self.settings
        checkpoint = VOICES[s.voice]
        other_checkpoints = sorted(set(VOICES.values()) - {checkpoint})

        # Скачиваем репозиторий целиком, кроме ONNX и чужих чекпоинтов:
        # там же лежит ru_g2p.py (русская фонетика и ударения через RUAccent).
        repo_dir = Path(
            snapshot_download(
                s.repo_id,
                revision=s.revision,
                ignore_patterns=[
                    "onnx/*",
                    "voices/*.bin",
                    "*.wav",
                    "*.mp3",
                    "*.png",
                    "*.jpg",
                    *other_checkpoints,
                ],
            )
        )

        # ВНИМАНИЕ: ru_g2p.py из репозитория модели выполняется как обычный код.
        sys.path.insert(0, str(repo_dir))
        ru_g2p = importlib.import_module("ru_g2p")
        self._g2p = ru_g2p.RuG2P()

        self._model = KModel(s.repo_id, model=str(repo_dir / checkpoint)).to(s.device).eval()

        pack = torch.load(
            repo_dir / "voices" / f"{s.voice}.pt", map_location="cpu", weights_only=False
        )
        self._pack = pack.to(s.device) if hasattr(pack, "to") else pack
        self._torch = torch

    # ------------------------------------------------------------------ синтез
    def synthesize(
        self, text: str, progress: ProgressCallback | None = None
    ) -> tuple[np.ndarray, set[str]]:
        """Возвращает (аудио float32 24 кГц, слова, которых нет в словаре G2P)."""
        s = self.settings
        sentence_pause = np.zeros(int(SAMPLE_RATE * s.pause_sentence), dtype=np.float32)
        paragraph_pause = np.zeros(int(SAMPLE_RATE * s.pause_paragraph), dtype=np.float32)

        paragraphs = [split_sentences(p) for p in split_paragraphs(text)]
        total = sum(len(sentences) for sentences in paragraphs)
        unknown: set[str] = set()
        parts: list[np.ndarray] = []
        done = 0

        for sentences in paragraphs:
            for sentence in sentences:
                parts.append(self._synthesize_text(sentence, unknown))
                parts.append(sentence_pause)
                done += 1
                if progress:
                    progress(done, total)
            parts.append(paragraph_pause)

        if not parts:
            return np.zeros(0, dtype=np.float32), unknown
        return np.concatenate(parts), unknown

    def _synthesize_text(self, text: str, unknown: set[str]) -> np.ndarray:
        ipa, oov = self._g2p(text)

        if len(ipa) > MAX_PHONEMES:
            halves = split_in_half(text)
            if halves is None:
                print(f"Пропускаю слишком длинное слово: {text[:40]!r}")
                return np.zeros(0, dtype=np.float32)
            return np.concatenate([self._synthesize_text(h, unknown) for h in halves])

        if not ipa.strip():
            return np.zeros(0, dtype=np.float32)
        if oov:
            unknown.update(oov)

        with self._torch.no_grad():
            output = self._model(
                ipa, self._pack[len(ipa) - 1], self.settings.speed, return_output=True
            )
        return output.audio.detach().cpu().numpy().astype(np.float32)


def save_wav(path: str | Path, audio: np.ndarray) -> None:
    import soundfile as sf

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), audio, SAMPLE_RATE)
