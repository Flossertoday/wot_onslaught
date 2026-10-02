"""First-run console setup for the Windows launcher; no game files are modified."""
import json
import sys
from pathlib import Path

if sys.version_info < (3, 11):
    raise SystemExit('Python 3.11 or newer is required')

import server
from local_paths import DEFAULT_CONFIG, local_paths


def main():
    if not sys.argv[1:]:
        try:
            game, _ = local_paths()
        except (OSError, ValueError) as error:
            print(f'Cannot read local settings: {error}', file=sys.stderr)
            return 1
        if game is None and sys.stdin.isatty():
            print('First run: select your World of Tanks installation folder.')
            print('It must contain res/packages/scripts.pkg. Your game and replays stay local.')
            value = input('Game folder (Enter to open an empty explorer): ').strip().strip('"')
            if value:
                game = Path(value).expanduser().resolve()
                if not (game / 'res/packages/scripts.pkg').is_file():
                    print(f'Missing {game / "res/packages/scripts.pkg"}', file=sys.stderr)
                    return 1
                try:
                    DEFAULT_CONFIG.write_text(json.dumps({'game': str(game)}, indent=2) + '\n', encoding='utf-8')
                except OSError as error:
                    print(f'Cannot save local settings: {error}', file=sys.stderr)
                    return 1
                print(f'Saved settings to {DEFAULT_CONFIG}')
    return server.main(['--open-browser', *sys.argv[1:]])


if __name__ == '__main__':
    raise SystemExit(main())
