# Документация проекта

- [Учебник: SDD для начинающих](spec-driven-development-guide.md) — подробное
  пошаговое руководство: зачем нужен подход, как написать первый спек,
  критерии приёмки, разбор ошибок и практика.
- [Стандарт spec-driven development](spec-driven-development.md) — как
  фиксировать требования до кода, жизненный цикл спеков, критерии приёмки,
  Definition of Done.
- [Спецификации](specs/) — архив требований и решений.
  - [Шаблон спека](specs/TEMPLATE.md)
  - [0001. Озвучка Markdown из вложенных папок narration](specs/0001-narration-folders.md)
  - [0002. Базовая озвучка Markdown и CLI](specs/0002-baseline-tts-cli.md)
  - [0003. Локальная папка модели `model/`](specs/0003-local-model-dir.md)
  - [0004. Повторные запуски без обращения к Hugging Face](specs/0004-offline-model-reuse.md)
  - [0005. MP3 по умолчанию и удаление промежуточного WAV](specs/0005-mp3-default.md)
  - [0006. Голос `dima` по умолчанию](specs/0006-default-voice-dima.md)
  - [0007. Пакетная обработка папки](specs/0007-batch-mode.md)
  - [0008. Аудио рядом с исходником и удаление временного текста](specs/0008-audio-next-to-source.md)
  - [0009. Один аргумент: файл или папка](specs/0009-single-argument.md)

Спеки 0002–0009 ретроспективные: они восстановлены по истории коммитов
(см. раздел 9 стандарта).

| Коммит | Спека |
|---|---|
| `ab47609` init | 0002 |
| `7b26c09` fixed model place problem | 0003 |
| `d3acb64` fixed model download | 0004, 0005, 0006 |
| `49bb480` remove intermediate wav in mp3 mode | 0005 |
| `210a94a` package mode | 0007 |
| `08e3cfe` default output folder by input folder | 0008 |
| `80a37f8` one arg support | 0009 |

Пользовательская документация и инструкции по запуску — в
[README.md](../README.md), правила работы с кодом — в
[AGENTS.md](../AGENTS.md).
