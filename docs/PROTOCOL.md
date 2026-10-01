# Isaac Bot protocol v1

Транспорт: UDP, только `127.0.0.1:21666`. Lua является сервером, Python
отправляет heartbeat/action и становится текущим получателем телеметрии.

## Python → Lua

```text
V1 HELLO
V1 ACTION <seq> <move_x> <move_y> <shoot_x> <shoot_y> <bomb> <item> <pill> <card> <drop>
V1 COMMAND AUTO_RESTART <0|1>
V1 COMMAND RESTART
V1 COMMAND NEW_RUN
V1 COMMAND PAUSE_AGENT
V1 COMMAND GOAL <x> <y> <label>
V1 COMMAND CLEAR_GOAL
V1 OBSERVE
```

Оси ограничены диапазоном `[-1, 1]`. Дискретные кнопки передаются как `0/1`.
Устаревший `seq` игнорируется. Если action не приходит 15 игровых кадров, Lua
перестаёт переопределять ввод и возвращает управление человеку.
`HELLO` открывает новую локальную управляющую сессию и сбрасывает ожидаемый
sequence, поэтому Python можно безопасно перезапускать между экспериментами.
`OBSERVE` registers a passive telemetry subscriber. It does not claim control,
reset sequence numbers, or inject actions, so the visualizer can run alongside
the bot. Goal commands expose the controller's actual current objective.

## Lua → Python

Все ответы — однострочный JSON с полями `v` и `type`.

- `hello`: версия мода, кадр и run ID;
- `observation`: кадр, ack, игрок, комната, двери,
  enemies/projectiles/player tears/pickups;
- `event`: `game_started`, `game_end`, `new_room`, `new_level`, `room_clear`,
  `damage`, `npc_death`, `auto_restart`.

`ack` — последний применённый sequence действия. `run_id` меняется при новом
ране, `room_visit` — при входе в комнату. Python отклоняет другую версию
протокола и считает повреждённые пакеты и разрывы последовательности кадров.
