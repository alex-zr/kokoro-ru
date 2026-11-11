# kokoro-ru-tts

Небольшой проект для озвучки Markdown-файлов русской моделью [kokoro-ru](https://huggingface.co/zaakirio/kokoro-ru) (неофициальный русский порт Kokoro-82M, голоса `sveta`, `masha`, `dima`).

Что делает: берёт `.md`, убирает разметку (ссылки, код, таблицы, заголовки), режет на предложения, озвучивает и сохраняет `.mp3` (по умолчанию голосом `dima`; с `--no-mp3` — `.wav`).

## Структура

```
kokoro-ru-tts/
├── main.py                  # точка входа (её запускаем из PyCharm)
├── requirements.txt
├── kokoro_tts/
│   ├── config.py            # голоса, константы, настройки
│   ├── markdown_cleaner.py  # md -> чистый текст (без тяжёлых зависимостей)
│   ├── chunking.py          # абзацы, предложения, деление длинных фраз
│   └── synthesizer.py       # загрузка модели и синтез
├── input/example.md         # пример входного файла
├── output/                  # сюда сохраняются .wav и очищенный .txt
└── tests/                   # unittest для очистки и разбиения текста
```

## Установка (macOS)

```bash
brew install espeak-ng ffmpeg
```
`ffmpeg` нужен для mp3, который сохраняется по умолчанию (отключить можно `--no-mp3`). `espeak-ng` часто требуется фонетике; если `ru_g2p` попросит другие зависимости, их список смотрите в README репозитория модели.

Python лучше взять 3.10–3.12: пакет `kokoro` может не поддерживать более новые версии.

### В PyCharm

1. **File → Open** и выберите папку `kokoro-ru-tts`.
2. **Settings → Project → Python Interpreter → Add Interpreter → Add Local Interpreter → Virtualenv**, база Python 3.11 или 3.12, расположение `.venv`.
3. Откройте терминал PyCharm и выполните `pip install -r requirements.txt`.
4. **Run → Edit Configurations → + → Python**:
   - Script: `main.py`
   - Parameters: `input/example.md` (по умолчанию голос `dima` и mp3)
   - Working directory: корень проекта
5. Запустите. При первом запуске модель скачается с Hugging Face (несколько сотен МБ, ONNX-файлы пропускаются).

### Из терминала

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py input/example.md
```
Пересоздать окружение с другой версией пайтон
```bash
rm -rf .venv
/opt/homebrew/bin/python3.12 -m venv .venv
source .venv/bin/activate
python --version        # должно показать 3.12.x
pip install -r requirements.txt
```




## Использование

```bash
python main.py                                   # input/example.md -> output/example.mp3 (голос dima)
python main.py input/notes.md --voice masha      # другой голос
python main.py input/notes.md --speed 0.95       # медленнее
python main.py input/notes.md --no-mp3           # только wav, mp3 не создаётся
python main.py input/notes.md --clean-only       # только очистка, модель не нужна
```

Рядом с аудио сохраняется очищенный текст (`output/<имя>.txt`): откройте его и убедитесь, что читаться будет именно то, что нужно.

Модель скачивается только один раз в `model/`. При следующих запусках, если все нужные файлы уже на месте, проект вообще не обращается к Hugging Face — можно работать офлайн. Чтобы обновить модель, удалите `model/` или укажите новый `--revision`.

| Параметр | Значение |
|---|---|
| `--voice` | `sveta`, `masha`, `dima` (по умолчанию) |
| `--speed` | скорость, 1.0 = обычная |
| `--device` | `cpu` (по умолчанию) или `mps` (на Mac, не проверялся) |
| `--no-mp3` | не создавать mp3 и оставить wav (по умолчанию mp3 сохраняется, а промежуточный wav удаляется) |
| `--clean-only` | только очистка текста |
| `--no-numbers` | не заменять числа словами |
| `--revision` | коммит репозитория модели |

## Тесты

Тесты не требуют модели:

```bash
python3 -m unittest discover -v
```
В PyCharm: ПКМ по папке `tests` → **Run 'Python tests in tests'**.

## Как это работает

1. `markdown_cleaner.clean_markdown` превращает md в абзацы. Блоки кода заменяются фразой «Здесь пример кода.», таблицы фразой «Здесь таблица.» (меняются в `markdown_cleaner.py`). Числа переводятся в слова через `num2words`, если он установлен.
2. `chunking` делит абзацы на предложения. Если фраза не помещается в лимит модели (~500 фонем), она делится пополам по границе слов.
3. `RussianSynthesizer` скачивает репозиторий модели, берёт оттуда `ru_g2p.py` (ударения через RUAccent) и чекпоинт, синтезирует каждое предложение и склеивает с паузами.

## Ограничения

- Проект собран по описанию на странице модели, **на реальной модели не запускался**. Если что-то упадёт при загрузке, присылайте traceback.
- `ru_g2p.py` берётся из репозитория модели и выполняется как обычный код. Чтобы код не менялся между запусками, зафиксируйте `--revision <коммит>`.
- Падежи у чисел не согласуются («в 2026 году» прочитается неправильно), даты вида `11.11.2026` не обрабатываются. Латиница и аббревиатуры могут читаться плохо; такие слова выводятся списком в конце.
- Сокращения вроде «т. е.» могут разрезать предложение.
- Голос `sveta` по описанию автора звучит темнее остальных (меньше всего обучающих данных).
