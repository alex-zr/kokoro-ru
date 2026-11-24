# 0001. Озвучка Markdown из вложенных папок narration

- **Статус:** Implemented
- **Дата:** 2026-11-24
- **Связанные спеки:** —
- **Затрагиваемые файлы:** `main.py`, `kokoro_tts/config.py`,
  `tests/test_batch.py`, `README.md`, `AGENTS.md`

## Контекст и проблема

Сейчас папка обрабатывается нерекурсивно: `collect_markdown_files()` берёт
только `.md` верхнего уровня. Для озвучки материала, разложенного по главам
(`Book/ch01/narration/…`, `Book/ch02/narration/…`), приходится запускать
утилиту для каждой папки `narration` отдельно. Модель при этом загружается
многократно, а список папок нужно собирать вручную.

## Цели и не-цели

**Цели:**

- Одной командой озвучить все `.md`/`.markdown` из всех папок `narration`
  внутри указанного дерева.
- Сохранить текущее поведение для обычной папки и одного файла.
- Загрузить модель один раз на весь прогон и не прерывать обработку из-за
  одного битого файла.

**Не-цели:**

- Рекурсивный сбор `.md` внутри самой `narration` (берётся только верхний
  уровень, как и в обычном пакетном режиме).
- Зеркалирование структуры в отдельную выходную папку (`-o` для папки
  по-прежнему запрещён).
- Автоматическое включение режима без флага.
- Изменение формата имени выходного файла: `.mp3` рядом с исходником
  (или `.wav` с `--no-mp3`).

## Пользовательский сценарий

```bash
# структура:
# ~/Books/ch01/narration/intro.md
# ~/Books/ch01/narration/body.md
# ~/Books/ch02/narration/part.md

python main.py ~/Books --narration
# -> ~/Books/ch01/narration/intro.mp3, body.mp3
# -> ~/Books/ch02/narration/part.mp3

python main.py ~/Books --narration voiceover   # папки называются voiceover
python main.py ~/Books --narration --voice masha --no-mp3
python main.py ~/Books --narration --clean-only  # без модели
```

Путь к папке указывается **перед** `--narration`: argparse с `nargs="?"`
съедает следующий аргумент как имя папки. Если после флага оказался путь,
выводится подсказка и код возврата 1.

## Требования

- **FR-1.** Новый аргумент `--narration [NAME]`: без значения ищет папки
  `narration`, со значением — папки с указанным именем. По умолчанию режим
  выключен.
- **FR-2.** В режиме `--narration` указанная папка обходится рекурсивно;
  сравнение имени папки регистронезависимое (`NARRATION` тоже подходит).
- **FR-3.** Из каждой найденной папки берутся `.md` и `.markdown` только
  верхнего уровня, отсортированные по полному пути.
- **FR-4.** При обходе не заходим в скрытые папки (начинаются с точки) и в
  служебные: `model`, `output`, `node_modules`, `venv`, `env`,
  `__pycache__`, `site-packages`. Символические ссылки не разворачиваются.
- **FR-5.** Если корень поиска сам называется `narration`, его файлы тоже
  обрабатываются.
- **FR-6.** `--narration` с файлом вместо папки — ошибка с кодом 1.
- **FR-7.** Если папки `NAME` не найдены или в них нет Markdown-файлов,
  печатается сообщение на русском с путём поиска, код возврата 1, синтез не
  запускается.
- **FR-8.** Модель загружается один раз на весь список; прогресс печатается
  с именем файла; в конце — «Обработано файлов: N из M».
- **FR-9.** `-o/--output` в режиме папки остаётся запрещён.
- **FR-10.** `audio_path_for()` не меняется: аудио сохраняется рядом с
  исходником, временный `.txt` удаляется после успешной озвучки
  (в `--clean-only` остаётся).

## Критерии приёмки

- **AC-1.** Дано дерево с двумя вложенными `narration` и посторонними `.md`,
  когда запускается `main.py <корень> --narration --clean-only`, тогда
  обрабатываются только файлы из `narration`, включая случай разного
  регистра.
- **AC-2.** Дано имя `voiceover`, когда передан `--narration voiceover`,
  тогда находятся только папки `voiceover`.
- **AC-3.** Дано `.git/narration`, `.venv/narration`, `model/narration` и
  `book/narration`, когда ищем `narration`, тогда найден только
  `book/narration`.
