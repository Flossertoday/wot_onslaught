# Replay feasibility tools

Run commands from the repository root. Inputs are read-only. Outputs contain no player names
or account IDs; they retain replay paths, hashes, battle IDs and requested performance/rank data.

Tested environment: Python from the local Anaconda installation, scipy 1.17.1,
cryptography 46.0.5, xdis 6.3.0. xdis was installed only into ignored `.drafts/deps`;
it is required only for the optional client bytecode evidence collector.

```powershell
python tools/replay_analysis/audit.py --cutoff 2026-09-30T13:32:22+08:00 --output DOCS/status/evidence/2026-09-30-replay-audit
python tools/replay_analysis/stream_audit.py --battles DOCS/status/evidence/2026-09-30-replay-audit/battles.csv --output DOCS/status/evidence/2026-09-30-replay-audit/stream-audit.json
python tools/replay_analysis/client_evidence.py --dependencies .drafts/deps --output DOCS/status/evidence/2026-09-30-replay-audit/client-bytecode.json
python -m unittest discover -s tools/replay_analysis -p test_*.py
```

`--game` defaults to `C:/Games/World_of_Tanks_CN`; `--replays` defaults to `replays`.
The cutoff is mandatory and must include a UTC offset. For a new snapshot, choose a new
output directory so the checked-in historical evidence is retained.

Files:

- `audit.py`: read bounded JSON blocks; validate identities/teams/vehicle/time; classify
  missing or invalid results; resolve map spawn and vehicle class definitions; export CSV
  and exploratory map summaries. Error records are preserved and the command fails if any
  file could not be processed. Old files are inventoried, but only in-window files enter summaries.
- `packed_xml.py`: read-only packed-XML decoder reused from the local
  `wot_teammate_bulb/tools/research` project; format reference is named in its header.
- `stream_audit.py`: decrypt/decompress then inspect packet framing, phase values and
  result-packet presence; no pickle execution, event simulation or outcome inference.
- `client_evidence.py`: selected Python 2.7 bytecode disassembly, never import/execute game code.
- `field_inventory.py`: verify replay hashes and cross-check all 19 participant metrics plus
  self rating against the CSV snapshot; report field coverage and observed prestige/rating
  distributions without names or account IDs. Run with `--output <report.json>`.

Important: `spawn_points` is the **map configuration**, not the actual vehicle position.
Header-only vehicles are not promoted to confirmed final vehicles. Rank is categorical;
exact pre/post rating is available only for self. CSV complex fields use JSON, missing values
are empty cells, and files use UTF-8 with BOM for desktop spreadsheet readability.

Fisher/BH results assume independent known-result battles and do not correct missingness,
confounding or time correlation. Treat them as exploration, not conclusive anomaly detection.
See [field rules](../../DOCS/facts/replay-fields.md) and
[current findings](../../DOCS/status/2026-09-30-analysis-feasibility.md).
