# Public source release readiness — 2026-10-02

The GitHub repository was already public, but its default startup assumed the
author's game location and silently displayed the author's historical dataset
when extraction failed. It also lacked a root README, a license, dependency
instructions and automated checks. Those were release blockers for a new user.

## Changes prepared

- Machine paths now come from explicit flags, environment variables or ignored
  `explorer.local.json`. Config-relative paths are anchored to the config file.
  An explicit game override also changes its default replay source.
- The Windows launcher prompts for a game folder on first run and saves it locally.
  Python 3.11+ is required; ordinary GUI startup and extraction need no third-party packages.
- A fresh checkout without game settings or recordings opens an empty local explorer.
  Failed extraction also shows no matches and an error message. Historical research
  data is displayed only with explicit `--demo`, visibly labelled as demo data.
- Missing replay downloads return HTTP 404; changed data returns 409; paths outside
  the local replay archive are refused. The UI hides downloads for missing demo recordings.
- MIT licensing was selected by the user. Root setup instructions, configuration
  example, format references and pinned optional research dependencies are included.
- GitHub Actions tests Windows and Ubuntu with Python 3.11 and 3.13, frontend checks,
  and the rule that raw recordings/cache databases cannot be tracked.

## Local verification

- 63 Python tests passed: 33 Explorer/launcher/startup/HTTP tests and 30 research tests.
- JavaScript syntax and all three frontend regression programs passed.
- The actual extractor processed a synthetic relocated game folder using `python -S`,
  verifying that normal extraction works without site packages or the author's install.
- Two real private recordings (one final report and one missing report) were synchronized
  using explicitly supplied paths and analyzed with `python -S`. The full 14-player
  scoreboard was extracted; the HTTP replay download matched its SHA-256; source
  recordings remained unchanged. Private test inputs and screenshots are ignored.
- Browser checks confirmed empty startup, explicit demo labelling, absent demo download
  controls and real replay details, with no captured JavaScript errors.
- Markdown relative links, ignore rules and whitespace checks passed.
- An export of the committed source (without private settings, recordings or caches)
  passed empty and demo startup from an unrelated directory with `python -S`;
  all browser assets loaded in both modes.
- Initial hosted Windows CI exposed a fixture expectation comparing a DOS short-name
  temp directory against its resolved full path. The fixture now resolves its root;
  runtime path resolution already returned the correct full path.

## Release scope

This is a Windows source release for the verified CN Onslaught format, not an EXE
distribution or a promise of compatibility with every region/game version.
Game resources and raw recordings are excluded. The anonymized historical research
dataset remains included for reproducible tests and explicit demo mode; it retains
battle IDs, filenames, hashes and performance/rank statistics.

The 30% missing-report win-rate assumption remains a labelled scenario, and all
missing rating/performance values remain unknown. Replay timestamps use UTC+08.

Merge and release publication require the user's approval under the repository's
Git rules. The prepared branch is `codex/public-release-readiness`; `main` is not
modified by this readiness task.
