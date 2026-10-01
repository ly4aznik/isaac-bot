# Визуализация внутреннего представления

Запуск:

```powershell
python run_bot.py visualize
python run_bot.py studio
python run_bot.py studio --layout reels
python run_bot.py studio --layout side
```

Окно показывает только данные структурированного наблюдения бота — изображения
игры в нём нет. Поэтому его можно честно подписывать в видео как «что видит ИИ».

## Отображение

- коллизионная сетка и разные классы препятствий;
- открытые и закрытые двери с номерами slot;
- игрок и вектор его скорости;
- враги и полосы здоровья;
- снаряды и прогнозируемое направление полёта;
- pickups;
- выбранная цель, путь A* и waypoint;
- номер кадра, комнаты, этажа, здоровье, ресурсы и ack действия.

The interface is entirely in English and is read-only. It has no target-selection
or agent-control buttons. The controller publishes its real current goal through
the protocol; the visualizer renders that goal and reconstructs the corresponding
A* path. When no controller goal exists, it displays `NONE` and `IDLE`.

`F11` enables fullscreen recording mode; `Escape` returns to a window.

Для OBS удобно захватывать окно с заголовком
`Isaac Bot — внутреннее представление`. Сцена масштабируется вместе с окном и
сохраняет пропорции игровой комнаты.

`studio` creates one visible `Isaac Bot Studio` window: a live capture of the
real game is shown on the left and the passive world model on the right. Direct
Win32 reparenting is not used because the game's DirectX process terminates when
its native window receives `SetParent`. `F11` toggles the whole composite
fullscreen. Closing Studio does not terminate the game.

Isaac itself stays in windowed mode (`Fullscreen=0`). Studio fullscreen changes
only the composite recording window and never sends a fullscreen command to the
game.

Studio has two deterministic layouts:

- `reels` (default): game on top, internal model below, vertical 9:16-oriented
  window for Shorts/Reels/TikTok capture;
- `side`: game on the left and internal model on the right for 16:9 videos.