- **AC-4.** Дано `narration/a.md`, `narration/b.markdown`,
  `narration/notes.txt`, `narration/chapter/nested.md`, когда собираются
  файлы, тогда результат — `a.md` и `b.markdown`.
- **AC-5.** Дано отсутствие папок `narration`, когда запускается режим,
  тогда печатается «Папки narration не найдены» и код 1.
- **AC-6.** Дано папки `narration` без Markdown, когда запускается режим,
  тогда печатается «нет Markdown-файлов» и код 1.
- **AC-7.** Дано файл вместо папки, когда передан `--narration`, тогда
  печатается «ожидает папку» и код 1.
- **AC-8.** Дано путь, случайно переданный после `--narration`, когда
  запускается CLI, тогда выводится подсказка про порядок аргументов и код 1.

## Крайние случаи и ошибки

| Ситуация | Ожидаемое поведение |
|---|---|
| Папка `narration` пуста | Ошибка «нет Markdown-файлов», код 1 |
| В дереве несколько `narration` | Обрабатываются все, сортировка по пути |
| Одинаковые имена файлов в разных главах | Конфликта нет: аудио рядом с каждым исходником |
| Вложенная `narration/narration` | Берутся файлы обеих папок, обход не зацикливается |
| Симлинк на папку | Не разворачивается (`followlinks=False`) |
| Имя папки с кириллицей | Сравнивается через `casefold()`, работает |
| Ошибка в одном файле | Печатается, остальные обрабатываются, итог с числом сбоев |
| `--clean-only` | Модель не импортируется и не скачивается |

## Решения и альтернативы

- **Решение:** отдельный флаг `--narration [NAME]`.
  **Почему:** текущее поведение папки — задокументированный контракт, ломать
  его нельзя; один параметр покрывает и стандартное имя, и произвольное.
  **Альтернатива:** автоматически включать режим при наличии `narration`.
  **Почему отвергнута:** неявный обход дерева и риск неожиданной обработки.
- **Решение:** только верхний уровень внутри `narration`.
  **Почему:** совпадает с семантикой обычного пакетного режима.
  **Альтернатива:** рекурсивный сбор внутри `narration`.
  **Почему отложена:** можно добавить отдельным флагом, если появится запрос.
- **Решение:** `-o` для папки запрещён.
  **Почему:** правило уже действует для пакетного режима; зеркалирование
  структуры — отдельная задача со своей спекой.

## Влияние

- Код: `kokoro_tts/config.py` — `NARRATION_DIR_NAME`, `SKIP_DIRS`;
  `main.py` — `find_narration_dirs`, `collect_narration_files`,
  `resolve_sources(..., narration=...)`, `narration_looks_like_path`,
  аргумент `--narration`.
- Тесты: `tests/test_batch.py` — классы `NarrationFilesTest`,
  `NarrationArgTest`, новые тесты в `ResolveSourcesTest`.
- README: раздел про пакетную обработку и таблица параметров.
- `AGENTS.md`: описание режима `--narration` и правила для новых режимов.
- Обратная совместимость: полная; без флага поведение не меняется.

## Проверка

| Критерий | Как проверено |
|---|---|
| AC-1 | `NarrationFilesTest.test_finds_nested_narration_dirs_case_insensitive`, `ResolveSourcesTest.test_narration_collects_files_from_nested_dirs`; ручной прогон `--clean-only` на временном дереве |
| AC-2 | `NarrationFilesTest.test_custom_narration_name` |
| AC-3 | `NarrationFilesTest.test_skips_hidden_and_service_dirs` |
| AC-4 | `NarrationFilesTest.test_collects_only_top_level_markdown_from_narration` |
| AC-5 | `ResolveSourcesTest.test_narration_without_dirs_reports_error` |
| AC-6 | `ResolveSourcesTest.test_narration_without_markdown_reports_error` |
| AC-7 | `ResolveSourcesTest.test_narration_rejects_file` |
| AC-8 | `NarrationArgTest.test_path_after_flag_is_detected` |
| FR-1 | `NarrationArgTest.test_flag_without_value_uses_default_name`, `test_flag_accepts_custom_name`, `test_flag_is_off_by_default` |
| FR-5 | `NarrationFilesTest.test_root_named_narration_is_included` |

Дата прогона: 2026-11-24. `python -m unittest discover -v` — 61 тест, OK.

## Открытые вопросы

Нет.
