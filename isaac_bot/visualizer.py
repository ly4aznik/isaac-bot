"""Passive live schematic of exactly the state and goal seen by the bot."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from .bridge import LuaBridge
from .navigation import GridMap, Navigator


C = {
    "background": "#0b0f14", "floor": "#151c24", "grid": "#26313d",
    "wall": "#526170", "pit": "#142d3b", "object": "#574933",
    "player": "#5de4e7", "enemy": "#ff667a", "projectile": "#ff9f43",
    "tear": "#75baff", "pickup": "#ffd166", "door_open": "#66d17a", "door_closed": "#768390",
    "path": "#bb86fc", "target": "#f4f1de", "text": "#dbe7f3", "muted": "#8291a3",
}


class SchematicVisualizer:
    def __init__(self, root: tk.Misc, embedded: bool = False, compact: bool = False) -> None:
        self.root = root
        self.embedded = embedded
        self.compact = compact
        if not embedded:
            self.root.title("Isaac Bot — Internal World Model")  # type: ignore[attr-defined]
            self.root.configure(bg=C["background"])
            self.root.minsize(900, 620)  # type: ignore[attr-defined]
        self.bridge = LuaBridge(timeout=0.001, role="observer")
        self.observation: dict[str, Any] | None = None
        self.navigator: Navigator | None = None
        self.goal_key: tuple[float, float, str] | None = None
        self.transform: tuple[float, float, float] | None = None
        self.tick_count = 0
        self.fullscreen = False
        self.status = tk.StringVar(value="WAITING FOR TELEMETRY")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=C["background"])
        style.configure("TLabel", background=C["background"], foreground=C["text"])

        shell = ttk.Frame(root, padding=12)
        shell.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(shell, bg=C["floor"], highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _event: self.draw())

        self.telemetry: ttk.Label | None = None
        self.goal_text: ttk.Label | None = None
        if compact:
            panel = None
        else:
            panel = ttk.Frame(shell, padding=(14, 2, 2, 2), width=235)
        if panel is not None:
            panel.pack(side="right", fill="y")
            panel.pack_propagate(False)
            ttk.Label(panel, text="ISAAC BOT / WORLD MODEL", font=("Consolas", 14, "bold")).pack(anchor="w", pady=(0, 12))
            self.telemetry = ttk.Label(panel, text="", font=("Consolas", 10), justify="left")
            self.telemetry.pack(anchor="w", fill="x")
            ttk.Separator(panel).pack(fill="x", pady=12)
            ttk.Label(panel, text="CURRENT GOAL", font=("Consolas", 10, "bold")).pack(anchor="w")
            self.goal_text = ttk.Label(panel, text="NONE", font=("Consolas", 11), wraplength=215, justify="left")
            self.goal_text.pack(anchor="w", pady=(3, 8))
            ttk.Label(panel, text="PLANNER STATUS", font=("Consolas", 10, "bold")).pack(anchor="w")
            ttk.Label(panel, textvariable=self.status, wraplength=215, justify="left").pack(anchor="w", pady=(3, 0))
            ttk.Separator(panel).pack(fill="x", pady=12)
            ttk.Label(panel, text="LEGEND", font=("Consolas", 10, "bold")).pack(anchor="w")
            for label, color in [
                ("● PLAYER", C["player"]), ("● ENEMY", C["enemy"]),
                ("• PROJECTILE", C["projectile"]), ("◆ PICKUP", C["pickup"]),
                ("• PLAYER TEAR", C["tear"]),
                ("━ A* PATH", C["path"]), ("× CURRENT GOAL", C["target"]),
            ]:
                tk.Label(panel, text=label, fg=color, bg=C["background"], font=("Consolas", 10)).pack(anchor="w")
            ttk.Label(panel, text="F11  FULLSCREEN\nESC  WINDOWED", foreground=C["muted"], font=("Consolas", 9)).pack(anchor="w", side="bottom")

        if not embedded:
            self.root.bind("<F11>", self._toggle_fullscreen)
            self.root.bind("<Escape>", self._leave_fullscreen)
            self.root.protocol("WM_DELETE_WINDOW", self.close)  # type: ignore[attr-defined]
        self.root.after(1, self.tick)

    def close(self) -> None:
        self.bridge.close()
        if not self.embedded:
            self.root.destroy()

    def _toggle_fullscreen(self, _event: object = None) -> None:
        self.fullscreen = not self.fullscreen
        self.root.attributes("-fullscreen", self.fullscreen)

    def _leave_fullscreen(self, _event: object = None) -> None:
        if self.fullscreen:
            self.fullscreen = False
            self.root.attributes("-fullscreen", False)

    def _update_goal(self) -> None:
        if not self.observation:
            return
        goal = self.observation.get("goal")
        if not goal:
            self.goal_key = None
            self.navigator = None
            if self.goal_text:
                self.goal_text.configure(text="NONE")
            self.status.set("IDLE — NO ACTIVE GOAL")
            return
        key = (float(goal["x"]), float(goal["y"]), str(goal["label"]))
        if self.goal_text:
            self.goal_text.configure(text=f"{key[2]}\nX {key[0]:.1f}   Y {key[1]:.1f}")
        if key == self.goal_key and self.navigator:
            return
        self.goal_key = key
        try:
            self.navigator = Navigator()
            self.navigator.plan(self.observation, (key[0], key[1]))
            self.status.set(f"PATH READY — {len(self.navigator.path)} CELLS")
        except ValueError as error:
            self.navigator = None
            self.status.set(f"NO PATH — {error}")

    def tick(self) -> None:
        self.tick_count += 1
        if self.tick_count % 30 == 0:
            self.bridge.observe()
        for _ in range(24):
            message = self.bridge.receive()
            if message is None:
                break
            if message.get("type") == "observation":
                room_changed = self.observation and message["room_index"] != self.observation["room_index"]
                self.observation = message
                if room_changed:
                    self.goal_key = None
                    self.navigator = None
                self._update_goal()
            elif message.get("type") == "event" and message.get("event") not in {"auto_restart"}:
                self.status.set(f"EVENT — {str(message.get('event')).upper()}")
        self.draw()
        self.root.after(33, self.tick)

    def world_to_canvas(self, x: float, y: float) -> tuple[float, float]:
        if self.transform is None:
            return x, y
        scale, ox, oy = self.transform
        return x * scale + ox, y * scale + oy

    def draw(self) -> None:
        cv = self.canvas
        cv.delete("all")
        obs = self.observation
        if not obs:
            cv.create_text(30, 30, anchor="nw", fill=C["muted"], text="WAITING FOR GAME STATE", font=("Consolas", 14))
            return
        grid = GridMap.from_observation(obs)
        width, height = (grid.width - 1) * grid.cell_size, (grid.height - 1) * grid.cell_size
        margin = 34.0
        scale = min((cv.winfo_width() - margin*2) / max(1, width), (cv.winfo_height() - margin*2) / max(1, height))
        self.transform = scale, (cv.winfo_width()-width*scale)/2-grid.origin_x*scale, (cv.winfo_height()-height*scale)/2-grid.origin_y*scale
        half = grid.cell_size * scale / 2

        for y in range(grid.height):
            for x in range(grid.width):
                collision = grid.cells[grid.index((x, y))]
                cx, cy = self.world_to_canvas(*grid.cell_to_world((x, y)))
                fill = C["floor"]
                if collision == 1: fill = C["pit"]
                elif collision == 2: fill = C["object"]
                elif collision >= 3: fill = C["wall"]
                cv.create_rectangle(cx-half, cy-half, cx+half, cy+half, fill=fill, outline=C["grid"])

        if self.navigator and self.navigator.path:
            points = [self.world_to_canvas(*grid.cell_to_world(cell)) for cell in self.navigator.path]
            cv.create_line(*[n for point in points for n in point], fill=C["path"], width=4, smooth=True)
            for i, (x, y) in enumerate(points):
                r = 6 if i in (0, len(points)-1) else 3
                cv.create_oval(x-r, y-r, x+r, y+r, fill=C["path"], outline="")
        if self.goal_key:
            x, y = self.world_to_canvas(self.goal_key[0], self.goal_key[1])
            cv.create_line(x-10, y, x+10, y, fill=C["target"], width=2)
            cv.create_line(x, y-10, x, y+10, fill=C["target"], width=2)

        for door in obs["doors"]:
            x, y = self.world_to_canvas(door["x"], door["y"])
            color = C["door_open"] if door["open"] else C["door_closed"]
            cv.create_rectangle(x-12, y-12, x+12, y+12, fill=color, outline="")
            cv.create_text(x, y-19, text=f"D{door['slot']}", fill=C["text"], font=("Consolas", 9))

        counts = {"enemy": 0, "projectile": 0, "tear": 0, "pickup": 0}
        for entity in obs["entities"]:
            kind = entity["kind"]
            counts[kind] = counts.get(kind, 0) + 1
            x, y = self.world_to_canvas(entity["x"], entity["y"])
            if kind == "enemy":
                r = max(6, min(18, entity["size"] * scale))
                cv.create_oval(x-r, y-r, x+r, y+r, fill=C["enemy"], outline="")
                if entity["max_hp"] > 0:
                    ratio = max(0.0, min(1.0, entity["hp"] / entity["max_hp"]))
                    cv.create_rectangle(x-16, y-r-8, x+16, y-r-5, fill=C["grid"], outline="")
                    cv.create_rectangle(x-16, y-r-8, x-16+32*ratio, y-r-5, fill=C["enemy"], outline="")
            elif kind == "projectile":
                cv.create_oval(x-4, y-4, x+4, y+4, fill=C["projectile"], outline="")
                ex, ey = self.world_to_canvas(entity["x"]+entity["vx"]*12, entity["y"]+entity["vy"]*12)
                cv.create_line(x, y, ex, ey, fill=C["projectile"], width=2, arrow="last")
            elif kind == "tear":
                cv.create_oval(x-4, y-4, x+4, y+4, fill=C["tear"], outline="")
                ex, ey = self.world_to_canvas(entity["x"]+entity["vx"]*8, entity["y"]+entity["vy"]*8)
                cv.create_line(x, y, ex, ey, fill=C["tear"], width=2)
            elif kind == "pickup":
                cv.create_polygon(x, y-8, x+8, y, x, y+8, x-8, y, fill=C["pickup"], outline="")

        player = obs["player"]
        px, py = self.world_to_canvas(player["x"], player["y"])
        cv.create_oval(px-10, py-10, px+10, py+10, fill=C["player"], outline="")
        vx, vy = self.world_to_canvas(player["x"]+player["vx"]*10, player["y"]+player["vy"]*10)
        cv.create_line(px, py, vx, vy, fill=C["player"], width=2, arrow="last")

        telemetry_text = (
            f"FRAME        {obs['frame']}\nRUN / ROOM   {obs['run_id']} / {obs['room_index']}\n"
            f"STAGE        {obs['stage']}:{obs['stage_type']}\nPOSITION     {player['x']:.1f}, {player['y']:.1f}\n"
            f"VELOCITY     {player['vx']:.2f}, {player['vy']:.2f}\nHEALTH       {player['hearts']} + {player['soul_hearts']}\n"
            f"RESOURCES    C{player['coins']} K{player['keys']} B{player['bombs']}\n"
            f"ENTITIES     E{counts['enemy']} P{counts['projectile']} T{counts['tear']} I{counts['pickup']}\n"
            f"GRID         {grid.width} x {grid.height}\nACTION ACK   {obs['ack']}"
        )
        if self.telemetry:
            self.telemetry.configure(text=telemetry_text)
        if self.compact:
            goal_label = self.goal_key[2] if self.goal_key else "NONE"
            cv.create_text(12, 12, anchor="nw", text=f"WORLD MODEL   ROOM {obs['room_index']}   FRAME {obs['frame']}", fill=C["text"], font=("Consolas", 10, "bold"))
            cv.create_text(12, 31, anchor="nw", text=f"GOAL {goal_label}   HP {player['hearts']}+{player['soul_hearts']}   E {counts['enemy']}  P {counts['projectile']}  T {counts['tear']}", fill=C["muted"], font=("Consolas", 9))


def run_visualizer() -> None:
    root = tk.Tk()
    SchematicVisualizer(root)
    root.mainloop()
