# Replay initialization - 2026-09-30

Protocol: `DOCS/policy/replay_protocal.md`.

- Input: 512 replay files.
- Kept: 431 Onslaught replays; header `gameplayID=comp7`, `battleType=43`.
- Removed from replays: 81 regular replays; header `gameplayID=ctf`, `battleType=1`. Local recovery copies are in ignored `.drafts/non-onslaught/`.
- Every mode classification also agrees with the filename Onslaught marker.
- Map folders use the header `mapName`, replacing only the separator after the numeric ID with a hyphen; map variants and remaining underscores are preserved.
- All 512 files passed SHA-256 comparison before and after moving.
- `ReplayCache.db` is preserved unchanged; it is a cache, not a replay inventory.
- Original inputs remain recoverable in the baseline Git commit on `main`.

| Map folder | Replays |
| --- | ---: |
| 04-himmelsdorf | 23 |
| 05-prohorovka | 20 |
| 06-ensk | 16 |
| 08-ruinberg | 16 |
| 10-hills | 19 |
| 11-murovanka | 18 |
| 114-czech | 20 |
| 115-sweden_comp7_nb | 18 |
| 121-lost_paradise_v | 20 |
| 127-japort | 19 |
| 128-last_frontier_v_comp7_nb | 24 |
| 14-siegfried_line | 22 |
| 18-cliff | 17 |
| 23-westfeld | 26 |
| 28-desert_comp7_nb | 13 |
| 29-el_hallouf | 14 |
| 31-airfield | 24 |
| 35-steppes_comp7_nb | 20 |
| 44-north_america | 19 |
| 63-tundra | 21 |
| 95-lost_city_ctf | 18 |
| 99-poland | 24 |
