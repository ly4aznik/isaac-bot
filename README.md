# Isaac Bot

Экспериментальный Windows-бот для The Binding of Isaac: Python управляет запуском, навигацией и боем, а собственный Lua-мод передаёт состояние игры и принимает действия через UDP localhost.

Это текущая реализация правил и инфраструктуры экспериментов; обучение полноценного RL-агента описано в плане развития.

## Возможности

- Запуск обычного забега и проверка Lua handshake.
- Наблюдения, запись действий и событий, измерение работы моста.
- Навигация к дверям и координатам, бой и уклонение.
- Схематическая визуализация и совместный экран игры и модели.
- Скрипты захвата и исходники Remotion-композиции.

## Требования и подготовка

Windows, современный Python 3 и собственная установленная копия игры с поддержкой Lua-модов. Основной Python-контроллер использует стандартную библиотеку.

По умолчанию контроллер ожидает `game/isaac-ng.exe`. Поместите свою копию игры в локальную `game/` либо настройте `GAME_DIR` в `isaac_bot/controller.py`. Включите мод `isaac_bot_bridge`; его исходники находятся в `game/mods/isaac_bot_bridge/`. Исполняемые файлы и ресурсы игры не входят в репозиторий.

## Запуск

```powershell
python run_bot.py start --smoke-test
python run_bot.py probe
python run_bot.py record --seconds 60
python run_bot.py navigate --door 2
python run_bot.py combat --seconds 60
python run_bot.py studio --layout reels
```

Список команд: `python run_bot.py --help`. Записи забегов сохраняются в локальной `runs/`.

## Проверка

```powershell
python -m unittest discover -s tests
```

Проверка взаимодействия с игрой выполняется отдельно через `start --smoke-test` и `probe` и требует работающей игры.

## Видеокомпозиция

```powershell
cd isaac-reels
npm ci
npm run dev
```

Нужны Node.js/npm и локально подготовленные записи; медиа не включены в Git. Проверка исходников: `npm run lint`.

## Документация

[Архитектура](docs/ARCHITECTURE.md), [протокол](docs/PROTOCOL.md), [навигация](docs/NAVIGATION.md), [бой](docs/COMBAT.md), [визуализация](docs/VISUALIZATION.md), [план развития](docs/ROADMAP.md).
