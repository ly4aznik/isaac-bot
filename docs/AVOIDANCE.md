# Stage 4 — Projectile avoidance

The combat controller predicts short-term collisions instead of reacting only
to the current projectile position.

## Decision loop

1. Build candidate movement vectors: preferred combat movement, idle, four
   cardinal directions, and four diagonals.
2. Reject candidates whose sampled path crosses a blocked collision-grid cell.
3. For every hostile projectile, solve the closest approach between its
   constant velocity and the candidate player velocity over 24 game frames.
4. Penalize collision distance and time-to-collision inside a safety radius.
5. Apply a shorter contact-risk prediction to living enemies so a bullet dodge
   does not route Isaac through another enemy.
6. Select the lowest-risk movement while preserving the independently computed
   shooting vector.

## Metrics

Each combat result includes:

- `projectile_frames`: frames containing hostile projectiles;
- `danger_frames`: frames where preferred movement predicted a collision;
- `dodge_frames`: frames where avoidance overrode preferred movement;
- `contact_danger_frames`: frames with predicted enemy contact;
- `closest_predicted_projectile_distance`: smallest predicted clearance.

The first live stress test entered a room containing 14 enemies. Before contact
risk was added it observed projectiles in 283 frames and issued 152 dodges, but
still died after colliding in the crowded room. That failure became the contact
hazard regression test and motivated the second risk layer.

After adding contact prediction, the next live run cleared a four-enemy room
with 1 health lost, then survived the following ten-enemy room for the full
45-second combat timeout with 1 additional health lost. It issued 111 contact
avoidance overrides across both rooms. The run stopped on timeout rather than
death; prolonged cautious positioning is now a known tuning issue.

## Current limitations

- projectile motion is assumed constant over the prediction horizon;
- lasers, explosions, creep and persistent area effects are not modeled yet;
- the 50% damage-reduction criterion still requires a repeatable benchmark with
  identical rooms/seeds and a stage-3 baseline run.
