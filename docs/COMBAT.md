# Stage 3 — Targeting and shooting

Run the combat controller in the current room:

```powershell
python run_bot.py combat --seconds 60
```

## Policy

1. Keep the current living target while it exists.
2. Otherwise select the nearest enemy.
3. Solve constant-velocity interception using enemy position/velocity and an
   approximate tear speed.
4. Publish the predicted intercept point as the controller's current goal.
5. Shoot continuously toward that point.
6. Retreat below the minimum range, approach beyond the maximum range, and use
   a gentle orbit inside the preferred range.
7. Reject movement that leads into a blocked collision-grid cell.
8. Switch targets after the current enemy disappears.
9. Stop and clear the goal when the room is clear or the timeout expires.

Stage 4 extends this policy with short-horizon hostile-projectile and enemy
contact prediction. See `AVOIDANCE.md` for the movement scoring model.

## Metrics

The command reports room-clear success, elapsed time, control frames, initial
and remaining enemies, observed kills, unique tears, target switches, and health
lost.

First verified room: 2 enemies, cleared in 3.578 seconds (104 control frames),
2 kills, 0 health lost.

Player-tear telemetry was verified separately after fixing Repentance+
`BitSet128` flag serialization: 38 observations contained 7 unique tears during
a 2.5-second firing test. The Studio world model renders these as light-blue
projectiles with velocity vectors.
