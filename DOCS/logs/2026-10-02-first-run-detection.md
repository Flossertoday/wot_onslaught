# First-run game detection — 2026-10-02

The Windows launcher now offers installation discovery before manual setup when
started without arguments and without a configured game directory.

Discovery reads per-user and machine uninstall records in both Windows registry
views, then probes a finite list of common game folder names on fixed local
drives. It never recursively traverses directories. Candidates must contain
`WorldOfTanks.exe` and `res/packages/scripts.pkg`; a replay directory is not
required because recording may not have been enabled yet. Matches are resolved
and deduplicated.

A separate standard-library Python worker has a two-second timeout. This keeps
slow or inaccessible filesystem paths from blocking initialization. Each match
is streamed immediately, so results already found remain available if a later
probe stalls. Discovery does not establish region/version compatibility.

The launcher shows each candidate and its replay source. Enter accepts a single
candidate; multiple candidates require selection. Users can paste another path,
choose manual entry, or open an empty explorer. No match or worker failure uses
the existing manual fallback. Saved configuration, environment overrides,
explicit arguments and noninteractive startup bypass discovery. Existing
`replay_source` settings survive saving the selected game directory.

## Verification

- Baseline: all 63 existing Python tests passed before edits.
- Focused detection and launcher tests passed, covering real worker termination,
  partial results on timeout, Unicode/spaced paths, duplicates, incomplete
  installs, unreadable candidates, missing replay directories, multiple matches,
  manual fallback/override, saved configuration and custom replay sources.
- Read-only detection using `python -S` found this machine's real CN installation
  and its existing replay directory in 0.187 seconds.
- A first-run smoke check used the real detector with temporary settings, saved
  the selected game directory, verified its derived replay source, and verified
  that a second launch reused the settings without searching or prompting.
  Server startup was substituted for this check, so no recordings were copied.
- All 80 Python tests passed after the change: 50 Explorer tests and 30 research
  tests. Git whitespace validation passed.

The change is prepared on `codex/first-run-detection`; merging requires separate
user authorization under the repository Git rules.
