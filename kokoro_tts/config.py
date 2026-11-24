"""Константы и настройки проекта."""
from __future__ import annotations

from dataclasses import dataclass

# Неофициальный русский порт Kokoro-82M на Hugging Face.
REPO_ID = "zaakirio/kokoro-ru"

SAMPLE_RATE = 24000

# Голосовой пак имеет форму [510, 256] и индексируется длиной строки фонем,
# поэтому фразы длиннее ~500 фонем нужно делить.
MAX_PHONEMES = 500

# Имя папки, содержимое которой озвучивается в режиме --narration.
NARRATION_DIR_NAME = "narration"

# Служебные папки, в которые не заходим при поиске вложенных narration.
# Скрытые папки (начинающиеся с точки) пропускаются отдельно.
SKIP_DIRS: frozenset[str] = frozenset(
    {"model", "output", "node_modules", "venv", "env", "__pycache__", "site-packages"}
)

# голос -> файл чекпоинта (sveta и masha делят один чекпоинт)
VOICES: dict[str, str] = {
    "sveta": "kokoro-ru-v2-base.pth",
    "masha": "kokoro-ru-v2-base.pth",
    "dima": "kokoro-ru-v2-dima.pth",
}


@dataclass
class Settings:
    voice: str = "dima"
    speed: float = 1.0
    device: str = "cpu"  # "cpu" или "mps" (на Mac; mps не проверялся)
    pause_sentence: float = 0.25  # секунды тишины после предложения
    pause_paragraph: float = 0.6  # секунды тишины после абзаца
    repo_id: str = REPO_ID
    # Зафиксируйте коммит репозитория модели, чтобы код ru_g2p.py не менялся
    # между запусками. None = последняя версия.
    revision: str | None = None
