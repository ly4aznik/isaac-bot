# Floor exploration

The floor controller keeps persistent memory for the current stage instead of
choosing the nearest door independently in every room.

## Stored world model

- room index and room type;
- observed doors, target room index/type and game-provided visit count;
- transitions and intentional backtracks;
- discovered special room types;
- current stage and stage type.

## Route policy

1. Prefer an accessible unvisited treasure room.
2. Prefer a shop when the player has useful spending money.
3. Explore ordinary accessible frontiers.
4. Defer the boss until higher-value frontiers are exhausted.
5. If the best frontier is not adjacent, use BFS over known room connections
   and take the first door on the shortest route.
6. Never plan toward a closed remote door or a room already marked visited by
   the game, even when the Python controller attached mid-floor.

After clearing a room the controller collects reachable free hearts (when
needed), coins, keys, bombs, grab bags, collectibles and trinkets. Unreachable
pickups are recorded and skipped rather than terminating the run. Shop items
and priced pickups are left for a later economy policy.

Boss rooms expose trapdoors/stairs through `floor_exits`; the controller walks
onto the exit and confirms that `(stage, stage_type)` changed before resetting
its graph.

## Verified behavior

- 26 automated tests pass;
- stale invulnerable targets are replaced after 120 frames without damage;
- the clean live run explored 6 unique rooms, including the treasure room;
- it collected a trinket and a bomb without taking combat damage;
- 9 transitions included 4 intentional backtracks and no navigation loop;
- the run stopped with `floor_explored_no_exit` because no known frontier was
  accessible with the current resources.

## Remaining work

- bomb suspected secret-room doors;
- decide when to spend keys and money;
- handle inaccessible pickups that require flight, bombs or special movement;
- validate boss defeat and trapdoor transition on a repeatable seed;
- persist the graph across controller restarts in the middle of a floor.
